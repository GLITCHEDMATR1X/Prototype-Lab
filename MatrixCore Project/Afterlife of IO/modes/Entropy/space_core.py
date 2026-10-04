
# ================== SURFACE MODE STATE ==================
GAME_MODE_SPACE = "SPACE"
GAME_MODE_SURFACE = "SURFACE"
GAME_MODE_INTERIOR = "INTERIOR"

game_mode = GAME_MODE_SPACE
interior_return_mode = GAME_MODE_SPACE

planet_surface_cache = {}  # deprecated (moved to terrains.py)
active_planet_seed = None
SHIP_REF = None  # set in main(); used by surface pickups
surface_return_state = None  # snapshot of space state before landing
# ========================================================


"""
Entropy — a one-minute science-fiction survival/exploration prototype.

Begin on HOME during its final minute, survive the first supernova, restore a
disabled ship, then recover six Data Fragments from abandoned worlds before
their systems collapse. Deliver the completed archive to Gleebs. The runtime
is pygame-ce; player data is stored outside the shipping directory.

Primary controls are documented in README.md and CONTROLS.txt.
"""


import argparse
import os
import sys
import math
import itertools
import random
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from collections import OrderedDict

import pygame

from audio_ambience import AmbientAudio, ensure_ambient_assets
from gamepad_input import ControllerInput
from music_score import STATE_BASE_VOLUME, STATE_TRACKS, ensure_score_assets, score_state_for
from runtime_paths import (
    CRASH_LOG, RUNTIME_LOG, SAVE_PATH, get_last_save_read_info, load_settings,
    mark_session_checkpoint, mark_session_clean_exit, mark_session_started,
    read_save, save_settings, write_save,
)
import crash_reporter
from standard_ui import (
    draw_bottom_hint, draw_collapse_banner, draw_collapse_panel, draw_collapse_pressure,
    draw_campaign_complete_screen, draw_controls_overlay, draw_failure_screen, draw_mission_brief, draw_mission_tracker,
    draw_mode_chip, draw_pause_menu, draw_settings_menu, draw_run_start_screen, fit_window_16_9,
    font as ui_font, window_to_virtual,
)
from mission_state import (
    MissionState, CAMPAIGN_HOME, CAMPAIGN_SHIP_RECOVERY, CAMPAIGN_EXPEDITION, CAMPAIGN_COMPLETE,
    legacy_save_needs_home_prologue, HAZARD_FAMILY_BY_STYLE,
)
from expedition_identity import style_variety_score, world_profile
from surface_resources import (
    normalize_harvest_map, planet_exclusion_radius, planet_is_landable, resolve_planet_exclusion,
)
from system_safety import (
    SYSTEM_SPAWN_POSITION, reset_ship_to_system_spawn, star_impact_detected,
)
from ship_progression import ensure_progression, scanner_level, warp_quote
from collapse_rules import (
    BLACK_HOLE_DAMAGE_PER_SECOND, COLLAPSE_DURATION, SINGULARITY_DELAY,
    SUPERNOVA_SHOCK_DAMAGE, hull_damage_rate, timer_label, warning_text,
)


# ----------------------------
# Crash log + runtime log
# ----------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "Entropy"
APP_VERSION = "Pass 33 — Expedition Identity"

# ----------------------------
# Standard PC windowing/scaling
# ----------------------------
# The game always *simulates and renders* at this fixed virtual resolution.
# The OS window can be resized freely; we scale the virtual frame to the window
# using aspect-preserving **fit** scaling (letterboxed when necessary; never crops HUD).
VIRTUAL_W, VIRTUAL_H = 1920, 1080
THIRD_PERSON_TOGGLE_KEY = pygame.K_v
PAUSE_KEY = getattr(pygame, "K_BACKQUOTE", ord("`"))


# ----------------------------
# Terrain module (loaded on-demand)
# ----------------------------
import importlib

_TERRAINS = None

_INTERIORS = None

def _interiors():
    """Lazy-load interiors.py (ship interior view)."""
    global _INTERIORS
    if _INTERIORS is None:
        if BASE_DIR not in sys.path:
            sys.path.insert(0, BASE_DIR)
        _INTERIORS = importlib.import_module("interiors")
    return _INTERIORS


def _generate_varied_system(system, initial_seed: int, previous_style: str = "unknown") -> tuple[int, int]:
    """Generate a new system that strongly prefers a different hazard personality.

    Entropy still uses its normal seeded System.generate() authority.  We only
    reroll the seed before committing a *new* system so consecutive expeditions
    do not immediately repeat the same world class or hazard family.  Existing
    saved systems are never regenerated through this helper.
    """
    seed = int(initial_seed)
    fallback = None
    for attempt in range(18):
        system.generate(seed)
        style = str(getattr(system.planets[0], "style", "unknown")) if getattr(system, "planets", None) else "unknown"
        score = style_variety_score(previous_style, style, HAZARD_FAMILY_BY_STYLE)
        if score >= 2:
            return seed, attempt
        if score == 1 and fallback is None:
            fallback = (seed, attempt)
        seed = random.randrange(1_000_000_000)
    if fallback is not None:
        seed, attempt = fallback
        system.generate(seed)
        return seed, attempt
    system.generate(seed)
    return seed, 18

def _terrains():
    """Lazy-load terrains.py at planet approach/landing time for smoother performance and easier debugging."""
    global _TERRAINS
    if _TERRAINS is None:
        if BASE_DIR not in sys.path:
            sys.path.insert(0, BASE_DIR)
        _TERRAINS = importlib.import_module("terrains")
    return _TERRAINS



