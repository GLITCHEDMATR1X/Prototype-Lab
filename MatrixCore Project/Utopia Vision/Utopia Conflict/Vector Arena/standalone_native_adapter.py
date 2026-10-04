"""Standalone built-in Vector Arena first-person arcade shooter.

Vector Arena is intentionally a native Panda3D game, not a child-window
route.  This pass keeps the presentation-grade first-person arcade shooter and adds between-set mutation choices on top of tactical horde pressure: ground-level camera, cursor-look, hitscan
pulse weapon, cover lanes, spawn gates, enemy waves, class-based menacing enemy models, solid armored hardlight materials, and a changing hardlight scenery shell.

ESC exits standalone builds.
H toggles the optional local help/status panel.  The reticle and minimal combat
readout stay visible because they are part of the arcade shooter presentation,
not legacy debug UI.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

import sys as _sys

from direct.gui.OnscreenText import OnscreenText

# 282.50: HoloVerse loads this adapter by file path, so Vector Arena's own modules are not on
# sys.path (the standalone main.py gets them from its folder). Add the folder only while they
# are imported, so nothing of Vector Arena stays importable by name inside HoloVerse.
_VA_DIR = str(Path(__file__).resolve().parent)
_VA_ADDED_PATH = _VA_DIR not in _sys.path
if _VA_ADDED_PATH:
    _sys.path.insert(0, _VA_DIR)
try:
    from vector_arena_audio import VectorArenaAudioRuntime
    from vector_arena_waves import WAVE_SET_SIZE, MAX_ACTIVE_THREATS, WAVE_KINDS, GATE_LABELS, wave_kind_for, build_wave_plan
    from vector_arena_progression import upgrade_choices, upgrade_effects, arena_mutation_for_set, apply_mutation_to_plan
    from vector_arena_evolution import apply_enemy_progression, encounter_doctrine_for, guardian_phase_for, guardian_phase_profile
    from vector_arena_arenas import (
        BASE_ARENA_RADIUS, MAX_ARENA_RADIUS, ARENA_FAMILIES, arena_profile_for_set,
        spawn_points_for_profile, breach_points_for_profile, hazard_points_for_profile,
        architecture_pieces_for_profile, validate_architecture, first_architecture_hit,
    )
finally:
    if _VA_ADDED_PATH:
        try:
            _sys.path.remove(_VA_DIR)
        except ValueError:
            pass
from panda3d.core import (
    AmbientLight,
    CardMaker,
    DirectionalLight,
    KeyboardButton,
    LineSegs,
    MouseButton,
    NodePath,
    TextNode,
    TransparencyAttrib,
    Vec3,
    Vec4,
    WindowProperties,
    Filename,
)

MODE_TITLE = "Vector Arena"
MODE_ID = "vector_arena"
MODE_STATUS = "VECTOR ARENA // STRATEGIC ARCHITECTURE PASS // TAB RETURN IN HOLOVERSE / ESC PAUSE / H HELP"

EYE_HEIGHT = 4.4
ENEMY_CAP = 32
PROJECTILE_CAP = 48  # hitscan beam/tracer pool; kept under the original projectile contract name
IMPACT_CAP = 48
SPAWN_PULSE_CAP = 10
KILL_BURST_CAP = 24
MUZZLE_FLASH_CAP = 12
REPULSOR_WAVE_CAP = 8
HEAT_VENT_SPARK_CAP = 16
BREACH_CORE_CAP = 3
MAX_HEAT = 100.0

WEAPON_UPGRADE_TIERS = (
    {
        "rank": 1,
        "name": "PULSE RIFLE MK I",
        "short": "MK I",
        "unlock_kills": 0,
        "unlock_score": 0,
        "unlock_wave": 1,
        "damage_mult": 1.00,
        "heat_mult": 1.00,
        "cooldown_mult": 1.00,
        "repulsor_mult": 1.00,
    },
    {
        "rank": 2,
        "name": "SPLIT CAPACITOR MK II",
        "short": "MK II",
        "unlock_kills": 4,
        "unlock_score": 700,
        "unlock_wave": 2,
        "damage_mult": 1.16,
        "heat_mult": 0.92,
        "cooldown_mult": 0.92,
        "repulsor_mult": 1.10,
    },
    {
        "rank": 3,
        "name": "ARC LANCE MK III",
        "short": "MK III",
        "unlock_kills": 9,
        "unlock_score": 1800,
        "unlock_wave": 3,
        "damage_mult": 1.32,
        "heat_mult": 0.86,
        "cooldown_mult": 0.86,
        "repulsor_mult": 1.22,
    },
    {
        "rank": 4,
        "name": "OVERDRIVE CORE MK IV",
        "short": "MK IV",
        "unlock_kills": 16,
        "unlock_score": 3600,
        "unlock_wave": 5,
        "damage_mult": 1.52,
        "heat_mult": 0.78,
        "cooldown_mult": 0.80,
        "repulsor_mult": 1.36,
    },
)
WEAPON_UPGRADE_TIER_COUNT = 4
PASS100_PRESENTATION_COMPAT_TOKENS = ("PASS 100 COMBAT PRESENTATION POLISH", "CLASS MARKERS + HP BARS ONLINE")


VECTOR_ARENA_SFX_FILES = {
    "pulse_rifle": "pulse_rifle.wav",
    "repulsor_blast": "repulsor_blast.wav",
    "heat_vent": "heat_vent.wav",
    "enemy_hit": "enemy_hit.wav",
    "enemy_destroyed": "enemy_destroyed.wav",
    "wave_start": "wave_start.wav",
    "player_hit": "player_hit.wav",
    "enemy_spawn": "enemy_spawn.wav",
    "weapon_upgrade": "weapon_upgrade.wav",
    "overheat_warning": "overheat_warning.wav",
    "low_health": "low_health.wav",
    "player_reboot": "player_reboot.wav",
    "ui_toggle": "ui_toggle.wav",
    "breach_spawn": "breach_spawn.wav",
    "breach_hit": "breach_hit.wav",
    "breach_sealed": "breach_sealed.wav",
    "combo_surge": "combo_surge.wav",
    "horde_alarm": "horde_alarm.wav",
    "guardian_alarm": "guardian_alarm.wav",
    "arena_reconstruct": "arena_reconstruct.wav",
    "gate_charge": "gate_charge.wav",
    "flank_alarm": "flank_alarm.wav",
    "guardian_charge": "guardian_charge.wav",
    "guardian_slam": "guardian_slam.wav",
    "hazard_warning": "hazard_warning.wav",
    "hazard_discharge": "hazard_discharge.wav",
    "upgrade_offer": "upgrade_offer.wav",
    "upgrade_select": "upgrade_select.wav",
    "mutation_shift": "mutation_shift.wav",
    "enemy_evolution": "enemy_evolution.wav",
    "guardian_phase2": "guardian_phase2.wav",
    "guardian_phase3": "guardian_phase3.wav",
    "doctrine_shift": "doctrine_shift.wav",
}
VECTOR_ARENA_SFX_MIN_INTERVALS = {
    "pulse_rifle": 0.055,
    "repulsor_blast": 0.35,
    "heat_vent": 0.09,
    "enemy_hit": 0.035,
    "enemy_destroyed": 0.08,
    "wave_start": 0.45,
    "player_hit": 0.18,
    "enemy_spawn": 0.16,
    "weapon_upgrade": 0.9,
    "overheat_warning": 0.8,
    "low_health": 1.5,
    "player_reboot": 1.0,
    "ui_toggle": 0.10,
    "breach_spawn": 0.55,
    "breach_hit": 0.08,
    "breach_sealed": 0.40,
    "combo_surge": 0.85,
    "horde_alarm": 0.9,
    "guardian_alarm": 1.2,
    "arena_reconstruct": 1.0,
    "gate_charge": 0.12,
    "flank_alarm": 0.85,
    "guardian_charge": 0.70,
    "guardian_slam": 0.65,
    "hazard_warning": 0.55,
    "hazard_discharge": 0.20,
    "upgrade_offer": 0.90,
    "upgrade_select": 0.24,
    "mutation_shift": 0.80,
    "enemy_evolution": 0.75,
    "guardian_phase2": 1.20,
    "guardian_phase3": 1.20,
    "doctrine_shift": 1.10,
}
VECTOR_ARENA_SFX_VOLUME_DEFAULTS = {
    "pulse_rifle": 0.62,
    "repulsor_blast": 0.80,
    "heat_vent": 0.52,
    "enemy_hit": 0.46,
    "enemy_destroyed": 0.76,
    "wave_start": 0.62,
    "player_hit": 0.70,
    "enemy_spawn": 0.46,
    "weapon_upgrade": 0.76,
    "overheat_warning": 0.64,
    "low_health": 0.58,
    "player_reboot": 0.78,
    "ui_toggle": 0.36,
    "breach_spawn": 0.58,
    "breach_hit": 0.42,
    "breach_sealed": 0.78,
    "combo_surge": 0.62,
    "horde_alarm": 0.72,
    "guardian_alarm": 0.84,
    "arena_reconstruct": 0.78,
    "gate_charge": 0.48,
    "flank_alarm": 0.62,
    "guardian_charge": 0.78,
    "guardian_slam": 0.88,
    "hazard_warning": 0.56,
    "hazard_discharge": 0.76,
    "upgrade_offer": 0.68,
    "upgrade_select": 0.82,
    "mutation_shift": 0.72,
    "enemy_evolution": 0.68,
    "guardian_phase2": 0.84,
    "guardian_phase3": 0.92,
    "doctrine_shift": 0.70,
}

ENEMY_VARIANTS = (
    {
        "id": "stalker",
        "name": "VECTOR STALKER",
        "color": Vec4(1.00, 0.18, 0.16, 0.95),
        "accent": Vec4(1.00, 0.74, 0.12, 0.82),
        "hp": 42.0,
        "speed": 1.35,
        "damage": 9.0,
        "score": 105,
        "scale": 0.92,
        "aim_radius": 0.012,
    },
    {
        "id": "brute",
        "name": "IRON BRUTE",
        "color": Vec4(1.00, 0.42, 0.08, 0.96),
        "accent": Vec4(1.00, 0.06, 0.04, 0.84),
        "hp": 108.0,
        "speed": 0.62,
        "damage": 20.0,
        "score": 240,
        "scale": 1.34,
        "aim_radius": 0.026,
    },
    {
        "id": "sentry",
        "name": "ARC SENTRY",
        "color": Vec4(0.62, 0.88, 1.00, 0.94),
        "accent": Vec4(0.26, 1.00, 0.96, 0.82),
        "hp": 72.0,
        "speed": 0.82,
        "damage": 13.0,
        "score": 165,
        "scale": 1.05,
        "aim_radius": 0.018,
    },
    {
        "id": "wraith",
        "name": "RED WRAITH",
        "color": Vec4(0.96, 0.10, 1.00, 0.92),
        "accent": Vec4(1.00, 0.18, 0.40, 0.82),
        "hp": 56.0,
        "speed": 1.12,
        "damage": 15.0,
        "score": 190,
        "scale": 1.06,
        "aim_radius": 0.014,
    },
    {
        "id": "guardian",
        "name": "GATE GUARDIAN",
        "color": Vec4(1.00, 0.08, 0.18, 0.98),
        "accent": Vec4(1.00, 0.82, 0.18, 0.88),
        "hp": 170.0,
        "speed": 0.52,
        "damage": 28.0,
        "score": 420,
        "scale": 1.58,
        "aim_radius": 0.034,
    },
)

ENEMY_POOL_VARIANTS = (
    "stalker", "stalker", "stalker", "stalker", "stalker", "stalker", "stalker", "stalker",
    "stalker", "stalker", "stalker", "stalker",
    "wraith", "wraith", "wraith", "wraith", "wraith", "wraith",
    "sentry", "sentry", "sentry", "sentry", "sentry", "sentry",
    "brute", "brute", "brute", "brute", "brute",
    "guardian", "guardian", "guardian",
)

VARIANT_BY_ID = {profile["id"]: profile for profile in ENEMY_VARIANTS}

BREACH_CORE_POINTS = (
    Vec3(-54, 26, 0), Vec3(54, 26, 0), Vec3(-44, -24, 0), Vec3(44, -24, 0),
    Vec3(0, 46, 0), Vec3(0, -38, 0), Vec3(-74, 8, 0), Vec3(74, 8, 0),
)

SCENERY_THEMES = tuple(
    {
        "name": str(item["name"]),
        "primary": Vec4(*item["wire_primary"]),
        "secondary": Vec4(*item["wire_secondary"]),
        "accent": Vec4(*item["wire_accent"]),
        "floor": Vec4(*item["floor"]),
        "sky": tuple(item["sky"]),
    }
    for item in ARENA_FAMILIES
)


@dataclass
class _Enemy:
    node: NodePath
    pos: Vec3
    vel: Vec3
    hp: float
    max_hp: float
    tier: int
    phase: float
    attack_cooldown: float
    variant: str = "stalker"
    display_name: str = "VECTOR STALKER"
    speed_scale: float = 1.0
    damage_scale: float = 1.0
    score_value: int = 100
    aim_radius: float = 0.012
    active: bool = True
    hit_flash: float = 0.0
    death_flash: float = 0.0
    hp_back: NodePath | None = None
    hp_fill: NodePath | None = None
    class_marker: NodePath | None = None
    tactic_role: str = "pressure"
    spawn_gate: int = 1
    formation: int = 0
    guardian_state: str = "idle"
    guardian_timer: float = 3.0
    guardian_attack_kind: str = ""
    guardian_attack_dir: Vec3 | None = None
    guardian_hit_player: bool = False
    guardian_telegraph: NodePath | None = None
    evolution_level: int = 0
    evolution_name: str = "BASELINE FRAME"
    evolution_hp_mult: float = 1.0
    evolution_speed_mult: float = 1.0
    evolution_damage_mult: float = 1.0
    evolution_attack_cooldown_mult: float = 1.0
    evolution_score_mult: float = 1.0
    evolution_lateral_mult: float = 1.0
    evolution_special_cooldown_mult: float = 1.0
    guardian_phase: int = 1


@dataclass
class _Projectile:
    node: NodePath
    age: float = 0.0
    life: float = 0.085
    active: bool = False


@dataclass
class _Impact:
    node: NodePath
    pos: Vec3
    age: float = 0.0
    life: float = 0.34
    active: bool = False


@dataclass
class _SpawnPulse:
    node: NodePath
    pos: Vec3
    age: float = 0.0
    life: float = 0.70
    active: bool = False


@dataclass
class _KillBurst:
    node: NodePath
    pos: Vec3
    age: float = 0.0
    life: float = 0.46
    active: bool = False


@dataclass
class _MuzzleFlash:
    node: NodePath
    pos: Vec3
    age: float = 0.0
    life: float = 0.105
    active: bool = False


@dataclass
class _RepulsorWave:
    node: NodePath
    pos: Vec3
    age: float = 0.0
    life: float = 0.42
    active: bool = False


@dataclass
class _HeatVentSpark:
    node: NodePath
    pos: Vec3
    age: float = 0.0
    life: float = 0.30
    active: bool = False


@dataclass
class _BreachCore:
    node: NodePath
    pos: Vec3
    hp: float = 0.0
    max_hp: float = 0.0
    age: float = 0.0
    life: float = 15.0
    active: bool = False
    sealed: bool = False
    warning_played: bool = False
    audio_loop: object | None = None


@dataclass
class _ArenaHazard:
    node: NodePath
    pos: Vec3
    state: str = "idle"
    timer: float = 0.0
    radius: float = 0.0
    damage: float = 0.0
    heat: float = 0.0
    kind: str = "NONE"
    player_hit: bool = False


@dataclass(frozen=True)
class _CoverBlock:
    pos: Vec3
    half: Vec3


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_dt(dt: float) -> float:
    try:
        return _clamp(float(dt), 0.0, 0.05)
    except Exception:
        return 0.016


def _heading_vec(deg: float) -> Vec3:
    """Return Panda3D camera-facing ground forward for a heading angle.

    Panda3D heading rotates around +Z using the engine camera convention.
    The old Vector Arena pass used ``+sin(H)`` here, which mirrored movement
    relative to the camera: W/S felt plausible at H=0, but A/D and mouse-look
    directions became inverted after turning. Use the same handedness as the
    camera HPR so WASD movement, hitscan aim, and the visible view all agree.
    """
    a = math.radians(float(deg))
    return Vec3(-math.sin(a), math.cos(a), 0.0)


def _right_vec_from_forward(forward: Vec3) -> Vec3:
    """Return the player-right vector for a normalized ground forward vector."""
    return Vec3(forward.y, -forward.x, 0.0)


def _forward_vec(yaw: float, pitch: float) -> Vec3:
    # Panda3D forward is +Y. Positive pitch aims down, so z uses -sin(pitch).
    y = math.radians(float(yaw))
    p = math.radians(float(pitch))
    cp = math.cos(p)
    vec = Vec3(-math.sin(y) * cp, math.cos(y) * cp, -math.sin(p))
    if vec.lengthSquared() > 0.0001:
        vec.normalize()
    return vec


def _line_node(name: str, points: list[Vec3], color: Vec4, thickness: float = 1.0, closed: bool = False) -> NodePath:
    seg = LineSegs(name)
    seg.setThickness(float(thickness))
    seg.setColor(color)
    if not points:
        return NodePath(name)
    seg.moveTo(points[0])
    for point in points[1:]:
        seg.drawTo(point)
    if closed and len(points) > 2:
        seg.drawTo(points[0])
    node = NodePath(seg.create())
    node.setTransparency(TransparencyAttrib.MAlpha)
    return node


def _circle_node(name: str, radius: float, color: Vec4, thickness: float = 1.0, segments: int = 48) -> NodePath:
    pts: list[Vec3] = []
    count = max(12, int(segments))
    for i in range(count):
        a = math.tau * i / count
        pts.append(Vec3(math.sin(a) * radius, math.cos(a) * radius, 0.0))
    return _line_node(name, pts, color, thickness, True)


def _wire_box(name: str, half: Vec3, color: Vec4, thickness: float = 1.0) -> NodePath:
    sx, sy, sz = abs(float(half.x)), abs(float(half.y)), abs(float(half.z))
    pts = [
        Vec3(-sx, -sy, -sz), Vec3(sx, -sy, -sz), Vec3(sx, sy, -sz), Vec3(-sx, sy, -sz),
        Vec3(-sx, -sy, sz), Vec3(sx, -sy, sz), Vec3(sx, sy, sz), Vec3(-sx, sy, sz),
    ]
    edges = ((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7))
    seg = LineSegs(name)
    seg.setThickness(float(thickness))
    seg.setColor(color)
    for a, b in edges:
        seg.moveTo(pts[a])
        seg.drawTo(pts[b])
    node = NodePath(seg.create())
    node.setTransparency(TransparencyAttrib.MAlpha)
    return node


def _panel_node(name: str, width: float, height: float, color: Vec4, axis: str = "floor") -> NodePath:
    cm = CardMaker(name)
    cm.setFrame(-width * 0.5, width * 0.5, -height * 0.5, height * 0.5)
    node = NodePath(cm.generate())
    if axis == "floor":
        node.setP(-90)
    elif axis == "wall_y":
        node.setP(0)
    elif axis == "wall_x":
        node.setH(90)
    node.setColor(color)
    if getattr(color, "w", 1.0) < 1.0:
        node.setTransparency(TransparencyAttrib.MAlpha)
    try:
        node.setTwoSided(True)
    except Exception:
        pass
    return node


def _solid_box_node(name: str, half: Vec3, color: Vec4, trim_color: Vec4 | None = None, trim_thickness: float = 0.8) -> NodePath:
    """Cheap opaque hard-surface cuboid built from cards plus optional neon trim.

    Pass 98 style rule: objects should read as solid current-gen armor first,
    with glow used as thin seams/cores instead of whole translucent bodies.
    """
    sx, sy, sz = abs(float(half.x)), abs(float(half.y)), abs(float(half.z))
    root = NodePath(name)
    faces = (
        ("front", "wall_y", Vec3(0, -sy, 0), 0),
        ("back", "wall_y", Vec3(0, sy, 0), 180),
        ("right", "wall_x", Vec3(sx, 0, 0), 0),
        ("left", "wall_x", Vec3(-sx, 0, 0), 180),
        ("top", "floor", Vec3(0, 0, sz), 0),
        ("bottom", "floor", Vec3(0, 0, -sz), 180),
    )
    for suffix, axis, pos, extra_h in faces:
        if axis == "floor":
            panel = _panel_node(f"{name}_{suffix}_solid_armor_face", sx * 2.0, sy * 2.0, color, axis)
        elif axis == "wall_x":
            panel = _panel_node(f"{name}_{suffix}_solid_armor_face", sy * 2.0, sz * 2.0, color, axis)
        else:
            panel = _panel_node(f"{name}_{suffix}_solid_armor_face", sx * 2.0, sz * 2.0, color, axis)
        panel.setPos(pos)
        if extra_h:
            panel.setH(panel.getH() + extra_h)
        panel.reparentTo(root)
    if trim_color is not None:
        trim = _wire_box(f"{name}_thin_emissive_seams", half, trim_color, trim_thickness)
        trim.reparentTo(root)
    return root


def _armor_strip_node(name: str, length: float, color: Vec4, vertical: bool = False) -> NodePath:
    if vertical:
        return _line_node(name, [Vec3(0, 0, -length * 0.5), Vec3(0, 0, length * 0.5)], color, 1.15, False)
    return _line_node(name, [Vec3(-length * 0.5, 0, 0), Vec3(length * 0.5, 0, 0)], color, 1.15, False)




def _diamond_node(name: str, width: float, height: float, color: Vec4, thickness: float = 1.0) -> NodePath:
    hw = abs(float(width)) * 0.5
    hh = abs(float(height)) * 0.5
    pts = [Vec3(0, 0, hh), Vec3(hw, 0, 0), Vec3(0, 0, -hh), Vec3(-hw, 0, 0)]
    return _line_node(name, pts, color, thickness, True)


def _chevron_node(name: str, width: float, height: float, color: Vec4, thickness: float = 1.0, flipped: bool = False) -> NodePath:
    hw = abs(float(width)) * 0.5
    hh = abs(float(height)) * 0.5
    tip = -hh if flipped else hh
    base = hh if flipped else -hh
    pts = [Vec3(-hw, 0, base), Vec3(0, 0, tip), Vec3(hw, 0, base)]
    return _line_node(name, pts, color, thickness, False)


def _fang_arc_node(name: str, radius: float, height: float, color: Vec4, thickness: float = 1.0, count: int = 5) -> NodePath:
    pts: list[Vec3] = []
    n = max(3, int(count))
    for i in range(n):
        t = -1.0 + 2.0 * i / max(1, n - 1)
        pts.append(Vec3(t * radius, -abs(t) * 0.18, height * (1.0 - 0.24 * abs(t))))
    return _line_node(name, pts, color, thickness, False)


def _enemy_threat_rig(name: str, profile: dict, scale: float, height: float, tier: int = 0) -> tuple[NodePath, ...]:
    """Shared current-gen enemy armor kit.

    Pass 98 keeps the old menacing-model tokens for validator continuity, but
    changes the look from translucent hologram stacks into opaque black armored
    hardlight bodies with thin emissive seams, core diamonds, and controlled
    threat lighting.
    """
    color = profile["color"]
    accent = profile["accent"]
    armor = Vec4(0.026, 0.032, 0.042, 1.0)
    armor_hi = Vec4(0.052, 0.062, 0.078, 1.0)
    seam = Vec4(accent.x, accent.y, accent.z, 0.62)
    aura_radius = (2.25 + tier * 0.22) * scale

    aura = _circle_node(name + "_floor_threat_aura", aura_radius, Vec4(accent.x, accent.y, accent.z, 0.20), 0.8 + tier * 0.08, 36)
    aura.setZ(0.08)
    shadow = _circle_node(name + "_inner_shadow_ring", aura_radius * 0.56, Vec4(color.x, color.y, color.z, 0.14), 0.75, 28)
    shadow.setZ(0.10)

    armored_core = _solid_box_node(name + "_current_gen_armored_core", Vec3(0.72 * scale, 0.34 * scale, height * 0.265), armor, seam, 0.72)
    armored_core.setZ(height * 0.46)
    chest_armor = _solid_box_node(name + "_current_gen_chest_plate", Vec3(0.96 * scale, 0.18 * scale, height * 0.108), armor_hi, Vec4(accent.x, accent.y, accent.z, 0.40), 0.58)
    chest_armor.setPos(0, -0.30 * scale, height * 0.56)
    shoulder_armor_l = _solid_box_node(name + "_current_gen_left_shoulder_armor", Vec3(0.54 * scale, 0.26 * scale, height * 0.055), armor_hi, seam, 0.58)
    shoulder_armor_l.setPos(-1.18 * scale, -0.05 * scale, height * 0.68)
    shoulder_armor_r = _solid_box_node(name + "_current_gen_right_shoulder_armor", Vec3(0.54 * scale, 0.26 * scale, height * 0.055), armor_hi, seam, 0.58)
    shoulder_armor_r.setPos(1.18 * scale, -0.05 * scale, height * 0.68)

    # Legacy token names kept, but these are now thin emissive cuts rather than full transparent body sheets.
    body_glow = _panel_node(name + "_hardlight_body_glow_panel", 1.18 * scale + tier * 0.08, height * 0.38, Vec4(color.x, color.y, color.z, 0.060), "wall_y")
    body_glow.setPos(0, -0.335 * scale, height * 0.48)
    shoulder_glow = _panel_node(name + "_hardlight_shoulder_glow_panel", 2.45 * scale + tier * 0.20, height * 0.050, Vec4(accent.x, accent.y, accent.z, 0.12), "wall_y")
    shoulder_glow.setPos(0, -0.355 * scale, height * 0.705)

    core = _diamond_node(name + "_weak_core_diamond", 0.82 * scale, 1.10 * scale, Vec4(accent.x, accent.y, accent.z, 0.95), 1.15 + tier * 0.08)
    core.setPos(0, -0.43 * scale, height * 0.565)
    optic = _circle_node(name + "_predator_optic", 0.30 * scale, Vec4(1.0, 0.08, 0.14, 0.92), 1.0, 18)
    optic.setPos(0, -0.42 * scale, height * 0.80)
    optic.setP(90)
    crest = _chevron_node(name + "_threat_crest", 1.74 * scale, 1.10 * scale, Vec4(accent.x, accent.y, accent.z, 0.76), 0.95 + tier * 0.08)
    crest.setPos(0, -0.22 * scale, height * 0.94)
    spine = _line_node(
        name + "_back_spine_stack",
        [
            Vec3(-0.76 * scale, 0.45 * scale, height * 0.38),
            Vec3(0.0, 0.82 * scale, height * 0.52),
            Vec3(0.76 * scale, 0.45 * scale, height * 0.38),
            Vec3(0.0, 0.98 * scale, height * 0.68),
            Vec3(-0.76 * scale, 0.45 * scale, height * 0.38),
        ],
        Vec4(accent.x, accent.y, accent.z, 0.48),
        0.82 + tier * 0.06,
        False,
    )
    marker = _line_node(
        name + "_vertical_threat_marker",
        [Vec3(0, -0.48 * scale, height * 0.18), Vec3(0, -0.48 * scale, height * 0.98)],
        Vec4(1.0, 0.06, 0.10, 0.42),
        0.85,
        False,
    )
    return (
        aura, shadow, armored_core, chest_armor, shoulder_armor_l, shoulder_armor_r,
        body_glow, shoulder_glow, core, optic, crest, spine, marker
    )



def _enemy_class_marker_node(name: str, profile: dict, scale: float, height: float) -> NodePath:
    """Small readable overhead marker for the enemy class silhouette.

    Pass 100 uses cheap line primitives only: no new mesh dependency, no runtime
    allocation during combat, and no large debug labels.  The marker helps the
    player read swarm / brute / sentry / wraith / guardian threats while moving.
    """
    vid = str(profile.get("id", "stalker"))
    accent = profile.get("accent", Vec4(1.0, 0.2, 0.2, 0.8))
    root = NodePath(name + "_pass100_readable_class_marker_root")
    marker_color = Vec4(accent.x, accent.y, accent.z, 0.86)
    if vid == "brute":
        top = _wire_box(name + "_brute_class_marker_heavy_bar", Vec3(1.10 * scale, 0.05, 0.12 * scale), marker_color, 1.25)
        bot = _wire_box(name + "_brute_class_marker_lower_bar", Vec3(0.82 * scale, 0.05, 0.10 * scale), marker_color, 1.00)
        bot.setZ(-0.34 * scale)
        for part in (top, bot):
            part.reparentTo(root)
    elif vid == "sentry":
        ring = _circle_node(name + "_sentry_class_marker_crosshair_ring", 0.72 * scale, marker_color, 1.20, 28)
        cross = _line_node(name + "_sentry_class_marker_crosshair_ticks", [Vec3(-0.92 * scale,0,0), Vec3(0.92 * scale,0,0), Vec3(0,0,-0.92 * scale), Vec3(0,0,0.92 * scale)], marker_color, 0.86, False)
        for part in (ring, cross):
            part.reparentTo(root)
    elif vid == "wraith":
        diamond = _diamond_node(name + "_wraith_class_marker_phase_diamond", 1.20 * scale, 1.20 * scale, marker_color, 1.12)
        slit = _line_node(name + "_wraith_class_marker_phase_slit", [Vec3(0,0,-0.72 * scale), Vec3(0,0,0.72 * scale)], Vec4(1.0, 0.10, 0.30, 0.72), 0.80, False)
        for part in (diamond, slit):
            part.reparentTo(root)
    elif vid == "guardian":
        crown = _chevron_node(name + "_guardian_class_marker_boss_crown", 1.78 * scale, 1.14 * scale, marker_color, 1.35, False)
        halo = _circle_node(name + "_guardian_class_marker_boss_halo", 0.94 * scale, Vec4(1.0, 0.82, 0.20, 0.76), 0.95, 32)
        for part in (crown, halo):
            part.reparentTo(root)
    else:
        chevron = _chevron_node(name + "_stalker_class_marker_swarm_chevron", 1.26 * scale, 0.86 * scale, marker_color, 1.04, False)
        dot = _circle_node(name + "_stalker_class_marker_swarm_dot", 0.20 * scale, Vec4(1.0, 0.82, 0.24, 0.78), 0.82, 18)
        dot.setZ(-0.42 * scale)
        for part in (chevron, dot):
            part.reparentTo(root)
    root.setPos(0, -0.56 * scale, height + 1.18 * scale)
    return root

def _enemy_profile(variant: str) -> dict:
    return VARIANT_BY_ID.get(str(variant or "stalker"), VARIANT_BY_ID["stalker"])


def _enemy_color(variant: str) -> Vec4:
    return _enemy_profile(variant)["color"]


def _pawn_node(name: str, variant: str = "stalker", tier: int = 0) -> NodePath:
    """Build a presentation-grade hardlight enemy model from cheap primitives.

    This intentionally avoids mesh/model dependencies so Vector Arena remains
    portable and fast, but each class now has a readable monster silhouette:
    armor layers, horns/claws/pauldrons, glowing weak cores, ground threat rings,
    and distinct head/torso proportions for first-person targeting.
    """
    root = NodePath(name)
    profile = _enemy_profile(variant)
    color = profile["color"]
    accent = profile["accent"]
    scale = float(profile.get("scale", 1.0)) * (1.0 + tier * 0.04)
    vid = profile["id"]

    if vid == "brute":
        height = 9.4 * scale
        feet = _line_node(name + "_heavy_claw_feet", [
            Vec3(-3.25*scale, -0.10, 0), Vec3(-2.35*scale, 0.12, 1.55*scale), Vec3(-1.38*scale, 0.05, 2.65*scale),
            Vec3(0, 0.16, 3.15*scale), Vec3(1.38*scale, 0.05, 2.65*scale), Vec3(2.35*scale, 0.12, 1.55*scale), Vec3(3.25*scale, -0.10, 0)
        ], color, 2.35, False)
        torso = _wire_box(name + "_layered_crusher_torso", Vec3(2.25*scale, 0.95*scale, 2.55*scale), color, 2.05)
        torso.setZ(4.85 * scale)
        chest_plate = _diamond_node(name + "_molten_chest_plate", 2.65*scale, 2.05*scale, accent, 1.65)
        chest_plate.setZ(5.10*scale)
        pauldron_l = _wire_box(name + "_left_pauldrons", Vec3(1.20*scale, 0.58*scale, 0.62*scale), accent, 1.55)
        pauldron_l.setPos(-2.65*scale, 0, 6.55*scale)
        pauldron_r = _wire_box(name + "_right_pauldrons", Vec3(1.20*scale, 0.58*scale, 0.62*scale), accent, 1.55)
        pauldron_r.setPos(2.65*scale, 0, 6.55*scale)
        head = _wire_box(name + "_executioner_mask", Vec3(1.18*scale, 0.44*scale, 0.78*scale), color, 1.75)
        head.setZ(7.92 * scale)
        horns = _fang_arc_node(name + "_heavy_horn_crown", 2.35*scale, 8.95*scale, accent, 1.75, 7)
        cleaver_l = _line_node(name + "_left_cleaver_arm", [Vec3(-3.45*scale, -0.34, 6.4*scale), Vec3(-1.85*scale, -0.92, 5.28*scale), Vec3(-4.05*scale, -1.08, 4.1*scale)], accent, 1.45, False)
        cleaver_r = _line_node(name + "_right_cleaver_arm", [Vec3(3.45*scale, -0.34, 6.4*scale), Vec3(1.85*scale, -0.92, 5.28*scale), Vec3(4.05*scale, -1.08, 4.1*scale)], accent, 1.45, False)
        belt = _line_node(name + "_armor_belt", [Vec3(-2.4*scale, -0.38, 3.85*scale), Vec3(2.4*scale, -0.38, 3.85*scale)], accent, 1.2, False)
        parts = (feet, torso, chest_plate, pauldron_l, pauldron_r, head, horns, cleaver_l, cleaver_r, belt)
    elif vid == "sentry":
        height = 8.0 * scale
        base = _circle_node(name + "_levitating_crawler_base", 1.72*scale, color, 1.8, 36)
        base.setZ(1.15 * scale); base.setP(90)
        lower_ring = _circle_node(name + "_rotor_lower_ring", 1.25*scale, accent, 1.1, 32)
        lower_ring.setZ(2.15*scale); lower_ring.setP(90)
        mast = _line_node(name + "_optic_mast", [Vec3(0,0,0.6*scale), Vec3(0,0,6.25*scale)], color, 1.75, False)
        eye_outer = _circle_node(name + "_wide_targeting_eye", 1.10*scale, accent, 1.65, 32)
        eye_outer.setZ(6.32*scale); eye_outer.setP(90)
        eye_inner = _diamond_node(name + "_diamond_lens", 1.15*scale, 1.15*scale, Vec4(1.0, 1.0, 0.62, 0.92), 1.0)
        eye_inner.setZ(6.32*scale)
        fins = _line_node(name + "_signal_wing_fins", [
            Vec3(-3.2*scale,0,4.0*scale), Vec3(-1.05*scale,0,5.05*scale), Vec3(-0.42*scale,0,4.54*scale),
            Vec3(0.42*scale,0,4.54*scale), Vec3(1.05*scale,0,5.05*scale), Vec3(3.2*scale,0,4.0*scale)
        ], accent, 1.35, False)
        spider_legs = _line_node(name + "_spider_tripod_plus", [
            Vec3(-2.85*scale,0,0), Vec3(-0.55*scale,0,1.65*scale), Vec3(0,0,2.05*scale), Vec3(0.55*scale,0,1.65*scale), Vec3(2.85*scale,0,0),
            Vec3(0,0,2.05*scale), Vec3(0,2.45*scale,0), Vec3(0,0,2.05*scale), Vec3(0,-1.95*scale,0.25*scale)
        ], color, 1.42, False)
        antennae = _line_node(name + "_antennae", [Vec3(-0.65*scale,0,6.92*scale), Vec3(-1.35*scale,0,7.88*scale), Vec3(0,0,6.92*scale), Vec3(1.35*scale,0,7.88*scale), Vec3(0.65*scale,0,6.92*scale)], accent, 1.05, False)
        parts = (base, lower_ring, mast, eye_outer, eye_inner, fins, spider_legs, antennae)
    elif vid == "wraith":
        height = 9.2 * scale
        spine = _line_node(name + "_knife_spine", [Vec3(0,0,0.10*scale), Vec3(0,0,7.9*scale)], color, 1.72, False)
        cloak_l = _line_node(name + "_left_phase_cloak", [Vec3(-2.65*scale,0.10,1.1*scale), Vec3(-1.25*scale,0.34,3.8*scale), Vec3(-1.9*scale,0.18,6.65*scale), Vec3(-0.42*scale,0.08,7.85*scale)], Vec4(color.x, color.y, color.z, 0.55), 1.22, False)
        cloak_r = _line_node(name + "_right_phase_cloak", [Vec3(2.65*scale,0.10,1.1*scale), Vec3(1.25*scale,0.34,3.8*scale), Vec3(1.9*scale,0.18,6.65*scale), Vec3(0.42*scale,0.08,7.85*scale)], Vec4(color.x, color.y, color.z, 0.55), 1.22, False)
        ribs = _line_node(name + "_exposed_rib_cage", [Vec3(-2.25*scale,0,3.35*scale), Vec3(-0.78*scale,0,4.58*scale), Vec3(0.0,0,4.95*scale), Vec3(0.78*scale,0,4.58*scale), Vec3(2.25*scale,0,3.35*scale)], color, 1.42, False)
        mask = _circle_node(name + "_floating_void_mask", 0.98*scale, accent, 1.45, 28)
        mask.setZ(7.72*scale); mask.setP(90)
        horns = _line_node(name + "_split_wraith_horns", [Vec3(-1.45*scale,0,8.05*scale), Vec3(-2.35*scale,0,8.95*scale), Vec3(-0.42*scale,0,8.15*scale), Vec3(0.42*scale,0,8.15*scale), Vec3(2.35*scale,0,8.95*scale), Vec3(1.45*scale,0,8.05*scale)], accent, 1.22, False)
        claws = _line_node(name + "_long_phase_claws", [Vec3(-3.45*scale,-0.35,5.75*scale), Vec3(-1.05*scale,-0.84,4.12*scale), Vec3(0, -1.02, 5.95*scale), Vec3(1.05*scale,-0.84,4.12*scale), Vec3(3.45*scale,-0.35,5.75*scale)], accent, 1.24, False)
        legs = _line_node(name + "_needle_split_legs", [Vec3(-1.55*scale,0,0), Vec3(-0.44*scale,0,2.8*scale), Vec3(0,0,3.35*scale), Vec3(0.44*scale,0,2.8*scale), Vec3(1.55*scale,0,0)], color, 1.32, False)
        phase_halo = _circle_node(name + "_phase_halo", 1.42*scale, Vec4(accent.x, accent.y, accent.z, 0.48), 1.05, 34)
        phase_halo.setZ(6.45*scale); phase_halo.setP(90)
        parts = (spine, cloak_l, cloak_r, ribs, mask, horns, claws, legs, phase_halo)
    elif vid == "guardian":
        height = 11.2 * scale
        legs = _line_node(name + "_guardian_titan_legs", [
            Vec3(-3.55*scale,0,0), Vec3(-1.85*scale,0,2.35*scale), Vec3(-0.78*scale,0,3.45*scale), Vec3(0,0,4.0*scale),
            Vec3(0.78*scale,0,3.45*scale), Vec3(1.85*scale,0,2.35*scale), Vec3(3.55*scale,0,0)
        ], color, 2.55, False)
        torso = _wire_box(name + "_fortress_torso", Vec3(2.75*scale, 1.12*scale, 2.95*scale), color, 2.25)
        torso.setZ(5.75*scale)
        shield_plate = _diamond_node(name + "_fortress_core_plate", 3.00*scale, 2.75*scale, accent, 1.85)
        shield_plate.setZ(6.0*scale)
        crown = _line_node(name + "_guardian_crown_spikes", [
            Vec3(-2.65*scale,0,8.95*scale), Vec3(-1.35*scale,0,10.35*scale), Vec3(-0.42*scale,0,9.35*scale),
            Vec3(0,0,10.70*scale), Vec3(0.42*scale,0,9.35*scale), Vec3(1.35*scale,0,10.35*scale), Vec3(2.65*scale,0,8.95*scale)
        ], accent, 1.95, False)
        halo_outer = _circle_node(name + "_boss_halo_outer", 2.05*scale, accent, 1.48, 42)
        halo_outer.setZ(8.10*scale); halo_outer.setP(90)
        halo_inner = _circle_node(name + "_boss_halo_inner", 1.10*scale, Vec4(1.0, 0.95, 0.56, 0.76), 1.05, 32)
        halo_inner.setZ(8.10*scale); halo_inner.setP(90)
        blade_l = _line_node(name + "_left_execution_blade", [Vec3(-4.25*scale,-0.38,6.25*scale), Vec3(-1.65*scale,-0.92,4.92*scale), Vec3(-3.70*scale,-1.18,3.85*scale)], accent, 1.58, False)
        blade_r = _line_node(name + "_right_execution_blade", [Vec3(4.25*scale,-0.38,6.25*scale), Vec3(1.65*scale,-0.92,4.92*scale), Vec3(3.70*scale,-1.18,3.85*scale)], accent, 1.58, False)
        shoulder_l = _wire_box(name + "_left_boss_shoulder", Vec3(1.38*scale, 0.65*scale, 0.75*scale), accent, 1.55)
        shoulder_l.setPos(-3.10*scale, 0, 7.05*scale)
        shoulder_r = _wire_box(name + "_right_boss_shoulder", Vec3(1.38*scale, 0.65*scale, 0.75*scale), accent, 1.55)
        shoulder_r.setPos(3.10*scale, 0, 7.05*scale)
        parts = (legs, torso, shield_plate, crown, halo_outer, halo_inner, blade_l, blade_r, shoulder_l, shoulder_r)
    else:
        height = 7.8 * scale
        legs = _line_node(name + "_razor_runner_legs", [Vec3(-1.85*scale, 0, 0), Vec3(-0.92*scale, 0, 2.20*scale), Vec3(0,0,3.20*scale), Vec3(0.92*scale,0,2.20*scale), Vec3(1.85*scale,0,0)], color, 1.78, False)
        torso = _wire_box(name + "_thin_predator_torso", Vec3(1.22*scale, 0.44*scale, 2.05*scale), color, 1.55)
        torso.setZ(4.35 * scale)
        chest_spike = _diamond_node(name + "_blade_chest_core", 1.52*scale, 1.92*scale, accent, 1.35)
        chest_spike.setZ(4.70*scale)
        head = _circle_node(name + "_bright_single_eye", 0.84 * scale, accent, 1.38, 26)
        head.setZ(6.86 * scale); head.setP(90)
        brow = _line_node(name + "_predator_brow", [Vec3(-1.28*scale,0,7.20*scale), Vec3(0,0,7.55*scale), Vec3(1.28*scale,0,7.20*scale)], Vec4(1.0, 0.84, 0.20, 0.82), 1.1, False)
        spikes = _line_node(name + "_knife_shoulder_spikes", [Vec3(-2.58*scale, 0, 4.9*scale), Vec3(-0.84*scale, 0, 5.82*scale), Vec3(0,0,5.18*scale), Vec3(0.84*scale,0,5.82*scale), Vec3(2.58*scale,0,4.9*scale)], accent, 1.16, False)
        blade_l = _line_node(name + "_left_razor_arm", [Vec3(-2.58*scale, -0.38, 4.65*scale), Vec3(-0.82*scale, -0.82, 5.55*scale), Vec3(-3.05*scale, -1.02, 3.68*scale)], color, 1.12, False)
        blade_r = _line_node(name + "_right_razor_arm", [Vec3(2.58*scale, -0.38, 4.65*scale), Vec3(0.82*scale, -0.82, 5.55*scale), Vec3(3.05*scale, -1.02, 3.68*scale)], color, 1.12, False)
        parts = (legs, torso, chest_spike, head, brow, spikes, blade_l, blade_r)

    marker = _enemy_class_marker_node(name, profile, scale, height)
    rig = _enemy_threat_rig(name, profile, scale, height, tier)
    for part in parts + rig + (marker,):
        part.reparentTo(root)
        try:
            part.setTransparency(TransparencyAttrib.MAlpha)
        except Exception:
            pass
    root.setName(f"{name}_{profile['id']}_menacing_model_pass100_readable_class_marker")
    return root

class HoloVerseNativeMode:
    """Built-in Vector Arena mounted in the live HoloVerse ShowBase."""

    def __init__(self, host, mode=None, entry_path=None, label=MODE_TITLE):
        self.host = host
        self.mode = mode or {}
        self.entry_path = Path(entry_path) if entry_path else Path(__file__).resolve().parent / "main.py"
        self.folder = self.entry_path.parent
        self.label = str(label or MODE_TITLE)
        self._entered = False
        self._rng = random.Random(49173)
        self._owned: list[NodePath] = []
        self._dimension_ui_node_names = ("local_ui_root",)
        self.dimension_ui_visible = False
        self.hosted_in_holoverse = bool(self.mode.get("dimension")) or str((self.mode.get("manifest") or {}).get("host_contract") or "") == "holoverse_dimension_v1"
        self.paused = False
        self._native_key_latches = {"escape": False, "h": False}
        self.pause_overlay_root: NodePath | None = None
        self.pause_text: OnscreenText | None = None
        self._saved_camera_parent = None
        self._saved_camera_transform = None
        self._saved_bg = None
        self._elapsed = 0.0
        self.player_pos = Vec3(0, -82, 0.0)
        self.player_vel = Vec3(0, 0, 0)
        self.player_yaw = 0.0
        self.player_pitch = 0.0
        self.max_health = 100.0
        self.max_armor = 82.0
        self.health = self.max_health
        self.armor = 50.0
        self.heat = 0.0
        self.upgrade_stacks: dict[str, int] = {"VOLT_LATTICE": 0, "REACTIVE_SHELL": 0, "PHASE_RECOVERY": 0}
        self.upgrades_selected = 0
        self.upgrade_pending = False
        self.upgrade_choices_cache: list[dict] = []
        self._upgrade_key_latches = {1: False, 2: False, 3: False}
        self.weapon_mutation_mult = 1.0
        self.incoming_damage_mult = 1.0
        self.hazard_damage_resist_mult = 1.0
        self.repulsor_cooldown_mult = 1.0
        self.reconstruction_health_restore = 4.0
        self.reconstruction_armor_restore = 7.0
        self.arena_profile = arena_profile_for_set(1)
        self.current_arena_radius = float(self.arena_profile["radius"])
        self.largest_arena_radius = float(self.current_arena_radius)
        self.arena_family_counts: dict[str, int] = {str(self.arena_profile["id"]): 1}
        self.arena_family_transitions = 0
        self.arena_geometry_root: NodePath | None = None
        self._arena_owned: list[NodePath] = []
        self.scoreboard_frame: NodePath | None = None
        self.arena_mutation_profile = arena_mutation_for_set(1)
        self.arena_mutations_survived = 0
        self.combo = 1
        self.combo_timer = 0.0
        self.score = 0
        self.kills = 0
        self.wave = 0
        self.highest_wave = 0
        self.wave_kind = "BOOT"
        self.wave_set = 0
        self.wave_spawn_queue: list[str] = []
        self.wave_spawn_script: list[dict] = []
        self.pending_spawns: list[dict] = []
        self.wave_total_threats = 0
        self.wave_spawned = 0
        self.wave_defeated = 0
        self.wave_spawn_timer = 0.0
        self.wave_spawn_interval = 0.70
        self.wave_max_active = 10
        self.wave_intermission_timer = 0.0
        self.wave_complete_pending = False
        self.wave_required_breaches = 0
        self.wave_breach_start_sealed = 0
        self.wave_forced_breach_timer = 0.0
        self.wave_heat_gain_mult = 1.0
        self.wave_heat_cool_mult = 1.0
        self.guardian_waves_completed = 0
        self.guardian_specials_used = 0
        self.flanking_spawns = 0
        self.reconstruction_count = 0
        self.special_wave_counts: dict[str, int] = {kind: 0 for kind in WAVE_KINDS}
        self.encounter_doctrine = encounter_doctrine_for("ASSAULT", 1)
        self.enemy_evolution_spawns = 0
        self.enemy_evolution_counts: dict[str, int] = {profile["id"]: 0 for profile in ENEMY_VARIANTS}
        self.highest_evolution_level_seen = 0
        self.guardian_phase_transitions = 0
        self._wave_evolution_announced: set[str] = set()
        self.fire_cooldown = 0.0
        self.blast_cooldown = 0.0
        self.damage_flash = 0.0
        self._mouse1_latched = False
        self._mouse3_latched = False
        self._r_latched = False
        self._block_combat_input_until_release = False
        self._capture_pointer_once = True
        self.enemies: list[_Enemy] = []
        self.projectiles: list[_Projectile] = []
        self.impacts: list[_Impact] = []
        self.spawn_pulses: list[_SpawnPulse] = []
        self.kill_bursts: list[_KillBurst] = []
        self.muzzle_flashes: list[_MuzzleFlash] = []
        self.repulsor_waves: list[_RepulsorWave] = []
        self.heat_vent_sparks: list[_HeatVentSpark] = []
        self.breach_cores: list[_BreachCore] = []
        self.arena_hazards: list[_ArenaHazard] = []
        self.hazard_profile: dict = {"kind": "NONE", "enabled": False}
        self.hazard_timer = 999.0
        self.hazard_cursor = 0
        self.hazard_activations = 0
        self.hazard_hits_taken = 0
        self.cover_blocks: list[_CoverBlock] = []
        self.cover_visual_groups: list[tuple[NodePath, ...]] = []
        self.enemy_variant_counts: dict[str, int] = {profile["id"]: 0 for profile in ENEMY_VARIANTS}
        self.spawn_points = [Vec3(x, y, 0) for x, y in spawn_points_for_profile(self.arena_profile)]
        self.reticle_root: NodePath | None = None
        self.local_ui_root: NodePath | None = None
        self.combat_text: OnscreenText | None = None
        self.help_text: OnscreenText | None = None
        self.wave_text: OnscreenText | None = None
        self.event_feed_text: OnscreenText | None = None
        self.hit_confirm_text: OnscreenText | None = None
        self.weapon_upgrade_text: OnscreenText | None = None
        self.upgrade_overlay_root: NodePath | None = None
        self.upgrade_choice_text: OnscreenText | None = None
        self.upgrade_mutation_text: OnscreenText | None = None
        self.damage_overlay: NodePath | None = None
        self.weapon_root: NodePath | None = None
        self.weapon_glow_nodes: list[NodePath] = []
        self.weapon_recoil = 0.0
        self.weapon_charge = 0.0
        self.repulsor_flash = 0.0
        self.weapon_rank = 1
        self.weapon_module_name = WEAPON_UPGRADE_TIERS[0]["name"]
        self.weapon_upgrade_charge = 0.0
        self.weapon_upgrade_notice_timer = 0.0
        self.weapon_rank_flash = 0.0
        self.vent_fx_cooldown = 0.0
        self.phase_banner: OnscreenText | None = None
        self.theme_index = 0
        self.theme_pulse = 0.0
        self.wave_intro_timer = 2.5
        self.combat_events: list[tuple[str, float, str]] = []
        self.hit_marker_timer = 0.0
        self.kill_marker_timer = 0.0
        self.combo_flash_timer = 0.0
        self.breach_spawn_timer = 4.6
        self.breach_phase = 0
        self.breaches_sealed = 0
        self.breach_pressure = 0.0
        self.breach_reward_flash = 0.0
        self.combo_sfx_step = 0
        self.overheat_event_cooldown = 0.0
        self.low_health_event_cooldown = 0.0
        self.scenery_nodes: dict[str, list[NodePath]] = {"primary": [], "secondary": [], "accent": [], "floor": []}
        self.scenery_motion_nodes: list[NodePath] = []
        self.cover_glow_nodes: list[NodePath] = []
        self.spawn_gate_nodes: list[NodePath] = []
        self.spawn_gate_groups: list[NodePath] = []
        self.sfx: dict[str, object] = {}
        self.sfx_volumes: dict[str, float] = dict(VECTOR_ARENA_SFX_VOLUME_DEFAULTS)
        self.sfx_master_volume = 0.85
        self.sfx_enabled = True
        self.sfx_loaded_count = 0
        self._last_sfx_time: dict[str, float] = {}
        self.audio_runtime: VectorArenaAudioRuntime | None = None

    # ------------------------------------------------------------------
    # Host resources
    # ------------------------------------------------------------------
    def _host_resources(self):
        self.render = self.host.render
        self.aspect2d = self.host.aspect2d
        self.render2d = getattr(self.host, "render2d", self.aspect2d)
        self.camera = self.host.camera
        self.camLens = self.host.camLens
        self.loader = getattr(self.host, "loader", None)
        self.win = getattr(self.host, "win", None)
        self.accept = getattr(self.host, "accept", lambda *a, **k: None)
        self.ignore = getattr(self.host, "ignore", lambda *a, **k: None)
        self.disableMouse = getattr(self.host, "disableMouse", lambda *a, **k: None)
        self.setBackgroundColor = getattr(self.host, "setBackgroundColor", lambda *a, **k: None)
        self._saved_camera_parent = self.camera.getParent()
        self._saved_camera_transform = self.camera.getTransform()
        try:
            self._saved_bg = self.win.getClearColor() if self.win is not None else None
        except Exception:
            self._saved_bg = None
        self.root = self.render.attachNewNode("vector_arena_fps_native_root")
        self.world_root = self.root.attachNewNode("vector_arena_fps_world")
        self.fx_root = self.root.attachNewNode("vector_arena_fps_fx")
        self.reticle_root = self.aspect2d.attachNewNode("vector_arena_fps_reticle_root")
        self.local_ui_root = self.aspect2d.attachNewNode("vector_arena_fps_help_root")
        self._owned.extend([self.root, self.world_root, self.fx_root, self.reticle_root, self.local_ui_root])
        try:
            self.disableMouse()
            self.camLens.setFov(78)
            self.camLens.setNearFar(0.08, 900.0)
            self.setBackgroundColor(0.0015, 0.0025, 0.0065)
            if self.win is not None and hasattr(self.win, "requestProperties"):
                props = WindowProperties()
                props.setCursorHidden(True)
                self.win.requestProperties(props)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Scene build
    # ------------------------------------------------------------------
    def _build_lights(self):
        ambient = AmbientLight("vector_arena_fps_ambient")
        ambient.setColor(Vec4(0.10, 0.13, 0.17, 1.0))
        amb_np = self.root.attachNewNode(ambient)
        self.world_root.setLight(amb_np)
        sun = DirectionalLight("vector_arena_fps_directional")
        sun.setColor(Vec4(0.78, 0.96, 1.0, 1.0))
        sun_np = self.root.attachNewNode(sun)
        sun_np.setHpr(-24, -62, 0)
        self.world_root.setLight(sun_np)
        self._owned.extend([amb_np, sun_np])

    def _build_floor_and_grid(self):
        floor = _panel_node("vector_arena_fps_floor", self.current_arena_radius * 2.25, self.current_arena_radius * 2.25, SCENERY_THEMES[0]["floor"], "floor")
        floor.reparentTo(self.arena_geometry_root)
        floor.setZ(-0.03)
        self.scenery_nodes["floor"].append(floor)
        self._owned.append(floor)

        seg = LineSegs("vector_arena_fps_floor_grid")
        seg.setThickness(0.9)
        step = max(10, int(round(float(self.arena_profile.get("grid_step", 12.0)))))
        span = int(self.current_arena_radius)
        seg.setColor(Vec4(0.08, 1.0, 0.82, 0.28))
        for i in range(-span, span + 1, step):
            seg.moveTo(Vec3(i, -span, 0.025)); seg.drawTo(Vec3(i, span, 0.025))
            seg.moveTo(Vec3(-span, i, 0.025)); seg.drawTo(Vec3(span, i, 0.025))
        seg.setThickness(2.0)
        seg.setColor(Vec4(0.18, 1.0, 0.88, 0.68))
        for radius in (self.current_arena_radius * 0.31, self.current_arena_radius * 0.61, self.current_arena_radius):
            for k in range(65):
                a = math.tau * (k % 64) / 64
                p = Vec3(math.sin(a) * radius, math.cos(a) * radius, 0.05)
                if k == 0:
                    seg.moveTo(p)
                else:
                    seg.drawTo(p)
        node = NodePath(seg.create())
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.reparentTo(self.arena_geometry_root)
        self.scenery_nodes["primary"].append(node)
        self._owned.append(node)

        # Fixed combat lanes make the arena readable even while scenery colors shift.
        lane_specs = [
            ("north_lane", Vec3(0, self.current_arena_radius * 0.32, 0.025), self.current_arena_radius * 1.45, 8.0, Vec4(0.08, 0.60, 0.72, 0.14)),
            ("south_lane", Vec3(0, -self.current_arena_radius * 0.32, 0.026), self.current_arena_radius * 1.45, 8.0, Vec4(0.08, 0.60, 0.72, 0.14)),
            ("center_lane", Vec3(0, 0, 0.027), 9.0, self.current_arena_radius * 1.55, Vec4(0.10, 0.38, 0.68, 0.12)),
        ]
        for name, pos, width, height, color in lane_specs:
            lane = _panel_node("vector_arena_fps_" + name, width, height, color, "floor")
            lane.reparentTo(self.arena_geometry_root)
            lane.setPos(pos)
            self.scenery_nodes["floor"].append(lane)
            self._owned.append(lane)

    def _build_walls_and_cover(self):
        """Build one strategic architecture family from authoritative blockers.

        Every solid gameplay blocker originates from architecture_pieces_for_profile(),
        and every architecture piece receives a visible opaque solid of exactly the
        same XY half-extents. Decorative seams stay on/in that solid. This prevents
        invisible collision volumes and prevents visible fake cover.
        """
        armor = Vec4(0.022, 0.028, 0.038, 1.0)
        armor_hi = Vec4(0.050, 0.060, 0.078, 1.0)
        primary = Vec4(*self.arena_profile["wire_primary"])
        secondary = Vec4(*self.arena_profile["wire_secondary"])
        accent = Vec4(*self.arena_profile["wire_accent"])

        # The gameplay boundary is radial, so the visible boundary is radial too.
        # Pass 07 deliberately removes the old square opaque wall shell because a
        # circular movement clamp inside square walls created an invisible barrier
        # near the corners. Three hardlight rings plus vertical fence traces now
        # sit exactly on current_arena_radius.
        for ring_index, z in enumerate((0.12, 9.5, 19.0)):
            ring = _circle_node(
                f"vector_arena_pass07_radial_boundary_ring_{ring_index}",
                self.current_arena_radius, primary if ring_index != 1 else secondary,
                1.5 if ring_index == 0 else 1.0, 96,
            )
            ring.reparentTo(self.arena_geometry_root); ring.setZ(z)
            self.scenery_nodes["primary" if ring_index != 1 else "secondary"].append(ring)
            self._owned.append(ring)
        for i in range(32):
            angle = math.tau * i / 32.0
            x = math.sin(angle) * self.current_arena_radius
            y = math.cos(angle) * self.current_arena_radius
            trace = _armor_strip_node(f"vector_arena_pass07_radial_boundary_trace_{i}", 18.5, accent if i % 4 == 0 else primary, True)
            trace.reparentTo(self.arena_geometry_root); trace.setPos(x, y, 9.5)
            self.scenery_nodes["accent" if i % 4 == 0 else "primary"].append(trace); self._owned.append(trace)

        pieces = architecture_pieces_for_profile(self.arena_profile)
        self.arena_architecture_piece_count = len(pieces)
        self.arena_architecture_name = str(self.arena_profile.get("architecture", "UNKNOWN"))
        for i, piece in enumerate(pieces):
            pos = Vec3(float(piece["x"]), float(piece["y"]), float(piece["half_z"]))
            half = Vec3(float(piece["half_x"]), float(piece["half_y"]), float(piece["half_z"]))
            style = str(piece["style"])
            self.cover_blocks.append(_CoverBlock(pos=Vec3(pos.x, pos.y, 0), half=Vec3(half.x, half.y, half.z)))

            base_color = armor_hi if style not in {"monolith", "bastion"} else Vec4(0.060, 0.030, 0.038, 1.0)
            base = _solid_box_node(f"vector_arena_pass07_{style}_{i}_authoritative_solid", half, base_color, primary, 0.72)
            base.reparentTo(self.arena_geometry_root); base.setPos(pos)
            visuals = [base]

            # Family-specific decorative language. All decorations sit on the
            # authoritative solid, so they cannot imply a path that is blocked.
            if style in {"pillar", "frost_spire", "relay_tower", "data_node", "monolith"}:
                strip_l = _armor_strip_node(f"vector_arena_pass07_{style}_{i}_vertical_a", max(2.0, half.z * 1.45), secondary, True)
                strip_r = _armor_strip_node(f"vector_arena_pass07_{style}_{i}_vertical_b", max(2.0, half.z * 1.15), accent, True)
                strip_l.reparentTo(base); strip_r.reparentTo(base)
                strip_l.setPos(-half.x * 0.55, -half.y - 0.05, 0); strip_r.setPos(half.x * 0.55, -half.y - 0.05, 0)
                visuals.extend([strip_l, strip_r]); self.scenery_nodes["primary"].extend([strip_l, strip_r])
            if style in {"machine", "reactor", "bastion"}:
                seam = _armor_strip_node(f"vector_arena_pass07_{style}_{i}_machine_seam", half.x * 1.45, secondary, False)
                seam.reparentTo(base); seam.setPos(0, -half.y - 0.05, half.z * 0.30)
                visuals.append(seam); self.scenery_nodes["primary"].append(seam)
                cap = _wire_box(f"vector_arena_pass07_{style}_{i}_top_frame", Vec3(half.x * 0.78, half.y * 0.78, 0.16), accent, 0.8)
                cap.reparentTo(base); cap.setZ(half.z * 0.78)
                visuals.append(cap); self.scenery_nodes["accent"].append(cap)
            if style == "canyon_wall":
                seam_a = _armor_strip_node(f"vector_arena_pass07_canyon_{i}_lane_seam_a", half.x * 1.55, secondary, False)
                seam_b = _armor_strip_node(f"vector_arena_pass07_canyon_{i}_lane_seam_b", half.x * 1.15, accent, False)
                seam_a.reparentTo(base); seam_b.reparentTo(base)
                seam_a.setPos(0, -half.y - 0.05, half.z * 0.32); seam_b.setPos(0, -half.y - 0.05, -half.z * 0.22)
                visuals.extend([seam_a, seam_b]); self.scenery_nodes["primary"].extend([seam_a, seam_b])
            if style in {"crystal", "frost_spire"}:
                crystal = _diamond_node(f"vector_arena_pass07_{style}_{i}_crystal_face", min(half.x * 1.2, 10.0), min(half.z * 1.25, 12.0), secondary, 1.0)
                crystal.reparentTo(base); crystal.setPos(0, -half.y - 0.06, 0)
                visuals.append(crystal); self.scenery_nodes["accent"].append(crystal)
            if style in {"data_segment", "data_node"}:
                glitch = _line_node(
                    f"vector_arena_pass07_{style}_{i}_broken_data_trace",
                    [Vec3(-half.x * 0.72, -half.y - 0.06, half.z * 0.35), Vec3(-half.x * 0.16, -half.y - 0.06, -half.z * 0.10), Vec3(half.x * 0.20, -half.y - 0.06, half.z * 0.24), Vec3(half.x * 0.72, -half.y - 0.06, -half.z * 0.28)],
                    accent, 1.0, False,
                )
                glitch.reparentTo(base); visuals.append(glitch); self.scenery_nodes["accent"].append(glitch)

            glow = _panel_node(f"vector_arena_pass07_{style}_{i}_footprint_glow", half.x * 1.65, half.y * 1.65, Vec4(primary.x, primary.y, primary.z, 0.07), "floor")
            glow.reparentTo(self.arena_geometry_root); glow.setPos(pos.x, pos.y, 0.08)
            visuals.append(glow); self.cover_glow_nodes.append(glow)
            self.cover_visual_groups.append(tuple(visuals))
            self.scenery_nodes["secondary"].append(base)
            self._owned.extend(visuals)

    def _build_spawn_gates(self):
        # Spawn portals are deliberately phase-safe, not physical cover.  Their
        # presentation therefore uses open hardlight wireframes instead of opaque
        # solid pylons.  This prevents a visual lie where a player sees a heavy
        # wall-like machine but can walk through it because gates are intentionally
        # excluded from the authoritative architecture blocker graph.
        primary = Vec4(*self.arena_profile["wire_primary"])
        accent = Vec4(1.0, 0.08, 0.18, 0.72)
        amber = Vec4(1.0, 0.58, 0.16, 0.58)
        for i, point in enumerate(self.spawn_points):
            gate_root = self.world_root.attachNewNode(f"vector_arena_fps_phase_safe_spawn_gate_{i}")
            direction = Vec3(-point.x, -point.y, 0)
            if direction.lengthSquared() > 0.001:
                direction.normalize()
            gate_root.setPos(point)
            gate_root.setH(math.degrees(math.atan2(direction.x, direction.y)))
            left = _wire_box(f"vector_arena_fps_spawn_gate_{i}_left_hardlight_pylon", Vec3(0.72, 0.78, 4.4), primary, 1.05)
            right = _wire_box(f"vector_arena_fps_spawn_gate_{i}_right_hardlight_pylon", Vec3(0.72, 0.78, 4.4), primary, 1.05)
            header = _wire_box(f"vector_arena_fps_spawn_gate_{i}_hardlight_header", Vec3(4.2, 0.72, 0.72), primary, 1.05)
            left.setPos(-4.1, 0.0, 4.4)
            right.setPos(4.1, 0.0, 4.4)
            header.setPos(0.0, 0.0, 8.55)
            slit_l = _armor_strip_node(f"vector_arena_fps_spawn_gate_{i}_left_red_light_slit", 6.2, accent, True)
            slit_r = _armor_strip_node(f"vector_arena_fps_spawn_gate_{i}_right_red_light_slit", 6.2, accent, True)
            slit_l.setPos(-4.95, -0.86, 4.7)
            slit_r.setPos(4.95, -0.86, 4.7)
            inner = _circle_node(f"vector_arena_fps_spawn_gate_inner_{i}", 2.25, amber, 0.95, 28)
            inner.setPos(0, -0.94, 5.8)
            inner.setP(90)
            gate = _circle_node(f"vector_arena_fps_spawn_gate_{i}", 4.05, Vec4(1.0, 0.08, 0.18, 0.34), 0.82, 36)
            gate.setPos(0, -0.96, 5.8)
            gate.setP(90)
            for part in (left, right, header, slit_l, slit_r, inner, gate):
                part.reparentTo(gate_root)
            self.spawn_gate_nodes.extend([gate_root, left, right, header, slit_l, slit_r, inner, gate])
            self.spawn_gate_groups.append(gate_root)
            self.scenery_nodes["accent"].extend([slit_l, slit_r, inner, gate])
            self.scenery_nodes["secondary"].extend([gate_root, left, right, header])
            self._owned.extend([gate_root, left, right, header, slit_l, slit_r, inner, gate])

    def _build_scenery_shell(self):
        # Presentation scenery: solid skyline machinery plus controlled glow rings.
        armor = Vec4(0.020, 0.026, 0.036, 1.0)
        trim = Vec4(0.18, 1.0, 0.90, 0.34)
        for i in range(12):
            angle = math.tau * i / 12.0
            radius = self.current_arena_radius + 18.0
            x = math.sin(angle) * radius
            y = math.cos(angle) * radius
            height = 18.0 + (i % 3) * 5.0
            pylon = _solid_box_node(f"vector_arena_fps_solid_skyline_pylon_{i}", Vec3(2.8, 2.8, height), armor, trim, 0.58)
            pylon.reparentTo(self.arena_geometry_root)
            pylon.setPos(x, y, height)
            pylon.setH(-math.degrees(angle))
            light_cut = _armor_strip_node(f"vector_arena_fps_skyline_pylon_{i}_vertical_light_cut", height * 1.2, trim, True)
            light_cut.reparentTo(pylon)
            light_cut.setPos(0, -2.92, 0)
            self.scenery_nodes["primary"].append(light_cut)
            self.scenery_nodes["secondary"].append(pylon)
            self.scenery_motion_nodes.append(pylon)
            self._owned.extend([pylon, light_cut])

        for j, (radius, z, thick) in enumerate(((self.current_arena_radius * 0.72, 25.0, 1.0), (self.current_arena_radius * 0.98, 33.0, 0.9), (self.current_arena_radius * 1.18, 43.0, 0.8))):
            ring = _circle_node(f"vector_arena_fps_overhead_ring_{j}", radius, Vec4(0.18, 1.0, 0.90, 0.26), thick, 80)
            ring.reparentTo(self.arena_geometry_root)
            ring.setZ(z)
            self.scenery_nodes["secondary"].append(ring)
            self.scenery_motion_nodes.append(ring)
            self._owned.append(ring)

        for i in range(8):
            angle = math.tau * i / 8.0 + math.radians(22.5)
            start = Vec3(math.sin(angle) * 42, math.cos(angle) * 42, 0.20)
            end = Vec3(math.sin(angle) * (self.current_arena_radius - 10), math.cos(angle) * (self.current_arena_radius - 10), 0.20)
            spoke = _line_node(f"vector_arena_fps_power_spoke_{i}", [start, end], Vec4(1.0, 0.72, 0.18, 0.32), 1.0, False)
            spoke.reparentTo(self.arena_geometry_root)
            self.scenery_nodes["accent"].append(spoke)
            self._owned.append(spoke)

    def _clear_arena_geometry(self):
        for node in list(self._arena_owned):
            try:
                if node in self._owned:
                    self._owned.remove(node)
            except Exception:
                pass
        self._arena_owned.clear()
        if self.arena_geometry_root is not None:
            try:
                self.arena_geometry_root.removeNode()
            except Exception:
                pass
        self.arena_geometry_root = None
        self.scenery_nodes = {"primary": [], "secondary": [], "accent": [], "floor": []}
        self.scenery_motion_nodes = []
        self.cover_glow_nodes = []
        self.spawn_gate_nodes = []
        self.spawn_gate_groups = []
        self.cover_blocks = []
        self.cover_visual_groups = []

    def _build_arena_geometry(self):
        self._clear_arena_geometry()
        start = len(self._owned)
        self.arena_geometry_root = self.world_root.attachNewNode(
            f"vector_arena_pass07_geometry_{self.arena_profile['id'].lower()}_r{int(self.current_arena_radius)}"
        )
        self._owned.append(self.arena_geometry_root)
        self._build_floor_and_grid()
        self._build_walls_and_cover()
        self._build_spawn_gates()
        self._build_scenery_shell()
        self._arena_owned = list(self._owned[start:])

    def _apply_arena_profile(self, set_number: int, rebuild: bool = False):
        previous_id = str(getattr(self, "arena_profile", {}).get("id", ""))
        previous_radius = float(getattr(self, "current_arena_radius", BASE_ARENA_RADIUS))
        profile = arena_profile_for_set(set_number)
        self.arena_profile = dict(profile)
        self.current_arena_radius = float(profile["radius"])
        self.largest_arena_radius = max(float(self.largest_arena_radius), self.current_arena_radius)
        self.spawn_points = [Vec3(x, y, 0) for x, y in spawn_points_for_profile(profile)]
        family_id = str(profile["id"])
        if family_id != previous_id:
            self.arena_family_transitions += 1
            self.arena_family_counts[family_id] = int(self.arena_family_counts.get(family_id, 0)) + 1
        self.theme_index = (max(1, int(set_number)) - 1) % max(1, len(SCENERY_THEMES))
        if rebuild or abs(previous_radius - self.current_arena_radius) > 0.01 or family_id != previous_id:
            self._build_arena_geometry()
        if self.scoreboard_frame is not None:
            try:
                self.scoreboard_frame.setPos(0, self.current_arena_radius - 2.0, 20)
            except Exception:
                pass

    def _build_score_board(self):
        frame = _wire_box("vector_arena_fps_scoreboard_frame", Vec3(34, 1.0, 8), Vec4(0.12, 1.0, 0.86, 0.68), 1.1)
        frame.reparentTo(self.world_root)
        frame.setPos(0, self.current_arena_radius - 2.0, 20)
        self.scoreboard_frame = frame
        self.wave_text = OnscreenText(
            text="VECTOR ARENA\nFIRST PERSON BOOT",
            mayChange=True,
            parent=frame,
            align=TextNode.ACenter,
            pos=(0, 0.02),
            scale=2.7,
            fg=(0.64, 1.0, 0.88, 0.94),
            shadow=(0, 0, 0, 0.85),
        )
        self.wave_text.setBillboardPointEye()
        self._owned.extend([frame, self.wave_text])

    def _build_enemy_pool(self):
        """Prebuild every enemy node once; the wave director only activates pooled slots."""
        for i in range(ENEMY_CAP):
            variant = ENEMY_POOL_VARIANTS[i % len(ENEMY_POOL_VARIANTS)]
            profile = _enemy_profile(variant)
            tier = max(0, min(3, ENEMY_VARIANTS.index(profile)))
            node = _pawn_node(f"vector_arena_fps_enemy_{i}", variant, tier)
            node.reparentTo(self.world_root)
            enemy = _Enemy(
                node=node,
                pos=Vec3(0, 0, 0),
                vel=Vec3(0, 0, 0),
                hp=float(profile["hp"]),
                max_hp=float(profile["hp"]),
                tier=tier,
                phase=self._rng.random() * math.tau,
                attack_cooldown=self._rng.uniform(0.2, 1.8),
                variant=variant,
                display_name=str(profile["name"]),
                speed_scale=float(profile["speed"]),
                damage_scale=float(profile["damage"]),
                score_value=int(profile["score"]),
                aim_radius=float(profile["aim_radius"]),
                active=False,
            )
            hp_back = _line_node(f"vector_arena_fps_enemy_{i}_pass100_hp_back", [Vec3(-2.0, -0.92, 8.55), Vec3(2.0, -0.92, 8.55)], Vec4(0.02, 0.02, 0.02, 0.86), 2.8, False)
            hp_fill = _line_node(f"vector_arena_fps_enemy_{i}_pass100_hp_fill", [Vec3(-2.0, -0.94, 8.58), Vec3(2.0, -0.94, 8.58)], Vec4(1.0, 0.20, 0.18, 0.92), 2.0, False)
            marker = _circle_node(f"vector_arena_fps_enemy_{i}_pass100_target_status_tick", 0.18, Vec4(1.0, 0.86, 0.20, 0.88), 0.70, 16)
            marker.setPos(0, -0.98, 8.95)
            for hud_node in (hp_back, hp_fill, marker):
                hud_node.reparentTo(node)
            enemy.hp_back = hp_back
            enemy.hp_fill = hp_fill
            enemy.class_marker = marker
            if variant == "guardian":
                telegraph = _circle_node(f"vector_arena_guardian_{i}_special_telegraph", 7.0, Vec4(1.0, 0.18, 0.08, 0.78), 1.7, 40)
                telegraph.reparentTo(self.fx_root)
                telegraph.setP(90)
                telegraph.hide()
                enemy.guardian_telegraph = telegraph
                self._owned.append(telegraph)
            enemy.node.hide()
            self.enemies.append(enemy)

    def _build_projectile_pool(self):
        for i in range(PROJECTILE_CAP):
            beam_root = NodePath(f"vector_arena_fps_hitscan_beam_{i}")
            core = _line_node(f"vector_arena_fps_hitscan_beam_core_{i}", [Vec3(0, 0, 0), Vec3(0, 1, 0)], Vec4(1.0, 0.96, 0.34, 0.98), 2.6, False)
            halo = _line_node(f"vector_arena_fps_hitscan_beam_halo_{i}", [Vec3(0, 0, 0), Vec3(0, 1, 0)], Vec4(0.22, 1.0, 0.90, 0.44), 5.2, False)
            spark = _line_node(f"vector_arena_fps_hitscan_beam_spark_{i}", [Vec3(-0.18, 0.50, 0), Vec3(0.18, 0.50, 0)], Vec4(1.0, 0.26, 0.94, 0.68), 1.1, False)
            for part in (halo, core, spark):
                part.reparentTo(beam_root)
            beam_root.reparentTo(self.fx_root)
            beam_root.hide()
            self.projectiles.append(_Projectile(node=beam_root))
        for i in range(IMPACT_CAP):
            impact_root = NodePath(f"vector_arena_fps_impact_{i}")
            ring = _circle_node(f"vector_arena_fps_impact_ring_{i}", 2.2, Vec4(1.0, 0.30, 0.94, 0.78), 1.6, 28)
            star_a = _line_node(f"vector_arena_fps_impact_star_a_{i}", [Vec3(-1.65,0,0), Vec3(1.65,0,0)], Vec4(1.0, 0.92, 0.22, 0.70), 1.0, False)
            star_b = _line_node(f"vector_arena_fps_impact_star_b_{i}", [Vec3(0,-1.65,0), Vec3(0,1.65,0)], Vec4(0.28, 1.0, 0.92, 0.62), 0.9, False)
            for part in (ring, star_a, star_b):
                part.reparentTo(impact_root)
            impact_root.reparentTo(self.fx_root)
            impact_root.hide()
            self.impacts.append(_Impact(node=impact_root, pos=Vec3(0, 0, 0)))
        for i in range(SPAWN_PULSE_CAP):
            node = _circle_node(f"vector_arena_fps_spawn_pulse_{i}", 3.0, Vec4(1.0, 0.20, 0.82, 0.62), 1.4, 28)
            node.reparentTo(self.fx_root)
            node.setP(90)
            node.hide()
            self.spawn_pulses.append(_SpawnPulse(node=node, pos=Vec3(0,0,0)))
        for i in range(KILL_BURST_CAP):
            burst_root = NodePath(f"vector_arena_fps_kill_burst_{i}")
            ring_a = _circle_node(f"vector_arena_fps_kill_burst_ring_a_{i}", 2.0, Vec4(1.0, 0.86, 0.18, 0.80), 1.75, 32)
            ring_b = _circle_node(f"vector_arena_fps_kill_burst_ring_b_{i}", 1.2, Vec4(1.0, 0.20, 0.92, 0.72), 1.25, 28)
            spike_a = _line_node(f"vector_arena_fps_kill_burst_spike_a_{i}", [Vec3(-3.2,0,0), Vec3(3.2,0,0)], Vec4(1.0, 0.92, 0.22, 0.84), 1.35, False)
            spike_b = _line_node(f"vector_arena_fps_kill_burst_spike_b_{i}", [Vec3(0,-3.2,0), Vec3(0,3.2,0)], Vec4(1.0, 0.25, 0.94, 0.74), 1.15, False)
            crown = _chevron_node(f"vector_arena_fps_kill_burst_crown_{i}", 5.0, 2.2, Vec4(0.30, 1.0, 0.92, 0.68), 1.0, False)
            for part in (ring_a, ring_b, spike_a, spike_b, crown):
                part.reparentTo(burst_root)
            burst_root.reparentTo(self.fx_root)
            burst_root.setP(90)
            burst_root.hide()
            self.kill_bursts.append(_KillBurst(node=burst_root, pos=Vec3(0,0,0)))
        for i in range(MUZZLE_FLASH_CAP):
            flash_root = NodePath(f"vector_arena_fps_muzzle_flash_{i}")
            cone = _circle_node(f"vector_arena_fps_muzzle_flash_cone_{i}", 0.34, Vec4(1.0, 0.92, 0.26, 0.86), 1.5, 20)
            cross = _line_node(f"vector_arena_fps_muzzle_flash_cross_{i}", [Vec3(-0.42,0,0), Vec3(0.42,0,0), Vec3(0,0,-0.42), Vec3(0,0,0.42)], Vec4(0.24, 1.0, 0.92, 0.68), 1.1, False)
            crown = _chevron_node(f"vector_arena_fps_muzzle_flash_crown_{i}", 0.72, 0.52, Vec4(1.0, 0.22, 0.92, 0.70), 1.0, False)
            for part in (cone, cross, crown):
                part.reparentTo(flash_root)
            flash_root.reparentTo(self.fx_root)
            flash_root.hide()
            self.muzzle_flashes.append(_MuzzleFlash(node=flash_root, pos=Vec3(0,0,0)))
        for i in range(REPULSOR_WAVE_CAP):
            wave_root = NodePath(f"vector_arena_fps_repulsor_wave_{i}")
            ring_a = _circle_node(f"vector_arena_fps_repulsor_wave_ring_a_{i}", 3.0, Vec4(0.24, 1.0, 0.96, 0.62), 1.45, 36)
            ring_b = _circle_node(f"vector_arena_fps_repulsor_wave_ring_b_{i}", 1.6, Vec4(1.0, 0.26, 0.96, 0.52), 1.05, 32)
            slash = _line_node(f"vector_arena_fps_repulsor_wave_slash_{i}", [Vec3(-3.2,0,0), Vec3(3.2,0,0), Vec3(0,-3.2,0), Vec3(0,3.2,0)], Vec4(1.0, 0.86, 0.22, 0.54), 1.0, False)
            for part in (ring_a, ring_b, slash):
                part.reparentTo(wave_root)
            wave_root.reparentTo(self.fx_root)
            wave_root.setP(90)
            wave_root.hide()
            self.repulsor_waves.append(_RepulsorWave(node=wave_root, pos=Vec3(0,0,0)))
        for i in range(HEAT_VENT_SPARK_CAP):
            spark_root = NodePath(f"vector_arena_fps_heat_vent_spark_{i}")
            line_a = _line_node(f"vector_arena_fps_heat_vent_spark_line_a_{i}", [Vec3(-0.5,0,0), Vec3(0.5,0,0)], Vec4(1.0, 0.72, 0.18, 0.70), 1.0, False)
            line_b = _line_node(f"vector_arena_fps_heat_vent_spark_line_b_{i}", [Vec3(0,0,-0.5), Vec3(0,0,0.5)], Vec4(1.0, 0.22, 0.92, 0.60), 0.9, False)
            for part in (line_a, line_b):
                part.reparentTo(spark_root)
            spark_root.reparentTo(self.fx_root)
            spark_root.hide()
            self.heat_vent_sparks.append(_HeatVentSpark(node=spark_root, pos=Vec3(0,0,0)))



    def _build_breach_core_pool(self):
        """Prebuild objective nodes for the breach-loop gameplay layer.

        These are pooled/hidden nodes. The loop adds a new reason to move and
        shoot during waves without creating objects mid-fight or changing the
        existing LMB/RMB/R heat controls.
        """
        for i in range(BREACH_CORE_CAP):
            root = NodePath(f"vector_arena_breach_core_objective_{i}")
            base = _circle_node(f"vector_arena_breach_core_base_ring_{i}", 3.4, Vec4(1.0, 0.14, 0.22, 0.66), 1.2, 36)
            inner = _circle_node(f"vector_arena_breach_core_inner_ring_{i}", 1.55, Vec4(1.0, 0.74, 0.20, 0.62), 1.0, 28)
            diamond = _diamond_node(f"vector_arena_breach_core_target_diamond_{i}", 4.2, 6.0, Vec4(1.0, 0.08, 0.28, 0.74), 1.1)
            spine = _line_node(
                f"vector_arena_breach_core_vertical_spine_{i}",
                [Vec3(0, 0, 0.0), Vec3(0, 0, 8.5)],
                Vec4(0.32, 1.0, 0.94, 0.62),
                1.0,
                False,
            )
            cross = _line_node(
                f"vector_arena_breach_core_cross_arcs_{i}",
                [Vec3(-2.6, 0, 4.0), Vec3(2.6, 0, 4.0), Vec3(0, -2.6, 4.0), Vec3(0, 2.6, 4.0)],
                Vec4(1.0, 0.78, 0.22, 0.50),
                0.85,
                False,
            )
            glow = _panel_node(f"vector_arena_breach_core_floor_warning_{i}", 9.0, 9.0, Vec4(1.0, 0.04, 0.08, 0.08), "floor")
            glow.setZ(0.04)
            base.setP(90)
            inner.setP(90)
            diamond.setP(90)
            for part in (glow, base, inner, diamond, spine, cross):
                part.reparentTo(root)
            root.reparentTo(self.fx_root)
            root.hide()
            self.breach_cores.append(_BreachCore(node=root, pos=Vec3(0, 0, 0)))
            self._owned.append(root)

    def _build_hazard_pool(self):
        """Prebuild bounded floor hazards; no hazard geometry is created mid-wave."""
        for i in range(6):
            root = NodePath(f"vector_arena_pass03_hazard_{i}")
            outer = _circle_node(f"vector_arena_pass03_hazard_{i}_outer", 1.0, Vec4(1.0, 0.68, 0.10, 0.78), 1.5, 36)
            inner = _circle_node(f"vector_arena_pass03_hazard_{i}_inner", 0.62, Vec4(1.0, 0.10, 0.18, 0.72), 1.1, 30)
            cross = _line_node(f"vector_arena_pass03_hazard_{i}_cross", [Vec3(-1,0,0), Vec3(1,0,0), Vec3(0,-1,0), Vec3(0,1,0)], Vec4(1.0, 0.92, 0.22, 0.78), 1.0, False)
            for part in (outer, inner, cross):
                part.reparentTo(root)
            root.reparentTo(self.fx_root)
            root.setP(90)
            root.hide()
            self.arena_hazards.append(_ArenaHazard(node=root, pos=Vec3(0,0,0)))
            self._owned.append(root)

    def _build_weapon_viewmodel(self):
        # Current-gen hardlight rifle: solid black receiver and barrel housing with
        # restrained cyan/magenta emissive seams.  Keeps old token names for route
        # validator continuity, but removes the see-through wireframe gun feel.
        self.weapon_root = self.camera.attachNewNode("vector_arena_fps_weapon_root")
        self.weapon_root.setPos(0.50, 1.02, -0.36)
        self.weapon_root.setHpr(-5.0, -2.0, 0.0)
        armor = Vec4(0.024, 0.030, 0.040, 1.0)
        armor_hi = Vec4(0.038, 0.045, 0.055, 1.0)
        cyan = Vec4(0.22, 1.0, 0.88, 0.78)
        gold = Vec4(1.0, 0.84, 0.24, 0.82)
        magenta = Vec4(1.0, 0.18, 0.66, 0.72)
        hot = Vec4(1.0, 0.20, 0.10, 0.70)

        receiver = _solid_box_node("vector_arena_fps_weapon_receiver", Vec3(0.18, 0.36, 0.105), armor_hi, cyan, 0.45)
        receiver.reparentTo(self.weapon_root); receiver.setPos(0, 0.14, 0)
        grip_body = _solid_box_node("vector_arena_fps_weapon_grip_solid_body", Vec3(0.075, 0.075, 0.22), armor, Vec4(0.18, 1.0, 0.88, 0.30), 0.35)
        grip_body.reparentTo(self.weapon_root); grip_body.setPos(0.06, -0.02, -0.25); grip_body.setR(-11)
        grip = _line_node("vector_arena_fps_weapon_grip", [Vec3(-0.08, -0.10, -0.08), Vec3(-0.13, -0.02, -0.30), Vec3(0.08, -0.10, -0.08), Vec3(0.13, -0.02, -0.30)], cyan, 0.55, False)
        grip.reparentTo(self.weapon_root)
        stock_body = _solid_box_node("vector_arena_fps_weapon_stock_solid_body", Vec3(0.24, 0.12, 0.055), armor, Vec4(0.14, 0.62, 1.0, 0.26), 0.34)
        stock_body.reparentTo(self.weapon_root); stock_body.setPos(0, -0.31, -0.055)
        stock = _line_node("vector_arena_fps_weapon_stock", [Vec3(-0.16, -0.26, -0.03), Vec3(-0.42, -0.42, -0.11), Vec3(0.16, -0.26, -0.03), Vec3(0.42, -0.42, -0.11)], Vec4(0.32, 0.80, 1.0, 0.42), 0.62, False)
        stock.reparentTo(self.weapon_root)
        barrel_shell = _solid_box_node("vector_arena_fps_weapon_barrel_opaque_shell", Vec3(0.105, 0.38, 0.055), armor, cyan, 0.36)
        barrel_shell.reparentTo(self.weapon_root); barrel_shell.setPos(0, 0.63, 0.02)
        barrel_core = _line_node("vector_arena_fps_weapon_barrel_core", [Vec3(0, 0.22, 0.035), Vec3(0, 1.08, 0.035)], gold, 1.42, False)
        barrel_core.reparentTo(self.weapon_root)
        barrel_top = _line_node("vector_arena_fps_weapon_top_rail", [Vec3(-0.10, 0.22, 0.112), Vec3(0.10, 0.22, 0.112), Vec3(0.10, 1.02, 0.112), Vec3(-0.10, 1.02, 0.112)], cyan, 0.75, True)
        barrel_top.reparentTo(self.weapon_root)
        side_a = _solid_box_node("vector_arena_fps_weapon_left_arc_fin_solid", Vec3(0.035, 0.28, 0.052), armor, cyan, 0.30)
        side_b = _solid_box_node("vector_arena_fps_weapon_right_arc_fin_solid", Vec3(0.035, 0.28, 0.052), armor, cyan, 0.30)
        side_a.reparentTo(self.weapon_root); side_a.setPos(-0.22, 0.56, -0.055); side_a.setH(-7)
        side_b.reparentTo(self.weapon_root); side_b.setPos(0.22, 0.56, -0.055); side_b.setH(7)
        coil_a = _circle_node("vector_arena_fps_weapon_capacitor_coil_a", 0.135, magenta, 0.95, 28)
        coil_b = _circle_node("vector_arena_fps_weapon_capacitor_coil_b", 0.100, gold, 0.85, 24)
        for coil, y, x in ((coil_a, 0.50, -0.085), (coil_b, 0.70, 0.085)):
            coil.reparentTo(self.weapon_root); coil.setPos(x, y, 0.040); coil.setP(90)
        heat_l = _line_node("vector_arena_fps_weapon_left_heat_strip", [Vec3(-0.192, 0.34, -0.045), Vec3(-0.192, 0.88, -0.045)], hot, 0.95, False)
        heat_r = _line_node("vector_arena_fps_weapon_right_heat_strip", [Vec3(0.192, 0.34, -0.045), Vec3(0.192, 0.88, -0.045)], hot, 0.95, False)
        heat_l.reparentTo(self.weapon_root); heat_r.reparentTo(self.weapon_root)
        sight_bridge = _solid_box_node("vector_arena_fps_weapon_projector_sight_bridge", Vec3(0.09, 0.05, 0.025), armor, gold, 0.28)
        sight_bridge.reparentTo(self.weapon_root); sight_bridge.setPos(0, 0.95, 0.115)
        sight = _circle_node("vector_arena_fps_weapon_projector_sight", 0.070, gold, 0.78, 20)
        sight.reparentTo(self.weapon_root); sight.setPos(0, 1.00, 0.135); sight.setP(90)
        muzzle_crown = _chevron_node("vector_arena_fps_weapon_muzzle_crown", 0.34, 0.24, Vec4(1.0, 0.24, 0.82, 0.70), 0.88, False)
        muzzle_crown.reparentTo(self.weapon_root); muzzle_crown.setPos(0, 1.12, 0.035)
        charge_core = _diamond_node("vector_arena_fps_weapon_charge_core", 0.18, 0.24, Vec4(0.32, 1.0, 0.92, 0.70), 0.82)
        charge_core.reparentTo(self.weapon_root); charge_core.setPos(0, 0.30, 0.032)
        upgrade_left = _line_node("vector_arena_fps_weapon_pass101_upgrade_meter_left", [Vec3(-0.29, 0.18, 0.136), Vec3(-0.29, 0.86, 0.136)], Vec4(0.42, 1.0, 0.92, 0.76), 0.78, False)
        upgrade_right = _line_node("vector_arena_fps_weapon_pass101_upgrade_meter_right", [Vec3(0.29, 0.18, 0.136), Vec3(0.29, 0.86, 0.136)], Vec4(1.0, 0.32, 0.92, 0.70), 0.78, False)
        upgrade_rank_core = _circle_node("vector_arena_fps_weapon_pass101_upgrade_rank_core", 0.112, Vec4(1.0, 0.86, 0.24, 0.80), 0.92, 24)
        upgrade_rank_core.setP(90)
        upgrade_rank_core.setPos(0, 0.48, 0.152)
        upgrade_crown = _chevron_node("vector_arena_fps_weapon_pass101_upgrade_crown", 0.38, 0.23, Vec4(0.54, 1.0, 0.92, 0.72), 0.78, False)
        upgrade_crown.setPos(0, 0.75, 0.154)
        for upgrade_node in (upgrade_left, upgrade_right, upgrade_rank_core, upgrade_crown):
            upgrade_node.reparentTo(self.weapon_root)
        self.weapon_glow_nodes = [coil_a, coil_b, heat_l, heat_r, muzzle_crown, charge_core, sight, upgrade_left, upgrade_right, upgrade_rank_core, upgrade_crown]
        for node in (self.weapon_root, receiver, grip_body, grip, stock_body, stock, barrel_shell, barrel_core, barrel_top, side_a, side_b, coil_a, coil_b, heat_l, heat_r, sight_bridge, sight, muzzle_crown, charge_core, upgrade_left, upgrade_right, upgrade_rank_core, upgrade_crown):
            self._owned.append(node)

    def _build_reticle_and_hud(self):
        assert self.reticle_root is not None
        # Reticle is not debug UI; it is part of the first-person shooter presentation.
        reticle_lines = [
            _line_node("vector_arena_fps_reticle_h", [Vec3(-0.030, 0, 0), Vec3(-0.010, 0, 0), Vec3(0.010, 0, 0), Vec3(0.030, 0, 0)], Vec4(0.72, 1.0, 0.92, 0.95), 1.15, False),
            _line_node("vector_arena_fps_reticle_v", [Vec3(0, 0, -0.030), Vec3(0, 0, -0.010), Vec3(0, 0, 0.010), Vec3(0, 0, 0.030)], Vec4(0.72, 1.0, 0.92, 0.95), 1.15, False),
            _circle_node("vector_arena_fps_reticle_ring", 0.045, Vec4(0.20, 1.0, 0.88, 0.44), 0.85, 32),
        ]
        for node in reticle_lines:
            node.reparentTo(self.reticle_root)
            self._owned.append(node)

        self.combat_text = OnscreenText(
            text="HP 100  ARMOR 050  HEAT 000  SCORE 00000",
            parent=self.reticle_root,
            pos=(-1.30, -0.88),
            align=TextNode.ALeft,
            scale=0.038,
            fg=(0.62, 1.0, 0.90, 0.92),
            shadow=(0, 0, 0, 0.85),
            mayChange=True,
        )
        self._owned.append(self.combat_text)

        self.event_feed_text = OnscreenText(
            text="MATCH LIVE // TARGET CLASS MARKERS ONLINE",
            parent=self.reticle_root,
            pos=(1.30, 0.86),
            align=TextNode.ARight,
            scale=0.033,
            fg=(0.82, 1.0, 0.92, 0.90),
            shadow=(0, 0, 0, 0.88),
            mayChange=True,
        )
        self.hit_confirm_text = OnscreenText(
            text="",
            parent=self.reticle_root,
            pos=(0.0, -0.118),
            align=TextNode.ACenter,
            scale=0.033,
            fg=(1.0, 0.92, 0.30, 0.0),
            shadow=(0, 0, 0, 0.90),
            mayChange=True,
        )
        self.weapon_upgrade_text = OnscreenText(
            text="WEAPON PULSE RIFLE MK I // NEXT UPGRADE 000%",
            parent=self.reticle_root,
            pos=(1.30, -0.78),
            align=TextNode.ARight,
            scale=0.032,
            fg=(0.70, 1.0, 0.92, 0.90),
            shadow=(0, 0, 0, 0.88),
            mayChange=True,
        )
        self._owned.extend([self.event_feed_text, self.hit_confirm_text, self.weapon_upgrade_text])

        self.phase_banner = OnscreenText(
            text="SCENERY SHIFT // PRISM FOUNDRY",
            parent=self.reticle_root,
            pos=(0.0, 0.72),
            align=TextNode.ACenter,
            scale=0.050,
            fg=(0.76, 1.0, 0.92, 0.90),
            shadow=(0, 0, 0, 0.90),
            mayChange=True,
        )
        self._owned.append(self.phase_banner)

        self.upgrade_overlay_root = self.aspect2d.attachNewNode("vector_arena_pass04_upgrade_overlay")
        panel = CardMaker("vector_arena_pass04_upgrade_panel")
        panel.setFrame(-1.05, 1.05, -0.60, 0.60)
        panel_np = self.upgrade_overlay_root.attachNewNode(panel.generate())
        panel_np.setColor(0.006, 0.012, 0.022, 0.94)
        panel_np.setTransparency(TransparencyAttrib.MAlpha)
        self.upgrade_choice_text = OnscreenText(
            text="", parent=self.upgrade_overlay_root, pos=(0.0, 0.43), align=TextNode.ACenter,
            scale=0.052, fg=(0.72, 1.0, 0.94, 0.98), shadow=(0,0,0,0.92), mayChange=True,
        )
        self.upgrade_mutation_text = OnscreenText(
            text="", parent=self.upgrade_overlay_root, pos=(0.0, -0.43), align=TextNode.ACenter,
            scale=0.034, fg=(1.0, 0.70, 0.30, 0.94), shadow=(0,0,0,0.92), mayChange=True,
        )
        self._owned.extend([self.upgrade_overlay_root, panel_np, self.upgrade_choice_text, self.upgrade_mutation_text])
        self.upgrade_overlay_root.hide()

        cm = CardMaker("vector_arena_fps_damage_overlay")
        cm.setFrameFullscreenQuad()
        self.damage_overlay = self.render2d.attachNewNode(cm.generate())
        self.damage_overlay.setColor(1.0, 0.05, 0.05, 0.0)
        self.damage_overlay.setTransparency(TransparencyAttrib.MAlpha)
        self._owned.append(self.damage_overlay)

        assert self.local_ui_root is not None
        self.help_text = OnscreenText(
            text=(
                "VECTOR ARENA // FIRST-PERSON ARCADE SHOOTER\n"
                "WASD move  Mouse look  LMB pulse rifle  RMB repulsor blast  Shift dash  R vent heat\n"
                "Destroy breach cores, read charging spawn gates, evade marked floor hazards, survive waves. After Guardian sets choose 1/2/3 mutations. TAB returns in HoloVerse; ESC is host pause."
            ),
            parent=self.local_ui_root,
            pos=(-1.30, 0.86),
            align=TextNode.ALeft,
            scale=0.035,
            fg=(0.74, 0.96, 1.0, 0.90),
            shadow=(0, 0, 0, 0.80),
            mayChange=True,
        )
        self._owned.append(self.help_text)

        # Native HoloVerse owns only TAB.  ESC/H therefore belong to this
        # dimension while mounted.  Keep the pause layer hidden unless toggled
        # so it never occupies gameplay space during normal combat.
        self.pause_overlay_root = self.aspect2d.attachNewNode("vector_arena_native_pause_overlay")
        pause_card = CardMaker("vector_arena_native_pause_panel")
        pause_card.setFrame(-0.72, 0.72, -0.28, 0.28)
        pause_panel = self.pause_overlay_root.attachNewNode(pause_card.generate())
        pause_panel.setColor(0.004, 0.008, 0.018, 0.90)
        pause_panel.setTransparency(TransparencyAttrib.MAlpha)
        self.pause_text = OnscreenText(
            text="VECTOR ARENA // PAUSED\n\nESC  RESUME\nH  HELP\nTAB  RETURN TO HOLOVERSE",
            parent=self.pause_overlay_root, pos=(0.0, 0.10), align=TextNode.ACenter,
            scale=0.048, fg=(0.76, 0.98, 1.0, 0.98), shadow=(0,0,0,0.92), mayChange=False,
        )
        self.pause_overlay_root.hide()
        self._owned.extend([self.pause_overlay_root, pause_panel, self.pause_text])

    def _build_scene(self):
        self._build_lights()
        self._build_arena_geometry()
        self._build_score_board()
        self._build_enemy_pool()
        self._build_projectile_pool()
        self._build_breach_core_pool()
        self._build_hazard_pool()
        self._build_weapon_viewmodel()
        self._build_reticle_and_hud()
        self._apply_scenery_theme(0, instant=True)

    def _current_theme(self) -> dict:
        profile = self.arena_profile
        def v(key):
            value = profile[key]
            return Vec4(float(value[0]), float(value[1]), float(value[2]), float(value[3]))
        return {
            "name": str(profile["name"]),
            "primary": v("wire_primary"),
            "secondary": v("wire_secondary"),
            "accent": v("wire_accent"),
            "floor": v("floor"),
            "sky": tuple(profile.get("sky", (0.002, 0.004, 0.010))),
        }

    def _set_nodes_color(self, nodes: list[NodePath], color: Vec4):
        for node in nodes:
            try:
                node.setColor(color)
                node.setColorScale(1, 1, 1, 1)
            except Exception:
                pass

    def _apply_scenery_theme(self, index: int | None = None, instant: bool = False):
        if index is not None:
            self.theme_index = int(index) % len(SCENERY_THEMES)
        theme = self._current_theme()
        self.theme_pulse = 1.0 if not instant else 0.25
        blackout = self.wave_kind == "BLACKOUT"
        brightness = 0.28 if blackout else 1.0
        overload = self.wave_kind == "OVERLOAD"
        def scaled(color: Vec4, mult: float = 1.0) -> Vec4:
            m = brightness * mult
            return Vec4(color.x * m, color.y * m, color.z * m, color.w)
        self._set_nodes_color(self.scenery_nodes.get("primary", []), scaled(theme["primary"], 0.78 if overload else 1.0))
        self._set_nodes_color(self.scenery_nodes.get("secondary", []), scaled(theme["secondary"], 0.70 if overload else 1.0))
        accent = Vec4(1.0, 0.10, 0.12, theme["accent"].w) if overload else theme["accent"]
        self._set_nodes_color(self.scenery_nodes.get("accent", []), scaled(accent, 1.15 if overload else 1.0))
        self._set_nodes_color(self.scenery_nodes.get("floor", []), scaled(theme["floor"], 0.45 if blackout else 1.0))
        cover_color = Vec4(theme["primary"].x * 0.30 * brightness, theme["primary"].y * 0.42 * brightness, theme["primary"].z * 0.46 * brightness, 0.22)
        self._set_nodes_color(self.cover_glow_nodes, cover_color)
        for core in getattr(self, "breach_cores", []):
            try:
                core.node.setColorScale(theme["accent"])
            except Exception:
                pass
        try:
            sky = theme.get("sky", (0.002, 0.004, 0.010))
            sky_mult = 0.16 if blackout else 1.0
            self.setBackgroundColor(float(sky[0]) * sky_mult, float(sky[1]) * sky_mult, float(sky[2]) * sky_mult)
        except Exception:
            pass
        if self.phase_banner is not None:
            self.phase_banner["text"] = f"{self.wave_kind} // {theme['name']}"
        if not instant:
            self._push_combat_event(f"ARENA STATE // {self.wave_kind} // {theme['name']}", "wave")
        if self.help_text is not None:
            self.help_text["text"] = (
                f"VECTOR ARENA // {self.wave_kind} // {theme['name']} // {int(self.current_arena_radius * 2)}u\n"
                "WASD move  Mouse look  LMB pulse rifle  RMB repulsor blast  Shift dash  R vent heat\n"
                "Clear every threat in the wave. Breach waves also require every marked core to be sealed."
            )

    def _wave_kind_for(self, wave: int) -> str:
        return wave_kind_for(wave)

    def _wave_plan(self, wave: int) -> dict:
        base = build_wave_plan(wave)
        set_number = (max(1, int(wave)) - 1) // WAVE_SET_SIZE + 1
        return apply_mutation_to_plan(base, set_number, MAX_ACTIVE_THREATS)

    def _refresh_upgrade_effects(self):
        effects = upgrade_effects(self.upgrade_stacks)
        old_max_armor = float(self.max_armor)
        self.weapon_mutation_mult = float(effects["weapon_damage_mult"])
        self.max_armor = float(effects["max_armor"])
        self.incoming_damage_mult = float(effects["incoming_damage_mult"])
        self.hazard_damage_resist_mult = float(effects["hazard_damage_mult"])
        self.repulsor_cooldown_mult = float(effects["repulsor_cooldown_mult"])
        self.reconstruction_health_restore = float(effects["reconstruction_health"])
        self.reconstruction_armor_restore = float(effects["reconstruction_armor"])
        if self.max_armor > old_max_armor:
            self.armor = min(self.max_armor, self.armor + (self.max_armor - old_max_armor))

    def _open_upgrade_choice(self):
        if self.upgrade_pending:
            return
        self.upgrade_pending = True
        self.wave_complete_pending = False
        for slot in (1, 2, 3):
            self._upgrade_key_latches[slot] = self._key_down(str(slot))
        self.upgrade_choices_cache = upgrade_choices(self.upgrade_stacks)
        next_mutation = arena_mutation_for_set(self.wave_set + 1)
        next_arena = arena_profile_for_set(self.wave_set + 1)
        if self.upgrade_choice_text is not None:
            lines = [
                f"SET {self.wave_set:02d} CLEARED // CHOOSE ONE MUTATION",
                "",
            ]
            for choice in self.upgrade_choices_cache:
                lines.append(f"[{choice['slot']}] {choice['title']}  //  STACK {choice['next_stack']:02d}")
                lines.append(f"    {choice['category']}  //  {choice['summary']}")
                lines.append("")
            lines.append("Combat is paused. Selection has no timer.")
            self.upgrade_choice_text["text"] = "\n".join(lines)
        if self.upgrade_mutation_text is not None:
            self.upgrade_mutation_text["text"] = (
                f"NEXT ARENA // {next_arena['name']} // {int(next_arena['diameter'])}u DIAMETER\n"
                f"MUTATION // {next_mutation['name']} // {next_mutation['summary']}"
            )
        if self.upgrade_overlay_root is not None:
            self.upgrade_overlay_root.show()
        self._play_sfx("upgrade_offer")
        self._push_combat_event("GUARDIAN CHECKPOINT // MUTATION CHOICE READY", "wave")

    def _select_upgrade(self, slot: int) -> bool:
        if not self.upgrade_pending:
            return False
        choice = next((item for item in self.upgrade_choices_cache if int(item.get("slot", 0)) == int(slot)), None)
        if choice is None:
            return False
        upgrade_id = str(choice["id"])
        self.upgrade_stacks[upgrade_id] = int(self.upgrade_stacks.get(upgrade_id, 0)) + 1
        self.upgrades_selected += 1
        self._refresh_upgrade_effects()
        self.health = min(self.max_health, self.health + 8.0)
        self.armor = min(self.max_armor, self.armor + 12.0)
        self.heat = max(0.0, self.heat - 30.0)
        self.upgrade_pending = False
        self.upgrade_choices_cache = []
        self._mouse1_latched = False
        self._mouse3_latched = False
        self._r_latched = False
        self._block_combat_input_until_release = True
        if self.upgrade_overlay_root is not None:
            self.upgrade_overlay_root.hide()
        self._play_sfx("upgrade_select")
        self._push_combat_event(f"MUTATION INSTALLED // {choice['title']} STACK {self.upgrade_stacks[upgrade_id]:02d}", "wave")
        self._advance_wave()
        return True

    def _update_upgrade_choice(self):
        if not self.upgrade_pending:
            return False
        for slot, key in ((1, "1"), (2, "2"), (3, "3")):
            down = self._key_down(key)
            latched = bool(self._upgrade_key_latches.get(slot, False))
            if down and not latched:
                self._upgrade_key_latches[slot] = True
                self._select_upgrade(slot)
                return True
            if not down:
                self._upgrade_key_latches[slot] = False
        return True

    def _apply_cover_layout(self, layout_index: int):
        """Pass 07 compatibility hook. Architecture is authored per family.

        Reconstruction already rebuilds the correct strategic family geometry,
        so this function intentionally never moves solids independently of their
        blocker data. It only guarantees that a player caught by a rebuild is
        pushed into legal open space.
        """
        self._push_out_of_cover()

    def _reconstruct_arena(self, set_number: int):
        self.reconstruction_count += 1
        self._apply_arena_profile(set_number, rebuild=True)
        self._apply_cover_layout(set_number - 1)
        self._apply_scenery_theme(set_number - 1, instant=False)
        self.theme_pulse = max(self.theme_pulse, 1.45)
        self.health = min(self.max_health, self.health + self.reconstruction_health_restore)
        self.armor = min(self.max_armor, self.armor + self.reconstruction_armor_restore)
        self.heat = max(0.0, self.heat - 18.0)
        self._play_sfx("arena_reconstruct")
        self._play_sfx("mutation_shift")
        mutation = self.arena_mutation_profile
        self._push_combat_event(
            f"ARENA RECONSTRUCTION {self.reconstruction_count:02d} // {self.arena_profile['name']} // "
            f"{int(self.arena_profile['diameter'])}u // {mutation.get('name','STABLE MATRIX')}", "wave"
        )

    def _begin_wave(self, wave: int):
        # Optional Breach cores never leak across wave boundaries. Required cores
        # must already be sealed before the director allows this transition.
        for core in self.breach_cores:
            if core.active:
                if self.audio_runtime is not None and core.audio_loop is not None:
                    try:
                        self.audio_runtime.stop_loop(core.audio_loop)
                    except Exception:
                        pass
                core.audio_loop = None
                core.active = False
                core.node.hide()
        self.breach_pressure = 0.0
        self.wave = max(1, int(wave))
        self.highest_wave = max(self.highest_wave, self.wave)
        self.wave_set = (self.wave - 1) // WAVE_SET_SIZE + 1
        if self.wave == 1:
            self._apply_arena_profile(1, rebuild=False)
        plan = self._wave_plan(self.wave)
        self.arena_mutation_profile = dict(plan.get("arena_mutation", arena_mutation_for_set(self.wave_set)))
        self.wave_kind = str(plan["kind"])
        self.special_wave_counts[self.wave_kind] = self.special_wave_counts.get(self.wave_kind, 0) + 1
        self.encounter_doctrine = encounter_doctrine_for(self.wave_kind, self.wave_set)
        self._wave_evolution_announced.clear()
        self.wave_spawn_queue = list(plan["queue"])
        self.wave_spawn_script = [dict(item) for item in plan.get("spawn_script", [])]
        self.pending_spawns.clear()
        self.wave_total_threats = len(self.wave_spawn_queue)
        self.wave_spawned = 0
        self.wave_defeated = 0
        self.wave_spawn_interval = float(plan["spawn_interval"])
        self.wave_spawn_timer = 0.20
        self.wave_max_active = int(plan["max_active"])
        self.wave_required_breaches = int(plan["required_breaches"])
        self.wave_breach_start_sealed = int(self.breaches_sealed)
        self.wave_forced_breach_timer = 1.4
        self.wave_heat_gain_mult = float(plan["heat_gain"])
        self.wave_heat_cool_mult = float(plan["heat_cool"])
        self.hazard_profile = dict(plan.get("hazard", {"kind": "NONE", "enabled": False}))
        self.hazard_timer = 2.5 if self.hazard_profile.get("enabled") else 999.0
        for hazard in self.arena_hazards:
            hazard.state = "idle"
            hazard.timer = 0.0
            hazard.player_hit = False
            hazard.node.hide()
        self.wave_complete_pending = False
        self.wave_intermission_timer = 0.0
        self.wave_intro_timer = 2.1
        self.breach_spawn_timer = 9.0
        self.armor = min(self.max_armor, self.armor + (14.0 if self.wave_kind == "GUARDIAN" else 9.0))
        self.health = min(self.max_health, self.health + (10.0 if self.wave_kind == "GUARDIAN" else 6.0))
        if self.wave > 1 and (self.wave - 1) % WAVE_SET_SIZE == 0:
            self._reconstruct_arena(self.wave_set)
        else:
            self._apply_scenery_theme(self.wave_set - 1, instant=self.wave == 1)
        if self.wave_kind == "HORDE":
            self._play_sfx("horde_alarm")
        elif self.wave_kind == "GUARDIAN":
            self._play_sfx("guardian_alarm")
            self._push_combat_event(f"GUARDIAN WAVE // SET {self.wave_set:02d} CHECKPOINT", "danger")
        else:
            self._play_sfx("wave_start")
        modifier = " // HEAT SURGE + ARC HAZARDS" if self.wave_kind == "OVERLOAD" else " // LOW VISIBILITY + SCAN HAZARDS" if self.wave_kind == "BLACKOUT" else " // REDLINE HAZARDS" if self.wave_kind == "GUARDIAN" else ""
        breach = f" // SEAL {self.wave_required_breaches} CORE(S)" if self.wave_required_breaches else ""
        mutation_name = str(self.arena_mutation_profile.get("name", "STABLE MATRIX"))
        doctrine_name = str(self.encounter_doctrine.get("name", "BASELINE DISCIPLINE"))
        if self.encounter_doctrine.get("active"):
            self._play_sfx("doctrine_shift")
        if self.phase_banner is not None:
            self.phase_banner["text"] = f"{self.wave_kind} // {doctrine_name}"
        self._push_combat_event(
            f"WAVE {self.wave:02d} // {self.wave_kind} // {self.wave_total_threats} THREATS{breach}{modifier} // "
            f"{self.arena_profile['name']} {int(self.current_arena_radius * 2)}u // {mutation_name} // {doctrine_name}", "wave"
        )

    def _pending_variant_count(self, variant: str) -> int:
        return sum(1 for pending in self.pending_spawns if pending.get("directive", {}).get("variant") == variant)

    def _schedule_spawn_from_script(self) -> bool:
        if not self.wave_spawn_script:
            return False
        active = sum(1 for enemy in self.enemies if enemy.active)
        if active + len(self.pending_spawns) >= self.wave_max_active:
            return False
        # Find the first directive whose pooled variant has a free slot even
        # after already-telegraphed pending spawns are accounted for.
        chosen_index = None
        for index, directive in enumerate(self.wave_spawn_script):
            wanted = str(directive.get("variant", "stalker"))
            inactive = sum(1 for enemy in self.enemies if (not enemy.active and enemy.variant == wanted))
            if inactive > self._pending_variant_count(wanted):
                chosen_index = index
                break
        if chosen_index is None:
            return False
        directive = self.wave_spawn_script.pop(chosen_index)
        wanted = str(directive.get("variant", "stalker"))
        try:
            self.wave_spawn_queue.remove(wanted)
        except ValueError:
            pass
        pending = {"directive": directive, "timer": float(directive.get("telegraph", 0.65))}
        self.pending_spawns.append(pending)
        gate = int(directive.get("gate", 1)) % max(1, len(self.spawn_points))
        self._play_sfx("gate_charge", self.spawn_points[gate] + Vec3(0,0,4))
        role = str(directive.get("role", "pressure"))
        if role in {"flank_left", "flank_right", "rear_left", "rear_right"}:
            self.flanking_spawns += 1
            if self._elapsed - float(self._last_sfx_time.get("flank_alarm", -999.0)) >= 0.85:
                self._play_sfx("flank_alarm")
                self._push_combat_event(f"TACTICAL GATE // {GATE_LABELS[gate]} // {role.replace('_',' ').upper()}", "danger")
        return True

    def _activate_pending_spawn(self, pending: dict) -> bool:
        directive = pending.get("directive", {})
        wanted = str(directive.get("variant", "stalker"))
        for slot, enemy in enumerate(self.enemies):
            if not enemy.active and enemy.variant == wanted:
                self.wave_spawned += 1
                self._spawn_enemy(enemy, slot, directive=directive)
                return True
        return False

    def _update_pending_spawns(self, dt: float):
        for pending in list(self.pending_spawns):
            pending["timer"] = float(pending.get("timer", 0.0)) - dt
            if pending["timer"] > 0.0:
                continue
            if self._activate_pending_spawn(pending):
                self.pending_spawns.remove(pending)
            else:
                pending["timer"] = 0.12

    def _update_spawn_gate_visuals(self):
        charged = {}
        for pending in self.pending_spawns:
            directive = pending.get("directive", {})
            gate = int(directive.get("gate", 1))
            charged[gate] = max(charged.get(gate, 0.0), float(pending.get("timer", 0.0)))
        for index, root in enumerate(self.spawn_gate_groups):
            try:
                if index in charged:
                    pulse = 1.15 + 0.28 * (0.5 + 0.5 * math.sin(self._elapsed * 16.0 + index))
                    root.setColorScale(pulse, 0.54 + pulse * 0.16, 0.72, 1.0)
                else:
                    root.clearColorScale()
            except Exception:
                pass

    def _advance_wave(self):
        self._begin_wave(self.wave + 1)

    def _update_wave_director(self, dt: float):
        if self.wave <= 0:
            return
        active = sum(1 for enemy in self.enemies if enemy.active)
        self._update_pending_spawns(dt)
        self._update_spawn_gate_visuals()
        if self.wave_intro_timer > 0.0:
            return
        if self.wave_required_breaches > 0:
            sealed_this_wave = max(0, self.breaches_sealed - self.wave_breach_start_sealed)
            active_cores = len(self._active_breach_cores())
            if sealed_this_wave + active_cores < self.wave_required_breaches:
                self.wave_forced_breach_timer = max(0.0, self.wave_forced_breach_timer - dt)
                if self.wave_forced_breach_timer <= 0.0:
                    self._spawn_breach_core()
                    self.wave_forced_breach_timer = 2.0
        if self.wave_spawn_script:
            self.wave_spawn_timer = max(0.0, self.wave_spawn_timer - dt)
            if self.wave_spawn_timer <= 0.0:
                burst = 2 if self.wave_kind == "HORDE" else 1
                spawned = 0
                for _ in range(burst):
                    if self._schedule_spawn_from_script():
                        spawned += 1
                    else:
                        break
                if spawned:
                    self.wave_spawn_timer = self.wave_spawn_interval
        active = sum(1 for enemy in self.enemies if enemy.active)
        sealed_this_wave = max(0, self.breaches_sealed - self.wave_breach_start_sealed)
        objective_done = sealed_this_wave >= self.wave_required_breaches
        wave_clear = not self.wave_spawn_script and not self.pending_spawns and active == 0 and objective_done
        if wave_clear and not self.wave_complete_pending:
            self.wave_complete_pending = True
            self.wave_intermission_timer = 2.8 if self.wave_kind != "GUARDIAN" else 4.0
            if self.wave_kind == "GUARDIAN":
                self.guardian_waves_completed += 1
                if self.wave_set > 1:
                    self.arena_mutations_survived += 1
                self._push_combat_event(f"SET {self.wave_set:02d} CLEARED // GUARDIAN DOWN", "wave")
            else:
                self._push_combat_event(f"WAVE {self.wave:02d} CLEARED // RECONSTRUCTING THREAT MODEL", "wave")
        if self.wave_complete_pending:
            self.wave_intermission_timer = max(0.0, self.wave_intermission_timer - dt)
            if self.wave_intermission_timer <= 0.0:
                if self.wave_kind == "GUARDIAN":
                    self._open_upgrade_choice()
                else:
                    self._advance_wave()

    def _arm_wave_hazard(self) -> bool:
        if not self.hazard_profile.get("enabled"):
            return False
        free = next((hazard for hazard in self.arena_hazards if hazard.state == "idle"), None)
        if free is None:
            return False
        points = tuple(Vec3(x, y, 0.08) for x, y in hazard_points_for_profile(self.arena_profile))
        # Deterministic cycling, with one skip when the chosen point is directly
        # under the player so hazards remain warnings rather than unavoidable hits.
        point = points[self.hazard_cursor % len(points)]
        self.hazard_cursor += 1
        if (point - self.player_pos).length() < 9.0:
            point = points[self.hazard_cursor % len(points)]
            self.hazard_cursor += 1
        profile = self.hazard_profile
        free.pos = Vec3(point)
        free.state = "warning"
        free.timer = float(profile.get("telegraph", 1.0))
        free.radius = float(profile.get("radius", 10.0))
        free.damage = float(profile.get("damage", 10.0))
        free.heat = float(profile.get("heat", 0.0))
        free.kind = str(profile.get("kind", "HAZARD"))
        free.player_hit = False
        free.node.setPos(free.pos)
        free.node.setScale(free.radius)
        free.node.setColorScale(1.0, 0.80, 0.22, 0.82)
        free.node.show()
        self.hazard_activations += 1
        self._play_sfx("hazard_warning", free.pos)
        return True

    def _apply_hazard_hit(self, hazard: _ArenaHazard):
        damage = hazard.damage * self.hazard_damage_resist_mult
        if self.armor > 0.0:
            used = min(self.armor, damage * 0.70)
            self.armor -= used
            damage -= used * 0.55
        self.health = max(0.0, self.health - damage)
        self.heat = min(MAX_HEAT, self.heat + hazard.heat)
        push = Vec3(self.player_pos - hazard.pos)
        push.z = 0
        if push.lengthSquared() > 0.001:
            push.normalize()
            self.player_vel += push * 22.0
        self.damage_flash = max(self.damage_flash, 0.28)
        self.hazard_hits_taken += 1
        self._play_sfx("player_hit")
        self._push_combat_event(f"{hazard.kind} CONTACT // MOVE OFF THE MARKED FLOOR", "danger")

    def _update_wave_hazards(self, dt: float):
        if self.wave_complete_pending or self.upgrade_pending:
            for hazard in self.arena_hazards:
                if hazard.state != "idle":
                    hazard.state = "idle"
                    hazard.node.hide()
            return
        if not self.hazard_profile.get("enabled") or self.wave_intro_timer > 0.0:
            return
        self.hazard_timer = max(0.0, self.hazard_timer - dt)
        if self.hazard_timer <= 0.0:
            self._arm_wave_hazard()
            self.hazard_timer = float(self.hazard_profile.get("interval", 4.0))
        for hazard in self.arena_hazards:
            if hazard.state == "idle":
                continue
            hazard.timer -= dt
            if hazard.state == "warning":
                pulse = 0.88 + 0.12 * math.sin(self._elapsed * 13.0)
                hazard.node.setColorScale(1.0, 0.65 + 0.25 * pulse, 0.10, 0.72 + 0.20 * pulse)
                if hazard.timer <= 0.0:
                    hazard.state = "hot"
                    hazard.timer = float(self.hazard_profile.get("active", 0.65))
                    hazard.node.setColorScale(1.0, 0.10, 0.18, 0.96)
                    self._play_sfx("hazard_discharge", hazard.pos)
            elif hazard.state == "hot":
                pulse = 1.0 + 0.10 * math.sin(self._elapsed * 25.0)
                hazard.node.setScale(hazard.radius * pulse)
                if not hazard.player_hit and (self.player_pos - hazard.pos).length() <= hazard.radius:
                    hazard.player_hit = True
                    self._apply_hazard_hit(hazard)
                if hazard.timer <= 0.0:
                    hazard.state = "idle"
                    hazard.node.hide()

    def _update_scenery(self, dt: float):
        self.theme_pulse = max(0.0, self.theme_pulse - dt * 0.70)
        if self.wave_intro_timer > 0.0:
            self.wave_intro_timer = max(0.0, self.wave_intro_timer - dt)
        pulse = 1.0 + self.theme_pulse * 0.04
        for i, node in enumerate(self.scenery_motion_nodes):
            try:
                if "overhead_ring" in node.getName():
                    node.setH((self._elapsed * (4.0 + i * 1.2)) % 360.0)
                    node.setScale(pulse + math.sin(self._elapsed * 1.4 + i) * 0.008)
                else:
                    node.setScale(1.0, 1.0, pulse + math.sin(self._elapsed * 2.0 + i) * 0.010)
            except Exception:
                pass
        if self.phase_banner is not None:
            alpha = 0.0
            if self.wave_intro_timer > 0.0:
                alpha = min(0.95, 0.35 + self.wave_intro_timer * 0.32)
            elif self.theme_pulse > 0.0:
                alpha = min(0.70, self.theme_pulse)
            self.phase_banner.setColorScale(1, 1, 1, alpha)

    # ------------------------------------------------------------------
    # Input helpers
    # ------------------------------------------------------------------
    def _keyboard_button(self, name: str):
        try:
            if len(name) == 1:
                return KeyboardButton.asciiKey(name)
            if name == "space":
                return KeyboardButton.space()
            if name == "shift":
                return KeyboardButton.shift()
            if name == "arrow_up":
                return KeyboardButton.up()
            if name == "arrow_down":
                return KeyboardButton.down()
            if name == "arrow_left":
                return KeyboardButton.left()
            if name == "arrow_right":
                return KeyboardButton.right()
        except Exception:
            return None
        return None

    def _button_down(self, button) -> bool:
        watcher = getattr(self.host, "mouseWatcherNode", None)
        if watcher is None or button is None:
            return False
        try:
            return bool(watcher.isButtonDown(button))
        except Exception:
            try:
                return bool(watcher.is_button_down(button))
            except Exception:
                return False

    def _key_down(self, *names: str) -> bool:
        return any(self._button_down(self._keyboard_button(name)) for name in names)

    def _mouse_down(self, index: int) -> bool:
        try:
            button = MouseButton.one() if index == 1 else MouseButton.three()
            return self._button_down(button)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Audio helpers
    # ------------------------------------------------------------------
    def _read_audio_config(self):
        """Read standalone audio settings without requiring HoloVerse.

        The adapter still works inside a host, but a split-out standalone build
        needs its own master SFX switch/volume and per-event mix.  Failures stay
        silent so validation and machines without sound devices remain safe.
        """
        self.sfx_enabled = True
        self.sfx_master_volume = 0.85
        self.sfx_volumes = dict(VECTOR_ARENA_SFX_VOLUME_DEFAULTS)
        config_path = self.folder / "vector_arena_config.json"
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            audio = data.get("audio", {}) if isinstance(data, dict) else {}
            if isinstance(audio, dict):
                enabled = audio.get("sfx_enabled", audio.get("enabled", True))
                if isinstance(enabled, str):
                    enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
                self.sfx_enabled = bool(enabled)
                self.sfx_master_volume = _clamp(float(audio.get("sfx_master_volume", 0.85)), 0.0, 1.0)
                volumes = audio.get("sfx_volumes", {})
                if isinstance(volumes, dict):
                    for key, value in volumes.items():
                        if str(key) in VECTOR_ARENA_SFX_FILES:
                            self.sfx_volumes[str(key)] = _clamp(float(value), 0.0, 1.0)
        except Exception:
            pass

    @staticmethod
    def _panda_audio_filename(path: Path) -> str:
        try:
            return Filename.fromOsSpecific(str(path.resolve())).getFullpath()
        except Exception:
            try:
                return Filename.fromOsSpecific(str(path)).getFullpath()
            except Exception:
                return str(path)

    def _load_sfx(self):
        """Load the complete local Vector Arena audio runtime.

        This remains host-safe: all sounds are local references and are
        explicitly stopped when the dimension exits. Missing/disabled audio
        never prevents gameplay from starting.
        """
        self.sfx.clear()
        self._last_sfx_time.clear()
        self.sfx_loaded_count = 0
        try:
            self.audio_runtime = VectorArenaAudioRuntime(self.host, self.folder)
            self.audio_runtime.load()
            self.audio_runtime.start()
            stats = self.audio_runtime.stats()
            self.sfx_loaded_count = int(stats.get("audio_loaded", 0))
            self.sfx = self.audio_runtime.sfx
            self.sfx_enabled = bool(self.audio_runtime.sfx_enabled)
        except Exception:
            self.audio_runtime = None
            self.sfx_enabled = False

    def _play_sfx(self, key: str, pos=None) -> bool:
        if self.audio_runtime is not None:
            try:
                return bool(self.audio_runtime.play(str(key), pos=pos))
            except Exception:
                return False
        return False

    # ------------------------------------------------------------------
    # Gameplay
    # ------------------------------------------------------------------
    def _push_combat_event(self, text: str, severity: str = "info"):
        """Push a compact player-facing combat-event feed line.

        Text-only feed keeps the 16:9 corners useful without creating nodes at
        runtime.  It is intentionally not the hidden legacy/debug dimension UI.
        """
        label = str(text or "").strip()
        if not label:
            return
        label = label[:72]
        self.combat_events.insert(0, (label, 3.6, str(severity or "info")))
        del self.combat_events[5:]

    def _update_combat_event_feed(self, dt: float):
        kept: list[tuple[str, float, str]] = []
        for label, ttl, severity in self.combat_events:
            ttl = float(ttl) - dt
            if ttl > 0.0:
                kept.append((label, ttl, severity))
        self.combat_events = kept
        if self.event_feed_text is not None:
            if not self.combat_events:
                self.event_feed_text["text"] = ""
                self.event_feed_text.setColorScale(1, 1, 1, 0.0)
            else:
                lines = []
                for label, ttl, severity in self.combat_events[:4]:
                    prefix = "!!" if severity == "danger" else "//" if severity == "wave" else ">>"
                    lines.append(f"{prefix} {label}")
                self.event_feed_text["text"] = "\n".join(lines)
                self.event_feed_text.setColorScale(1, 1, 1, min(1.0, 0.42 + self.combat_events[0][1] * 0.22))
        if self.hit_confirm_text is not None:
            alpha = max(self.hit_marker_timer, self.kill_marker_timer)
            if self.kill_marker_timer > 0.0:
                self.hit_confirm_text["text"] = "CORE BROKEN"
                self.hit_confirm_text.setColor(1.0, 0.84, 0.24, min(1.0, alpha * 3.2))
            elif self.hit_marker_timer > 0.0:
                self.hit_confirm_text["text"] = "HIT"
                self.hit_confirm_text.setColor(0.70, 1.0, 0.92, min(0.9, alpha * 4.4))
            else:
                self.hit_confirm_text["text"] = ""
                self.hit_confirm_text.setColor(1.0, 1.0, 1.0, 0.0)
        if self.reticle_root is not None:
            pulse = max(self.hit_marker_timer * 1.8, self.kill_marker_timer * 2.4, self.combo_flash_timer * 0.6)
            try:
                self.reticle_root.setScale(1.0 + min(0.09, pulse * 0.035))
            except Exception:
                pass

    def _weapon_tier(self) -> dict:
        index = max(0, min(WEAPON_UPGRADE_TIER_COUNT - 1, int(self.weapon_rank) - 1))
        return WEAPON_UPGRADE_TIERS[index]

    def _next_weapon_tier(self) -> dict | None:
        if int(self.weapon_rank) >= WEAPON_UPGRADE_TIER_COUNT:
            return None
        return WEAPON_UPGRADE_TIERS[int(self.weapon_rank)]

    def _refresh_weapon_upgrade(self):
        """Advance the match weapon rank from score/kills/wave progress.

        Pass 101 keeps upgrades automatic and readable: no shop screen, no new
        control burden, and no runtime node creation.  The player gets a clear
        arcade reward loop while the same LMB/RMB heat-management controls stay.
        """
        desired_rank = 1
        for tier in WEAPON_UPGRADE_TIERS:
            unlocked = (
                self.kills >= int(tier["unlock_kills"])
                or self.score >= int(tier["unlock_score"])
                or self.wave >= int(tier["unlock_wave"])
            )
            if unlocked:
                desired_rank = max(desired_rank, int(tier["rank"]))
        if desired_rank > self.weapon_rank:
            self.weapon_rank = desired_rank
            self.weapon_module_name = str(self._weapon_tier()["name"])
            self.weapon_upgrade_notice_timer = 3.6
            self.weapon_rank_flash = 1.0
            self.weapon_charge = 1.0
            self.repulsor_flash = max(self.repulsor_flash, 0.70)
            self.heat = max(0.0, self.heat - 22.0)
            self._push_combat_event(f"WEAPON UPGRADE // {self.weapon_module_name}", "wave")
        next_tier = self._next_weapon_tier()
        if next_tier is None:
            self.weapon_upgrade_charge = 1.0
        else:
            kill_need = max(1, int(next_tier["unlock_kills"]) - int(self._weapon_tier()["unlock_kills"]))
            score_need = max(1, int(next_tier["unlock_score"]) - int(self._weapon_tier()["unlock_score"]))
            wave_need = max(1, int(next_tier["unlock_wave"]) - int(self._weapon_tier()["unlock_wave"]))
            kill_progress = (self.kills - int(self._weapon_tier()["unlock_kills"])) / kill_need
            score_progress = (self.score - int(self._weapon_tier()["unlock_score"])) / score_need
            wave_progress = (self.wave - int(self._weapon_tier()["unlock_wave"])) / wave_need
            self.weapon_upgrade_charge = _clamp(max(kill_progress, score_progress, wave_progress), 0.0, 1.0)

    def _arc_followup_target(self, primary: _Enemy, max_distance: float = 18.0) -> _Enemy | None:
        best: _Enemy | None = None
        best_dist = float(max_distance)
        for enemy in self.enemies:
            if enemy is primary or not enemy.active:
                continue
            dist = (enemy.pos - primary.pos).length()
            if dist < best_dist:
                best = enemy
                best_dist = dist
        return best

    def _spawn_pulse(self, pos: Vec3):
        for pulse in self.spawn_pulses:
            if not pulse.active:
                pulse.active = True
                pulse.age = 0.0
                pulse.pos = Vec3(pos)
                pulse.node.setPos(pos + Vec3(0, 0, 4.8))
                pulse.node.setScale(0.5)
                try:
                    pulse.node.setColor(self._current_theme()["accent"])
                except Exception:
                    pass
                pulse.node.show()
                return

    def _spawn_enemy(self, enemy: _Enemy, slot: int, initial: bool = False, directive: dict | None = None):
        directive = dict(directive or {})
        gate_index = int(directive.get("gate", slot % len(self.spawn_points))) % len(self.spawn_points)
        point = self.spawn_points[gate_index]
        jitter = Vec3(self._rng.uniform(-8, 8), self._rng.uniform(-5, 5), 0)
        enemy.pos = point + jitter
        enemy.vel = Vec3(0, 0, 0)
        profile = _enemy_profile(enemy.variant)
        progression = apply_enemy_progression(enemy.variant, self.wave_set, self.wave_kind)
        elite_bonus = 1.18 if self.wave_kind == "ELITE" else 1.0
        guardian_bonus = 1.22 if self.wave_kind == "GUARDIAN" and enemy.variant == "guardian" else 1.0
        wave_hp = self.wave * (3.0 if enemy.variant == "stalker" else 6.5)
        enemy.evolution_level = int(progression.get("level", 0))
        enemy.evolution_name = str(progression.get("name", "BASELINE FRAME"))
        enemy.evolution_hp_mult = float(progression.get("hp_mult", 1.0))
        enemy.evolution_speed_mult = float(progression.get("speed_mult", 1.0))
        enemy.evolution_damage_mult = float(progression.get("damage_mult", 1.0))
        enemy.evolution_attack_cooldown_mult = float(progression.get("attack_cooldown_mult", 1.0))
        enemy.evolution_score_mult = float(progression.get("score_mult", 1.0))
        enemy.evolution_lateral_mult = float(progression.get("lateral_mult", 1.0))
        enemy.evolution_special_cooldown_mult = float(progression.get("special_cooldown_mult", 1.0))
        enemy.max_hp = (float(profile["hp"]) + wave_hp) * elite_bonus * guardian_bonus * enemy.evolution_hp_mult
        enemy.hp = enemy.max_hp
        enemy.speed_scale = float(profile["speed"]) * enemy.evolution_speed_mult
        enemy.damage_scale = float(profile["damage"]) * enemy.evolution_damage_mult
        enemy.score_value = int(round(float(profile["score"]) * enemy.evolution_score_mult))
        enemy.aim_radius = float(profile["aim_radius"])
        enemy.attack_cooldown = self._rng.uniform(0.4, 1.6) * enemy.evolution_attack_cooldown_mult
        enemy.tactic_role = str(directive.get("role", "pressure"))
        enemy.spawn_gate = gate_index
        enemy.formation = int(directive.get("formation", 0))
        enemy.guardian_state = "idle"
        enemy.guardian_timer = self._rng.uniform(2.8, 4.2)
        enemy.guardian_attack_kind = ""
        enemy.guardian_attack_dir = None
        enemy.guardian_hit_player = False
        enemy.guardian_phase = 1
        if enemy.guardian_telegraph is not None:
            enemy.guardian_telegraph.hide()
        enemy.hit_flash = 0.0
        enemy.death_flash = 0.0
        enemy.active = True
        enemy.node.show()
        enemy.node.setPos(enemy.pos)
        enemy.node.setScale(float(profile.get("scale", 1.0)) * (1.0 + self.wave * 0.012) * (1.06 if self.wave_kind == "ELITE" else 1.0))
        try:
            enemy.node.clearColorScale()
            if enemy.class_marker is not None:
                enemy.class_marker.clearColorScale()
                enemy.class_marker.setScale(1.0 + 0.07 * enemy.evolution_level)
                if enemy.evolution_level > 0:
                    enemy.class_marker.setColorScale(1.0 + 0.10 * enemy.evolution_level, 0.92, 1.0 + 0.05 * enemy.evolution_level, 1.0)
        except Exception:
            pass
        if enemy.evolution_level > 0:
            self.enemy_evolution_spawns += 1
            self.enemy_evolution_counts[enemy.variant] = self.enemy_evolution_counts.get(enemy.variant, 0) + 1
            self.highest_evolution_level_seen = max(self.highest_evolution_level_seen, enemy.evolution_level)
            if enemy.variant not in self._wave_evolution_announced:
                self._wave_evolution_announced.add(enemy.variant)
                self._play_sfx("enemy_evolution", enemy.pos + Vec3(0,0,4))
                self._push_combat_event(f"EVOLUTION // {enemy.display_name} // {enemy.evolution_name} L{enemy.evolution_level}", "danger")
        if not initial:
            self._spawn_pulse(enemy.pos)
            if enemy.variant in {"guardian", "brute", "wraith"}:
                self._push_combat_event(f"{enemy.display_name} ENTERED THE RING", "danger" if enemy.variant == "guardian" else "info")
                if not self._play_sfx(f"enemy_{enemy.variant}", enemy.pos):
                    self._play_sfx("enemy_spawn", enemy.pos)

    def _architecture_hit(self, start: Vec3, end: Vec3):
        return first_architecture_hit(
            self.arena_profile,
            (float(start.x), float(start.y), float(start.z)),
            (float(end.x), float(end.y), float(end.z)),
        )

    def _architecture_blocks_segment(self, start: Vec3, end: Vec3) -> bool:
        hit = self._architecture_hit(start, end)
        return bool(hit is not None and float(hit.get("t", 2.0)) < 0.999)

    def _clip_segment_to_architecture(self, start: Vec3, end: Vec3) -> Vec3:
        hit = self._architecture_hit(start, end)
        if hit is None:
            return Vec3(end)
        point = hit.get("point")
        if not point:
            return Vec3(end)
        return Vec3(float(point[0]), float(point[1]), float(point[2]))

    def _clip_segment_to_arena_boundary(self, start: Vec3, end: Vec3) -> Vec3:
        """Clip a segment to the exact radial hardlight boundary."""
        sx, sy = float(start.x), float(start.y)
        dx, dy = float(end.x - start.x), float(end.y - start.y)
        a = dx * dx + dy * dy
        if a <= 1e-9:
            return Vec3(end)
        b = 2.0 * (sx * dx + sy * dy)
        c = sx * sx + sy * sy - self.current_arena_radius * self.current_arena_radius
        disc = b * b - 4.0 * a * c
        if disc < 0.0:
            return Vec3(end)
        root = math.sqrt(disc)
        candidates = [t for t in ((-b - root) / (2.0 * a), (-b + root) / (2.0 * a)) if 0.0 <= t <= 1.0]
        if not candidates:
            return Vec3(end)
        t = min(candidates)
        return Vec3(start + (end - start) * t)

    def _clip_combat_segment(self, start: Vec3, end: Vec3) -> Vec3:
        boundary_end = self._clip_segment_to_arena_boundary(start, end)
        return self._clip_segment_to_architecture(start, boundary_end)

    def _closest_target_in_reticle(self, max_range: float | None = None):
        if max_range is None:
            max_range = max(155.0, self.current_arena_radius * 1.12)
        eye = self.player_pos + Vec3(0, 0, EYE_HEIGHT)
        forward = _forward_vec(self.player_yaw, self.player_pitch)
        best_enemy = None
        best_score = -1.0
        for enemy in self.enemies:
            if not enemy.active:
                continue
            target = enemy.pos + Vec3(0, 0, 4.6 + enemy.tier * 0.42)
            delta = target - eye
            distance = delta.length()
            if distance <= 0.001 or distance > max_range:
                continue
            if self._architecture_blocks_segment(eye, target):
                continue
            aim = Vec3(delta)
            aim.normalize()
            dot = forward.dot(aim)
            # Slightly forgiving arcade cone.  Bigger enemies are easier to catch.
            required = 0.986 - enemy.aim_radius - enemy.tier * 0.006
            if dot >= required:
                score = dot * 3.0 - distance / max_range
                if score > best_score:
                    best_score = score
                    best_enemy = enemy
        return best_enemy

    def _emit_beam(self, start: Vec3, end: Vec3):
        for beam in self.projectiles:
            if not beam.active:
                beam.active = True
                beam.age = 0.0
                beam.life = 0.070
                delta = end - start
                length = max(0.1, delta.length())
                beam.node.setPos(start)
                try:
                    beam.node.lookAt(end)
                except Exception:
                    pass
                beam.node.setScale(1.0, length, 1.0)
                beam.node.setR(self._elapsed * 720.0)
                beam.node.setColorScale(1, 1, 1, 1)
                beam.node.show()
                return

    def _impact(self, pos: Vec3):
        for impact in self.impacts:
            if not impact.active:
                impact.active = True
                impact.age = 0.0
                impact.pos = Vec3(pos)
                impact.node.setPos(pos)
                impact.node.setScale(0.35)
                try:
                    impact.node.setColorScale(self._current_theme()["accent"])
                except Exception:
                    impact.node.setColorScale(1, 1, 1, 1)
                impact.node.show()
                return

    def _kill_burst(self, pos: Vec3, enemy: _Enemy | None = None):
        for burst in self.kill_bursts:
            if not burst.active:
                burst.active = True
                burst.age = 0.0
                burst.pos = Vec3(pos)
                burst.node.setPos(pos + Vec3(0, 0, 4.2))
                burst.node.setScale(0.42)
                if enemy is not None:
                    try:
                        burst.node.setColorScale(_enemy_profile(enemy.variant)["accent"])
                    except Exception:
                        burst.node.setColorScale(1, 1, 1, 1)
                burst.node.show()
                return

    def _muzzle_flash(self, pos: Vec3, forward: Vec3, repulsor: bool = False):
        for flash in self.muzzle_flashes:
            if not flash.active:
                flash.active = True
                flash.age = 0.0
                flash.life = 0.150 if repulsor else 0.095
                flash.pos = Vec3(pos)
                flash.node.setPos(pos)
                try:
                    flash.node.lookAt(pos + forward)
                except Exception:
                    pass
                flash.node.setScale(0.70 if repulsor else 0.42)
                flash.node.setColorScale(1.0, 0.92 if not repulsor else 0.58, 1.0, 1.0)
                flash.node.show()
                return

    def _repulsor_wave(self, pos: Vec3, forward: Vec3):
        for wave in self.repulsor_waves:
            if not wave.active:
                wave.active = True
                wave.age = 0.0
                wave.pos = Vec3(pos)
                wave.node.setPos(pos + forward * 2.8)
                try:
                    wave.node.lookAt(pos + forward * 8.0)
                except Exception:
                    pass
                wave.node.setScale(0.45)
                wave.node.show()
                return

    def _heat_vent_spark(self):
        if self.weapon_root is None:
            return
        forward = _forward_vec(self.player_yaw, self.player_pitch)
        side = _right_vec_from_forward(forward)
        if side.lengthSquared() > 0.001:
            side.normalize()
        eye = self.player_pos + Vec3(0, 0, EYE_HEIGHT)
        base = eye + forward * 1.65 + side * 0.54 + Vec3(0, 0, -0.48)
        for spark in self.heat_vent_sparks:
            if not spark.active:
                spark.active = True
                spark.age = 0.0
                spark.pos = base + side * self._rng.uniform(-0.18, 0.18) + Vec3(0, 0, self._rng.uniform(-0.08, 0.18))
                spark.node.setPos(spark.pos)
                try:
                    spark.node.lookAt(spark.pos + forward + Vec3(self._rng.uniform(-0.2, 0.2), self._rng.uniform(-0.2, 0.2), 0.2))
                except Exception:
                    pass
                spark.node.setScale(0.28)
                spark.node.show()
                return


    def _active_breach_cores(self) -> list[_BreachCore]:
        return [core for core in self.breach_cores if core.active]

    def _spawn_breach_core(self):
        for core in self.breach_cores:
            if core.active:
                return
        for core in self.breach_cores:
            if not core.active:
                breach_points = breach_points_for_profile(self.arena_profile)
                bx, by = breach_points[self.breach_phase % len(breach_points)]
                point = Vec3(bx, by, 0)
                self.breach_phase += 1
                core.active = True
                core.sealed = False
                core.warning_played = False
                core.age = 0.0
                core.life = max(10.0, 16.0 - min(4.5, self.wave * 0.35))
                core.max_hp = (92.0 + self.wave * 18.0) * float(self.arena_mutation_profile.get("breach_hp_mult", 1.0))
                core.hp = core.max_hp
                core.pos = Vec3(point)
                core.node.setPos(core.pos + Vec3(0, 0, 0.08))
                core.node.setScale(0.55)
                try:
                    core.node.setColorScale(self._current_theme()["accent"])
                except Exception:
                    core.node.setColorScale(1, 1, 1, 1)
                core.node.show()
                self._push_combat_event("BREACH CORE OPEN // DESTROY FOR BONUS", "wave")
                self._play_sfx("breach_spawn", core.pos)
                if self.audio_runtime is not None:
                    core.audio_loop = self.audio_runtime.start_positional_loop("breach_core_loop.wav", core.node, volume=0.28)
                self._spawn_pulse(core.pos)
                return

    def _closest_breach_in_reticle(self, max_range: float | None = None) -> _BreachCore | None:
        if max_range is None:
            max_range = max(145.0, self.current_arena_radius * 1.02)
        eye = self.player_pos + Vec3(0, 0, EYE_HEIGHT)
        forward = _forward_vec(self.player_yaw, self.player_pitch)
        best: _BreachCore | None = None
        best_score = -999.0
        for core in self.breach_cores:
            if not core.active:
                continue
            target = core.pos + Vec3(0, 0, 4.2)
            delta = target - eye
            distance = delta.length()
            if distance <= 0.001 or distance > max_range:
                continue
            if self._architecture_blocks_segment(eye, target):
                continue
            aim = Vec3(delta)
            aim.normalize()
            dot = forward.dot(aim)
            if dot >= 0.975:
                score = dot * 4.0 - distance / max_range
                if score > best_score:
                    best_score = score
                    best = core
        return best

    def _damage_breach_core(self, core: _BreachCore, damage: float, source: str = "pulse"):
        if core is None or not core.active:
            return
        core.hp -= max(0.0, float(damage))
        self.hit_marker_timer = max(self.hit_marker_timer, 0.12)
        self._play_sfx("breach_hit", core.pos + Vec3(0, 0, 4.2))
        self._impact(core.pos + Vec3(0, 0, 4.2))
        if core.hp <= 0.0:
            self._seal_breach_core(core, source)

    def _seal_breach_core(self, core: _BreachCore, source: str = "pulse"):
        if core is None or not core.active:
            return
        core.active = False
        core.sealed = True
        core.node.hide()
        self.breaches_sealed += 1
        reward = int(260 + self.wave * 42 + min(240, core.age * 12))
        self.score += reward
        self.combo = min(99, self.combo + 2)
        self.combo_timer = max(self.combo_timer, 4.0)
        self.armor = min(self.max_armor, self.armor + 12.0)
        self.heat = max(0.0, self.heat - 22.0)
        self.breach_pressure = max(0.0, self.breach_pressure - 0.55)
        self.breach_reward_flash = 1.0
        self.combo_flash_timer = max(self.combo_flash_timer, 1.2)
        self._push_combat_event(f"BREACH SEALED +{reward} // ARMOR SURGE", "wave")
        if self.audio_runtime is not None and core.audio_loop is not None:
            self.audio_runtime.stop_loop(core.audio_loop)
            core.audio_loop = None
        self._play_sfx("breach_sealed", core.pos)
        self._kill_burst(core.pos + Vec3(0, 0, 1.6), None)
        self._spawn_pulse(core.pos)

    def _update_breach_loop(self, dt: float):
        # Forced BREACH waves are owned by the wave director. Other waves retain sparse optional cores.
        if self.wave_required_breaches <= 0 and self.wave_intro_timer <= 0.0 and not self._active_breach_cores():
            self.breach_spawn_timer = max(0.0, self.breach_spawn_timer - dt)
            if self.breach_spawn_timer <= 0.0 and self.wave_kind not in {"GUARDIAN", "BLACKOUT"}:
                self._spawn_breach_core()
                self.breach_spawn_timer = max(14.0, 20.0 - min(4.0, self.wave * 0.30))
        for core in self.breach_cores:
            if not core.active:
                continue
            core.age += dt
            pressure = _clamp(core.age / max(core.life, 0.001), 0.0, 1.0)
            self.breach_pressure = max(self.breach_pressure, pressure * 0.36)
            if pressure > 0.62 and not core.warning_played:
                core.warning_played = True
                self._push_combat_event("BREACH CORE DESTABILIZING", "danger")
                self._play_sfx("breach_spawn", core.pos)
            if pressure >= 1.0:
                self.breach_pressure = min(1.0, self.breach_pressure + dt * 0.16)
                if self.armor > 0.0:
                    self.armor = max(0.0, self.armor - dt * (1.8 + self.wave * 0.05))
            hp_ratio = _clamp(core.hp / max(core.max_hp, 0.001), 0.0, 1.0)
            scale = 0.82 + pressure * 0.72 + (1.0 - hp_ratio) * 0.26
            try:
                core.node.setScale(scale)
                core.node.setH(self._elapsed * (34.0 + pressure * 58.0))
                core.node.setColorScale(1.0 + pressure * 0.35, 0.74 + hp_ratio * 0.26, 0.86 + math.sin(self._elapsed * 9.0) * 0.06, 0.72 + pressure * 0.24)
            except Exception:
                pass
        self.breach_pressure = max(0.0, self.breach_pressure - dt * 0.10)
        self.breach_reward_flash = max(0.0, self.breach_reward_flash - dt * 1.25)
        combo_step = int(self.combo // 8)
        if combo_step > self.combo_sfx_step and self.combo >= 8:
            self.combo_sfx_step = combo_step
            self._play_sfx("combo_surge")
            self._push_combat_event(f"COMBO SURGE x{self.combo:02d}", "info")
        if self.combo <= 2:
            self.combo_sfx_step = 0

    def _score_enemy_kill(self, enemy: _Enemy, multiplier: float = 1.0):
        enemy.active = False
        enemy.node.hide()
        if enemy.guardian_telegraph is not None:
            enemy.guardian_telegraph.hide()
        enemy.death_flash = 0.35
        self.kills += 1
        self.wave_defeated += 1
        self.combo += 1
        self.combo_timer = 3.2
        self.enemy_variant_counts[enemy.variant] = self.enemy_variant_counts.get(enemy.variant, 0) + 1
        gained = int((enemy.score_value + self.wave * 18) * min(4.5, multiplier * (1.0 + self.combo * 0.045)))
        self.score += gained
        self._refresh_weapon_upgrade()
        self.kill_marker_timer = 0.34
        self.combo_flash_timer = 1.0
        self._push_combat_event(f"{enemy.display_name} DOWN  +{gained}  COMBO x{self.combo:02d}", "danger" if enemy.variant == "guardian" else "info")
        self._play_sfx("enemy_destroyed", enemy.pos + Vec3(0, 0, 3.0))
        self._kill_burst(enemy.pos, enemy)
        self._impact(enemy.pos + Vec3(0, 0, 4.8))

    def _fire_primary(self):
        if self.fire_cooldown > 0.0:
            return
        self._refresh_weapon_upgrade()
        tier = self._weapon_tier()
        if self.heat >= MAX_HEAT:
            if self.overheat_event_cooldown <= 0.0:
                self._push_combat_event("HEAT LOCK // HOLD R TO VENT", "danger")
                self._play_sfx("overheat_warning")
                self.overheat_event_cooldown = 1.25
            return
        self.fire_cooldown = 0.082 * float(tier["cooldown_mult"])
        self._play_sfx("pulse_rifle")
        self.heat = min(MAX_HEAT, self.heat + 8.5 * float(tier["heat_mult"]) * self.wave_heat_gain_mult)
        self.weapon_recoil = max(self.weapon_recoil, 0.20 + 0.035 * max(0, self.weapon_rank - 1))
        self.weapon_charge = min(1.0, self.weapon_charge + 0.22 + 0.05 * max(0, self.weapon_rank - 1))
        eye = self.player_pos + Vec3(0, 0, EYE_HEIGHT)
        forward = _forward_vec(self.player_yaw, self.player_pitch)
        side = _right_vec_from_forward(forward)
        if side.lengthSquared() > 0.001:
            side.normalize()
        muzzle = eye + forward * 2.2 + side * 0.36 + Vec3(0, 0, -0.44)
        target = self._closest_target_in_reticle()
        breach_target = None if target is not None else self._closest_breach_in_reticle()
        end = muzzle + forward * max(152.0, self.current_arena_radius * 1.15)
        if target is not None:
            target_point = target.pos + Vec3(0, 0, 4.6 + target.tier * 0.5)
            end = target_point
            damage = (27.0 + max(0, self.combo - 1) * 1.5) * float(tier["damage_mult"]) * self.weapon_mutation_mult
            if target.variant in {"wraith", "sentry"}:
                damage *= 1.08
            if self.weapon_rank >= 3 and target.variant in {"brute", "guardian"}:
                damage *= 1.10
            target.hp -= damage
            target.hit_flash = 0.18 + 0.02 * max(0, self.weapon_rank - 1)
            self.hit_marker_timer = 0.16
            if target.variant in {"brute", "guardian"} and target.hp / max(target.max_hp, 0.001) < 0.34:
                self._push_combat_event(f"{target.display_name} ARMOR CRACKING", "danger")
            self._play_sfx("enemy_hit", target_point)
            self._impact(target_point)
            if self.weapon_rank >= 3 and target.hp > 0.0:
                chain = self._arc_followup_target(target)
                if chain is not None:
                    chain_point = chain.pos + Vec3(0, 0, 4.6 + chain.tier * 0.45)
                    chain_damage = damage * (0.26 + 0.05 * min(2, self.weapon_rank - 3))
                    chain.hp -= chain_damage
                    chain.hit_flash = 0.16
                    self._emit_beam(target_point, chain_point)
                    self._impact(chain_point)
                    self._push_combat_event("ARC LANCE CHAIN HIT", "info")
                    if chain.hp <= 0.0:
                        self._score_enemy_kill(chain, 0.88)
            if target.hp <= 0.0:
                self._score_enemy_kill(target, 1.0)
        elif breach_target is not None:
            core_point = breach_target.pos + Vec3(0, 0, 4.2)
            end = core_point
            self._damage_breach_core(breach_target, 34.0 * float(tier["damage_mult"]) * self.weapon_mutation_mult, "pulse")
        end = self._clip_combat_segment(muzzle, end)
        self._muzzle_flash(muzzle, forward, False)
        self._emit_beam(muzzle, end)

    def _fire_repulsor(self):
        self._refresh_weapon_upgrade()
        tier = self._weapon_tier()
        heat_ceiling = 85.0 + max(0, self.weapon_rank - 1) * 3.0
        if self.blast_cooldown > 0.0 or self.heat > heat_ceiling:
            return
        self.blast_cooldown = 2.2 * float(tier["cooldown_mult"]) * self.repulsor_cooldown_mult
        self._play_sfx("repulsor_blast")
        self.heat = min(MAX_HEAT, self.heat + 26.0 * float(tier["heat_mult"]) * self.wave_heat_gain_mult)
        self.weapon_recoil = max(self.weapon_recoil, 0.55 + 0.05 * max(0, self.weapon_rank - 1))
        self.repulsor_flash = 1.0
        self.weapon_charge = 1.0
        eye = self.player_pos + Vec3(0, 0, EYE_HEIGHT)
        forward = _forward_vec(self.player_yaw, self.player_pitch)
        radius = 34.0 + max(0, self.weapon_rank - 1) * 3.8
        for enemy in self.enemies:
            if not enemy.active:
                continue
            target = enemy.pos + Vec3(0, 0, 4.2)
            delta = target - eye
            distance = delta.length()
            if distance > radius:
                continue
            aim = Vec3(delta)
            if aim.lengthSquared() > 0.001:
                aim.normalize()
            if forward.dot(aim) < 0.58:
                continue
            if self._architecture_blocks_segment(eye, target):
                continue
            damage = (55.0 * (1.0 - distance / radius) + 15.0) * float(tier["repulsor_mult"]) * self.weapon_mutation_mult
            if enemy.variant in {"brute", "guardian"}:
                damage *= 0.78 if self.weapon_rank < 4 else 0.92
            enemy.hp -= damage
            enemy.hit_flash = 0.26
            self.hit_marker_timer = max(self.hit_marker_timer, 0.20)
            self._play_sfx("enemy_hit", target)
            push = Vec3(enemy.pos - self.player_pos)
            push.z = 0
            if push.lengthSquared() > 0.001:
                push.normalize()
                enemy.vel += push * (64.0 + enemy.tier * 14.0) / max(0.72, enemy.speed_scale)
            self._impact(target)
            if enemy.hp <= 0.0:
                self._score_enemy_kill(enemy, 1.12)
        for core in self.breach_cores:
            if not core.active:
                continue
            target = core.pos + Vec3(0, 0, 4.0)
            delta = target - eye
            distance = delta.length()
            if distance <= radius * 1.10 and distance > 0.001:
                aim = Vec3(delta)
                aim.normalize()
                if forward.dot(aim) >= 0.48 and not self._architecture_blocks_segment(eye, target):
                    self._damage_breach_core(core, 72.0 * float(tier["repulsor_mult"]) * self.weapon_mutation_mult, "repulsor")
        muzzle = eye + forward * 2.0
        self._push_combat_event(f"{tier['short']} REPULSOR BLAST // SPACE CREATED", "info")
        self._muzzle_flash(muzzle, forward, True)
        self._repulsor_wave(eye, forward)
        self._emit_beam(muzzle, self._clip_combat_segment(muzzle, eye + forward * radius))

    def _update_pointer_look(self, dt: float):
        # Fallback keyboard look for dev/offscreen and keyboard-only users.
        if self._key_down("arrow_left"):
            self.player_yaw += 118.0 * dt
        if self._key_down("arrow_right"):
            self.player_yaw -= 118.0 * dt
        if self._key_down("q"):
            self.player_yaw += 92.0 * dt
        if self._key_down("e"):
            self.player_yaw -= 92.0 * dt

        if self.win is None:
            return
        try:
            props = self.win.getProperties()
            width = max(1, int(props.getXSize()))
            height = max(1, int(props.getYSize()))
            cx, cy = width // 2, height // 2
            pointer = self.win.getPointer(0)
            px, py = int(pointer.getX()), int(pointer.getY())
            if self._capture_pointer_once:
                self._capture_pointer_once = False
                if hasattr(self.win, "movePointer"):
                    self.win.movePointer(0, cx, cy)
                return
            dx, dy = px - cx, py - cy
            if abs(dx) > 0 or abs(dy) > 0:
                self.player_yaw -= dx * 0.105
                self.player_pitch = _clamp(self.player_pitch - dy * 0.092, -62.0, 58.0)
                if hasattr(self.win, "movePointer"):
                    self.win.movePointer(0, cx, cy)
        except Exception:
            return

    def _push_out_of_cover(self):
        for cover in self.cover_blocks:
            dx = self.player_pos.x - cover.pos.x
            dy = self.player_pos.y - cover.pos.y
            px = cover.half.x + 1.6 - abs(dx)
            py = cover.half.y + 1.6 - abs(dy)
            if px > 0 and py > 0:
                if px < py:
                    sign = 1.0 if dx >= 0 else -1.0
                    self.player_pos.x = cover.pos.x + sign * (cover.half.x + 1.6)
                    self.player_vel.x = 0.0
                else:
                    sign = 1.0 if dy >= 0 else -1.0
                    self.player_pos.y = cover.pos.y + sign * (cover.half.y + 1.6)
                    self.player_vel.y = 0.0

    def _update_player(self, dt: float):
        self._update_pointer_look(dt)
        forward = _heading_vec(self.player_yaw)
        right = _right_vec_from_forward(forward)
        move = Vec3(0, 0, 0)
        if self._key_down("w"):
            move += forward
        if self._key_down("s"):
            move -= forward
        if self._key_down("d"):
            move += right
        if self._key_down("a"):
            move -= right
        if move.lengthSquared() > 0.001:
            move.normalize()
        dash = self._key_down("shift") and self.heat < 86.0
        speed = 46.0 * (1.55 if dash else 1.0)
        if dash:
            self.heat = min(MAX_HEAT, self.heat + dt * 13.0)
        desired = move * speed
        self.player_vel += (desired - self.player_vel) * min(1.0, dt * 10.0)
        self.player_pos += self.player_vel * dt
        self._push_out_of_cover()
        r = math.sqrt(self.player_pos.x * self.player_pos.x + self.player_pos.y * self.player_pos.y)
        if r > self.current_arena_radius - 5.0:
            n = Vec3(self.player_pos.x, self.player_pos.y, 0)
            if n.lengthSquared() > 0.001:
                n.normalize()
                self.player_pos = n * (self.current_arena_radius - 5.0)
                self.player_vel -= n * max(0.0, self.player_vel.dot(n)) * 1.2
        self.player_pos.z = 0.0

    def _steer_enemy_from_cover(self, enemy: _Enemy, desired: Vec3) -> Vec3:
        steer = Vec3(desired)
        for cover in self.cover_blocks:
            dx = enemy.pos.x - cover.pos.x
            dy = enemy.pos.y - cover.pos.y
            px = cover.half.x + 4.5 - abs(dx)
            py = cover.half.y + 4.5 - abs(dy)
            if px > 0 and py > 0:
                if px < py:
                    steer.x += (1.0 if dx >= 0 else -1.0) * 28.0
                else:
                    steer.y += (1.0 if dy >= 0 else -1.0) * 28.0
        return steer

    def _push_enemy_out_of_cover(self, enemy: _Enemy, margin: float = 3.6):
        """Hard safety after steering so fast/charging enemies cannot ghost through cover."""
        for cover in self.cover_blocks:
            dx = enemy.pos.x - cover.pos.x
            dy = enemy.pos.y - cover.pos.y
            px = cover.half.x + margin - abs(dx)
            py = cover.half.y + margin - abs(dy)
            if px > 0 and py > 0:
                if px < py:
                    sign = 1.0 if dx >= 0 else -1.0
                    enemy.pos.x = cover.pos.x + sign * (cover.half.x + margin)
                    enemy.vel.x = 0.0
                else:
                    sign = 1.0 if dy >= 0 else -1.0
                    enemy.pos.y = cover.pos.y + sign * (cover.half.y + margin)
                    enemy.vel.y = 0.0

    def _damage_player_from_enemy(self, damage: float, source_pos: Vec3, push_strength: float = 18.0):
        damage = max(0.0, float(damage)) * self.incoming_damage_mult
        if self.armor > 0.0:
            used = min(self.armor, damage * 0.70)
            self.armor -= used
            damage -= used * 0.55
        self.health = max(0.0, self.health - damage)
        self.damage_flash = max(self.damage_flash, 0.24)
        self._play_sfx("player_hit")
        push = Vec3(self.player_pos - source_pos)
        push.z = 0
        if push.lengthSquared() > 0.001:
            push.normalize()
            self.player_vel += push * push_strength

    def _update_guardian_special(self, enemy: _Enemy, distance: float, to_player: Vec3, dt: float) -> bool:
        if enemy.variant != "guardian":
            return False
        phase = guardian_phase_for(enemy.hp, enemy.max_hp)
        if phase != enemy.guardian_phase:
            enemy.guardian_phase = phase
            self.guardian_phase_transitions += 1
            phase_profile = guardian_phase_profile(phase)
            if phase == 2:
                self._play_sfx("guardian_phase2", enemy.pos + Vec3(0,0,4))
            elif phase == 3:
                self._play_sfx("guardian_phase3", enemy.pos + Vec3(0,0,4))
                # Guardian waves already own a fair telegraphed hazard system;
                # entering Redline simply asks it for one extra marked discharge.
                if self.hazard_profile.get("enabled"):
                    self._arm_wave_hazard()
            self._push_combat_event(f"GUARDIAN PHASE {phase} // {phase_profile['name']}", "danger")
            if enemy.class_marker is not None:
                try:
                    enemy.class_marker.setScale(1.0 + 0.12 * phase + 0.05 * enemy.evolution_level)
                except Exception:
                    pass
        phase_profile = guardian_phase_profile(enemy.guardian_phase)
        enemy.guardian_timer -= dt
        if enemy.guardian_state == "idle":
            if enemy.guardian_timer <= 0.0 and distance < 62.0:
                pattern_index = self.guardian_specials_used + enemy.formation + enemy.guardian_phase - 1
                enemy.guardian_attack_kind = "PULSE" if pattern_index % 2 == 0 else "RUSH"
                enemy.guardian_state = "telegraph"
                authored = 1.15 if enemy.guardian_attack_kind == "PULSE" else 0.95
                enemy.guardian_timer = max(0.78, authored * float(phase_profile["telegraph_mult"]))
                direction = Vec3(to_player)
                direction.z = 0
                if direction.lengthSquared() > 0.001:
                    direction.normalize()
                enemy.guardian_attack_dir = direction
                enemy.guardian_hit_player = False
                if enemy.guardian_telegraph is not None:
                    enemy.guardian_telegraph.setPos(enemy.pos + Vec3(0,0,0.10))
                    enemy.guardian_telegraph.setScale(1.0)
                    color = Vec4(1.0, 0.22 if enemy.guardian_attack_kind == "PULSE" else 0.74, 0.08 if enemy.guardian_phase < 3 else 0.34, 0.88)
                    enemy.guardian_telegraph.setColor(color)
                    enemy.guardian_telegraph.show()
                self.guardian_specials_used += 1
                self._play_sfx("guardian_charge", enemy.pos + Vec3(0,0,4))
                self._push_combat_event(f"GUARDIAN {phase_profile['name']} {enemy.guardian_attack_kind} // TELEGRAPH ACTIVE", "danger")
            return False
        if enemy.guardian_state == "telegraph":
            if enemy.guardian_telegraph is not None:
                enemy.guardian_telegraph.setPos(enemy.pos + Vec3(0,0,0.10))
                authored = 1.15 if enemy.guardian_attack_kind == "PULSE" else 0.95
                scale = 1.0 + (authored - max(0.0, enemy.guardian_timer)) * (2.0 if enemy.guardian_attack_kind == "PULSE" else 1.2)
                enemy.guardian_telegraph.setScale(max(0.8, scale))
            if enemy.guardian_timer <= 0.0:
                if enemy.guardian_attack_kind == "PULSE":
                    enemy.guardian_state = "recover"
                    enemy.guardian_timer = max(0.72, 1.10 * float(phase_profile["special_cooldown_mult"]) * enemy.evolution_special_cooldown_mult)
                    if enemy.guardian_telegraph is not None:
                        enemy.guardian_telegraph.setScale(3.4 + (enemy.guardian_phase - 1) * 0.35)
                    self._play_sfx("guardian_slam", enemy.pos)
                    if distance <= float(phase_profile["pulse_radius"]):
                        damage = min(36.0, (22.0 + self.wave * 0.75) * float(phase_profile["damage_mult"]))
                        self._damage_player_from_enemy(damage, enemy.pos, 34.0 + enemy.guardian_phase * 3.0)
                else:
                    enemy.guardian_state = "rush"
                    enemy.guardian_timer = max(0.48, 0.62 * float(phase_profile["special_cooldown_mult"]))
                    direction = enemy.guardian_attack_dir if enemy.guardian_attack_dir is not None else Vec3(0,1,0)
                    enemy.vel = Vec3(direction) * min(104.0, (78.0 + self.wave * 1.4) * float(phase_profile["rush_speed_mult"]))
                    self._play_sfx("guardian_slam", enemy.pos)
            return True
        if enemy.guardian_state == "rush":
            if not enemy.guardian_hit_player and distance < 8.8:
                enemy.guardian_hit_player = True
                damage = min(40.0, (26.0 + self.wave * 0.85) * float(phase_profile["damage_mult"]))
                self._damage_player_from_enemy(damage, enemy.pos, 42.0 + enemy.guardian_phase * 3.0)
            if enemy.guardian_timer <= 0.0:
                enemy.guardian_state = "recover"
                enemy.guardian_timer = max(0.72, 0.90 * float(phase_profile["special_cooldown_mult"]) * enemy.evolution_special_cooldown_mult)
                if enemy.guardian_telegraph is not None:
                    enemy.guardian_telegraph.hide()
            return True
        if enemy.guardian_state == "recover":
            if enemy.guardian_timer <= 0.0:
                enemy.guardian_state = "idle"
                base = self._rng.uniform(3.8, 5.6)
                enemy.guardian_timer = max(2.35, base * float(phase_profile["special_cooldown_mult"]) * enemy.evolution_special_cooldown_mult)
                enemy.guardian_attack_kind = ""
                if enemy.guardian_telegraph is not None:
                    enemy.guardian_telegraph.hide()
            return True
        return False

    def _update_enemies(self, dt: float):
        active_count = 0
        for i, enemy in enumerate(self.enemies):
            if not enemy.active:
                continue
            active_count += 1
            to_player = self.player_pos - enemy.pos
            distance = max(0.001, to_player.length())
            seek = Vec3(to_player)
            seek.z = 0
            if seek.lengthSquared() > 0.001:
                seek.normalize()
            orbit = Vec3(-seek.y, seek.x, 0) * math.sin(self._elapsed * (0.9 + enemy.tier * 0.2) + enemy.phase)
            base_speed = 24.0 + self.wave * 1.2
            if enemy.variant == "stalker":
                desired = seek * (base_speed * 1.42) + orbit * 5.5
            elif enemy.variant == "brute":
                desired = seek * (base_speed * 0.72) + orbit * 3.0
            elif enemy.variant == "sentry":
                keep = -seek * 18.0 if distance < 28.0 else seek * 10.0
                desired = keep + orbit * 20.0
            elif enemy.variant == "wraith":
                zig = math.sin(self._elapsed * 4.6 + enemy.phase)
                desired = seek * (base_speed * 1.05) + orbit * (17.0 * zig * enemy.evolution_lateral_mult)
            else:  # guardian
                desired = seek * (base_speed * 0.56) + orbit * 2.2
            role = enemy.tactic_role
            if role == "flank_left":
                desired = seek * (base_speed * 0.72) + Vec3(-seek.y, seek.x, 0) * (base_speed * 0.88)
            elif role == "flank_right":
                desired = seek * (base_speed * 0.72) - Vec3(-seek.y, seek.x, 0) * (base_speed * 0.88)
            elif role in {"rear_left", "rear_right"}:
                desired = seek * (base_speed * 1.22) + orbit * 8.0
            elif role == "anchor" and enemy.variant == "sentry":
                desired = (-seek * 13.0 if distance < 34.0 else seek * 5.0) + orbit * 17.0
            elif role == "boss_support":
                desired = seek * (base_speed * 0.80) + orbit * 14.0
            special_busy = self._update_guardian_special(enemy, distance, to_player, dt)
            if enemy.variant == "guardian" and enemy.guardian_state == "rush":
                desired = Vec3(enemy.vel)
            if distance < 9.0 and not special_busy:
                desired -= seek * (20.0 if enemy.variant not in {"brute", "guardian"} else 9.0)
            desired = self._steer_enemy_from_cover(enemy, desired)
            enemy.vel += (desired * enemy.speed_scale - enemy.vel) * min(1.0, dt * (2.3 + enemy.speed_scale * 0.55))
            enemy.pos += enemy.vel * dt
            self._push_enemy_out_of_cover(enemy)
            r = math.sqrt(enemy.pos.x * enemy.pos.x + enemy.pos.y * enemy.pos.y)
            if r > self.current_arena_radius - 6.0:
                n = Vec3(enemy.pos.x, enemy.pos.y, 0)
                if n.lengthSquared() > 0.001:
                    n.normalize()
                    enemy.pos = n * (self.current_arena_radius - 6.0)
                    enemy.vel -= n * max(0.0, enemy.vel.dot(n)) * 1.15
            enemy.pos.z = 0.0
            if enemy.vel.lengthSquared() > 1.0:
                enemy.node.setH(math.degrees(math.atan2(enemy.vel.x, enemy.vel.y)))
            bob = math.sin(self._elapsed * 5.0 + enemy.phase) * 0.16
            enemy.node.setPos(enemy.pos + Vec3(0, 0, bob))
            enemy.node.setR(math.sin(self._elapsed * 3.1 + enemy.phase) * 4.5)
            if enemy.hit_flash > 0.0:
                enemy.hit_flash = max(0.0, enemy.hit_flash - dt)
                enemy.node.setColorScale(1.9, 1.9, 1.9, 1.0)
            else:
                enemy.node.clearColorScale()
            hp_ratio = _clamp(enemy.hp / max(enemy.max_hp, 0.001), 0.0, 1.0)
            if enemy.hp_fill is not None:
                try:
                    enemy.hp_fill.setScale(max(0.04, hp_ratio), 1.0, 1.0)
                    if hp_ratio < 0.34:
                        enemy.hp_fill.setColor(Vec4(1.0, 0.12, 0.08, 0.94))
                    elif enemy.variant in {"brute", "guardian"}:
                        enemy.hp_fill.setColor(Vec4(1.0, 0.62, 0.14, 0.92))
                    else:
                        enemy.hp_fill.setColor(Vec4(0.24, 1.0, 0.88, 0.90))
                except Exception:
                    pass
            if enemy.class_marker is not None:
                try:
                    enemy.class_marker.setH(self._elapsed * (80.0 + enemy.tier * 14.0))
                    enemy.class_marker.setScale(1.0 + 0.07 * enemy.evolution_level + 0.07 * max(0, enemy.guardian_phase - 1) + math.sin(self._elapsed * 5.0 + enemy.phase) * 0.08)
                except Exception:
                    pass
            enemy.attack_cooldown -= dt
            if self.breach_pressure > 0.58 and distance < 44.0:
                enemy.vel += to_player * dt * (4.0 + self.breach_pressure * 8.0)
            if distance < 7.8 and enemy.attack_cooldown <= 0.0 and not (enemy.variant == "guardian" and enemy.guardian_state != "idle"):
                base_attack_cd = max(0.52, 1.05 - enemy.speed_scale * 0.18) + enemy.tier * 0.08
                enemy.attack_cooldown = max(0.46, base_attack_cd * enemy.evolution_attack_cooldown_mult)
                damage = min(42.0, (enemy.damage_scale + self.wave * 0.85) * (1.10 if self.wave_kind == "ELITE" else 1.0))
                self._damage_player_from_enemy(damage, enemy.pos, 18.0)
            if enemy.hp <= 0.0:
                self._score_enemy_kill(enemy, 1.0)

    def _update_input_fire(self, dt: float):
        if self._block_combat_input_until_release:
            self._mouse1_latched = False
            self._mouse3_latched = False
            self._r_latched = False
            if not self._mouse_down(1) and not self._mouse_down(3) and not self._key_down("r"):
                self._block_combat_input_until_release = False
            return
        mouse1 = self._mouse_down(1) or self._mouse1_latched
        mouse3 = self._mouse_down(3) or self._mouse3_latched
        if mouse1:
            self._fire_primary()
        if mouse3:
            self._fire_repulsor()
        if self._r_latched or self._key_down("r"):
            self.heat = max(0.0, self.heat - dt * 95.0)
            self.vent_fx_cooldown = max(0.0, self.vent_fx_cooldown - dt)
            if self.vent_fx_cooldown <= 0.0:
                self.vent_fx_cooldown = 0.075
                self._play_sfx("heat_vent")
                self._heat_vent_spark()
        self._mouse1_latched = False
        self._mouse3_latched = False
        self._r_latched = False

    def _update_projectiles(self, dt: float):
        for beam in self.projectiles:
            if not beam.active:
                continue
            beam.age += dt
            t = beam.age / max(beam.life, 0.001)
            if t >= 1.0:
                beam.active = False
                try:
                    beam.node.hide()
                except Exception:
                    pass
                continue
            try:
                beam.node.setColorScale(1, 1, 1, max(0.0, 1.0 - t))
            except Exception:
                pass

    def _update_impacts(self, dt: float):
        for impact in self.impacts:
            if not impact.active:
                continue
            impact.age += dt
            t = impact.age / max(impact.life, 0.001)
            if t >= 1.0:
                impact.active = False
                impact.node.hide()
                continue
            impact.node.setScale(0.4 + t * 3.8)
            impact.node.setColorScale(1, 1, 1, max(0.0, 1.0 - t))
        for pulse in self.spawn_pulses:
            if not pulse.active:
                continue
            pulse.age += dt
            t = pulse.age / max(pulse.life, 0.001)
            if t >= 1.0:
                pulse.active = False
                pulse.node.hide()
                continue
            pulse.node.setScale(0.7 + t * 4.7)
            pulse.node.setColorScale(1, 1, 1, max(0.0, 1.0 - t))
        for burst in self.kill_bursts:
            if not burst.active:
                continue
            burst.age += dt
            t = burst.age / max(burst.life, 0.001)
            if t >= 1.0:
                burst.active = False
                burst.node.hide()
                continue
            burst.node.setScale(0.55 + t * 6.2)
            burst.node.setH(self._elapsed * 220.0)
            burst.node.setColorScale(1.0, 1.0, 1.0, max(0.0, 1.0 - t))
        for flash in self.muzzle_flashes:
            if not flash.active:
                continue
            flash.age += dt
            t = flash.age / max(flash.life, 0.001)
            if t >= 1.0:
                flash.active = False
                flash.node.hide()
                continue
            flash.node.setScale(0.42 + t * 1.6)
            flash.node.setColorScale(1.0, 1.0, 1.0, max(0.0, 1.0 - t))
        for wave in self.repulsor_waves:
            if not wave.active:
                continue
            wave.age += dt
            t = wave.age / max(wave.life, 0.001)
            if t >= 1.0:
                wave.active = False
                wave.node.hide()
                continue
            wave.node.setScale(0.45 + t * 8.8)
            wave.node.setColorScale(1.0, 1.0, 1.0, max(0.0, 0.86 - t))
        for spark in self.heat_vent_sparks:
            if not spark.active:
                continue
            spark.age += dt
            t = spark.age / max(spark.life, 0.001)
            if t >= 1.0:
                spark.active = False
                spark.node.hide()
                continue
            spark.node.setZ(spark.pos.z + t * 1.8)
            spark.node.setScale(0.25 + t * 0.9)
            spark.node.setH(self._elapsed * 360.0 + t * 120.0)
            spark.node.setColorScale(1.0, 0.78, 0.34, max(0.0, 1.0 - t))

    def _update_weapon_viewmodel(self, dt: float):
        self.weapon_recoil = max(0.0, self.weapon_recoil - dt * 3.8)
        self.weapon_charge = max(0.0, self.weapon_charge - dt * 1.4)
        self.repulsor_flash = max(0.0, self.repulsor_flash - dt * 2.2)
        self.weapon_rank_flash = max(0.0, self.weapon_rank_flash - dt * 1.6)
        if self.weapon_root is None:
            return
        bob = math.sin(self._elapsed * 5.2) * 0.012
        recoil = self.weapon_recoil
        self.weapon_root.setPos(0.48 + recoil * 0.035, 1.05 - recoil * 0.22, -0.34 + bob - recoil * 0.045)
        self.weapon_root.setHpr(-5.0 - recoil * 7.0, -2.0 + recoil * 4.0, math.sin(self._elapsed * 2.6) * 0.8)
        heat_ratio = _clamp(self.heat / MAX_HEAT, 0.0, 1.0)
        pulse = 0.58 + 0.42 * math.sin(self._elapsed * (8.0 + heat_ratio * 10.0))
        rank_glow = 0.10 * max(0, self.weapon_rank - 1) + self.weapon_rank_flash * 0.44
        for node in self.weapon_glow_nodes:
            try:
                node.setColorScale(1.0 + rank_glow, 1.0 - heat_ratio * 0.32 + rank_glow * 0.30, 1.0 - heat_ratio * 0.70 + pulse * 0.18, 0.72 + max(self.weapon_charge, self.repulsor_flash, self.weapon_rank_flash) * 0.28)
            except Exception:
                pass

    def _update_camera(self, dt: float):
        self.camera.reparentTo(self.render)
        eye = self.player_pos + Vec3(0, 0, EYE_HEIGHT)
        self.camera.setPos(eye)
        self.camera.setHpr(self.player_yaw, self.player_pitch, 0)

    def _update_status(self, dt: float):
        self.heat = max(0.0, self.heat - dt * 18.0 * self.wave_heat_cool_mult)
        self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
        self.blast_cooldown = max(0.0, self.blast_cooldown - dt)
        self.vent_fx_cooldown = max(0.0, self.vent_fx_cooldown - dt)
        self.damage_flash = max(0.0, self.damage_flash - dt)
        self.combo_timer = max(0.0, self.combo_timer - dt)
        self.hit_marker_timer = max(0.0, self.hit_marker_timer - dt)
        self.kill_marker_timer = max(0.0, self.kill_marker_timer - dt)
        self.combo_flash_timer = max(0.0, self.combo_flash_timer - dt)
        self.overheat_event_cooldown = max(0.0, self.overheat_event_cooldown - dt)
        self.low_health_event_cooldown = max(0.0, self.low_health_event_cooldown - dt)
        self.weapon_upgrade_notice_timer = max(0.0, self.weapon_upgrade_notice_timer - dt)
        self.breach_reward_flash = max(0.0, self.breach_reward_flash - dt * 1.25)
        self._refresh_weapon_upgrade()
        self._update_combat_event_feed(dt)
        if self.combo_timer <= 0.0:
            self.combo = max(1, self.combo - 1)
        if self.health <= 0.0:
            self.health = self.max_health
            self.armor = min(self.max_armor, 50.0)
            self.heat = 0.0
            self.score = max(0, self.score - 300)
            self.combo = 1
            self.player_pos = Vec3(0, -82, 0.0)
            self.player_vel = Vec3(0, 0, 0)
            self.damage_flash = 0.35
            self._push_combat_event("PLAYER REBOOTED // SCORE PENALTY", "danger")
            self._play_sfx("player_reboot")
        if self.health < 28.0 and self.low_health_event_cooldown <= 0.0:
            self._push_combat_event("CRITICAL HEALTH // USE COVER", "danger")
            self._play_sfx("low_health")
            self.low_health_event_cooldown = 2.4
        active = sum(1 for enemy in self.enemies if enemy.active)
        theme_name = self._current_theme()["name"]
        if self.combat_text is not None:
            self.combat_text["text"] = (
                f"HP {int(self.health):03d}  ARMOR {int(self.armor):03d}  HEAT {int(self.heat):03d}  "
                f"WAVE {self.wave:02d} {self.wave_kind}  SCORE {self.score:05d}  COMBO x{self.combo:02d}  KILLS {self.kills:03d}  ACTIVE {active:02d}  "
                f"REMAIN {len(self.wave_spawn_script)+len(self.pending_spawns)+active:02d}  BREACH {self.breaches_sealed:02d}  WEAPON {self._weapon_tier()['short']}  {theme_name}"
            )
        if self.wave_text is not None:
            remaining = len(self.wave_spawn_script) + len(self.pending_spawns) + active
            breach_done = max(0, self.breaches_sealed - self.wave_breach_start_sealed)
            breach_state = (f"CORES {breach_done}/{self.wave_required_breaches}" if self.wave_required_breaches else ("OPTIONAL CORE ACTIVE" if self._active_breach_cores() else "NO REQUIRED CORE"))
            intermission = f"INTERMISSION {self.wave_intermission_timer:0.1f}s" if self.wave_complete_pending else f"THREATS REMAIN {remaining:02d}"
            self.wave_text["text"] = (
                f"VECTOR ARENA // SET {self.wave_set:02d}\nWAVE {self.wave:02d} // {self.wave_kind}\n"
                f"{theme_name} // {int(self.current_arena_radius * 2)}u // {self.arena_mutation_profile.get('name','STABLE MATRIX')}\n"
                f"{intermission}  {breach_state}  HAZARD {self.hazard_profile.get('kind','NONE')}\nSCORE {self.score:05d}  COMBO x{self.combo:02d}  MUTATIONS {self.upgrades_selected:02d}\nWEAPON {self.weapon_module_name}"
            )
        if self.weapon_upgrade_text is not None:
            next_tier = self._next_weapon_tier()
            if next_tier is None:
                next_label = "MAX RANK"
                charge = 100
            else:
                next_label = str(next_tier["short"])
                charge = int(self.weapon_upgrade_charge * 100)
            notice = " // UPGRADE ONLINE" if self.weapon_upgrade_notice_timer > 0.0 else ""
            self.weapon_upgrade_text["text"] = (
                f"WEAPON {self.weapon_module_name}{notice}\n"
                f"NEXT {next_label} {charge:03d}%  DMG x{float(self._weapon_tier()['damage_mult']):.2f}  HEAT x{float(self._weapon_tier()['heat_mult']):.2f}"
            )
            self.weapon_upgrade_text.setColorScale(1.0 + self.weapon_rank_flash * 0.22, 1.0, 1.0, 0.90)
        if self.damage_overlay is not None:
            alpha = min(0.32, self.damage_flash * 1.2)
            self.damage_overlay.setColor(1.0, 0.05, 0.05, alpha)

    # ------------------------------------------------------------------
    # Dimension UI / host contract
    # ------------------------------------------------------------------
    def _dimension_ui_nodes(self):
        nodes = []
        for name in getattr(self, "_dimension_ui_node_names", ()):
            node = getattr(self, name, None)
            if node is not None:
                nodes.append(node)
        return nodes

    def _set_dimension_ui_visible(self, visible: bool):
        self.dimension_ui_visible = bool(visible)
        for node in self._dimension_ui_nodes():
            try:
                node.show() if self.dimension_ui_visible else node.hide()
            except Exception:
                pass

    def toggle_dimension_ui(self) -> bool:
        self._set_dimension_ui_visible(not self.dimension_ui_visible)
        self._play_sfx("ui_toggle")
        return True

    def _toggle_native_pause(self) -> bool:
        if not self.hosted_in_holoverse:
            return False
        self.paused = not self.paused
        if self.pause_overlay_root is not None:
            self.pause_overlay_root.show() if self.paused else self.pause_overlay_root.hide()
        self._play_sfx("ui_toggle")
        return True

    def _update_native_owned_keys(self) -> None:
        if not self.hosted_in_holoverse:
            return
        for name in ("escape", "h"):
            down = self._key_down(name)
            was = bool(self._native_key_latches.get(name, False))
            if down and not was:
                self._native_key_latches[name] = True
                if name == "escape":
                    self._toggle_native_pause()
                else:
                    self.toggle_dimension_ui()
            elif not down:
                self._native_key_latches[name] = False

    def enter(self):
        self._host_resources()
        self._build_scene()
        self._load_sfx()
        self._begin_wave(1)
        self._set_dimension_ui_visible(False)
        self._push_combat_event("MATCH LIVE // HORDE DIRECTOR ONLINE", "wave")
        self._entered = True
        self._update_camera(0.016)
        self._update_status(0.016)

    def on_host_action(self, action: str) -> bool:
        action = str(action or "").strip().lower()
        if action in {"toggle_dimension_ui", "dimension_ui", "h"}:
            return self.toggle_dimension_ui()
        if action in {"mouse1", "mouse1_down", "fire"}:
            if not self.upgrade_pending:
                self._mouse1_latched = True
            return True
        if action in {"mouse3", "right_click", "shock", "repulsor"}:
            if not self.upgrade_pending:
                self._mouse3_latched = True
            return True
        if action in {"reload", "vent", "r"}:
            if not self.upgrade_pending:
                self._r_latched = True
            return True
        if action in {"1", "number_1", "upgrade_1"}:
            return self._select_upgrade(1)
        if action in {"2", "number_2", "upgrade_2"}:
            return self._select_upgrade(2)
        if action in {"3", "number_3", "upgrade_3"}:
            return self._select_upgrade(3)
        if action in {"escape", "pause", "tab", "number_0", "return", "return_to_core", "return_to_holoverse"}:
            return False
        return False

    def update(self, dt: float):
        if not self._entered:
            return
        dt = _safe_dt(dt)
        self._update_native_owned_keys()
        # Pause is local to Vector Arena.  TAB remains outside this adapter and
        # is still handled by HoloVerse, so return can never be trapped here.
        if self.paused:
            if self.audio_runtime is not None:
                try:
                    self.audio_runtime.update(dt)
                except Exception:
                    pass
            return
        self._elapsed += dt
        if self.audio_runtime is not None:
            try:
                self.audio_runtime.update(dt)
            except Exception:
                pass
        if self._update_upgrade_choice():
            return
        self._update_player(dt)
        self._update_input_fire(dt)
        self._update_projectiles(dt)
        self._update_enemies(dt)
        self._update_impacts(dt)
        self._update_breach_loop(dt)
        self._update_wave_director(dt)
        self._update_wave_hazards(dt)
        self._update_scenery(dt)
        self._update_status(dt)
        self._update_weapon_viewmodel(dt)
        self._update_camera(dt)

    def get_native_contract(self) -> dict:
        """Describe host-facing behavior without requiring HoloVerse imports."""
        return {
            "schema": "holoverse_native_dimension_contract_v1",
            "dimension_id": MODE_ID,
            "title": MODE_TITLE,
            "same_window": True,
            "creates_showbase": False,
            "return_action": "tab",
            "pause_action": "escape",
            "help_action": "h",
            "entry_transition_audio": "assets/audio/transition/dimension_enter.wav",
            "exit_transition_audio": "assets/audio/transition/dimension_exit.wav",
            "result_method": "get_result",
        }

    def get_result(self) -> dict:
        return {
            "mode_id": MODE_ID,
            "score_delta": int(self.score),
            "completed": bool(self.wave >= 4 or self.kills >= 25),
            "kills": int(self.kills),
            "wave": int(self.wave),
            "highest_wave": int(self.highest_wave),
            "wave_kind": str(self.wave_kind),
            "wave_set": int(self.wave_set),
            "wave_threats_total": int(self.wave_total_threats),
            "wave_threats_defeated": int(self.wave_defeated),
            "guardian_waves_completed": int(self.guardian_waves_completed),
            "arena_reconstructions": int(self.reconstruction_count),
            "arena_mutations_survived": int(self.arena_mutations_survived),
            "arena_family": str(self.arena_profile.get("id", "PRISM_FOUNDRY")),
            "arena_family_name": str(self.arena_profile.get("name", "PRISM FOUNDRY")),
            "arena_radius": float(self.current_arena_radius),
            "arena_diameter": float(self.current_arena_radius * 2.0),
            "largest_arena_radius": float(self.largest_arena_radius),
            "arena_family_transitions": int(self.arena_family_transitions),
            "arena_family_counts": dict(self.arena_family_counts),
            "arena_architecture": str(getattr(self, "arena_architecture_name", self.arena_profile.get("architecture", "UNKNOWN"))),
            "arena_architecture_piece_count": int(getattr(self, "arena_architecture_piece_count", len(self.cover_blocks))),
            "arena_mutations_survived": int(self.arena_mutations_survived),
            "arena_mutation": str(self.arena_mutation_profile.get("id", "STABLE_MATRIX")),
            "arena_mutation_name": str(self.arena_mutation_profile.get("name", "STABLE MATRIX")),
            "upgrade_stacks": dict(self.upgrade_stacks),
            "upgrades_selected": int(self.upgrades_selected),
            "flanking_spawns": int(self.flanking_spawns),
            "guardian_specials_used": int(self.guardian_specials_used),
            "hazard_activations": int(self.hazard_activations),
            "hazard_hits_taken": int(self.hazard_hits_taken),
            "special_wave_counts": dict(self.special_wave_counts),
            "encounter_doctrine": str(self.encounter_doctrine.get("name", "BASELINE DISCIPLINE")),
            "enemy_evolution_spawns": int(self.enemy_evolution_spawns),
            "enemy_evolution_counts": dict(self.enemy_evolution_counts),
            "highest_evolution_level_seen": int(self.highest_evolution_level_seen),
            "guardian_phase_transitions": int(self.guardian_phase_transitions),
            "signal": "VECTOR_ARENA_PHASED_WAVE_COMBAT_TRACE" if self.kills else "VECTOR_ARENA_PHASED_ARENA_BOOT_TRACE",
            "scenery_theme": self._current_theme()["name"],
            "enemy_variants": dict(self.enemy_variant_counts),
            "weapon_fx": "pooled_muzzle_flash_repulsor_wave_heat_vent_sparks_and_layered_hitscan_beams",
            "weapon_rank": int(self.weapon_rank),
            "weapon_module": str(self.weapon_module_name),
            "weapon_upgrade_loop": "pass101_score_kill_wave_unlocked_weapon_tiers",
            "breaches_sealed": int(self.breaches_sealed),
            "breach_loop": "pass02_director_required_breach_waves_plus_sparse_optional_cores",
            "horde_director": "pass07_strategic_arena_architecture_plus_pass06_large_scale_plus_pass05_enemy_evolutions_guardian_phases",
            "sfx_loaded": int(self.sfx_loaded_count),
            "audio": self.audio_runtime.stats() if self.audio_runtime is not None else {"audio_loaded": 0, "spatial_enabled": False},
            "native_contract": self.get_native_contract(),
            "gleebs_response": "Vector Arena returned evolved-horde telemetry with enemy evolution levels, Guardian phases, doctrines, upgrades, arena mutations and hazards." if self.kills else "Vector Arena loaded as a clean HoloVerse evolved wave arena.",
        }

    def exit(self):
        if self.audio_runtime is not None:
            try:
                for core in self.breach_cores:
                    if core.audio_loop is not None:
                        self.audio_runtime.stop_loop(core.audio_loop)
                        core.audio_loop = None
                self.audio_runtime.stop()
            except Exception:
                pass
            self.audio_runtime = None
        try:
            self.ignore("mouse1")
            self.ignore("mouse3")
        except Exception:
            pass
        try:
            self.camera.reparentTo(self._saved_camera_parent)
            self.camera.setTransform(self._saved_camera_transform)
        except Exception:
            pass
        try:
            if self._saved_bg is not None and self.win is not None:
                self.win.setClearColor(self._saved_bg)
        except Exception:
            pass
        try:
            if self.win is not None and hasattr(self.win, "requestProperties"):
                props = WindowProperties()
                props.setCursorHidden(False)
                self.win.requestProperties(props)
        except Exception:
            pass
        for node in list(self._owned):
            try:
                if node is not None and not node.isEmpty():
                    node.removeNode()
            except Exception:
                pass
        self._owned.clear()
        self.enemies.clear()
        self.projectiles.clear()
        self.impacts.clear()
        self.spawn_pulses.clear()
        self.kill_bursts.clear()
        self.muzzle_flashes.clear()
        self.repulsor_waves.clear()
        self.heat_vent_sparks.clear()
        self.breach_cores.clear()
        self.arena_hazards.clear()
        self.pending_spawns.clear()
        self.wave_spawn_script.clear()
        self.upgrade_choices_cache.clear()
        self.upgrade_pending = False
        self.paused = False
        self._native_key_latches = {"escape": False, "h": False}
        self.cover_blocks.clear()
        self.enemy_variant_counts.clear()
        self.enemy_evolution_counts.clear()
        self._wave_evolution_announced.clear()
        self.sfx.clear()
        self._last_sfx_time.clear()
        self.scenery_nodes = {"primary": [], "secondary": [], "accent": [], "floor": []}
        self.scenery_motion_nodes.clear()
        self.cover_glow_nodes.clear()
        self.spawn_gate_nodes.clear()
        self.spawn_gate_groups.clear()
        self.weapon_glow_nodes.clear()
        self._entered = False


def create_mode(host, mode=None, entry_path=None, label=MODE_TITLE):
    return HoloVerseNativeMode(host, mode=mode, entry_path=entry_path, label=label)
