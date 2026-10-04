
from __future__ import annotations

import colorsys
import math
import os
import random
import time
import traceback
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pygame

from gamepad_input import get_active_gamepad

from runtime_paths import LOG_DIR, SCREENSHOT_DIR
from ship_progression import add_resource, level, surface_speed_multiplier
from hazard_rules import evaluate_hazard
import ruin_dive
from expedition_identity import world_profile
from surface_landmarks import generate_landmarks
from surface_resources import harvest_id, harvest_yield, normalize_harvest_map
from surface_chunks import (
    CHUNK_CACHE_LIMIT, CHUNK_WORLD_SIZE, OBJECT_CACHE_LIMIT, TERRAIN_TEXELS_PER_UNIT,
    build_chunk_pixels, generate_chunk_objects, sample_geology,
)

ROOT = Path(__file__).resolve().parent

WORLD_SIZE = 384
FOV = math.pi / 3
HALF_FOV = FOV / 2
MOUSE_SENS = 0.0021
PITCH_LIMIT = 96
TOPDOWN_VIEW_WORLD_W = 160.0
TOPDOWN_VIEW_WORLD_H = 90.0
TOPDOWN_MAP_SCALE = 4  # 640x360 internal terrain crop; exact 3x presentation at 1080p
PLAYER_RADIUS = 0.18
NUM_RAYS = 360
MAX_DEPTH = 24.0
DELTA_ANGLE = FOV / NUM_RAYS
INDOOR_MOVE_SPEED = 0.043
SURFACE_WALK_SPEED = 10.5  # world units per second; frame-rate independent
SURFACE_ACCEL_RESPONSE = 12.0
SURFACE_BRAKE_RESPONSE = 15.0
SURFACE_CAMERA_RESPONSE = 7.5
SURFACE_CAMERA_LOOKAHEAD = 3.6
SURFACE_RECOVERY_FX_LIMIT = 6
MIN_SPAWN_DIST = 8.0
MAX_SPAWN_DIST = 15.0
ALIEN_SPEED = 0.013
ALIEN_CATCH_DIST = 0.58
SPAWN_CHANCE_PER_SEC = 0.10

BIOMES = [
    # Legacy worlds, now given explicit weather and dormant-art identities.
    {'name': 'Serekh Dunes', 'terrain': 'desert', 'sky': (224, 180, 120), 'fog': (245, 214, 170), 'base_hue': 0.10, 'accent_hue': 0.86, 'weather': 'sand', 'fog_density': 0.92, 'prop_files': ('decor/8.png', 'decor/9.png', 'collision/1.png'), 'prop_density': 48, 'relic_art': (10, 16, 17, 18, 19)},
    {'name': 'Nivalis Reach', 'terrain': 'ice', 'sky': (138, 168, 214), 'fog': (192, 216, 246), 'base_hue': 0.58, 'accent_hue': 0.10, 'weather': 'snow', 'fog_density': 1.05, 'prop_files': ('decor/3.png', 'decor/6.png', 'collision/5.png'), 'prop_density': 56, 'relic_art': (2, 14, 15, 20, 31)},
    {'name': 'Viridian Crown', 'terrain': 'jungle', 'sky': (124, 170, 122), 'fog': (164, 208, 158), 'base_hue': 0.33, 'accent_hue': 0.72, 'weather': 'rain', 'fog_density': 1.08, 'prop_files': ('decor/1.png', 'decor/2.png', 'decor/5.png', 'collision/9.png'), 'prop_density': 84, 'relic_art': (11, 12, 13, 18, 23)},
    {'name': 'Cinder Atlas', 'terrain': 'volcanic', 'sky': (132, 98, 102), 'fog': (178, 130, 122), 'base_hue': 0.01, 'accent_hue': 0.12, 'weather': 'ash', 'fog_density': 1.18, 'prop_files': ('collision/6.png', 'collision/7.png', 'collision/8.png', 'decor/9.png'), 'prop_density': 62, 'relic_art': (21, 27, 33, 41, 46)},
    {'name': 'Aurel Glass', 'terrain': 'crystal', 'sky': (126, 146, 205), 'fog': (188, 208, 248), 'base_hue': 0.70, 'accent_hue': 0.92, 'weather': 'shards', 'fog_density': 0.88, 'prop_files': ('decor/4.png', 'decor/6.png', 'decor/8.png', 'collision/3.png'), 'prop_density': 72, 'relic_art': (20, 26, 30, 36, 43)},
    {'name': 'Pelagos Vault', 'terrain': 'oceanic', 'sky': (108, 160, 188), 'fog': (156, 210, 224), 'base_hue': 0.53, 'accent_hue': 0.18, 'weather': 'mist', 'fog_density': 1.22, 'prop_files': ('decor/1.png', 'decor/3.png', 'decor/7.png', 'collision/5.png'), 'prop_density': 74, 'relic_art': (1, 24, 28, 35, 44)},

    # Pass 2 world families.  Each changes terrain grammar, atmosphere, ruins and field objects.
    {'name': 'Mycelian Bloom', 'terrain': 'fungal', 'sky': (96, 72, 126), 'fog': (174, 112, 184), 'base_hue': 0.86, 'accent_hue': 0.46, 'weather': 'spores', 'fog_density': 1.26, 'prop_files': ('decor/1.png', 'decor/2.png', 'decor/5.png', 'decor/6.png', 'decor/7.png'), 'prop_density': 112, 'relic_art': (11, 12, 13, 18, 23)},
    {'name': 'Ferric Grave', 'terrain': 'rust', 'sky': (154, 92, 66), 'fog': (206, 138, 92), 'base_hue': 0.055, 'accent_hue': 0.13, 'weather': 'cinders', 'fog_density': 1.03, 'prop_files': ('collision/1.png', 'collision/2.png', 'collision/4.png', 'collision/7.png', 'collision/8.png'), 'prop_density': 76, 'relic_art': (10, 15, 16, 17, 19)},
    {'name': 'Ilyr Salt Mirror', 'terrain': 'salt', 'sky': (190, 182, 210), 'fog': (238, 232, 244), 'base_hue': 0.72, 'accent_hue': 0.12, 'weather': 'salt', 'fog_density': 0.74, 'prop_files': ('collision/5.png', 'collision/8.png', 'decor/8.png', 'decor/9.png'), 'prop_density': 36, 'relic_art': (14, 21, 22, 25, 31)},
    {'name': 'Noctilucent Basin', 'terrain': 'abyss', 'sky': (24, 38, 72), 'fog': (54, 142, 166), 'base_hue': 0.56, 'accent_hue': 0.48, 'weather': 'embers', 'fog_density': 1.34, 'prop_files': ('decor/3.png', 'decor/4.png', 'decor/8.png', 'hostile/7.png', 'hostile/8.png', 'hostile/9.png'), 'prop_density': 82, 'relic_art': (2, 24, 27, 35, 44)},
    {'name': 'Tempest Plateaus', 'terrain': 'storm', 'sky': (74, 92, 126), 'fog': (146, 166, 190), 'base_hue': 0.60, 'accent_hue': 0.12, 'weather': 'tempest', 'fog_density': 1.14, 'prop_files': ('collision/4.png', 'collision/5.png', 'collision/7.png', 'decor/3.png'), 'prop_density': 58, 'relic_art': (1, 28, 32, 40, 47)},
    {'name': 'Roseglass Barrens', 'terrain': 'roseglass', 'sky': (144, 74, 122), 'fog': (224, 146, 190), 'base_hue': 0.92, 'accent_hue': 0.52, 'weather': 'glass', 'fog_density': 0.94, 'prop_files': ('collision/3.png', 'collision/6.png', 'decor/4.png', 'decor/6.png', 'decor/9.png'), 'prop_density': 88, 'relic_art': (20, 26, 30, 36, 43)},
]
BIOME_BY_TERRAIN = {item['terrain']: item for item in BIOMES}
BIOME_IDS = tuple(item['terrain'] for item in BIOMES)

STRUCTURE_LIBRARY = [
    ('ziggurat', 'Solar Ziggurat', 'dungeon'),
    ('observatory', 'Orbital Observatory', 'dungeon'),
    ('bastion', 'Astral Bastion', 'castle'),
    ('spire', 'Archive Spire', 'castle'),
    ('sepulcher', 'Buried Sepulcher', 'catacomb'),
    ('labyrinth', 'Relic Labyrinth', 'catacomb'),
]


def _log(msg: str) -> None:
    try:
        with (LOG_DIR / 'runtime.log').open('a', encoding='utf-8') as f:
            f.write(msg.rstrip() + '\n')
    except Exception:
        pass


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def hsv_to_rgb255(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s, 0.0, 1.0), clamp(v, 0.0, 1.0))
    return int(r * 255), int(g * 255), int(b * 255)


def boost_vibrance(rgb, vib=1.25):
    r, g, b = rgb
    m = (r + g + b) / 3.0
    return (
        int(clamp(m + (r - m) * vib, 0, 255)),
        int(clamp(m + (g - m) * vib, 0, 255)),
        int(clamp(m + (b - m) * vib, 0, 255)),
    )


def value_noise_2d(seed, w, h, grid=32):
    rng = random.Random(seed)
    gw = w // grid + 3
    gh = h // grid + 3
    nodes = [[rng.random() for _ in range(gw)] for __ in range(gh)]
    out = [[0.0] * w for _ in range(h)]
    for y in range(h):
        gy = y / grid
        y0 = int(gy)
        ty = smoothstep(gy - y0)
        n0 = nodes[y0]
        n1 = nodes[y0 + 1]
        row = out[y]
        for x in range(w):
            gx = x / grid
            x0 = int(gx)
            tx = smoothstep(gx - x0)
            a = lerp(n0[x0], n0[x0 + 1], tx)
            b = lerp(n1[x0], n1[x0 + 1], tx)
            row[x] = lerp(a, b, ty)
    return out


def fractal_noise(seed, w, h):
    n1 = value_noise_2d(seed + 11, w, h, 64)
    n2 = value_noise_2d(seed + 29, w, h, 32)
    n3 = value_noise_2d(seed + 47, w, h, 16)
    out = [[0.0] * w for _ in range(h)]
    for y in range(h):
        row = out[y]
        a1, a2, a3 = n1[y], n2[y], n3[y]
        for x in range(w):
            row[x] = a1[x] * 0.55 + a2[x] * 0.30 + a3[x] * 0.15
    return out


@dataclass
class OverworldStructure:
    x: float
    y: float
    seed: int
    kind: str
    title: str
    interior_type: str
    radius: float
    sprite: pygame.Surface


@dataclass
class DungeonCreature:
    x: float
    y: float
    seed: int
    sprite: pygame.Surface
    seen: bool = False


@dataclass
class DungeonProp:
    x: float
    y: float
    kind: str
    seed: int
    sprite: pygame.Surface