def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    line = f"[{_ts()}] {msg}"
    try:
        with open(RUNTIME_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


# Pass 30 installs durable crash reporting inside main() after launch-mode
# detection.  This keeps verification runs from leaving false unclean-session
# markers while still covering runtime initialization and gameplay failures.


# ----------------------------
# Asset scaffolding
# ----------------------------

def ensure_sfx_folders():
    """Best-effort developer scaffolding; packaged installs may be read-only."""
    ship_root = os.path.join(BASE_DIR, "assets", "sfx", "ship")
    folders = [
        *(os.path.join(ship_root, name) for name in (
            "engine_idle", "engine_thrust", "boost", "hyperspace",
            "laser", "missile", "ui",
        )),
        os.path.join(BASE_DIR, "assets", "sfx", "echo"),
        os.path.join(BASE_DIR, "assets", "holograms", "former_civ"),
        os.path.join(BASE_DIR, "assets", "music"),
        os.path.join(BASE_DIR, "assets", "galaxies"),
    ]
    failures = []
    for folder in folders:
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            failures.append(f"{folder}: {exc}")
    if failures:
        log("WARN: install folder is read-only; using packaged assets only. " + " | ".join(failures))
    return ship_root


def list_audio_files(folder: str):
    out = []
    if not os.path.isdir(folder):
        return out
    for fn in os.listdir(folder):
        lo = fn.lower()
        if lo.endswith((".wav", ".ogg", ".mp3")):
            out.append(os.path.join(folder, fn))
    out.sort()
    return out


def list_music_files(folder: str):
    # Music playlist scanner (no recursion)
    out = []
    if not os.path.isdir(folder):
        return out
    for fn in os.listdir(folder):
        lo = fn.lower()
        if lo.endswith((".mp3", ".ogg", ".wav")):
            out.append(os.path.join(folder, fn))
    out.sort()
    return out


# ----------------------------
# Math helpers
# ----------------------------

def clamp(x: float, a: float, b: float) -> float:
    return a if x < a else b if x > b else x


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smoothstep(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def vec3_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vec3_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec3_mul(a, s: float):
    return (a[0] * s, a[1] * s, a[2] * s)


def vec3_dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vec3_len(a) -> float:
    return math.sqrt(vec3_dot(a, a))


def vec3_norm(a):
    L = vec3_len(a)
    if L <= 1e-9:
        return (0.0, 0.0, 0.0)
    return (a[0] / L, a[1] / L, a[2] / L)


# Quaternion helpers use (w, x, y, z). They keep the spacecraft's three
# rotational axes independent at every attitude, avoiding Euler pitch clamps
# and gimbal-lock behavior near vertical flight.
def quat_identity():
    return (1.0, 0.0, 0.0, 0.0)


def quat_normalize(q):
    length = math.sqrt(sum(c * c for c in q))
    if length <= 1e-12:
        return quat_identity()
    return tuple(c / length for c in q)


def quat_conjugate(q):
    return (q[0], -q[1], -q[2], -q[3])


def quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def quat_from_axis_angle(axis, angle):
    axis = vec3_norm(axis)
    half = angle * 0.5
    scale = math.sin(half)
    return quat_normalize((math.cos(half), axis[0] * scale, axis[1] * scale, axis[2] * scale))


def quat_rotate_normalized(q, v):
    """Rotate a vector by an already-normalized quaternion without allocations."""
    w, x, y, z = q
    vx, vy, vz = v
    # Optimized q * v * conjugate(q) form. Spacecraft and camera quaternions
    # are normalized at mutation boundaries, so hot render loops avoid doing
    # another square root and tuple allocation for every visible object.
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def quat_rotate(q, v):
    """Safe public helper for quaternions that may not be normalized."""
    return quat_rotate_normalized(quat_normalize(q), v)


def quat_from_ypr(yaw, pitch, roll):
    # Matches the legacy renderer's Y -> X -> Z order.
    qy = quat_from_axis_angle((0.0, 1.0, 0.0), yaw)
    qx = quat_from_axis_angle((1.0, 0.0, 0.0), pitch)
    qz = quat_from_axis_angle((0.0, 0.0, 1.0), roll)
    return quat_normalize(quat_mul(quat_mul(qz, qx), qy))


def is_quaternion(value):
    return isinstance(value, (tuple, list)) and len(value) == 4


def wrap_angle(angle):
    return (angle + math.pi) % (math.tau) - math.pi


def hsv_to_rgb(h, s, v):
    h = (h % 1.0) * 6.0
    i = int(h)
    f = h - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    return (int(r * 255), int(g * 255), int(b * 255))


# -----------------------------
# REDSHIFT UNIVERSE RULE: static red background starfield (2D, cached)
# -----------------------------
_REDSHIFT_STAR_BG_CACHE = {}

def get_redshift_star_bg(w: int, h: int, seed: int):
    """Return a cached Surface containing many small red stars."""
    key = (int(w), int(h), int(seed))
    surf = _REDSHIFT_STAR_BG_CACHE.get(key)
    if surf is not None:
        return surf

    rr = random.Random(int(seed) ^ 0x51A7F00D)
    s = pygame.Surface((w, h), pygame.SRCALPHA)

    # Density tuned to stay visible even with vignette/scanline post FX.
    # Small stars only (1–3 px), biased to 1 px.
    n = int(w * h * 0.0012)  # dense but not windshield-like
    for _ in range(n):
        x = rr.randrange(0, w)
        y = rr.randrange(0, h)
        u = rr.random()
        if u < 0.92:
            r = 1
        else:
            r = 2
        # Red-only palette (end-of-universe redshift)
        cr = rr.randint(110, 200)
        cg = rr.randint(0, 22)
        cb = rr.randint(0, 22)
        a = rr.randint(80, 170)

        if r == 1:
            s.set_at((x, y), (cr, cg, cb, a))
        else:
            pygame.draw.circle(s, (cr, cg, cb, a), (x, y), r)

    surf = s.convert_alpha()
    _REDSHIFT_STAR_BG_CACHE[key] = surf
    return surf


# ----------------------------
# Orientation (yaw/pitch/roll)
# ----------------------------

def rot_x(v, a):
    ca, sa = math.cos(a), math.sin(a)
    return (v[0], v[1] * ca - v[2] * sa, v[1] * sa + v[2] * ca)


def rot_y(v, a):
    ca, sa = math.cos(a), math.sin(a)
    return (v[0] * ca + v[2] * sa, v[1], -v[0] * sa + v[2] * ca)


def rot_z(v, a):
    ca, sa = math.cos(a), math.sin(a)
    return (v[0] * ca - v[1] * sa, v[0] * sa + v[1] * ca, v[2])


def apply_ypr(v, yaw, pitch=0.0, roll=0.0):
    # Backward-compatible: callers may pass either legacy Euler angles or a
    # normalized quaternion in the yaw slot.
    if is_quaternion(yaw):
        return quat_rotate_normalized(yaw, v)
    v2 = rot_y(v, yaw)
    v2 = rot_x(v2, pitch)
    v2 = rot_z(v2, roll)
    return v2


def apply_inv_ypr(v, yaw, pitch=0.0, roll=0.0):
    if is_quaternion(yaw):
        return quat_rotate_normalized(quat_conjugate(yaw), v)
    v2 = rot_z(v, -roll)
    v2 = rot_x(v2, -pitch)
    v2 = rot_y(v2, -yaw)
    return v2


# ----------------------------
# Starfield
# ----------------------------

@dataclass
class Star:
    dir_world: tuple
    dist: float
    mag: float
    twinkle: float
    spectral: tuple = (255, 120, 96)
    glint: float = 0.0


@dataclass
class StellarCluster:
    dir_world: tuple
    size: float
    phase: float
    col: tuple
    density: float


class Starfield:
    """Layered redshift starfield with sparse bright anchors and deep clusters."""
    def __init__(self, n=6200, seed=17):
        rng = random.Random(seed)
        self.stars = []
        self.clusters = []
        for _ in range(9):
            z = rng.uniform(-0.65, 0.88)
            a = rng.uniform(0.0, math.tau)
            r = math.sqrt(max(0.0, 1.0 - z * z))
            d = vec3_norm((r * math.cos(a), r * math.sin(a), z))
            hue_pick = rng.random()
            if hue_pick < 0.55:
                col = (170, 38, 58)
            elif hue_pick < 0.85:
                col = (126, 54, 110)
            else:
                col = (72, 82, 138)
            self.clusters.append(StellarCluster(
                d, rng.uniform(34.0, 86.0), rng.uniform(0.0, math.tau), col, rng.uniform(0.45, 0.95)
            ))

        for _ in range(n):
            cluster = rng.choice(self.clusters) if rng.random() < 0.24 else None
            if cluster is None:
                z = rng.uniform(-1.0, 1.0)
                a = rng.uniform(0.0, math.tau)
                rr = math.sqrt(max(0.0, 1.0 - z * z))
                d = vec3_norm((rr * math.cos(a), rr * math.sin(a), z))
            else:
                spread = rng.uniform(0.018, 0.18) ** 1.25
                d = vec3_norm((
                    cluster.dir_world[0] + rng.uniform(-spread, spread),
                    cluster.dir_world[1] + rng.uniform(-spread, spread),
                    cluster.dir_world[2] + rng.uniform(-spread, spread),
                ))
            dist = lerp(120.0, 18000.0, rng.random() ** 2.35)
            mag = rng.uniform(0.18, 1.0) ** 2.0
            tw = rng.uniform(0.0, math.tau)
            q = rng.random()
            if q < 0.60:
                spectral = (255, 92, 76)
            elif q < 0.84:
                spectral = (255, 142, 92)
            elif q < 0.96:
                spectral = (255, 205, 166)
            else:
                spectral = (190, 204, 255)
            glint = rng.random() if mag > 0.72 and rng.random() < 0.10 else 0.0
            self.stars.append(Star(d, dist, mag, tw, spectral, glint))

        self._blue = 0.0
        self._last_tsec = None
        self._cluster_layer = None
        self._cluster_layer_size = (0, 0)

    def _cluster_surface(self, w, h):
        if self._cluster_layer is None or self._cluster_layer_size != (w, h):
            self._cluster_layer = pygame.Surface((w, h), pygame.SRCALPHA)
            self._cluster_layer_size = (w, h)
        else:
            self._cluster_layer.fill((0, 0, 0, 0))
        return self._cluster_layer

    def _draw_clusters(self, surf, w, h, inv_orientation, legacy_angles, tsec):
        cx, cy = w * 0.5, h * 0.5
        f = (w * 0.5) / math.tan(math.radians(88.0) * 0.5)
        layer = self._cluster_surface(w, h)
        for c in self.clusters:
            if inv_orientation is not None:
                dcam = quat_rotate_normalized(inv_orientation, c.dir_world)
            else:
                dcam = apply_inv_ypr(c.dir_world, *legacy_angles)
            if dcam[2] <= 0.10:
                continue
            x = dcam[0] * f / dcam[2] + cx
            y = dcam[1] * f / dcam[2] + cy
            if x < -180 or x > w + 180 or y < -180 or y > h + 180:
                continue
            pulse = 0.82 + 0.18 * math.sin(tsec * 0.20 + c.phase)
            rad = int(clamp(c.size * (0.65 + 0.55 * dcam[2]), 24, 110))
            for band in range(4, 0, -1):
                rr = int(rad * band / 4.0)
                alpha = int((8 + (4 - band) * 3) * c.density * pulse)
                pygame.draw.circle(layer, (*c.col, alpha), (int(x), int(y)), rr)
        surf.blit(layer, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def draw(self, surf, w, h, yaw, pitch, roll, vel_world, speed_norm, warp, tsec, hyperspace=False):
        inv_orientation = quat_conjugate(yaw) if is_quaternion(yaw) else None
        legacy_angles = (yaw, pitch, roll)
        self._draw_clusters(surf, w, h, inv_orientation, legacy_angles, tsec)
        cx, cy = w * 0.5, h * 0.5
        fov = lerp(78.0, 104.0, clamp(speed_norm * 0.8 + warp * 0.8, 0.0, 1.0))
        if hyperspace:
            fov = 110.0
        f = (w * 0.5) / math.tan(math.radians(fov) * 0.5)

        vdir = vec3_norm(vel_world)
        vmag = vec3_len(vel_world)
        beta = clamp(vmag / (1600.0 if hyperspace else 850.0), 0.0, 1.0)
        streak = smoothstep(clamp(warp, 0.0, 1.0))
        if hyperspace:
            streak = 1.0

        if self._last_tsec is None:
            dt = 0.0
            self._last_tsec = tsec
        else:
            dt = max(0.0, min(0.2, tsec - self._last_tsec))
            self._last_tsec = tsec
        self._blue = max(self._blue * math.exp(-dt * 2.6), 1.0 if hyperspace else clamp(warp, 0.0, 1.0))
        boost = 1.0 if hyperspace else self._blue
        forward_bias = lerp(1.0, 4.2 if hyperspace else 3.1, boost)

        # Fast-motion LOD removes only the faintest half of the field while
        # streaks are already filling the view. Idle exploration retains the
        # complete authored star distribution. islice avoids allocating a new
        # ~3K-entry list on every boost/warp render frame.
        fast_lod = bool(hyperspace or boost > 0.82)
        star_iter = itertools.islice(self.stars, 0, None, 2) if fast_lod else iter(self.stars)
        single_pixels = []
        if inv_orientation is not None:
            qw, qx, qy, qz = inv_orientation
        else:
            qw = qx = qy = qz = 0.0
        vdx, vdy, vdz = vdir
        for s in star_iter:
            if inv_orientation is not None:
                # Inline the normalized-quaternion vector rotation in this
                # hottest render loop. This preserves the exact math while
                # avoiding thousands of Python function calls per frame.
                vx, vy, vz = s.dir_world
                tx = 2.0 * (qy * vz - qz * vy)
                ty = 2.0 * (qz * vx - qx * vz)
                tz = 2.0 * (qx * vy - qy * vx)
                dcx = vx + qw * tx + (qy * tz - qz * ty)
                dcy = vy + qw * ty + (qz * tx - qx * tz)
                dcz = vz + qw * tz + (qx * ty - qy * tx)
            else:
                dcx, dcy, dcz = apply_inv_ypr(s.dir_world, *legacy_angles)
            z = dcz
            if z <= 0.04:
                continue
            x = dcx * f / z + cx
            y = dcy * f / z + cy
            if x < -100 or x > w + 100 or y < -100 or y > h + 100:
                continue

            if beta > 1e-6:
                svx, svy, svz = s.dir_world
                ct = vdx * svx + vdy * svy + vdz * svz
            else:
                ct = 0.0
            shift = clamp(ct * beta, -1.0, 1.0)
            tw = 0.80 + 0.20 * math.sin(tsec * (1.1 + 1.8 * s.mag) + s.twinkle)
            depth = clamp(1.0 - s.dist / 18000.0, 0.0, 1.0)
            brightness = clamp((0.38 + 0.72 * s.mag) * tw * (0.78 + 0.38 * depth), 0.0, 1.0)
            if boost > 0.02:
                target = (142, 112, 255) if shift < 0.22 else (112, 202, 255)
                col = _mix(s.spectral, target, clamp(0.38 + boost * 0.55 + max(0.0, shift) * 0.22, 0.0, 0.95))
            else:
                col = _mix(s.spectral, (255, 40, 56), 0.58)
            col = (
                int(clamp(col[0] * brightness, 0, 255)),
                int(clamp(col[1] * brightness, 0, 255)),
                int(clamp(col[2] * brightness, 0, 255)),
            )

            size = 1
            if s.mag > 0.66 and depth > 0.15:
                size = 2
            if s.mag > 0.91 and depth > 0.38:
                size = 3

            dx = x - cx
            dy = y - cy
            pull = lerp(1.0, 1.0 / forward_bias, clamp((z - 0.04) * 0.25, 0.0, 1.0))
            xw = cx + dx * pull
            yw = cy + dy * pull
            ix, iy = int(xw), int(yw)

            if size == 1 and s.glint <= 0.0 and streak <= 0.0 and 0 <= ix < w and 0 <= iy < h:
                single_pixels.append((ix, iy, col))
            else:
                pygame.draw.circle(surf, col, (ix, iy), size)

            if s.glint > 0.0 and streak < 0.18:
                gl = 2 + int(5 * s.glint * brightness)
                gcol = _mix(col, (255, 230, 228), 0.40)
                pygame.draw.aaline(surf, gcol, (xw - gl, yw), (xw + gl, yw))
                pygame.draw.aaline(surf, gcol, (xw, yw - gl), (xw, yw + gl))

            if streak > 0.0:
                dl = math.hypot(dx, dy) + 1e-6
                ux, uy = dx / dl, dy / dl
                align = clamp(z, 0.0, 1.0)
                length = (26 + 170 * boost) * (0.24 + 0.95 * s.mag) * (0.34 + 0.66 * align)
                pygame.draw.aaline(surf, col, (xw, yw), (xw + ux * length, yw + uy * length))

        if single_pixels:
            pixels = pygame.PixelArray(surf)
            for px, py, col in single_pixels:
                pixels[px, py] = col
            pixels.close()


_TRANSITION_LAYER_CACHE = {}


def _transition_layer(name, size):
    key = (name, int(size[0]), int(size[1]))
    layer = _TRANSITION_LAYER_CACHE.get(key)
    if layer is None:
        layer = pygame.Surface(size, pygame.SRCALPHA)
        _TRANSITION_LAYER_CACHE[key] = layer
        for old_key in list(_TRANSITION_LAYER_CACHE):
            if old_key != key and old_key[0] == name:
                _TRANSITION_LAYER_CACHE.pop(old_key, None)
    else:
        layer.fill((0, 0, 0, 0))
    return layer


def draw_warp_tunnel(screen, w, h, tsec, strength=1.0):
    """Animated warp tunnel overlay (separate from boost star-streaking)."""
    strength = clamp(strength, 0.0, 1.0)
    if strength <= 0.001:
        return
    cx, cy = w * 0.5, h * 0.5
    ov = _transition_layer('warp', (w, h))

    rings = 26
    for i in range(rings):
        u = i / (rings - 1)
        # rings move "toward" viewer
        z = (1.0 - u) ** 1.6
        r = (0.12 + 1.15 * z) * min(w, h) * 0.42
        wob = math.sin(tsec * (1.6 + u * 2.2) + i) * (8.0 + 22.0 * u)
        x0 = cx + wob * 0.35
        y0 = cy + wob * 0.20
        a = int((140 * strength) * (1.0 - u) * 0.95)
        pygame.draw.ellipse(ov, (210, 230, 255, a), (x0 - r, y0 - r * 0.62, r * 2, r * 1.24), 1)

    # radial streaks
    rays = 90
    for k in range(rays):
        ang = (k / rays) * math.tau + math.sin(tsec * 0.75) * 0.08
        r0 = min(w, h) * 0.05
        r1 = min(w, h) * (0.45 + 0.25 * math.sin(tsec * 1.2 + k))
        x0 = cx + math.cos(ang) * r0
        y0 = cy + math.sin(ang) * r0
        x1 = cx + math.cos(ang) * r1
        y1 = cy + math.sin(ang) * r1
        a = int(30 + 90 * strength)
        pygame.draw.aaline(ov, (220, 240, 255, a), (x0, y0), (x1, y1))

    screen.blit(ov, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)


def draw_atmosphere_entry(screen, w, h, tsec, strength=1.0):
    """Atmosphere-entry style warp overlay: heated streaks + horizon glow."""
    strength = clamp(strength, 0.0, 1.0)
    if strength <= 0.001:
        return
    cx, cy = w * 0.5, h * 0.5
    ov = _transition_layer('atmosphere_entry', (w, h))

    # heated streaks (downward bias)
    streaks = 140
    for k in range(streaks):
        ang = (k / streaks) * math.tau
        # bias toward bottom hemisphere to feel like "down"
        bias = 0.55 + 0.45 * math.sin(ang)  # [-? ..]
        r0 = min(w, h) * 0.10
        r1 = min(w, h) * (0.55 + 0.20 * math.sin(tsec * 1.4 + k))
        x0 = cx + math.cos(ang) * r0
        y0 = cy + math.sin(ang) * r0 * 0.8 + (bias * h * 0.04)
        x1 = cx + math.cos(ang) * r1
        y1 = cy + math.sin(ang) * r1 * 0.9 + (bias * h * 0.10)
        a = int(30 + 110 * strength)
        # warm plasma tint
        pygame.draw.aaline(ov, (255, 160, 90, a), (x0, y0), (x1, y1))

    # horizon glow band
    band_h = int(h * 0.45)
    band = _transition_layer('atmosphere_band', (w, band_h))
    for yy in range(band_h):
        u = yy / max(1, band_h - 1)
        a = int(180 * (1.0 - u) * strength)
        band.fill((255, 120, 60, a), rect=pygame.Rect(0, yy, w, 1))
    screen.blit(band, (0, int(h * 0.55)), special_flags=pygame.BLEND_RGBA_ADD)

    screen.blit(ov, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)



# ----------------------------
# Distant Galaxies + Solar Systems
# ----------------------------

@dataclass
class Galaxy:
    dir_world: tuple
    dist: float
    size: float
    twist: float
    hue: float
    img: any = field(default=None, repr=False, compare=False)


class GalaxyField:
    """
    Very-far background galaxies. Projected like stars but drawn as faint smudges.
    Used as warp destinations.
    """
    def __init__(self, n=42, seed=2025):
        rng = random.Random(seed)
        self.galaxy_images = []
        gal_dir = os.path.join(BASE_DIR, "assets", "galaxies")
        if os.path.isdir(gal_dir):
            for fn in os.listdir(gal_dir):
                lo = fn.lower()
                if lo.endswith((".png", ".jpg", ".jpeg", ".webp")):
                    fp = os.path.join(gal_dir, fn)
                    try:
                        img = pygame.image.load(fp)
                        try:
                            img = img.convert_alpha()
                        except Exception:
                            pass
                        self.galaxy_images.append(img)
                    except Exception:
                        pass
        self._scaled_image_cache = {}
        self._layer = None
        self._layer_size = (0, 0)
        self.galaxies = []
        for _ in range(n):
            z = rng.uniform(-0.25, 1.0)
            t = rng.uniform(0.0, 2.0 * math.pi)
            r = math.sqrt(max(0.0, 1.0 - z * z))
            x = r * math.cos(t)
            y = r * math.sin(t)
            d = vec3_norm((x, y, z))
            dist = rng.uniform(160000.0, 420000.0)
            size = rng.uniform(10.0, 24.0)
            twist = rng.uniform(0.0, math.tau)
            hue = rng.random()
            g = Galaxy(d, dist, size, twist, hue)
            if self.galaxy_images:
                g.img = rng.choice(self.galaxy_images)
            self.galaxies.append(g)

    def best_target_in_view(self, forward_world):
        best_i = -1
        best_align = -1.0
        fwd = vec3_norm(forward_world)
        for i, g in enumerate(self.galaxies):
            a = vec3_dot(fwd, g.dir_world)
            if a > best_align:
                best_align = a
                best_i = i
        return best_i, best_align

    def draw(self, surf, w, h, yaw, pitch, roll, tsec, highlight_idx=-1):
        cx, cy = w * 0.5, h * 0.5
        fov = 86.0
        f = (w * 0.5) / math.tan(math.radians(fov) * 0.5)

        if self._layer is None or self._layer_size != (w, h):
            self._layer = pygame.Surface((w, h), pygame.SRCALPHA)
            self._layer_size = (w, h)
        else:
            self._layer.fill((0, 0, 0, 0))
        layer = self._layer
        inv_orientation = quat_conjugate(yaw) if is_quaternion(yaw) else None

        for i, g in enumerate(self.galaxies):
            if inv_orientation is not None:
                dcam = quat_rotate_normalized(inv_orientation, g.dir_world)
            else:
                dcam = apply_inv_ypr(g.dir_world, yaw, pitch, roll)
            z = dcam[2]
            if z <= 0.08:
                continue

            invz = 1.0 / z
            x = dcam[0] * f * invz + cx
            y = dcam[1] * f * invz + cy
            if x < -120 or x > w + 120 or y < -120 or y > h + 120:
                continue

            base = hsv_to_rgb(g.hue, 0.45, 0.95)
            hi = (i == highlight_idx)
            alpha = 42 if not hi else 84
            sz = int(g.size * (0.70 + 0.85 * z))
            sz = int(clamp(sz, 14, 64))

            # If galaxy images exist, use them as background billboards.
            if g.img is not None:
                # Scale with depth; keep soft additive presence.
                s2 = int(clamp(sz * 2, 24, 220))
                alpha_value = 72 if not hi else 118
                cache_key = (id(g.img), s2, alpha_value)
                img = self._scaled_image_cache.get(cache_key)
                if img is None:
                    try:
                        img = pygame.transform.smoothscale(g.img, (s2, s2))
                    except Exception:
                        img = g.img.copy()
                    try:
                        img.set_alpha(alpha_value)
                    except Exception:
                        pass
                    if len(self._scaled_image_cache) >= 128:
                        self._scaled_image_cache.pop(next(iter(self._scaled_image_cache)), None)
                    self._scaled_image_cache[cache_key] = img
                layer.blit(img, img.get_rect(center=(int(x), int(y))), special_flags=pygame.BLEND_RGBA_ADD)
                continue

            # Swirl: draw a logarithmic-spiral ribbon made of many short segments
            arms = 3
            for arm in range(arms):
                arm_phase = g.twist + (arm / arms) * math.tau
                prev = None
                steps = 46
                # spiral winds outward
                for s in range(steps):
                    u = s / (steps - 1)
                    ang = arm_phase + (u * (4.0 * math.pi)) + math.sin(tsec * 0.25 + i) * 0.15
                    rad = (u ** 0.85) * sz
                    sx = x + math.cos(ang) * rad
                    sy = y + math.sin(ang) * rad * 0.62
                    if prev is not None:
                        # taper alpha and thickness outward
                        a = int(alpha * (1.0 - 0.55 * u))
                        col = (base[0], base[1], base[2], a)
                        pygame.draw.aaline(layer, col, prev, (sx, sy))
                    prev = (sx, sy)

            # bright nucleus
            pygame.draw.circle(layer, (255, 255, 255, 18 if not hi else 32), (int(x), int(y)), max(1, sz // 12))
            pygame.draw.circle(layer, (base[0], base[1], base[2], 10 if not hi else 18), (int(x), int(y)), max(1, sz // 7))

        # subtle additive blend to keep them behind everything
        surf.blit(layer, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)



# ----------------------------
# Orbital planet materials (cached procedural rendering)
# ----------------------------

ORBITAL_PLANET_STYLES = (
    "desert", "ice", "jungle", "volcanic", "crystal", "oceanic",
    "fungal", "rust", "salt", "abyss", "storm", "roseglass",
)

ORBITAL_STYLE_PALETTES = {
    "desert": {
        "low": (72, 42, 30), "mid": (168, 104, 54), "high": (236, 184, 102),
        "accent": (255, 214, 130), "atmo": (255, 164, 82), "cloud": (244, 196, 144),
    },
    "ice": {
        "low": (22, 50, 84), "mid": (92, 154, 196), "high": (224, 244, 255),
        "accent": (146, 236, 255), "atmo": (120, 210, 255), "cloud": (236, 250, 255),
    },
    "jungle": {
        "low": (10, 42, 58), "mid": (32, 112, 72), "high": (126, 186, 90),
        "accent": (126, 255, 154), "atmo": (94, 220, 154), "cloud": (208, 238, 210),
    },
    "volcanic": {
        "low": (12, 12, 18), "mid": (46, 30, 34), "high": (92, 54, 42),
        "accent": (255, 82, 34), "atmo": (255, 90, 50), "cloud": (154, 94, 76),
    },
    "crystal": {
        "low": (18, 22, 58), "mid": (58, 52, 126), "high": (116, 102, 210),
        "accent": (112, 255, 246), "atmo": (116, 166, 255), "cloud": (196, 190, 255),
    },
    "oceanic": {
        "low": (4, 32, 78), "mid": (12, 92, 150), "high": (64, 170, 178),
        "accent": (124, 255, 238), "atmo": (88, 194, 255), "cloud": (232, 248, 255),
    },
    "fungal": {
        "low": (38, 18, 58), "mid": (106, 48, 114), "high": (168, 86, 144),
        "accent": (172, 255, 112), "atmo": (220, 112, 234), "cloud": (230, 180, 226),
    },
    "rust": {
        "low": (54, 28, 24), "mid": (142, 62, 38), "high": (218, 126, 66),
        "accent": (255, 188, 92), "atmo": (230, 110, 68), "cloud": (202, 134, 104),
    },
    "salt": {
        "low": (82, 76, 102), "mid": (184, 176, 204), "high": (246, 242, 252),
        "accent": (255, 188, 222), "atmo": (202, 188, 255), "cloud": (255, 252, 255),
    },
    "abyss": {
        "low": (2, 8, 28), "mid": (10, 42, 74), "high": (24, 104, 126),
        "accent": (66, 255, 224), "atmo": (46, 132, 196), "cloud": (92, 142, 170),
    },
    "storm": {
        "low": (30, 38, 64), "mid": (76, 92, 134), "high": (178, 176, 190),
        "accent": (255, 196, 118), "atmo": (154, 178, 238), "cloud": (228, 222, 226),
    },
    "roseglass": {
        "low": (42, 12, 48), "mid": (124, 44, 106), "high": (224, 104, 170),
        "accent": (102, 255, 246), "atmo": (255, 116, 210), "cloud": (246, 184, 226),
    },
}


def _planet_wave(lon, lat, seed, freq=1.0):
    """Smooth deterministic pseudo-noise using layered spherical waves."""
    s = float(seed & 0xFFFF) * 0.000173
    v = (
        math.sin(lon * (1.65 * freq) + s * 7.1) * 0.34
        + math.sin(lat * (2.75 * freq) - lon * 0.47 + s * 11.3) * 0.24
        + math.cos(lon * (3.8 * freq) + lat * 1.55 + s * 17.7) * 0.18
        + math.sin(lon * (7.1 * freq) - lat * 4.2 + s * 23.9) * 0.12
        + math.cos(lon * (13.7 * freq) + lat * 8.4 + s * 31.1) * 0.07
    )
    return clamp(0.5 + v, 0.0, 1.0)


def _planet_ridge(lon, lat, seed, freq=1.0):
    n = _planet_wave(lon, lat, seed, freq)
    return 1.0 - abs(n * 2.0 - 1.0)


def _style_surface_color(style, palette, lon, lat, seed):
    broad = _planet_wave(lon, lat, seed, 0.72)
    detail = _planet_wave(lon + broad * 0.35, lat, seed ^ 0x51A9, 1.42)
    fine = _planet_wave(lon, lat, seed ^ 0xB17E, 2.35)
    ridge = _planet_ridge(lon, lat, seed ^ 0xD15C, 1.55)
    emission = 0.0
    specular = 0.0

    if style == "oceanic":
        land = broad > 0.61
        if land:
            t = clamp((broad - 0.61) * 2.2 + detail * 0.28, 0.0, 1.0)
            col = _mix(palette["mid"], (86, 148, 92), t)
        else:
            t = clamp(detail * 0.72, 0.0, 1.0)
            col = _mix(palette["low"], palette["mid"], t)
            specular = 0.72
    elif style == "jungle":
        ocean = broad < 0.39
        if ocean:
            col = _mix((5, 34, 70), (18, 88, 112), detail)
            specular = 0.48
        else:
            height = clamp((broad - 0.39) * 1.55 + fine * 0.18, 0.0, 1.0)
            col = _mix(palette["mid"], palette["high"], height)
    elif style == "desert":
        dunes = 0.5 + 0.5 * math.sin(lon * 9.0 + lat * 4.0 + fine * 3.2)
        basin = broad < 0.32
        col = _mix(palette["low"] if basin else palette["mid"], palette["high"], dunes * 0.55 + detail * 0.25)
    elif style == "ice":
        polar = clamp(abs(lat) / (math.pi * 0.5), 0.0, 1.0)
        col = _mix(palette["mid"], palette["high"], clamp(0.32 + polar * 0.60 + broad * 0.22, 0.0, 1.0))
        crack = ridge > 0.91 and fine > 0.46
        if crack:
            col = _mix(palette["low"], palette["accent"], 0.34)
        specular = 0.38 + polar * 0.30
    elif style == "volcanic":
        crust = clamp(detail * 0.68 + broad * 0.24, 0.0, 1.0)
        col = _mix(palette["low"], palette["high"], crust * 0.62)
        lava = (ridge > 0.86 and fine > 0.52) or broad > 0.88
        if lava:
            heat = clamp((ridge - 0.82) * 5.5 + (broad - 0.82) * 3.0, 0.0, 1.0)
            col = _mix((180, 42, 16), palette["accent"], heat)
            emission = 0.72 + heat * 0.28
    elif style == "crystal":
        facets = int((lon + math.pi) * 3.2 + int((lat + math.pi * 0.5) * 4.0)) & 3
        facet_t = clamp(detail * 0.55 + facets * 0.12, 0.0, 1.0)
        col = _mix(palette["low"], palette["high"], facet_t)
        crack = ridge > 0.88 or abs(math.sin(lon * 11.0 + lat * 7.0 + seed * 0.01)) < 0.045
        if crack:
            col = _mix(palette["accent"], (255, 255, 255), 0.30)
            emission = 0.78
    elif style == "fungal":
        spots = 0.5 + 0.5 * math.sin(lon * 8.0 + math.sin(lat * 6.0) * 2.4 + seed * 0.013)
        col = _mix(palette["low"], palette["high"], broad * 0.42 + detail * 0.30)
        if spots > 0.82 and fine > 0.52:
            col = _mix(col, palette["accent"], 0.58)
            emission = 0.26
    elif style == "rust":
        canyon = ridge > 0.84
        col = _mix(palette["low"], palette["high"], broad * 0.55 + detail * 0.25)
        if canyon:
            col = _mix(col, (44, 20, 20), 0.62)
    elif style == "salt":
        plate = clamp(int(detail * 6.0) / 5.0, 0.0, 1.0)
        col = _mix(palette["mid"], palette["high"], plate * 0.72 + broad * 0.18)
        if ridge > 0.91:
            col = _mix(palette["low"], palette["accent"], 0.38)
        specular = 0.28
    elif style == "abyss":
        col = _mix(palette["low"], palette["mid"], broad * 0.44 + detail * 0.22)
        trench = ridge > 0.88 and fine > 0.48
        if trench:
            col = _mix(palette["accent"], palette["high"], 0.34)
            emission = 0.66
    elif style == "storm":
        bands = 0.5 + 0.5 * math.sin(lat * 14.0 + math.sin(lon * 2.0 + seed * 0.01) * 1.4)
        swirl = _planet_wave(lon + math.sin(lat * 3.0) * 0.6, lat, seed ^ 0xAA71, 1.4)
        col = _mix(palette["low"], palette["high"], clamp(bands * 0.58 + swirl * 0.34, 0.0, 1.0))
        storm_eye = math.hypot(math.sin(lon * 0.5), (lat - 0.16) * 1.8)
        if storm_eye < 0.18:
            col = _mix(palette["accent"], (255, 240, 210), clamp((0.18 - storm_eye) * 5.5, 0.0, 1.0))
    elif style == "roseglass":
        col = _mix(palette["low"], palette["high"], broad * 0.44 + detail * 0.34)
        shard = ridge > 0.87 or abs(math.sin(lon * 8.0 - lat * 9.0 + seed * 0.015)) < 0.052
        if shard:
            col = _mix(palette["accent"], (255, 214, 248), 0.24)
            emission = 0.58
    else:
        col = _mix(palette["low"], palette["high"], broad)

    return col, emission, specular


def _planet_lod_for_radius(rpx):
    if rpx < 11:
        return 24
    if rpx < 24:
        return 48
    if rpx < 52:
        return 80
    if rpx < 110:
        return 128
    return 192


def _quantized_light(light_cam):
    # Stable cache buckets avoid rebuilding textures for tiny camera changes.
    return tuple(int(round(clamp(v, -1.0, 1.0) * 4.0)) for v in light_cam)




def _surface_pixel_count(surface):
    try:
        if isinstance(surface, tuple) and surface and hasattr(surface[0], 'get_size'):
            surface = surface[0]
        w, h = surface.get_size()
        return int(w) * int(h)
    except Exception:
        return 0


def _cache_surface_lru(cache, key, surface, max_items, max_pixels):
    """Bound surface caches by both item count and approximate pixel memory."""
    if not isinstance(cache, OrderedDict):
        cache = OrderedDict(cache)
    cache[key] = surface
    cache.move_to_end(key)
    total_pixels = sum(_surface_pixel_count(item) for item in cache.values())
    while cache and (len(cache) > max_items or total_pixels > max_pixels):
        old_key, old_surface = cache.popitem(last=False)
        if old_key == key and not cache:
            cache[old_key] = old_surface
            break
        total_pixels -= _surface_pixel_count(old_surface)
    return cache

def render_orbital_planet(p, diameter, light_cam, tsec):
    """Return a cached textured/lit planet disc at the requested diameter."""
    diameter = max(4, int(diameter))
    rpx = diameter * 0.5
    lod = _planet_lod_for_radius(rpx)
    rotation = float(getattr(p, "texture_phase", 0.0)) + tsec * float(getattr(p, "texture_speed", 0.0))
    cloud_rotation = float(getattr(p, "cloud_phase", 0.0)) + tsec * float(getattr(p, "cloud_speed", 0.0))
    rotation_step = int((rotation % math.tau) / math.tau * 32.0) % 32
    cloud_step = int((cloud_rotation % math.tau) / math.tau * 40.0) % 40
    key = (lod, rotation_step, cloud_step, _quantized_light(light_cam))
    cache = getattr(p, "orbital_cache", None)
    if not isinstance(cache, OrderedDict):
        cache = OrderedDict(cache or {})
        p.orbital_cache = cache
    base = cache.get(key)
    if base is not None:
        cache.move_to_end(key)
    if base is None:
        base = pygame.Surface((lod, lod), pygame.SRCALPHA)
        rad = lod * 0.5
        inv = 1.0 / rad
        style = getattr(p, "style", "oceanic")
        palette = ORBITAL_STYLE_PALETTES.get(style, ORBITAL_STYLE_PALETTES["oceanic"])
        seed = int(getattr(p, "surface_seed", 0))
        rot = (rotation_step / 32.0) * math.tau
        cloud_rot = (cloud_step / 40.0) * math.tau
        light = vec3_norm(light_cam)
        view = (0.0, 0.0, 1.0)
        half_vec = vec3_norm(vec3_add(light, view))
        cloud_density = float(getattr(p, "cloud_density", 0.0))
        emission_strength = float(getattr(p, "emission_strength", 1.0))

        pixels = pygame.PixelArray(base)
        for py in range(lod):
            ny = (py + 0.5 - rad) * inv
            for px in range(lod):
                nx = (px + 0.5 - rad) * inv
                rr2 = nx * nx + ny * ny
                if rr2 > 1.0:
                    continue
                nz = math.sqrt(max(0.0, 1.0 - rr2))
                lon = math.atan2(nx, nz) + rot
                lat = math.asin(clamp(ny, -1.0, 1.0))
                surface_col, emission, specular = _style_surface_color(style, palette, lon, lat, seed)

                ndl_raw = nx * light[0] + ny * light[1] + nz * light[2]
                diffuse = clamp(ndl_raw, 0.0, 1.0)
                night = clamp(-ndl_raw, 0.0, 1.0)
                shade = 0.165 + diffuse * 0.835
                col = [surface_col[0] * shade, surface_col[1] * shade, surface_col[2] * shade]

                if emission > 0.0:
                    e = emission * emission_strength * (0.34 + night * 0.92)
                    accent = palette["accent"]
                    col[0] += accent[0] * e
                    col[1] += accent[1] * e
                    col[2] += accent[2] * e

                if specular > 0.0 and diffuse > 0.0:
                    ndh = clamp(nx * half_vec[0] + ny * half_vec[1] + nz * half_vec[2], 0.0, 1.0)
                    shine = (ndh ** 24.0) * specular * 190.0
                    col[0] += shine
                    col[1] += shine
                    col[2] += shine

                if cloud_density > 0.0:
                    cloud_n = _planet_wave(lon + cloud_rot, lat * 1.06, seed ^ 0xC10D, 1.18)
                    band = 0.5 + 0.5 * math.sin(lat * (11.0 if style == "storm" else 6.0) + lon * 0.42)
                    cloud_signal = cloud_n * 0.72 + band * 0.28
                    threshold = 0.76 - cloud_density * 0.27
                    if cloud_signal > threshold:
                        alpha = clamp((cloud_signal - threshold) / max(0.08, 1.0 - threshold), 0.0, 1.0)
                        alpha *= 0.34 + diffuse * 0.56
                        cloud_col = palette["cloud"]
                        col[0] = lerp(col[0], cloud_col[0] * (0.35 + diffuse * 0.65), alpha)
                        col[1] = lerp(col[1], cloud_col[1] * (0.35 + diffuse * 0.65), alpha)
                        col[2] = lerp(col[2], cloud_col[2] * (0.35 + diffuse * 0.65), alpha)

                rim = (1.0 - nz) ** 2.35
                atmo = palette["atmo"]
                rim_strength = rim * (0.16 + diffuse * 0.24)
                col[0] += atmo[0] * rim_strength
                col[1] += atmo[1] * rim_strength
                col[2] += atmo[2] * rim_strength

                pixels[px, py] = (
                    int(clamp(col[0], 0, 255)),
                    int(clamp(col[1], 0, 255)),
                    int(clamp(col[2], 0, 255)),
                    255,
                )
        pixels.close()

        pygame.draw.circle(base, (3, 5, 10, 180), (lod // 2, lod // 2), lod // 2, max(1, lod // 48))
        p.orbital_cache = _cache_surface_lru(
            cache, key, base, max_items=8, max_pixels=8 * 192 * 192
        )
        cache = p.orbital_cache

    draw_diameter = max(4, int(round(diameter / 2.0) * 2))
    if base.get_size() == (draw_diameter, draw_diameter):
        return base
    scaled_cache = getattr(p, "orbital_scaled_cache", None)
    if not isinstance(scaled_cache, OrderedDict):
        scaled_cache = OrderedDict(scaled_cache or {})
        p.orbital_scaled_cache = scaled_cache
    scaled_key = (key, draw_diameter)
    scaled = scaled_cache.get(scaled_key)
    if scaled is not None:
        scaled_cache.move_to_end(scaled_key)
    if scaled is None:
        try:
            scaled = pygame.transform.smoothscale(base, (draw_diameter, draw_diameter))
        except Exception:
            scaled = pygame.transform.scale(base, (draw_diameter, draw_diameter))
        # Large close-up discs can otherwise retain hundreds of MB across
        # multiple planets. Keep an LRU pixel budget while retaining the most
        # recent approach sizes for smooth motion.
        pixel_budget = 6_000_000 if draw_diameter <= 1024 else 4_000_000
        p.orbital_scaled_cache = _cache_surface_lru(
            scaled_cache, scaled_key, scaled, max_items=8, max_pixels=pixel_budget
        )
    return scaled


def draw_orbital_atmosphere(screen, sx, sy, rpx, p, light_cam):
    if rpx < 3 or getattr(p, "atmo_alpha", 0) <= 0:
        return
    # Atmosphere geometry changes slowly relative to frame rate. Quantize size
    # and light direction so close approaches reuse the same local halo.
    qr = max(3, int(round(float(rpx) / 2.0) * 2))
    light_bucket = (
        int(round(clamp(light_cam[0], -1.0, 1.0) * 5.0)),
        int(round(clamp(light_cam[1], -1.0, 1.0) * 5.0)),
    )
    cache = getattr(p, "orbital_atmo_cache", None)
    if not isinstance(cache, OrderedDict):
        cache = OrderedDict(cache or {})
        p.orbital_atmo_cache = cache
    key = (qr, light_bucket)
    cached = cache.get(key)
    if cached is not None:
        cache.move_to_end(key)
        layer, center = cached
    else:
        at_r = max(int(qr * float(getattr(p, "atmo_thickness", 1.18))), qr + 2)
        layer = pygame.Surface((at_r * 2 + 4, at_r * 2 + 4), pygame.SRCALPHA)
        center = at_r + 2
        col = getattr(p, "atmo_col", (160, 210, 255))
        alpha = int(getattr(p, "atmo_alpha", 50))
        span = max(2, at_r - qr)
        for rr in range(at_r, qr, -1):
            u = (rr - qr) / float(span)
            aa = max(1, int(alpha * ((1.0 - u) ** 1.6) * 0.18))
            pygame.draw.circle(layer, (*col, aa), (center, center), rr, 1)

        lxy = vec3_norm((light_bucket[0], light_bucket[1], 0.0))
        ox = int(lxy[0] * qr * 0.08)
        oy = int(lxy[1] * qr * 0.08)
        pygame.draw.circle(
            layer, (*col, max(12, int(alpha * 0.34))),
            (center + ox, center + oy), max(2, int(qr * 1.04)),
            max(1, int(qr * 0.014)),
        )
        p.orbital_atmo_cache = _cache_surface_lru(
            cache,
            key,
            (layer, center),
            max_items=6,
            max_pixels=4_000_000,
        )
    screen.blit(layer, (int(sx) - center, int(sy) - center), special_flags=pygame.BLEND_RGBA_ADD)


# ----------------------------
# Pixel ring helper (retained for a future ring redesign)
# ----------------------------
# Pass 8: orbital rings are intentionally disabled. The procedural ring data
# fields remain intact so this is reversible without changing system seeds,
# orbit generation, saves, or planet identities.
ORBITAL_RINGS_ENABLED = False
SPACE_COMBAT_ENABLED = False  # Deferred until the recovery loop is proven.

def _mix(a, b, t):
    return (int(a[0] + (b[0]-a[0])*t), int(a[1] + (b[1]-a[1])*t), int(a[2] + (b[2]-a[2])*t))

def gen_pixel_ring_points(seed: int, base_col: tuple, accent_col: tuple, alpha: int, inner: float, outer: float, count: int):
    """Return (back_points, front_points). Points are tuples: (x_norm, y_norm, size, r, g, b, a).

    Colored ring layers:
      - We derive 3–5 radial "bands" between inner..outer.
      - Each band blends between a pale ice/sand base and the planet's accent tint.
    """
    rng = random.Random(int(seed) & 0xFFFFFFFF)
    back = []
    front = []
    # Keep alpha sensible for tiny 1px dots
    a0 = max(22, min(200, int(alpha)))

    # Build band palette (disc-like rings with layered coloration)
    # Start with a bright icy base, then blend toward planet tint.
    ice = _mix((235, 235, 245), base_col, 0.18)
    sand = _mix((220, 210, 190), base_col, 0.25)
    tint = _mix(accent_col, (255, 255, 255), 0.20)
    bands = [ice, sand, _mix(sand, tint, 0.45), _mix(ice, tint, 0.55)]
    if rng.random() < 0.55:
        bands.append(_mix(tint, (255, 255, 255), 0.35))

    span = max(1e-6, (outer - inner))

    for _ in range(int(count)):
        ang = rng.random() * math.tau
        # sqrt for uniform area distribution (fills the disc)
        rad = inner + span * (rng.random() ** 0.5)
        x = math.cos(ang) * rad
        y = math.sin(ang) * rad

        # Per-dot micro jitter to break perfect circle
        x += (rng.random() - 0.5) * 0.03
        y += (rng.random() - 0.5) * 0.03

        # Size (1..2 px) and alpha variance
        size = 1 if rng.random() < 0.80 else 2
        a = int(a0 * (0.62 + 0.60 * rng.random()))

        # Choose band color by normalized radius
        t = (rad - inner) / span
        bi = int(t * (len(bands) - 1))
        bi = 0 if bi < 0 else (len(bands) - 1 if bi >= len(bands) else bi)
        band = bands[bi]

        # Add subtle per-dot drift so it doesn't look like perfectly uniform stripes
        drift = rng.uniform(-14, 16)
        r = max(0, min(255, int(band[0] + drift)))
        g = max(0, min(255, int(band[1] + drift * 0.85)))
        b = max(0, min(255, int(band[2] + drift * 0.70)))
        pt = (x, y, size, r, g, b, a)

        # Back/front split using y sign (works with later tilt)
        if y < 0.0:
            back.append(pt)
        else:
            front.append(pt)
    return back, front

def draw_pixel_rings(screen, cx: float, cy: float, rpx: int, p, phase: str, tsec: float):
    """Fast ring renderer: draws cached 1–2px specs; phase="back" or "front"."""
    if (not getattr(p, "ringed", False)) or rpx < 8:
        return

    # LOD: skip more points when small on-screen
    if rpx < 16:
        skip = 8
    elif rpx < 28:
        skip = 4
    elif rpx < 45:
        skip = 2
    else:
        skip = 1

    tilt = max(0.10, float(getattr(p, "ring_tilt", 0.55)))
    # Draw specs (phase-select)
    if phase == "back":
        pts = getattr(p, "ring_pts_back", None) or []
    else:
        pts = getattr(p, "ring_pts_front", None) or []
    ang = float(getattr(p, 'ring_rot_phase', 0.0)) + tsec * float(getattr(p, 'ring_rot_speed', 0.0))
    ca = math.cos(ang)
    sa = math.sin(ang)
    for i in range(0, len(pts), skip):
        x, y, size, r, g, b, a = pts[i]
        # Rotate ring orientation (disc can be angled per planet)
        xr = x * ca - y * sa
        yr = x * sa + y * ca
        px = int(cx + xr * rpx)
        py = int(cy + yr * rpx * tilt)
        screen.fill((r, g, b, a), (px, py, size, size))


def draw_solar_erosion(screen, sx: float, sy: float, rpx: int, planet, light_cam, tsec: float, star_col, exposure: float):
    """Pull tiny sampled planet pixels toward the sun-facing direction.

    The effect is deterministic and allocation-light: each world owns a fixed
    set of particle specifications, while positions are derived from time. It
    borrows the visual language of the black-hole devour effect without
    creating a second unbounded particle list.
    """
    specs = getattr(planet, "solar_erosion_pts", ())
    if not specs or rpx < 6:
        return

    dx = float(light_cam[0])
    dy = float(-light_cam[1])
    mag = math.hypot(dx, dy)
    if mag <= 1e-5:
        dx, dy, mag = -1.0, 0.0, 1.0
    dx /= mag
    dy /= mag
    px, py = -dy, dx
    exposure = clamp(float(exposure), 0.0, 1.0)
    count = min(len(specs), int(20 + exposure * 48))

    surface = getattr(planet, "_last_orbital_surface", None)
    sw = sh = 0
    if surface is not None:
        try:
            sw, sh = surface.get_size()
        except Exception:
            surface = None

    for phase, lateral, edge_depth, speed, size, heat_mix in specs[:count]:
        travel = (phase + tsec * speed) % 1.0
        edge_r = rpx * (0.78 + edge_depth * 0.18)
        source_x = sx + dx * edge_r + px * lateral * rpx * 0.62
        source_y = sy + dy * edge_r + py * lateral * rpx * 0.62
        pull_len = rpx * (0.10 + travel * (1.55 + exposure * 2.85))
        curl = math.sin((travel + phase) * math.tau * 1.7) * rpx * 0.07 * (1.0 - travel)
        x = source_x + dx * pull_len + px * curl
        y = source_y + dy * pull_len + py * curl
        if x < -3 or x > screen.get_width() + 3 or y < -3 or y > screen.get_height() + 3:
            continue

        base_col = getattr(planet, "col", (170, 180, 190))
        if surface is not None and sw > 0 and sh > 0:
            sample_x = int(clamp((source_x - (sx - rpx)) / max(1.0, rpx * 2.0) * sw, 0, sw - 1))
            sample_y = int(clamp((source_y - (sy - rpx)) / max(1.0, rpx * 2.0) * sh, 0, sh - 1))
            try:
                sampled = surface.get_at((sample_x, sample_y))
                base_col = (int(sampled[0]), int(sampled[1]), int(sampled[2]))
            except Exception:
                pass

        heated = _mix(base_col, star_col, clamp(heat_mix + travel * 0.45, 0.0, 0.88))
        fade = clamp(1.0 - travel * 0.78, 0.18, 1.0)
        col = tuple(max(0, min(255, int(channel * (0.55 + fade * 0.45)))) for channel in heated)
        draw_size = 1 if rpx < 34 else int(size)
        screen.fill(col, (int(x), int(y), draw_size, draw_size))
        if exposure > 0.62 and int(phase * 1000) % 3 == 0:
            tail_x = int(x - dx * max(2.0, rpx * 0.035))
            tail_y = int(y - dy * max(2.0, rpx * 0.035))
            screen.fill(tuple(max(0, int(c * 0.62)) for c in col), (tail_x, tail_y, 1, 1))

        # A few single-pixel edge gaps sell gradual deterioration without
        # changing collision geometry or obscuring the planet's material.
        if travel < 0.085 and exposure > 0.38 and rpx >= 12:
            screen.fill((3, 4, 7), (int(source_x), int(source_y), 1, 1))


@dataclass
class PlanetBody:
    orbit_r: float
    orbit_speed: float
    phase: float
    radius: float
    col: tuple

    # Stable orbital world identity/materials.
    style: str = "oceanic"
    surface_seed: int = 0
    texture_phase: float = 0.0
    texture_speed: float = 0.0
    cloud_phase: float = 0.0
    cloud_speed: float = 0.0
    cloud_density: float = 0.0
    emission_strength: float = 1.0
    orbital_cache: dict = field(default_factory=OrderedDict, repr=False)
    orbital_scaled_cache: dict = field(default_factory=OrderedDict, repr=False)
    orbital_atmo_cache: dict = field(default_factory=OrderedDict, repr=False)

    # Deterministic sunward pixel erosion (space-view only)
    solar_erosion_seed: int = 0
    solar_erosion_pts: tuple = field(default_factory=tuple, repr=False)
    _last_orbital_surface: object = field(default=None, repr=False)

    # Atmosphere / halo (space-view only)
    atmo_col: tuple = (180, 210, 255)
    atmo_alpha: int = 55           # 0..255
    atmo_thickness: float = 1.18   # halo radius multiplier

    # Rings
    ringed: bool = False
    ring_tilt: float = 0.0
    ring_width: float = 0.0
    ring_alpha: int = 0

    

    # Ring orientation randomness + slow spin (space-view only)
    ring_rot_phase: float = 0.0
    ring_rot_speed: float = 0.0
# Cached pixel-ring points (normalized to planet radius); generated once per planet/system
    ring_pts_back: list = field(default_factory=list)
    ring_pts_front: list = field(default_factory=list)
    ring_col: tuple = (220, 220, 220)
    ring_seed: int = 0

    # Pass 15 mission identity. Assigned by MissionState after generation.
    mission_role: str = "survey"
    signal_label: str = "LOW-VALUE SURVEY"
    hazard_family: str = "UNKNOWN"
    is_fragment_target: bool = False

    # Destruction state (missile impact)
    destroyed: bool = False
    nebula_parts: list = field(default_factory=list)  # list[NebulaParticle]




@dataclass
class SolarFlarePixel:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    col: tuple


@dataclass
class SolarBelt:
    orbit_r: float
    width: float
    tilt_y: float
    tilt_z: float
    phase: float
    speed: float
    col: tuple
    points: list = field(default_factory=list, repr=False)


class SolarSystem:
    """Readable procedural system: one star, one varied landable world."""
    def __init__(self, seed=1337):
        self.seed = seed
        self.star_col = (255, 220, 170)
        self.star_radius = 1200.0
        self.star_pos = (0.0, 0.0, 24000.0)
        self.star_class = "scarlet dwarf"
        self.star_surface_seed = int(seed) ^ 0x57A2
        self.star_rotation_speed = 0.018
        self.planets = []
        self.solar_belts = []
        self.solar_flares = []  # persistent pixel-spray flare particles
        self._render_layers = {}
        self._star_visual_seed = None
        self._star_ray_defs = ()
        self._star_spot_defs = ()
        self._star_prom_defs = ()
        self._last_star_draw_t = None
        self._flare_spawn_acc = 0.0
        self._orbit_unit = tuple(
            (math.cos((i / 48.0) * math.tau), math.sin((i / 48.0) * math.tau))
            for i in range(49)
        )
        self.generate(seed)
        # Supernova timer/state (controlled by main loop)
        self.supernova_t0 = None
        self.supernova_triggered = False
        self.supernova_time = 0.0
        self.post_supernova = False
        self.supernova_parts = []
        # Black hole state (forms after post-supernova countdown)
        self.blackhole_active = False
        self.blackhole_t0 = None

    def generate(self, seed=None):
        if seed is None:
            seed = random.randrange(1_000_000_000)
        self.seed = int(seed)
        rng = random.Random(self.seed)

        # REDSHIFT UNIVERSE RULE: all suns are red (fixed hue band).
        h = rng.uniform(0.0, 0.03)  # red hue band
        s = rng.uniform(0.55, 0.88)
        v = rng.uniform(0.78, 1.00)
        self.star_col = hsv_to_rgb(h, s, v)
        # Distinct stellar classes and more readable stellar scale.
        self.star_radius = rng.uniform(1500.0, 2800.0)
        class_roll = rng.random()
        if class_roll < 0.42:
            self.star_class = "scarlet dwarf"
        elif class_roll < 0.76:
            self.star_class = "ember sun"
        elif class_roll < 0.94:
            self.star_class = "crimson giant"
        else:
            self.star_class = "fractured remnant"
        self.star_surface_seed = self.seed ^ 0x57A2C91
        self.star_rotation_speed = rng.uniform(0.010, 0.028)
        self._rebuild_star_visual_defs()
        self._last_star_draw_t = None
        self._flare_spawn_acc = 0.0

        self.planets = []
        self.solar_belts = []
        self.solar_flares = []
        # Pass 20 direction lock: one world per system. All twelve surface
        # styles remain in the deterministic shuffled variant pool, so the
        # variety appears across consecutive systems instead of as clutter.
        n = 1
        base_r = max(self.star_radius * 5.8, rng.uniform(14500.0, 19000.0))
        last_orbit = 0.0
        # Ring presence remains a world variation instead of being forced on
        # the sole planet in every system.
        ring_indices = set()
        ring_variant_rng = random.Random(self.seed ^ 0x7116B4D)
        # Material identity uses its own RNG so adding graphics never changes
        # existing orbit positions, planet sizes, ring membership, or timing.
        style_rng = random.Random(self.seed ^ 0x50A7B17)
        style_order = list(ORBITAL_PLANET_STYLES)
        style_rng.shuffle(style_order)
        for i in range(n):
            if i == 0:
                orbit_r = base_r
            else:
                gap = rng.uniform(9500.0, 15500.0) * (1.0 + i * 0.025)
                orbit_r = last_orbit + gap
            last_orbit = orbit_r
            orbit_speed = rng.uniform(0.0012, 0.0060) / max(1.0, (orbit_r / 6000.0))
            phase = rng.uniform(0.0, math.tau)

            # Preserve the original random stream exactly. These legacy values
            # still consume the same draws as Pass 6, while the new renderer
            # uses the separate material RNG below.
            legacy_hue = (rng.random() + (i * 0.11)) % 1.0
            legacy_sat = rng.uniform(0.62, 0.96)
            legacy_val = rng.uniform(0.68, 0.96)
            _legacy_col = hsv_to_rgb(legacy_hue, legacy_sat, legacy_val)

            radius = rng.uniform(52.0, 136.0)

            legacy_atmo_h = (legacy_hue + rng.uniform(-0.07, 0.07)) % 1.0
            legacy_atmo_sat = rng.uniform(0.20, 0.55)
            _legacy_atmo_col = hsv_to_rgb(legacy_atmo_h, legacy_atmo_sat, 1.0)
            legacy_atmo_alpha = rng.randint(32, 72)
            legacy_atmo_thickness = rng.uniform(1.18, 1.42)

            # Stable world class and readable orbital palette.
            style = style_order[i % len(style_order)]
            style_palette = ORBITAL_STYLE_PALETTES[style]
            material_rng = random.Random((self.seed * 104729 + i * 7919) & 0xFFFFFFFF)
            palette_variation = material_rng.uniform(-0.08, 0.10)
            col = _mix(style_palette["mid"], style_palette["high"], clamp(0.32 + palette_variation, 0.18, 0.52))

            # Biome-derived atmosphere, remapped from the old values without
            # changing the original procedural system structure.
            atmo_col = style_palette["atmo"]
            atmo_alpha = int(30 + ((legacy_atmo_alpha - 32) / 40.0) * 28)
            atmo_thickness = 1.08 + ((legacy_atmo_thickness - 1.18) / 0.24) * 0.09
            if style in ("storm", "jungle", "fungal", "oceanic"):
                atmo_alpha += 10
                atmo_thickness += 0.035

            ringed = (i in ring_indices) or (ring_variant_rng.random() < 0.36)
            ring_tilt = rng.uniform(-0.85, 0.85)
            ring_width = rng.uniform(0.55, 1.25)
            ring_alpha = rng.randint(80, 155)

            pb = PlanetBody(
                orbit_r=orbit_r,
                orbit_speed=orbit_speed,
                phase=phase,
                radius=radius,
                col=col,
                style=style,
                surface_seed=(self.seed * 104729 + i * 7919) & 0xFFFFFFFF,
                texture_phase=material_rng.uniform(0.0, math.tau),
                texture_speed=material_rng.uniform(-0.018, 0.018),
                cloud_phase=material_rng.uniform(0.0, math.tau),
                cloud_speed=material_rng.uniform(-0.030, 0.030),
                cloud_density={
                    "storm": 0.96, "oceanic": 0.72, "jungle": 0.64,
                    "fungal": 0.54, "ice": 0.42, "desert": 0.22,
                    "rust": 0.18, "salt": 0.20, "volcanic": 0.14,
                    "crystal": 0.10, "abyss": 0.12, "roseglass": 0.08,
                }.get(style, 0.20),
                emission_strength={
                    "volcanic": 1.0, "crystal": 0.92, "abyss": 0.88,
                    "roseglass": 0.76, "fungal": 0.42,
                }.get(style, 0.0),
                atmo_col=atmo_col,
                atmo_alpha=atmo_alpha,
                atmo_thickness=atmo_thickness,
                ringed=ringed,
                ring_tilt=ring_tilt,
                ring_width=ring_width,
                ring_alpha=ring_alpha,
                ring_rot_phase=rng.uniform(0.0, math.tau),
                ring_rot_speed=rng.uniform(-0.12, 0.12) * 0.12
            )
            erosion_rng = random.Random(pb.surface_seed ^ 0xE20510)
            pb.solar_erosion_seed = pb.surface_seed ^ 0xE20510
            pb.solar_erosion_pts = tuple(
                (
                    erosion_rng.random(),
                    erosion_rng.uniform(-1.0, 1.0),
                    erosion_rng.random(),
                    erosion_rng.uniform(0.12, 0.32),
                    1 if erosion_rng.random() < 0.68 else 2,
                    erosion_rng.uniform(0.12, 0.42),
                )
                for _ in range(72)
            )
            if ringed and ORBITAL_RINGS_ENABLED:
                # Build deterministic pixel-ring cache only when the ring renderer is enabled
                pb.ring_seed = (self.seed * 1315423911 + i * 2654435761) & 0xFFFFFFFF
                # Base ring color: sandy/icy mix leaning slightly toward planet tint
                pb.ring_col = _mix((210, 210, 210), col, 0.18)
                inner = 1.18
                outer = max(inner + 0.55, float(ring_width) + 0.85)
                # Count tuned for performance; LOD skipping reduces work when far away
                count = 980 + int(420 * (outer - inner))
                pb.ring_pts_back, pb.ring_pts_front = gen_pixel_ring_points(
                    pb.ring_seed, pb.ring_col, col, ring_alpha, inner, outer, count
                )
            self.planets.append(pb)

        # Place sparse asteroid/dust belts only inside roomy radial gaps.
        belt_rng = random.Random(self.seed ^ 0xA57E10D)
        candidate_edges = [self.star_radius * 3.5] + [p.orbit_r for p in self.planets]
        for gap_i in range(len(candidate_edges) - 1):
            inner = candidate_edges[gap_i]
            outer = candidate_edges[gap_i + 1]
            gap = outer - inner
            if gap < 11800.0 or belt_rng.random() > 0.48:
                continue
            orbit_r = inner + gap * belt_rng.uniform(0.42, 0.58)
            width = min(2600.0, gap * 0.16)
            pts = []
            count = 520 + belt_rng.randint(0, 320)
            for _ in range(count):
                ang = belt_rng.random() * math.tau
                radial = belt_rng.uniform(-width, width) * (belt_rng.random() ** 0.72)
                vertical = belt_rng.uniform(-1.0, 1.0) * width * 0.08
                size = 1 if belt_rng.random() < 0.87 else 2
                alpha = belt_rng.randint(34, 108)
                pts.append((ang, radial, vertical, size, alpha))
            base_col = _mix(self.star_col, (116, 106, 128), 0.70)
            self.solar_belts.append(SolarBelt(
                orbit_r=orbit_r, width=width,
                tilt_y=belt_rng.uniform(0.08, 0.20),
                tilt_z=belt_rng.uniform(0.03, 0.11),
                phase=belt_rng.uniform(0.0, math.tau),
                speed=belt_rng.uniform(-0.00065, 0.00065),
                col=base_col, points=pts
            ))
            break  # Pass 15: never more than one belt per system.

    def _alpha_layer(self, name, w, h):
        key = (name, int(w), int(h))
        layer = self._render_layers.get(key)
        if layer is None:
            layer = pygame.Surface((w, h), pygame.SRCALPHA)
            self._render_layers[key] = layer
            # Remove stale sizes of the same layer after display changes.
            for old_key in list(self._render_layers):
                if old_key != key and old_key[0] == name:
                    self._render_layers.pop(old_key, None)
        else:
            layer.fill((0, 0, 0, 0))
        return layer

    def _rebuild_star_visual_defs(self):
        if self._star_visual_seed == self.star_surface_seed:
            return
        self._star_visual_seed = self.star_surface_seed
        ray_rng = random.Random(self.star_surface_seed)
        self._star_ray_defs = tuple(
            (
                (i / 34.0) * math.tau + ray_rng.uniform(-0.045, 0.045),
                ray_rng.uniform(1.02, 1.14),
                ray_rng.uniform(1.65, 2.65),
                ray_rng.randint(14, 42),
            )
            for i in range(34)
        )
        spot_rng = random.Random(self.star_surface_seed)
        self._star_spot_defs = tuple(
            (
                spot_rng.uniform(0.0, math.tau),
                0.55 + spot_rng.random() * 0.7,
                (spot_rng.random() ** 0.72) * 0.82,
                spot_rng.uniform(0.025, 0.10),
                spot_rng.uniform(0.08, 0.28),
                (i % 5 == 0),
            )
            for i in range(42)
        )
        prom_rng = random.Random(self.star_surface_seed ^ 0xA91F)
        self._star_prom_defs = tuple(
            (
                prom_rng.uniform(0.0, math.tau),
                1.0 if i % 2 == 0 else -1.0,
                prom_rng.uniform(0.28, 0.58),
                prom_rng.uniform(0.25, 0.58),
            )
            for i in range(5)
        )

    def planet_world_pos(self, i: int, tsec: float):
        p = self.planets[i]
        a = p.phase + tsec * p.orbit_speed
        x = self.star_pos[0] + math.cos(a) * p.orbit_r
        y = self.star_pos[1] + math.sin(a) * p.orbit_r * 0.12
        z = self.star_pos[2] + math.sin(a) * p.orbit_r * 0.06
        return (x, y, z)

    
    def trigger_supernova(self, now_t: float, instant: bool = False):
        if self.supernova_triggered or self.post_supernova:
            return
        self.supernova_triggered = True
        self.supernova_time = float(now_t)
        # when instant (missile hit), skip ramp-up a little
        self.supernova_t0 = float(now_t) - (1.0 if instant else 0.0)
        log("SYSTEM: Supernova triggered.")

    def destroy_planet(self, planet_i: int, world_pos: tuple, rng_seed: int = 0):
        if planet_i < 0 or planet_i >= len(self.planets):
            return
        p = self.planets[planet_i]
        if getattr(p, "destroyed", False):
            return
        p.destroyed = True
        rr = random.Random((self.seed * 99991 + planet_i * 7919 + int(rng_seed)) & 0xFFFFFFFF)
        # Build a pixel nebula cloud in world space around the planet's current position.
        parts = []
        base = _mix(p.col, (255, 70, 60), 0.22)
        n = 1400
        cloud_r = max(6.0, float(p.radius) * 5.5)
        for _ in range(n):
            ang = rr.random() * math.tau
            u = rr.random() * 2.0 - 1.0
            r = cloud_r * (rr.random() ** 0.55)
            sx = math.cos(ang) * r
            sz = math.sin(ang) * r
            sy = u * r * 0.45
            vx = sx * rr.uniform(0.35, 1.10)
            vy = sy * rr.uniform(0.35, 1.10)
            vz = sz * rr.uniform(0.35, 1.10)
            a = rr.randint(120, 220)
            col = (
                clamp(int(base[0] + rr.uniform(-40, 40)), 0, 255),
                clamp(int(base[1] + rr.uniform(-35, 35)), 0, 255),
                clamp(int(base[2] + rr.uniform(-35, 35)), 0, 255),
                a
            )
            life = rr.uniform(4.0, 10.0)
            parts.append(NebulaParticle(vec3_add(world_pos, (sx, sy, sz)), (vx, vy, vz), life, col))
        p.nebula_parts = parts
        log(f"SYSTEM: Planet {planet_i} destroyed (nebula spawned).")

    def update(self, dt: float, tsec: float):
        # Update nebula particles for destroyed planets
        for p in self.planets:
            parts = getattr(p, "nebula_parts", None)
            if not parts:
                continue
            nxt = []
            for q in parts:
                q.life -= dt
                if q.life <= 0.0:
                    continue
                q.pos = vec3_add(q.pos, vec3_mul(q.vel, dt))
                q.vel = vec3_mul(q.vel, 0.992)
                nxt.append(q)
            p.nebula_parts = nxt

        # Mark system as post-supernova once animation is complete (blocks landings)
        if self.supernova_triggered and (not self.post_supernova):
            elapsed = (tsec - self.supernova_t0) if (self.supernova_t0 is not None) else 0.0
            if elapsed >= 7.5:
                self.post_supernova = True


        # Black hole devour phase: after the brown dwarf, planets spiral inward and get consumed.
        if getattr(self, 'blackhole_active', False):
            # Use a gentle exponential decay of orbit radius for a slow, inevitable inward drift.
            # This is intentionally low-cost (no allocations) to avoid performance spikes.
            pull = clamp(0.012 + 0.028 * min(1.0, max(0.0, tsec - (self.blackhole_t0 or tsec)) / 20.0), 0.012, 0.055)
            for i, p in enumerate(self.planets):
                if getattr(p, 'destroyed', False):
                    continue
                p.orbit_r *= (1.0 - pull * dt)
                # As the orbit collapses, increase orbit speed slightly to suggest a tightening spiral.
                p.orbit_speed *= (1.0 + 0.10 * pull * dt)
                if p.orbit_r <= 900.0:
                    # Planet is close enough to be considered consumed.
                    wp = self.planet_world_pos(i, tsec)
                    self.destroy_planet(i, wp, rng_seed=int(tsec * 1000.0))

    def draw_star(self, screen, w, h, ship_pos, yaw, pitch, roll, tsec: float):
        visible, (sx, sy), rpx = project_sphere(
            w, h, ship_pos, yaw, pitch, roll, self.star_pos,
            k_px=self.star_radius * 320.0, min_z=10.0
        )
        if not visible or getattr(self, 'blackhole_active', False):
            return

        self_star_col = self.star_col
        if self.supernova_triggered:
            t0 = self.supernova_t0 if (self.supernova_t0 is not None) else tsec
            e = max(0.0, tsec - t0)
            if e < 3.0:
                tt = smoothstep(e / 3.0)
                rpx = int(rpx * (1.0 + 2.2 * tt))
                col = _mix(self.star_col, (255, 240, 220), 0.35 + 0.45 * tt)
            else:
                tt = smoothstep((e - 3.0) / 4.5)
                rpx = int(max(2, rpx * lerp(3.2, 0.55, tt)))
                col = _mix((255, 240, 220), (165, 120, 80), tt)
            self_star_col = (int(col[0]), int(col[1]), int(col[2]))

        self._rebuild_star_visual_defs()
        if self._last_star_draw_t is None:
            dtp = 1.0 / 60.0
        else:
            dtp = clamp(tsec - self._last_star_draw_t, 0.0, 0.10)
        self._last_star_draw_t = tsec

        # The old renderer allocated two 1920x1080 alpha surfaces for every
        # visible star frame. All stellar art now lives in a reusable local
        # surface bounded to the star's actual screen footprint.
        extent = max(8, int(math.ceil(rpx * 2.78)) + 4)
        local_size = extent * 2 + 1
        emission = self._alpha_layer('star_emission', local_size, local_size)
        halo = self._alpha_layer('star_halo', local_size, local_size)
        center = extent
        pulse = 0.86 + 0.14 * math.sin(tsec * 1.35)

        for ang, inner_mul, outer_mul, alpha in self._star_ray_defs:
            inner = rpx * inner_mul
            outer = rpx * outer_mul * pulse
            x0 = center + math.cos(ang) * inner
            y0 = center + math.sin(ang) * inner
            x1 = center + math.cos(ang) * outer
            y1 = center + math.sin(ang) * outer
            pygame.draw.aaline(emission, (*self_star_col, alpha), (x0, y0), (x1, y1))

        for band in range(22, 0, -1):
            u = band / 22.0
            radius = max(2, int(rpx * (1.02 + u * 1.38)))
            alpha = int(4 + (1.0 - u) * 42)
            pygame.draw.circle(halo, (*self_star_col, alpha), (center, center), radius)

        pygame.draw.circle(emission, self_star_col, (center, center), max(2, rpx))
        rot = tsec * self.star_rotation_speed
        for base_ang, rot_mul, radial_mul, size_mul, light_mix, dark in self._star_spot_defs:
            a0 = base_ang + rot * rot_mul
            rr = rpx * radial_mul
            px = center + math.cos(a0) * rr
            py = center + math.sin(a0) * rr * 0.72
            sr = max(1, int(rpx * size_mul))
            if dark:
                scol = _mix(self_star_col, (58, 8, 16), 0.66)
            else:
                scol = _mix(self_star_col, (255, 232, 186), light_mix)
            pygame.draw.circle(emission, scol, (int(px), int(py)), sr)
        for band in range(4):
            rr = max(2, int(rpx * (0.94 - band * 0.08)))
            col = _mix(self_star_col, (255, 232, 210), 0.05 + band * 0.05)
            pygame.draw.circle(emission, col, (center, center), rr, 1)

        prom_col = (*_mix(self_star_col, (255, 92, 72), 0.42), 90)
        for base_ang, direction, width, lift_mul in self._star_prom_defs:
            moving_base = base_ang + tsec * 0.055 * direction
            points = []
            for step in range(18):
                u = step / 17.0
                ang = moving_base + (u - 0.5) * width
                rr = rpx * 1.01 + math.sin(u * math.pi) * rpx * lift_mul
                points.append((center + math.cos(ang) * rr, center + math.sin(ang) * rr))
            pygame.draw.aalines(emission, prom_col, False, points)

        dest = (int(sx) - center, int(sy) - center)
        screen.blit(halo, dest)
        screen.blit(emission, dest, special_flags=pygame.BLEND_RGBA_ADD)

        # Spawn flare particles at a fixed 20 Hz instead of every render frame.
        # This removes frame-rate-dependent particle counts and keeps the same
        # visual activity with a bounded list.
        self._flare_spawn_acc += dtp
        spawn_steps = min(3, int(self._flare_spawn_acc / 0.05))
        if spawn_steps:
            self._flare_spawn_acc -= spawn_steps * 0.05
            base = _mix(self_star_col, (255, 60, 60), 0.22)
            for step in range(spawn_steps):
                rrng = random.Random((self.seed ^ 0x51F1A) + int((tsec - step * 0.05) * 20.0))
                spawn = 2 if rpx > 12 else 1
                for _ in range(spawn):
                    ang = rrng.random() * math.tau
                    speed = rrng.uniform(12.0, 30.0) * (0.75 + 0.55 * min(1.0, rpx / 40.0))
                    curl = rrng.uniform(-0.6, 0.6)
                    self.solar_flares.append(SolarFlarePixel(
                        x=sx + math.cos(ang) * rpx, y=sy + math.sin(ang) * rpx,
                        vx=math.cos(ang + curl) * speed, vy=math.sin(ang + curl) * speed,
                        life=rrng.uniform(1.6, 3.4), col=(base[0], base[1], base[2], 120)
                    ))

        next_flares = []
        for fp in self.solar_flares:
            fp.life -= dtp
            if fp.life <= 0.0:
                continue
            fp.x += fp.vx * dtp
            fp.y += fp.vy * dtp
            alpha = int(fp.col[3] * clamp(fp.life / 3.4, 0.0, 1.0))
            size = 2 if rpx > 24 else 1
            screen.fill((fp.col[0], fp.col[1], fp.col[2], alpha), (int(fp.x), int(fp.y), size, size))
            next_flares.append(fp)
        self.solar_flares = next_flares[-320:]

    def draw_solar_structures(self, screen, w, h, ship_pos, yaw, pitch, roll, tsec: float):
        if not self.solar_belts:
            return
        cx, cy = w * 0.5, h * 0.5
        f = (w * 0.5) / math.tan(math.radians(86.0) * 0.5)
        layer = self._alpha_layer('solar_belts', w, h)
        inv_orientation = quat_conjugate(yaw) if is_quaternion(yaw) else None
        center_dist = vec3_len(vec3_sub(self.star_pos, ship_pos))
        stride = 4 if center_dist > 100000.0 else (2 if center_dist > 52000.0 else 1)
        single_pixels = []
        for belt in self.solar_belts:
            spin = belt.phase + tsec * belt.speed
            for ang0, radial, vertical, size, alpha in belt.points[::stride]:
                ang = ang0 + spin
                rr = belt.orbit_r + radial
                rel = (
                    self.star_pos[0] + math.cos(ang) * rr - ship_pos[0],
                    self.star_pos[1] + math.sin(ang) * rr * belt.tilt_y + vertical - ship_pos[1],
                    self.star_pos[2] + math.sin(ang) * rr * belt.tilt_z - ship_pos[2],
                )
                if inv_orientation is not None:
                    cam = quat_rotate_normalized(inv_orientation, rel)
                else:
                    cam = apply_inv_ypr(rel, yaw, pitch, roll)
                if cam[2] <= 10.0:
                    continue
                x = cam[0] * f / cam[2] + cx
                y = cam[1] * f / cam[2] + cy
                ix, iy = int(x), int(y)
                if ix < -3 or ix > w + 3 or iy < -3 or iy > h + 3:
                    continue
                fade = clamp(90000.0 / cam[2], 0.18, 1.0)
                col = (*belt.col, int(alpha * fade))
                if size <= 1 and 0 <= ix < w and 0 <= iy < h:
                    single_pixels.append((ix, iy, col))
                else:
                    pygame.draw.circle(layer, col, (ix, iy), size)
        if single_pixels:
            pixels = pygame.PixelArray(layer)
            for px, py, col in single_pixels:
                pixels[px, py] = col
            pixels.close()
        screen.blit(layer, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def draw_planets(self, screen, w, h, ship_pos, yaw, pitch, roll, tsec: float, mission_state=None, scanner_upgrade: int = 0):
        self.draw_solar_structures(screen, w, h, ship_pos, yaw, pitch, roll, tsec)

        path_layer = self._alpha_layer('orbit_paths', w, h)
        cx, cy = w * 0.5, h * 0.5
        f = (w * 0.5) / math.tan(math.radians(86.0) * 0.5)
        inv_orientation = quat_conjugate(yaw) if is_quaternion(yaw) else None

        # Planet debris / pixel nebulae behind everything else.
        for planet in self.planets:
            parts = getattr(planet, 'nebula_parts', None)
            if not parts:
                continue
            for particle in parts[::3]:
                rel = vec3_sub(particle.pos, ship_pos)
                cam = quat_rotate_normalized(inv_orientation, rel) if inv_orientation is not None else apply_inv_ypr(rel, yaw, pitch, roll)
                if cam[2] <= 10.0:
                    continue
                x = cam[0] * f / cam[2] + cx
                y = cam[1] * f / cam[2] + cy
                if x < -2 or x > w + 2 or y < -2 or y > h + 2:
                    continue
                size = 2 if cam[2] < 22000 else 1
                screen.fill(particle.col, (int(x), int(y), size, size))

        # Orbit paths are informational, not gameplay collision geometry. A
        # 48-segment unit circle preserves their look while removing hundreds
        # of per-frame trigonometric calls and a third of their transforms.
        center_dist = vec3_len(vec3_sub(self.star_pos, ship_pos))
        drew_paths = False
        if center_dist < 190000.0:
            for planet in self.planets:
                if planet.orbit_r < 2000 or getattr(planet, 'destroyed', False):
                    continue
                pts2d = []
                for ux, uy in self._orbit_unit:
                    rel = (
                        self.star_pos[0] + ux * planet.orbit_r - ship_pos[0],
                        self.star_pos[1] + uy * planet.orbit_r * 0.12 - ship_pos[1],
                        self.star_pos[2] + uy * planet.orbit_r * 0.06 - ship_pos[2],
                    )
                    cam = quat_rotate_normalized(inv_orientation, rel) if inv_orientation is not None else apply_inv_ypr(rel, yaw, pitch, roll)
                    if cam[2] <= 10.0:
                        continue
                    pts2d.append((cx + cam[0] / cam[2] * (w * 0.55), cy - cam[1] / cam[2] * (h * 0.55)))
                if len(pts2d) >= 6:
                    col = _mix(planet.col, (255, 255, 255), 0.35)
                    pygame.draw.aalines(path_layer, (*col, 26), False, pts2d)
                    drew_paths = True
        if drew_paths:
            screen.blit(path_layer, (0, 0))

        # Transform each planet only once. The previous path transformed a
        # planet for depth sorting and then repeated the same camera transform
        # inside project_sphere().
        items = []
        for index, planet in enumerate(self.planets):
            if getattr(planet, 'destroyed', False):
                continue
            pos = self.planet_world_pos(index, tsec)
            rel = vec3_sub(pos, ship_pos)
            cam = quat_rotate_normalized(inv_orientation, rel) if inv_orientation is not None else apply_inv_ypr(rel, yaw, pitch, roll)
            items.append((cam[2], index, pos, cam))
        items.sort(reverse=True)

        max_radius = min(w, h) * 0.75
        for z, index, pos, cam in items:
            if z <= 10.0:
                continue
            planet = self.planets[index]
            sx = cam[0] * f / z + cx
            sy = cam[1] * f / z + cy
            rpx = int(clamp((planet.radius * 6200.0) / z, 4, max_radius))
            if sx < -rpx or sx > w + rpx or sy < -rpx or sy > h + rpx:
                continue

            if ORBITAL_RINGS_ENABLED and planet.ringed and rpx >= 8:
                draw_pixel_rings(screen, sx, sy, rpx, planet, 'back', tsec)

            light_world = vec3_sub(self.star_pos, pos)
            light_cam = vec3_norm(
                quat_rotate_normalized(inv_orientation, light_world)
                if inv_orientation is not None else apply_inv_ypr(light_world, yaw, pitch, roll)
            )
            draw_orbital_atmosphere(screen, sx, sy, rpx, planet, light_cam)
            surface = render_orbital_planet(planet, max(4, rpx * 2), light_cam, tsec)
            planet._last_orbital_surface = surface
            screen.blit(surface, surface.get_rect(center=(int(sx), int(sy))))

            collapse_pressure = 0.0
            if mission_state is not None:
                remaining = float(getattr(mission_state, "collapse_remaining", COLLAPSE_DURATION))
                collapse_pressure = 1.0 - clamp(remaining / max(0.001, COLLAPSE_DURATION), 0.0, 1.0)
            stellar_ratio = self.star_radius / max(1.0, float(planet.orbit_r))
            proximity = clamp((stellar_ratio - 0.07) / 0.11, 0.0, 1.0)
            erosion_exposure = clamp(0.22 + proximity * 0.55 + collapse_pressure * 0.38, 0.22, 1.0)
            draw_solar_erosion(
                screen, sx, sy, rpx, planet, light_cam, tsec, self.star_col, erosion_exposure
            )

            # The fragment world is the one dominant navigation signal. Optional
            # worlds remain unmarked until later scanner upgrades are implemented.
            if mission_state is not None and index == getattr(mission_state, "target_planet_index", -1):
                pulse = 0.5 + 0.5 * math.sin(tsec * 3.2)
                mark_r = max(18, int(rpx * 1.42 + pulse * 8))
                col = (112, 244, 238)
                dim = (52, 132, 144)
                corner = max(7, min(20, mark_r // 3))
                x0, x1 = int(sx - mark_r), int(sx + mark_r)
                y0, y1 = int(sy - mark_r), int(sy + mark_r)
                pygame.draw.line(screen, col, (x0, y0), (x0 + corner, y0), 2)
                pygame.draw.line(screen, col, (x0, y0), (x0, y0 + corner), 2)
                pygame.draw.line(screen, col, (x1, y0), (x1 - corner, y0), 2)
                pygame.draw.line(screen, col, (x1, y0), (x1, y0 + corner), 2)
                pygame.draw.line(screen, col, (x0, y1), (x0 + corner, y1), 2)
                pygame.draw.line(screen, col, (x0, y1), (x0, y1 - corner), 2)
                pygame.draw.line(screen, col, (x1, y1), (x1 - corner, y1), 2)
                pygame.draw.line(screen, col, (x1, y1), (x1, y1 - corner), 2)
                pygame.draw.circle(screen, dim, (int(sx), int(sy)), mark_r, 1)
                if rpx >= 10:
                    label = ui_font(16, True).render(f"P{index + 1}  DATA SIGNAL  /  LANDABLE", True, col)
                    screen.blit(label, (int(sx - label.get_width() * 0.5), y0 - 24))

            if mission_state is not None and index != getattr(mission_state, "target_planet_index", -1):
                signal = getattr(mission_state, "signals", {}).get(index)
                role = getattr(signal, "role", "survey") if signal is not None else "survey"
                reveal = (role == "fuel" and scanner_upgrade >= 1) or (role == "salvage" and scanner_upgrade >= 2) or (role == "survey" and scanner_upgrade >= 3)
                if reveal:
                    role_col = {"fuel": (112, 224, 255), "salvage": (255, 190, 94), "survey": (154, 170, 188)}.get(role, (154, 170, 188))
                    mark_r = max(12, int(rpx * 1.24))
                    pygame.draw.circle(screen, role_col, (int(sx), int(sy)), mark_r, 1)
                    if rpx >= 8:
                        label = ui_font(14, True).render(f"P{index + 1}  {role.upper()} SIGNAL  /  LANDABLE", True, role_col)
                        screen.blit(label, (int(sx - label.get_width() * 0.5), int(sy + mark_r + 7)))
                elif rpx >= 8:
                    # The base scanner identifies planetary index only. This
                    # keeps mission-brief P-numbers usable without revealing
                    # optional resource roles before their upgrade level.
                    label = ui_font(13, True).render(f"P{index + 1}  LANDABLE", True, (124, 146, 160))
                    screen.blit(label, (int(sx - label.get_width() * 0.5), int(sy + rpx + 7)))

            if ORBITAL_RINGS_ENABLED and planet.ringed and rpx >= 8:
                draw_pixel_rings(screen, sx, sy, rpx, planet, 'front', tsec)

# ----------------------------
# Retro post-processing
# ----------------------------

class RetroFX:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.scan = pygame.Surface((w, h), pygame.SRCALPHA)
        self.vign = pygame.Surface((w, h), pygame.SRCALPHA)
        self.noise = pygame.Surface((w, h), pygame.SRCALPHA)
        self.static_overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        self._noise_frame_id = None
        self._build_static()

    def resize(self, w, h):
        self.__init__(w, h)

    def _build_static(self):
        w, h = self.w, self.h
        self.scan.fill((0, 0, 0, 0))
        for y in range(0, h, 2):
            self.scan.fill((0, 0, 0, 32), rect=pygame.Rect(0, y, w, 1))

        self.vign.fill((0, 0, 0, 0))
        steps = 18
        for i in range(steps):
            t = i / (steps - 1)
            a = int(lerp(0, 100, t))
            margin = int(lerp(0, min(w, h) * 0.19, t))
            rect = pygame.Rect(margin, margin, w - margin * 2, h - margin * 2)
            pygame.draw.rect(self.vign, (0, 0, 0, a), rect, width=2)

        # Scanlines and vignette are static between resizes. Precompose them
        # once so the frame loop pays for one full-screen static FX blit rather
        # than two while preserving their authored source-over order.
        self.static_overlay.fill((0, 0, 0, 0))
        self.static_overlay.blit(self.scan, (0, 0))
        self.static_overlay.blit(self.vign, (0, 0))

    def apply(self, surf, tsec):
        w, h = self.w, self.h
        # The authored CRT noise already changes at 25 Hz. The old render loop rebuilt
        # the exact same noise frame more than once when rendering at 60 Hz. Keep
        # the previous noise surface until its authored 25 Hz frame advances.
        noise_frame_id = int(tsec * 25.0)
        if noise_frame_id != self._noise_frame_id:
            self._noise_frame_id = noise_frame_id
            self.noise.fill((0, 0, 0, 0))
            n = int((w * h) * 0.00040)
            rnd = random.Random(noise_frame_id ^ 0xA5A5)
            for _ in range(n):
                x = rnd.randrange(0, w)
                y = rnd.randrange(0, h)
                a = rnd.randrange(8, 28)
                self.noise.set_at((x, y), (255, 210, 150, a))

        surf.blit(self.static_overlay, (0, 0))
        surf.blit(self.noise, (0, 0))


# ----------------------------
# Procedural planet (kept)
# ----------------------------

class Planet:
    def __init__(self, seed=1337):
        self.seed = seed
        self.tex = None
        self.tex_size = 512
        self._build_texture()

    def _build_texture(self):
        rnd = random.Random(self.seed)
        s = self.tex_size
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        base = [[rnd.random() for _ in range(s // 4)] for _ in range(s // 4)]

        def noise(x, y):
            gx = (x / (s - 1)) * (len(base) - 1)
            gy = (y / (s - 1)) * (len(base) - 1)
            x0 = int(gx); y0 = int(gy)
            x1 = min(x0 + 1, len(base) - 1); y1 = min(y0 + 1, len(base) - 1)
            tx = gx - x0; ty = gy - y0
            a = base[y0][x0]
            b = base[y0][x1]
            c = base[y1][x0]
            d = base[y1][x1]
            ab = a + (b - a) * tx
            cd = c + (d - c) * tx
            return ab + (cd - ab) * ty

        for y in range(s):
            lat = (y / (s - 1)) * math.pi - math.pi / 2
            for x in range(s):
                n0 = noise(x, y)
                n1 = noise((x * 2) % s, (y * 2) % s)
                n2 = noise((x * 4) % s, (y * 4) % s)
                h = (0.62 * n0 + 0.28 * n1 + 0.10 * n2)
                ice = clamp((abs(lat) - 1.05) / 0.35, 0.0, 1.0)
                land = h > 0.52
                if ice > 0.02 and (h > 0.40):
                    col = (235, 240, 245, 255)
                elif land:
                    humid = clamp((n1 - 0.45) * 2.2, 0.0, 1.0)
                    r = int(lerp(75, 165, 1.0 - humid))
                    g = int(lerp(125, 185, humid))
                    b = int(lerp(60, 90, humid))
                    col = (r, g, b, 255)
                else:
                    depth = clamp((0.52 - h) / 0.52, 0.0, 1.0)
                    r = int(lerp(18, 10, depth))
                    g = int(lerp(55, 35, depth))
                    b = int(lerp(120, 80, depth))
                    col = (r, g, b, 255)
                surf.set_at((x, y), col)

        for _ in range(28):
            y = rnd.randrange(0, s)
            band_h = rnd.randrange(6, 18)
            alpha = rnd.randrange(14, 42)
            pygame.draw.rect(surf, (255, 255, 255, alpha), pygame.Rect(0, y, s, band_h))

        self.tex = surf

    def draw(self, screen, w, h, ship_pos, yaw, pitch, roll, planet_pos_world):
        rel = vec3_sub(planet_pos_world, ship_pos)
        cam = apply_inv_ypr(rel, yaw, pitch, roll)
        if cam[2] <= 10.0:
            return

        cx, cy = w * 0.5, h * 0.5
        fov = 86.0
        f = (w * 0.5) / math.tan(math.radians(fov) * 0.5)
        sx = cam[0] * f / cam[2] + cx
        sy = cam[1] * f / cam[2] + cy

        k = 240000.0
        radius_px = int(clamp(k / cam[2], 26, min(w, h) * 0.62))
        if sx < -radius_px or sx > w + radius_px or sy < -radius_px or sy > h + radius_px:
            return

        sphere = render_sphere(self.tex, radius_px)
        rect = sphere.get_rect(center=(int(sx), int(sy)))
        screen.blit(sphere, rect)

    def project(self, w, h, ship_pos, yaw, pitch, roll, planet_pos_world):
        """Return (visible, (sx,sy), radius_px, sphere_surf) for the planet."""
        rel = vec3_sub(planet_pos_world, ship_pos)
        cam = apply_inv_ypr(rel, yaw, pitch, roll)
        if cam[2] <= 10.0:
            return (False, (0, 0), 0, None)

        cx, cy = w * 0.5, h * 0.5
        fov = 86.0
        f = (w * 0.5) / math.tan(math.radians(fov) * 0.5)
        sx = cam[0] * f / cam[2] + cx
        sy = cam[1] * f / cam[2] + cy

        k = 240000.0
        radius_px = int(clamp(k / cam[2], 26, min(w, h) * 0.62))
        if sx < -radius_px or sx > w + radius_px or sy < -radius_px or sy > h + radius_px:
            return (False, (0, 0), 0, None)

        sphere = render_sphere(self.tex, radius_px)
        return (True, (sx, sy), radius_px, sphere)


_sphere_cache = {}


def render_sphere(tex, radius_px: int) -> pygame.Surface:
    key = (id(tex), radius_px)
    cached = _sphere_cache.get(key)
    if cached is not None:
        return cached

    d = radius_px * 2
    surf = pygame.Surface((d, d), pygame.SRCALPHA)
    s = tex.get_width()
    light = vec3_norm((-0.45, -0.25, 0.86))

    for py in range(d):
        ny = (py - radius_px) / max(1, radius_px)
        for px in range(d):
            nx = (px - radius_px) / max(1, radius_px)
            rr = nx * nx + ny * ny
            if rr > 1.0:
                continue
            nz = math.sqrt(max(0.0, 1.0 - rr))
            n = (nx, ny, nz)
            lon = math.atan2(n[0], n[2])
            lat = math.asin(n[1])
            u = (lon / (2.0 * math.pi) + 0.5) % 1.0
            v = clamp(lat / math.pi + 0.5, 0.0, 1.0)
            tx = int(u * (s - 1))
            ty = int(v * (s - 1))
            r, g, b, a = tex.get_at((tx, ty))
            ndl = clamp(vec3_dot(n, light), 0.0, 1.0)
            shade = 0.22 + 0.78 * ndl
            rim = (1.0 - nz)
            rim_boost = clamp((rim - 0.60) / 0.35, 0.0, 1.0)
            ar = int(clamp(r * shade + 30 * rim_boost, 0, 255))
            ag = int(clamp(g * shade + 55 * rim_boost, 0, 255))
            ab = int(clamp(b * shade + 85 * rim_boost, 0, 255))
            surf.set_at((px, py), (ar, ag, ab, a))

    pygame.draw.circle(surf, (0, 0, 0, 120), (radius_px, radius_px), radius_px, 2)

    if len(_sphere_cache) > 10:
        _sphere_cache.clear()
    _sphere_cache[key] = surf
    return surf


# ----------------------------
# SFX manager
# ----------------------------

class SFX:
    def __init__(self, root, enabled: bool = True):
        self.root = root
        self.requested_enabled = bool(enabled)
        self.enabled = False
        self.ok = False
        self.engine_idle = []
        self.engine_thrust = []
        self.boost = []
        self.hyper = []
        self.laser = []
        self.missile = []

        self.chan_engine = None
        self.chan_fx = None
        self.master_volume = 1.0
        self.sfx_volume = 1.0
        self.muted = False
        self.engine_base_volume = 0.0
        self.fx_base_volume = 0.0

        if self.requested_enabled:
            self._load()
        else:
            log("SFX: disabled by launch option.")

    def _load(self):
        try:
            pygame.mixer.init()
            self.ok = True
        except Exception as e:
            log(f"SFX: mixer init failed ({e}). Audio disabled.")
            self.ok = False
            return

        self.engine_idle = self._load_folder("engine_idle")
        self.engine_thrust = self._load_folder("engine_thrust")
        self.boost = self._load_folder("boost")
        self.hyper = self._load_folder("hyperspace")
        self.laser = self._load_folder("laser")
        self.missile = self._load_folder("missile")

        pygame.mixer.set_num_channels(max(8, pygame.mixer.get_num_channels()))
        pygame.mixer.set_reserved(5)
        self.chan_engine = pygame.mixer.Channel(0)
        self.chan_fx = pygame.mixer.Channel(1)
        self.enabled = True
        self.engine_context = "stopped"

        log("SFX: folders scanned; channels 0-4 reserved for engine, FX and ambience.")
        log(f"SFX: engine_idle={len(self.engine_idle)} engine_thrust={len(self.engine_thrust)} boost={len(self.boost)} hyper={len(self.hyper)} laser={len(self.laser)}")

    def _load_folder(self, name):
        folder = os.path.join(self.root, name)
        files = list_audio_files(folder)
        out = []
        for fp in files:
            try:
                out.append(pygame.mixer.Sound(fp))
            except Exception:
                # ignore unsupported formats
                pass
        return out

    def _scaled_volume(self, base: float) -> float:
        if self.muted:
            return 0.0
        return clamp(float(base) * self.master_volume * self.sfx_volume, 0.0, 1.0)

    def set_mix(self, master: float, sfx: float, muted: bool = False):
        self.master_volume = clamp(float(master), 0.0, 1.0)
        self.sfx_volume = clamp(float(sfx), 0.0, 1.0)
        self.muted = bool(muted)
        try:
            if self.chan_engine is not None and self.chan_engine.get_busy():
                self.chan_engine.set_volume(self._scaled_volume(self.engine_base_volume))
            if self.chan_fx is not None and self.chan_fx.get_busy():
                self.chan_fx.set_volume(self._scaled_volume(self.fx_base_volume))
        except Exception:
            pass

    def stop_engine(self, fade_ms: int = 320):
        if not (self.enabled and self.ok and self.chan_engine):
            return
        if getattr(self, "engine_context", "stopped") == "stopped":
            return
        try:
            if self.chan_engine.get_busy():
                if int(fade_ms) <= 0:
                    self.chan_engine.stop()
                else:
                    self.chan_engine.fadeout(int(fade_ms))
            self.engine_context = "stopped"
        except Exception:
            pass

    def set_context(self, context: str, thrusting: bool = False):
        """Engine loops only belong to free-flight space mode."""
        if context != "space":
            self.stop_engine()
            return
        self.engine_context = "space"
        self.set_engine_state(thrusting)

    def set_engine_state(self, thrusting: bool):
        if not (self.enabled and self.ok and self.chan_engine):
            return
        # If thrusting loop exists, switch; otherwise keep idle.
        try:
            if thrusting and self.engine_thrust:
                snd = self.engine_thrust[0]
                if not self.chan_engine.get_busy() or self.chan_engine.get_sound() != snd:
                    self.chan_engine.play(snd, loops=-1, fade_ms=120)
                    self.engine_base_volume = 0.82
                    self.chan_engine.set_volume(self._scaled_volume(self.engine_base_volume))
            elif self.engine_idle:
                snd = self.engine_idle[0]
                if not self.chan_engine.get_busy() or self.chan_engine.get_sound() != snd:
                    self.chan_engine.play(snd, loops=-1, fade_ms=160)
                    self.engine_base_volume = 0.68
                    self.chan_engine.set_volume(self._scaled_volume(self.engine_base_volume))
        except Exception:
            pass

    def play_boost(self):
        if self.enabled and self.ok and self.boost:
            try:
                self.chan_fx.play(random.choice(self.boost))
                self.fx_base_volume = 0.92
                self.chan_fx.set_volume(self._scaled_volume(self.fx_base_volume))
            except Exception:
                pass

    def play_hyper(self):
        if self.enabled and self.ok and self.hyper:
            try:
                self.chan_fx.play(random.choice(self.hyper))
                self.fx_base_volume = 0.98
                self.chan_fx.set_volume(self._scaled_volume(self.fx_base_volume))
            except Exception:
                pass

    def play_laser(self):
        if self.enabled and self.ok and self.laser:
            try:
                self.chan_fx.play(random.choice(self.laser))
                self.fx_base_volume = 0.88
                self.chan_fx.set_volume(self._scaled_volume(self.fx_base_volume))
            except Exception:
                pass

    def play_missile(self):
        if self.enabled and self.ok and getattr(self, "missile", None):
            try:
                self.chan_fx.play(random.choice(self.missile))
                self.fx_base_volume = 0.90
                self.chan_fx.set_volume(self._scaled_volume(self.fx_base_volume))
            except Exception:
                pass


# ----------------------------
# State-aware music (assets/music)
# ----------------------------

class MusicPlayer:
    """Single-stream, state-aware score player.

    Pass 28 replaces the old sequential playlist with one authoritative score
    state.  A context change always stops the previous stream before loading
    the next one, and every state loops until gameplay requests a different
    state.  The existing MCF24 file is retained as the expedition theme.
    """

    ENDEVENT = pygame.USEREVENT + 7

    def __init__(self, music_folder: str, enabled: bool):
        self.music_folder = os.path.abspath(music_folder)
        self.enabled = bool(enabled)
        self.master_volume = 1.0
        self.music_volume = 1.0
        self.muted = False
        self.current_state = None
        self.current_path = None
        self.started = False

        if self.enabled:
            try:
                pygame.mixer.music.set_endevent(self.ENDEVENT)
            except Exception:
                pass

    def _base_volume(self) -> float:
        return float(STATE_BASE_VOLUME.get(self.current_state, 0.56))

    def _scaled_volume(self) -> float:
        if self.muted or self.current_state == "silence":
            return 0.0
        return clamp(self._base_volume() * self.master_volume * self.music_volume, 0.0, 1.0)

    def set_mix(self, master: float, music: float, muted: bool = False):
        self.master_volume = clamp(float(master), 0.0, 1.0)
        self.music_volume = clamp(float(music), 0.0, 1.0)
        self.muted = bool(muted)
        if self.enabled:
            try:
                pygame.mixer.music.set_volume(self._scaled_volume())
            except Exception:
                pass

    def _path_for_state(self, state: str):
        name = STATE_TRACKS.get(str(state))
        if not name:
            return None
        path = os.path.join(self.music_folder, name)
        if os.path.isfile(path):
            return path
        # Expedition source is also the safe fallback if a generated score asset
        # is missing from a read-only/partial package.
        fallback = os.path.join(self.music_folder, STATE_TRACKS.get("expedition", "MCF24.mp3"))
        return fallback if os.path.isfile(fallback) else None

    def sync(self, state: str, force: bool = False):
        if not self.enabled:
            return
        state = str(state or "expedition")
        if not force and state == self.current_state:
            return

        # SDL_mixer exposes one music stream.  Stop first so state transitions
        # cannot overlap or leave the previous track alive underneath the next.
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

        self.current_state = state
        self.current_path = None
        self.started = False
        if state == "silence":
            log("Music: state=silence")
            return

        path = self._path_for_state(state)
        if not path:
            log(f"Music: no playable track for state={state}")
            return

        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(loops=-1)
            # pygame-ce resets music volume when a new stream is loaded, so set
            # the effective category volume after load/play on every transition.
            pygame.mixer.music.set_volume(self._scaled_volume())
            self.current_path = path
            self.started = True
            log(f"Music: state={state} loop={os.path.basename(path)}")
        except Exception as exc:
            log(f"Music: failed state={state} path={path} ({exc})")

    def start(self, state: str = "expedition"):
        self.sync(state, force=True)

    def on_end(self):
        # loops=-1 should keep a state alive.  If SDL emits an unexpected end
        # event, restart the same state rather than advancing a playlist.
        if self.current_state and self.current_state != "silence":
            self.sync(self.current_state, force=True)

    def update(self):
        if not (self.enabled and self.started and self.current_state != "silence"):
            return
        try:
            if not pygame.mixer.music.get_busy():
                self.sync(self.current_state, force=True)
        except Exception:
            pass



# ----------------------------
# Cockpit art / HUD integration
# ----------------------------

@dataclass
class CockpitStyle:
    name: str
    symmetry: float          # 0..1
    bezel: int               # px-ish
    grime: float             # 0..1
    wiring: float            # 0..1
    crt: float               # 0..1
    roundness: float         # 0..1


@dataclass
class CableDef:
    points: list            # list[(x,y)] control polyline points
    width: int
    col: tuple              # (r,g,b,a) base
    glow: tuple             # (r,g,b,a) additive
    phase: float
    freq: float
    amp: float              # base amplitude in px
    pulse: float            # how much reacts to boost/hyper (0..1)


class ProceduralCockpitGenerator:
    """
    Semantic cockpit generator (v1.7):
    - Windshield is dominant (>=80% of screen area target).
    - Everything outside the windshield is filled with cockpit structure.
    - Dense mechanical detailing around the windshield.
    - Meters are smaller/thinner and anchored to slots (never drift/overlap).
    - Cable paths are generated deterministically from the seed and then animated at render time.
    """
    STYLE_PRESETS = [
        CockpitStyle("REBELLION_ANALOG", symmetry=0.70, bezel=6, grime=0.55, wiring=0.65, crt=0.75, roundness=0.70),
        CockpitStyle("IMPERIAL_MONO",    symmetry=0.92, bezel=4, grime=0.15, wiring=0.25, crt=0.45, roundness=0.15),
        CockpitStyle("CORPORATE_RETRO",  symmetry=0.98, bezel=5, grime=0.22, wiring=0.35, crt=0.85, roundness=0.35),
        CockpitStyle("SALVAGED_FRIGATE", symmetry=0.35, bezel=7, grime=0.85, wiring=0.90, crt=0.35, roundness=0.40),
        CockpitStyle("EXPERIMENTAL_PROTO", symmetry=0.80, bezel=5, grime=0.28, wiring=0.75, crt=0.65, roundness=0.85),
    ]

    def __init__(self, seed=None):
        self.seed = int(seed if seed is not None else random.randrange(1_000_000_000))
        self.rng = random.Random(self.seed)
        self.style = self.rng.choice(self.STYLE_PRESETS)

        # palette (strong per-seed variation)
        self.col_hull = self._pick_hull_color()
        self.col_hull2 = self._shade(self.col_hull, -22)
        self.col_line = self._shade(self.col_hull, 34)

        # randomized accents (alien + machine)
        self.col_accent1 = self._pick_accent_color()
        self.col_accent2 = self._pick_accent_color(alt=True)
        self.col_glow = self._pick_glow_color()
        self.col_dim = self._shade(self.col_glow, -120)

        self.col_glass = (18, 24, 32, 70)

        self.zones = {}
        self.meter_rects = {}
        self.cables = []

    def _pick_hull_color(self):
        rng = self.rng
        bases = [
            (18, 16, 14),   # dark brown
            (14, 16, 20),   # blue steel
            (22, 18, 16),   # warm iron
            (16, 14, 22),   # violet gunmetal
            (20, 18, 14),   # brass dark
            (16, 20, 16),   # oxidized
        ]
        base = rng.choice(bases)
        jitter = lambda v: int(clamp(v + rng.uniform(-10, 10), 0, 255))
        return (jitter(base[0]), jitter(base[1]), jitter(base[2]))

    def _pick_accent_color(self, alt=False):
        rng = self.rng
        # saturated accents, but kept somewhat retro
        hs = rng.random()
        if alt:
            hs = (hs + rng.uniform(0.28, 0.62)) % 1.0
        s = rng.uniform(0.35, 0.80)
        v = rng.uniform(0.35, 0.85)
        r, g, b = hsv_to_rgb(hs, s, v)
        return (r, g, b)

    def _pick_glow_color(self):
        rng = self.rng
        choices = [
            (255, 170, 85),   # amber
            (140, 220, 255),  # cyan
            (200, 120, 255),  # violet
            (255, 120, 120),  # red
            (140, 255, 170),  # green
        ]
        c = rng.choice(choices)
        # slight jitter
        return (int(clamp(c[0] + rng.uniform(-10, 10), 0, 255)),
                int(clamp(c[1] + rng.uniform(-10, 10), 0, 255)),
                int(clamp(c[2] + rng.uniform(-10, 10), 0, 255)))

    def _shade(self, rgb, d):
        return (int(clamp(rgb[0] + d, 0, 255)),
                int(clamp(rgb[1] + d, 0, 255)),
                int(clamp(rgb[2] + d, 0, 255)))

    def _zones_for_size(self, w: int, h: int):
        rng = self.rng
        s = self.style

        # Windshield must dominate (>=80% of the screen).
        # We approximate by choosing very large width/height and a shallow border.
        ws_w = int(w * rng.uniform(0.90, 0.96))
        ws_h = int(h * rng.uniform(0.82, 0.90))
        ws_y = int(h * rng.uniform(0.02, 0.05))
        ws = pygame.Rect((w - ws_w) // 2, ws_y, ws_w, ws_h)

        # keep-out padding for surrounding mechanical ring
        pad = int(max(10, s.bezel * 3))
        keepout = ws.inflate(pad * 2, pad * 2).clip(pygame.Rect(0, 0, w, h))

        # thin surrounding band zones (built around windshield perimeter)
        # bottom rail
        rail_h = int(max(32, h * 0.06))
        band = pygame.Rect(0, h - rail_h, w, rail_h)

        # left/right rails
        side_w = int(max(28, w * 0.06))
        left_rail = pygame.Rect(0, 0, side_w, h)
        right_rail = pygame.Rect(w - side_w, 0, side_w, h)

        # top rail
        top_h = int(max(26, h * 0.05))
        top_rail = pygame.Rect(0, 0, w, top_h)

        # meter anchor zones: slim regions on bottom/side rails
        dash_left = pygame.Rect(int(w * 0.02), int(h * 0.78), int(w * 0.18), int(h * 0.16)).clip(band.inflate(0, int(h*0.10)))
        dash_right = pygame.Rect(w - int(w * 0.20), int(h * 0.78), int(w * 0.18), int(h * 0.16)).clip(band.inflate(0, int(h*0.10)))
        center_stack = pygame.Rect(int(w * 0.42), int(h * 0.82), int(w * 0.16), int(h * 0.10)).clip(band.inflate(0, int(h*0.10)))

        self.zones = {
            "WIND_SHIELD": ws,
            "WIND_KEEP": keepout,
            "BAND": band,
            "LEFT_RAIL": left_rail,
            "RIGHT_RAIL": right_rail,
            "TOP_RAIL": top_rail,
            "DASH_LEFT": dash_left,
            "DASH_RIGHT": dash_right,
            "CENTER_STACK": center_stack,
        }

    def _slot_rects(self, zone: pygame.Rect, n: int, vertical: bool = True, pad: int = 8):
        r = zone.inflate(-pad * 2, -pad * 2)
        if r.width < 8 or r.height < 8:
            return [zone.copy() for _ in range(n)]
        out = []
        if vertical:
            slot_h = max(12, (r.height - (n - 1) * pad) // n)
            y = r.top
            for _ in range(n):
                out.append(pygame.Rect(r.left, y, r.width, slot_h))
                y += slot_h + pad
        else:
            slot_w = max(12, (r.width - (n - 1) * pad) // n)
            x = r.left
            for _ in range(n):
                out.append(pygame.Rect(x, r.top, slot_w, r.height))
                x += slot_w + pad
        return out

    def _assign_meters(self):
        dl = self.zones["DASH_LEFT"]
        dr = self.zones["DASH_RIGHT"]
        cs = self.zones["CENTER_STACK"]

        # Make meters thinner/smaller
        right_slots = self._slot_rects(dr, 3, vertical=True, pad=max(6, self.style.bezel))
        left_slots = self._slot_rects(dl, 1, vertical=True, pad=max(6, self.style.bezel))
        center_slots = self._slot_rects(cs, 1, vertical=True, pad=max(6, self.style.bezel))

        def thin(r: pygame.Rect):
            return r.inflate(-max(10, r.width // 10), -max(6, r.height // 5))

        self.meter_rects = {
            "SPEED": thin(center_slots[0]),
            "DIST": thin(left_slots[0]),
            "HEAT": thin(right_slots[0]),
            "POWER": thin(right_slots[1]),
            "SHIELD": thin(right_slots[2]),
        }

    def _build_cables(self, w: int, h: int):
        rng = self.rng
        s = self.style
        keep = self.zones["WIND_KEEP"]

        def pick_point_on_ring():
            # pick a point outside keepout with bias toward its edges
            for _ in range(40):
                side = rng.choice(["TOP", "BOT", "L", "R"])
                if side == "TOP":
                    x = rng.randrange(0, w)
                    y = rng.randrange(0, max(1, keep.top))
                elif side == "BOT":
                    x = rng.randrange(0, w)
                    y = rng.randrange(min(h-1, keep.bottom), h)
                elif side == "L":
                    x = rng.randrange(0, max(1, keep.left))
                    y = rng.randrange(0, h)
                else:
                    x = rng.randrange(min(w-1, keep.right), w)
                    y = rng.randrange(0, h)
                if not keep.collidepoint(x, y):
                    return (x, y)
            return (rng.randrange(0, w), rng.randrange(0, h))

        self.cables = []
        cable_n = int(10 + 26 * s.wiring + rng.random() * 10)
        for _ in range(cable_n):
            p0 = pick_point_on_ring()
            p3 = pick_point_on_ring()

            # mid controls: curve around keepout
            mx = int((p0[0] + p3[0]) * 0.5 + rng.uniform(-w * 0.10, w * 0.10))
            my = int((p0[1] + p3[1]) * 0.5 + rng.uniform(-h * 0.10, h * 0.10))
            p1 = (int(lerp(p0[0], mx, 0.55)), int(lerp(p0[1], my, 0.55)))
            p2 = (int(lerp(p3[0], mx, 0.55)), int(lerp(p3[1], my, 0.55)))

            # convert cubic into polyline points
            pts = []
            steps = rng.randint(9, 14)
            for i in range(steps + 1):
                t = i / steps
                u = 1.0 - t
                x = (u*u*u)*p0[0] + 3*(u*u)*t*p1[0] + 3*u*(t*t)*p2[0] + (t*t*t)*p3[0]
                y = (u*u*u)*p0[1] + 3*(u*u)*t*p1[1] + 3*u*(t*t)*p2[1] + (t*t*t)*p3[1]
                pts.append((int(x), int(y)))

            # base appearance
            width = rng.randint(1, 3)
            if rng.random() < 0.20:
                width += 1

            # random cable color family
            if rng.random() < 0.55:
                base = (*self._shade(self.col_accent1, rng.uniform(-30, 30)), 170)
                glow = (*self._shade(self.col_glow, rng.uniform(-10, 10)), 55)
            else:
                base = (*self._shade(self.col_accent2, rng.uniform(-30, 30)), 160)
                glow = (*self._shade(self.col_glow, rng.uniform(-10, 10)), 45)

            self.cables.append(CableDef(
                points=pts,
                width=width,
                col=(int(base[0]), int(base[1]), int(base[2]), int(base[3])),
                glow=(int(glow[0]), int(glow[1]), int(glow[2]), int(glow[3])),
                phase=rng.uniform(0.0, 6.28318),
                freq=rng.uniform(0.8, 2.2),
                amp=rng.uniform(0.6, 1.6),
                pulse=rng.uniform(0.35, 1.0)
            ))

    def render_static(self, w: int, h: int):
        self._zones_for_size(w, h)
        self._assign_meters()
        self._build_cables(w, h)

        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        self._draw_hull_fill(surf, w, h)
        self._draw_dense_ring(surf, w, h)
        self._draw_windshield_punch(surf, w, h)
        self._draw_micro_instrument_rails(surf, w, h)

        # pixelate for retro style
        surf = self._pixelate(surf, factor=int(clamp(4 + self.style.bezel // 2, 4, 6)))
        return surf, self.meter_rects, self.cables, self.zones["WIND_KEEP"]

    def _pixelate(self, surf, factor=5):
        w, h = surf.get_size()
        sw = max(1, w // factor)
        sh = max(1, h // factor)
        small = pygame.transform.smoothscale(surf, (sw, sh))
        big = pygame.transform.scale(small, (w, h))
        return big

    def _draw_hull_fill(self, surf, w, h):
        # full screen hull base (everything outside windshield will read as cockpit)
        pygame.draw.rect(surf, (*self.col_hull, 255), pygame.Rect(0, 0, w, h))

    def _draw_dense_ring(self, surf, w, h):
        # heavy detail in the ring area around the windshield
        rng = self.rng
        keep = self.zones["WIND_KEEP"]
        s = self.style

        def clip_keep(layer):
            mask = pygame.Surface((w, h), pygame.SRCALPHA)
            mask.fill((255, 255, 255, 255))
            pygame.draw.rect(mask, (0, 0, 0, 0), keep)
            layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        # ridges/ribs
        ribs = pygame.Surface((w, h), pygame.SRCALPHA)
        rib_n = int(24 + rng.random() * 26)
        for _ in range(rib_n):
            if rng.random() < 0.5:
                # radial-ish from windshield
                a = rng.uniform(0, math.tau)
                x0 = keep.centerx + math.cos(a) * rng.uniform(keep.width*0.55, keep.width*0.75)
                y0 = keep.centery + math.sin(a) * rng.uniform(keep.height*0.55, keep.height*0.75)
                x1 = keep.centerx + math.cos(a) * rng.uniform(keep.width*0.85, keep.width*1.20)
                y1 = keep.centery + math.sin(a) * rng.uniform(keep.height*0.85, keep.height*1.20)
                pygame.draw.line(ribs, (*self._shade(self.col_line, rng.uniform(-40, 40)), 110), (x0, y0), (x1, y1), rng.randint(1, 3))
            else:
                # stepped ridge segments
                x = rng.randrange(0, w)
                y = rng.randrange(0, h)
                if keep.collidepoint(x, y):
                    continue
                L = rng.uniform(w*0.05, w*0.18)
                dx = rng.uniform(-1, 1)
                dy = rng.uniform(-1, 1)
                x2 = x + dx * L
                y2 = y + dy * L
                pygame.draw.line(ribs, (*self._shade(self.col_line, rng.uniform(-55, 55)), 90), (x, y), (x2, y2), rng.randint(1, 2))
        clip_keep(ribs)
        surf.blit(ribs, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # panels
        panels = pygame.Surface((w, h), pygame.SRCALPHA)
        p_n = int(18 + rng.random() * 18)
        for _ in range(p_n):
            pw = int(w * rng.uniform(0.04, 0.14))
            ph = int(h * rng.uniform(0.03, 0.10))
            px = rng.randrange(0, max(1, w - pw))
            py = rng.randrange(0, max(1, h - ph))
            r = pygame.Rect(px, py, pw, ph)
            if r.colliderect(keep):
                continue
            br = int(2 + 10 * s.roundness)
            base = self._shade(self.col_hull, rng.uniform(-26, 22))
            pygame.draw.rect(panels, (*base, 255), r, border_radius=br)
            pygame.draw.rect(panels, (*self.col_line, 160), r, width=1, border_radius=br)

            # vents
            if rng.random() < 0.45:
                sl = rng.randint(3, 7)
                for i in range(sl):
                    yy = r.top + 2 + i * max(2, (r.height - 4) // sl)
                    pygame.draw.line(panels, (*self.col_dim, 150), (r.left + 3, yy), (r.right - 3, yy), 1)

            # alien glyph panel
            if rng.random() < 0.22:
                gx = r.left + rng.randint(3, max(3, r.width - 22))
                gy = r.top + rng.randint(3, max(3, r.height - 14))
                gw = rng.randint(18, 34)
                gh = rng.randint(10, 14)
                gr = pygame.Rect(gx, gy, gw, gh)
                pygame.draw.rect(panels, (0, 0, 0, 140), gr, border_radius=2)
                for k in range(rng.randint(5, 10)):
                    xx = gr.left + rng.randint(2, gr.width - 3)
                    yy = gr.top + rng.randint(2, gr.height - 3)
                    pygame.draw.circle(panels, (*self.col_accent1, 160), (xx, yy), 1)

        clip_keep(panels)
        surf.blit(panels, (0, 0))

        # gears (partial arcs)
        gears = pygame.Surface((w, h), pygame.SRCALPHA)
        g_n = int(8 + rng.random() * 10)
        for _ in range(g_n):
            cx = rng.randrange(0, w)
            cy = rng.randrange(0, h)
            if keep.collidepoint(cx, cy):
                continue
            rad = rng.randint(int(min(w, h) * 0.03), int(min(w, h) * 0.08))
            a0 = rng.uniform(0.0, math.tau)
            a1 = a0 + rng.uniform(0.6, 1.8)
            steps = 18
            last = None
            for i in range(steps + 1):
                t = i / steps
                a = lerp(a0, a1, t)
                x = cx + math.cos(a) * rad
                y = cy + math.sin(a) * rad
                if last is not None:
                    pygame.draw.line(gears, (*self.col_line, 120), last, (x, y), 2)
                last = (x, y)
            # teeth
            teeth = rng.randint(8, 16)
            for i in range(teeth):
                a = lerp(a0, a1, i / max(1, teeth - 1))
                x = cx + math.cos(a) * rad
                y = cy + math.sin(a) * rad
                x2 = cx + math.cos(a) * (rad + rng.randint(4, 8))
                y2 = cy + math.sin(a) * (rad + rng.randint(4, 8))
                pygame.draw.line(gears, (*self.col_line, 120), (x, y), (x2, y2), 2)

        clip_keep(gears)
        surf.blit(gears, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # grime specks
        if s.grime > 0.02:
            n = int((w * h) * (0.00008 + 0.00020 * s.grime))
            for _ in range(n):
                x = rng.randrange(0, w)
                y = rng.randrange(0, h)
                if keep.collidepoint(x, y):
                    continue
                a = rng.randrange(8, 28)
                c = rng.randrange(0, 50)
                surf.set_at((x, y), (c, c, c, a))

        # accent stripes
        if rng.random() < 0.8:
            stripe = pygame.Surface((w, h), pygame.SRCALPHA)
            col = (*self.col_accent2, int(22 + 44 * s.crt))
            y = int(h * rng.uniform(0.78, 0.92))
            thick = int(5 + 14 * rng.random())
            pygame.draw.rect(stripe, col, pygame.Rect(int(w * 0.06), y, int(w * 0.88), thick))
            clip_keep(stripe)
            surf.blit(stripe, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_windshield_punch(self, surf, w, h):
        ws = self.zones["WIND_SHIELD"]
        keep = self.zones["WIND_KEEP"]
        s = self.style
        rng = self.rng

        # Use large curved canopy by default for maximum view; still allow variation.
        mode = rng.choices(["CURVE", "TRAP", "SPLIT"], weights=[0.55, 0.30, 0.15])[0]

        def punch_polygon(poly):
            mask = pygame.Surface((w, h), pygame.SRCALPHA)
            mask.fill((255, 255, 255, 255))
            pygame.draw.polygon(mask, (0, 0, 0, 0), poly)
            surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        def punch_rect(rect, br):
            mask = pygame.Surface((w, h), pygame.SRCALPHA)
            mask.fill((255, 255, 255, 255))
            pygame.draw.rect(mask, (0, 0, 0, 0), rect, border_radius=br)
            surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        if mode == "TRAP":
            inset = int(ws.width * rng.uniform(0.06, 0.12))
            poly = [
                (ws.left + inset, ws.top),
                (ws.right - inset, ws.top),
                (ws.right, ws.bottom),
                (ws.left, ws.bottom),
            ]
            punch_polygon(poly)
            # Windshield must be perfectly clear: no tint or glare.
            pygame.draw.polygon(surf, (*self.col_line, 220), poly, width=max(2, s.bezel // 2))
        elif mode == "SPLIT":
            br = int(10 + 18 * s.roundness)
            punch_rect(ws, br)
            mid = ws.centerx
            pygame.draw.line(surf, (*self.col_line, 230), (mid, ws.top), (mid, ws.bottom), max(2, s.bezel // 2))
            pygame.draw.rect(surf, (*self.col_line, 210), ws, width=max(2, s.bezel // 2), border_radius=br)
        else:
            r = int(min(ws.width, ws.height) * rng.uniform(1.00, 1.25))
            center = (ws.centerx, ws.bottom + int(r * 0.06))
            cut = pygame.Surface((w, h), pygame.SRCALPHA)
            cut.fill((255, 255, 255, 255))
            pygame.draw.circle(cut, (0, 0, 0, 0), center, r)
            clip = pygame.Surface((w, h), pygame.SRCALPHA)
            clip.fill((0, 0, 0, 0))
            pygame.draw.rect(clip, (255, 255, 255, 255), keep)
            cut.blit(clip, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(cut, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

            # No glass tint; only an outline to read the frame edge.
            pygame.draw.circle(surf, (*self.col_line, 210), center, r, width=max(2, s.bezel // 2))

            glass_clip = pygame.Surface((w, h), pygame.SRCALPHA)
            glass_clip.fill((0, 0, 0, 0))
            pygame.draw.rect(glass_clip, (255, 255, 255, 255), keep)
            surf.blit(glass_clip, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        # No reflections/shine: windshield stays unobstructed.

        # thick bezel ring around keepout for depth
        ring = keep.inflate(int(s.bezel * 4), int(s.bezel * 4)).clip(pygame.Rect(0, 0, w, h))
        pygame.draw.rect(surf, (*self._shade(self.col_hull, -20), 255), ring, width=max(3, s.bezel), border_radius=int(8 + 18 * s.roundness))
        pygame.draw.rect(surf, (*self.col_line, 200), ring, width=max(1, s.bezel // 2), border_radius=int(8 + 18 * s.roundness))

    def _draw_micro_instrument_rails(self, surf, w, h):
        # subtle rails so meters feel integrated (not stickers)
        rng = self.rng
        s = self.style
        keep = self.zones["WIND_KEEP"]

        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(10):
            x = rng.randrange(0, w)
            y = rng.randrange(int(h * 0.70), h)
            if keep.collidepoint(x, y):
                continue
            pygame.draw.rect(layer, (*self._shade(self.col_line, rng.uniform(-40, 40)), 70),
                             pygame.Rect(x, y, rng.randint(10, 60), rng.randint(1, 3)))
        # clip out windshield
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        mask.fill((255, 255, 255, 255))
        pygame.draw.rect(mask, (0, 0, 0, 0), keep)
        layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(layer, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)


class CockpitArt:
    def __init__(self):
        self.base_img = None
        self.scaled = None
        self.last_size = None
        self.font_small = None
        self.font_mono = None
        self._glow_text_cache = OrderedDict()

        # Procedural cockpit state
        self.proc_seed = random.randrange(1_000_000_000)
        self.proc_overlay = None
        self.proc_meter_rects = {}
        self.proc_cables = []
        self.proc_keepout = None
        self.proc_last_size = None

        self.saved_seeds = []
        self.saved_index = -1  # -1 means "current unsaved"

        # Optional external art (if user supplies cockpit.png)
        self.use_image = False
        self.allow_procedural = False  # user request: no forced procedural cockpit
        self._try_load()

    def _try_load(self):
        # User-provided cockpit overlay art (no procedural fallback requested).
        # Folder: assets/ui/cockpit/  (first image found is used)
        folder = os.path.join(BASE_DIR, "assets", "ui", "cockpit")
        os.makedirs(folder, exist_ok=True)
        path = None
        for fn in sorted(os.listdir(folder)):
            if fn.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
                path = os.path.join(folder, fn)
                break

        if path and os.path.isfile(path):
            try:
                self.base_img = pygame.image.load(path).convert_alpha()
                self.use_image = True
                log(f"Cockpit: loaded {path} (image overlay enabled).")
                return
            except Exception:
                self.base_img = None
                self.use_image = False
                log("Cockpit: failed to load cockpit overlay; continuing without cockpit art.")
                return

        self.base_img = None
        self.use_image = False



    def _ensure_fonts(self):
        if self.font_small is None:
            self.font_small = pygame.font.Font(None, 18)
            self.font_mono = pygame.font.Font(None, 18)

    def _pixelate(self, surf, factor: int = 4):
        w, h = surf.get_size()
        sw = max(1, w // factor)
        sh = max(1, h // factor)
        small = pygame.transform.smoothscale(surf, (sw, sh))
        big = pygame.transform.scale(small, (w, h))
        return big

    def _ensure_procedural(self, w, h):
        if self.proc_last_size != (w, h) or self.proc_overlay is None:
            gen = ProceduralCockpitGenerator(seed=self.proc_seed)
            overlay, rects, cables, keepout = gen.render_static(w, h)

            self.proc_overlay = overlay
            self.proc_meter_rects = rects
            self.proc_cables = cables
            self.proc_keepout = keepout
            self.proc_last_size = (w, h)

    def render(self, screen, w, h, ship, tsec, supernova_remaining=None, blackhole_remaining=None, paused=False, hud_visible=True):
        self._ensure_fonts()
        if (not self.use_image) and self.allow_procedural:
            self._ensure_procedural(w, h)

        # cockpit overlay (image-driven; procedural disabled unless explicitly enabled)
        if self.use_image and self.base_img:
            if self.last_size != (w, h) or self.scaled is None:
                src_w, src_h = self.base_img.get_size()
                scale = max(w / max(1.0, float(src_w)), h / max(1.0, float(src_h)))
                expanded = pygame.transform.smoothscale(
                    self.base_img,
                    (max(1, int(round(src_w * scale))), max(1, int(round(src_h * scale)))),
                )
                crop_x = max(0, (expanded.get_width() - w) // 2)
                crop_y = max(0, (expanded.get_height() - h) // 2)
                self.scaled = expanded.subsurface(pygame.Rect(crop_x, crop_y, w, h)).copy()
                self.last_size = (w, h)
            screen.blit(self.scaled, (0, 0))
        elif self.allow_procedural and self.proc_overlay is not None:
            screen.blit(self.proc_overlay, (0, 0))

        # animated cables overlay (reacts to boost/hyperspace)
        self._draw_animated_cables(screen, w, h, ship, tsec)

        # The cockpit shell is world presentation; HUD instruments are optional.
        if not hud_visible:
            return

        # meters (thin)
        hud_col = (255, 170, 85)
        dim_col = (120, 80, 40)

        r_speed = self.proc_meter_rects.get("SPEED")
        r_dist = self.proc_meter_rects.get("DIST")
        r_heat = self.proc_meter_rects.get("HEAT")
        r_pwr = self.proc_meter_rects.get("POWER")
        r_shd = self.proc_meter_rects.get("SHIELD")

        if r_speed:
            self._draw_box_text(screen, r_speed, f"SPD {int(ship.speed):4d}", hud_col, dim_col, mode="SCREEN")
        if r_dist:
            self._draw_box_text(screen, r_dist, f"DST {int(ship.dist_to_planet):6d}", hud_col, dim_col, mode="SCREEN")

        if r_heat:
            self._draw_meter_bar(screen, r_heat, "HEAT", ship.heat, hud_col, dim_col)
        if r_pwr:
            self._draw_meter_bar(screen, r_pwr, "PWR", ship.power, hud_col, dim_col)
        if r_shd:
            self._draw_meter_bar(screen, r_shd, "SHD", ship.shield, hud_col, dim_col)

        # reticle
        cx, cy = w // 2, h // 2
        pygame.draw.circle(screen, (0, 0, 0, 130), (cx, cy), 12)
        pygame.draw.circle(screen, hud_col, (cx, cy), 12, 1)
        pygame.draw.line(screen, hud_col, (cx - 18, cy), (cx - 6, cy), 1)
        pygame.draw.line(screen, hud_col, (cx + 6, cy), (cx + 18, cy), 1)
        pygame.draw.line(screen, hud_col, (cx, cy - 18), (cx, cy - 6), 1)
        pygame.draw.line(screen, hud_col, (cx, cy + 6), (cx, cy + 18), 1)

        mode = "PAUSED" if paused else ("HYPER" if ship.hyperspace else "FLIGHT")
        # saved/seed HUD removed (legacy)
        status = f"ENTROPY   {mode}"
        self._glow_text(screen, status, (18, 14), hud_col, glow=2, alpha=70)
        if supernova_remaining is not None:
            rem = max(0.0, float(supernova_remaining))
            mm = int(rem // 60)
            ss = int(rem % 60)
            ttxt = f"SUPERNOVA T-{mm:02d}:{ss:02d}"
            if rem <= 30.0:
                self._glow_text(screen, ttxt, (18, 54), (255, 110, 70), glow=2, alpha=80)
            else:
                self._glow_text(screen, ttxt, (18, 54), dim_col, glow=1, alpha=60)
        if blackhole_remaining is not None:
            rem = max(0.0, float(blackhole_remaining))
            mm = int(rem // 60)
            ss = int(rem % 60)
            btxt = f"BLACK HOLE T-{mm:02d}:{ss:02d}"
            col = (255, 120, 90) if rem <= 30.0 else dim_col
            self._glow_text(screen, btxt, (18, 72), col, glow=2 if rem <= 30.0 else 1, alpha=78 if rem <= 30.0 else 60)


    def _draw_animated_cables(self, screen, w, h, ship, tsec):
        if not self.proc_cables or self.proc_keepout is None:
            return
        keep = self.proc_keepout

        # Reaction intensity
        boost = 1.0 if ship.boost_norm > 0.5 else ship.boost_norm
        hyper = 1.0 if ship.hyperspace else 0.0
        inten = clamp(0.10 + 0.70 * boost + 1.10 * hyper, 0.0, 1.6)

        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        glow = pygame.Surface((w, h), pygame.SRCALPHA)

        for c in self.proc_cables:
            amp = c.amp * (0.8 + inten * 3.0 * c.pulse)
            # "shiver" frequency increases in hyperspace
            f = c.freq * (1.0 + 1.8 * hyper) + 0.3 * boost

            pts = []
            for idx, (x, y) in enumerate(c.points):
                # local wave with index-based phase
                wob = math.sin(tsec * f + c.phase + idx * 0.45)
                wob2 = math.cos(tsec * (f * 1.37) + c.phase * 0.7 + idx * 0.22)
                ox = int(wob * amp)
                oy = int(wob2 * amp * 0.7)
                px = x + ox
                py = y + oy
                # don't animate inside windshield keepout; keep glass clean
                if keep.collidepoint(px, py):
                    # try snapping to nearest outside by ignoring offset
                    px, py = x, y
                pts.append((px, py))

            # draw segments, skipping those that cross into keepout too much
            if len(pts) >= 2:
                # base cable
                pygame.draw.lines(layer, c.col, False, pts, c.width)

                # clamps / nodes (small circles)
                if (boost > 0.05 or hyper > 0.0) and (len(pts) > 6):
                    step = 5
                    for i in range(0, len(pts), step):
                        if keep.collidepoint(pts[i][0], pts[i][1]):
                            continue
                        pygame.draw.circle(layer, (*c.col[:3], 200), pts[i], max(1, c.width - 1))

                # glow when boosting/hyperspace
                if inten > 0.25:
                    a = int(clamp(c.glow[3] * (0.35 + 0.65 * inten), 0, 255))
                    pygame.draw.lines(glow, (c.glow[0], c.glow[1], c.glow[2], a), False, pts, max(1, c.width + 1))

        # clip out windshield keepout
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        mask.fill((255, 255, 255, 255))
        pygame.draw.rect(mask, (0, 0, 0, 0), keep)
        layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        glow.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        screen.blit(layer, (0, 0))
        screen.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_box_text(self, screen, rect: pygame.Rect, text: str, col, dim, mode="SCREEN"):
        r = rect
        pygame.draw.rect(screen, (0, 0, 0, 175), r)
        pygame.draw.rect(screen, dim, r, 1)

        if mode == "SCREEN":
            gx = r.left + int(r.width * 0.10)
            gy = r.top + int(r.height * 0.18)
            gw = max(10, int(r.width * 0.80))
            gh = max(4, int(r.height * 0.16))
            # A meter sheen is only a small strip. The old code allocated a
            # full 1920x1080 alpha surface for every box, every frame.
            sheen = pygame.Surface((gw, gh), pygame.SRCALPHA)
            sheen.fill((255, 255, 255, 22))
            screen.blit(sheen, (gx, gy), special_flags=pygame.BLEND_RGBA_ADD)

        t = self.font_mono.render(text, True, col)
        screen.blit(t, (r.left + 6, r.top + (r.height - t.get_height()) // 2))

    def _draw_meter_bar(self, screen, rect: pygame.Rect, label: str, value: float, col, dim):
        r = rect
        value = clamp(value, 0.0, 1.0)
        pygame.draw.rect(screen, (0, 0, 0, 190), r)
        pygame.draw.rect(screen, dim, r, 1)

        pad = 6
        inner = r.inflate(-pad * 2, -pad * 2)
        inner_h = max(6, int(inner.height * 0.28))
        bar = pygame.Rect(inner.left, inner.bottom - inner_h, int(inner.width * value), inner_h)

        bar_col = col
        if label == "HEAT" and value >= 0.75:
            bar_col = (255, 110, 70)
        if label == "SHD" and value <= 0.25:
            bar_col = (255, 110, 70)

        pygame.draw.rect(screen, bar_col, bar)

        pct = int(value * 100)
        t = self.font_mono.render(f"{label} {pct:3d}%", True, col)
        screen.blit(t, (r.left + 6, r.top + 2))

    def _glow_text(self, surf, text, pos, col, glow=2, alpha=90):
        key = (str(text), tuple(col), int(glow), int(alpha))
        gx = self._glow_text_cache.get(key)
        if gx is None:
            base = self.font_small.render(text, True, col)
            gx = pygame.Surface((base.get_width() + glow * 2, base.get_height() + glow * 2), pygame.SRCALPHA)
            ghost = base.copy()
            ghost.set_alpha(alpha)
            for ox in (-glow, 0, glow):
                for oy in (-glow, 0, glow):
                    if ox == 0 and oy == 0:
                        continue
                    gx.blit(ghost, (ox + glow, oy + glow))
            gx.blit(base, (glow, glow))
            self._glow_text_cache[key] = gx
            self._glow_text_cache.move_to_end(key)
            while len(self._glow_text_cache) > 48:
                self._glow_text_cache.popitem(last=False)
        else:
            self._glow_text_cache.move_to_end(key)
        surf.blit(gx, (pos[0] - glow, pos[1] - glow))


# ----------------------------
# Projectiles (laser bullets)
# ----------------------------

@dataclass
class Laser:
    pos: tuple
    vel: tuple
    life: float


class Lasers:
    def __init__(self):
        self.items = []
        self.cool = 0.0

    def spawn(self, ship_pos, fwd_world, ship_vel, hyperspace):
        rate = 0.075 if not hyperspace else 0.11
        if self.cool > 0.0:
            return False
        self.cool = rate
        muzzle = vec3_add(ship_pos, vec3_mul(fwd_world, 2.0))
        speed = 950.0
        v = vec3_add(vec3_mul(fwd_world, speed), ship_vel)
        self.items.append(Laser(muzzle, v, 1.5))
        return True

    def update(self, dt):
        if self.cool > 0.0:
            self.cool = max(0.0, self.cool - dt)
        nxt = []
        for l in self.items:
            pos = vec3_add(l.pos, vec3_mul(l.vel, dt))
            life = l.life - dt
            if life > 0.0:
                nxt.append(Laser(pos, l.vel, life))
        self.items = nxt

    def draw(self, screen, w, h, yaw, pitch, roll, ship_pos):
        cx, cy = w * 0.5, h * 0.5
        fov = 86.0
        f = (w * 0.5) / math.tan(math.radians(fov) * 0.5)
        col = (255, 110, 70)

        for l in self.items:
            rel = vec3_sub(l.pos, ship_pos)
            cam = apply_inv_ypr(rel, yaw, pitch, roll)
            if cam[2] <= 0.2:
                continue
            x = cam[0] * f / cam[2] + cx
            y = cam[1] * f / cam[2] + cy
            if x < -30 or x > w + 30 or y < -30 or y > h + 30:
                continue
            L = clamp(110.0 / cam[2], 3.0, 20.0)
            pygame.draw.aaline(screen, col, (x, y), (x, y - L))
            pygame.draw.circle(screen, col, (int(x), int(y)), 2)


# ----------------------------
# Projectiles (missiles)
# ----------------------------

@dataclass
class Missile:
    pos: tuple
    vel: tuple
    life: float
    armed: bool = True


@dataclass
class NebulaParticle:
    pos: tuple
    vel: tuple
    life: float
    col: tuple


class Missiles:
    def __init__(self):
        self.items = []
        self.cool = 0.0

    def spawn(self, ship_pos, fwd_world, ship_vel, hyperspace):
        # Slower fire rate than lasers; single heavy shot.
        rate = 0.50 if not hyperspace else 0.65
        if self.cool > 0.0:
            return False
        self.cool = rate
        muzzle = vec3_add(ship_pos, vec3_mul(fwd_world, 6.0))
        speed = 1250.0
        v = vec3_add(vec3_mul(fwd_world, speed), ship_vel)
        self.items.append(Missile(muzzle, v, 5.0, True))
        return True

    def update(self, dt):
        if self.cool > 0.0:
            self.cool = max(0.0, self.cool - dt)
        nxt = []
        for m in self.items:
            pos = vec3_add(m.pos, vec3_mul(m.vel, dt))
            life = m.life - dt
            if life > 0.0:
                nxt.append(Missile(pos, m.vel, life, m.armed))
        self.items = nxt

    def draw(self, screen, w, h, yaw, pitch, roll, ship_pos):
        cx, cy = w * 0.5, h * 0.5
        fov = 86.0
        f = (w * 0.5) / math.tan(math.radians(fov) * 0.5)

        for m in self.items:
            rel = vec3_sub(m.pos, ship_pos)
            cam = apply_inv_ypr(rel, yaw, pitch, roll)
            if cam[2] <= 0.2:
                continue
            x = cam[0] * f / cam[2] + cx
            y = cam[1] * f / cam[2] + cy
            if x < -40 or x > w + 40 or y < -40 or y > h + 40:
                continue

            # Pixel missile: small bright head + faint tail.
            size = int(clamp(14.0 / cam[2], 1.0, 3.0))
            pygame.draw.circle(screen, (255, 190, 110), (int(x), int(y)), size)
            pygame.draw.circle(screen, (255, 80, 40), (int(x), int(y)), max(1, size - 1))

            # Tail (screen-space)
            L = clamp(180.0 / cam[2], 6.0, 26.0)
            pygame.draw.aaline(screen, (255, 110, 70), (x, y + L * 0.55), (x, y + L))

# ----------------------------
# Ship (quaternion rotation + full 6DOF translation)
# ----------------------------

class Ship:
    def __init__(self):
        # Quaternion is the authoritative orientation. Legacy Euler values are
        # retained only for old save/surface-state compatibility.
        self.orientation = quat_identity()
        self.yaw = 0.0
        self.pitch = 0.0
        self.roll = 0.0

        self.yaw_rate = 0.0
        self.pitch_rate = 0.0
        self.roll_rate = 0.0

        self.pos = SYSTEM_SPAWN_POSITION
        self.vel = (0.0, 0.0, 0.0)

        self.speed = 0.0
        self.speed_norm = 0.0

        self.hyperspace = False
        self.hyper_t = 0.0
        self.hyper_cooldown = 0.0

        self.heat = 0.15
        self.power = 0.85
        self.shield = 0.95

        self.boost_norm = 0.0
        self.hyper_norm = 0.0
        self.dist_to_planet = 0.0
        self.local_clearance = 0.0
        # Boost fuel system (capacity can be increased via planet-surface rock resources)
        self.boost_cap = 6        # max boost "units"
        self.boost_fuel = 6.0     # current fuel (float for smooth drain)

        # --- Persistent ship resources / stats (used by terrains.py + interiors.py) ---
        self.cargo = {}            # ship storage (dict[str,int])
        self.player_pack = {}      # player inventory while on foot (dict[str,int])
        self.consumables = {}      # planet pickups (dict[str,int]) e.g. "medkit:rare" -> 2

        self.fuel_max = 100
        self.fuel = 60
        self.fuel_quality = 0.50   # 0..1, improves warp distance and efficiency

        self.hull_hp_max = 100
        self.hull_hp = 100

        self.player_hp_max = 100
        self.player_hp = 100

        self.state_dirty = False
        self.flight_assist = True
        self.upgrade_levels = {"warp": 0, "scanner": 0, "hull": 0, "surface": 0}
        self.shield_recharge_rate = 0.70
        self._loaded_mission_data = None
        self.system_checkpoint = None
        self.surface_harvests = {}
        ensure_progression(self)

    def set_orientation(self, orientation):
        self.orientation = quat_normalize(tuple(float(v) for v in orientation))

    def restore_orientation(self, state):
        if isinstance(state, dict):
            orientation = state.get("orientation")
            if is_quaternion(orientation):
                self.set_orientation(orientation)
                return
            self.yaw = float(state.get("yaw", self.yaw))
            self.pitch = float(state.get("pitch", self.pitch))
            self.roll = float(state.get("roll", self.roll))
            self.orientation = quat_from_ypr(self.yaw, self.pitch, self.roll)

    def forward_right_up(self):
        fwd = quat_rotate_normalized(self.orientation, (0.0, 0.0, 1.0))
        right = quat_rotate_normalized(self.orientation, (1.0, 0.0, 0.0))
        up = quat_rotate_normalized(self.orientation, (0.0, -1.0, 0.0))
        return (vec3_norm(fwd), vec3_norm(right), vec3_norm(up))

    def update(self, dt, inp):
        # True six-degree-of-freedom local-axis rotation. Mouse movement creates
        # angular velocity, then yaw/pitch/roll deltas are composed into the
        # quaternion. There is intentionally no pitch clamp.
        safe_dt = max(1.0 / 500.0, dt)
        mouse_sensitivity = 0.0026
        target_yaw_rate = inp.mouse_dx * mouse_sensitivity / safe_dt
        target_pitch_rate = inp.mouse_dy * mouse_sensitivity / safe_dt

        self.yaw_rate = lerp(self.yaw_rate, target_yaw_rate, clamp(dt * 16.0, 0.0, 1.0))
        self.pitch_rate = lerp(self.pitch_rate, target_pitch_rate, clamp(dt * 16.0, 0.0, 1.0))

        roll_input = float(getattr(inp, "roll_axis", 0.0))
        if abs(roll_input) < 1e-5:
            roll_input = (1.0 if inp.roll_right else 0.0) - (1.0 if inp.roll_left else 0.0)
        if inp.roll_mouse:
            roll_input = clamp(inp.mouse_dx * 0.010, -1.0, 1.0)
            self.yaw_rate *= 0.30
        self.roll_rate = lerp(self.roll_rate, roll_input * 1.9, clamp(dt * 12.0, 0.0, 1.0))

        yaw_delta = self.yaw_rate * dt
        pitch_delta = self.pitch_rate * dt
        roll_delta = self.roll_rate * dt

        local_yaw = quat_from_axis_angle((0.0, 1.0, 0.0), yaw_delta)
        local_pitch = quat_from_axis_angle((1.0, 0.0, 0.0), pitch_delta)
        local_roll = quat_from_axis_angle((0.0, 0.0, 1.0), roll_delta)
        local_delta = quat_mul(quat_mul(local_yaw, local_pitch), local_roll)
        self.orientation = quat_normalize(quat_mul(self.orientation, local_delta))

        # Compatibility telemetry only. Rendering and movement never depend on
        # these Euler accumulators.
        self.yaw = wrap_angle(self.yaw + yaw_delta)
        self.pitch = wrap_angle(self.pitch + pitch_delta)
        self.roll = wrap_angle(self.roll + roll_delta)

        fwd, right, up = self.forward_right_up()

        # Boost fuel: keep INFINITE for now (user request), while still allowing capacity upgrades.
        # We retain boost_cap as the upgradable stat, but we do not drain boost_fuel.
        want_boost = bool(inp.boost and not self.hyperspace)
        boost = 1.0 if want_boost else 0.0
        self.boost_fuel = float(self.boost_cap)


        if inp.hyper and (not self.hyperspace) and self.hyper_cooldown <= 0.0:
            self.hyperspace = True
            self.hyper_t = 0.0
            self.hyper_cooldown = 2.8

        if self.hyper_cooldown > 0.0:
            self.hyper_cooldown = max(0.0, self.hyper_cooldown - dt)

        if self.hyperspace:
            self.hyper_t += dt
            accel = 1750.0
            if self.hyper_t >= 1.85:
                self.hyperspace = False
        else:
            # Precision thrust near major bodies; high-speed interplanetary cruise
            # only engages in open space so expanded systems remain practical.
            clearance = max(0.0, float(getattr(self, "local_clearance", 0.0)))
            cruise = smoothstep(clamp((clearance - 6500.0) / 18000.0, 0.0, 1.0))
            accel = lerp(120.0, lerp(560.0, 4200.0, cruise), boost)

        # True 6DOF translation along the spacecraft's local axes.
        thrust_fb = float(getattr(inp, "thrust_axis", 0.0))
        strafe_lr = float(getattr(inp, "strafe_axis", 0.0))
        vertical = float(getattr(inp, "vertical_axis", 0.0))
        if abs(thrust_fb) < 1e-5:
            thrust_fb = (1.0 if inp.thrust_forward else 0.0) - (1.0 if inp.thrust_reverse else 0.0)
        if abs(strafe_lr) < 1e-5:
            strafe_lr = (1.0 if inp.strafe_right else 0.0) - (1.0 if inp.strafe_left else 0.0)
        if abs(vertical) < 1e-5:
            vertical = (1.0 if inp.vertical_up else 0.0) - (1.0 if inp.vertical_down else 0.0)

        local_thrust = vec3_add(
            vec3_add(vec3_mul(fwd, thrust_fb), vec3_mul(right, strafe_lr)),
            vec3_mul(up, vertical),
        )
        local_thrust = vec3_norm(local_thrust)

        vx, vy, vz = self.vel
        thrust_accel = accel if not self.hyperspace else 1750.0
        tv = vec3_mul(local_thrust, thrust_accel)
        vx += tv[0] * dt
        vy += tv[1] * dt
        vz += tv[2] * dt

        if inp.brake:
            brake_blend = clamp(dt * 4.8, 0.0, 1.0)
            vx = lerp(vx, 0.0, brake_blend)
            vy = lerp(vy, 0.0, brake_blend)
            vz = lerp(vz, 0.0, brake_blend)
        elif self.flight_assist and not self.hyperspace:
            # Light dampers make release-to-coast controllable without forcing the
            # ship back onto an arbitrary world axis or mandatory cruise speed.
            clearance = max(0.0, float(getattr(self, "local_clearance", 0.0)))
            approach = 1.0 - smoothstep(clamp(clearance / 9000.0, 0.0, 1.0))
            assist_rate = lerp(0.34, 1.15, approach)
            assist_blend = clamp(dt * assist_rate, 0.0, 1.0)
            vx = lerp(vx, 0.0, assist_blend)
            vy = lerp(vy, 0.0, assist_blend)
            vz = lerp(vz, 0.0, assist_blend)
        elif self.hyperspace:
            # Warp remains locked to the entry heading and adds forward drive.
            hv = vec3_mul(fwd, thrust_accel)
            vx += hv[0] * dt
            vy += hv[1] * dt
            vz += hv[2] * dt

        self.vel = (vx, vy, vz)
        self.pos = vec3_add(self.pos, vec3_mul(self.vel, dt))

        self.speed = vec3_len(self.vel)
        self.speed_norm = clamp(self.speed / 9000.0, 0.0, 1.0)

        self.boost_norm = boost
        self.hyper_norm = 1.0 if self.hyperspace else clamp(1.0 - self.hyper_cooldown / 2.8, 0.0, 1.0)

        target_heat = 0.15 + (0.70 if self.hyperspace else 0.30 * boost)
        self.heat = clamp(lerp(self.heat, target_heat, clamp(dt * 1.2, 0.0, 1.0)), 0.0, 1.0)
        self.power = clamp(lerp(self.power, 0.90 - (0.28 if self.hyperspace else 0.12 * boost), clamp(dt * 0.8, 0.0, 1.0)), 0.0, 1.0)
        self.shield = clamp(lerp(self.shield, 0.95, clamp(dt * float(getattr(self, "shield_recharge_rate", 0.70)), 0.0, 1.0)), 0.0, 1.0)

    def take_hull_damage(self, amount: float) -> int:
        amount = max(0.0, float(amount))
        if amount <= 0.0:
            return int(self.hull_hp)
        self.hull_hp = max(0, int(self.hull_hp) - max(1, int(round(amount))))
        self.state_dirty = True
        return int(self.hull_hp)

    def _checkpoint_ship_state(self) -> dict:
        return {
            "cargo": dict(self.cargo),
            "player_pack": dict(self.player_pack),
            "consumables": dict(self.consumables),
            "fuel": int(self.fuel),
            "fuel_max": int(self.fuel_max),
            "fuel_quality": float(self.fuel_quality),
            "hull_hp": int(self.hull_hp),
            "hull_hp_max": int(self.hull_hp_max),
            "player_hp": int(self.player_hp),
            "player_hp_max": int(self.player_hp_max),
            "boost_cap": int(self.boost_cap),
            "flight_assist": bool(self.flight_assist),
            "upgrade_levels": dict(getattr(self, "upgrade_levels", {})),
            "surface_harvests": normalize_harvest_map(getattr(self, "surface_harvests", {})),
            "pos": [float(v) for v in self.pos],
            "vel": [float(v) for v in self.vel],
            "orientation": [float(v) for v in self.orientation],
        }

    def capture_system_checkpoint(self, mission) -> dict:
        self.system_checkpoint = {
            "checkpoint_version": 1,
            "ship": self._checkpoint_ship_state(),
            "mission": mission.to_dict(),
        }
        self.state_dirty = True
        return dict(self.system_checkpoint)

    def restore_system_checkpoint(self):
        checkpoint = self.system_checkpoint if isinstance(self.system_checkpoint, dict) else None
        if not checkpoint or not isinstance(checkpoint.get("ship"), dict):
            return None
        state = checkpoint["ship"]
        for key in ("cargo", "player_pack", "consumables"):
            if isinstance(state.get(key), dict):
                setattr(self, key, dict(state[key]))
        for key in ("fuel", "fuel_max", "hull_hp", "hull_hp_max", "player_hp", "player_hp_max", "boost_cap"):
            if key in state:
                setattr(self, key, int(state[key]))
        if "fuel_quality" in state:
            self.fuel_quality = float(state["fuel_quality"])
        if "flight_assist" in state:
            self.flight_assist = bool(state["flight_assist"])
        if isinstance(state.get("upgrade_levels"), dict):
            self.upgrade_levels = dict(state["upgrade_levels"])
        self.surface_harvests = normalize_harvest_map(state.get("surface_harvests", {}))
        if isinstance(state.get("pos"), (list, tuple)) and len(state["pos"]) == 3:
            self.pos = tuple(float(v) for v in state["pos"])
        if isinstance(state.get("vel"), (list, tuple)) and len(state["vel"]) == 3:
            self.vel = tuple(float(v) for v in state["vel"])
        if is_quaternion(state.get("orientation")):
            self.set_orientation(state["orientation"])
        self.hyperspace = False
        self.hyper_t = 0.0
        self.hyper_cooldown = 0.0
        ensure_progression(self)
        self.state_dirty = True
        mission_data = checkpoint.get("mission")
        return dict(mission_data) if isinstance(mission_data, dict) else None


# ----------------------------
# Inputs
# ----------------------------

    # -------------------------
    # Persistence (lightweight)
    # -------------------------
    def save_state(self, path: str = None, reason: str = "autosave"):
        """Crash-resistant save in the per-user data directory.

        The runtime layer publishes through a validated previous-good generation;
        this method adds lightweight provenance without changing schema v5.
        """
        try:
            data = {
                "schema_version": 5,
                "save_meta": {
                    "build": APP_VERSION,
                    "reason": str(reason),
                    "saved_at_unix": float(time.time()),
                },
                "cargo": self.cargo,
                "player_pack": self.player_pack,
                "consumables": self.consumables,
                "fuel": int(self.fuel),
                "fuel_max": int(self.fuel_max),
                "fuel_quality": float(self.fuel_quality),
                "hull_hp": int(self.hull_hp),
                "hull_hp_max": int(self.hull_hp_max),
                "player_hp": int(self.player_hp),
                "player_hp_max": int(self.player_hp_max),
                "boost_cap": int(self.boost_cap),
                "flight_assist": bool(self.flight_assist),
                "upgrade_levels": dict(getattr(self, "upgrade_levels", {})),
                "surface_harvests": normalize_harvest_map(getattr(self, "surface_harvests", {})),
                "mission": getattr(getattr(self, "mission_state", None), "to_dict", lambda: None)(),
                "system_checkpoint": self.system_checkpoint,
            }
            target = None if path is None else __import__("pathlib").Path(path)
            write_save(data, path=target)
            self.state_dirty = False
            if path is None:
                try:
                    mark_session_checkpoint(str(reason))
                except Exception:
                    pass
            return True
        except Exception:
            log("WARN: save failed\n" + traceback.format_exc())
            return False

    def load_state(self, path: str = None):
        """Best-effort load from the standardized per-user save location."""
        try:
            target = None if path is None else __import__("pathlib").Path(path)
            data = read_save(path=target)
            if isinstance(data.get("cargo"), dict): self.cargo = data["cargo"]
            if isinstance(data.get("player_pack"), dict): self.player_pack = data["player_pack"]
            if isinstance(data.get("consumables"), dict): self.consumables = data["consumables"]
            if "fuel" in data: self.fuel = int(data["fuel"])
            if "fuel_max" in data: self.fuel_max = int(data["fuel_max"])
            if "fuel_quality" in data: self.fuel_quality = float(data["fuel_quality"])
            if "hull_hp" in data: self.hull_hp = int(data["hull_hp"])
            if "hull_hp_max" in data: self.hull_hp_max = int(data["hull_hp_max"])
            if "player_hp" in data: self.player_hp = int(data["player_hp"])
            if "player_hp_max" in data: self.player_hp_max = int(data["player_hp_max"])
            if "boost_cap" in data: self.boost_cap = int(data["boost_cap"])
            if "flight_assist" in data: self.flight_assist = bool(data["flight_assist"])
            if isinstance(data.get("upgrade_levels"), dict): self.upgrade_levels = dict(data["upgrade_levels"])
            self.surface_harvests = normalize_harvest_map(data.get("surface_harvests", {}))
            self._loaded_mission_data = data.get("mission") if isinstance(data.get("mission"), dict) else None
            self.system_checkpoint = data.get("system_checkpoint") if isinstance(data.get("system_checkpoint"), dict) else None
            ensure_progression(self)
        except Exception:
            log("WARN: save load failed\n" + traceback.format_exc())



class Inputs:
    def __init__(self):
        self.mouse_dx = 0.0
        self.mouse_dy = 0.0
        self.roll_mouse = False

        # translation
        self.thrust_forward = False
        self.thrust_reverse = False
        self.strafe_left = False
        self.strafe_right = False
        self.vertical_up = False
        self.vertical_down = False
        self.brake = False

        self.roll_left = False
        self.roll_right = False

        self.boost = False
        self.hyper = False
        self.fire = False

        self.quit = False
        self.pause_toggle = False
        self.interact = False

        # Analog controller channels. Keyboard remains authoritative when used;
        # these values are added by the SDL controller provider when connected.
        self.thrust_axis = 0.0
        self.strafe_axis = 0.0
        self.vertical_axis = 0.0
        self.roll_axis = 0.0


# ----------------------------
# Black Hole + Planet Devour Simulation
# ----------------------------

@dataclass
class DevourParticle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    col: tuple


def project_sphere(w, h, ship_pos, yaw, pitch, roll, pos_world, k_px=240000.0, min_z=10.0):
    """Project a world-space point as a screen-space sphere; returns (visible,(sx,sy),radius_px)."""
    rel = vec3_sub(pos_world, ship_pos)
    cam = apply_inv_ypr(rel, yaw, pitch, roll)
    if cam[2] <= min_z:
        return (False, (0.0, 0.0), 0)
    cx, cy = w * 0.5, h * 0.5
    fov = 86.0
    f = (w * 0.5) / math.tan(math.radians(fov) * 0.5)
    sx = cam[0] * f / cam[2] + cx
    sy = cam[1] * f / cam[2] + cy
    radius_px = int(clamp(k_px / cam[2], 4, min(w, h) * 0.75))
    if sx < -radius_px or sx > w + radius_px or sy < -radius_px or sy > h + radius_px:
        return (False, (0.0, 0.0), 0)
    return (True, (sx, sy), radius_px)


def project_world_point(w, h, cam_pos, yaw, pitch, roll, pos_world, min_z=0.2):
    rel = vec3_sub(pos_world, cam_pos)
    cam = apply_inv_ypr(rel, yaw, pitch, roll)
    if cam[2] <= min_z:
        return None
    cx, cy = w * 0.5, h * 0.5
    fov = 86.0
    f = (w * 0.5) / math.tan(math.radians(fov) * 0.5)
    sx = cam[0] * f / cam[2] + cx
    sy = cam[1] * f / cam[2] + cy
    return (sx, sy, cam[2])


def _mix_rgb(a, b, t):
    t = clamp(t, 0.0, 1.0)
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def _scale_rgb(col, scale):
    return (
        int(clamp(col[0] * scale, 0, 255)),
        int(clamp(col[1] * scale, 0, 255)),
        int(clamp(col[2] * scale, 0, 255)),
    )


def _poly_centroid(poly):
    if not poly:
        return (0.0, 0.0)
    sx = sum(p[0] for p in poly)
    sy = sum(p[1] for p in poly)
    inv = 1.0 / len(poly)
    return (sx * inv, sy * inv)


def _inset_polygon(poly, scale=0.84):
    cx, cy = _poly_centroid(poly)
    return [(cx + (px - cx) * scale, cy + (py - cy) * scale) for (px, py) in poly]


def _polygon_radius(poly, center=None):
    if center is None:
        center = _poly_centroid(poly)
    return max(1.0, max(math.hypot(px - center[0], py - center[1]) for (px, py) in poly))


def _draw_fractured_polygon(screen, poly, base_col, edge_col, glow_col, tsec, phase=0.0, core_bias=0.0):
    if len(poly) < 3:
        return
    center = _poly_centroid(poly)
    radius = _polygon_radius(poly, center)
    pulse = 0.5 + 0.5 * math.sin(tsec * 2.6 + phase)
    deep = _mix_rgb(base_col, (10, 10, 18), 0.38)
    rim = _mix_rgb(base_col, glow_col, 0.16 + pulse * 0.08)
    inner = _inset_polygon(poly, 0.82)
    core = _inset_polygon(poly, 0.62)

    pygame.draw.polygon(screen, deep, poly)
    n = len(poly)
    for i in range(n):
        next_i = (i + 1) % n
        quad = [poly[i], poly[next_i], inner[next_i], inner[i]]
        band_mix = 0.10 + 0.08 * ((i + int(phase * 3.0)) % 2) + pulse * 0.08
        band_col = _mix_rgb(base_col, glow_col, band_mix)
        pygame.draw.polygon(screen, band_col, quad)

        mid_outer = ((poly[i][0] + poly[next_i][0]) * 0.5, (poly[i][1] + poly[next_i][1]) * 0.5)
        mid_inner = ((inner[i][0] + inner[next_i][0]) * 0.5, (inner[i][1] + inner[next_i][1]) * 0.5)
        fracture_t = 0.48 + 0.10 * math.sin(tsec * 1.5 + phase + i * 1.23)
        fracture_pt = (
            center[0] + (mid_outer[0] - center[0]) * fracture_t,
            center[1] + (mid_outer[1] - center[1]) * fracture_t,
        )
        line_col = _mix_rgb(edge_col, glow_col, 0.45 + 0.18 * pulse)
        pygame.draw.aaline(screen, line_col, center, fracture_pt)
        pygame.draw.aaline(screen, _mix_rgb(edge_col, glow_col, 0.25), mid_inner, mid_outer)

    core_col = _mix_rgb(base_col, glow_col, 0.16 + pulse * (0.14 + core_bias * 0.08))
    pygame.draw.polygon(screen, core_col, core)
    pygame.draw.polygon(screen, edge_col, poly, 2)
    pygame.draw.polygon(screen, _mix_rgb(edge_col, glow_col, 0.36), inner, 1)

    if radius > 12.0:
        gem = max(2, int(radius * 0.12))
        glow_ring = _mix_rgb(glow_col, (255, 255, 255), 0.25 + pulse * 0.15)
        pygame.draw.circle(screen, glow_ring, (int(center[0]), int(center[1])), gem)
        pygame.draw.circle(screen, (255, 255, 255), (int(center[0]), int(center[1])), max(1, gem // 2))


def draw_third_person_ship(screen, w, h, cam_pos, yaw, pitch, roll, ship, tsec):
    body = [(-4.8, -1.0, -15.0), (0.0, -0.2, 20.0), (4.8, -1.0, -15.0), (0.0, 1.8, -7.0)]
    left_wing = [(-20.0, 1.0, -8.0), (-5.2, 0.1, -6.0), (-4.2, -0.1, 5.5), (-22.0, 1.8, 2.5)]
    right_wing = [(20.0, 1.0, -8.0), (5.2, 0.1, -6.0), (4.2, -0.1, 5.5), (22.0, 1.8, 2.5)]
    tail = [(-3.4, -0.3, -18.5), (3.4, -0.3, -18.5), (0.0, 8.4, -14.0)]
    canopy = [(-2.3, -0.3, 1.8), (0.0, -1.8, 7.6), (2.3, -0.3, 1.8), (0.0, 0.3, -1.4)]
    fin_l = [(-1.2, -1.0, -6.0), (-0.1, -2.0, 4.5), (-0.1, -0.7, 10.0), (-1.5, 0.2, 0.0)]
    fin_r = [(1.2, -1.0, -6.0), (0.1, -2.0, 4.5), (0.1, -0.7, 10.0), (1.5, 0.2, 0.0)]
    engine_l = (-6.4, 0.4, -15.8)
    engine_r = (6.4, 0.4, -15.8)
    spine_nodes = [(0.0, -0.5, 12.0), (0.0, -0.2, 5.0), (0.0, 0.2, -3.0), (0.0, 0.5, -11.0)]
    wing_emitters = [(-10.0, 0.5, -2.5), (10.0, 0.5, -2.5)]

    default_glow = (88, 255, 242)
    accent_glow = (255, 92, 196)
    if ship.hyperspace:
        default_glow = (255, 196, 96)
        accent_glow = (255, 112, 208)

    face_defs = [
        ('body', body, (44, 36, 70), (168, 236, 255), default_glow, 0.10, 0.25),
        ('left_wing', left_wing, (22, 34, 66), (148, 244, 255), accent_glow, 0.40, 0.10),
        ('right_wing', right_wing, (22, 34, 66), (148, 244, 255), accent_glow, 0.65, 0.10),
        ('tail', tail, (58, 28, 74), (190, 150, 255), accent_glow, 0.90, 0.18),
        ('canopy', canopy, (28, 58, 84), (186, 255, 255), default_glow, 1.20, 0.38),
        ('fin_l', fin_l, (42, 20, 76), (182, 124, 255), accent_glow, 1.46, 0.16),
        ('fin_r', fin_r, (42, 20, 76), (182, 124, 255), accent_glow, 1.72, 0.16),
    ]

    projected = []
    for name, verts, base_col, edge_col, glow_col, phase, core_bias in face_defs:
        world_pts = [vec3_add(ship.pos, apply_ypr(v, ship.orientation, 0.0, 0.0)) for v in verts]
        poly = []
        ok = True
        zsum = 0.0
        for wp in world_pts:
            pr = project_world_point(w, h, cam_pos, yaw, pitch, roll, wp, min_z=0.2)
            if pr is None:
                ok = False
                break
            poly.append((pr[0], pr[1]))
            zsum += pr[2]
        if ok:
            projected.append((zsum / len(world_pts), name, poly, base_col, edge_col, glow_col, phase, core_bias))

    if not projected:
        return

    projected.sort(reverse=True, key=lambda item: item[0])
    for _depth, _name, poly, base_col, edge_col, glow_col, phase, core_bias in projected:
        _draw_fractured_polygon(screen, poly, base_col, edge_col, glow_col, tsec, phase=phase, core_bias=core_bias)

    # Fractured spine running down the hull.
    projected_nodes = []
    for node in spine_nodes:
        wp = vec3_add(ship.pos, apply_ypr(node, ship.orientation, 0.0, 0.0))
        pr = project_world_point(w, h, cam_pos, yaw, pitch, roll, wp, min_z=0.2)
        if pr is not None:
            projected_nodes.append(pr)
    if len(projected_nodes) >= 2:
        spine_col = _mix_rgb(default_glow, accent_glow, 0.45 + 0.15 * math.sin(tsec * 2.2))
        for i in range(len(projected_nodes) - 1):
            p0 = projected_nodes[i]
            p1 = projected_nodes[i + 1]
            pygame.draw.aaline(screen, _mix_rgb(spine_col, (255, 255, 255), 0.25), (p0[0], p0[1]), (p1[0], p1[1]))
            gem_r = max(1, int(clamp(180.0 / ((p0[2] + p1[2]) * 0.5), 1.0, 4.0)))
            pygame.draw.circle(screen, spine_col, (int(p0[0]), int(p0[1])), gem_r + 1)
            pygame.draw.circle(screen, (255, 255, 255), (int(p0[0]), int(p0[1])), gem_r)

    # Wing emitters / dimensional cracks.
    crack_phase = 0.5 + 0.5 * math.sin(tsec * 3.0)
    for emitter in wing_emitters:
        wp = vec3_add(ship.pos, apply_ypr(emitter, ship.orientation, 0.0, 0.0))
        pr = project_world_point(w, h, cam_pos, yaw, pitch, roll, wp, min_z=0.2)
        if pr is None:
            continue
        r = int(clamp(180.0 / pr[2], 2.0, 7.0))
        glow = _mix_rgb(accent_glow, default_glow, crack_phase)
        pygame.draw.circle(screen, glow, (int(pr[0]), int(pr[1])), r)
        pygame.draw.circle(screen, (255, 255, 255), (int(pr[0]), int(pr[1])), max(1, r // 2))

    # Engine glows and boost trails.
    for eng in (engine_l, engine_r):
        wp = vec3_add(ship.pos, apply_ypr(eng, ship.orientation, 0.0, 0.0))
        pr = project_world_point(w, h, cam_pos, yaw, pitch, roll, wp, min_z=0.2)
        if pr is None:
            continue
        r = int(clamp(180.0 / pr[2], 2.0, 10.0))
        core_col = _mix_rgb(default_glow, (255, 255, 255), 0.28)
        shell_col = _mix_rgb(accent_glow, default_glow, 0.55)
        pygame.draw.circle(screen, shell_col, (int(pr[0]), int(pr[1])), r + 2)
        pygame.draw.circle(screen, core_col, (int(pr[0]), int(pr[1])), r)
        pygame.draw.circle(screen, (255, 255, 255), (int(pr[0]), int(pr[1])), max(1, r // 2))
        if ship.boost_norm > 0.05 or ship.hyperspace:
            trail_len = clamp(340.0 / pr[2], 8.0, 26.0) * (1.0 + ship.boost_norm * 1.25 + (0.6 if ship.hyperspace else 0.0))
            trail_tip = (pr[0], pr[1] + trail_len)
            pygame.draw.aaline(screen, shell_col, (pr[0], pr[1]), trail_tip)
            pygame.draw.aaline(screen, _mix_rgb(core_col, (255, 255, 255), 0.40), (pr[0], pr[1]), (pr[0], pr[1] + trail_len * 0.72))


class BlackHole:

    """
    World-space black hole visual (screen-space render):
    - Draws an event horizon at a projected world position
    - Rotating accretion disk
    - If engaged (near a target planet), pulls sampled planet pixels toward the sink
      and reveals a hot core glow.
    """
    def __init__(self, seed=42):
        self.t = 0.0               # "devour time" (only advances when engaged)
        self.disk_phase = 0.0
        self.rng = random.Random(seed)
        self.parts = []

    def reset(self):
        self.t = 0.0
        self.disk_phase = 0.0
        self.parts.clear()

    def update(self, dt, engaged: bool):
        # disk always animates (so it looks alive even when not eating)
        self.disk_phase += dt * 1.35
        if engaged:
            self.t += dt

        nxt = []
        for p in self.parts:
            p.life -= dt
            if p.life <= 0.0:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            nxt.append(p)
        self.parts = nxt

    def _spawn_from_planet(self, planet_surf, planet_center, planet_radius, sink_center):
        if planet_surf is None:
            return
        w, h = planet_surf.get_size()

        pcx, pcy = planet_center
        scx, scy = sink_center

        px0 = pcx - w * 0.5
        py0 = pcy - h * 0.5

        strength = clamp(self.t / 10.0, 0.0, 1.0)
        n = int(40 + 360 * strength)

        for _ in range(n):
            sx = self.rng.randrange(0, w)
            sy = self.rng.randrange(0, h)
            col = planet_surf.get_at((sx, sy))
            if col.a < 50:
                continue

            wx = px0 + sx
            wy = py0 + sy

            dxp = wx - pcx
            dyp = wy - pcy
            if (dxp * dxp + dyp * dyp) > (planet_radius * 1.02) ** 2:
                continue

            dx = scx - wx
            dy = scy - wy
            dist = math.hypot(dx, dy) + 1e-6

            pull = (140.0 + 520.0 * strength) / max(18.0, dist)
            vx = dx * pull
            vy = dy * pull
            life = self.rng.uniform(0.35, 1.10) * (0.6 + 0.7 * strength)
            self.parts.append(DevourParticle(wx, wy, vx, vy, life, (col.r, col.g, col.b, 200)))

        if len(self.parts) > 9000:
            self.parts = self.parts[-9000:]

    def draw(self, screen, sink_center, eh_radius_px, engaged=False, planet_surf=None, planet_center=None, planet_radius_px=0):
        scx, scy = int(sink_center[0]), int(sink_center[1])
        strength = clamp(self.t / 10.0, 0.0, 1.0)

        if engaged and (planet_surf is not None) and (planet_center is not None) and (planet_radius_px > 0):
            self._spawn_from_planet(planet_surf, planet_center, planet_radius_px, (scx, scy))

        if self.parts:
            for p in self.parts:
                dx = p.x - scx
                dy = p.y - scy
                dist = math.hypot(dx, dy) + 1e-6
                if dist < eh_radius_px * 1.6:
                    col = (255, 110, 70, 220)
                else:
                    col = p.col
                pygame.draw.circle(screen, col, (int(p.x), int(p.y)), 1)

        disk = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        tilt = 0.45
        outer = int(eh_radius_px * 2.6)
        inner = int(eh_radius_px * 1.15)
        rings = 7

        for r_i in range(rings):
            rr = lerp(inner, outer, r_i / max(1, rings - 1))
            a = int(22 + 46 * (r_i / max(1, rings - 1)))
            col = (255, int(170 - 50 * (r_i / rings)), int(90 - 40 * (r_i / rings)), a)
            pts = []
            seg = 90
            ph = self.disk_phase * (1.0 + 0.25 * r_i)
            for k in range(seg):
                ang = (k / seg) * math.tau + ph
                x = scx + math.cos(ang) * rr
                y = scy + math.sin(ang) * rr * tilt
                pts.append((x, y))
            pygame.draw.aalines(disk, col, True, pts)

        screen.blit(disk, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        pygame.draw.circle(screen, (0, 0, 0), (scx, scy), max(3, eh_radius_px))

        if engaged and strength > 0.12:
            core_r = int(eh_radius_px * (0.55 + 0.65 * strength))
            glow = pygame.Surface((core_r * 6, core_r * 6), pygame.SRCALPHA)
            for r in range(core_r * 3, 0, -1):
                aa = int(140 * (r / (core_r * 3)) * (0.25 + 0.75 * strength))
                pygame.draw.circle(glow, (255, 80, 40, aa), (core_r * 3, core_r * 3), r)
            screen.blit(glow, (scx - core_r * 3, scy - core_r * 3), special_flags=pygame.BLEND_RGBA_ADD)

        shadow_r = int(max(12, eh_radius_px * 3.0))
        sh = pygame.Surface((shadow_r * 2, shadow_r * 2), pygame.SRCALPHA)
        for r in range(shadow_r, 0, -1):
            aa = int(90 * (1.0 - r / shadow_r) * (0.35 + 0.65 * (strength if engaged else 0.15)))
            pygame.draw.circle(sh, (0, 0, 0, aa), (shadow_r, shadow_r), r)
        screen.blit(sh, (scx - shadow_r, scy - shadow_r))

# ----------------------------
# Main
# ----------------------------

def _parse_launch_args(argv=None):
    parser = argparse.ArgumentParser(description="Entropy launch and verification options")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    parser.add_argument("--no-audio", action="store_true", help="Disable mixer initialization and audio playback")
    parser.add_argument("--inherit-display", action="store_true", help="Adopt an already-active pygame display supplied by another GX mode")
    parser.add_argument("--smoke-test", action="store_true", help="Run a bounded automated launch and exit cleanly")
    parser.add_argument("--test-shot", metavar="PATH", help="Save a deterministic in-engine screenshot and exit")
    parser.add_argument("--test-suite-dir", metavar="DIR", help="Capture space, cockpit and ship-interior states in one launch")
    parser.add_argument(
        "--test-state",
        choices=("space", "mission-space", "mission-brief", "run-start", "home", "ship-recovery", "campaign-complete", "cockpit", "orbital-far", "orbital-mid", "orbital-close", "interior", "surface", "recovery-surface", "recovery-relic", "recovery-deposit", "recovery-secured", "collapse-critical", "collapse-failure"),
        default="space",
        help="State used by --test-shot",
    )
    parser.add_argument("--test-seed", type=int, default=7, help="Deterministic planetary test seed")
    parser.add_argument("--test-biome", choices=("desert", "ice", "jungle", "volcanic", "crystal", "oceanic", "fungal", "rust", "salt", "abyss", "storm", "roseglass"), help="Force a world class for deterministic surface verification")
    parser.add_argument("--test-overlay", choices=("none", "pause", "settings", "controls", "hud-off"), default="none", help="Overlay used by deterministic visual verification")
    args, _unknown = parser.parse_known_args(argv)
    return args


def main(argv=None):
    args = _parse_launch_args(argv)
    verification_mode = bool(args.test_shot or args.test_suite_dir or args.smoke_test)
    if not verification_mode:
        crash_reporter.install(APP_VERSION)
    session_info = mark_session_started(APP_VERSION, verification=verification_mode)
    previous_session_unclean = bool(session_info.get("previous_unclean", False))
    ensure_sfx_folders()
    ensure_ambient_assets()

    # Ask SDL for true physical pixels on high-DPI Windows displays. These
    # hints must be set before display initialization.
    os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
    os.environ.setdefault("SDL_HINT_WINDOWS_DPI_AWARENESS", "permonitorv2")
    os.environ.setdefault("SDL_VIDEO_HIGHDPI_DISABLED", "0")
    os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
    pygame.init()
    gamepad = ControllerInput()

    # -------------------------------------------------
    # Window + virtual canvas (NON-NEGOTIABLE behavior)
    # -------------------------------------------------
    # - Render/simulate at fixed 1920x1080 every frame
    # - Present to a resizable OS window via cover scaling
    settings = load_settings()
    info = pygame.display.Info()
    desk_w, desk_h = int(info.current_w), int(info.current_h)
    target_w = int(settings.get("target_width", 1920))
    target_h = int(settings.get("target_height", 1080))
    requested_window_mode = str(settings.get("window_mode", "fullscreen"))

    def open_display(mode: str, requested_size=None):
        native_ok = desk_w >= target_w and desk_h >= target_h
        if mode == "fullscreen":
            # Borderless desktop fullscreen: cover the current desktop without
            # asking SDL/Windows to switch the monitor's display resolution.
            size = (desk_w, desk_h)
            flags = pygame.NOFRAME | pygame.DOUBLEBUF
            actual_mode = "fullscreen"
        elif mode == "native_1080p" and native_ok:
            size = (target_w, target_h)
            flags = pygame.NOFRAME | pygame.DOUBLEBUF
            actual_mode = "native_1080p"
        else:
            saved_size = (
                max(960, int(settings.get("bordered_width", 1600))),
                max(540, int(settings.get("bordered_height", 900))),
            )
            size = requested_size or saved_size
            if size[0] > desk_w or size[1] > desk_h:
                size = fit_window_16_9(desk_w, desk_h, target_w, target_h)
            flags = pygame.RESIZABLE | pygame.DOUBLEBUF
            actual_mode = "bordered"
        try:
            surface = pygame.display.set_mode(size, flags, vsync=1)
        except TypeError:
            surface = pygame.display.set_mode(size, flags)
        return surface, flags, actual_mode

    inherited_display = pygame.display.get_surface() if args.inherit_display else None
    if inherited_display is not None:
        # Afterlife of IO can hand Entropy its live SDL display. Reusing this
        # Surface avoids a close/reopen flash and preserves the exact host window
        # dimensions. Entropy still renders at fixed 1920x1080 and uses its normal
        # aspect-safe presenter, so a 1280x720/1600x900 host is never stretched.
        display = inherited_display
        import standard_ui as _standard_ui
        _standard_ui.EXIT_LABEL = "RETURN TO AFTERLIFE"
        _standard_ui.FINISH_EXIT_LABEL = "RETURN TO AFTERLIFE"
        window_flags = int(display.get_flags())
        inherited_size = tuple(map(int, display.get_size()))
        inherited_fullscreen = bool(window_flags & pygame.FULLSCREEN)
        inherited_borderless_desktop = bool(
            window_flags & pygame.NOFRAME
            and inherited_size == (desk_w, desk_h)
        )
        active_window_mode = "fullscreen" if (inherited_fullscreen or inherited_borderless_desktop) else "bordered"
        if active_window_mode == "bordered":
            settings["bordered_width"], settings["bordered_height"] = inherited_size
    else:
        display, window_flags, active_window_mode = open_display(requested_window_mode)
    win_w, win_h = display.get_size()

    pygame.display.set_caption(f"{APP_NAME} — {APP_VERSION}")

    # Virtual render surface (game logic uses this size ONLY)
    screen = pygame.Surface((VIRTUAL_W, VIRTUAL_H)).convert()
    w, h = VIRTUAL_W, VIRTUAL_H

    clock = pygame.time.Clock()

    # Cached presenter surface (avoids per-frame allocations on big windows)
    present_cache = {"surf": None, "size": (0, 0)}
    automation = {
        "frames": 0,
        "done": False,
        "shot": os.path.abspath(args.test_shot) if args.test_shot else None,
        "suite_dir": os.path.abspath(args.test_suite_dir) if args.test_suite_dir else None,
        "suite_step": 0,
        "limit": 120 if args.smoke_test and not args.test_shot and not args.test_suite_dir else (4 if args.test_shot else 0),
    }

    def present_cover() -> None:
        """Scale the fixed virtual frame to the OS window without cropping gameplay or HUD."""
        nonlocal third_person_space
        dw, dh = display.get_size()
        if dw <= 0 or dh <= 0:
            return
        scale = min(dw / VIRTUAL_W, dh / VIRTUAL_H)
        tw = max(1, int(VIRTUAL_W * scale))
        th = max(1, int(VIRTUAL_H * scale))
        ox = int((dw - tw) * 0.5)
        oy = int((dh - th) * 0.5)

        # Exact 1:1 presentation is the normal Full-HD path. Windowed fallback
        # uses filtered scaling so text and authored artwork remain clean.
        if (dw, dh) == (VIRTUAL_W, VIRTUAL_H):
            display.blit(screen, (0, 0))
        else:
            if (tw, th) != (dw, dh):
                display.fill((0, 0, 0))
            cache = present_cache["surf"]
            if cache is None or present_cache["size"] != (tw, th):
                cache = pygame.Surface((tw, th)).convert()
                present_cache["surf"] = cache
                present_cache["size"] = (tw, th)
            # Integer upscales (especially 1920x1080 -> 3840x2160 on the
            # user's 4K display) do not need an expensive filtered resample.
            # Exact integer scaling is both sharper and substantially cheaper.
            integer_upscale = (
                tw >= VIRTUAL_W and th >= VIRTUAL_H
                and tw % VIRTUAL_W == 0 and th % VIRTUAL_H == 0
                and (tw // VIRTUAL_W) == (th // VIRTUAL_H)
            )
            transform = pygame.transform.scale if integer_upscale else pygame.transform.smoothscale
            try:
                transform(screen, (tw, th), cache)
                display.blit(cache, (ox, oy))
            except TypeError:
                scaled = transform(screen, (tw, th))
                display.blit(scaled, (ox, oy))

        pygame.display.flip()

        if automation["suite_dir"] and not automation["done"]:
            automation["frames"] += 1
            if automation["frames"] >= 4:
                os.makedirs(automation["suite_dir"], exist_ok=True)
                names = ("space", "cockpit", "interior")
                step = int(automation["suite_step"])
                target = os.path.join(automation["suite_dir"], names[step] + ".png")
                pygame.image.save(screen, target)
                log(f"Verification screenshot: {target}")
                automation["frames"] = 0
                automation["suite_step"] = step + 1
                if step == 0:
                    third_person_space = False
                elif step == 1:
                    globals()["interior_return_mode"] = GAME_MODE_SPACE
                    globals()["game_mode"] = GAME_MODE_INTERIOR
                    _interiors().enter_interior(screen, ship, return_mode=GAME_MODE_SPACE)
                    pygame.event.set_grab(False)
                    pygame.mouse.set_visible(True)
                else:
                    automation["done"] = True
                    pygame.event.post(pygame.event.Event(pygame.QUIT))

        if automation["limit"] > 0 and not automation["done"]:
            automation["frames"] += 1
            if automation["frames"] >= automation["limit"]:
                if automation["shot"]:
                    os.makedirs(os.path.dirname(automation["shot"]) or ".", exist_ok=True)
                    pygame.image.save(screen, automation["shot"])
                    log(f"Verification screenshot: {automation['shot']}")
                automation["done"] = True
                pygame.event.post(pygame.event.Event(pygame.QUIT))

    # Audio scaffold + load
    sfx_root = os.path.join(BASE_DIR, "assets", "sfx", "ship")
    sfx = SFX(sfx_root, enabled=not args.no_audio)
    ambience = AmbientAudio(enabled=bool(sfx.ok) and not args.no_audio)
    log(f"Ambience: surface={len(ambience.surface_sounds)} ruins={len(ambience.ruin_sounds)} ship_hum={bool(ambience.ship_hum)}")

    # Pass 28 state-aware score.  Generated loops are deterministic and the
    # user-supplied MCF24 remains the expedition theme.
    music_root = os.path.join(BASE_DIR, "assets", "music")
    try:
        ensure_score_assets(music_root, force=False)
    except Exception as exc:
        log(f"WARN: state-aware score assets unavailable ({exc}); packaged tracks only.")
    music = MusicPlayer(music_root, enabled=bool(sfx.ok) and not args.no_audio)

    def apply_audio_settings():
        master = clamp(float(settings.get("master_volume", 1.0)), 0.0, 1.0)
        music_level = clamp(float(settings.get("music_volume", 0.85)), 0.0, 1.0)
        sfx_level = clamp(float(settings.get("sfx_volume", 0.95)), 0.0, 1.0)
        ambience_level = clamp(float(settings.get("ambience_volume", 0.80)), 0.0, 1.0)
        muted = bool(settings.get("audio_muted", False))
        sfx.set_mix(master, sfx_level, muted)
        ambience.set_mix(master, ambience_level, muted)
        music.set_mix(master, music_level, muted)

    apply_audio_settings()

    fx = RetroFX(w, h)
    cockpit = CockpitArt()
    info_font = pygame.font.SysFont("consolas", 18)
    notice_font = pygame.font.SysFont("consolas", 28, bold=True)
    stars = Starfield(n=5200, seed=17)
    galaxies = GalaxyField(n=42, seed=2025)
    system = SolarSystem(seed=1337)

    supernova_duration = COLLAPSE_DURATION  # 1 minute
    system_enter_time = time.time()
    supernova_deadline = system_enter_time + supernova_duration
    supernova_remaining = supernova_duration
    blackhole_duration = SINGULARITY_DELAY  # 2 minutes (starts after supernova completes)
    blackhole_deadline = None   # wall-clock time when BH forms
    blackhole_remaining = None
    blackhole_active = False
    system_index = 1
    system_has_bh = False  # set on arrival/generation
    planet = None  # lazily generated only if black-hole texture sampling is needed
    system_has_bh = (system_index % 10 == 0)

    mission = MissionState()
    # Verification captures should exercise the post-HOME expedition by default.
    # Dedicated states keep HOME, ship recovery and completion directly testable.
    if verification_mode:
        if args.test_state in ("home", "run-start"):
            mission.campaign_phase = CAMPAIGN_HOME
        elif args.test_state == "ship-recovery":
            mission.campaign_phase = CAMPAIGN_SHIP_RECOVERY
        elif args.test_state == "campaign-complete":
            mission.campaign_phase = CAMPAIGN_COMPLETE
            mission.fragments_secured_total = mission.data_fragments_required
            mission.gleebs_transmission_complete = True
        else:
            mission.campaign_phase = CAMPAIGN_EXPEDITION
    mission.begin_system(system, system_index)
    if verification_mode and args.test_state == "ship-recovery":
        mission.begin_ship_recovery()

    ship = Ship()
    ship.load_state()
    save_read_info = get_last_save_read_info()
    if bool(save_read_info.get("recovered", False)):
        log(f"SAVE RECOVERY: restored previous-good generation ({save_read_info.get('error', '')}).")
    if not verification_mode and isinstance(getattr(ship, "_loaded_mission_data", None), dict):
        saved_mission = ship._loaded_mission_data
        # Pass 31 migration: old pre-campaign saves could be stamped as an
        # expedition with zero fragments and no completed ship boot, which made
        # the new story appear to start in space.  Those untouched legacy runs
        # now get the intended HOME prologue once, while real Pass 25+ campaign
        # progress (boot sequence and/or recovered fragments) still resumes.
        legacy_skipped_home = legacy_save_needs_home_prologue(saved_mission)
        if legacy_skipped_home:
            ship._loaded_mission_data = None
            ship.system_checkpoint = None
            log("CAMPAIGN MIGRATION: legacy zero-progress save routed to HOME prologue.")
        else:
            saved_seed = int(saved_mission.get("system_seed", system.seed))
            saved_index = max(1, int(saved_mission.get("system_index", system_index)))
            if saved_seed != system.seed:
                system.generate(saved_seed)
            system_index = saved_index
            mission.begin_system(system, system_index)
            mission.restore_from_dict(saved_mission, system)
            system_has_bh = (system_index % 10 == 0)
    third_person_space = True

    # Deterministic orbital art verification: place the ship on the selected
    # planet's camera line at fixed far/mid/close distances.
    if args.test_state in ("orbital-far", "orbital-mid", "orbital-close"):
        test_planet_i = min(1, len(system.planets) - 1)
        target = system.planet_world_pos(test_planet_i, 0.0)
        distance_by_state = {"orbital-far": 31000.0, "orbital-mid": 10500.0, "orbital-close": 4200.0}
        distance = distance_by_state[args.test_state]
        ship.pos = (target[0], target[1], target[2] - distance)
        ship.vel = (0.0, 0.0, 0.0)
        ship.set_orientation(quat_identity())
        third_person_space = True

    if args.test_state in ("mission-space", "mission-brief") and mission.target_planet_index >= 0:
        target = system.planet_world_pos(mission.target_planet_index, 0.0)
        ship.pos = (target[0], target[1], target[2] - 22000.0)
        ship.vel = (0.0, 0.0, 0.0)
        ship.set_orientation(quat_identity())
        third_person_space = True


    ship.mission_state = mission
    if mission.run_started and not isinstance(getattr(ship, "system_checkpoint", None), dict):
        # Migration safety: a Pass 17.1 mid-system save becomes its own first
        # retry checkpoint rather than losing existing advancement.
        ship.capture_system_checkpoint(mission)

    global SHIP_REF
    SHIP_REF = ship
    missiles = Missiles()
    lasers = Lasers()  # legacy (unused unless re-enabled)

    # Solar system anchor is system.star_pos; planets orbit it.

    paused = bool(args.test_overlay in ("pause", "settings"))
    hud_visible = bool(settings.get("hud_visible", True)) and args.test_overlay != "hud-off"
    controls_visible = bool(args.test_overlay == "controls")
    settings_visible = bool(args.test_overlay == "settings")
    settings_selection = 0
    pause_selection = 0
    pause_status = ""
    pause_buttons = {}
    settings_buttons = {}
    last_windowed_mode = "native_1080p" if active_window_mode in ("native_1080p", "fullscreen") else "bordered"
    mission_brief_visible = bool(args.test_state == "mission-brief")
    run_intro_active = bool(args.test_state == "run-start")
    if run_intro_active:
        system_enter_time = None
        supernova_deadline = None
    landed_planet_i = None

    def current_context():
        gm = globals().get("game_mode", GAME_MODE_SPACE)
        if gm == GAME_MODE_INTERIOR:
            return "interior"
        if gm == GAME_MODE_SURFACE:
            try:
                seed = globals().get("active_planet_seed")
                if seed is not None:
                    surface = _terrains().get_surface(seed, screen, ship)
                    if getattr(surface, "mode", "surface") != "surface":
                        return "ruin"
            except Exception:
                pass
            return "surface"
        return "space"

    def mission_target_distance():
        idx = int(getattr(mission, "target_planet_index", -1))
        if idx < 0 or idx >= len(system.planets):
            return None
        try:
            target_pos = system.planet_world_pos(idx, max(0.0, time.time() - t0))
            return vec3_len(vec3_sub(target_pos, ship.pos))
        except Exception:
            return None

    last_checkpoint_wall = 0.0

    def checkpoint_runtime(reason: str, force: bool = False):
        """Persist a small lifecycle checkpoint without spamming disk writes."""
        nonlocal last_checkpoint_wall
        if verification_mode:
            return False
        now = time.time()
        if (not force) and (now - last_checkpoint_wall) < 0.75:
            return False
        ok = bool(ship.save_state(reason=str(reason)))
        if ok:
            last_checkpoint_wall = now
        return ok

    def apply_pointer_mode():
        interior_mode = globals().get("game_mode") == GAME_MODE_INTERIOR
        visible = paused or interior_mode
        pygame.event.set_grab(not visible)
        pygame.mouse.set_visible(visible)
        if not visible:
            pygame.mouse.get_rel()

    def set_paused(value):
        nonlocal paused, settings_visible, pause_status
        was_paused = bool(paused)
        paused = bool(value)
        if paused and not was_paused:
            checkpoint_runtime("pause_or_lifecycle", force=True)
        if not paused:
            settings_visible = False
            pause_status = ""
        apply_pointer_mode()

    def persist_ui_settings():
        if verification_mode:
            return
        settings["hud_visible"] = bool(hud_visible)
        settings["controls_overlay_seen"] = bool(settings.get("controls_overlay_seen", False) or controls_visible)
        try:
            save_settings(settings)
        except Exception:
            log("WARN: settings save failed\n" + traceback.format_exc())

    DISPLAY_MODES = ("bordered", "native_1080p", "fullscreen")
    BORDERED_SIZES = ((1280, 720), (1600, 900), (1920, 1080))
    AUDIO_KEYS = {2: "master_volume", 3: "music_volume", 4: "sfx_volume", 5: "ambience_volume"}

    def save_all_settings():
        if verification_mode:
            return
        try:
            save_settings(settings)
        except Exception:
            log("WARN: settings save failed\n" + traceback.format_exc())

    def apply_display_choice(mode: str, requested_size=None):
        nonlocal display, window_flags, active_window_mode, last_windowed_mode
        requested = str(mode)
        if requested != "fullscreen":
            last_windowed_mode = requested
        display, window_flags, active_window_mode = open_display(requested, requested_size)
        settings["window_mode"] = active_window_mode
        if active_window_mode == "bordered":
            bw, bh = display.get_size()
            settings["bordered_width"] = int(bw)
            settings["bordered_height"] = int(bh)
        present_cache["surf"] = None
        present_cache["size"] = (0, 0)
        save_all_settings()
        apply_pointer_mode()

    def toggle_fullscreen():
        if active_window_mode == "fullscreen":
            apply_display_choice(last_windowed_mode)
        else:
            apply_display_choice("fullscreen")

    def adjust_settings_row(row: int, direction: int):
        nonlocal settings_selection
        settings_selection = max(0, min(6, int(row)))
        direction = -1 if int(direction) < 0 else 1
        if settings_selection == 0:
            index = DISPLAY_MODES.index(active_window_mode) if active_window_mode in DISPLAY_MODES else 0
            apply_display_choice(DISPLAY_MODES[(index + direction) % len(DISPLAY_MODES)])
        elif settings_selection == 1:
            current = (int(settings.get("bordered_width", 1600)), int(settings.get("bordered_height", 900)))
            try:
                index = BORDERED_SIZES.index(current)
            except ValueError:
                index = 1
            size = BORDERED_SIZES[(index + direction) % len(BORDERED_SIZES)]
            settings["bordered_width"], settings["bordered_height"] = size
            if active_window_mode == "bordered":
                apply_display_choice("bordered", size)
            else:
                save_all_settings()
        elif settings_selection in AUDIO_KEYS:
            key = AUDIO_KEYS[settings_selection]
            value = clamp(float(settings.get(key, 1.0)) + 0.10 * direction, 0.0, 1.0)
            settings[key] = round(value, 2)
            apply_audio_settings()
            save_all_settings()
        elif settings_selection == 6:
            settings["audio_muted"] = not bool(settings.get("audio_muted", False))
            apply_audio_settings()
            save_all_settings()

    def handle_settings_key(key):
        nonlocal settings_selection, settings_visible
        if not settings_visible:
            return False
        if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            settings_visible = False
            return True
        if key == pygame.K_UP:
            settings_selection = (settings_selection - 1) % 7
            return True
        if key == pygame.K_DOWN:
            settings_selection = (settings_selection + 1) % 7
            return True
        if key in (pygame.K_LEFT, pygame.K_a):
            adjust_settings_row(settings_selection, -1)
            return True
        if key in (pygame.K_RIGHT, pygame.K_d):
            adjust_settings_row(settings_selection, 1)
            return True
        if key in (pygame.K_RETURN, pygame.K_SPACE):
            if settings_selection == 6:
                adjust_settings_row(6, 1)
            return True
        return False

    def activate_pause_selection():
        nonlocal controls_visible, hud_visible, running, settings_visible, pause_selection, settings_selection
        choice = int(pause_selection) % 5
        if choice == 0:
            set_paused(False)
        elif choice == 1:
            settings_selection = 0
            settings_visible = True
        elif choice == 2:
            controls_visible = not controls_visible
            persist_ui_settings()
        elif choice == 3:
            hud_visible = not hud_visible
            persist_ui_settings()
        elif choice == 4:
            running = False
        return True

    def handle_pause_key(key):
        nonlocal pause_selection, controls_visible, hud_visible, running, settings_visible
        if not paused or settings_visible:
            return False
        if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            set_paused(False)
            return True
        if key == pygame.K_UP:
            pause_selection = (pause_selection - 1) % 5
            return True
        if key == pygame.K_DOWN:
            pause_selection = (pause_selection + 1) % 5
            return True
        if key in (pygame.K_RETURN, pygame.K_SPACE):
            return activate_pause_selection()
        if key == pygame.K_s:
            pause_selection = 1
            settings_visible = True
            return True
        if key == getattr(pygame, "K_F1", 1073741882):
            pause_selection = 2
            controls_visible = not controls_visible
            persist_ui_settings()
            return True
        if key == getattr(pygame, "K_h", 104):
            pause_selection = 3
            hud_visible = not hud_visible
            persist_ui_settings()
            return True
        if key == pygame.K_q:
            pause_selection = 4
            running = False
            return True
        return False

    def handle_standard_key(key):
        nonlocal controls_visible, hud_visible, mission_brief_visible, running, settings_visible
        key_f1 = getattr(pygame, "K_F1", 1073741882)
        key_h = getattr(pygame, "K_h", 104)
        key_m = getattr(pygame, "K_m", 109)
        if key == PAUSE_KEY:
            set_paused(not paused)
            return True
        if paused and settings_visible and handle_settings_key(key):
            return True
        if paused and handle_pause_key(key):
            return True
        if key == key_m and not run_intro_active and not paused:
            mission_brief_visible = not mission_brief_visible
            return True
        if key == key_f1 and not settings_visible:
            controls_visible = not controls_visible
            persist_ui_settings()
            return True
        if key == key_h and not settings_visible:
            hud_visible = not hud_visible
            persist_ui_settings()
            return True
        return False

    def post_key(key):
        try:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))
        except Exception:
            pass

    def inject_controller_events(context):
        """Translate controller edges into the existing state-specific key paths.

        Continuous stick/trigger values are read directly below; only one-shot
        actions are injected here so the keyboard and controller share the same
        mission/pause/save logic.
        """
        if not bool(getattr(gamepad, "connected", False)):
            return
        if failure_active:
            if gamepad.pressed("a"):
                post_key(pygame.K_r)
            elif gamepad.pressed("b"):
                post_key(pygame.K_q)
            return
        if campaign_complete_active:
            if gamepad.pressed("a"):
                post_key(pygame.K_RETURN)
            elif gamepad.pressed("b"):
                post_key(pygame.K_ESCAPE)
            return
        if run_intro_active:
            if gamepad.pressed("a"):
                post_key(pygame.K_RETURN)
            elif gamepad.pressed("b"):
                post_key(pygame.K_ESCAPE)
            return
        if paused:
            if gamepad.pressed("start"):
                post_key(PAUSE_KEY)
                return
            if settings_visible:
                if gamepad.nav_pressed("up"):
                    post_key(pygame.K_UP)
                elif gamepad.nav_pressed("down"):
                    post_key(pygame.K_DOWN)
                elif gamepad.nav_pressed("left"):
                    post_key(pygame.K_LEFT)
                elif gamepad.nav_pressed("right"):
                    post_key(pygame.K_RIGHT)
                if gamepad.pressed("a"):
                    post_key(pygame.K_RETURN)
                elif gamepad.pressed("b"):
                    post_key(pygame.K_ESCAPE)
                return
            if gamepad.nav_pressed("up"):
                post_key(pygame.K_UP)
            elif gamepad.nav_pressed("down"):
                post_key(pygame.K_DOWN)
            if gamepad.pressed("a"):
                post_key(pygame.K_RETURN)
            elif gamepad.pressed("b"):
                post_key(pygame.K_ESCAPE)
            elif gamepad.pressed("view"):
                post_key(getattr(pygame, "K_F1", 1073741882))
            return
        if mission_brief_visible:
            if gamepad.pressed("b") or gamepad.pressed("y") or gamepad.pressed("view"):
                post_key(getattr(pygame, "K_m", 109))
            elif gamepad.pressed("start"):
                post_key(PAUSE_KEY)
            return

        if gamepad.pressed("start"):
            post_key(PAUSE_KEY)
            return
        # If the controls panel followed us out of Pause, its documented VIEW
        # close action owns the button before Mission Brief does.
        if controls_visible and gamepad.pressed("view"):
            post_key(getattr(pygame, "K_F1", 1073741882))
            return
        if gamepad.pressed("view"):
            post_key(getattr(pygame, "K_m", 109))

        if context == "space":
            if gamepad.pressed("x"):
                post_key(pygame.K_TAB)
            if gamepad.pressed("y"):
                post_key(THIRD_PERSON_TOGGLE_KEY)
            if gamepad.pressed("dpad_right"):
                post_key(pygame.K_f)
            if gamepad.pressed("dpad_left"):
                post_key(pygame.K_c)
        elif context == "surface":
            if gamepad.pressed("a"):
                post_key(pygame.K_e)
            if gamepad.pressed("x"):
                post_key(pygame.K_TAB)
            if gamepad.pressed("b"):
                post_key(pygame.K_SPACE)
            if gamepad.pressed("y"):
                post_key(getattr(pygame, "K_m", 109))
        elif context == "ruin":
            if gamepad.pressed("a"):
                post_key(pygame.K_e)
            if gamepad.pressed("b"):
                post_key(pygame.K_x)
            if gamepad.pressed("y"):
                post_key(getattr(pygame, "K_m", 109))
        elif context == "interior":
            upgrade_open = False
            try:
                upgrade_open = bool(getattr(_interiors().get_interior(screen, ship), "upgrade_menu_open", False))
            except Exception:
                pass
            if gamepad.nav_pressed("up"):
                post_key(pygame.K_UP)
            elif gamepad.nav_pressed("down"):
                post_key(pygame.K_DOWN)
            elif upgrade_open and gamepad.nav_pressed("left"):
                post_key(pygame.K_LEFT)
            elif upgrade_open and gamepad.nav_pressed("right"):
                post_key(pygame.K_RIGHT)
            if gamepad.pressed("a"):
                post_key(pygame.K_RETURN if upgrade_open else pygame.K_e)
            if gamepad.pressed("b"):
                post_key(pygame.K_ESCAPE if upgrade_open else pygame.K_TAB)
            if gamepad.pressed("x") and not upgrade_open:
                post_key(pygame.K_SPACE)
            if gamepad.pressed("y"):
                post_key(getattr(pygame, "K_m", 109))

    def handle_settings_click(pos):
        nonlocal settings_visible, settings_selection
        virtual_pos = window_to_virtual(pos, display.get_size(), (VIRTUAL_W, VIRTUAL_H))
        if settings_buttons.get("back") and settings_buttons["back"].collidepoint(virtual_pos):
            settings_visible = False
            return True
        names = ("display", "size", "master", "music", "sfx", "ambience")
        for row, name in enumerate(names):
            if settings_buttons.get(f"{name}_prev") and settings_buttons[f"{name}_prev"].collidepoint(virtual_pos):
                adjust_settings_row(row, -1)
                return True
            if settings_buttons.get(f"{name}_next") and settings_buttons[f"{name}_next"].collidepoint(virtual_pos):
                adjust_settings_row(row, 1)
                return True
        for row in range(7):
            rect = settings_buttons.get(f"row_{row}")
            if rect and rect.collidepoint(virtual_pos):
                settings_selection = row
                if row == 6:
                    adjust_settings_row(row, 1)
                return True
        return False

    def handle_pause_click(pos):
        nonlocal controls_visible, hud_visible, running, settings_visible
        if not paused:
            return False
        if settings_visible:
            return handle_settings_click(pos)
        virtual_pos = window_to_virtual(pos, display.get_size(), (VIRTUAL_W, VIRTUAL_H))
        if pause_buttons.get("resume") and pause_buttons["resume"].collidepoint(virtual_pos):
            set_paused(False)
        elif pause_buttons.get("settings") and pause_buttons["settings"].collidepoint(virtual_pos):
            settings_visible = True
        elif pause_buttons.get("controls") and pause_buttons["controls"].collidepoint(virtual_pos):
            controls_visible = not controls_visible
            persist_ui_settings()
        elif pause_buttons.get("hud") and pause_buttons["hud"].collidepoint(virtual_pos):
            hud_visible = not hud_visible
            persist_ui_settings()
        elif pause_buttons.get("quit") and pause_buttons["quit"].collidepoint(virtual_pos):
            running = False
        else:
            return False
        return True

    def draw_standard_layer(context):
        nonlocal pause_buttons, settings_buttons
        collapse_timer = blackhole_remaining if (system.post_supernova and blackhole_remaining is not None) else supernova_remaining
        collapse_timer_name = timer_label(mission.collapse_state, system.post_supernova and blackhole_remaining is not None)
        pressure = 0.0
        if mission.collapse_state == "UNSTABLE":
            pressure = 0.35
        elif mission.collapse_state == "CRITICAL":
            pressure = 0.72
        elif mission.collapse_state in ("SUPERNOVA", "BLACK HOLE"):
            pressure = 1.0
        show_collapse_hud = not bool(getattr(mission, "is_ship_recovery_phase", False)) and not bool(getattr(mission, "campaign_complete", False))
        if show_collapse_hud:
            draw_collapse_pressure(screen, mission.collapse_state, pressure, tsec)
        if hud_visible:
            draw_mode_chip(screen, context)
            if show_collapse_hud:
                draw_collapse_panel(screen, mission.collapse_state, collapse_timer, collapse_timer_name, ship.hull_hp, ship.hull_hp_max)
            draw_mission_tracker(
                screen,
                mission.objective_title(context),
                mission.objective_detail(context, mission_target_distance() if context == "space" else None),
                mission.collapse_state,
            )
            controller_connected = bool(getattr(gamepad, "connected", False))
            if context == "space":
                warp_jumps, warp_cost = warp_quote(ship)
                if bool(getattr(mission, "warp_unlocked", False)):
                    warp_text_controller = f"DPAD RIGHT WARP  {max(1, warp_jumps)}J / {warp_cost} FUEL"
                    warp_text_keyboard = f"F WARP  {max(1, warp_jumps)}J / {warp_cost} FUEL"
                else:
                    warp_text_controller = "DPAD RIGHT WARP LOCKED — RESOLVE SYSTEM GOAL"
                    warp_text_keyboard = "F WARP LOCKED — RESOLVE SYSTEM GOAL"
                if controller_connected:
                    draw_bottom_hint(screen, "Y VIEW  •  X INTERIOR  •  DPAD LEFT DAMPERS", f"{warp_text_controller}  •  VIEW MISSION  •  MENU PAUSE")
                else:
                    draw_bottom_hint(screen, "V VIEW  •  TAB INTERIOR  •  C DAMPERS", f"{warp_text_keyboard}  •  M MISSION  •  F1 CONTROLS  •  ` PAUSE")
            elif context == "surface":
                if controller_connected:
                    draw_bottom_hint(screen, "A INTERACT  •  X INTERIOR  •  B ORBIT", "Y / VIEW MISSION  •  MENU PAUSE")
                else:
                    draw_bottom_hint(screen, "E INTERACT / ENTER  •  TAB INTERIOR  •  SPACE ORBIT", "M MISSION  •  F1 CONTROLS  •  ` PAUSE")
            elif context == "ruin":
                if controller_connected:
                    draw_bottom_hint(screen, "A INTERACT  •  B LEAVE RUIN", "Y / VIEW MISSION  •  MENU PAUSE")
                else:
                    draw_bottom_hint(screen, "E EXTRACT / EXIT  •  X LEAVE RUIN", "M MISSION  •  F1 CONTROLS  •  ` PAUSE")
            else:
                if controller_connected:
                    draw_bottom_hint(screen, "LEFT STICK MOVE  •  A USE STATION  •  B BACK", "X TAKEOFF  •  Y / VIEW MISSION  •  MENU PAUSE")
                else:
                    draw_bottom_hint(screen, "WASD MOVE  •  E USE SHIP STATION  •  TAB BACK", "SPACE TAKEOFF  •  M MISSION  •  ` PAUSE")
        if collapse_banner_t > 0.0 and not paused and not run_intro_active:
            draw_collapse_banner(screen, collapse_banner)
        if controls_visible and not paused and not run_intro_active and not mission_brief_visible:
            draw_controls_overlay(screen, context, controller=bool(getattr(gamepad, "connected", False)))
        if mission_brief_visible and not paused and not run_intro_active:
            draw_mission_brief(screen, mission, context, mission_target_distance() if context == "space" else None, controller=bool(getattr(gamepad, "connected", False)))
        if paused:
            if settings_visible:
                settings_buttons = draw_settings_menu(screen, settings, active_window_mode, settings_selection, controller=bool(getattr(gamepad, "connected", False)))
                pause_buttons = {}
            else:
                pause_buttons = draw_pause_menu(screen, context, hud_visible, controls_visible, pause_selection, controller=bool(getattr(gamepad, "connected", False)), status_text=pause_status)
                settings_buttons = {}
        else:
            pause_buttons = {}
            settings_buttons = {}
        if run_intro_active and context == "space":
            draw_run_start_screen(screen, mission, controller=bool(getattr(gamepad, "connected", False)))

    apply_pointer_mode()

    log(f"Boot: {APP_NAME} {APP_VERSION} started.")
    log(f"Resolution: {w}x{h}; window={win_w}x{win_h}")
    log(f"User save: {SAVE_PATH}")
    log(f"Mission: system={mission.system_index} target=P{mission.target_planet_index + 1} style={mission.target_style}")
    log(f"Runtime log: {RUNTIME_LOG}")
    log("Cockpit: place your cockpit art at assets/ui/cockpit/<image files>")
    log("SFX: drop files into assets/sfx/ship/* (mp3/ogg/wav; support depends on your SDL_mixer build).")
    log("Music: state-aware score routes HOME / recovery / expedition / collapse / Gleebs through assets/music/.")

    t0 = time.time()
    last_periodic_save_wall = t0
    AUTOSAVE_SECONDS = 20.0
    lifecycle_frame_count = 0
    running = True
    last_boost = False
    last_hyper = False
    pending_galaxy = -1
    pending_align = -1.0
    warp_pending = False
    warp_timer = 0.0
    WARP_DURATION = 3.0
    warp_lock_yaw = 0.0
    warp_lock_pitch = 0.0
    warp_lock_roll = 0.0
    warp_lock_orientation = quat_identity()
    hud_notice = ""
    hud_notice_t = 0.0
    hud_notice_cache_text = None
    hud_notice_cache_panel = None
    if bool(save_read_info.get("recovered", False)):
        hud_notice = "SAVE RECOVERED FROM PREVIOUS-GOOD COPY"
        hud_notice_t = 4.2
    elif previous_session_unclean:
        hud_notice = "PREVIOUS SESSION ENDED UNEXPECTEDLY — SAVE STATE CHECKED"
        hud_notice_t = 4.2
    mode = "space"  # or "planet"
    planet_entry_pending = False
    planet_entry_timer = 0.0
    planet_entry_surface_ready = False
    planet_entry_ready_index = None
    transition_gap_grace_frames = 0
    PLANET_ENTRY_DURATION = 1.55
    saved_space = None
    current_planet_seed = 0
    planet_world = None
    planet_cam_x = 0.0

    planet_exit_requested = False

    # Prevent an infinite planet-entry loop if surface generation fails or if we return to space
    # while still inside the entry radius.
    entry_block_planet_i = None
    entry_block_dist = 0.0
    entry_block_active = False
    nearest_planet_i = -1
    nearest_planet_pos = None

    failure_active = False
    failure_reason = ""
    failure_backdrop = None
    failure_buttons = {}
    campaign_complete_active = bool(getattr(mission, "campaign_complete", False))
    campaign_complete_backdrop = None
    campaign_complete_buttons = {}
    home_evacuation_pending = False
    home_evacuation_timer = 0.0
    collapse_banner = ""
    collapse_banner_t = 0.0
    last_collapse_state = mission.collapse_state
    collapse_shock_applied = False
    collapse_damage_pool = 0.0

    if not verification_mode:
        crash_reporter.set_context_provider(lambda: {
            "campaign_phase": str(getattr(mission, "campaign_phase", "unknown")),
            "mission_phase": str(getattr(mission, "phase", "unknown")),
            "system_index": int(getattr(mission, "system_index", 0)),
            "system_seed": int(getattr(mission, "system_seed", 0)),
            "data_fragments": int(getattr(mission, "data_fragments_secured", 0)),
            "data_fragments_required": int(getattr(mission, "data_fragments_required", 6)),
            "collapse_state": str(getattr(mission, "collapse_state", "unknown")),
            "collapse_remaining": float(getattr(mission, "collapse_remaining", 0.0)),
            "game_mode": str(globals().get("game_mode", GAME_MODE_SPACE)),
            "paused": bool(paused),
            "controller_connected": bool(getattr(gamepad, "connected", False)),
            "fuel": int(getattr(ship, "fuel", 0)),
            "hull_hp": int(getattr(ship, "hull_hp", 0)),
        })

    def activate_failure(reason: str):
        nonlocal failure_active, failure_reason, failure_backdrop, paused, settings_visible
        nonlocal mission_brief_visible, controls_visible, warp_pending, planet_entry_pending
        nonlocal planet_entry_surface_ready, planet_entry_ready_index
        nonlocal mode, landed_planet_i, saved_space
        if failure_active:
            return
        failure_active = True
        failure_reason = str(reason or "EXPEDITION FAILURE")
        paused = False
        settings_visible = False
        mission_brief_visible = False
        controls_visible = False
        warp_pending = False
        planet_entry_pending = False
        planet_entry_surface_ready = False
        planet_entry_ready_index = None
        ship.hyperspace = False
        ship.vel = (0.0, 0.0, 0.0)
        try:
            if globals().get("game_mode") == GAME_MODE_SURFACE:
                _terrains().leave_surface()
            elif globals().get("game_mode") == GAME_MODE_INTERIOR:
                _interiors().leave_interior()
        except Exception:
            pass
        globals()["active_planet_seed"] = None
        globals()["game_mode"] = GAME_MODE_SPACE
        mode = "space"
        landed_planet_i = None
        saved_space = None
        failure_backdrop = screen.copy()
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
        log(f"FAILURE: {failure_reason}")

    def retry_system_checkpoint():
        nonlocal failure_active, failure_reason, failure_backdrop, failure_buttons
        nonlocal supernova_deadline, supernova_remaining, system_enter_time
        nonlocal blackhole_deadline, blackhole_remaining, blackhole_active, system_has_bh
        nonlocal system_index, stars, mode, landed_planet_i, saved_space
        nonlocal warp_pending, warp_timer, planet_entry_pending, planet_entry_timer
        nonlocal planet_entry_surface_ready, planet_entry_ready_index, transition_gap_grace_frames
        nonlocal current_planet_seed, planet_world, planet_cam_x, collapse_shock_applied
        nonlocal collapse_damage_pool, collapse_banner, collapse_banner_t, last_collapse_state
        mission_data = ship.restore_system_checkpoint()
        if not isinstance(mission_data, dict):
            # Defensive fallback for damaged/legacy checkpoint data.
            mission_data = mission.to_dict()
            mission_data["carrying_fragment"] = False
            mission_data["fragment_deposited"] = False
            ship.hull_hp = ship.hull_hp_max
            ship.player_hp = ship.player_hp_max
        seed = int(mission_data.get("system_seed", system.seed))
        system_index = max(1, int(mission_data.get("system_index", system_index)))
        system.generate(seed)
        mission.begin_system(system, system_index)
        mission.restore_from_dict(mission_data, system)
        mission.mark_run_started()
        ship.mission_state = mission
        system_enter_time = time.time()
        supernova_deadline = system_enter_time + supernova_duration
        supernova_remaining = supernova_duration
        blackhole_deadline = None
        blackhole_remaining = None
        blackhole_active = False
        system.blackhole_active = False
        system.blackhole_t0 = None
        system.supernova_t0 = None
        system.supernova_triggered = False
        system.post_supernova = False
        system.supernova_parts = []
        system_has_bh = (system_index % 10 == 0)
        if not system_has_bh and hasattr(main, "_bh_pos"):
            delattr(main, "_bh_pos")
        stars = Starfield(n=5200, seed=seed ^ 0xC011A95E)
        globals()["active_planet_seed"] = None
        globals()["game_mode"] = GAME_MODE_SPACE
        mode = "space"
        landed_planet_i = None
        saved_space = None
        warp_pending = False
        warp_timer = 0.0
        planet_entry_pending = False
        planet_entry_timer = 0.0
        planet_entry_surface_ready = False
        planet_entry_ready_index = None
        transition_gap_grace_frames = 2
        current_planet_seed = 0
        planet_world = None
        planet_cam_x = 0.0
        collapse_shock_applied = False
        collapse_damage_pool = 0.0
        collapse_banner = "CHECKPOINT RESTORED — CURRENT SYSTEM RESET"
        collapse_banner_t = 3.2
        last_collapse_state = mission.collapse_state
        failure_active = False
        failure_reason = ""
        failure_backdrop = None
        failure_buttons = {}
        try:
            ship.save_state()
        except Exception:
            pass
        apply_pointer_mode()
        log(f"RETRY: restored system-entry checkpoint for system {system_index} seed={seed}.")

    def commit_home_evacuation():
        """Guaranteed first-collapse transfer from HOME into the next ship interior."""
        nonlocal system_index, system_has_bh, stars
        nonlocal supernova_deadline, supernova_remaining, blackhole_deadline, blackhole_remaining, blackhole_active
        nonlocal collapse_shock_applied, collapse_damage_pool, collapse_banner, collapse_banner_t, last_collapse_state
        nonlocal mode, landed_planet_i, saved_space, warp_pending, warp_timer, planet_entry_pending, planet_entry_timer
        nonlocal planet_entry_surface_ready, planet_entry_ready_index, transition_gap_grace_frames
        nonlocal current_planet_seed, planet_world, planet_cam_x, home_evacuation_pending, home_evacuation_timer
        try:
            if globals().get("game_mode") == GAME_MODE_SURFACE:
                _terrains().leave_surface()
            elif globals().get("game_mode") == GAME_MODE_INTERIOR:
                _interiors().leave_interior()
        except Exception:
            log("WARN: HOME evacuation cleanup failed:\n" + traceback.format_exc())

        # HOME is gone. Generate the first abandoned system, but freeze its
        # collapse timer while the player restores the disabled ship.
        mission.campaign_phase = "ship_recovery"
        previous_style = str(getattr(system.planets[0], "style", "unknown")) if getattr(system, "planets", None) else "unknown"
        new_seed, variety_rerolls = _generate_varied_system(system, random.randrange(1_000_000_000), previous_style)
        system_index += 1
        mission.begin_system(system, system_index)
        mission.begin_ship_recovery()
        mission.mark_run_started()

        # A player who missed the visible HOME cache still receives a tiny
        # emergency reserve so the tutorial cannot deadlock. Recovering the
        # cache remains strongly rewarded with a much larger field pack.
        pack = getattr(ship, "player_pack", None)
        if not isinstance(pack, dict):
            pack = {}
            ship.player_pack = pack
        if int(pack.get("fuel_cells", 0)) <= 0:
            pack["fuel_cells"] = 1
        if int(pack.get("salvage", 0)) <= 0:
            pack["salvage"] = 2
        ship.state_dirty = True

        reset_ship_to_system_spawn(ship)
        system_enter_time_local = time.time()
        supernova_deadline = None
        supernova_remaining = supernova_duration
        blackhole_deadline = None
        blackhole_remaining = None
        blackhole_active = False
        system.blackhole_active = False
        system.blackhole_t0 = None
        system.supernova_t0 = None
        system.supernova_triggered = False
        system.post_supernova = False
        system.supernova_parts = []
        system_has_bh = False
        stars = Starfield(n=5200, seed=int(new_seed) ^ 0xC011A95E)
        collapse_shock_applied = False
        collapse_damage_pool = 0.0
        collapse_banner = "EMERGENCY TRANSFER COMPLETE — RESTORE SHIP SYSTEMS"
        collapse_banner_t = 4.0
        last_collapse_state = mission.collapse_state

        globals()["active_planet_seed"] = None
        globals()["game_mode"] = GAME_MODE_INTERIOR
        globals()["interior_return_mode"] = GAME_MODE_SPACE
        mode = "space"
        landed_planet_i = None
        saved_space = None
        warp_pending = False
        warp_timer = 0.0
        planet_entry_pending = False
        planet_entry_timer = 0.0
        planet_entry_surface_ready = False
        planet_entry_ready_index = None
        transition_gap_grace_frames = 2
        current_planet_seed = 0
        planet_world = None
        planet_cam_x = 0.0
        home_evacuation_pending = False
        home_evacuation_timer = 0.0

        try:
            _interiors().enter_interior(screen, ship, return_mode=GAME_MODE_SPACE)
            _interiors().get_interior(screen, ship).set_notification("HOME LOST — AUXILIARY POWER OFFLINE", 3.6)
        except Exception:
            log("ERROR: failed to enter ship after HOME evacuation:\n" + traceback.format_exc())
            globals()["game_mode"] = GAME_MODE_SPACE
        ship.capture_system_checkpoint(mission)
        try:
            ship.save_state()
        except Exception:
            pass
        apply_pointer_mode()
        log(f"CAMPAIGN: HOME evacuated into system {system_index} seed={new_seed}; ship recovery started.")

    # Data Fragment recovery never auto-warps. The player explicitly decides
    # when to leave a collapsing system, preserving the salvage-risk loop.

    # Deterministic verification states use the same runtime render paths as normal play.
    if args.test_state == "cockpit":
        third_person_space = False
    elif args.test_state in ("interior", "recovery-deposit", "ship-recovery"):
        if args.test_state == "recovery-deposit":
            mission.land_on(mission.target_planet_index)
            mission.target_structure_seed = int(args.test_seed) ^ 0xD00D
            mission.inside_target_ruin = True
            mission.recover_fragment(mission.target_structure_seed)
        globals()["interior_return_mode"] = GAME_MODE_SPACE
        globals()["game_mode"] = GAME_MODE_INTERIOR
        _interiors().enter_interior(screen, ship, return_mode=GAME_MODE_SPACE)
        test_interior = _interiors().get_interior(screen, ship)
        if args.test_state == "recovery-deposit":
            test_interior.player.x = test_interior.cargo_console_pos[0] - 72
            test_interior.player.y = test_interior.cargo_console_pos[1] + 18
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
    elif args.test_state in ("surface", "recovery-surface", "recovery-relic", "home"):
        globals()["active_planet_seed"] = int(args.test_seed)
        globals()["game_mode"] = GAME_MODE_SURFACE
        landed_planet_i = mission.target_planet_index if mission.target_planet_index >= 0 else 0
        mission.land_on(landed_planet_i)
        test_surface = _terrains().get_surface(int(args.test_seed), screen, ship, forced_biome=args.test_biome)
        test_surface.mode = "surface"
        test_surface.configure_mission(mission, landed_planet_i)
        if args.test_state in ("recovery-surface", "recovery-relic") and test_surface.mission_target_structure is not None:
            target = test_surface.mission_target_structure
            test_surface.cam_x = target.x - 10.0
            test_surface.cam_y = target.y + 6.0
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
    elif args.test_state == "recovery-secured":
        mission.land_on(mission.target_planet_index)
        mission.target_structure_seed = int(args.test_seed) ^ 0xD00D
        mission.recover_surface_relic(mission.target_structure_seed)
        mission.return_to_orbit()
    elif args.test_state == "collapse-critical":
        mission.mark_run_started()
        run_intro_active = False
        supernova_deadline = time.time() + 24.0
    elif args.test_state == "collapse-failure":
        mission.mark_run_started()
        run_intro_active = False
        ship.capture_system_checkpoint(mission)
        activate_failure("EVENT HORIZON CONSUMED THE SHIP")


    # Pass 25 campaign entry routing. A clean profile starts directly on HOME;
    # no modal tutorial is required. Resuming during ship recovery returns to
    # the interior with the stellar timer intentionally frozen.
    if not verification_mode:
        if bool(getattr(mission, "is_home_phase", False)):
            mission.mark_run_started()
            home_planet_i = max(0, int(mission.target_planet_index))
            home_seed = (system.seed * 1000 + home_planet_i * 97 + 12345) & 0x7fffffff
            globals()["active_planet_seed"] = int(home_seed)
            globals()["game_mode"] = GAME_MODE_SURFACE
            globals()["interior_return_mode"] = GAME_MODE_SURFACE
            landed_planet_i = home_planet_i
            mission.land_on(home_planet_i)
            try:
                _terrains().enter_surface(home_seed, screen, ship)
                home_surface = _terrains().get_surface(home_seed, screen, ship)
                home_surface.configure_mission(mission, home_planet_i)
                home_surface.set_notification("HOME — 60 SECONDS UNTIL STELLAR COLLAPSE", 3.6)
            except Exception:
                log("ERROR: HOME surface initialization failed:\n" + traceback.format_exc())
                globals()["game_mode"] = GAME_MODE_SPACE
            mode = "landed"
            system_enter_time = time.time()
            supernova_deadline = system_enter_time + supernova_duration
            run_intro_active = False
            try:
                ship.save_state()
            except Exception:
                pass
            apply_pointer_mode()
            log(f"CAMPAIGN: new expedition begins on HOME surface seed={home_seed}.")
        elif bool(getattr(mission, "is_ship_recovery_phase", False)):
            supernova_deadline = None
            globals()["active_planet_seed"] = None
            globals()["game_mode"] = GAME_MODE_INTERIOR
            globals()["interior_return_mode"] = GAME_MODE_SPACE
            _interiors().enter_interior(screen, ship, return_mode=GAME_MODE_SPACE)
            mode = "space"
            apply_pointer_mode()
            log("CAMPAIGN: resumed ship-recovery tutorial; collapse timer remains frozen.")

    def run_archive_dive(surface, structure):
        """DreamCrawler dive into the marked archive ruin, in this window.

        The collapse clock is charged at ruin_dive.DIVE_COLLAPSE_RATE while
        underground; the rest of the dive's wall time is refunded to the
        wall-clock deadlines so the normal collapse rules stay authoritative.
        """
        nonlocal supernova_deadline, blackhole_deadline, transition_gap_grace_frames
        import ruin_dive

        remaining = None
        if supernova_deadline is not None and not system.supernova_triggered:
            remaining = max(0.0, supernova_deadline - time.time())
        slot = int(getattr(mission, "current_archive_slot", 1))
        required = int(getattr(mission, "data_fragments_required", 6))
        site = f"ARCHIVE {slot}/{required} — {str(getattr(structure, 'title', 'ARCHIVE RUIN'))}"
        ambience.stop_all()
        sfx.stop_engine(80)
        log(f"DIVE: start structure_seed={int(structure.seed)} collapse_remaining={remaining}")
        result = None
        try:
            result = ruin_dive.run_dive(seed=int(structure.seed), site_label=site, collapse_remaining=remaining)
        except Exception:
            log("ERROR: ruin dive failed; using surface recovery instead:\n" + traceback.format_exc())
        finally:
            clock.tick()
            transition_gap_grace_frames = max(transition_gap_grace_frames, 3)
            pygame.event.clear()
        if result is None:
            surface.try_collect_relic_core(structure)
            apply_pointer_mode()
            return
        wall = max(0.0, float(result.get("wall_seconds", 0.0)))
        charged = max(0.0, float(result.get("collapse_charged", 0.0)))
        refund = ruin_dive.collapse_refund(result)
        if supernova_deadline is not None:
            supernova_deadline += refund
        if blackhole_deadline is not None:
            blackhole_deadline += refund
        outcome = str(result.get("outcome", "retreat"))
        log(f"DIVE: outcome={outcome} wall={wall:.1f}s charged={charged:.1f}s floors={result.get('floors_reached')}")
        if outcome == "recovered":
            mission.enter_structure(int(structure.seed), str(getattr(structure, "title", "ARCHIVE RUIN")))
            recovered = mission.recover_fragment(int(structure.seed))
            mission.leave_structure()
            if recovered:
                surface.set_notification("DATA FRAGMENT RECOVERED — RETURN TO THE SHIP AND SECURE IT AT CARGO", 3.8)
                checkpoint_runtime("ruin_dive_recovered", force=True)
            else:
                surface.set_notification("THE ARCHIVE SIGNAL SHIFTED — FRAGMENT NOT RECOVERED", 3.0)
        elif outcome == "collapse":
            surface.set_notification("COLLAPSE REACHED THE RUIN — THE TEAM CLIMBED OUT", 3.0)
        elif outcome == "downed":
            surface.set_notification("DIVER DOWNED — FRAGMENT STILL BELOW — PRESS E TO DIVE AGAIN", 3.4)
        else:
            surface.set_notification("DIVE ABORTED — FRAGMENT STILL BELOW — PRESS E TO DIVE AGAIN", 3.2)
        try:
            surface._sync_mission_distance()
        except Exception:
            pass
        apply_pointer_mode()

    while running:
        wall_dt = clock.tick(60) / 1000.0
        # Motion/animation time is bounded separately from wall-clock time.
        # A short OS/asset hitch therefore cannot throw the ship/camera across
        # the scene, while collapse/save deadlines still use real wall time.
        dt = min(max(0.0, wall_dt), 0.050)
        tsec = time.time() - t0

        # A process-lifetime resume can return a very large frame delta without
        # a focus event.  Deliberate asset/system transitions are excluded: the
        # old guard treated atmosphere preload + surface creation as two separate
        # "suspends", which caused the double-pause on planetfall.
        known_loading_transition = bool(
            planet_entry_pending or planet_entry_surface_ready or home_evacuation_pending
            or warp_pending or transition_gap_grace_frames > 0
        )
        # Historical Pass 30 contract searched for the literal expression
        # `lifecycle_frame_count > 0 and dt > 1.0`; Pass 32 intentionally uses
        # raw wall_dt here so motion-delta clamping can never hide a resume.
        if lifecycle_frame_count > 0 and wall_dt > 1.0 and not known_loading_transition and not paused and not failure_active and not campaign_complete_active:
            pause_status = "SESSION RESUMED — EXPEDITION PAUSED"
            set_paused(True)
        lifecycle_frame_count += 1
        if transition_gap_grace_frames > 0:
            transition_gap_grace_frames -= 1

        # Commit a fully prepared planet only at the start of a fresh frame.
        # The prior frame remains 100% atmosphere transition, so orbital space
        # can never flash back between the transition and the surface.
        if planet_entry_surface_ready:
            globals()["game_mode"] = GAME_MODE_SURFACE
            landed_planet_i = int(planet_entry_ready_index if planet_entry_ready_index is not None else 0)
            mode = "landed"
            planet_entry_pending = False
            planet_entry_timer = 0.0
            planet_entry_surface_ready = False
            planet_entry_ready_index = None
            transition_gap_grace_frames = max(transition_gap_grace_frames, 2)
            hud_notice = "planetfall — data signal active — warp locked until system goal resolves"
            hud_notice_t = 2.8
            apply_pointer_mode()

        # Controller and focus are resolved before collapse timing so losing the
        # active pad/window cannot silently consume a 60-second expedition.
        gamepad.update()
        if bool(getattr(gamepad, "just_disconnected", False)):
            pause_status = "CONTROLLER DISCONNECTED — KEYBOARD / MOUSE REMAIN AVAILABLE"
            if not failure_active and not campaign_complete_active:
                set_paused(True)
        elif bool(getattr(gamepad, "just_connected", False)):
            pause_status = ""
        try:
            window_active = bool(pygame.display.get_active())
        except Exception:
            window_active = True
        if not window_active and not paused and not failure_active and not campaign_complete_active:
            pause_status = "WINDOW FOCUS LOST — EXPEDITION PAUSED"
            set_paused(True)
        inject_controller_events(current_context())

        # Collapse time is simulation time: pause, mission brief, run intro,
        # and failure screens never consume the player's system lifetime.
        now_wall = time.time()
        collapse_frozen = paused or run_intro_active or mission_brief_visible or failure_active or campaign_complete_active
        if collapse_frozen:
            if supernova_deadline is not None:
                supernova_deadline += wall_dt
            if blackhole_deadline is not None:
                blackhole_deadline += wall_dt
        if home_evacuation_pending:
            supernova_remaining = 0.0
        elif supernova_deadline is None:
            supernova_remaining = supernova_duration
        else:
            supernova_remaining = max(0.0, supernova_deadline - now_wall)
        mission.update_collapse(
            supernova_remaining, supernova_duration,
            triggered=system.supernova_triggered,
            post_supernova=system.post_supernova,
            blackhole=blackhole_active,
        )
        if (not verification_mode and not collapse_frozen and
                (now_wall - last_periodic_save_wall) >= AUTOSAVE_SECONDS):
            if checkpoint_runtime("periodic_20s"):
                last_periodic_save_wall = now_wall
        if mission.collapse_state != last_collapse_state:
            last_collapse_state = mission.collapse_state
            collapse_banner = warning_text(last_collapse_state)
            collapse_banner_t = 4.0 if collapse_banner else 0.0
        if collapse_banner_t > 0.0 and not collapse_frozen:
            collapse_banner_t = max(0.0, collapse_banner_t - dt)

        if supernova_deadline is not None and (not system.supernova_triggered) and (now_wall >= supernova_deadline):
            if bool(getattr(mission, "is_home_phase", False)):
                # The first collapse is the inciting incident, not a failure.
                system.trigger_supernova(tsec, instant=False)
                supernova_deadline = None
                home_evacuation_pending = True
                home_evacuation_timer = 0.0
                collapse_banner = "HOME SUPERNOVA — EMERGENCY TRANSFER ENGAGED"
                collapse_banner_t = 3.0
                log("CAMPAIGN: HOME supernova triggered; emergency transfer charging.")
            else:
                system.trigger_supernova(tsec, instant=False)
                # The world is no longer a valid mission destination. Remove its
                # waypoint immediately. If the Data Fragment never left the
                # planet, mark this system as MISSED so the same required data
                # can spawn again in the next system and hyperdrive can unlock.
                if int(getattr(mission, "target_planet_index", -1)) >= 0:
                    outcome = mission.resolve_target_loss("system_collapse")
                    if outcome == "missed":
                        hud_notice = "data signal lost — fragment returned to future cycle"
                        hud_notice_t = 3.4
                    elif outcome == "carrying":
                        hud_notice = "target lost — secure carried data before hyperdrive"
                        hud_notice_t = 3.4
                    checkpoint_runtime("system_goal_resolved_by_collapse", force=True)
                if not collapse_shock_applied:
                    ship.take_hull_damage(SUPERNOVA_SHOCK_DAMAGE)
                    collapse_shock_applied = True
                    collapse_banner = f"SUPERNOVA SHOCK — HULL -{SUPERNOVA_SHOCK_DAMAGE}"
                    collapse_banner_t = 4.5
                # Ordinary systems eject the player from surface/interior into flight.
                if globals().get("game_mode") != GAME_MODE_SPACE:
                    try:
                        if globals().get("game_mode") == GAME_MODE_SURFACE:
                            try:
                                _terrains().leave_surface()
                            except Exception:
                                pass
                        if globals().get("game_mode") == GAME_MODE_INTERIOR:
                            try:
                                _interiors().leave_interior()
                            except Exception:
                                pass
                    except Exception:
                        pass

                    saved_space = globals().get("surface_return_state")
                    if isinstance(saved_space, dict):
                        ship.pos = saved_space.get("pos", ship.pos)
                        ship.vel = saved_space.get("vel", ship.vel)
                        ship.restore_orientation(saved_space)
                        system.generate(saved_space.get("system_seed", system.seed))
                        mission.apply_to_system(system)
                        system_index = saved_space.get("system_index", system_index)
                        system_has_bh = saved_space.get("system_has_bh", system_has_bh)

                    globals()["active_planet_seed"] = None
                    globals()["game_mode"] = GAME_MODE_SPACE
                    mode = "space"
                    landed_planet_i = None
                    mission.return_to_orbit()
                    ship.hyperspace = False
                    warp_pending = False

        if home_evacuation_pending and not paused and not mission_brief_visible:
            home_evacuation_timer += dt
            if home_evacuation_timer >= 1.85:
                commit_home_evacuation()
                continue

        if not collapse_frozen and not failure_active and not bool(getattr(mission, "is_home_phase", False)):
            damage_rate = hull_damage_rate(
                triggered=system.supernova_triggered,
                post_supernova=system.post_supernova,
                blackhole_active=blackhole_active,
            )
            collapse_damage_pool += damage_rate * dt
            whole_damage = int(collapse_damage_pool)
            if whole_damage > 0:
                collapse_damage_pool -= whole_damage
                ship.take_hull_damage(whole_damage)
            if ship.hull_hp <= 0:
                cause = "EVENT HORIZON CONSUMED THE SHIP" if blackhole_active else "STELLAR COLLAPSE DESTROYED THE HULL"
                activate_failure(cause)

        if dt > 0.05:
            dt = 0.05

        # The score follows campaign/collapse state rather than camera mode.
        # HOME, recovery, expedition, critical collapse and Gleebs each own one
        # stream; pause/settings do not restart or replace the current score.
        music.sync(score_state_for(
            mission,
            failure_active=failure_active,
            campaign_complete_active=campaign_complete_active,
        ))
        music.update()

        # Campaign completion owns input and presentation.
        if campaign_complete_active:
            for e in pygame.event.get():
                gamepad.handle_event(e)
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif e.type == getattr(pygame, "MOUSEBUTTONDOWN", 0x401):
                    virtual_pos = window_to_virtual(getattr(e, "pos", (-1, -1)), display.get_size(), (VIRTUAL_W, VIRTUAL_H))
                    if campaign_complete_buttons.get("quit") and campaign_complete_buttons["quit"].collidepoint(virtual_pos):
                        running = False
            if campaign_complete_active:
                if campaign_complete_backdrop is not None:
                    screen.blit(campaign_complete_backdrop, (0, 0))
                else:
                    screen.fill((0, 0, 0))
                campaign_complete_buttons = draw_campaign_complete_screen(
                    screen, mission.system_index, mission.fragments_secured_total, mission.data_fragments_required,
                    controller=bool(getattr(gamepad, "connected", False)),
                )
                present_cover()
                continue

        # Failure owns input and presentation; no simulation continues behind it.
        if failure_active:
            for e in pygame.event.get():
                gamepad.handle_event(e)
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_F11:
                        toggle_fullscreen()
                    elif e.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                        retry_system_checkpoint()
                    elif e.key in (pygame.K_q, pygame.K_ESCAPE):
                        running = False
                elif e.type == getattr(pygame, "MOUSEBUTTONDOWN", 0x401):
                    virtual_pos = window_to_virtual(getattr(e, "pos", (-1, -1)), display.get_size(), (VIRTUAL_W, VIRTUAL_H))
                    if failure_buttons.get("retry") and failure_buttons["retry"].collidepoint(virtual_pos):
                        retry_system_checkpoint()
                    elif failure_buttons.get("quit") and failure_buttons["quit"].collidepoint(virtual_pos):
                        running = False
            if failure_active:
                if failure_backdrop is not None:
                    screen.blit(failure_backdrop, (0, 0))
                else:
                    screen.fill((0, 0, 0))
                failure_buttons = draw_failure_screen(
                    screen, failure_reason, mission.system_index,
                    mission.fragments_secured_total, ship.hull_hp_max,
                    controller=bool(getattr(gamepad, "connected", False)),
                )
                present_cover()
                continue

        # ----------------------------
        # Interior mode fast-path (top-down 2D ship layout)
        # ----------------------------
        if game_mode == GAME_MODE_INTERIOR:
            sfx.set_context("interior")
            ambience.sync_interior()
            intr = _interiors()
            view = intr.get_interior(screen, ship)
            for e in pygame.event.get():
                gamepad.handle_event(e)
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == MusicPlayer.ENDEVENT:
                    music.on_end()
                elif e.type == getattr(pygame, "MOUSEBUTTONDOWN", 0x401) and paused:
                    handle_pause_click(getattr(e, "pos", (-1, -1)))
                elif e.type == pygame.KEYDOWN:
                    if mission_brief_visible:
                        if e.key in (getattr(pygame, "K_m", 109), pygame.K_ESCAPE):
                            mission_brief_visible = False
                        continue
                    if not paused and getattr(view, 'upgrade_menu_open', False) and view.handle_event(e):
                        pass
                    elif handle_standard_key(e.key):
                        pass
                    elif not paused and view.handle_event(e):
                        pass
                    elif e.key == pygame.K_TAB and not paused:
                        if bool(getattr(mission, "is_ship_recovery_phase", False)):
                            view.set_notification('SHIP RECOVERY ACTIVE — COMPLETE THE BOOT SEQUENCE', 2.2)
                            continue
                        # Toggle back to previous view (SPACE or SURFACE)
                        intr.leave_interior()
                        back = globals().get('interior_return_mode', GAME_MODE_SPACE)
                        globals()['game_mode'] = back
                        if back == GAME_MODE_SPACE:
                            pygame.event.set_grab(True)
                            pygame.mouse.set_visible(False)
                            pygame.mouse.get_rel()
                        else:
                            pygame.event.set_grab(False)
                            pygame.mouse.set_visible(True)

                    elif e.key == pygame.K_SPACE and not paused:
                        if bool(getattr(mission, "is_ship_recovery_phase", False)):
                            view.set_notification('COCKPIT LOCKED — COMPLETE THE SHIP RECOVERY SEQUENCE', 2.4)
                            continue
                        # A carried fragment (ruin dive) must be secured at CARGO before lift-off.
                        if mission.carrying_fragment and not mission.fragment_deposited:
                            view.set_notification('SECURE THE DATA FRAGMENT AT CARGO / DATA ARCHIVE', 2.5)
                            continue
                        # SPACE: take off / return to space from the interior (also works when you entered from a planet).
                        intr.leave_interior()
                        back = globals().get('interior_return_mode', GAME_MODE_SPACE)
                        # If we came from a planet surface, lift off and return to space state
                        if back == GAME_MODE_SURFACE and globals().get('active_planet_seed') is not None:
                            try:
                                _terrains().leave_surface()
                            except Exception:
                                pass
                            globals()['active_planet_seed'] = None
                            if surface_return_state:
                                ship.pos = surface_return_state.get('pos', ship.pos)
                                ship.vel = surface_return_state.get('vel', (0.0, 0.0, 0.0))
                                ship.restore_orientation(surface_return_state)
                            ship.hyperspace = False
                            warp_pending = False
                            mode = 'space'
                            landed_planet_i = None
                            mission.return_to_orbit()
                            globals()['game_mode'] = GAME_MODE_SPACE
                            pygame.event.set_grab(True)
                            pygame.mouse.set_visible(False)
                            pygame.mouse.get_rel()
                        else:
                            globals()['game_mode'] = GAME_MODE_SPACE
                            pygame.event.set_grab(True)
                            pygame.mouse.set_visible(False)
                            pygame.mouse.get_rel()

            music.update()
            if not paused and not mission_brief_visible:
                view.update(dt)
                if getattr(view, 'request_campaign_complete', False):
                    campaign_complete_active = True
                    campaign_complete_backdrop = screen.copy()
                    pygame.event.set_grab(False)
                    pygame.mouse.set_visible(True)
                    try:
                        ship.save_state()
                    except Exception:
                        pass
                # cockpit takeoff request (interior -> SPACE)
                if getattr(view, 'request_takeoff', False) and not campaign_complete_active:
                    if bool(getattr(mission, "is_expedition_phase", False)) and supernova_deadline is None:
                        system_enter_time = time.time()
                        supernova_deadline = system_enter_time + supernova_duration
                        supernova_remaining = supernova_duration
                        collapse_shock_applied = False
                        collapse_damage_pool = 0.0
                        collapse_banner = "EXPEDITION ONLINE — SYSTEM COLLAPSE CLOCK STARTED"
                        collapse_banner_t = 3.2
                        ship.capture_system_checkpoint(mission)
                        try:
                            ship.save_state()
                        except Exception:
                            pass
                        log("CAMPAIGN: cockpit launched expedition; collapse timer started.")
                    intr.leave_interior()
                    # If we came from a planet surface, lift off and return to space state
                    if globals().get('interior_return_mode') == GAME_MODE_SURFACE and globals().get('active_planet_seed') is not None:
                        try:
                            _terrains().leave_surface()
                        except Exception:
                            pass
                        globals()['active_planet_seed'] = None
                        if surface_return_state:
                            ship.pos = surface_return_state.get('pos', ship.pos)
                            ship.vel = surface_return_state.get('vel', (0.0, 0.0, 0.0))
                            ship.restore_orientation(surface_return_state)
                        ship.hyperspace = False
                        warp_pending = False
                        mode = 'space'
                        landed_planet_i = None
                        mission.return_to_orbit()
                        planet_exit_requested = True
                        entry_block_planet_i = None
                        entry_block_dist = max(2200.0, ship.dist_to_planet)
                        entry_block_active = True
                    globals()['game_mode'] = GAME_MODE_SPACE
            view.hud_visible = hud_visible
            view.draw()
            draw_standard_layer("interior")
            present_cover()
            continue

        # ----------------------------
        # Surface mode fast-path (top-down 2D)
        # ----------------------------
        if game_mode == GAME_MODE_SURFACE and active_planet_seed is not None:
            terr = _terrains()
            surface = terr.get_surface(active_planet_seed, screen, ship, forced_biome=args.test_biome if args.test_shot else None)
            if landed_planet_i is not None:
                surface.configure_mission(mission, landed_planet_i)
            sfx.set_context("level")
            ambience.sync_surface_view(surface)
            # Backtick toggles pause; Data Fragment recovery never auto-leaves the surface.
            events = []
            entered_interior_now = False
            for e in pygame.event.get():
                gamepad.handle_event(e)
                events.append(e)
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == MusicPlayer.ENDEVENT:
                    music.on_end()
                elif e.type == getattr(pygame, "MOUSEBUTTONDOWN", 0x401) and paused:
                    handle_pause_click(getattr(e, "pos", (-1, -1)))
                elif e.type == pygame.KEYDOWN:
                    if mission_brief_visible:
                        if e.key in (getattr(pygame, "K_m", 109), pygame.K_ESCAPE):
                            mission_brief_visible = False
                        continue
                    if handle_standard_key(e.key):
                        pass
                    elif e.key == pygame.K_TAB and not paused:
                        if bool(getattr(mission, "is_home_phase", False)):
                            surface.set_notification('SHIP ACCESS OFFLINE — RECOVER SUPPLIES AND SURVIVE THE COLLAPSE', 2.6)
                            continue
                        # Enter ship interior only when near the ship marker
                        try:
                            sx, sy = surface.ship_pos
                            near = ((sx - surface.px) ** 2 + (sy - surface.py) ** 2) <= (80 ** 2)
                        except Exception:
                            near = True
                        if near:
                            globals()['interior_return_mode'] = GAME_MODE_SURFACE
                            globals()['game_mode'] = GAME_MODE_INTERIOR
                            try:
                                _interiors().enter_interior(screen, ship)
                            except Exception:
                                log("ERROR: failed to enter interior from surface (TAB):\n" + traceback.format_exc())
                                globals()['game_mode'] = GAME_MODE_SURFACE
                            else:
                                pygame.event.set_grab(False)
                                pygame.mouse.set_visible(True)
                                entered_interior_now = True
                                break
                    elif e.key == pygame.K_SPACE and not paused:
                        if bool(getattr(mission, "is_home_phase", False)):
                            surface.set_notification('NO LAUNCH AVAILABLE — HOME EVACUATION IS AUTOMATIC AT SUPERNOVA', 2.7)
                            continue
                        # Recovery route is deliberately completed through the ship interior.
                        if mission.carrying_fragment and not mission.fragment_deposited:
                            surface.set_notification('DATA FRAGMENT RECOVERED — RETURN TO SHIP AND SECURE IT AT STORAGE', 2.7)
                            continue
                        # SPACE: lift off / return to space from the planet surface
                        try:
                            _terrains().leave_surface()
                        except Exception:
                            pass
                        globals()["active_planet_seed"] = None
                        globals()["game_mode"] = GAME_MODE_SPACE
                        mode = "space"
                        landed_planet_i = None
                        mission.return_to_orbit()
                        entry_block_planet_i = None
                        entry_block_dist = max(2200.0, ship.dist_to_planet)
                        entry_block_active = True
                        pygame.event.set_grab(True)
                        pygame.mouse.set_visible(False)
                        pygame.mouse.get_rel()
                        continue

            music.update()
            if not paused and not mission_brief_visible:
                try:
                    surface.update(dt, events)
                except Exception:
                    log("ERROR: surface update crashed (falling back to SPACE):\n" + traceback.format_exc())
                    terr.leave_surface()
                    globals()["active_planet_seed"] = None
                    globals()["game_mode"] = GAME_MODE_SPACE
                    mode = "space"
                    landed_planet_i = None
                    mission.return_to_orbit()
                    entry_block_planet_i = None
                    entry_block_dist = max(2200.0, ship.dist_to_planet)
                    entry_block_active = True
                    continue

                # Surface update may have entered or left a ruin; sync immediately.
                ambience.sync_surface_view(surface)

                # E at the archive ruin: the DreamCrawler team dives for the fragment.
                dive_structure = getattr(surface, "ruin_dive_request", None)
                if dive_structure is not None:
                    surface.ruin_dive_request = None
                    run_archive_dive(surface, dive_structure)
                    continue

                # Enter ship interior from the surface (TAB near ship)
                if getattr(surface, 'enter_interior_requested', False):
                    if bool(getattr(mission, "is_home_phase", False)):
                        surface.set_notification('SHIP ACCESS OFFLINE — EMERGENCY TRANSFER NOT YET TRIGGERED', 2.5)
                        surface.enter_interior_requested = False
                        continue
                    globals()['interior_return_mode'] = GAME_MODE_SURFACE
                    globals()['game_mode'] = GAME_MODE_INTERIOR
                    try:
                        _interiors().enter_interior(screen, ship)
                    except Exception:
                        log("ERROR: failed to enter interior from surface:\n" + traceback.format_exc())
                        globals()['game_mode'] = GAME_MODE_SURFACE
                    else:
                        pygame.event.set_grab(False)
                        pygame.mouse.set_visible(True)
                        continue

            surface.hud_visible = hud_visible
            try:
                surface.draw()
            except Exception:
                log("ERROR: surface draw crashed (falling back to SPACE):\n" + traceback.format_exc())
                terr.leave_surface()
                globals()["active_planet_seed"] = None
                globals()["game_mode"] = GAME_MODE_SPACE
                mode = "space"
                landed_planet_i = None
                mission.return_to_orbit()
                entry_block_planet_i = None
                entry_block_dist = max(2200.0, ship.dist_to_planet)
                entry_block_active = True
                continue
            draw_standard_layer("ruin" if getattr(surface, "mode", "surface") != "surface" else "surface")
            present_cover()
            continue

        # If surface mode is requested but terrain isn't cached yet, build it safely and show a loading screen.
        if game_mode == GAME_MODE_SURFACE and active_planet_seed is not None:
            try:
                terr = _terrains()
                terr.get_surface(active_planet_seed, screen, ship, forced_biome=args.test_biome if args.test_shot else None)
            except Exception:
                log("ERROR: surface build failed (falling back to SPACE):\n" + traceback.format_exc())
                _terrains().leave_surface()
                globals()["active_planet_seed"] = None
                globals()["game_mode"] = GAME_MODE_SPACE
                mode = "space"
                landed_planet_i = None
                mission.return_to_orbit()

                # Prevent re-triggering entry immediately while we're still within the entry radius.
                entry_block_planet_i = None
                entry_block_dist = max(2200.0, ship.dist_to_planet)
                entry_block_active = True
            else:
                # Next frame will enter the fast-path.
                screen.fill((0, 0, 0))
                msg = info_font.render("Generating terrain...", True, (220, 220, 240))
                screen.blit(msg, (20, 20))
                present_cover()
                continue

        system.update(dt, tsec)

        # A destroyed/devoured target must stop advertising a waypoint the
        # player can no longer reach. Unsecured data returns to the next-system
        # pool; carried data remains the player's responsibility to store.
        target_i = int(getattr(mission, "target_planet_index", -1))
        if (target_i >= 0 and target_i < len(system.planets)
                and not planet_is_landable(system.planets[target_i])):
            outcome = mission.resolve_target_loss("planet_destroyed")
            if outcome == "missed":
                hud_notice = "target world destroyed — data fragment will reappear next system"
                hud_notice_t = 3.4
            elif outcome == "carrying":
                hud_notice = "target world destroyed — secure carried data before warp"
                hud_notice_t = 3.4
            checkpoint_runtime("target_world_lost", force=True)

        # ----------------------------
        # Black hole lifecycle (after supernova completes -> 2 minute countdown -> devour phase)
        # ----------------------------
        if system.post_supernova and (not blackhole_active):
            if blackhole_deadline is None:
                blackhole_deadline = now_wall + blackhole_duration
                log('SYSTEM: Black hole countdown started.')
            blackhole_remaining = max(0.0, float(blackhole_deadline - now_wall))
            if now_wall >= blackhole_deadline:
                blackhole_active = True
                blackhole_remaining = 0.0
                system_has_bh = True
                # Bind BH to the star position so it replaces the brown dwarf remnant.
                if hasattr(main, '_bh_pos'):
                    main._bh_pos = system.star_pos
                else:
                    main._bh_pos = system.star_pos
                if not hasattr(main, '_bh'):
                    main._bh = BlackHole(seed=777)
                try:
                    main._bh.reset()
                except Exception:
                    pass
                system.blackhole_active = True
                system.blackhole_t0 = tsec
                log('SYSTEM: Black hole formed. Planets are being devoured.')
        elif blackhole_active:
            blackhole_remaining = 0.0
            system.blackhole_active = True
        else:
            blackhole_deadline = None
            blackhole_remaining = None


        inp = Inputs()

        events = []
        for e in pygame.event.get():
            gamepad.handle_event(e)
            if e.type == pygame.QUIT:
                inp.quit = True
            elif e.type == MusicPlayer.ENDEVENT:
                music.on_end()
            elif e.type == pygame.KEYDOWN:
                if run_intro_active:
                    if e.key in (getattr(pygame, "K_RETURN", 13), pygame.K_SPACE):
                        run_intro_active = False
                        mission.mark_run_started()
                        system_enter_time = time.time()
                        supernova_deadline = system_enter_time + supernova_duration
                        ship.capture_system_checkpoint(mission)
                        try:
                            ship.save_state()
                        except Exception:
                            pass
                        hud_notice = "data fragment signal locked — warp locked until secured or missed"
                        hud_notice_t = 3.0
                    elif e.key == pygame.K_ESCAPE:
                        running = False
                    continue
                if mission_brief_visible:
                    if e.key in (getattr(pygame, "K_m", 109), pygame.K_ESCAPE):
                        mission_brief_visible = False
                    continue
                if e.key == pygame.K_F11:
                    toggle_fullscreen()
                    hud_notice = "fullscreen desktop" if active_window_mode == "fullscreen" else ("borderless 1920x1080" if active_window_mode == "native_1080p" else "bordered window")
                    hud_notice_t = 1.8
                elif handle_standard_key(e.key):
                    pass
                elif e.key == pygame.K_f and not paused:
                    if bool(getattr(mission, "is_delivery_phase", False)):
                        hud_notice = "all data recovered — return to ship cockpit and contact Gleebs"
                        hud_notice_t = 3.0
                        continue
                    if bool(getattr(mission, "is_ship_recovery_phase", False)):
                        hud_notice = "ship recovery incomplete — use the interior stations"
                        hud_notice_t = 2.4
                        continue
                    if mission.carrying_fragment and not mission.fragment_deposited:
                        hud_notice = "secure data fragment in ship before warp"
                        hud_notice_t = 2.4
                        continue
                    if not bool(getattr(mission, "warp_unlocked", False)):
                        hud_notice = str(getattr(mission, "warp_lock_reason", "resolve current system goal before warp")).lower()
                        hud_notice_t = 3.0
                        continue
                    inp.hyper = True
                    if mode == "planet":
                        # Return warp: back to saved solar system without regeneration
                        warp_pending = True
                        warp_timer = 0.0
                        pending_galaxy = -1
                        pending_align = 1.0
                        warp_lock_yaw = ship.yaw
                        warp_lock_pitch = ship.pitch
                        warp_lock_roll = ship.roll
                        warp_lock_orientation = ship.orientation
                        planet_exit_requested = True
                    else:
                        fwd, _, _ = ship.forward_right_up()
                        gi, ga = galaxies.best_target_in_view(fwd)
                        pending_galaxy = gi
                        pending_align = ga

                        # The same progression quote drives both the HUD and
                        # the committed warp, so displayed range/cost cannot drift.
                        fuel = int(getattr(ship, "fuel", 0))
                        best_jumps, cost = warp_quote(ship)
                        if best_jumps <= 0:
                            hud_notice = f"insufficient fuel — warp requires {cost}"
                            hud_notice_t = 2.0
                        else:
                            ship.fuel = max(0, fuel - cost)
                            ship.state_dirty = True
                            try:
                                ship.save_state()
                            except Exception:
                                pass

                        globals()["pending_warp_jumps"] = int(best_jumps)

                        if best_jumps > 0:
                            warp_pending = True
                            warp_timer = 0.0
                            # lock heading at warp start; disable steering until warp completes
                            warp_lock_yaw = ship.yaw
                            warp_lock_pitch = ship.pitch
                            warp_lock_roll = ship.roll
                            warp_lock_orientation = ship.orientation

                        # lock heading at warp start; disable steering until warp completes
                        warp_lock_yaw = ship.yaw
                        warp_lock_pitch = ship.pitch
                        warp_lock_roll = ship.roll
                        warp_lock_orientation = ship.orientation
                elif e.key == pygame.K_c and not paused and globals().get("game_mode") == GAME_MODE_SPACE:
                    ship.flight_assist = not ship.flight_assist
                    hud_notice = "inertial dampers on" if ship.flight_assist else "inertial dampers off"
                    hud_notice_t = 1.5
                elif e.key == THIRD_PERSON_TOGGLE_KEY and not paused and globals().get("game_mode") == GAME_MODE_SPACE:
                    third_person_space = not third_person_space
                    hud_notice = "third-person" if third_person_space else "cockpit view"
                    hud_notice_t = 1.5
                elif e.key == pygame.K_TAB and not paused:
                    # Enter ship interior (separate module)
                    interior_return_mode = globals().get("game_mode", GAME_MODE_SPACE)
                    globals()["interior_return_mode"] = interior_return_mode
                    globals()["game_mode"] = GAME_MODE_INTERIOR
                    try:
                        _interiors().enter_interior(screen, ship, return_mode=interior_return_mode)
                    except Exception:
                        log("ERROR: failed to enter interior\\n" + traceback.format_exc())
                        globals()["game_mode"] = interior_return_mode
                    else:
                        # Interior is a 2D UI mode: release mouse
                        pygame.event.set_grab(False)
                        pygame.mouse.set_visible(True)

            elif e.type == getattr(pygame, "MOUSEBUTTONDOWN", 0x401) and paused:
                handle_pause_click(getattr(e, "pos", (-1, -1)))
            elif e.type == pygame.MOUSEMOTION and not paused and not run_intro_active and not mission_brief_visible:
                mx, my = e.rel
                inp.mouse_dx += mx
                inp.mouse_dy += my
            elif e.type == pygame.VIDEORESIZE and active_window_mode == "bordered":
                # Window resize never changes the native 1920x1080 render canvas.
                req_w = max(960, int(e.w))
                req_h = max(540, int(e.h))
                if req_w / max(1.0, float(req_h)) >= (16.0 / 9.0):
                    resize_h = req_h
                    resize_w = int(round(resize_h * 16.0 / 9.0))
                else:
                    resize_w = req_w
                    resize_h = int(round(resize_w * 9.0 / 16.0))
                display, window_flags, active_window_mode = open_display("bordered", (resize_w, resize_h))
                settings["window_mode"] = "bordered"
                settings["bordered_width"] = resize_w
                settings["bordered_height"] = resize_h
                save_all_settings()
                present_cache["surf"] = None
                present_cache["size"] = (0, 0)
                log(f"Resize: {resize_w}x{resize_h} (native canvas {VIRTUAL_W}x{VIRTUAL_H})")

        keys = pygame.key.get_pressed()
        if not paused and not run_intro_active and not mission_brief_visible:
            # Full 6DOF local-axis translation. Keyboard stays fully supported;
            # mapped gamepads add analog values without emulating a mouse cursor.
            inp.thrust_forward = keys[pygame.K_w]
            inp.thrust_reverse = keys[pygame.K_s]
            inp.strafe_left = keys[pygame.K_a]
            inp.strafe_right = keys[pygame.K_d]
            inp.vertical_up = keys[pygame.K_SPACE]
            inp.vertical_down = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]
            inp.brake = keys[pygame.K_x]

            inp.roll_left = keys[pygame.K_q]
            inp.roll_right = keys[pygame.K_e]

            inp.boost = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
            inp.interact = False
            inp.thrust_axis = 0.0
            inp.strafe_axis = 0.0
            inp.vertical_axis = 0.0
            inp.roll_axis = 0.0

            if bool(getattr(gamepad, "connected", False)):
                gx, gy = gamepad.move_vector()
                look_x, look_y = gamepad.look_vector()
                inp.strafe_axis = float(gx)
                inp.thrust_axis = -float(gy)
                inp.vertical_axis = float(gamepad.frame.trigger_right) - float(gamepad.frame.trigger_left)
                inp.roll_axis = (1.0 if gamepad.held("right_shoulder") else 0.0) - (1.0 if gamepad.held("left_shoulder") else 0.0)
                inp.boost = bool(inp.boost or gamepad.held("a"))
                inp.brake = bool(inp.brake or gamepad.held("b"))
                # Ship.update consumes relative look deltas; convert a stick rate
                # to the same per-frame delta path so mouse and controller share
                # quaternion damping and never diverge into separate flight code.
                inp.mouse_dx += float(look_x) * 720.0 * dt
                inp.mouse_dy += float(look_y) * 720.0 * dt

            # middle mouse roll mode
            mbtn = pygame.mouse.get_pressed(num_buttons=3)
            inp.roll_mouse = bool(mbtn[1])

            # hold LMB to fire
            inp.fire = bool(mbtn[0]) and SPACE_COMBAT_ENABLED

        if inp.quit:
            running = False

        if inp.pause_toggle:
            set_paused(not paused)

        # update
        # The normal path is free-flight space; level/interior paths continue above.
        sfx.set_context("space", thrusting=False)
        ambience.sync_space()
        # keep music flowing even when paused (fallback path if end-events aren't supported)
        music.update()
        if not paused and not run_intro_active and not mission_brief_visible:
            # --- WARP PRE-UPDATE OVERRIDE ---
            if warp_pending:
                # keep warping even if player releases the key
                inp.hyper = True
                # disable directional input while checks/generation are happening
                # hard-lock ship orientation to warp entry heading
                ship.yaw = warp_lock_yaw
                ship.pitch = warp_lock_pitch
                ship.roll = warp_lock_roll
                ship.set_orientation(warp_lock_orientation)

            if mode == "space" and system.planets:
                clearances = [max(0.0, vec3_len(vec3_sub(system.star_pos, ship.pos)) - system.star_radius)]
                for _pi in range(len(system.planets)):
                    if not planet_is_landable(system.planets[_pi]):
                        continue
                    _pp = system.planet_world_pos(_pi, tsec)
                    clearances.append(max(0.0, vec3_len(vec3_sub(_pp, ship.pos)) - system.planets[_pi].radius * 8.0))
                ship.local_clearance = min(clearances)
            else:
                ship.local_clearance = 0.0

            previous_ship_pos = ship.pos
            ship.update(dt, inp)

            # Stellar contact is a navigation reset, not a run-ending failure.
            # The swept check catches high-speed crossings between frames. The
            # current system, objective, cargo, hull, and collapse clock remain.
            if mode == "space" and not warp_pending and star_impact_detected(
                previous_ship_pos, ship.pos, system.star_pos, system.star_radius
            ):
                reset_ship_to_system_spawn(ship)
                missiles.items.clear()
                planet_entry_pending = False
                planet_entry_timer = 0.0
                planet_entry_surface_ready = False
                planet_entry_ready_index = None
                entry_block_active = False
                entry_block_planet_i = None
                hud_notice = "stellar impact — reset to system entry"
                hud_notice_t = 3.2
                collapse_banner = "SUN COLLISION — FLIGHT POSITION RESTORED"
                collapse_banner_t = 2.6
                log("NAV: sun collision reset ship to the current system spawn.")

            # A world that cannot currently transition to its surface is never
            # solid collision geometry. It becomes a soft exclusion volume that
            # removes inward momentum and places the ship back outside atmosphere.
            if mode == "space" and system.planets and not warp_pending:
                for _pi, _planet in enumerate(system.planets):
                    _blocked = bool(entry_block_active and entry_block_planet_i == _pi)
                    if planet_is_landable(_planet) and not _blocked:
                        continue
                    _pp = system.planet_world_pos(_pi, tsec)
                    _new_pos, _new_vel, _corrected = resolve_planet_exclusion(
                        ship.pos, ship.vel, _pp, _planet, force_blocked=_blocked
                    )
                    if _corrected:
                        ship.pos = _new_pos
                        ship.vel = _new_vel
                        ship.dist_to_planet = planet_exclusion_radius(_planet)
                        hud_notice = "planetfall unavailable — safe course corrected"
                        hud_notice_t = 1.8
                        log(f"NAV: deflected from unavailable planet P{_pi + 1}.")

            # If we requested leaving the planet, tear down planet-only objects early.
            if planet_exit_requested:
                planet_world = None
                planet_cam_x = 0.0
                current_planet_seed = 0
                planet_exit_requested = False

            # --- WARP STATE MACHINE ---
            # Keep warp active until new system is generated (and old system cleared).
            if warp_pending:
                warp_timer += dt
                ship.hyperspace = True

                # unload old system content immediately at warp start
                if warp_timer < 0.10:
                    system.planets = []

                # generate new system at arrival (always; no limiting)
                if warp_timer >= WARP_DURATION:
                    # If we were on a planet surface, this warp is a "return to orbit" into the SAME solar system.
                    if mode == "planet" and saved_space is not None:
                        # Restore ship + system context (same solar system seed)
                        ship.pos = saved_space.get("pos", (0.0, 0.0, 0.0))
                        ship.vel = saved_space.get("vel", (0.0, 0.0, 0.0))
                        ship.restore_orientation(saved_space)

                        system.generate(saved_space.get("system_seed", system.seed))
                        mission.apply_to_system(system)
                        system_index = saved_space.get("system_index", system_index)
                        system_has_bh = saved_space.get("system_has_bh", system_has_bh)

                        mode = "space"
                        landed_planet_i = None
                        mission.return_to_orbit()
                        planet_world = None
                        planet_cam_x = 0.0
                        current_planet_seed = 0

                        hud_notice = "returned to orbit"
                        hud_notice_t = 3.0

                        saved_space = None
                        log("Warp: returned to orbit (same solar system).")
                    else:
                        # Normal warp: generate a brand new solar system.
                        jumps = int(globals().get("pending_warp_jumps", 1) or 1)

                        # Multi-jump warp: we simply advance through 'jumps' seeds and land in the last.
                        # The old planet list is intentionally unloaded near warp start.
                        # MissionState retains the outgoing archive identity (including
                        # MISSED/dead-target runs), so use it as the variety authority.
                        previous_style = str(getattr(mission, "current_archive_style", "unknown") or "unknown")
                        new_seed = None
                        variety_rerolls = 0
                        for _j in range(jumps):
                            new_seed, variety_rerolls = _generate_varied_system(
                                system, random.randrange(1_000_000_000), previous_style
                            )
                            previous_style = str(getattr(system.planets[0], "style", "unknown")) if getattr(system, "planets", None) else previous_style

                        system_index += int(jumps)
                        mission.begin_system(system, system_index)
                                                
                        system_enter_time = time.time()
                        supernova_deadline = system_enter_time + supernova_duration
                        collapse_shock_applied = False
                        collapse_damage_pool = 0.0
                        collapse_banner = "NEW SYSTEM — CHECKPOINT COMMITTED"
                        collapse_banner_t = 2.8
                        last_collapse_state = mission.collapse_state
                        ship.capture_system_checkpoint(mission)
                        try:
                            ship.save_state()
                        except Exception:
                            pass
                        # reset black hole lifecycle for the new system
                        blackhole_deadline = None
                        blackhole_remaining = None
                        blackhole_active = False
                        system.blackhole_active = False
                        system.blackhole_t0 = None

                        system_has_bh = (system_index % 10 == 0)
                        if not system_has_bh and hasattr(main, '_bh_pos'):
                            delattr(main, '_bh_pos')

                        # respawn background stars on arrival
                        stars = Starfield(n=5200, seed=random.randrange(1_000_000_000))

                        # reset ship at origin in the new system
                        reset_ship_to_system_spawn(ship)

                        # reposition the black hole near the new system (if present)
                        if hasattr(main, '_bh_pos'):
                            main._bh_pos = vec3_add(system.star_pos, (1200.0, -500.0, -3200.0))

                        profile = world_profile(mission.target_style)
                        hud_notice = (
                            f"archive {mission.current_archive_slot}/{mission.data_fragments_required} — "
                            f"{profile.world_name} / {profile.record_name} — {mission.target_hazard_family} hazard"
                        )
                        hud_notice_t = 3.6
                        log(
                            f'Warp: arrived at new solar system (seed={new_seed}, target_galaxy={pending_galaxy}, '
                            f'align={pending_align:.3f}, style={mission.target_style}, rerolls={variety_rerolls}).'
                        )

                    # clear warp state and exit hyperspace
                    warp_pending = False
                    warp_timer = 0.0
                    pending_galaxy = -1
                    pending_align = -1.0
                    globals()["pending_warp_jumps"] = 1
                    ship.hyperspace = False

# --- PLANET ATMOSPHERE ENTRY (space -> planet) ---
            if (mode == "space") and (not ship.hyperspace) and (not warp_pending) and (not planet_entry_pending):
                # If we've just exited a planet (or a surface build failed), require the ship to move
                # clear of the entry radius before allowing another auto-entry.
                if entry_block_active and ship.dist_to_planet > entry_block_dist * 1.25:
                    entry_block_active = False

                if nearest_planet_i >= 0:
                    # Touch the atmosphere rather than the tiny old collision radius.
                    atmosphere_touch = planet_exclusion_radius(system.planets[nearest_planet_i])
                    if planet_is_landable(system.planets[nearest_planet_i]) and (not entry_block_active) and ship.dist_to_planet <= atmosphere_touch:
                        planet_entry_pending = True
                        planet_entry_timer = 0.0
                        planet_entry_surface_ready = False
                        planet_entry_ready_index = None
                        transition_gap_grace_frames = max(transition_gap_grace_frames, 4)
                        current_planet_seed = (system.seed * 1000 + nearest_planet_i * 97 + 12345) & 0x7fffffff
                        # Preload/generate the planet surface during the entry transition as soon as atmosphere is touched.
                        try:
                            _terrains().preload_surface(int(current_planet_seed), screen, ship)
                        except Exception:
                            log('WARN: surface preload failed (will retry on entry):\n' + traceback.format_exc())
                        mode = "landing"
                        warp_lock_yaw = ship.yaw
                        warp_lock_pitch = ship.pitch
                        warp_lock_roll = ship.roll
                        warp_lock_orientation = ship.orientation
                        saved_space = {
                            "pos": ship.pos,
                            "vel": ship.vel,
                            "yaw": ship.yaw,
                            "pitch": ship.pitch,
                            "roll": ship.roll,
                            "orientation": tuple(ship.orientation),
                            "system_seed": system.seed,
                            "system_index": system_index,
                            "system_has_bh": system_has_bh
                        }
                        globals()["surface_return_state"] = dict(saved_space)
                        entry_block_planet_i = nearest_planet_i
                        entry_block_dist = atmosphere_touch
                        entry_block_active = True
                        log(f"Planet entry: atmosphere touched (planet_i={nearest_planet_i}, seed={current_planet_seed}, trigger={atmosphere_touch:.1f}).")

            if planet_entry_pending:
                planet_entry_timer += dt
                # keep controls locked during entry
                ship.yaw = warp_lock_yaw
                ship.pitch = warp_lock_pitch
                ship.roll = warp_lock_roll
                ship.set_orientation(warp_lock_orientation)

                # Once the visible entry animation has run, prepare the entire
                # surface while KEEPING this transition authoritative on screen.
                # The actual game-mode handoff happens at the start of the next
                # frame, eliminating the old one-frame orbital flash.
                if planet_entry_timer >= PLANET_ENTRY_DURATION and not planet_entry_surface_ready:
                    try:
                        globals()["active_planet_seed"] = int(current_planet_seed)
                        ready_index = int(entry_block_planet_i if entry_block_planet_i is not None else nearest_planet_i)
                        mission.land_on(ready_index)
                        _terrains().enter_surface(active_planet_seed, screen, ship)
                        _terrains().get_surface(active_planet_seed, screen, ship).configure_mission(mission, ready_index)
                        planet_entry_ready_index = ready_index
                        planet_entry_surface_ready = True
                        transition_gap_grace_frames = max(transition_gap_grace_frames, 3)
                        log(f"Planet entry: surface ready behind transition (planet_i={ready_index}, seed={current_planet_seed}).")
                    except Exception:
                        log("ERROR: failed to enter planet surface:\n" + traceback.format_exc())
                        globals()["active_planet_seed"] = None
                        planet_entry_pending = False
                        planet_entry_surface_ready = False
                        planet_entry_ready_index = None
                        planet_entry_timer = 0.0
                        mode = "space"
                        ship.hyperspace = False
                        warp_pending = False
            missiles.update(dt)

            fwd, right, up = ship.forward_right_up()

            fired = False
            if SPACE_COMBAT_ENABLED and inp.fire:
                fired = missiles.spawn(ship.pos, fwd, ship.vel, ship.hyperspace)
                if fired:
                    if hasattr(sfx, "play_missile"):
                        sfx.play_missile()
                    else:
                        sfx.play_laser()

                        
            # Missile collisions (space only): sun triggers supernova; planets become pixel nebulae.
            if SPACE_COMBAT_ENABLED and mode != "planet":
                if missiles.items:
                    nxt_m = []
                    for ms in missiles.items:
                        hit = False
                        if vec3_len(vec3_sub(ms.pos, system.star_pos)) <= (system.star_radius * 1.05):
                            system.trigger_supernova(tsec, instant=True)
                            hit = True

                        if (not hit) and system.planets:
                            for pi in range(len(system.planets)):
                                p = system.planets[pi]
                                if getattr(p, "destroyed", False):
                                    continue
                                pp = system.planet_world_pos(pi, tsec)
                                if vec3_len(vec3_sub(ms.pos, pp)) <= (p.radius * 1.15):
                                    system.destroy_planet(pi, pp, rng_seed=int(tsec * 1000))
                                    hit = True
                                    break
                        if not hit:
                            nxt_m.append(ms)
                    missiles.items = nxt_m
# distance to nearest planet (for HUD) + nearest index
            nearest_planet_i = -1
            nearest_planet_pos = None
            if system.planets:
                dmin = 1e18
                for i in range(len(system.planets)):
                    if not planet_is_landable(system.planets[i]):
                        continue
                    pp = system.planet_world_pos(i, tsec)
                    d = vec3_len(vec3_sub(pp, ship.pos))
                    if d < dmin:
                        dmin = d
                        nearest_planet_i = i
                        nearest_planet_pos = pp
                ship.dist_to_planet = dmin
            else:
                ship.dist_to_planet = vec3_len(vec3_sub(system.star_pos, ship.pos))

            # SFX: engine state + one-shots
            thrusting = inp.boost or ship.hyperspace
            sfx.set_context("space", thrusting=thrusting)

            if inp.boost and not last_boost:
                sfx.play_boost()
            last_boost = inp.boost

            if ship.hyperspace and not last_hyper:
                sfx.play_hyper()
            last_hyper = ship.hyperspace

        # render
        render_pos = ship.pos
        screen.fill((6, 5, 4))

        if planet_entry_pending:
            # Atmosphere entry: hide space objects and show entry effect
            draw_atmosphere_entry(screen, w, h, tsec, strength=1.0)
        elif ship.hyperspace:
            # During warp: hide all space objects so it feels like we instantly departed.
            draw_warp_tunnel(screen, w, h, tsec, strength=1.0)
        elif mode == "planet":
            # Planet surface scene
            spd = ship.speed_norm * 120.0
            # camera scroll based on boost/forward intent for a sense of flight
            boost_factor = 1.6 if ship.boost_norm > 0.25 else 1.0
            planet_cam_x += (spd * dt) * boost_factor
            if planet_world is None:
                terr = _terrains()
                planet_world = terr.get_planet_world(current_planet_seed or 1)
            planet_world.draw(screen, w, h, tsec, planet_cam_x, spd)
        else:
            # stars (deep background)
            screen.fill((0, 0, 0))
            fwd, _, up = ship.forward_right_up()
            if third_person_space and (not ship.hyperspace):
                render_pos = vec3_add(vec3_sub(ship.pos, vec3_mul(fwd, 92.0 + ship.speed_norm * 28.0)), vec3_mul(up, 20.0))
            else:
                render_pos = ship.pos
            boost_warp = clamp(getattr(ship, 'boost_norm', 0.0), 0.0, 1.0)
            stars.draw(screen, w, h, ship.orientation, 0.0, 0.0, ship.vel, ship.speed_norm, boost_warp, tsec, hyperspace=False)

            # galaxies (warp targets behind everything)
            gi, ga = galaxies.best_target_in_view(fwd)
            galaxies.draw(screen, w, h, ship.orientation, 0.0, 0.0, tsec, highlight_idx=(gi if (ga >= 0.965) else -1))

            # solar system (star + orbiting planets)
            system.draw_star(screen, w, h, render_pos, ship.orientation, 0.0, 0.0, tsec)
            system.draw_planets(screen, w, h, render_pos, ship.orientation, 0.0, 0.0, tsec, mission, scanner_level(ship))
            if third_person_space and (not ship.hyperspace):
                draw_third_person_ship(screen, w, h, render_pos, ship.orientation, 0.0, 0.0, ship, tsec)

            # black hole in world space (rare)
            if system_has_bh:
                if not hasattr(main, "_bh_pos"):
                    main._bh_pos = vec3_add(system.star_pos, (1200.0, -500.0, -3200.0))
                bh_pos = main._bh_pos
                if not hasattr(main, "_bh"):
                    main._bh = BlackHole(seed=777)

                bh_visible, (bhx, bhy), bhr = project_sphere(w, h, render_pos, ship.orientation, 0.0, 0.0, bh_pos, k_px=68000.0, min_z=8.0)
                engage = bool(getattr(system, "blackhole_active", False)) or (vec3_len(vec3_sub(system.star_pos, bh_pos)) < 6500.0)
                main._bh.update(dt, engaged=engage)

                if bh_visible:
                    nearest_i = -1
                    nearest_d = 1e18
                    for i in range(len(system.planets)):
                        pp = system.planet_world_pos(i, tsec)
                        d = vec3_len(vec3_sub(pp, ship.pos))
                        if d < nearest_d:
                            nearest_d = d
                            nearest_i = i

                    planet_sphere = None
                    planet_center = None
                    planet_rpx = 0
                    if nearest_i >= 0:
                        pp = system.planet_world_pos(nearest_i, tsec)
                        vis, (psx, psy), pr = project_sphere(w, h, render_pos, ship.orientation, 0.0, 0.0, pp, k_px=system.planets[nearest_i].radius * 6200.0, min_z=10.0)
                        if vis and pr >= 10:
                            if planet is None:
                                planet = Planet(seed=1337)
                            planet_sphere = render_sphere(planet.tex, pr)
                            planet_center = (psx, psy)
                            planet_rpx = pr

                    main._bh.draw(
                        screen,
                        sink_center=(bhx, bhy),
                        eh_radius_px=max(6, int(bhr * 0.55)),
                        engaged=engage and (planet_sphere is not None),
                        planet_surf=planet_sphere,
                        planet_center=planet_center,
                        planet_radius_px=planet_rpx
                    )

        # Legacy projectile renderer remains dormant unless explicitly re-enabled.
        missiles.draw(screen, w, h, ship.orientation, 0.0, 0.0, render_pos if (mode == "space" and third_person_space and (not ship.hyperspace)) else ship.pos)

        # Cockpit art remains visible when the HUD is hidden; only instruments toggle.
        if not ((mode == "space") and third_person_space and (not ship.hyperspace)):
            cockpit.render(
                screen, w, h, ship, tsec,
                supernova_remaining=supernova_remaining,
                blackhole_remaining=blackhole_remaining,
                paused=paused, hud_visible=hud_visible,
            )

        if hud_notice_t > 0.0 and hud_notice and hud_visible:
            hud_notice_t = max(0.0, hud_notice_t - dt)
            notice_text = hud_notice.upper()
            if notice_text != hud_notice_cache_text or hud_notice_cache_panel is None:
                msg = notice_font.render(notice_text, True, (238, 244, 248))
                pad_x, pad_y = 22, 12
                panel = pygame.Surface((msg.get_width() + pad_x * 2, msg.get_height() + pad_y * 2), pygame.SRCALPHA)
                panel.fill((5, 8, 12, 188))
                panel.blit(msg, (pad_x, pad_y))
                hud_notice_cache_text = notice_text
                hud_notice_cache_panel = panel
            panel = hud_notice_cache_panel
            px = (w - panel.get_width()) // 2
            py = int(h * 0.14)
            screen.blit(panel, (px, py))

        # post fx
        fx.apply(screen, tsec)
        draw_standard_layer("space")
        present_cover()

    try:
        if not verification_mode:
            if not failure_active:
                ship.save_state(reason="clean_exit")
            persist_ui_settings()
            mark_session_clean_exit()
    except Exception:
        log("WARN: shutdown persistence failed\n" + traceback.format_exc())
    ambience.stop_all()
    sfx.stop_engine(80)
    gamepad.close()
    if not verification_mode:
        crash_reporter.shutdown()
    log("Shutdown: clean exit.")
    if inherited_display is not None:
        # Hosted by Afterlife of IO: the window and mixer belong to the host,
        # which returns to its title screen.  Only silence Entropy's audio.
        try:
            pygame.mixer.music.stop()
            pygame.mixer.stop()
        except pygame.error:
            pass
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
        return 0
    pygame.quit()
    return 0