class PlanetBackdrop:
    def __init__(self, seed: int):
        rng = random.Random(seed)
        self.name = random.Random(seed ^ 0xCAFE).choice(BIOMES)['name']
        self.sky = hsv_to_rgb255(rng.random(), 0.35, 0.88)
        self.horizon = hsv_to_rgb255((rng.random() + 0.1) % 1.0, 0.55, 0.72)
        self.moons = []
        for i in range(rng.randint(2, 4)):
            self.moons.append((rng.randint(80, 1840), rng.randint(60, 280), rng.randint(24, 72), hsv_to_rgb255(rng.random(), 0.4, 0.95)))

    def draw(self, screen: pygame.Surface, w: int, h: int, tsec: float, cam_x: float, spd: float) -> None:
        for y in range(h):
            t = y / max(1, h - 1)
            col = (
                int(lerp(self.sky[0], self.horizon[0], t)),
                int(lerp(self.sky[1], self.horizon[1], t)),
                int(lerp(self.sky[2], self.horizon[2], t)),
            )
            screen.fill(col, (0, y, w, 1))
        for x, y, r, col in self.moons:
            xx = int(x - (cam_x * 0.4) % (w + r * 2))
            yy = int(y + math.sin(tsec * 0.2 + x * 0.01) * 2.5)
            pygame.draw.circle(screen, col, (xx, yy), r)
            pygame.draw.circle(screen, (255, 255, 255), (xx - max(4, r // 3), yy - max(4, r // 3)), max(4, r // 6))
        ground_y = int(h * 0.62)
        for y in range(ground_y, h):
            t = (y - ground_y) / max(1, h - ground_y)
            col = (
                int(lerp(self.horizon[0] * 0.55, 20, t)),
                int(lerp(self.horizon[1] * 0.45, 18, t)),
                int(lerp(self.horizon[2] * 0.40, 16, t)),
            )
            screen.fill(col, (0, y, w, 1))


class SurfaceView:
    def __init__(self, seed: int, screen: pygame.Surface, ship=None, forced_biome: Optional[str] = None) -> None:
        self.seed = int(seed)
        self.screen = screen
        self.ship = ship
        self.forced_biome = forced_biome if forced_biome in BIOME_BY_TERRAIN else None
        self.mode = 'surface'
        self.enter_interior_requested = False
        # Set when E is pressed at the archive ruin; space_core runs the
        # DreamCrawler dive in the live window and clears it.
        self.ruin_dive_request = None
        self.notification = ''
        self.notification_until = 0.0
        self.hud_visible = True
        # Planet surfaces use the standardized top-down gameplay view.
        self.topdown_map = None
        self.topdown_map_size = (0, 0)
        self.topdown_sprite_cache = {}
        self._topdown_layers = {}
        self._topdown_spatial_index = {}
        self._topdown_visible_cache_key = None
        self._topdown_visible_cache = ((), (), ())
        self._terrain_chunk_cache = OrderedDict()
        self._procedural_object_cache = OrderedDict()
        self._topdown_scaled_surface = None
        self._topdown_scaled_size = (0, 0)
        self.frame_counter = 0
        self.surface_facing = 'up'
        self.surface_is_moving = False
        self.surface_anim_time = 0.0
        # Pass 23 separates physical movement from the presentation camera.
        # Acceleration removes keyboard-start/stop snapping, while a restrained
        # velocity look-ahead lets the world pan without losing the actor.
        self.surface_vel_x = 0.0
        self.surface_vel_y = 0.0
        self.surface_view_x = 0.0
        self.surface_view_y = 0.0
        self.surface_entry_fade = 1.0
        self.surface_recovery_fx = []
        # Pass 16 mission binding. The same state object follows the player
        # from orbit to surface, ruin, and ship interior.
        self.mission_state = getattr(ship, 'mission_state', None)
        self.mission_planet_index = None
        self.mission_target_structure = None
        self.fragment_pos = None
        self.fragment_recovery_flash = 0.0
        self.fragment_sprite = None
        self.resource_cache_pos = None
        self.resource_cache_role = None
        self.resource_cache_claimed = False
        self.harvested_ids = set()
        self._harvest_state_loaded = False
        self.harvest_candidate = None
        self.harvest_scan_at = 0.0
        self.harvest_scan_pos = (-999.0, -999.0)
        # Pass 26 surface-hazard runtime. These values are ephemeral and
        # deterministic from the live world state; no save-schema change.
        self.surface_elapsed = 0.0
        self.hazard_frame = evaluate_hazard("UNKNOWN", distance_from_ship=0.0, elapsed_seconds=0.0)
        self._px = 0.0
        self._py = 0.0
        self.ship_pos = (0.0, 0.0)
        self.lowres = None
        self.lowres_size = (0, 0)
        self._grain = []
        self._grain_i = 0
        self.fps_font = pygame.font.SysFont('consolas', 20)
        self.title_font = pygame.font.SysFont('consolas', 26)
        self.bg_world = PlanetBackdrop(seed)
        self._build_textures()
        self.fragment_sprite = self.make_fragment_sprite(self.seed ^ 0xF16A6E)
        self._build_world()

    @property
    def px(self):
        return self._px

    @property
    def py(self):
        return self._py

    def set_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen

    def _build_textures(self) -> None:
        self.stone_tex = self.make_stone_texture(self.seed ^ 17)
        self.floor_tex = self.make_pattern_texture(self.seed ^ 31, (118, 88, 62), (68, 50, 38))
        self.ceil_tex = self.make_pattern_texture(self.seed ^ 43, (72, 66, 84), (42, 38, 54))
        self.door_tex = self.make_door_texture(self.seed ^ 61)
        self.active_wall_tex = self.stone_tex
        self.active_panel_tex = self.tint_texture(self.stone_tex, (168, 136, 108), 10)
        self.active_floor_tex = self.floor_tex
        self.active_ceil_tex = self.ceil_tex
        self.active_door_tex = self.door_tex
        self.topdown_player_frames = {}
        for direction, files in {
            'up': ('assets/player/up/step1.png', 'assets/player/up/step2.png'),
            'down': ('assets/player/down/step1.png', 'assets/player/down/step2.png'),
            'left': ('assets/player/left/1.png', 'assets/player/left/2.png'),
            'right': ('assets/player/right/1.png', 'assets/player/right/2.png'),
        }.items():
            frames = []
            for rel in files:
                path = ROOT / rel
                try:
                    if path.is_file():
                        frames.append(pygame.image.load(str(path)).convert_alpha())
                except Exception:
                    _log(f'WARN: top-down player frame failed to load: {path}\n{traceback.format_exc()}')
            if frames:
                self.topdown_player_frames[direction] = frames

    def _ensure_lowres(self) -> None:
        w, h = self.screen.get_size()
        target = (max(320, w // 2), max(180, h // 2))
        if self.lowres is None or self.lowres_size != target:
            self.lowres = pygame.Surface(target)
            self.lowres_size = target
            self._grain = []
            rr = random.Random(self.seed ^ 0xBEEF)
            for _ in range(4):
                g = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
                for __ in range(max(800, (w * h) // 1800)):
                    x = rr.randrange(0, w)
                    y = rr.randrange(0, h)
                    a = rr.randrange(0, 16)
                    v = rr.randrange(120, 255)
                    g.set_at((x, y), (v, v, v, a))
                self._grain.append(g)

    def _build_world(self) -> None:
        rng = random.Random(self.seed)
        self.biome = BIOME_BY_TERRAIN[self.forced_biome] if self.forced_biome else rng.choice(BIOMES)
        self.planet_name = self.build_planet_name(self.seed)
        self.world_size = WORLD_SIZE
        n = fractal_noise(self.seed, WORLD_SIZE, WORLD_SIZE)
        ridge_noise = value_noise_2d(self.seed + 200, WORLD_SIZE, WORLD_SIZE, 48)
        dune_noise = value_noise_2d(self.seed + 444, WORLD_SIZE, WORLD_SIZE, 20)
        light_noise = value_noise_2d(self.seed + 888, WORLD_SIZE, WORLD_SIZE, 64)
        self.height = [[0] * WORLD_SIZE for _ in range(WORLD_SIZE)]
        self.color = [[(0, 0, 0)] * WORLD_SIZE for _ in range(WORLD_SIZE)]
        terrain = self.biome['terrain']
        for y in range(WORLD_SIZE):
            for x in range(WORLD_SIZE):
                base = n[y][x]
                ridge = (1.0 - abs(2.0 * base - 1.0)) ** (3.2 if terrain in ('ice', 'crystal') else 2.1)
                dune = math.sin((x * 0.035) + dune_noise[y][x] * 4.8) * 0.08 if terrain == 'desert' else 0.0
                ocean = -0.12 if terrain == 'oceanic' else 0.0
                jungle = 0.05 if terrain == 'jungle' else 0.0
                volcanic = (ridge_noise[y][x] - 0.5) * 0.22 if terrain == 'volcanic' else 0.0
                h = clamp(base * 0.48 + ridge * 0.44 + dune + ocean + jungle + volcanic, 0.0, 1.0)
                if terrain == 'fungal':
                    # Rolling organic basins with swollen ridges.
                    h = clamp(base * 0.40 + ridge * 0.24 + (0.62 - ridge_noise[y][x]) * 0.13 + (dune_noise[y][x] - 0.5) * 0.08, 0.0, 1.0)
                elif terrain == 'rust':
                    # Eroded, stepped badlands and broad iron mesas.
                    raw = clamp(base * 0.38 + ridge * 0.42 + (ridge_noise[y][x] - 0.5) * 0.18, 0.0, 1.0)
                    h = round(raw * 8.0) / 8.0
                elif terrain == 'salt':
                    # Extremely flat reflective plain broken by rare mineral islands.
                    island = max(0.0, ridge_noise[y][x] - 0.80) * 2.6
                    h = clamp(0.30 + (base - 0.5) * 0.16 + island, 0.0, 1.0)
                elif terrain == 'abyss':
                    # Deep basins with isolated luminous knife ridges.
                    h = clamp(base * 0.22 + (ridge ** 1.65) * 0.76 - 0.10 + (dune_noise[y][x] - 0.5) * 0.06, 0.0, 1.0)
                elif terrain == 'storm':
                    # Broad elevated shelves suitable for violent horizon weather.
                    raw = clamp(base * 0.34 + ridge * 0.50 + 0.08, 0.0, 1.0)
                    h = round(raw * 6.0) / 6.0
                elif terrain == 'roseglass':
                    # Tall crystalline splinters and narrow valleys.
                    h = clamp(base * 0.22 + (ridge ** 1.30) * 0.78 + (ridge_noise[y][x] - 0.5) * 0.08, 0.0, 1.0)
                hv = int(h * 255)
                self.height[y][x] = hv
                hue = (self.biome['base_hue'] + (ridge_noise[y][x] - 0.5) * 0.18 + (dune_noise[y][x] - 0.5) * 0.10) % 1.0
                sat = 0.55 + ridge_noise[y][x] * 0.28
                val = 0.48 + h * 0.46
                if terrain == 'desert':
                    hue = (0.08 + (dune_noise[y][x] - 0.5) * 0.04) % 1.0
                    sat = 0.55 + dune_noise[y][x] * 0.18
                    val = 0.60 + h * 0.28
                elif terrain == 'ice':
                    hue = (0.56 + (ridge_noise[y][x] - 0.5) * 0.08) % 1.0
                    sat = 0.28 + ridge_noise[y][x] * 0.14
                    val = 0.68 + h * 0.22
                elif terrain == 'jungle':
                    hue = (0.30 + (ridge_noise[y][x] - 0.5) * 0.07) % 1.0
                    sat = 0.62 + ridge_noise[y][x] * 0.22
                    val = 0.44 + h * 0.32
                elif terrain == 'volcanic':
                    hue = (0.02 + (ridge_noise[y][x] - 0.5) * 0.05) % 1.0
                    sat = 0.48 + ridge_noise[y][x] * 0.18
                    val = 0.32 + h * 0.28
                elif terrain == 'crystal':
                    hue = (0.70 + (ridge_noise[y][x] - 0.5) * 0.10) % 1.0
                    sat = 0.38 + ridge_noise[y][x] * 0.18
                    val = 0.56 + h * 0.30
                elif terrain == 'oceanic':
                    hue = (0.53 + (ridge_noise[y][x] - 0.5) * 0.06) % 1.0
                    sat = 0.54 + ridge_noise[y][x] * 0.16
                    val = 0.42 + h * 0.26
                elif terrain == 'fungal':
                    hue = (0.82 + (ridge_noise[y][x] - 0.5) * 0.18 + (0.09 if dune_noise[y][x] > 0.64 else 0.0)) % 1.0
                    sat = 0.58 + ridge_noise[y][x] * 0.24
                    val = 0.38 + h * 0.38
                elif terrain == 'rust':
                    hue = (0.045 + (ridge_noise[y][x] - 0.5) * 0.045) % 1.0
                    sat = 0.62 + ridge_noise[y][x] * 0.20
                    val = 0.34 + h * 0.38
                elif terrain == 'salt':
                    hue = (0.67 + (ridge_noise[y][x] - 0.5) * 0.05) % 1.0
                    sat = 0.10 + ridge_noise[y][x] * 0.10
                    val = 0.76 + h * 0.18
                elif terrain == 'abyss':
                    hue = (0.54 + (ridge_noise[y][x] - 0.5) * 0.10) % 1.0
                    sat = 0.66 + ridge_noise[y][x] * 0.20
                    val = 0.20 + h * 0.46
                elif terrain == 'storm':
                    hue = (0.60 + (ridge_noise[y][x] - 0.5) * 0.055) % 1.0
                    sat = 0.26 + ridge_noise[y][x] * 0.20
                    val = 0.42 + h * 0.34
                elif terrain == 'roseglass':
                    hue = (0.92 + (ridge_noise[y][x] - 0.5) * 0.12) % 1.0
                    sat = 0.48 + ridge_noise[y][x] * 0.26
                    val = 0.40 + h * 0.42
                r, g, b = hsv_to_rgb255(hue, sat, val)
                lift = int((light_noise[y][x] - 0.5) * 20)
                self.color[y][x] = boost_vibrance((int(clamp(r + lift + 72, 0, 255)), int(clamp(g + lift + 72, 0, 255)), int(clamp(b + lift + 72, 0, 255))), 1.18)

        self.spawn_x = WORLD_SIZE // 2
        self.spawn_y = WORLD_SIZE // 2
        self.cam_x = self.spawn_x + 12.0
        self.cam_y = self.spawn_y + 10.0
        self.cam_ang = 0.0
        self.pitch = 0.0
        self.surface_vel_x = 0.0
        self.surface_vel_y = 0.0
        self.surface_view_x = self.cam_x
        self.surface_view_y = self.cam_y
        self.surface_entry_fade = 1.0
        self.surface_recovery_fx = []
        self.ship_pos = (self.spawn_x + 6.0, self.spawn_y + 8.0)
        self._px = self.cam_x
        self._py = self.cam_y
        self.storm_t = 0.0
        self.storm_end = 0.0
        self.storm_active = False
        self.storm_intensity = 0.0
        self.surface_elapsed = 0.0
        self.hazard_frame = evaluate_hazard("UNKNOWN", distance_from_ship=0.0, elapsed_seconds=0.0)
        self.sky_bodies = self.make_sky_bodies(self.seed)
        self.structures = []
        self.structures_by_seed = {}
        self.landmarks = []
        self.motes = []
        self.trees = []
        self.plants = []
        self.world_props = []
        self.surface_harvest_count = 0
        self.world_prop_sprites = []
        self.build_structures()
        self.landmarks = list(generate_landmarks(self.seed, self.biome['terrain'], self.ship_pos, self.structures, world_size=WORLD_SIZE, count=3))
        self.build_foliage()
        self.build_world_props()
        self.build_motes()
        self._build_topdown_spatial_index()
        self.active_structure = None
        self.dungeon_map = []
        self.map_w = 0
        self.map_h = 0
        self.interior_px = 3.5
        self.interior_py = 3.5
        self.interior_angle = 0.0
        self.interior_pitch = 0.0
        self.interior_props = []
        self.interior_creatures = []
        self.current_area = 'dungeon'
        self.interior_theme = 'Star Tomb'
        self.last_spawn_check = time.time()
        self.particles = []
        self.set_notification(f'{self.planet_name}: seamless planetary surface online', 2.2)
        # Pass 22 streams deterministic chunks around the camera.  The finite
        # Pass 21 map is retained only as a compatibility fallback for old
        # tools and is no longer allocated at planetfall.
        self.topdown_map = None
        self.topdown_map_size = (0, 0)

    def set_notification(self, text: str, duration: float = 2.0) -> None:
        self.notification = text
        self.notification_until = time.time() + duration

    def _store_recovered_resource(self, resource: str, amount: int) -> int:
        """HOME keeps recovered material in the field pack until ship storage is restored."""
        amount = max(0, int(amount))
        mission = self.mission_state
        if self.ship is None or amount <= 0:
            return 0
        if bool(getattr(mission, 'is_home_phase', False)):
            pack = getattr(self.ship, 'player_pack', None)
            if not isinstance(pack, dict):
                pack = {}
                self.ship.player_pack = pack
            pack[resource] = max(0, int(pack.get(resource, 0))) + amount
            self.ship.state_dirty = True
            return int(pack[resource])
        return add_resource(self.ship, resource, amount)

    def configure_mission(self, mission, planet_index: int) -> None:
        """Bind the live mission state to this generated surface.

        This is idempotent and may be called every frame after planetfall.
        """
        self.mission_state = mission
        self.mission_planet_index = int(planet_index)
        if self.ship is not None and not self._harvest_state_loaded:
            self.ship.surface_harvests = normalize_harvest_map(getattr(self.ship, 'surface_harvests', {}))
            self.harvested_ids = set(self.ship.surface_harvests.get(str(self.seed), ()))
            self._harvest_state_loaded = True
        if mission is None:
            self.mission_target_structure = None
            self.resource_cache_pos = None
            self.resource_cache_role = None
            return
        if mission.current_planet_index != self.mission_planet_index:
            mission.land_on(self.mission_planet_index)

        # Optional signal worlds expose one deterministic, reachable resource
        # cache. It is separate from the primary fragment ruin route.
        role = mission.resource_role(self.mission_planet_index)
        claimed = mission.resource_claimed(self.mission_planet_index)
        self.resource_cache_role = role
        self.resource_cache_claimed = claimed
        if role and not claimed:
            if self.resource_cache_pos is None:
                rng = random.Random(self.seed ^ self.mission_planet_index ^ 0xCACE17)
                candidates = []
                for _ in range(16):
                    ang = rng.uniform(0.0, math.tau)
                    dist = rng.uniform(34.0, 58.0)
                    x = clamp(self.ship_pos[0] + math.cos(ang) * dist, 12.0, WORLD_SIZE - 13.0)
                    y = clamp(self.ship_pos[1] + math.sin(ang) * dist, 12.0, WORLD_SIZE - 13.0)
                    if all(math.hypot(x - st.x, y - st.y) >= 18.0 for st in self.structures):
                        candidates.append((x, y))
                self.resource_cache_pos = candidates[0] if candidates else (
                    clamp(self.ship_pos[0] + 42.0, 12.0, WORLD_SIZE - 13.0),
                    clamp(self.ship_pos[1] + 18.0, 12.0, WORLD_SIZE - 13.0),
                )
        else:
            self.resource_cache_pos = None

        target_seed = mission.bind_surface_target(self.seed, self.structures, self.ship_pos)
        self.mission_target_structure = None
        if target_seed is not None:
            for structure in self.structures:
                is_target = int(structure.seed) == int(target_seed)
                setattr(structure, 'is_mission_target', is_target)
                if is_target:
                    self.mission_target_structure = structure
        else:
            for structure in self.structures:
                setattr(structure, 'is_mission_target', False)
        self._sync_mission_distance()

    def _sync_mission_distance(self) -> None:
        mission = self.mission_state
        if mission is None:
            return
        if mission.carrying_fragment:
            distance = math.hypot(self.cam_x - self.ship_pos[0], self.cam_y - self.ship_pos[1])
        elif self.mode == 'surface' and self.resource_cache_pos is not None and not self.resource_cache_claimed:
            distance = math.hypot(self.cam_x - self.resource_cache_pos[0], self.cam_y - self.resource_cache_pos[1])
        elif self.mode == 'surface' and self.mission_target_structure is not None:
            distance = math.hypot(self.cam_x - self.mission_target_structure.x, self.cam_y - self.mission_target_structure.y)
        elif self.mode != 'surface' and self.fragment_pos is not None:
            distance = math.hypot(self.interior_px - self.fragment_pos[0], self.interior_py - self.fragment_pos[1])
        else:
            distance = None
        mission.update_surface_target_distance(distance)

    def resource_cache_distance(self) -> float:
        if self.resource_cache_pos is None:
            return 1e9
        return math.hypot(self.cam_x - self.resource_cache_pos[0], self.cam_y - self.resource_cache_pos[1])

    def try_collect_resource(self) -> bool:
        if (
            self.mode != 'surface'
            or self.resource_cache_pos is None
            or self.resource_cache_claimed
            or self.mission_state is None
            or self.ship is None
            or self.resource_cache_distance() > 8.0
        ):
            return False
        role = self.mission_state.claim_resource(self.mission_planet_index)
        if role is None:
            return False
        if role == 'home':
            fuel_amount = 4
            salvage_amount = 6
            self._store_recovered_resource('fuel_cells', fuel_amount)
            self._store_recovered_resource('salvage', salvage_amount)
            self.set_notification(f'EMERGENCY CACHE SECURED — {fuel_amount} FUEL CELLS + {salvage_amount} SALVAGE IN FIELD PACK', 3.4)
        elif role == 'fuel':
            amount = 3
            self._store_recovered_resource('fuel_cells', amount)
            self.set_notification(f'Fuel cache secured — {amount} cells transferred to ship cargo', 3.0)
        else:
            amount = 6
            self._store_recovered_resource('salvage', amount)
            self.set_notification(f'Salvage cache secured — {amount} salvage transferred to ship cargo', 3.0)
        self.resource_cache_claimed = True
        self.resource_cache_pos = None
        try:
            self.ship.save_state()
        except Exception:
            pass
        self._sync_mission_distance()
        return True

    def target_awaits_fragment(self, structure) -> bool:
        """True while this marked archive still holds the system's fragment."""
        mission = self.mission_state
        return bool(
            structure is not None
            and getattr(structure, 'is_mission_target', False)
            and mission is not None
            and not bool(getattr(mission, 'fragment_deposited', False))
            and not bool(getattr(mission, 'carrying_fragment', False))
        )

    def try_collect_relic_core(self, structure=None) -> bool:
        if self.mode != 'surface' or self.mission_state is None or self.ship is None:
            return False
        structure = structure or self.mission_target_structure
        if structure is None or not bool(getattr(structure, 'is_mission_target', False)):
            return False
        if bool(getattr(self.mission_state, 'fragment_deposited', False)):
            self.set_notification('Data archive already stripped — fragment is secured', 2.2)
            return True
        distance = math.hypot(self.cam_x - structure.x, self.cam_y - structure.y)
        if distance > structure.radius:
            return False
        if not self.mission_state.recover_surface_relic(structure.seed):
            return False
        self.set_notification(
            f'DATA FRAGMENT RECOVERED — {str(getattr(self.mission_state, "current_archive_record", "DATA RECORD"))} — ARCHIVE {int(getattr(self.mission_state, "fragments_secured_total", 0))}/{int(getattr(self.mission_state, "data_fragments_required", 6))}',
            3.4,
        )
        try:
            self.ship.save_state()
        except Exception:
            pass
        self._sync_mission_distance()
        return True

    def _target_structure_is_active(self) -> bool:
        return bool(
            self.mission_state is not None
            and self.active_structure is not None
            and self.mission_state.target_structure_seed is not None
            and int(self.active_structure.seed) == int(self.mission_state.target_structure_seed)
        )

    def build_planet_name(self, seed: int) -> str:
        rng = random.Random(seed ^ 0x51A7)
        prefixes = ['Astra', 'Nemer', 'Thal', 'Ossi', 'Cel', 'Khep', 'Vatra', 'Lyss', 'Orun', 'Saqq']
        suffixes = ['-Ruune', '-Khepra', ' Meridian', ' Veil', ' Expanse', ' Depths', ' Prime', ' Reach', ' Axiom', ' Cinder']
        return rng.choice(prefixes) + rng.choice(suffixes)

    def make_sky_bodies(self, seed: int) -> list[dict]:
        rng = random.Random(seed ^ 0xA11CE)
        bodies = []
        for i in range(rng.randint(2, 4)):
            hue = (self.biome['accent_hue'] + rng.uniform(-0.12, 0.12) + i * 0.09) % 1.0
            bodies.append({
                'x': rng.randint(120, 1800),
                'y': rng.randint(70, 250),
                'r': rng.randint(28, 76),
                'color': hsv_to_rgb255(hue, 0.42 + rng.random() * 0.22, 0.95),
                'ring': rng.random() < 0.45,
                'ring_tilt': rng.uniform(-0.55, 0.55),
            })
        return bodies

    def build_structures(self) -> None:
        rng = random.Random(self.seed ^ 0xDEADBEEF)
        tint = hsv_to_rgb255((self.biome['accent_hue'] + 0.07) % 1.0, 0.25, 0.62)

        def carve_disk(cx: int, cy: int, radius: int, target_h: int):
            for oy in range(-radius, radius + 1):
                yy = cy + oy
                if yy < 1 or yy >= WORLD_SIZE - 1:
                    continue
                for ox in range(-radius, radius + 1):
                    xx = cx + ox
                    if xx < 1 or xx >= WORLD_SIZE - 1:
                        continue
                    d = math.hypot(ox, oy)
                    if d > radius:
                        continue
                    blend = max(0.0, 1.0 - d / max(1.0, radius))
                    self.height[yy][xx] = int(self.height[yy][xx] * (1.0 - 0.78 * blend) + target_h * (0.78 * blend))
                    cr, cg, cb = self.color[yy][xx]
                    self.color[yy][xx] = (
                        int(clamp(cr * (1.0 - 0.18 * blend) + tint[0] * (0.18 * blend), 0, 255)),
                        int(clamp(cg * (1.0 - 0.18 * blend) + tint[1] * (0.18 * blend), 0, 255)),
                        int(clamp(cb * (1.0 - 0.18 * blend) + tint[2] * (0.18 * blend), 0, 255)),
                    )

        def carve_path(ax: float, ay: float, bx: float, by: float):
            steps = int(max(10, math.hypot(bx - ax, by - ay) * 1.5))
            for i in range(steps + 1):
                t = i / max(1, steps)
                x = int(round(ax * (1.0 - t) + bx * t + math.sin(t * math.pi * 2.0 + self.seed * 0.0001) * 1.6))
                y = int(round(ay * (1.0 - t) + by * t + math.cos(t * math.pi * 2.0 + self.seed * 0.0002) * 1.6))
                carve_disk(x, y, 5, min(190, max(96, self.height[y][x])))

        attempts = 0
        while len(self.structures) < 9 and attempts < 1000:
            attempts += 1
            x = rng.randint(self.spawn_x - 112, self.spawn_x + 112)
            y = rng.randint(self.spawn_y - 112, self.spawn_y + 112)
            x = max(24, min(WORLD_SIZE - 24, x))
            y = max(24, min(WORLD_SIZE - 24, y))
            if math.hypot(x - self.spawn_x, y - self.spawn_y) < 26:
                continue
            hh = self.height[y][x]
            if not 64 < hh < 228:
                continue
            if any(math.hypot(x - s.x, y - s.y) < 34 for s in self.structures):
                continue
            kind, title, interior_type = rng.choice(STRUCTURE_LIBRARY)
            art_ids = self.biome.get('relic_art', ())
            if art_ids and rng.random() < 0.78:
                art_id = art_ids[len(self.structures) % len(art_ids)]
                spr = self.make_relic_structure_sprite(self.seed + 4400 + len(self.structures) * 17, art_id, kind)
            else:
                spr = self.make_structure_sprite(self.seed + 4400 + len(self.structures) * 17, kind)
            radius = 20.0 if interior_type == 'castle' else 18.0
            st = OverworldStructure(float(x), float(y), self.seed + len(self.structures) * 97, kind, title, interior_type, radius, spr)
            self.structures.append(st)
            self.structures_by_seed[st.seed] = st
        for st in self.structures:
            carve_disk(int(st.x), int(st.y), 7 if st.interior_type == 'castle' else 6, min(188, max(104, self.height[int(st.y)][int(st.x)])))
            carve_path(self.spawn_x, self.spawn_y, st.x, st.y)
        carve_disk(int(self.ship_pos[0]), int(self.ship_pos[1]), 7, 148)
        carve_path(self.ship_pos[0], self.ship_pos[1], self.spawn_x, self.spawn_y)

    def build_foliage(self) -> None:
        rng = random.Random(self.seed ^ 0x1234ABCD)
        terrain = self.biome['terrain']
        tree_mult = {
            'desert': 0.0, 'volcanic': 0.0, 'jungle': 1.0, 'ice': 0.55, 'crystal': 0.45, 'oceanic': 0.55,
            'fungal': 0.72, 'rust': 0.12, 'salt': 0.02, 'abyss': 0.10, 'storm': 0.20, 'roseglass': 0.08,
        }.get(terrain, 0.45)
        plant_mult = {
            'volcanic': 0.25, 'jungle': 0.85, 'desert': 0.60, 'ice': 0.55, 'crystal': 0.72, 'oceanic': 0.72,
            'fungal': 1.15, 'rust': 0.32, 'salt': 0.18, 'abyss': 0.82, 'storm': 0.35, 'roseglass': 0.58,
        }.get(terrain, 0.60)
        tree_hue = (self.biome['base_hue'] + rng.uniform(-0.18, 0.18)) % 1.0
        plant_hue = (self.biome['accent_hue'] + rng.uniform(-0.18, 0.18)) % 1.0
        self.tree_sprite = self.make_tree_sprite(self.seed + 900, tree_hue, terrain)
        self.plant_sprite = self.make_plant_sprite(self.seed + 1200, plant_hue, terrain)
        for _ in range(int(300 * tree_mult)):
            x = rng.randint(0, WORLD_SIZE - 1)
            y = rng.randint(0, WORLD_SIZE - 1)
            if any(math.hypot(x - s.x, y - s.y) < 12 for s in self.structures):
                continue
            if any(math.hypot(x - lm.x, y - lm.y) < (11 if lm.primary else 8) for lm in self.landmarks):
                continue
            if 68 < self.height[y][x] < 220 and rng.random() < 0.42:
                self.trees.append({'x': x, 'y': y, 'seed': self.seed + 700000 + len(self.trees) * 17})
        for _ in range(int(700 * plant_mult)):
            x = rng.randint(0, WORLD_SIZE - 1)
            y = rng.randint(0, WORLD_SIZE - 1)
            if any(math.hypot(x - lm.x, y - lm.y) < (8 if lm.primary else 5) for lm in self.landmarks):
                continue
            if self.height[y][x] < 220 and rng.random() < 0.62:
                self.plants.append({'x': x, 'y': y, 'seed': self.seed + 900000 + len(self.plants) * 19})
        self.ship_sprite = self.make_ship_beacon(self.seed ^ 0x5150)

    def _load_world_sprite(self, relative_path: str) -> Optional[pygame.Surface]:
        path = ROOT / 'assets' / 'world_objects' / relative_path
        try:
            if not path.is_file():
                return None
            src = pygame.image.load(str(path)).convert_alpha()
            bounds = src.get_bounding_rect(min_alpha=2)
            if bounds.width > 0 and bounds.height > 0:
                src = src.subsurface(bounds).copy()
            max_dim = 220
            scale = min(1.0, max_dim / max(1, src.get_width(), src.get_height()))
            if scale < 0.999:
                src = pygame.transform.smoothscale(src, (max(2, int(src.get_width() * scale)), max(2, int(src.get_height() * scale))))
            return src
        except Exception:
            _log(f'WARN: world prop failed to load: {path}\n{traceback.format_exc()}')
            return None

    def build_world_props(self) -> None:
        rng = random.Random(self.seed ^ 0xC011EC7)
        self.world_props.clear()
        self.world_prop_sprites = [s for s in (self._load_world_sprite(p) for p in self.biome.get('prop_files', ())) if s is not None]
        if not self.world_prop_sprites:
            return
        target = int(self.biome.get('prop_density', 48))
        attempts = 0
        while len(self.world_props) < target and attempts < target * 20:
            attempts += 1
            x = rng.randint(8, WORLD_SIZE - 9)
            y = rng.randint(8, WORLD_SIZE - 9)
            if math.hypot(x - self.spawn_x, y - self.spawn_y) < 20:
                continue
            if math.hypot(x - self.ship_pos[0], y - self.ship_pos[1]) < 16:
                continue
            if any(math.hypot(x - s.x, y - s.y) < 10 for s in self.structures):
                continue
            if any(math.hypot(x - lm.x, y - lm.y) < (13 if lm.primary else 9) for lm in self.landmarks):
                continue
            hh = self.height[y][x]
            if not 38 < hh < 238:
                continue
            self.world_props.append({
                'x': float(x), 'y': float(y),
                'seed': self.seed + 500000 + len(self.world_props) * 23,
                'kind': 'surface object',
                'sprite': rng.choice(self.world_prop_sprites),
                'scale': rng.uniform(0.72, 1.65),
            })

    def build_motes(self) -> None:
        rng = random.Random(self.seed ^ 0xBB11)
        self.motes.clear()
        for _ in range(rng.randint(24, 56)):
            x = rng.uniform(0, WORLD_SIZE - 1)
            y = rng.uniform(0, WORLD_SIZE - 1)
            hh = self.height[int(y)][int(x)]
            hue = (self.biome['accent_hue'] + rng.uniform(-0.15, 0.15)) % 1.0
            self.motes.append({'x': x, 'y': y, 'base_h': hh + rng.randint(84, 160), 'amp': rng.uniform(8.0, 24.0), 'phase': rng.uniform(0.0, math.tau), 'hue': hue})

    def update(self, dt: float, events) -> None:
        self.frame_counter += 1
        # The top-down surface renderer never uses the half-resolution
        # raycaster or its grain buffers. Allocate them only after entering a
        # ruin/castle/catacomb instead of consuming memory at planetfall.
        if self.mode != 'surface':
            self._ensure_lowres()
        self.enter_interior_requested = False
        mx = 0
        my = 0
        for e in events:
            if e.type == pygame.MOUSEMOTION:
                mx += e.rel[0]
                my += e.rel[1]
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_e:
                    if self.mode == 'surface':
                        if self.try_collect_resource():
                            continue
                        if self.try_harvest_nearby():
                            continue
                    # Legacy dungeon handling remains load-safe for old saves,
                    # but new gameplay never enters this mode.
                    else:
                        if e.key == pygame.K_e:
                            c, _, _, dist = self.trace_center_hit()
                            if c == '2' and dist <= 2.4:
                                self.leave_dungeon()
                elif e.key == pygame.K_x and self.mode == 'dungeon':
                    self.leave_dungeon()

        if self.mode == 'surface':
            self.update_surface(dt, mx, my)
            self._px = self.cam_x
            self._py = self.cam_y
        else:
            self.update_dungeon(dt, mx, my)
            self._px = -1e9
            self._py = -1e9

    def _surface_hazard_family(self) -> str:
        mission = self.mission_state
        if mission is not None and self.mission_planet_index is not None:
            signal = mission.signal_for_planet(self.mission_planet_index)
            if signal is not None:
                return str(getattr(signal, "hazard_family", "UNKNOWN") or "UNKNOWN").upper()
        # HOME and verification surfaces still derive from the same terrain rules.
        terrain = str(self.biome.get("terrain", "unknown"))
        family_by_terrain = {
            "desert": "HEAT", "volcanic": "HEAT", "rust": "HEAT",
            "ice": "COLD", "salt": "COLD", "storm": "COLD",
            "jungle": "BIOLOGICAL", "fungal": "BIOLOGICAL", "oceanic": "BIOLOGICAL",
            "crystal": "ANOMALOUS", "abyss": "ANOMALOUS", "roseglass": "ANOMALOUS",
        }
        return family_by_terrain.get(terrain, "UNKNOWN")

    def _evaluate_surface_hazard(self) -> None:
        family = self._surface_hazard_family()
        distance_from_ship = math.hypot(self.cam_x - self.ship_pos[0], self.cam_y - self.ship_pos[1])
        target_distance = None
        if self.mission_target_structure is not None and not bool(getattr(self.mission_state, "fragment_deposited", False)):
            target_distance = math.hypot(self.cam_x - self.mission_target_structure.x, self.cam_y - self.mission_target_structure.y)
        rig_level = level(self.ship, "surface") if self.ship is not None else 0
        self.hazard_frame = evaluate_hazard(
            family,
            distance_from_ship=distance_from_ship,
            elapsed_seconds=self.surface_elapsed,
            seed=self.seed,
            surface_rig_level=rig_level,
            storm_intensity=self.storm_intensity,
            target_distance=target_distance,
        )

    def update_surface(self, dt: float, mx: int, my: int) -> None:
        """Update polished top-down traversal using acceleration and camera easing."""
        safe_dt = max(0.0, min(float(dt), 0.10))
        self.surface_elapsed += safe_dt
        self._evaluate_surface_hazard()
        keys = pygame.key.get_pressed()
        move_x = (1.0 if keys[pygame.K_d] else 0.0) - (1.0 if keys[pygame.K_a] else 0.0)
        move_y = (1.0 if keys[pygame.K_s] else 0.0) - (1.0 if keys[pygame.K_w] else 0.0)
        gamepad = get_active_gamepad()
        if gamepad is not None and bool(getattr(gamepad, "connected", False)):
            gx, gy = gamepad.move_vector()
            move_x += float(gx)
            move_y += float(gy)
        length = math.hypot(move_x, move_y)
        if length > 1.0:
            move_x /= length
            move_y /= length

        walk_speed = SURFACE_WALK_SPEED * surface_speed_multiplier(self.ship) * float(getattr(self.hazard_frame, "move_multiplier", 1.0))
        target_vx = move_x * walk_speed
        target_vy = move_y * walk_speed
        response = SURFACE_ACCEL_RESPONSE if length > 1e-6 else SURFACE_BRAKE_RESPONSE
        blend = 1.0 - math.exp(-response * safe_dt) if safe_dt > 0.0 else 0.0
        self.surface_vel_x = lerp(self.surface_vel_x, target_vx, blend)
        self.surface_vel_y = lerp(self.surface_vel_y, target_vy, blend)
        velocity = math.hypot(self.surface_vel_x, self.surface_vel_y)
        if velocity < 0.025 and length <= 1e-6:
            self.surface_vel_x = 0.0
            self.surface_vel_y = 0.0
            velocity = 0.0

        self.surface_is_moving = velocity > 0.18
        self.cam_x += self.surface_vel_x * safe_dt
        self.cam_y += self.surface_vel_y * safe_dt
        if self.surface_is_moving:
            self.surface_anim_time += safe_dt * clamp(velocity / max(0.001, walk_speed), 0.45, 1.0)
            # Facing follows actual motion, so diagonal releases do not snap the
            # actor back to the last raw keyboard axis.
            if abs(self.surface_vel_x) > abs(self.surface_vel_y):
                self.surface_facing = 'right' if self.surface_vel_x > 0.0 else 'left'
            else:
                self.surface_facing = 'down' if self.surface_vel_y > 0.0 else 'up'
            facing_angles = {
                'right': 0.0, 'down': math.pi * 0.5,
                'left': math.pi, 'up': math.pi * 1.5,
            }
            self.cam_ang = facing_angles[self.surface_facing]
        elif length <= 1e-6:
            self.surface_anim_time = 0.0

        # Camera look-ahead is measured in world units and eases back to the
        # actor at rest. It never changes simulation coordinates or harvesting.
        if velocity > 0.001:
            ahead_x = self.surface_vel_x / velocity * SURFACE_CAMERA_LOOKAHEAD
            ahead_y = self.surface_vel_y / velocity * SURFACE_CAMERA_LOOKAHEAD
        else:
            ahead_x = ahead_y = 0.0
        target_view_x = self.cam_x + ahead_x
        target_view_y = self.cam_y + ahead_y
        camera_blend = 1.0 - math.exp(-SURFACE_CAMERA_RESPONSE * safe_dt) if safe_dt > 0.0 else 0.0
        self.surface_view_x = lerp(self.surface_view_x, target_view_x, camera_blend)
        self.surface_view_y = lerp(self.surface_view_y, target_view_y, camera_blend)
        self.surface_entry_fade = max(0.0, self.surface_entry_fade - safe_dt / 0.65)

        now = time.time()
        self.surface_recovery_fx = [fx for fx in self.surface_recovery_fx if now - float(fx.get('started', now)) < float(fx.get('duration', 0.9))]
        if not self.storm_active:
            storm_rate = 0.060 if self.biome.get('weather') == 'tempest' else 0.025
            chance = 1.0 - (1.0 - storm_rate) ** safe_dt
            if random.random() < chance:
                self.storm_active = True
                self.storm_t = now
                duration = (7.0, 13.0) if self.biome.get('weather') == 'tempest' else (4.0, 9.0)
                self.storm_end = now + random.uniform(*duration)
                self.storm_intensity = 0.0
        else:
            dur = max(0.1, self.storm_end - self.storm_t)
            t = (now - self.storm_t) / dur
            self.storm_intensity = max(0.0, min(1.0, math.sin(min(1.0, t) * math.pi)))
            if now >= self.storm_end:
                self.storm_active = False
                self.storm_intensity = 0.0
        self.update_particles(safe_dt)
        if now >= self.harvest_scan_at or math.hypot(self.cam_x - self.harvest_scan_pos[0], self.cam_y - self.harvest_scan_pos[1]) >= 1.5:
            self.harvest_candidate = self.nearest_harvestable(10.0)
            self.harvest_scan_at = now + 0.15
            self.harvest_scan_pos = (self.cam_x, self.cam_y)
        self._sync_mission_distance()

    def _is_harvested(self, category: str, item_seed: int) -> bool:
        return harvest_id(category, item_seed) in self.harvested_ids

    def _mark_harvested(self, category: str, item_seed: int) -> None:
        hid = harvest_id(category, item_seed)
        self.harvested_ids.add(hid)
        if self.ship is not None:
            self.ship.surface_harvests = normalize_harvest_map(getattr(self.ship, 'surface_harvests', {}))
            self.ship.surface_harvests[str(self.seed)] = sorted(self.harvested_ids)
            self.ship.state_dirty = True

    def nearest_harvestable(self, max_distance: float = 10.0):
        """Return the closest recoverable object using local spatial buckets.

        Structures are a tiny fixed list, while foliage and props may number
        in the hundreds.  Only the 3x3 bucket neighborhood around the player
        is examined, keeping interaction cost bounded as planets grow denser.
        """
        best = None
        best_d = float(max_distance)
        for st in self.structures:
            if self._is_harvested('structure', st.seed):
                continue
            d = max(0.0, math.hypot(self.cam_x - st.x, self.cam_y - st.y) - st.radius * 0.72)
            if d <= best_d:
                best = ('structure', st, d)
                best_d = d

        cell_size = 32
        base_cx = math.floor(self.cam_x / cell_size)
        base_cy = math.floor(self.cam_y / cell_size)
        harvest_index = self._topdown_spatial_index.get('harvest', {})
        for cy in range(base_cy - 1, base_cy + 2):
            for cx in range(base_cx - 1, base_cx + 2):
                for category, item in harvest_index.get((cx, cy), ()):
                    item_seed = int(item.get('seed', 0))
                    if self._is_harvested(category, item_seed):
                        continue
                    limit = {'prop': 7.5, 'tree': 7.0, 'plant': 5.5}[category]
                    d = math.hypot(self.cam_x - float(item['x']), self.cam_y - float(item['y']))
                    if d <= min(best_d, limit):
                        best = (category, item, d)
                        best_d = d

        chunk_x = math.floor(self.cam_x / CHUNK_WORLD_SIZE)
        chunk_y = math.floor(self.cam_y / CHUNK_WORLD_SIZE)
        category_key = (('tree', 'trees'), ('plant', 'plants'), ('prop', 'props'))
        for cy in range(chunk_y - 1, chunk_y + 2):
            for cx in range(chunk_x - 1, chunk_x + 2):
                objects = self._procedural_objects_for_chunk(cx, cy)
                for category, key in category_key:
                    for item in objects.get(key, ()):
                        item_seed = int(item.get('seed', 0))
                        if self._is_harvested(category, item_seed):
                            continue
                        limit = {'prop': 7.5, 'tree': 7.0, 'plant': 5.5}[category]
                        d = math.hypot(self.cam_x - float(item['x']), self.cam_y - float(item['y']))
                        if d <= min(best_d, limit):
                            best = (category, item, d)
                            best_d = d
        return best

    def try_harvest_nearby(self) -> bool:
        candidate = self.nearest_harvestable(10.0)
        if candidate is None or self.ship is None:
            return False
        category, item, _distance = candidate
        item_seed = int(item.seed if category == 'structure' else item.get('seed', 0))
        title = item.title if category == 'structure' else {
            'prop': 'surface object', 'tree': 'organic growth', 'plant': 'field sample',
        }.get(category, 'surface material')
        core_added = False
        if category == 'structure' and self.target_awaits_fragment(item):
            if ruin_dive.dive_available():
                # The fragment is below: hand the ruin to the DreamCrawler team.
                self.ruin_dive_request = item
                return True
            core_added = self.try_collect_relic_core(item)
            if not core_added:
                return False
        result = harvest_yield(self.seed, item_seed, category, level(self.ship, 'surface'))
        for resource, amount in result.items():
            if amount > 0:
                self._store_recovered_resource(resource, amount)
        self._mark_harvested(category, item_seed)
        fx_x = float(item.x if category == 'structure' else item.get('x', self.cam_x))
        fx_y = float(item.y if category == 'structure' else item.get('y', self.cam_y))
        self.surface_harvest_count += 1
        parts = []
        if core_added:
            parts.append('1 DATA FRAGMENT')
        if result.get('salvage', 0):
            parts.append(f"{result['salvage']} SALVAGE")
        if result.get('fuel_cells', 0):
            parts.append(f"{result['fuel_cells']} FUEL CELL")
        reward = ' + '.join(parts) or 'MATERIAL RECOVERED'
        self._start_surface_recovery_fx(fx_x, fx_y, reward)
        self.set_notification(f'SURFACE RIG PROCESSED {str(title).upper()} — {reward}', 3.0)
        self.harvest_candidate = self.nearest_harvestable(10.0)
        try:
            self.ship.save_state()
        except Exception:
            pass
        return True

    def _start_surface_recovery_fx(self, x: float, y: float, reward: str) -> None:
        """Start one bounded world-space recovery burst and reward label."""
        self.surface_recovery_fx.append({
            'x': float(x), 'y': float(y), 'reward': str(reward),
            'started': time.time(), 'duration': 1.05,
            'seed': int(self.seed ^ self.surface_harvest_count * 0x45D9F3B),
        })
        if len(self.surface_recovery_fx) > SURFACE_RECOVERY_FX_LIMIT:
            self.surface_recovery_fx = self.surface_recovery_fx[-SURFACE_RECOVERY_FX_LIMIT:]

    def _surface_action_prompt(self):
        """Return one standardized bottom action prompt without duplicating HUD text."""
        if self.resource_cache_pos is not None and not self.resource_cache_claimed and self.resource_cache_distance() <= 12.0:
            return 'E', f'RECOVER {str(self.resource_cache_role or "RESOURCE").upper()} CACHE', (112, 224, 255)
        candidate = self.harvest_candidate
        if candidate is None:
            return None
        category, item, _distance = candidate
        title = item.title if category == 'structure' else {
            'prop': 'SURFACE OBJECT', 'tree': 'ORGANIC GROWTH', 'plant': 'FIELD SAMPLE',
        }.get(category, 'SURFACE MATERIAL')
        if category == 'structure' and self.target_awaits_fragment(item):
            if ruin_dive.dive_available():
                return 'E', f'DIVE INTO {str(title).upper()}  /  DREAMCRAWLER TEAM', (255, 214, 112)
            return 'E', f'RECOVER DATA FRAGMENT  /  {str(title).upper()}', (255, 214, 112)
        return 'E', f'PROCESS {str(title).upper()}', (124, 244, 176)

    def _draw_surface_action_prompt(self) -> bool:
        prompt = self._surface_action_prompt()
        if prompt is None:
            return False
        key, text, color = prompt
        w, h = self.screen.get_size()
        key_surface = self.title_font.render(key, True, (4, 8, 12))
        max_text_w = max(180, w - 200)
        shown_text = str(text)
        text_surface = self.fps_font.render(shown_text, True, (236, 244, 248))
        while text_surface.get_width() > max_text_w and len(shown_text) > 20:
            shown_text = shown_text[:-4].rstrip() + '...'
            text_surface = self.fps_font.render(shown_text, True, (236, 244, 248))
        total_w = min(w - 96, 76 + text_surface.get_width() + 34)
        x = w // 2 - total_w // 2
        y = h - 78
        panel = pygame.Surface((total_w, 50), pygame.SRCALPHA)
        panel.fill((4, 8, 13, 220))
        self.screen.blit(panel, (x, y))
        pygame.draw.rect(self.screen, color, pygame.Rect(x, y, total_w, 50), 1, border_radius=12)
        pygame.draw.rect(self.screen, color, pygame.Rect(x + 8, y + 8, 48, 34), border_radius=9)
        self.screen.blit(key_surface, (x + 32 - key_surface.get_width() // 2, y + 25 - key_surface.get_height() // 2))
        self.screen.blit(text_surface, (x + 70, y + 25 - text_surface.get_height() // 2))
        return True

    def _draw_surface_recovery_fx(self, view) -> None:
        now = time.time()
        layer = self._topdown_layer('recovery_fx', *self.screen.get_size())
        for fx in self.surface_recovery_fx:
            duration = max(0.01, float(fx.get('duration', 1.05)))
            t = clamp((now - float(fx.get('started', now))) / duration, 0.0, 1.0)
            if t >= 1.0 or not self._topdown_visible(float(fx['x']), float(fx['y']), view, margin=10.0):
                continue
            sx, sy = self._topdown_world_to_screen(float(fx['x']), float(fx['y']), view)
            alpha = int(220 * (1.0 - t))
            radius = int(18 + 46 * t)
            pygame.draw.circle(layer, (124, 244, 176, alpha), (sx, sy), radius, 2)
            rng = random.Random(int(fx.get('seed', 0)))
            for index in range(12):
                angle = rng.random() * math.tau
                reach = 14 + (42 + rng.random() * 24) * t
                px = int(sx + math.cos(angle) * reach)
                py = int(sy + math.sin(angle) * reach - 18 * t)
                pygame.draw.circle(layer, (160, 255, 204, max(0, alpha - index * 4)), (px, py), 2)
            reward = self.fps_font.render(str(fx.get('reward', 'MATERIAL RECOVERED')), True, (230, 250, 238))
            layer.blit(reward, (sx - reward.get_width() // 2, sy - 48 - int(28 * t)))
        self.screen.blit(layer, (0, 0))

    def _draw_surface_finish(self) -> None:
        """Apply inexpensive edge focus and a short entry fade."""
        w, h = self.screen.get_size()
        vignette = self._topdown_layer('vignette', w, h)
        for i in range(7):
            alpha = 9 + i * 4
            inset_x = i * 12
            inset_y = i * 8
            pygame.draw.rect(vignette, (0, 0, 0, alpha), pygame.Rect(inset_x, inset_y, w - inset_x * 2, h - inset_y * 2), max(8, 18 - i * 2))
        self.screen.blit(vignette, (0, 0))
        if self.surface_entry_fade > 0.001:
            fade = self._topdown_layer('entry_fade', w, h)
            fade.fill((2, 5, 10, int(210 * self.surface_entry_fade * self.surface_entry_fade)))
            self.screen.blit(fade, (0, 0))

    def enter_dungeon(self, structure: OverworldStructure) -> None:
        """Retired Pass 18 ruin transition.

        Ruins are surface landmarks only. This guard prevents old callers or
        stale test hooks from reactivating the first-person raycaster.
        """
        self.mode = 'surface'
        self.active_structure = None
        self.fragment_pos = None
        self.interior_creatures = []
        self.set_notification('RUIN INTERIORS RETIRED — RECOVER THE CORE FROM THE SURFACE', 2.8)

    def leave_dungeon(self) -> None:
        self.mode = 'surface'
        if self.mission_state is not None:
            self.mission_state.leave_structure()
        self.fragment_pos = None
        if self.active_structure is not None:
            self.cam_x = self.active_structure.x - 14.0
            self.cam_y = self.active_structure.y - 14.0
            self.cam_ang = math.atan2(self.active_structure.y - self.cam_y, self.active_structure.x - self.cam_x)
            angle = self.cam_ang % math.tau
            if math.pi * 0.25 <= angle < math.pi * 0.75:
                self.surface_facing = 'down'
            elif math.pi * 0.75 <= angle < math.pi * 1.25:
                self.surface_facing = 'left'
            elif math.pi * 1.25 <= angle < math.pi * 1.75:
                self.surface_facing = 'up'
            else:
                self.surface_facing = 'right'
        self.surface_is_moving = False
        self.surface_anim_time = 0.0
        self._sync_mission_distance()
        self.set_notification('Returned to the planetary surface', 2.0)

    def set_theme(self, theme: str) -> None:
        if theme == 'castle':
            self.active_wall_tex = self.tint_texture(self.stone_tex, (110, 150, 176), 8)
            self.active_panel_tex = self.tint_texture(self.stone_tex, (146, 208, 226), 18)
            self.active_floor_tex = self.make_pattern_texture(self.seed ^ 71, (72, 96, 118), (48, 62, 78))
            self.active_ceil_tex = self.make_pattern_texture(self.seed ^ 73, (56, 78, 94), (34, 46, 58))
            self.active_door_tex = self.tint_texture(self.door_tex, (138, 188, 214), 12)
            self.interior_theme = 'Sky Keep'
        elif theme == 'catacomb':
            self.active_wall_tex = self.tint_texture(self.stone_tex, (138, 150, 112), 0)
            self.active_panel_tex = self.tint_texture(self.stone_tex, (164, 178, 126), 0)
            self.active_floor_tex = self.make_pattern_texture(self.seed ^ 81, (92, 102, 74), (62, 70, 52))
            self.active_ceil_tex = self.make_pattern_texture(self.seed ^ 83, (70, 76, 60), (44, 48, 36))
            self.active_door_tex = self.tint_texture(self.door_tex, (176, 182, 132), 0)
            self.interior_theme = 'Buried Catacomb'
        else:
            self.active_wall_tex = self.tint_texture(self.stone_tex, (178, 132, 92), 6)
            self.active_panel_tex = self.tint_texture(self.stone_tex, (212, 164, 112), 14)
            self.active_floor_tex = self.make_pattern_texture(self.seed ^ 91, (132, 96, 66), (86, 62, 44))
            self.active_ceil_tex = self.make_pattern_texture(self.seed ^ 93, (92, 68, 48), (58, 42, 28))
            self.active_door_tex = self.tint_texture(self.door_tex, (214, 176, 96), 12)
            self.interior_theme = 'Star Tomb'

    def update_dungeon(self, dt: float, mx: int, my: int) -> None:
        self.interior_angle += mx * MOUSE_SENS
        self.interior_pitch = clamp(self.interior_pitch - my * 0.42, -PITCH_LIMIT, PITCH_LIMIT)
        keys = pygame.key.get_pressed()
        sin_a = math.sin(self.interior_angle)
        cos_a = math.cos(self.interior_angle)
        move_dx = 0.0
        move_dy = 0.0
        if keys[pygame.K_w]:
            move_dx += cos_a * INDOOR_MOVE_SPEED
            move_dy += sin_a * INDOOR_MOVE_SPEED
        if keys[pygame.K_s]:
            move_dx -= cos_a * INDOOR_MOVE_SPEED
            move_dy -= sin_a * INDOOR_MOVE_SPEED
        if keys[pygame.K_a]:
            move_dx += sin_a * INDOOR_MOVE_SPEED
            move_dy -= cos_a * INDOOR_MOVE_SPEED
        if keys[pygame.K_d]:
            move_dx -= sin_a * INDOOR_MOVE_SPEED
            move_dy += cos_a * INDOOR_MOVE_SPEED
        if move_dx or move_dy:
            # Preserve the existing interior feel while making it frame-rate independent.
            frame_scale = max(0.0, min(float(dt), 0.05)) * 60.0
            self.move_with_barrier(move_dx * frame_scale, move_dy * frame_scale)
        self.try_spawn_monsters()
        self.update_dungeon_creatures()
        self.fragment_recovery_flash = max(0.0, self.fragment_recovery_flash - max(0.0, float(dt)))
        self._sync_mission_distance()

    def draw(self) -> None:
        if self.mode == 'surface':
            self.draw_surface()
        else:
            self.draw_dungeon()
        self.draw_notification()

    def draw_notification(self) -> None:
        if not self.notification or time.time() > self.notification_until:
            return
        w, h = self.screen.get_size()
        text = str(self.notification)
        txt = self.fps_font.render(text, True, (236, 238, 244))
        max_text_w = max(240, w - 180)
        while txt.get_width() > max_text_w and len(text) > 24:
            text = text[:-4].rstrip() + '...'
            txt = self.fps_font.render(text, True, (236, 238, 244))
        panel_w = min(w - 96, max(360, txt.get_width() + 48))
        surf = pygame.Surface((panel_w, 44), pygame.SRCALPHA)
        surf.fill((6, 10, 16, 218))
        x = w // 2 - panel_w // 2
        # Surface actions own the lowest safe strip; notifications rise above it.
        has_action = self.mode == 'surface' and self._surface_action_prompt() is not None
        y = h - (140 if has_action else 82)
        self.screen.blit(surf, (x, y))
        pygame.draw.rect(self.screen, (68, 116, 132), pygame.Rect(x, y, panel_w, 44), 1, border_radius=10)
        self.screen.blit(txt, (w // 2 - txt.get_width() // 2, y + 11))

    def draw_surface(self) -> None:
        self.draw_surface_topdown()

    def _topdown_layer(self, name: str, w: int, h: int) -> pygame.Surface:
        key = (name, int(w), int(h))
        layer = self._topdown_layers.get(key)
        if layer is None:
            layer = pygame.Surface((w, h), pygame.SRCALPHA)
            self._topdown_layers[key] = layer
            for old_key in list(self._topdown_layers):
                if old_key != key and old_key[0] == name:
                    self._topdown_layers.pop(old_key, None)
        else:
            layer.fill((0, 0, 0, 0))
        return layer

    def _build_topdown_spatial_index(self) -> None:
        """Bucket static props so each frame visits only visible world cells."""
        cell_size = 32
        index = {'trees': {}, 'plants': {}, 'props': {}, 'harvest': {}}

        def add(kind, item):
            key = (int(item['x']) // cell_size, int(item['y']) // cell_size)
            index[kind].setdefault(key, []).append(item)

        def add_harvest(category, item):
            key = (int(item['x']) // cell_size, int(item['y']) // cell_size)
            index['harvest'].setdefault(key, []).append((category, item))

        for item in self.trees:
            add('trees', item)
            add_harvest('tree', item)
        for item in self.plants:
            add_harvest('plant', item)
        for item in self.plants[::2]:
            add('plants', item)
        for item in self.world_props:
            add('props', item)
            add_harvest('prop', item)
        self._topdown_spatial_index = index
        self._topdown_visible_cache_key = None
        self._topdown_visible_cache = ((), (), ())
        self._terrain_chunk_cache = OrderedDict()
        self._procedural_object_cache = OrderedDict()
        self._topdown_scaled_surface = None
        self._topdown_scaled_size = (0, 0)

    def _procedural_objects_for_chunk(self, chunk_x: int, chunk_y: int):
        """Return deterministic exploration objects for one absolute chunk."""
        key = (int(chunk_x), int(chunk_y))
        cached = self._procedural_object_cache.get(key)
        if cached is not None:
            self._procedural_object_cache.move_to_end(key)
            return cached
        generated = generate_chunk_objects(self.seed, self.biome, key[0], key[1])
        filtered = {'trees': [], 'plants': [], 'props': []}
        for kind in filtered:
            for item in generated.get(kind, ()):
                x = float(item['x'])
                y = float(item['y'])
                if math.hypot(x - self.ship_pos[0], y - self.ship_pos[1]) < 18.0:
                    continue
                if any(math.hypot(x - st.x, y - st.y) < 13.0 for st in self.structures):
                    continue
                filtered[kind].append(item)
        cached = {kind: tuple(items) for kind, items in filtered.items()}
        self._procedural_object_cache[key] = cached
        self._procedural_object_cache.move_to_end(key)
        while len(self._procedural_object_cache) > OBJECT_CACHE_LIMIT:
            self._procedural_object_cache.popitem(last=False)
        return cached

    def _visible_topdown_static(self, view_rect):
        """Collect finite mission-zone and streamed exploration objects."""
        left, top, view_w, view_h = view_rect
        cell_size = 32
        min_bx = math.floor((left - 4.0) / cell_size)
        min_by = math.floor((top - 4.0) / cell_size)
        max_bx = math.floor((left + view_w + 4.0) / cell_size)
        max_by = math.floor((top + view_h + 4.0) / cell_size)
        min_cx = math.floor((left - 4.0) / CHUNK_WORLD_SIZE)
        min_cy = math.floor((top - 4.0) / CHUNK_WORLD_SIZE)
        max_cx = math.floor((left + view_w + 4.0) / CHUNK_WORLD_SIZE)
        max_cy = math.floor((top + view_h + 4.0) / CHUNK_WORLD_SIZE)
        cache_key = (min_bx, min_by, max_bx, max_by, min_cx, min_cy, max_cx, max_cy)
        if cache_key == self._topdown_visible_cache_key:
            return self._topdown_visible_cache
        visible = []
        for kind in ('trees', 'plants', 'props'):
            items = []
            buckets = self._topdown_spatial_index.get(kind, {})
            for by in range(min_by, max_by + 1):
                for bx in range(min_bx, max_bx + 1):
                    items.extend(buckets.get((bx, by), ()))
            for cy in range(min_cy, max_cy + 1):
                for cx in range(min_cx, max_cx + 1):
                    items.extend(self._procedural_objects_for_chunk(cx, cy).get(kind, ()))
            visible.append(tuple(items))
        self._topdown_visible_cache_key = cache_key
        self._topdown_visible_cache = tuple(visible)
        return self._topdown_visible_cache

    def _build_topdown_map(self) -> None:
        """Build a deterministic relief map once and reuse it every frame."""
        base = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        light_dir = (-0.72, -0.42)
        for y in range(WORLD_SIZE):
            ym = max(0, y - 1)
            yp = min(WORLD_SIZE - 1, y + 1)
            for x in range(WORLD_SIZE):
                xm = max(0, x - 1)
                xp = min(WORLD_SIZE - 1, x + 1)
                h0 = self.height[y][x]
                dx = self.height[y][xp] - self.height[y][xm]
                dy = self.height[yp][x] - self.height[ym][x]
                relief = clamp(1.02 - (dx * light_dir[0] + dy * light_dir[1]) * 0.010, 0.64, 1.34)
                contour = 0.90 if ((h0 // 18) != (self.height[y][xm] // 18) or (h0 // 18) != (self.height[ym][x] // 18)) else 1.0
                col = self.color[y][x]
                # The surface palette is intentionally luminous. The
                # top-down tactical camera uses a darker filmic map response so
                # landmarks and actors remain readable against the terrain.
                base.set_at((x, y), (
                    int(clamp(max(0, col[0] - 30) * 0.70 * relief * contour + 8, 0, 224)),
                    int(clamp(max(0, col[1] - 30) * 0.70 * relief * contour + 10, 0, 224)),
                    int(clamp(max(0, col[2] - 30) * 0.70 * relief * contour + 14, 0, 224)),
                ))
        # Keep a four-texel-per-world-unit cache. The 160x90 camera window
        # becomes a compact 640x360 source region that scales exactly to
        # 1280x720 or 1920x1080 without retaining a 4608x4608 world texture.
        hd_size = (WORLD_SIZE * TOPDOWN_MAP_SCALE, WORLD_SIZE * TOPDOWN_MAP_SCALE)
        self.topdown_map = pygame.transform.smoothscale(base, hd_size)
        self.topdown_map_size = self.topdown_map.get_size()
        self.topdown_sprite_cache.clear()

    def _terrain_chunk_surface(self, chunk_x: int, chunk_y: int) -> pygame.Surface:
        key = (int(chunk_x), int(chunk_y))
        cached = self._terrain_chunk_cache.get(key)
        if cached is not None:
            self._terrain_chunk_cache.move_to_end(key)
            return cached
        pixels = build_chunk_pixels(self.seed, self.biome, key[0], key[1], CHUNK_WORLD_SIZE)
        sample_h = len(pixels)
        sample_w = len(pixels[0]) if pixels else 1
        base = pygame.Surface((sample_w, sample_h))
        for y, row in enumerate(pixels):
            for x, color in enumerate(row):
                base.set_at((x, y), color)
        try:
            base = base.convert()
        except Exception:
            pass
        target_size = CHUNK_WORLD_SIZE * TERRAIN_TEXELS_PER_UNIT
        cached = pygame.transform.smoothscale(base, (target_size, target_size))
        self._terrain_chunk_cache[key] = cached
        self._terrain_chunk_cache.move_to_end(key)
        while len(self._terrain_chunk_cache) > CHUNK_CACHE_LIMIT:
            self._terrain_chunk_cache.popitem(last=False)
        return cached

    def _draw_chunked_terrain(self, view_rect) -> None:
        """Compose only the chunks crossing the current camera window."""
        left, top, view_w, view_h = view_rect
        source_w = max(1, int(round(view_w * TERRAIN_TEXELS_PER_UNIT)))
        source_h = max(1, int(round(view_h * TERRAIN_TEXELS_PER_UNIT)))
        canvas = self._topdown_layer('terrain_canvas', source_w, source_h)
        canvas.fill((4, 7, 12, 255))
        min_cx = math.floor(left / CHUNK_WORLD_SIZE)
        min_cy = math.floor(top / CHUNK_WORLD_SIZE)
        max_cx = math.floor((left + view_w) / CHUNK_WORLD_SIZE)
        max_cy = math.floor((top + view_h) / CHUNK_WORLD_SIZE)
        scale = TERRAIN_TEXELS_PER_UNIT
        for chunk_y in range(min_cy, max_cy + 1):
            for chunk_x in range(min_cx, max_cx + 1):
                chunk = self._terrain_chunk_surface(chunk_x, chunk_y)
                dx = int(round((chunk_x * CHUNK_WORLD_SIZE - left) * scale))
                dy = int(round((chunk_y * CHUNK_WORLD_SIZE - top) * scale))
                canvas.blit(chunk, (dx, dy))
        w, h = self.screen.get_size()
        if (source_w, source_h) == (w, h):
            self.screen.blit(canvas, (0, 0))
            return
        if self._topdown_scaled_surface is None or self._topdown_scaled_size != (w, h):
            self._topdown_scaled_surface = pygame.Surface((w, h))
            self._topdown_scaled_size = (w, h)
        try:
            pygame.transform.scale(canvas, (w, h), self._topdown_scaled_surface)
            self.screen.blit(self._topdown_scaled_surface, (0, 0))
        except TypeError:
            self.screen.blit(pygame.transform.scale(canvas, (w, h)), (0, 0))

    def _topdown_view_rect(self):
        view_w = TOPDOWN_VIEW_WORLD_W
        view_h = TOPDOWN_VIEW_WORLD_H
        view_x = float(getattr(self, 'surface_view_x', self.cam_x))
        view_y = float(getattr(self, 'surface_view_y', self.cam_y))
        if not math.isfinite(view_x) or not math.isfinite(view_y):
            return self.cam_x - view_w * 0.5, self.cam_y - view_h * 0.5, view_w, view_h
        return view_x - view_w * 0.5, view_y - view_h * 0.5, view_w, view_h

    def _topdown_world_to_screen(self, x, y, view_rect=None):
        if view_rect is None:
            view_rect = self._topdown_view_rect()
        left, top, view_w, view_h = view_rect
        w, h = self.screen.get_size()
        return (
            int((x - left) / max(0.001, view_w) * w),
            int((y - top) / max(0.001, view_h) * h),
        )

    @staticmethod
    def _topdown_visible(x, y, view_rect, margin=4.0):
        left, top, view_w, view_h = view_rect
        return (left - margin) <= x <= (left + view_w + margin) and (top - margin) <= y <= (top + view_h + margin)

    def _scaled_topdown_sprite(self, sprite, target_h, cache_key):
        key = (cache_key, int(target_h))
        cached = self.topdown_sprite_cache.get(key)
        if cached is not None:
            return cached
        sw, sh = sprite.get_size()
        scale = float(target_h) / max(1.0, float(sh))
        target = (max(2, int(sw * scale)), max(2, int(target_h)))
        cached = pygame.transform.smoothscale(sprite, target)
        if len(self.topdown_sprite_cache) >= 96:
            self.topdown_sprite_cache.pop(next(iter(self.topdown_sprite_cache)), None)
        self.topdown_sprite_cache[key] = cached
        return cached

    def _draw_topdown_weather(self) -> None:
        intensity = clamp(self.storm_intensity, 0.0, 1.0)
        weather = self.biome.get('weather', '')
        if intensity <= 0.01 and weather not in ('mist', 'spores', 'embers'):
            return
        w, h = self.screen.get_size()
        layer = self._topdown_layer('weather', w, h)
        rng = random.Random((self.seed ^ 0x10D0) + self.frame_counter // 3)
        count = int(40 + 120 * max(0.18, intensity))
        if weather in ('rain', 'tempest'):
            col = (132, 196, 232, int(35 + 80 * intensity))
            for _ in range(count):
                x = rng.randrange(0, w)
                y = rng.randrange(0, h)
                pygame.draw.line(layer, col, (x, y), (x - 10, y + 24), 2)
        elif weather in ('snow', 'salt', 'shards'):
            col = (226, 242, 255, int(48 + 72 * max(0.25, intensity)))
            for _ in range(count):
                x = rng.randrange(0, w)
                y = rng.randrange(0, h)
                pygame.draw.circle(layer, col, (x, y), rng.randint(1, 3))
        else:
            layer.fill((*self.biome['fog'], int(20 + 48 * max(0.25, intensity))))
        self.screen.blit(layer, (0, 0))

    def _draw_surface_hazard_fx(self) -> None:
        frame = getattr(self, "hazard_frame", None)
        if frame is None or float(getattr(frame, "severity", 0.0)) <= 0.02:
            return
        family = str(getattr(frame, "family", "UNKNOWN"))
        severity = clamp(float(getattr(frame, "severity", 0.0)), 0.0, 1.0)
        w, h = self.screen.get_size()
        layer = self._topdown_layer("hazard_fx", w, h)
        layer.fill((0, 0, 0, 0))
        if family == "HEAT":
            layer.fill((255, 86, 32, int(18 + 30 * severity)))
            # Restrained edge heat shimmer; gameplay remains readable.
            for i in range(4):
                y = int((i + 1) * h / 5 + math.sin(self.surface_elapsed * 2.0 + i) * 8)
                pygame.draw.line(layer, (255, 194, 126, int(18 + 26 * severity)), (0, y), (w, y), 2)
        elif family == "COLD":
            layer.fill((74, 142, 255, int(15 + 34 * severity)))
            inset = int(10 + 28 * severity)
            pygame.draw.rect(layer, (196, 236, 255, int(24 + 56 * severity)), pygame.Rect(inset, inset, max(1, w - inset * 2), max(1, h - inset * 2)), max(2, int(3 + severity * 5)), border_radius=18)
        elif family == "BIOLOGICAL" and bool(getattr(frame, "pulse_active", False)):
            layer.fill((76, 166, 82, int(12 + 32 * severity)))
            rng = random.Random((self.seed ^ 0xB10) + self.frame_counter // 4)
            for _ in range(int(18 + 48 * severity)):
                x = rng.randrange(0, max(1, w))
                y = rng.randrange(0, max(1, h))
                pygame.draw.circle(layer, (186, 246, 164, int(30 + 70 * severity)), (x, y), rng.randint(1, 3))
        elif family == "ANOMALOUS":
            layer.fill((116, 60, 176, int(10 + 24 * severity)))
            offset = int(math.sin(self.surface_elapsed * 4.0) * 10 * severity)
            pygame.draw.line(layer, (226, 158, 255, int(50 + 50 * severity)), (0, h // 3 + offset), (w, h // 3 - offset), 2)
            pygame.draw.line(layer, (100, 240, 232, int(36 + 42 * severity)), (0, h * 2 // 3 - offset), (w, h * 2 // 3 + offset), 1)
        self.screen.blit(layer, (0, 0))

    def _draw_surface_landmark(self, landmark, sx: int, sy: int, view) -> None:
        """Draw one large, non-colliding world anchor behind gameplay objects."""
        w, h = self.screen.get_size()
        ppu = min(w / TOPDOWN_VIEW_WORLD_W, h / TOPDOWN_VIEW_WORLD_H)
        base_radius = 6.4 if bool(getattr(landmark, 'primary', False)) else 4.7
        r = max(26, int(base_radius * ppu * float(getattr(landmark, 'scale', 1.0))))
        seed = int(getattr(landmark, 'seed', 0))
        kind = str(getattr(landmark, 'kind', 'sun_ring'))
        accent = hsv_to_rgb255(self.biome['accent_hue'], 0.68, 0.94)
        accent2 = hsv_to_rgb255((self.biome['accent_hue'] + 0.10) % 1.0, 0.48, 0.82)
        base = hsv_to_rgb255(self.biome['base_hue'], 0.42, 0.48)
        pale = tuple(min(255, int(c * 0.55 + 112)) for c in accent)
        dark = (5, 8, 13)
        metal = (96, 112, 122)
        pulse = 0.5 + 0.5 * math.sin(time.time() * 1.8 + (seed % 37))

        # Grounding silhouette. Landmarks are visual-only and never participate
        # in collision or harvesting, so they cannot block a timed route.
        pygame.draw.ellipse(self.screen, (4, 7, 10), pygame.Rect(sx - r, sy + int(r * 0.28), r * 2, max(9, int(r * 0.48))))

        if kind == 'sun_ring':
            outer = pygame.Rect(sx - r, sy - r, r * 2, r * 2)
            pygame.draw.arc(self.screen, accent, outer, 0.18, 2.45, max(3, r // 12))
            pygame.draw.arc(self.screen, accent2, outer, 3.12, 5.72, max(3, r // 15))
            pygame.draw.circle(self.screen, dark, (sx, sy), max(8, r // 4))
            pygame.draw.rect(self.screen, pale, pygame.Rect(sx - max(3, r // 13), sy - int(r * 0.64), max(6, r // 7), int(r * 1.12)), border_radius=2)
            for ang in (0.0, 1.57, 3.14, 4.71):
                x1 = sx + int(math.cos(ang) * r * 0.70); y1 = sy + int(math.sin(ang) * r * 0.70)
                x2 = sx + int(math.cos(ang) * r * 0.96); y2 = sy + int(math.sin(ang) * r * 0.96)
                pygame.draw.line(self.screen, metal, (x1, y1), (x2, y2), 2)
        elif kind == 'cryo_needles':
            for i, off in enumerate((-0.48, 0.0, 0.46)):
                cx = sx + int(r * off)
                height = int(r * (1.35 if i == 1 else 0.92))
                width = max(12, int(r * (0.42 if i == 1 else 0.30)))
                points = ((cx, sy - height), (cx + width, sy + int(r * 0.52)), (cx, sy + int(r * 0.34)), (cx - width, sy + int(r * 0.52)))
                pygame.draw.polygon(self.screen, (18, 28, 42), points)
                pygame.draw.polygon(self.screen, pale if i == 1 else accent2, points, max(2, r // 22))
                pygame.draw.line(self.screen, (226, 246, 255), (cx, sy - height + 7), (cx, sy + int(r * 0.27)), 2)
        elif kind == 'root_cathedral':
            pygame.draw.circle(self.screen, (12, 24, 17), (sx, sy), int(r * 0.65))
            pygame.draw.circle(self.screen, accent2, (sx, sy), int(r * 0.62), max(3, r // 16))
            for i in range(7):
                ang = i * math.tau / 7.0 + 0.21
                ex = sx + int(math.cos(ang) * r * 0.98)
                ey = sy + int(math.sin(ang) * r * 0.78)
                mx = sx + int(math.cos(ang + 0.35) * r * 0.46)
                my = sy + int(math.sin(ang + 0.35) * r * 0.42)
                pygame.draw.line(self.screen, base, (sx, sy), (mx, my), max(4, r // 11))
                pygame.draw.line(self.screen, accent, (mx, my), (ex, ey), max(2, r // 22))
            pygame.draw.circle(self.screen, pale, (sx, sy), max(5, r // 10), 2)
        elif kind == 'caldera_crown':
            pygame.draw.circle(self.screen, (18, 9, 10), (sx, sy), int(r * 0.78))
            pygame.draw.circle(self.screen, base, (sx, sy), int(r * 0.76), max(5, r // 10))
            pygame.draw.circle(self.screen, accent, (sx, sy), int(r * (0.46 + pulse * 0.03)), max(3, r // 17))
            pygame.draw.circle(self.screen, dark, (sx, sy), int(r * 0.31))
            for i in range(9):
                ang = i * math.tau / 9.0
                p1 = (sx + int(math.cos(ang - 0.10) * r * 0.78), sy + int(math.sin(ang - 0.10) * r * 0.78))
                p2 = (sx + int(math.cos(ang + 0.10) * r * 0.78), sy + int(math.sin(ang + 0.10) * r * 0.78))
                tip = (sx + int(math.cos(ang) * r), sy + int(math.sin(ang) * r))
                pygame.draw.polygon(self.screen, metal, (p1, tip, p2))
        elif kind == 'prism_choir':
            for i, off in enumerate((-0.54, -0.18, 0.22, 0.56)):
                cx = sx + int(r * off)
                hh = int(r * (1.02 - abs(off) * 0.52 + (0.18 if i == 2 else 0.0)))
                ww = max(9, int(r * 0.24))
                points = ((cx, sy - hh), (cx + ww, sy), (cx, sy + int(hh * 0.55)), (cx - ww, sy))
                pygame.draw.polygon(self.screen, (13, 18, 34), points)
                pygame.draw.polygon(self.screen, accent if i % 2 else accent2, points, max(2, r // 24))
                pygame.draw.line(self.screen, pale, (cx, sy - hh + 5), (cx, sy + int(hh * 0.38)), 1)
        elif kind == 'flood_pylons':
            pygame.draw.circle(self.screen, (10, 23, 30), (sx, sy), int(r * 0.68), max(4, r // 12))
            for i in range(5):
                ang = i * math.tau / 5.0 + 0.3
                cx = sx + int(math.cos(ang) * r * 0.62)
                cy = sy + int(math.sin(ang) * r * 0.48)
                rr = max(7, int(r * 0.16))
                pygame.draw.circle(self.screen, dark, (cx, cy), rr)
                pygame.draw.circle(self.screen, accent2, (cx, cy), rr, 2)
                pygame.draw.line(self.screen, accent, (cx, cy - rr), (cx, cy - rr * 3), 3)
            pygame.draw.arc(self.screen, pale, pygame.Rect(sx - r, sy - int(r * 0.62), r * 2, int(r * 1.24)), 0.25, 2.88, 2)
        elif kind == 'spore_crown':
            pygame.draw.circle(self.screen, (20, 9, 25), (sx, sy), int(r * 0.54))
            for i in range(6):
                ang = i * math.tau / 6.0 + 0.25
                cx = sx + int(math.cos(ang) * r * 0.55)
                cy = sy + int(math.sin(ang) * r * 0.42)
                rr = max(8, int(r * (0.20 + (i % 2) * 0.05)))
                pygame.draw.line(self.screen, base, (cx, cy + rr), (cx, cy + rr * 2), max(3, rr // 3))
                pygame.draw.circle(self.screen, accent2, (cx, cy), rr)
                pygame.draw.arc(self.screen, pale, pygame.Rect(cx - rr, cy - rr, rr * 2, rr * 2), 3.5, 5.8, 2)
            pygame.draw.circle(self.screen, accent, (sx, sy), max(5, int(r * (0.10 + pulse * 0.03))), 2)
        elif kind == 'foundry_ribs':
            for i in range(4):
                rr = int(r * (0.40 + i * 0.17))
                pygame.draw.arc(self.screen, metal, pygame.Rect(sx - rr, sy - int(rr * 0.62), rr * 2, int(rr * 1.24)), 3.35, 6.05, max(3, r // 22))
            pygame.draw.line(self.screen, base, (sx - r, sy + int(r * 0.32)), (sx + r, sy - int(r * 0.15)), max(5, r // 12))
            for off in (-0.54, 0.02, 0.57):
                cx = sx + int(r * off)
                pygame.draw.rect(self.screen, accent2, pygame.Rect(cx - 3, sy - int(r * 0.46), 6, int(r * 0.88)))
        elif kind == 'mirror_obelisk':
            ww = int(r * 0.34); hh = int(r * 1.18)
            points = ((sx, sy - hh), (sx + ww, sy), (sx, sy + int(hh * 0.55)), (sx - ww, sy))
            pygame.draw.polygon(self.screen, (18, 22, 28), points)
            pygame.draw.polygon(self.screen, pale, points, max(3, r // 20))
            pygame.draw.line(self.screen, accent, (sx, sy - hh + 8), (sx, sy + int(hh * 0.40)), 2)
            for side in (-1, 1):
                pygame.draw.line(self.screen, accent2, (sx + side * ww, sy), (sx + side * int(r * 0.82), sy + int(r * 0.34)), 3)
        elif kind == 'void_lantern':
            pygame.draw.circle(self.screen, (2, 4, 9), (sx, sy), int(r * 0.72))
            pygame.draw.circle(self.screen, accent2, (sx, sy), int(r * (0.76 + pulse * 0.03)), max(3, r // 17))
            pygame.draw.circle(self.screen, accent, (sx, sy), int(r * 0.48), 2)
            pygame.draw.circle(self.screen, (2, 3, 7), (sx, sy), int(r * 0.28))
            for i in range(5):
                ang = i * math.tau / 5 + time.time() * 0.04
                cx = sx + int(math.cos(ang) * r * 0.91)
                cy = sy + int(math.sin(ang) * r * 0.66)
                pygame.draw.circle(self.screen, pale, (cx, cy), max(2, r // 22))
        elif kind == 'storm_mast':
            mast_top = sy - int(r * 1.15)
            pygame.draw.line(self.screen, metal, (sx, sy + int(r * 0.58)), (sx, mast_top), max(5, r // 11))
            pygame.draw.line(self.screen, pale, (sx - 2, sy + int(r * 0.50)), (sx - 2, mast_top + 5), 2)
            for side in (-1, 1):
                arm_y = sy - int(r * 0.42)
                arm_x = sx + side * int(r * 0.66)
                pygame.draw.line(self.screen, accent2, (sx, arm_y), (arm_x, arm_y - int(r * 0.18)), 4)
                bolt = [(arm_x, arm_y - int(r * 0.18)), (arm_x + side * 10, arm_y - int(r * 0.36)), (arm_x + side * 2, arm_y - int(r * 0.50)), (arm_x + side * 13, arm_y - int(r * 0.68))]
                pygame.draw.lines(self.screen, accent, False, bolt, 2)
            pygame.draw.circle(self.screen, accent, (sx, mast_top), max(4, r // 12), 2)
        elif kind == 'roseglass_fan':
            for i in range(7):
                ang = -1.95 + i * 0.31
                inner = (sx + int(math.cos(ang) * r * 0.16), sy + int(math.sin(ang) * r * 0.16))
                left = (sx + int(math.cos(ang - 0.09) * r * 0.98), sy + int(math.sin(ang - 0.09) * r * 0.98))
                right = (sx + int(math.cos(ang + 0.09) * r * 0.98), sy + int(math.sin(ang + 0.09) * r * 0.98))
                pygame.draw.polygon(self.screen, (26, 10, 28), (inner, left, right))
                pygame.draw.polygon(self.screen, accent if i % 2 else accent2, (inner, left, right), 2)
            pygame.draw.circle(self.screen, pale, (sx, sy), max(5, r // 10), 2)
        else:
            pygame.draw.circle(self.screen, accent, (sx, sy), int(r * 0.72), 3)

        # Only the primary anchor identifies itself, and only at conversational
        # distance.  This adds orientation without becoming another HUD panel.
        distance = math.hypot(self.cam_x - float(landmark.x), self.cam_y - float(landmark.y))
        if bool(getattr(landmark, 'primary', False)) and distance <= 58.0:
            title = self.fps_font.render(str(getattr(landmark, 'title', 'LANDMARK')), True, pale)
            label_x = int(clamp(sx - title.get_width() // 2, 18, w - title.get_width() - 18))
            label_y = int(clamp(sy - r - 34, 118, h - 94))
            bg = pygame.Rect(label_x - 8, label_y - 4, title.get_width() + 16, title.get_height() + 8)
            pygame.draw.rect(self.screen, (5, 9, 14), bg, border_radius=4)
            pygame.draw.rect(self.screen, accent2, bg, 1, border_radius=4)
            self.screen.blit(title, (label_x, label_y))

    def draw_surface_topdown(self) -> None:
        w, h = self.screen.get_size()
        view = self._topdown_view_rect()
        left, top, view_w, view_h = view
        self._draw_chunked_terrain(view)

        # Pass 23 removes the screen-wide navigation lattice. ridges, basins, strata,
        # faults, and localized deposits remain readable. Region and
        # objective information remain in the HUD, leaving geological relief
        # unobstructed during exploration.

        # Pass 27: large visual-only anchors give each world family a readable
        # silhouette and navigation memory without adding collision or another
        # objective layer. Draw them behind harvestable props and authored ruins.
        for landmark in self.landmarks:
            if not self._topdown_visible(landmark.x, landmark.y, view, margin=14.0):
                continue
            lx, ly = self._topdown_world_to_screen(landmark.x, landmark.y, view)
            self._draw_surface_landmark(landmark, lx, ly, view)

        tree_col = hsv_to_rgb255(self.biome['base_hue'], 0.62, 0.56)
        plant_col = hsv_to_rgb255(self.biome['accent_hue'], 0.66, 0.88)
        visible_trees, visible_plants, visible_props = self._visible_topdown_static(view)
        for tree in visible_trees:
            if self._is_harvested('tree', int(tree.get('seed', 0))):
                continue
            if self._topdown_visible(tree['x'], tree['y'], view):
                sx, sy = self._topdown_world_to_screen(tree['x'], tree['y'], view)
                size = 5 + (int(tree.get('seed', 0)) % 3)
                pygame.draw.ellipse(self.screen, (5, 9, 13), pygame.Rect(sx - size - 1, sy + 2, size * 2 + 5, size + 5))
                pygame.draw.line(self.screen, (54, 48, 42), (sx, sy + 1), (sx, sy + 8), 2)
                pygame.draw.circle(self.screen, tree_col, (sx, sy - 2), size)
                pygame.draw.circle(self.screen, tuple(min(255, c + 28) for c in tree_col), (sx - 2, sy - 4), max(2, size // 2))
        for plant in visible_plants:
            if self._is_harvested('plant', int(plant.get('seed', 0))):
                continue
            if self._topdown_visible(plant['x'], plant['y'], view):
                sx, sy = self._topdown_world_to_screen(plant['x'], plant['y'], view)
                pygame.draw.line(self.screen, plant_col, (sx - 4, sy + 2), (sx + 4, sy - 2), 2)
                pygame.draw.line(self.screen, plant_col, (sx - 2, sy - 4), (sx + 2, sy + 4), 2)
                pygame.draw.circle(self.screen, (220, 250, 224), (sx, sy), 2)
        for prop in visible_props:
            if self._is_harvested('prop', int(prop.get('seed', 0))):
                continue
            if self._topdown_visible(prop['x'], prop['y'], view):
                sx, sy = self._topdown_world_to_screen(prop['x'], prop['y'], view)
                variant = int(prop.get('seed', 0)) % 3
                pygame.draw.ellipse(self.screen, (5, 9, 13), pygame.Rect(sx - 7, sy + 2, 15, 7))
                if variant == 0:
                    points = ((sx, sy - 6), (sx + 6, sy + 4), (sx - 5, sy + 5))
                    pygame.draw.polygon(self.screen, (32, 42, 50), points)
                    pygame.draw.polygon(self.screen, (154, 186, 198), points, 1)
                else:
                    rect = pygame.Rect(sx - 5, sy - 5, 11, 10)
                    pygame.draw.rect(self.screen, (18, 24, 32), rect, border_radius=2)
                    pygame.draw.rect(self.screen, (154, 186, 198), rect, 1, border_radius=2)
                    if variant == 2:
                        pygame.draw.line(self.screen, (98, 232, 220), (sx - 3, sy), (sx + 3, sy), 1)

        target_visible = False
        pulse = 0.5 + 0.5 * math.sin(time.time() * 3.2)
        for st in self.structures:
            if not self._topdown_visible(st.x, st.y, view, margin=8.0):
                continue
            sx, sy = self._topdown_world_to_screen(st.x, st.y, view)
            near = math.hypot(self.cam_x - st.x, self.cam_y - st.y) <= st.radius * 1.5
            harvested = self._is_harvested('structure', st.seed)
            is_target = self.target_awaits_fragment(st)
            if is_target:
                target_visible = True
                ring_col = (255, 210, 92)
                pygame.draw.circle(self.screen, (255, 196, 72), (sx, sy), int(36 + pulse * 8), 2)
                pygame.draw.circle(self.screen, (82, 244, 232), (sx, sy), 33, 2)
            else:
                ring_col = (118, 250, 238) if near else (166, 120, 242)
            pygame.draw.circle(self.screen, (4, 7, 12), (sx, sy), 30)
            pygame.draw.circle(self.screen, (76, 86, 94) if harvested else ring_col, (sx, sy), 29, 2)
            if harvested:
                pygame.draw.line(self.screen, (76, 86, 94), (sx - 15, sy), (sx + 15, sy), 3)
            else:
                icon = self._scaled_topdown_sprite(st.sprite, 58, ('structure', st.seed))
                self.screen.blit(icon, (sx - icon.get_width() // 2, sy - icon.get_height() // 2))
            if is_target:
                tag = self.fps_font.render('DATA FRAGMENT', True, (255, 226, 132))
                self.screen.blit(tag, (sx - tag.get_width() // 2, sy - 58))

        if self.resource_cache_pos is not None and not self.resource_cache_claimed:
            rx, ry = self._topdown_world_to_screen(self.resource_cache_pos[0], self.resource_cache_pos[1], view)
            role = self.resource_cache_role or 'salvage'
            cache_col = (118, 248, 214) if role == 'home' else ((112, 224, 255) if role == 'fuel' else (255, 190, 94))
            pygame.draw.circle(self.screen, cache_col, (rx, ry), int(30 + pulse * 7), 2)
            pygame.draw.rect(self.screen, (7, 12, 18), pygame.Rect(rx - 20, ry - 15, 40, 30), border_radius=5)
            pygame.draw.rect(self.screen, cache_col, pygame.Rect(rx - 20, ry - 15, 40, 30), 2, border_radius=5)
            pygame.draw.line(self.screen, cache_col, (rx - 12, ry), (rx + 12, ry), 3)
            if role in ('fuel', 'home'):
                pygame.draw.line(self.screen, cache_col, (rx, ry - 9), (rx, ry + 9), 3)
            label = self.fps_font.render(f'{role.upper()} CACHE', True, cache_col)
            self.screen.blit(label, (rx - label.get_width() // 2, ry - 46))

        candidate = self.harvest_candidate
        if candidate is not None:
            category, item, distance = candidate
            hx = float(item.x if category == 'structure' else item['x'])
            hy = float(item.y if category == 'structure' else item['y'])
            if self._topdown_visible(hx, hy, view):
                csx, csy = self._topdown_world_to_screen(hx, hy, view)
                pygame.draw.circle(self.screen, (124, 244, 176), (csx, csy), int(22 + pulse * 4), 2)

        self._draw_surface_recovery_fx(view)

        sx, sy = self._topdown_world_to_screen(self.ship_pos[0], self.ship_pos[1], view)
        carrying = bool(getattr(self.mission_state, 'carrying_fragment', False))
        if carrying:
            pygame.draw.circle(self.screen, (255, 206, 92), (sx, sy), int(52 + pulse * 8), 3)
        pygame.draw.circle(self.screen, (4, 8, 12), (sx, sy), 46)
        pygame.draw.circle(self.screen, (255, 214, 112) if carrying else (92, 244, 238), (sx, sy), 44, 2)
        ship_icon = self._scaled_topdown_sprite(self.ship_sprite, 92, ('ship', self.seed))
        self.screen.blit(ship_icon, (sx - ship_icon.get_width() // 2, sy - ship_icon.get_height() // 2))

        px, py = self._topdown_world_to_screen(self.cam_x, self.cam_y, view)
        direction = self.surface_facing
        fwd_by_direction = {
            'right': (1.0, 0.0),
            'down': (0.0, 1.0),
            'left': (-1.0, 0.0),
            'up': (0.0, -1.0),
        }
        fwd = fwd_by_direction.get(direction, (0.0, -1.0))
        frames = self.topdown_player_frames.get(direction, ())
        if frames:
            if self.surface_is_moving and len(frames) > 1:
                frame_index = int(self.surface_anim_time * 7.0) % len(frames)
            else:
                frame_index = 0
            frame = frames[frame_index]
            actor = self._scaled_topdown_sprite(frame, 72, ('player', direction, frame_index))
            pygame.draw.ellipse(self.screen, (3, 7, 11), pygame.Rect(px - 27, py + 20, 54, 19))
            if self.surface_is_moving:
                pygame.draw.circle(self.screen, (82, 238, 232), (px, py), 31, 1)
            self.screen.blit(actor, (px - actor.get_width() // 2, py - actor.get_height() // 2))
        else:
            right = (-fwd[1], fwd[0])
            nose = (px + fwd[0] * 20, py + fwd[1] * 20)
            rear = (px - fwd[0] * 12, py - fwd[1] * 12)
            p1 = (rear[0] + right[0] * 11, rear[1] + right[1] * 11)
            p2 = (rear[0] - right[0] * 11, rear[1] - right[1] * 11)
            pygame.draw.polygon(self.screen, (232, 250, 252), [nose, p1, p2])
            pygame.draw.polygon(self.screen, (82, 238, 232), [nose, p1, p2], 2)
        # A compact facing chevron replaces the long debug-like direction line.
        tip = (int(px + fwd[0] * 35), int(py + fwd[1] * 35))
        right = (-fwd[1], fwd[0])
        p1 = (int(px + fwd[0] * 27 + right[0] * 5), int(py + fwd[1] * 27 + right[1] * 5))
        p2 = (int(px + fwd[0] * 27 - right[0] * 5), int(py + fwd[1] * 27 - right[1] * 5))
        pygame.draw.polygon(self.screen, (112, 244, 238), (tip, p1, p2))

        st, dist = self.get_nearby_structure()
        if st is not None and dist <= 34.0 and self._topdown_visible(st.x, st.y, view):
            tx, ty = self._topdown_world_to_screen(st.x, st.y, view)
            pygame.draw.line(self.screen, (112, 244, 238), (px, py), (tx, ty), 1)

        # Keep the objective readable even when it is outside the camera crop.
        objective = None
        objective_color = (255, 214, 112)
        if carrying:
            objective = self.ship_pos
        elif self.resource_cache_pos is not None and not self.resource_cache_claimed:
            objective = self.resource_cache_pos
            objective_color = (112, 224, 255) if self.resource_cache_role == 'fuel' else (255, 190, 94)
        elif self.mission_target_structure is not None and not bool(getattr(self.mission_state, 'fragment_deposited', False)):
            objective = (self.mission_target_structure.x, self.mission_target_structure.y)
        if objective is not None:
            ox, oy = self._topdown_world_to_screen(objective[0], objective[1], view)
            if not (52 <= ox <= w - 52 and 112 <= oy <= h - 92):
                dx = ox - px
                dy = oy - py
                length = max(1.0, math.hypot(dx, dy))
                dx /= length
                dy /= length
                # ANOMALOUS worlds deliberately corrupt only long-range guidance.
                # The actual objective position/collision remains authoritative.
                drift = float(getattr(self.hazard_frame, "signal_angle_offset", 0.0))
                if abs(drift) > 1e-6:
                    cos_d = math.cos(drift)
                    sin_d = math.sin(drift)
                    dx, dy = (dx * cos_d - dy * sin_d, dx * sin_d + dy * cos_d)
                edge_x = int(clamp(px + dx * 420, 70, w - 70))
                edge_y = int(clamp(py + dy * 300, 126, h - 106))
                right = (-dy, dx)
                tip = (edge_x + int(dx * 18), edge_y + int(dy * 18))
                p1 = (edge_x - int(dx * 10) + int(right[0] * 10), edge_y - int(dy * 10) + int(right[1] * 10))
                p2 = (edge_x - int(dx * 10) - int(right[0] * 10), edge_y - int(dy * 10) - int(right[1] * 10))
                pygame.draw.polygon(self.screen, objective_color, (tip, p1, p2))
                pygame.draw.circle(self.screen, (4, 8, 12), (edge_x, edge_y), 24, 2)

        self._draw_topdown_weather()
        self._draw_surface_hazard_fx()
        self._draw_surface_finish()
        if self.hud_visible:
            self.draw_surface_hud()
            self._draw_surface_action_prompt()

    def draw_surface_hud(self) -> None:
        st, dist = self.get_nearby_structure()
        region_x = math.floor(self.cam_x / CHUNK_WORLD_SIZE)
        region_y = math.floor(self.cam_y / CHUNK_WORLD_SIZE)
        lines = [
            f'{self.planet_name}  /  {self.biome["name"]}',
            f'REGION {region_x:+d},{region_y:+d}  /  COORD {self.cam_x:+06.1f}, {self.cam_y:+06.1f}',
        ]
        mission = self.mission_state
        hazard = getattr(self, "hazard_frame", None)
        if hazard is not None and str(getattr(hazard, "family", "UNKNOWN")) != "UNKNOWN":
            family = str(hazard.family)
            label = str(hazard.label)
            instruction = str(hazard.instruction)
            lines.append(f'HAZARD {family}  /  {label}  /  {instruction}')
        if mission is not None and self.resource_cache_role in ('fuel', 'salvage'):
            if self.resource_cache_claimed:
                lines.append(f'{self.resource_cache_role.upper()} CACHE SECURED  /  RETURN TO SHIP')
            elif self.resource_cache_pos is not None:
                lines.append(f'{self.resource_cache_role.upper()} CACHE  /  {self.resource_cache_distance():03.0f}m')
        if mission is not None and self.mission_planet_index == mission.target_planet_index:
            profile = world_profile(getattr(mission, "target_style", self.biome.get("terrain", "unknown")))
            lines.append(
                f'ARCHIVE {int(getattr(mission, "current_archive_slot", 1))}/{int(getattr(mission, "data_fragments_required", 6))}  /  {profile.record_name}'
            )
            if mission.fragment_deposited:
                lines.append(f'DATA FRAGMENT SECURED  /  ARCHIVE {int(getattr(mission, "fragments_secured_total", 0))}/{int(getattr(mission, "data_fragments_required", 6))}')
            elif bool(getattr(mission, "carrying_fragment", False)):
                lines.append('DATA FRAGMENT CARRIED  /  RETURN TO SHIP  /  SECURE AT CARGO')
            elif self.mission_target_structure is not None:
                target_dist = math.hypot(self.cam_x - self.mission_target_structure.x, self.cam_y - self.mission_target_structure.y)
                display_dist = target_dist * float(getattr(self.hazard_frame, "signal_distance_multiplier", 1.0))
                suffix = "  /  SIGNAL UNSTABLE" if str(getattr(self.hazard_frame, "family", "")) == "ANOMALOUS" and float(getattr(self.hazard_frame, "severity", 0.0)) >= 0.12 else ""
                lines.append(f'DATA FRAGMENT  {self.mission_target_structure.title.upper()}  /  {display_dist:03.0f}m{suffix}')
        candidate = self.harvest_candidate
        if candidate is None and st is not None and dist <= st.radius * 1.5:
            target_tag = '  /  TARGET' if bool(getattr(st, 'is_mission_target', False)) else ''
            lines.append(f'NEARBY  {st.title.upper()}  /  STRIPPED LANDMARK{target_tag}')
        if math.hypot(self.cam_x - self.ship_pos[0], self.cam_y - self.ship_pos[1]) <= 80:
            lines.append('SHIP BEACON IN RANGE')
        panel_w = min(720, self.screen.get_width() - 96)
        panel_h = 48 + max(0, len(lines) - 1) * 24
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((5, 8, 14, 188))
        self.screen.blit(panel, (48, 36))
        pygame.draw.rect(self.screen, (55, 92, 112), pygame.Rect(48, 36, panel_w, panel_h), 1, border_radius=8)
        for i, line in enumerate(lines):
            color = (232, 242, 248) if i == 0 else (138, 222, 226)
            txt = self.fps_font.render(line, True, color)
            self.screen.blit(txt, (64, 48 + i * 24))

    def draw_sky_bodies(self) -> None:
        for body in self.sky_bodies:
            x = int(body['x'] - math.sin(self.cam_ang * 0.35) * 42.0)
            y = int(body['y'] + self.pitch * 0.08)
            r = body['r']
            halo = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
            for i in range(5, 0, -1):
                pygame.draw.circle(halo, (*body['color'], 16 + i * 10), (halo.get_width() // 2, halo.get_height() // 2), r + i * 8)
            self.screen.blit(halo, (x - halo.get_width() // 2, y - halo.get_height() // 2), special_flags=pygame.BLEND_RGBA_ADD)
            pygame.draw.circle(self.screen, body['color'], (x, y), r)
            pygame.draw.circle(self.screen, (255, 255, 255), (x - max(4, r // 3), y - max(4, r // 3)), max(4, r // 6))
            if body['ring']:
                ring = pygame.Surface((r * 4, r * 2), pygame.SRCALPHA)
                pygame.draw.ellipse(ring, (*body['color'], 110), ring.get_rect().inflate(-20, -20), 3)
                ring = pygame.transform.rotozoom(ring, math.degrees(body['ring_tilt']), 1.0)
                self.screen.blit(ring, (x - ring.get_width() // 2, y - ring.get_height() // 2), special_flags=pygame.BLEND_RGBA_ADD)

    def draw_dungeon(self) -> None:
        self.draw_floor_ceiling_casting()
        self.raycast_dungeon()
        self.draw_dungeon_props()
        if self.fragment_pos is not None and self.fragment_sprite is not None:
            self.draw_dungeon_billboard(
                self.fragment_sprite, self.fragment_pos[0], self.fragment_pos[1],
                self.seed ^ 0xF16A6E, 1.30, -18, True,
            )
        self.draw_dungeon_creatures_render()
        if self.fragment_recovery_flash > 0.0:
            flash = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            flash.fill((88, 255, 238, int(120 * min(1.0, self.fragment_recovery_flash))))
            self.screen.blit(flash, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        if self.hud_visible:
            panel_h = 78 if self._target_structure_is_active() else 48
            panel = pygame.Surface((760, panel_h), pygame.SRCALPHA)
            panel.fill((5, 8, 14, 188))
            self.screen.blit(panel, (48, 36))
            pygame.draw.rect(self.screen, (55, 92, 112), pygame.Rect(48, 36, 760, panel_h), 1, border_radius=8)
            title = f'{self.interior_theme}  /  {self.active_structure.title if self.active_structure else "Ruin"}'
            a = self.fps_font.render(title.upper(), True, (232, 242, 248))
            self.screen.blit(a, (64, 49))
            if self._target_structure_is_active():
                if self.fragment_pos is not None:
                    distance = math.hypot(self.interior_px - self.fragment_pos[0], self.interior_py - self.fragment_pos[1])
                    prompt = 'E  EXTRACT MATRIX FRAGMENT' if distance <= 1.75 else f'VAULT SIGNAL  /  {distance:04.1f}m'
                    color = (255, 226, 132) if distance <= 1.75 else (112, 244, 238)
                elif self.mission_state is not None and self.mission_state.carrying_fragment:
                    prompt = 'FRAGMENT RECOVERED  /  FIND THE EXIT'
                    color = (255, 226, 132)
                else:
                    prompt = 'VAULT SIGNAL LOST'
                    color = (220, 150, 120)
                b = self.fps_font.render(prompt, True, color)
                self.screen.blit(b, (64, 78))

    def get_nearby_structure(self):
        best = None
        best_dist = 1e9
        for st in self.structures:
            d = math.hypot(self.cam_x - st.x, self.cam_y - st.y)
            if d < best_dist:
                best = st
                best_dist = d
        return best, best_dist

    def height_at(self, fx, fy):
        return int(sample_geology(self.seed, self.biome['terrain'], float(fx), float(fy)).height * 255.0)

    def project_point(self, cam_x, cam_y, cam_ang, cam_z, pitch_px, x, y, z):
        dx = x - cam_x
        dy = y - cam_y
        dist = math.hypot(dx, dy)
        if dist < 0.001:
            return None
        ang_to = math.atan2(dy, dx)
        rel = (ang_to - cam_ang + math.pi) % (2 * math.pi) - math.pi
        if not (-HALF_FOV < rel < HALF_FOV):
            return None
        ow_w, ow_h = self.lowres.get_size()
        sx = (ow_w // 2) + math.tan(rel) * (ow_w // 2 / math.tan(HALF_FOV))
        sy = (ow_h // 2) + int(pitch_px / 2) - ((z - cam_z) / dist) * (240 / 2)
        sc = self.screen.get_width() / max(1, ow_w)
        scy = self.screen.get_height() / max(1, ow_h)
        return int(sx * sc), int(sy * scy), dist

    def fog_factor(self, dist, storm_intensity):
        f = dist * 0.0035 * float(self.biome.get('fog_density', 1.0)) * (1.0 + 0.55 * storm_intensity)
        return 0.0 if f < 0.0 else 1.0 if f > 1.0 else f

    def sprite_fog_blend(self, sprite, fog_color, alpha):
        if alpha <= 0:
            return sprite
        spr = sprite.copy()
        ov = pygame.Surface(spr.get_size(), pygame.SRCALPHA)
        ov.fill((*fog_color, alpha))
        ov.blit(spr, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        spr.blit(ov, (0, 0))
        return spr

    def billboard_draw(self, sprite, cam_x, cam_y, cam_ang, cam_z, obj_x, obj_y, obj_h, base_scale, pitch_px, storm_intensity, extra_alpha=10):
        dx = obj_x - cam_x
        dy = obj_y - cam_y
        dist = math.hypot(dx, dy)
        if dist < 2.0 or dist > 420.0:
            return
        ang_to = math.atan2(dy, dx)
        rel = (ang_to - cam_ang + math.pi) % (2 * math.pi) - math.pi
        if not (-HALF_FOV < rel < HALF_FOV):
            return
        ow_w, ow_h = self.lowres.get_size()
        screen_dist = ow_w // 2 / math.tan(HALF_FOV)
        size = (screen_dist / dist) * 1.22 * base_scale
        size = max(4, min(size, 1200))
        sw = max(2, int(sprite.get_width() * size / 90))
        sh = max(2, int(sprite.get_height() * size / 90))
        spr = pygame.transform.smoothscale(sprite, (sw, sh))
        scx = self.screen.get_width() / max(1, ow_w)
        scy = self.screen.get_height() / max(1, ow_h)
        x = int((((ow_w // 2) + math.tan(rel) * screen_dist - spr.get_width() // 2) * scx))
        y = int(((ow_h // 2 + int(pitch_px / 2) - ((obj_h - cam_z) / dist) * (240 / 2) - spr.get_height()) * scy))
        ff = self.fog_factor(dist, storm_intensity)
        alpha = int(clamp((ff * 125) + extra_alpha, 0, 170))
        spr = self.sprite_fog_blend(spr, self.biome['fog'], alpha)
        shadow_w = max(12, int(spr.get_width() * 0.42))
        shadow_h = max(8, int(shadow_w * 0.28))
        shadow = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 70), shadow.get_rect())
        self.screen.blit(shadow, (int(x + spr.get_width() * 0.32), int(y + spr.get_height() * 0.92)))
        self.screen.blit(spr, (x, y))

    def draw_magic_mote(self, cam_x, cam_y, cam_ang, cam_z, pitch_px, storm_intensity, mote, now):
        bob = math.sin(now * 1.3 + mote['phase']) * mote['amp']
        proj = self.project_point(cam_x, cam_y, cam_ang, cam_z, pitch_px, mote['x'], mote['y'], mote['base_h'] + bob)
        if not proj:
            return
        sx, sy, dist = proj
        ff = self.fog_factor(dist, storm_intensity)
        col = hsv_to_rgb255(mote['hue'], 0.80, 1.0)
        a = int(220 * (1.0 - ff))
        if a <= 0:
            return
        pygame.draw.circle(self.screen, (*col, a), (sx, sy), 3)
        pygame.draw.circle(self.screen, (*col, a // 2), (sx, sy), 8, 2)

    def draw_voxel_world_lowres(self, surf, cam_x, cam_y, cam_z, cam_ang, pitch_px, storm_intensity):
        biome = self.biome
        ow_w, ow_h = surf.get_size()
        horizon = ow_h // 2 + int(pitch_px / 2)
        # sky gradient
        for y in range(max(0, horizon)):
            t = y / max(1, horizon)
            col = (
                int(lerp(biome['sky'][0], biome['fog'][0], t * 0.65)),
                int(lerp(biome['sky'][1], biome['fog'][1], t * 0.65)),
                int(lerp(biome['sky'][2], biome['fog'][2], t * 0.65)),
            )
            surf.fill(col, (0, y, ow_w, 1))
        for y in range(max(0, horizon), ow_h):
            t = (y - horizon) / max(1, ow_h - horizon)
            surf.fill((int(lerp(18, 8, t)), int(lerp(18, 8, t)), int(lerp(20, 10, t))), (0, y, ow_w, 1))

        y_scale = 330.0 / 2
        max_dist = 720.0
        ca = math.cos(cam_ang)
        sa = math.sin(cam_ang)
        rel_angles = [(-HALF_FOV + (i / max(1, ow_w - 1)) * (2 * HALF_FOV)) for i in range(ow_w)]
        for sx in range(ow_w):
            rel = rel_angles[sx]
            dx = ca * math.cos(rel) - sa * math.sin(rel)
            dy = sa * math.cos(rel) + ca * math.sin(rel)
            y_min = ow_h
            dist = 1.0
            while dist < max_dist and y_min > 0:
                wx = cam_x + dx * dist
                wy = cam_y + dy * dist
                ix = int(wx) & (WORLD_SIZE - 1)
                iy = int(wy) & (WORLD_SIZE - 1)
                h = self.height[iy][ix]
                r, g, b = self.color[iy][ix]
                # slope lighting to increase 3D feel
                hx = self.height[iy][(ix + 1) & (WORLD_SIZE - 1)] - self.height[iy][(ix - 1) & (WORLD_SIZE - 1)]
                hy = self.height[(iy + 1) & (WORLD_SIZE - 1)][ix] - self.height[(iy - 1) & (WORLD_SIZE - 1)][ix]
                slope = clamp(0.55 + (-hx * 0.0035 + hy * 0.0025), 0.28, 1.18)
                proj_y = int(horizon - ((h - cam_z) / dist) * y_scale)
                if proj_y < y_min:
                    ff = self.fog_factor(dist, storm_intensity) * 0.44
                    rr = int((r * slope) * (1.0 - ff) + biome['fog'][0] * ff)
                    gg = int((g * slope) * (1.0 - ff) + biome['fog'][1] * ff)
                    bb = int((b * slope) * (1.0 - ff) + biome['fog'][2] * ff)
                    rr = max(74, min(255, rr))
                    gg = max(74, min(255, gg))
                    bb = max(74, min(255, bb))
                    pygame.draw.line(surf, (rr, gg, bb), (sx, proj_y), (sx, y_min))
                    y_min = proj_y
                dist += 1.72

    def draw_atmosphere_fx(self) -> None:
        weather = self.biome.get('weather', 'mist')
        w, h = self.screen.get_size()
        now = time.time()
        strength = 0.45 + self.storm_intensity * 0.85
        count = int(30 + 52 * strength)
        accent = hsv_to_rgb255(self.biome['accent_hue'], 0.62, 0.98)
        fog = self.biome['fog']
        for i in range(count):
            code = (self.seed * 1103515245 + i * 2654435761) & 0xFFFFFFFF
            phase = ((code >> 8) & 0xFFFF) / 65535.0
            speed = 18.0 + ((code >> 24) & 0xFF) * 0.38
            x0 = code % max(1, w)
            y0 = (code // max(1, w)) % max(1, h)
            if weather in ('rain', 'tempest'):
                x = int((x0 - now * speed * 0.35) % w)
                y = int((y0 + now * speed * 2.8) % h)
                col = tuple(int(lerp(fog[c], 230, 0.42)) for c in range(3))
                pygame.draw.line(self.screen, col, (x, y), (x - 6, y + 24 + int(18 * strength)), 1)
            elif weather in ('sand', 'cinders', 'ash'):
                x = int((x0 + now * speed * 1.45) % w)
                y = int((y0 + math.sin(now * 0.7 + phase * math.tau) * 22) % h)
                col = accent if weather == 'cinders' else tuple(int(lerp(fog[c], accent[c], 0.35)) for c in range(3))
                pygame.draw.line(self.screen, col, (x, y), (x + 5 + int(10 * strength), y - 2), 1)
            elif weather in ('snow', 'salt', 'glass', 'shards'):
                x = int((x0 + math.sin(now * 0.5 + phase * math.tau) * 34) % w)
                y = int((y0 + now * speed * (0.55 if weather == 'snow' else 0.80)) % h)
                col = (238, 242, 250) if weather in ('snow', 'salt') else accent
                if weather in ('glass', 'shards'):
                    pygame.draw.line(self.screen, col, (x, y), (x + 4, y + 10), 1)
                else:
                    pygame.draw.circle(self.screen, col, (x, y), 1 + (code & 1))
            elif weather in ('spores', 'embers'):
                x = int((x0 + math.sin(now * 0.35 + phase * math.tau) * 48) % w)
                y = int((y0 - now * speed * 0.38) % h)
                col = accent
                pygame.draw.circle(self.screen, col, (x, y), 1 + (code & 2))
            else:  # ocean mist and quiet atmospheric drift
                x = int((x0 + now * speed * 0.32) % w)
                y = int((y0 + math.sin(now * 0.22 + phase * math.tau) * 14) % h)
                pygame.draw.circle(self.screen, fog, (x, y), 1)
        if weather == 'tempest':
            flash = math.sin(now * 1.75 + (self.seed & 31))
            if flash > 0.985:
                horizon = int(h * 0.28)
                x = int((self.seed * 97 + int(now * 37)) % w)
                pts = [(x, 0), (x - 22, horizon // 3), (x + 8, horizon * 2 // 3), (x - 34, horizon)]
                pygame.draw.lines(self.screen, (236, 242, 255), False, pts, 3)

    def blit_grain(self):
        if not self._grain:
            return
        self._grain_i = (self._grain_i + 1) % len(self._grain)
        self.screen.blit(self._grain[self._grain_i], (0, 0))

    def update_particles(self, dt):
        i = 0
        while i < len(self.particles):
            p = self.particles[i]
            p['life'] -= dt
            if p['life'] <= 0:
                self.particles[i] = self.particles[-1]
                self.particles.pop()
                continue
            p['vx'] *= 0.985
            p['vy'] *= 0.985
            p['vz'] *= 0.995
            p['x'] += p['vx'] * dt * 8.0
            p['y'] += p['vy'] * dt * 8.0
            p['z'] += p['vz'] * dt * 8.0
            i += 1

    def draw_particles(self, cam_x, cam_y, cam_ang, cam_z, pitch_px, storm_intensity):
        for p in self.particles:
            proj = self.project_point(cam_x, cam_y, cam_ang, cam_z, pitch_px, p['x'], p['y'], p['z'])
            if proj:
                sx, sy, dist = proj
                ff = self.fog_factor(dist, storm_intensity)
                col = hsv_to_rgb255(p['hue'], 0.85, 1.0)
                a = int(240 * (p['life'] / 0.85) * (1.0 - ff))
                if a > 0:
                    pygame.draw.circle(self.screen, (*col, a), (sx, sy), p['size'])
                    pygame.draw.circle(self.screen, (*col, a // 3), (sx, sy), p['size'] + 6, 2)

    def preload(self) -> None:
        self._ensure_lowres()

    # -------------------- dungeon helpers --------------------
    def set_dungeon_map(self, rows):
        self.dungeon_map = rows
        self.map_h = len(rows)
        self.map_w = len(rows[0]) if rows else 0

    def cell_at(self, tx, ty):
        if 0 <= tx < self.map_w and 0 <= ty < self.map_h:
            return self.dungeon_map[ty][tx]
        return '1'

    def is_floor_cell(self, tx, ty):
        return self.cell_at(tx, ty) in ('0', '2')

    def is_wall_cell(self, tx, ty):
        return self.cell_at(tx, ty) in ('1', '2')

    def is_exit_cell(self, tx, ty):
        return self.cell_at(tx, ty) == '2'

    def circle_hits_wall(self, cx, cy, radius):
        min_tx = int(cx - radius) - 1
        max_tx = int(cx + radius) + 1
        min_ty = int(cy - radius) - 1
        max_ty = int(cy + radius) + 1
        for ty in range(min_ty, max_ty + 1):
            for tx in range(min_tx, max_tx + 1):
                if not self.is_wall_cell(tx, ty):
                    continue
                x0, y0 = tx, ty
                x1, y1 = tx + 1.0, ty + 1.0
                px = cx if x0 <= cx <= x1 else (x0 if cx < x0 else x1)
                py = cy if y0 <= cy <= y1 else (y0 if cy < y0 else y1)
                dx = cx - px
                dy = cy - py
                if dx * dx + dy * dy < radius * radius:
                    return True
        return False

    def move_with_barrier(self, dx, dy):
        nx = self.interior_px + dx
        if not self.circle_hits_wall(nx, self.interior_py, PLAYER_RADIUS) and self.is_floor_cell(int(nx), int(self.interior_py)):
            self.interior_px = nx
        ny = self.interior_py + dy
        if not self.circle_hits_wall(self.interior_px, ny, PLAYER_RADIUS) and self.is_floor_cell(int(self.interior_px), int(ny)):
            self.interior_py = ny

    def tile_clearance_score(self, tx, ty, max_r=6):
        if not self.is_floor_cell(tx, ty):
            return -999
        best = max_r
        for r in range(1, max_r + 1):
            for oy in range(-r, r + 1):
                for ox in range(-r, r + 1):
                    if abs(ox) != r and abs(oy) != r:
                        continue
                    if self.is_wall_cell(tx + ox, ty + oy):
                        return r - 1
        return best

    def find_safe_spawn(self, prefer_near=(3, 3)):
        best = None
        best_score = -999.0
        px0, py0 = prefer_near
        for ty in range(1, self.map_h - 1):
            for tx in range(1, self.map_w - 1):
                if not self.is_floor_cell(tx, ty) or self.is_exit_cell(tx, ty):
                    continue
                cx, cy = tx + 0.5, ty + 0.5
                if self.circle_hits_wall(cx, cy, PLAYER_RADIUS + 0.02):
                    continue
                cscore = self.tile_clearance_score(tx, ty, 6)
                dist_bias = -0.15 * math.hypot(tx - px0, ty - py0)
                score = cscore * 2.0 + dist_bias
                if score > best_score:
                    best_score = score
                    best = (cx, cy)
        return best if best is not None else (3.5, 3.5)

    def reset_dungeon_player(self):
        sx, sy = self.find_safe_spawn((3, 3))
        self.interior_px = sx
        self.interior_py = sy
        self.interior_angle = 0.0
        self.interior_pitch = 0.0

    def find_fragment_vault(self):
        """Place the fragment in a distant, clear, reachable floor cell."""
        best = None
        best_score = -1e9
        for ty in range(1, self.map_h - 1):
            for tx in range(1, self.map_w - 1):
                if not self.is_floor_cell(tx, ty) or self.is_exit_cell(tx, ty):
                    continue
                cx, cy = tx + 0.5, ty + 0.5
                if self.circle_hits_wall(cx, cy, PLAYER_RADIUS + 0.08):
                    continue
                clearance = self.tile_clearance_score(tx, ty, 6)
                if clearance < 2:
                    continue
                distance = math.hypot(cx - self.interior_px, cy - self.interior_py)
                score = distance * 2.0 + clearance * 3.0
                if score > best_score:
                    best_score = score
                    best = (cx, cy)
        return best

    def try_recover_fragment(self) -> bool:
        if self.fragment_pos is None or self.mission_state is None or self.active_structure is None:
            return False
        distance = math.hypot(self.interior_px - self.fragment_pos[0], self.interior_py - self.fragment_pos[1])
        if distance > 1.75:
            return False
        if not self.mission_state.recover_fragment(self.active_structure.seed):
            return False
        self.fragment_pos = None
        self.fragment_recovery_flash = 1.1
        self.interior_creatures.clear()
        self.set_notification('MATRIX FRAGMENT RECOVERED — RETURN TO THE SHIP', 3.2)
        return True

    def has_line_of_sight(self, x0, y0, x1, y1, step=0.08):
        dx = x1 - x0
        dy = y1 - y0
        dist = math.hypot(dx, dy)
        if dist < 0.001:
            return True
        vx = dx / dist
        vy = dy / dist
        t = 0.0
        while t < dist:
            cx = x0 + vx * t
            cy = y0 + vy * t
            if self.is_wall_cell(int(cx), int(cy)):
                return False
            t += step
        return True

    def trace_center_hit(self, max_depth=2.8, step=0.02):
        sin_a = math.sin(self.interior_angle)
        cos_a = math.cos(self.interior_angle)
        dist = 0.05
        while dist < max_depth:
            x = self.interior_px + dist * cos_a
            y = self.interior_py + dist * sin_a
            tx, ty = int(x), int(y)
            c = self.cell_at(tx, ty)
            if c != '0':
                return c, tx, ty, dist
            dist += step
        return None, int(self.interior_px), int(self.interior_py), max_depth

    def try_spawn_monsters(self):
        if len(self.interior_creatures) >= 1 + min(6, len(self.structures)):
            return
        now = time.time()
        dt = now - self.last_spawn_check
        if dt <= 0:
            return
        self.last_spawn_check = now
        pressure = min(0.24, SPAWN_CHANCE_PER_SEC + 0.02 * max(0, len(self.interior_props) // 3))
        chance = 1.0 - (1.0 - pressure) ** dt
        if random.random() > chance:
            return
        for _ in range(220):
            tx = random.randint(1, self.map_w - 2)
            ty = random.randint(1, self.map_h - 2)
            if not self.is_floor_cell(tx, ty) or self.is_exit_cell(tx, ty):
                continue
            sx = tx + 0.5
            sy = ty + 0.5
            d = math.hypot(sx - self.interior_px, sy - self.interior_py)
            if not (MIN_SPAWN_DIST <= d <= MAX_SPAWN_DIST):
                continue
            ang_to = math.atan2(sy - self.interior_py, sx - self.interior_px)
            rel = (ang_to - self.interior_angle + math.pi) % (2 * math.pi) - math.pi
            if abs(rel) < HALF_FOV * 0.7:
                continue
            if not self.has_line_of_sight(sx, sy, self.interior_px, self.interior_py):
                continue
            seed = random.randint(0, 999999)
            self.interior_creatures.append(DungeonCreature(sx, sy, seed, self.make_nightmare_sprite(seed), False))
            break

    def update_dungeon_creatures(self):
        alive = []
        for m in self.interior_creatures:
            dist = math.hypot(m.x - self.interior_px, m.y - self.interior_py)
            if dist < ALIEN_CATCH_DIST:
                self.reset_dungeon_player()
                self.interior_creatures.clear()
                self.set_notification('The ruin rejects you back to the gate', 2.0)
                return
            los = self.has_line_of_sight(m.x, m.y, self.interior_px, self.interior_py)
            speed = ALIEN_SPEED * (1.0 if los else 0.55)
            dx = self.interior_px - m.x
            dy = self.interior_py - m.y
            d = math.hypot(dx, dy)
            if d > 0.001:
                dx /= d
                dy /= d
            if not los:
                drift = random.uniform(-0.35, 0.35)
                dx, dy = (dx * math.cos(drift) - dy * math.sin(drift), dx * math.sin(drift) + dy * math.cos(drift))
            nx = m.x + dx * speed
            ny = m.y + dy * speed
            if self.is_floor_cell(int(nx), int(ny)) and not self.is_exit_cell(int(nx), int(ny)):
                m.x = nx
                m.y = ny
            alive.append(m)
        self.interior_creatures = alive

    def raycast_dungeon(self):
        w, h = self.screen.get_size()
        screen_dist = w // 2 / math.tan(HALF_FOV)
        scale = max(1, w // NUM_RAYS)
        cur_angle = self.interior_angle - HALF_FOV
        for ray in range(NUM_RAYS):
            sin_a = math.sin(cur_angle)
            cos_a = math.cos(cur_angle)
            depth = 0.01
            while depth < MAX_DEPTH:
                x = self.interior_px + depth * cos_a
                y = self.interior_py + depth * sin_a
                if int(x) < 0 or int(y) < 0 or int(x) >= self.map_w or int(y) >= self.map_h:
                    break
                c = self.cell_at(int(x), int(y))
                if c != '0':
                    depth_corr = depth * math.cos(self.interior_angle - cur_angle)
                    wall_h = screen_dist / (depth_corr + 0.0001)
                    tex = self.active_door_tex if c == '2' else self.active_panel_tex if ((int(x) * 73856093) ^ (int(y) * 19349663)) & 5 == 1 else self.active_wall_tex
                    tex_x = int((x + y) * 32) % 64
                    col = pygame.transform.scale(tex.subsurface(pygame.Rect(tex_x, 0, 1, 64)), (scale, max(1, int(wall_h))))
                    fog = min(255, int(depth_corr * 22))
                    col.fill((fog, fog, fog), special_flags=pygame.BLEND_RGB_SUB)
                    self.screen.blit(col, (ray * scale, h // 2 - wall_h // 2 + int(self.interior_pitch)))
                    break
                depth += 0.02
            cur_angle += DELTA_ANGLE

    def draw_floor_ceiling_casting(self):
        w, h = self.screen.get_size()
        scale = 3
        rw = max(1, w // scale)
        rh = max(1, h // scale)
        h2 = rh // 2
        floor_buf = pygame.Surface((rw, rh))
        ceil_buf = pygame.Surface((rw, rh))
        dir_x = math.cos(self.interior_angle)
        dir_y = math.sin(self.interior_angle)
        plane_x = -dir_y * math.tan(HALF_FOV)
        plane_y = dir_x * math.tan(HALF_FOV)
        pshift = int(self.interior_pitch / scale)
        pos_z = 0.55 * rh
        fpx = pygame.PixelArray(floor_buf)
        cpx = pygame.PixelArray(ceil_buf)
        tex_w = self.active_floor_tex.get_width()
        tex_h = self.active_floor_tex.get_height()
        y_start = max(h2 + max(-pshift, 1), 0)
        for y in range(y_start, rh):
            p = y - h2 - pshift
            if p == 0:
                continue
            row_dist = pos_z / p
            ray0x = dir_x - plane_x
            ray0y = dir_y - plane_y
            ray1x = dir_x + plane_x
            ray1y = dir_y + plane_y
            step_x = row_dist * (ray1x - ray0x) / rw
            step_y = row_dist * (ray1y - ray0y) / rw
            floor_x = self.interior_px + row_dist * ray0x
            floor_y = self.interior_py + row_dist * ray0y
            shade = max(0.0, min(1.0, 1.0 - (row_dist / MAX_DEPTH)))
            sh = int(34 * (1.0 - shade))
            for x in range(rw):
                tx = int(floor_x)
                ty = int(floor_y)
                fx = int((floor_x - tx) * tex_w) & (tex_w - 1)
                fy = int((floor_y - ty) * tex_h) & (tex_h - 1)
                col = self.active_floor_tex.get_at((fx, fy))
                cr, cg, cb = col[0], col[1], col[2]
                fpx[x, y] = ((int(clamp(cr - sh, 0, 255)) << 16) | (int(clamp(cg - sh, 0, 255)) << 8) | int(clamp(cb - sh, 0, 255)))
                floor_x += step_x
                floor_y += step_y
        y_end = min(h2 + min(-pshift, 0), h2)
        for y in range(0, max(0, y_end)):
            p = h2 - y + pshift
            if p == 0:
                continue
            row_dist = pos_z / p
            ray0x = dir_x - plane_x
            ray0y = dir_y - plane_y
            ray1x = dir_x + plane_x
            ray1y = dir_y + plane_y
            step_x = row_dist * (ray1x - ray0x) / rw
            step_y = row_dist * (ray1y - ray0y) / rw
            ceil_x = self.interior_px + row_dist * ray0x
            ceil_y = self.interior_py + row_dist * ray0y
            shade = max(0.0, min(1.0, 1.0 - (row_dist / MAX_DEPTH)))
            sh = int(46 * (1.0 - shade))
            for x in range(rw):
                tx = int(ceil_x)
                ty = int(ceil_y)
                cx = int((ceil_x - tx) * tex_w) & (tex_w - 1)
                cy = int((ceil_y - ty) * tex_h) & (tex_h - 1)
                col = self.active_ceil_tex.get_at((cx, cy))
                cr, cg, cb = col[0], col[1], col[2]
                cpx[x, y] = ((int(clamp(cr - sh, 0, 255)) << 16) | (int(clamp(cg - sh, 0, 255)) << 8) | int(clamp(cb - sh, 0, 255)))
                ceil_x += step_x
                ceil_y += step_y
        del fpx
        del cpx
        comb = pygame.Surface((rw, rh))
        comb.blit(ceil_buf, (0, 0))
        comb.blit(floor_buf, (0, 0))
        self.screen.blit(pygame.transform.smoothscale(comb, (w, h)), (0, 0))

    def draw_dungeon_billboard(self, sprite, ax, ay, seed, base_scale=1.0, y_offset=0, emissive=False):
        w, h = self.screen.get_size()
        screen_dist = w // 2 / math.tan(HALF_FOV)
        dx = ax - self.interior_px
        dy = ay - self.interior_py
        dist = math.hypot(dx, dy)
        if dist <= 0.6 or dist > MAX_DEPTH:
            return
        ang_to = math.atan2(dy, dx)
        rel = (ang_to - self.interior_angle + math.pi) % (2 * math.pi) - math.pi
        if not (-HALF_FOV < rel < HALF_FOV):
            return
        size = (screen_dist / dist) * base_scale
        size = max(12, min(size, 650))
        sp = pygame.transform.smoothscale(sprite, (int(size * 0.78), int(size)))
        jitter_x = int(math.sin(time.time() * 12.0 + seed) * 0.8)
        jitter_y = int(math.cos(time.time() * 10.0 + seed) * 0.6)
        x = w // 2 + math.tan(rel) * screen_dist - sp.get_width() // 2 + jitter_x
        y = h // 2 - sp.get_height() // 2 + int(self.interior_pitch) + jitter_y + y_offset
        sp = sp.copy()
        if not emissive:
            fog = min(255, int(dist * 42))
            sp.fill((fog, fog, fog), special_flags=pygame.BLEND_RGB_SUB)
        shadow = pygame.Surface((max(18, int(sp.get_width() * 0.46)), max(8, int(sp.get_width() * 0.14))), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 60), shadow.get_rect())
        self.screen.blit(shadow, (int(x + sp.get_width() * 0.28), int(y + sp.get_height() * 0.90)))
        if emissive:
            glow_size = max(sp.get_width(), sp.get_height()) + 90
            glow = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
            center = glow_size // 2
            pulse = 0.5 + 0.5 * math.sin(time.time() * 4.0 + seed)
            pygame.draw.circle(glow, (58, 246, 224, int(42 + pulse * 34)), (center, center), max(20, int(glow_size * 0.35)))
            self.screen.blit(glow, (int(x + sp.get_width() * 0.5 - center), int(y + sp.get_height() * 0.5 - center)), special_flags=pygame.BLEND_RGBA_ADD)
        self.screen.blit(sp, (x, y))

    def draw_dungeon_props(self):
        for p in sorted(self.interior_props, key=lambda item: -math.hypot(item.x - self.interior_px, item.y - self.interior_py)):
            scale = 1.15 if p.kind == 'arch' else 1.05 if p.kind == 'statue' else 1.0
            y_off = -8 if p.kind == 'arch' else -4 if p.kind == 'statue' else -2
            self.draw_dungeon_billboard(p.sprite, p.x, p.y, p.seed, scale, y_off)

    def draw_dungeon_creatures_render(self):
        for m in sorted(self.interior_creatures, key=lambda item: -math.hypot(item.x - self.interior_px, item.y - self.interior_py)):
            self.draw_dungeon_billboard(m.sprite, m.x, m.y, m.seed, 1.05, 0)
            m.seen = True

    def generate_dungeon_props(self):
        self.interior_props = []
        ctx, cty = int(self.interior_px), int(self.interior_py)
        spots = []
        taken = []
        for ty in range(1, self.map_h - 1):
            for tx in range(1, self.map_w - 1):
                if not self.is_floor_cell(tx, ty) or self.is_exit_cell(tx, ty):
                    continue
                dist = math.hypot(tx - ctx, ty - cty)
                if dist > 8.0:
                    continue
                clear = self.tile_clearance_score(tx, ty, 5)
                if clear < 2:
                    continue
                spots.append((tx, ty, clear, dist))
        spots.sort(key=lambda item: (-item[2], item[3]))
        rng = random.Random(self.seed ^ 0x9191)
        for tx, ty, _, _ in spots:
            if any(math.hypot(tx - ox, ty - oy) < 3.0 for ox, oy in taken):
                continue
            taken.append((tx, ty))
            sx, sy = tx + 0.5, ty + 0.5
            if math.hypot(sx - self.interior_px, sy - self.interior_py) < 2.0:
                continue
            roll = rng.random()
            seed = rng.randint(0, 999999)
            if roll < 0.32:
                self.interior_props.append(DungeonProp(sx, sy, 'column', seed, self.make_column_sprite(seed)))
            elif roll < 0.62:
                self.interior_props.append(DungeonProp(sx, sy, 'statue', seed, self.make_statue_sprite(seed)))
            else:
                self.interior_props.append(DungeonProp(sx, sy, 'arch', seed, self.make_arch_sprite(seed)))
            if len(self.interior_props) >= 12:
                break

    def carve_room(self, grid, x0, y0, w, h, door_chance, rng):
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                on_edge = x == x0 or y == y0 or x == x0 + w - 1 or y == y0 + h - 1
                grid[y][x] = '1' if on_edge else '0'
        if rng.random() < door_chance:
            side = rng.choice(['n', 's', 'e', 'w'])
            if side == 'n':
                x = rng.randrange(x0 + 2, x0 + w - 2); y = y0
            elif side == 's':
                x = rng.randrange(x0 + 2, x0 + w - 2); y = y0 + h - 1
            elif side == 'e':
                x = x0 + w - 1; y = rng.randrange(y0 + 2, y0 + h - 2)
            else:
                x = x0; y = rng.randrange(y0 + 2, y0 + h - 2)
            grid[y][x] = '2'

    def generate_dungeon_map(self, seed=1, w=37, h=25):
        rng = random.Random(seed)
        w = max(27, w | 1)
        h = max(19, h | 1)
        grid = [['1'] * w for _ in range(h)]
        rooms = []
        for _ in range(18):
            rw = (rng.randrange(5, 11) | 1)
            rh = (rng.randrange(5, 9) | 1)
            rx = rng.randrange(2, w - rw - 2)
            ry = rng.randrange(2, h - rh - 2)
            rect = pygame.Rect(rx, ry, rw, rh)
            if any(rect.inflate(2, 2).colliderect(other) for other in rooms):
                continue
            rooms.append(rect)
            for y in range(ry, ry + rh):
                for x in range(rx, rx + rw):
                    grid[y][x] = '0'
        rooms.sort(key=lambda r: (r.centerx, r.centery))
        if not rooms:
            return self.generate_castle_map(seed, w, h)
        for i in range(1, len(rooms)):
            a = rooms[i - 1].center
            b = rooms[i].center
            if rng.random() < 0.5:
                for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                    grid[a[1]][x] = '0'
                for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                    grid[y][b[0]] = '0'
            else:
                for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                    grid[y][a[0]] = '0'
                for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                    grid[b[1]][x] = '0'
        for rect in rooms:
            for x in range(rect.left - 1, rect.right + 1):
                grid[rect.top - 1][x] = '1'
                grid[rect.bottom][x] = '1'
            for y in range(rect.top - 1, rect.bottom + 1):
                grid[y][rect.left - 1] = '1'
                grid[y][rect.right] = '1'
        start = rooms[0].center
        end = rooms[-1].center
        grid[start[1]][start[0]] = '0'
        grid[end[1]][end[0]] = '2'
        return [''.join(row) for row in grid]

    def generate_castle_map(self, seed=2, w=41, h=27):
        rng = random.Random(seed)
        w = max(31, w | 1)
        h = max(21, h | 1)
        grid = [['0'] * w for _ in range(h)]
        for x in range(w):
            grid[0][x] = grid[h - 1][x] = '1'
        for y in range(h):
            grid[y][0] = grid[y][w - 1] = '1'
        towers = [(3, 3), (w - 4, 3), (3, h - 4), (w - 4, h - 4)]
        for tx, ty in towers:
            for y in range(ty - 2, ty + 3):
                for x in range(tx - 2, tx + 3):
                    if 0 <= x < w and 0 <= y < h and (x - tx) ** 2 + (y - ty) ** 2 <= 6:
                        grid[y][x] = '1'
        inset = 6
        for x in range(inset, w - inset):
            grid[inset][x] = grid[h - inset - 1][x] = '1'
        for y in range(inset, h - inset):
            grid[y][inset] = grid[y][w - inset - 1] = '1'
        grid[h // 2][0] = grid[h // 2][inset] = grid[h // 2][w - inset - 1] = grid[h // 2][w - 1] = '2'
        kx, ky = w // 2 - 6, h // 2 - 4
        kw, kh = 13, 9
        self.carve_room(grid, kx, ky, kw, kh, 0.0, rng)
        grid[ky + kh // 2][kx] = '2'
        grid[ky + kh // 2][kx + kw - 1] = '2'
        for _ in range(12):
            x = rng.randrange(inset + 2, w - inset - 2)
            y = rng.randrange(inset + 2, h - inset - 2)
            ln = rng.randrange(4, 10)
            if rng.random() < 0.5:
                for i in range(ln):
                    if inset + 1 <= x + i < w - inset - 1:
                        grid[y][x + i] = '1'
            else:
                for i in range(ln):
                    if inset + 1 <= y + i < h - inset - 1:
                        grid[y + i][x] = '1'
        for y in range(h // 2 - 2, h // 2 + 3):
            for x in range(2, 10):
                if 0 <= x < w and 0 <= y < h:
                    grid[y][x] = '0'
        grid[h // 2][1] = '0'
        return [''.join(row) for row in grid]

    def generate_catacomb_map(self, seed=3, w=41, h=27):
        rng = random.Random(seed)
        w = max(31, w | 1)
        h = max(21, h | 1)
        grid = [['1'] * w for _ in range(h)]
        cx, cy = 2, h // 2
        for _ in range(1800):
            grid[cy][cx] = '0'
            if rng.random() < 0.18:
                for oy in range(-1, 2):
                    for ox in range(-1, 2):
                        xx = clamp(cx + ox, 1, w - 2)
                        yy = clamp(cy + oy, 1, h - 2)
                        grid[int(yy)][int(xx)] = '0'
            dx, dy = rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
            nx = int(clamp(cx + dx, 1, w - 2))
            ny = int(clamp(cy + dy, 1, h - 2))
            cx, cy = nx, ny
        for x in range(w):
            grid[0][x] = grid[h - 1][x] = '1'
        for y in range(h):
            grid[y][0] = grid[y][w - 1] = '1'
        grid[h // 2][1] = '0'
        grid[h // 2][w - 2] = '2'
        return [''.join(row) for row in grid]

    # -------------------- art builders --------------------
    def tint_texture(self, surf, tint, glow=0):
        out = surf.copy()
        lay = pygame.Surface(out.get_size())
        lay.fill(tint)
        out.blit(lay, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        if glow:
            g = pygame.Surface(out.get_size())
            g.fill((glow, glow, glow))
            out.blit(g, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        return out

    def make_stone_texture(self, seed=7):
        rng = random.Random(seed)
        surf = pygame.Surface((64, 64))
        base = rng.randint(78, 102)
        for y in range(64):
            for x in range(64):
                n = rng.randint(-20, 20)
                c = int(clamp(base + n, 26, 150))
                surf.set_at((x, y), (c, max(0, c - 6), max(0, c - 14)))
        for _ in range(160):
            x = rng.randint(0, 63); y = rng.randint(0, 63)
            ww = rng.randint(3, 12); hh = rng.randint(1, 3)
            shade = rng.randint(10, 26)
            for yy in range(y, min(64, y + hh)):
                for xx in range(x, min(64, x + ww)):
                    r, g, b, _ = surf.get_at((xx, yy))
                    surf.set_at((xx, yy), (max(0, r - shade), max(0, g - shade), max(0, b - shade)))
        return surf

    def make_pattern_texture(self, seed, base, line):
        rng = random.Random(seed)
        size = 256
        s = pygame.Surface((size, size))
        s.fill(base)
        step = 16
        for y in range(0, size, step):
            for x in range(0, size, step):
                cx, cy = x + step // 2, y + step // 2
                pygame.draw.polygon(s, line, [(cx, y), (x + step, cy), (cx, y + step), (x, cy)], 1)
        for y in range(step // 2, size, step):
            for x in range(step // 2, size, step):
                if rng.random() < 0.35:
                    pygame.draw.circle(s, (min(255, base[0] + 34), min(255, base[1] + 34), min(255, base[2] + 34)), (x, y), 2)
        return s

    def make_door_texture(self, seed=77):
        rng = random.Random(seed)
        s = self.make_stone_texture(seed)
        pygame.draw.rect(s, (12, 10, 18), (0, 0, 63, 63), 3)
        for x in range(10, 54, 8):
            pygame.draw.line(s, (24, 22, 20), (x, 6), (x, 58), 2)
        pygame.draw.rect(s, (144, 108, 48), (40, 30, 16, 6), 0)
        for _ in range(120):
            if rng.random() < 0.3:
                pygame.draw.circle(s, (0, 0, 0), (rng.randrange(64), rng.randrange(64)), rng.randint(1, 2))
        return s

    def make_tree_sprite(self, seed, hue, terrain):
        rng = random.Random(seed)
        w, h = 72, 144
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        if terrain == 'desert':
            trunk = (122, 98, 70); crown = (198, 168, 116)
        elif terrain == 'ice':
            trunk = (132, 148, 164); crown = (206, 232, 244)
        elif terrain == 'volcanic':
            trunk = (78, 54, 46); crown = (166, 86, 54)
        elif terrain == 'fungal':
            trunk = (84, 54, 96); crown = (218, 96, 190)
        elif terrain == 'rust':
            trunk = (82, 62, 54); crown = (186, 104, 62)
        elif terrain == 'abyss':
            trunk = (28, 48, 66); crown = (58, 222, 220)
        elif terrain == 'storm':
            trunk = (68, 74, 88); crown = (188, 166, 106)
        elif terrain == 'roseglass':
            trunk = (86, 44, 74); crown = (238, 112, 188)
        elif terrain == 'salt':
            trunk = (168, 166, 178); crown = (238, 236, 246)
        else:
            trunk = hsv_to_rgb255((hue + 0.08) % 1.0, 0.34, 0.48)
            crown = hsv_to_rgb255(hue, 0.60, 0.90)
        cx = w // 2 + rng.randint(-4, 4)
        base_y = h - 10
        bend = rng.uniform(-0.25, 0.25)
        for i in range(14):
            t = i / 13
            dx = int(math.sin(t * 4.5 + bend) * (7 + rng.randint(0, 3)))
            thick = int(14 - t * 9)
            y0 = base_y - int(t * 100)
            pygame.draw.line(s, trunk, (cx + dx, y0), (cx + dx + rng.randint(-2, 2), y0 - 11), thick)
        if terrain == 'desert':
            for off in (-22, 22):
                pygame.draw.line(s, crown, (cx, 42), (cx + off, 28), 6)
                pygame.draw.line(s, crown, (cx + off, 28), (cx + off * 1.2, 48), 5)
        else:
            for _ in range(128):
                x = cx + rng.randint(-26, 26)
                y = 22 + rng.randint(-8, 42)
                pygame.draw.circle(s, crown, (x, y), rng.randint(1, 4))
        return s

    def make_plant_sprite(self, seed, hue, terrain):
        rng = random.Random(seed)
        w, h = 36, 36
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        if terrain == 'desert':
            base = (188, 162, 96); hi = (214, 196, 128)
        elif terrain == 'ice':
            base = (188, 218, 236); hi = (232, 246, 255)
        elif terrain == 'volcanic':
            base = (176, 94, 64); hi = (232, 144, 88)
        elif terrain == 'fungal':
            base = (202, 70, 170); hi = (98, 244, 202)
        elif terrain == 'rust':
            base = (172, 82, 42); hi = (238, 154, 78)
        elif terrain == 'salt':
            base = (218, 214, 232); hi = (255, 250, 255)
        elif terrain == 'abyss':
            base = (38, 160, 178); hi = (104, 248, 226)
        elif terrain == 'storm':
            base = (118, 126, 146); hi = (226, 196, 110)
        elif terrain == 'roseglass':
            base = (212, 74, 158); hi = (255, 166, 224)
        else:
            base = hsv_to_rgb255(hue, 0.72, 0.92)
            hi = hsv_to_rgb255((hue + 0.05) % 1.0, 0.50, 1.0)
        for _ in range(30):
            x = rng.randint(8, 26); y = rng.randint(12, 30)
            if rng.random() < 0.60:
                pygame.draw.circle(s, base, (x, y), rng.randint(1, 3))
            else:
                pygame.draw.polygon(s, hi, [(x, y), (x + rng.randint(-1, 2), y - rng.randint(4, 8)), (x + rng.randint(1, 4), y)])
        return s

    def make_fragment_sprite(self, seed: int) -> pygame.Surface:
        """Procedural Matrix Fragment used by the real ruin renderer."""
        rng = random.Random(seed)
        w, h = 128, 180
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        # Soft aura kept inside the sprite so billboard scaling remains cheap.
        for radius in range(58, 8, -5):
            alpha = int(8 + (58 - radius) * 0.7)
            pygame.draw.circle(surf, (76, 246, 232, alpha), (cx, cy), radius)
        outer = [(cx, 18), (cx + 34, cy - 10), (cx + 20, h - 24), (cx, h - 8), (cx - 20, h - 24), (cx - 34, cy - 10)]
        inner = [(cx, 38), (cx + 20, cy - 5), (cx + 10, h - 40), (cx, h - 24), (cx - 10, h - 40), (cx - 20, cy - 5)]
        pygame.draw.polygon(surf, (22, 80, 96, 248), outer)
        pygame.draw.polygon(surf, (94, 250, 236, 255), outer, 4)
        pygame.draw.polygon(surf, (190, 255, 246, 245), inner)
        pygame.draw.line(surf, (255, 255, 255, 230), (cx - 8, 50), (cx + 6, h - 46), 4)
        for _ in range(12):
            ang = rng.random() * math.tau
            rr = rng.uniform(22, 54)
            x = int(cx + math.cos(ang) * rr)
            y = int(cy + math.sin(ang) * rr)
            pygame.draw.circle(surf, (170, 255, 244, rng.randint(90, 190)), (x, y), rng.randint(1, 3))
        return surf

    def make_ship_beacon(self, seed):
        rng = random.Random(seed)
        ship_path = ROOT / 'assets' / 'ship' / 'landed' / 'ship.png'
        palette_core = (108, 255, 244)
        palette_accent = (255, 84, 188)
        if ship_path.is_file():
            try:
                src = pygame.image.load(str(ship_path)).convert_alpha()
                bounds = src.get_bounding_rect(min_alpha=4)
                if bounds.width > 0 and bounds.height > 0:
                    src = src.subsurface(bounds).copy()
                scale = min(112 / max(1, src.get_width()), 152 / max(1, src.get_height()))
                scaled = pygame.transform.smoothscale(
                    src,
                    (max(4, int(src.get_width() * scale)), max(4, int(src.get_height() * scale))),
                )
                canvas = pygame.Surface((132, 182), pygame.SRCALPHA)
                x = (canvas.get_width() - scaled.get_width()) // 2
                y = canvas.get_height() - scaled.get_height() - 10
                shadow = pygame.Surface((scaled.get_width(), scaled.get_height()), pygame.SRCALPHA)
                shadow.fill((0, 0, 0, 0))
                pygame.draw.ellipse(
                    canvas,
                    (0, 0, 0, 72),
                    (x + 8, y + scaled.get_height() - 16, scaled.get_width() - 16, 18),
                )
                mask = pygame.mask.from_surface(scaled)
                cyan_glow = mask.to_surface(setcolor=(*palette_core, 48), unsetcolor=(0, 0, 0, 0))
                magenta_glow = mask.to_surface(setcolor=(*palette_accent, 32), unsetcolor=(0, 0, 0, 0))
                for ox, oy in ((-4, 0), (4, 0), (0, -4), (0, 4)):
                    canvas.blit(cyan_glow, (x + ox, y + oy))
                for ox, oy in ((-6, 0), (6, 0), (0, -6), (0, 6)):
                    canvas.blit(magenta_glow, (x + ox, y + oy))
                tint = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
                tint.fill((62, 44, 102, 58))
                shaded = scaled.copy()
                shaded.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
                canvas.blit(shaded, (x, y))

                fracture_paths = [
                    [(0.50, 0.07), (0.42, 0.28), (0.52, 0.56), (0.46, 0.92)],
                    [(0.29, 0.22), (0.36, 0.44), (0.30, 0.74)],
                    [(0.71, 0.18), (0.64, 0.42), (0.70, 0.76)],
                    [(0.18, 0.58), (0.32, 0.51), (0.42, 0.63)],
                    [(0.82, 0.56), (0.68, 0.51), (0.57, 0.65)],
                ]
                for idx, path in enumerate(fracture_paths):
                    pts = [
                        (x + int(px * scaled.get_width()), y + int(py * scaled.get_height()))
                        for (px, py) in path
                    ]
                    glow_col = palette_core if idx % 2 == 0 else palette_accent
                    for width, alpha in ((4, 36), (2, 68)):
                        c = (*glow_col, alpha)
                        pygame.draw.lines(canvas, c, False, pts, width)
                    pygame.draw.lines(canvas, (255, 255, 255, 120), False, pts, 1)

                core_pos = (x + scaled.get_width() // 2, y + int(scaled.get_height() * 0.52))
                for rad, col in ((22, (*palette_core, 24)), (14, (*palette_accent, 42)), (8, (*palette_core, 78))):
                    pygame.draw.circle(canvas, col, core_pos, rad)
                pygame.draw.circle(canvas, palette_core, core_pos, 5)
                pygame.draw.circle(canvas, (255, 255, 255), core_pos, 2)
                return canvas
            except Exception:
                _log(f'WARN: ship art failed to load: {ship_path}\n{traceback.format_exc()}')

        # Fallback: a purely procedural Fractured Dimension beacon silhouette.
        w, h = 104, 172
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        shadow = pygame.Rect(18, 144, 68, 18)
        pygame.draw.ellipse(s, (0, 0, 0, 70), shadow)
        hull = [(52, 16), (76, 46), (84, 126), (52, 154), (20, 126), (28, 46)]
        inner = [(52, 26), (68, 54), (74, 118), (52, 142), (30, 118), (36, 54)]
        fins_l = [(20, 40), (10, 102), (18, 130), (34, 84)]
        fins_r = [(84, 40), (94, 102), (86, 130), (70, 84)]
        pygame.draw.polygon(s, (36, 28, 74), hull)
        pygame.draw.polygon(s, (64, 46, 110), inner)
        pygame.draw.polygon(s, (30, 22, 64), fins_l)
        pygame.draw.polygon(s, (30, 22, 64), fins_r)
        for poly in (hull, inner, fins_l, fins_r):
            pygame.draw.polygon(s, palette_core if poly is inner else (168, 132, 255), poly, 2)
        fractures = [((52, 24), (44, 58), (56, 96), (48, 136)), ((34, 68), (42, 92), (34, 120)), ((70, 68), (62, 92), (70, 120))]
        for path in fractures:
            pygame.draw.lines(s, (*palette_accent, 60), False, path, 3)
            pygame.draw.lines(s, (*palette_core, 96), False, path, 1)
        for i in range(5):
            a = 92 - i * 12
            pygame.draw.circle(s, (*palette_core, a), (52, 84), 8 + i * 8, 2)
        pygame.draw.circle(s, (255, 255, 255), (52, 84), 4)
        return s

    def make_relic_structure_sprite(self, seed: int, art_id: int, fallback_kind: str) -> pygame.Surface:
        path = ROOT / 'assets' / 'holograms' / 'former_civ' / f'{art_id}.png'
        try:
            if not path.is_file():
                return self.make_structure_sprite(seed, fallback_kind)
            src = pygame.image.load(str(path)).convert_alpha()
            bounds = src.get_bounding_rect(min_alpha=2)
            if bounds.width > 0 and bounds.height > 0:
                src = src.subsurface(bounds).copy()
            scale = min(188 / max(1, src.get_width()), 220 / max(1, src.get_height()))
            scaled = pygame.transform.smoothscale(src, (max(2, int(src.get_width() * scale)), max(2, int(src.get_height() * scale))))
            canvas = pygame.Surface((220, 250), pygame.SRCALPHA)
            x = (canvas.get_width() - scaled.get_width()) // 2
            y = canvas.get_height() - scaled.get_height() - 8
            glow = pygame.mask.from_surface(scaled).to_surface(setcolor=(*hsv_to_rgb255(self.biome['accent_hue'], 0.72, 1.0), 62), unsetcolor=(0, 0, 0, 0))
            for ox, oy in ((-4, 0), (4, 0), (0, -4), (0, 4)):
                canvas.blit(glow, (x + ox, y + oy))
            canvas.blit(scaled, (x, y))
            return canvas
        except Exception:
            _log(f'WARN: relic structure failed to load: {path}\n{traceback.format_exc()}')
            return self.make_structure_sprite(seed, fallback_kind)

    def make_structure_sprite(self, seed, kind):
        rng = random.Random(seed)
        w, h = 180, 220
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        stone = (104, 90, 74)
        gold = (214, 176, 104)
        crystal = (120, 210, 244)
        shadow = (28, 20, 16)
        if kind == 'ziggurat':
            for i in range(5):
                ww = 140 - i * 22
                rect = pygame.Rect((w - ww) // 2, 150 - i * 24, ww, 22)
                pygame.draw.rect(s, stone, rect, border_radius=4)
                pygame.draw.rect(s, gold, rect, 2, border_radius=4)
        elif kind == 'observatory':
            pygame.draw.rect(s, stone, (48, 78, 84, 104), border_radius=10)
            pygame.draw.rect(s, gold, (48, 78, 84, 104), 2, border_radius=10)
            pygame.draw.circle(s, (84, 104, 130), (90, 72), 38)
            pygame.draw.circle(s, crystal, (90, 72), 26, 2)
        elif kind == 'bastion':
            pygame.draw.rect(s, stone, (34, 86, 112, 100), border_radius=12)
            pygame.draw.rect(s, gold, (34, 86, 112, 100), 2, border_radius=12)
            for tx in (42, 118):
                pygame.draw.rect(s, stone, (tx, 42, 20, 58), border_radius=6)
        elif kind == 'spire':
            pygame.draw.polygon(s, stone, [(90, 18), (122, 112), (108, 188), (72, 188), (58, 112)])
            pygame.draw.polygon(s, gold, [(90, 18), (122, 112), (108, 188), (72, 188), (58, 112)], 2)
            for i in range(4):
                pygame.draw.circle(s, crystal, (90, 58 + i * 28), 6, 2)
        elif kind == 'sepulcher':
            pygame.draw.rect(s, stone, (30, 92, 120, 86), border_radius=16)
            pygame.draw.rect(s, gold, (30, 92, 120, 86), 2, border_radius=16)
            pygame.draw.ellipse(s, shadow, (56, 112, 68, 42))
        else:  # labyrinth
            pygame.draw.rect(s, stone, (34, 90, 112, 92), border_radius=14)
            for i in range(4):
                pygame.draw.rect(s, gold, (44 + i * 22, 100, 12, 72), 2, border_radius=4)
            pygame.draw.circle(s, crystal, (90, 68), 18, 2)
        return s

    def make_column_sprite(self, seed):
        w, h = 92, 170
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        body = pygame.Rect(int(w * 0.30), int(h * 0.18), int(w * 0.40), int(h * 0.70))
        pygame.draw.rect(s, (86, 84, 96), body, border_radius=6)
        for gx in range(body.left + 5, body.right - 5, 6):
            pygame.draw.line(s, (66, 64, 76), (gx, body.top + 4), (gx, body.bottom - 4), 1)
        cap = pygame.Rect(int(w * 0.22), int(h * 0.10), int(w * 0.56), int(h * 0.10))
        base = pygame.Rect(int(w * 0.22), int(h * 0.88), int(w * 0.56), int(h * 0.10))
        pygame.draw.rect(s, (74, 72, 84), cap, border_radius=8)
        pygame.draw.rect(s, (74, 72, 84), base, border_radius=8)
        pygame.draw.rect(s, (124, 104, 40), cap.inflate(-10, -10), 2, border_radius=7)
        pygame.draw.rect(s, (124, 104, 40), base.inflate(-10, -10), 2, border_radius=7)
        return s

    def make_statue_sprite(self, seed):
        w, h = 110, 190
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pl = pygame.Rect(int(w * 0.18), int(h * 0.80), int(w * 0.64), int(h * 0.18))
        pygame.draw.rect(s, (70, 68, 78), pl, border_radius=8)
        pygame.draw.rect(s, (124, 104, 40), pl.inflate(-12, -10), 2, border_radius=7)
        col = (62, 60, 70)
        head = (int(w * 0.50), int(h * 0.26))
        pygame.draw.circle(s, col, head, 16)
        pygame.draw.ellipse(s, col, (int(w * 0.38), int(h * 0.32), int(w * 0.24), int(h * 0.34)))
        pygame.draw.ellipse(s, col, (int(w * 0.30), int(h * 0.44), int(w * 0.16), int(h * 0.22)))
        pygame.draw.ellipse(s, col, (int(w * 0.54), int(h * 0.44), int(w * 0.16), int(h * 0.22)))
        pygame.draw.ellipse(s, col, (int(w * 0.40), int(h * 0.64), int(w * 0.12), int(h * 0.18)))
        pygame.draw.ellipse(s, col, (int(w * 0.50), int(h * 0.64), int(w * 0.12), int(h * 0.18)))
        pygame.draw.ellipse(s, (0, 0, 0), (head[0] - 10, head[1] - 6, 20, 12))
        return s

    def make_arch_sprite(self, seed):
        rng = random.Random(seed)
        w, h = 140, 170
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        frame = pygame.Rect(int(w * 0.10), int(h * 0.20), int(w * 0.80), int(h * 0.70))
        pygame.draw.rect(s, (78, 74, 90), frame, border_radius=12)
        inner = frame.inflate(-28, -26)
        pygame.draw.rect(s, (0, 0, 0, 0), inner, border_radius=16)
        for _ in range(60):
            x = rng.randint(frame.left + 6, frame.right - 6)
            y = rng.randint(frame.top + 6, frame.bottom - 6)
            if rng.random() < 0.35:
                s.set_at((x, y), (124, 104, 40, rng.randint(60, 160)))
        return s

    def make_nightmare_sprite(self, seed=1337, w=112, h=160):
        rng = random.Random(seed)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for _ in range(46):
            cx = int(w * 0.5 + rng.uniform(-10, 10))
            cy = int(h * 0.45 + rng.uniform(-18, 18))
            rx = int(rng.uniform(12, 36))
            ry = int(rng.uniform(16, 44))
            shade = rng.randint(10, 42)
            pygame.draw.ellipse(s, (shade, shade, shade, 255), (cx - rx, cy - ry, rx * 2, ry * 2))
        limb = (18, 18, 18, 255)
        for _ in range(9):
            x0 = int(w * 0.5 + rng.uniform(-18, 18))
            y0 = int(h * 0.55 + rng.uniform(-18, 18))
            x1 = int(x0 + rng.uniform(-60, 60))
            y1 = int(y0 + rng.uniform(30, 90))
            pygame.draw.line(s, limb, (x0, y0), (x1, y1), rng.randint(4, 9))
        pygame.draw.ellipse(s, (0, 0, 0, 255), (int(w * 0.32), int(h * 0.16), int(w * 0.36), int(h * 0.22)))
        for _ in range(6):
            ex = int(w * 0.42 + rng.uniform(-10, 10))
            ey = int(h * 0.23 + rng.uniform(-8, 8))
            pygame.draw.ellipse(s, (210, 210, 210, 255), (ex, ey, rng.randint(4, 10), rng.randint(3, 8)))
        return s


_SURFACES: dict[tuple[int, Optional[str]], SurfaceView] = {}
_PLANET_BACKDROPS: dict[int, PlanetBackdrop] = {}


def preload_surface(seed: int, screen: pygame.Surface, ship=None, forced_biome: Optional[str] = None) -> None:
    get_surface(seed, screen, ship, forced_biome=forced_biome)


def enter_surface(seed: int, screen: pygame.Surface, ship=None, forced_biome: Optional[str] = None) -> None:
    surf = get_surface(seed, screen, ship, forced_biome=forced_biome)
    surf.mode = 'surface'
    surf.set_notification(f'Planetfall on {surf.planet_name}', 2.2)


def get_surface(seed: int, screen: pygame.Surface, ship=None, forced_biome: Optional[str] = None) -> SurfaceView:
    seed = int(seed)
    forced = forced_biome if forced_biome in BIOME_BY_TERRAIN else None
    key = (seed, forced)
    surf = _SURFACES.get(key)
    if surf is None:
        surf = SurfaceView(seed, screen, ship, forced_biome=forced)
        _SURFACES[key] = surf
        if len(_SURFACES) > 8:
            # keep cache bounded
            for k in list(_SURFACES.keys())[:-8]:
                _SURFACES.pop(k, None)
    surf.set_screen(screen)
    surf.ship = ship
    for other_key, other in _SURFACES.items():
        if other_key != key:
            other.topdown_map = None
            other.topdown_map_size = (0, 0)
            other.topdown_sprite_cache.clear()
            other._terrain_chunk_cache.clear()
            other._procedural_object_cache.clear()
    return surf


def leave_surface() -> None:
    # Keep cached surfaces so the current planet can persist if revisited.
    return None


def get_planet_world(seed: int):
    seed = int(seed)
    pb = _PLANET_BACKDROPS.get(seed)
    if pb is None:
        pb = PlanetBackdrop(seed)
        _PLANET_BACKDROPS[seed] = pb
    return pb
