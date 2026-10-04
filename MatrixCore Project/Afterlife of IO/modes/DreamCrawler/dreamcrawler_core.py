"""Dream Crawler engine (Pass 12 — hostable core).

This module has no import-time side effects: it never opens a window, starts
audio or writes into the install folder when imported.  That lets two callers
share one engine:

* ``main.py`` — the standalone Dream Crawler launcher (``run_standalone``).
* Entropy — archive-ruin dives that run inside Entropy's live window and hand
  the result back (``run_expedition``).

The protected Pass 11 loop is unchanged in standalone play:
explore -> scavenge -> evade or fight the crawler -> find the stairs -> descend.
"""
from __future__ import annotations

import datetime
import math
import os
import random
import sys
import time
import traceback
from heapq import heappop, heappush
from pathlib import Path

import pygame

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_LABEL = "Pass 12 — Hostable Core & Ruin Dives"


def _path(*parts):
    return os.path.join(BASE_DIR, *parts)


def _user_data_dir() -> Path:
    """Writable per-user folder; the install folder may be read-only (Steam)."""
    candidates: list[Path] = []
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / "GLITCHED MATRIX" / "DreamCrawler")
    candidates.append(Path.home() / ".glitched_matrix" / "DreamCrawler")
    candidates.append(Path(BASE_DIR))
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    return Path(BASE_DIR)


def crash_report(exc: BaseException) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = _user_data_dir() / "logs"
    fn = folder / f"crash_{ts}.txt"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with open(fn, "w", encoding="utf-8") as f:
            f.write("Dream Crawler crash report\n")
            f.write(f"Build: {BUILD_LABEL}\n")
            f.write(f"Timestamp: {datetime.datetime.now().isoformat()}\n\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:
        pass
    return str(fn)


# ---------------------------------------------------------------------------
# Audio (lazy).  A host that already owns the mixer keeps its settings.
# ---------------------------------------------------------------------------
AUDIO_OK = False
AUDIO_MUTED = False
SFX: dict = {}


def _load_any(path_no_ext: str):
    if not AUDIO_OK:
        return None
    for ext in (".wav", ".ogg", ".mp3"):
        p = path_no_ext + ext
        if os.path.isfile(p):
            try:
                return pygame.mixer.Sound(p)
            except Exception:
                return None
    return None


def init_audio(own_mixer: bool) -> None:
    """Load SFX. ``own_mixer`` is True only for the standalone launcher."""
    global AUDIO_OK
    try:
        if pygame.mixer.get_init() is None:
            if not own_mixer:
                AUDIO_OK = False
                return
            pygame.mixer.init(44100, -16, 2, 512)
        if own_mixer:
            pygame.mixer.set_num_channels(16)
        AUDIO_OK = True
    except Exception:
        AUDIO_OK = False
    for name in ("spawn", "exit", "step", "caught", "hit", "loot", "alert"):
        SFX[name] = _load_any(_path("assets", "sfx", name))


def play_sfx(name, vol=0.6):
    if AUDIO_MUTED:
        return
    s = SFX.get(name)
    if not s:
        return
    try:
        s.set_volume(max(0.0, min(1.0, float(vol))))
        s.play()
    except Exception:
        pass


def start_music():
    if not AUDIO_OK:
        return
    md = _path("assets", "music")
    try:
        files = [os.path.join(md, f) for f in os.listdir(md) if f.lower().endswith((".mp3", ".ogg", ".wav"))]
        if not files:
            return
        files.sort()
        pygame.mixer.music.load(files[0])
        pygame.mixer.music.set_volume(0.42)
        pygame.mixer.music.play(-1)
    except Exception:
        pass


def init_fonts() -> None:
    global FONT, BIG, SMALL
    if not pygame.font.get_init():
        pygame.font.init()
    FONT = pygame.font.SysFont("consolas", 18)
    BIG = pygame.font.SysFont("consolas", 28, bold=True)
    SMALL = pygame.font.SysFont("consolas", 15)


# Standalone launches are supported by default.  MatrixOS can opt into a strict
# launch-only contract with DREAMCRAWLER_REQUIRE_MATRIX=1.
FORCE_MATRIX_LAUNCH = os.getenv("DREAMCRAWLER_REQUIRE_MATRIX") == "1"
MATRIX_LAUNCH_OK = os.getenv("PYGAME_OS_LAUNCHER") == "1" or os.getenv("DREAMCRAWLER_ALLOW_STANDALONE") == "1"

# Fixed 16:9 logical frame; presentation letterboxes it into any window.
W, H = 1280, 720
SMALL = None

# Ruin-dive (Entropy expedition) constants.
DIVE_DEFAULT_DEPTH = 2
DIVE_COLLAPSE_RATE = 0.25
FRAGMENT_COLOR = (88, 255, 238)
ASCENT_COLOR = (255, 214, 112)


TILE = 20
GRID_W = 78
GRID_H = 50

WALL = 1
FLOOR = 0
STAIRS = 3

PLAYER_R = 7.0
VISION_RADIUS_TILES = 9

FONT = None
BIG = None


def clamp(x, a, b):
    return a if x < a else b if x > b else x


def in_bounds(x, y):
    return 0 <= x < GRID_W and 0 <= y < GRID_H


def carve_room(g, x0, y0, rw, rh):
    for y in range(y0, y0 + rh):
        for x in range(x0, x0 + rw):
            if in_bounds(x, y):
                g[y][x] = FLOOR


def carve_hall(g, x1, y1, x2, y2, width=2):
    sx = 1 if x2 >= x1 else -1
    for xx in range(x1, x2 + sx, sx):
        for dy in range(-width // 2, width // 2 + 1):
            if in_bounds(xx, y1 + dy):
                g[y1 + dy][xx] = FLOOR
    sy = 1 if y2 >= y1 else -1
    for yy in range(y1, y2 + sy, sy):
        for dx in range(-width // 2, width // 2 + 1):
            if in_bounds(x2 + dx, yy):
                g[yy][x2 + dx] = FLOOR


def generate_grid(seed=None):
    rng = random.Random(seed)
    g = [[WALL for _ in range(GRID_W)] for _ in range(GRID_H)]
    rooms = []

    for _ in range(rng.randint(16, 24)):
        rw = rng.randint(8, 15)
        rh = rng.randint(7, 12)
        x0 = rng.randint(1, GRID_W - rw - 2)
        y0 = rng.randint(1, GRID_H - rh - 2)
        carve_room(g, x0, y0, rw, rh)
        rooms.append((x0 + rw // 2, y0 + rh // 2, x0, y0, rw, rh))

    rooms.sort(key=lambda r: r[0] + r[1])
    for i in range(1, len(rooms)):
        x1, y1 = rooms[i - 1][0], rooms[i - 1][1]
        x2, y2 = rooms[i][0], rooms[i][1]
        carve_hall(g, x1, y1, x2, y2, width=2 if rng.random() < 0.9 else 1)

    for _ in range(rng.randint(48, 78)):
        cx = rng.randint(2, GRID_W - 3)
        cy = rng.randint(2, GRID_H - 3)
        r = rng.randint(1, 4)
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if in_bounds(xx, yy) and (xx - cx) * (xx - cx) + (yy - cy) * (yy - cy) <= r * r:
                    if rng.random() < 0.72:
                        g[yy][xx] = FLOOR

    sx, sy = rooms[0][0], rooms[0][1]
    ex, ey = rooms[-1][0], rooms[-1][1]
    g[ey][ex] = STAIRS
    return g, (sx, sy), (ex, ey)


def is_wall(g, tx, ty):
    if not in_bounds(tx, ty):
        return True
    return g[ty][tx] == WALL


def resolve_circle(px, py, g, radius=PLAYER_R):
    tx = int(px // TILE)
    ty = int(py // TILE)
    for yy in range(ty - 1, ty + 2):
        for xx in range(tx - 1, tx + 2):
            if is_wall(g, xx, yy):
                rx, ry = xx * TILE, yy * TILE
                cx = clamp(px, rx, rx + TILE)
                cy = clamp(py, ry, ry + TILE)
                dx = px - cx
                dy = py - cy
                dist2 = dx * dx + dy * dy
                if dist2 < radius * radius and dist2 > 1e-9:
                    dist = math.sqrt(dist2)
                    push = radius - dist
                    px += (dx / dist) * push
                    py += (dy / dist) * push
                elif dist2 <= 1e-9:
                    px += 0.4
                    py += 0.4
    return px, py


def noisy_surface(size, rng, base=180, contrast=55):
    w, h = size
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        for x in range(w):
            n = rng.randint(-contrast, contrast)
            v = clamp(base + n, 0, 255)
            a = rng.randint(140, 220)
            s.set_at((x, y), (v, v, v, a))
    return s


def make_monster_sprite(seed):
    rng = random.Random(seed)
    w, h = 34, 38
    s = pygame.Surface((w, h), pygame.SRCALPHA)

    body_pts = []
    cx, cy = w / 2.0, h / 2.0 + 1.0
    for i in range(18):
        ang = (math.pi * 2.0 * i) / 18.0
        rx = 11.0 + rng.uniform(-2.2, 3.2)
        ry = 13.0 + rng.uniform(-2.5, 2.8)
        if 0.2 < ang < 2.9:
            ry += 1.5
        if 3.6 < ang < 5.8:
            rx += 0.8
        x = cx + math.cos(ang) * rx
        y = cy + math.sin(ang) * ry
        body_pts.append((x, y))
    pygame.draw.polygon(s, (198, 190, 176, 0), body_pts)

    noise = noisy_surface((w, h), rng, base=192, contrast=44)
    mask = pygame.mask.from_surface(s)
    body = mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0)).convert_alpha()
    noise.blit(body, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    s = noise

    shadow_pts = [(int(x), int(y)) for x, y in body_pts]
    pygame.draw.polygon(s, (24, 20, 26, 140), shadow_pts, 2)

    for _ in range(7):
        x = int(cx + rng.uniform(-9, 9))
        y = int(cy + rng.uniform(-10, 10))
        r = rng.randint(2, 4)
        col = rng.randint(90, 135)
        pygame.draw.circle(s, (col, col + 6, col + 10, 58), (x, y), r)

    # Spines / appendages to break the square silhouette.
    for side in (-1, 1):
        for idx in range(3):
            base_x = int(cx + side * (9 + idx * 2))
            base_y = int(cy - 2 + idx * 5)
            tip_x = base_x + side * rng.randint(5, 9)
            tip_y = base_y + rng.randint(-3, 3)
            pygame.draw.line(s, (38, 34, 42, 220), (base_x, base_y), (tip_x, tip_y), 2)
            pygame.draw.line(s, (205, 198, 185, 190), (base_x, base_y), (tip_x, tip_y), 1)

    # Eyes and mouth.
    eye_y = int(cy - 5)
    for ex in (int(cx - 6), int(cx + 6)):
        pygame.draw.circle(s, (14, 12, 18, 230), (ex, eye_y), 4)
        pygame.draw.circle(s, (242, 80, 92, 240), (ex, eye_y), 2)
        pygame.draw.circle(s, (255, 200, 200, 180), (ex - 1, eye_y - 1), 1)

    mouth_rect = pygame.Rect(int(cx - 6), int(cy + 3), 12, 6)
    pygame.draw.arc(s, (40, 20, 20, 220), mouth_rect, 0.05, math.pi - 0.05, 2)
    for tx in range(5):
        x = int(cx - 4 + tx * 2)
        pygame.draw.line(s, (230, 220, 205, 210), (x, int(cy + 6)), (x, int(cy + 9)), 1)

    # Trim transparent margin so the sprite reads as a shape, not a box.
    bbox = s.get_bounding_rect(min_alpha=8)
    if bbox.width > 0 and bbox.height > 0:
        trimmed = pygame.Surface((bbox.width, bbox.height), pygame.SRCALPHA)
        trimmed.blit(s, (0, 0), bbox)
        return trimmed
    return s


def make_player_sprite(seed, color):
    rng = random.Random(seed)
    s = pygame.Surface((22, 26), pygame.SRCALPHA)
    for y in range(26):
        for x in range(22):
            d = math.hypot(x - 11, (y - 13) * 1.15)
            if d < 8.8 and rng.random() < 0.9:
                c0 = clamp(color[0] + rng.randint(-30, 30), 0, 255)
                c1 = clamp(color[1] + rng.randint(-30, 30), 0, 255)
                c2 = clamp(color[2] + rng.randint(-30, 30), 0, 255)
                s.set_at((x, y), (c0, c1, c2, 230))
    pygame.draw.circle(s, (20, 20, 26, 230), (8, 10), 1)
    pygame.draw.circle(s, (20, 20, 26, 230), (14, 10), 1)
    pygame.draw.line(s, (20, 20, 26, 200), (8, 15), (14, 15), 1)
    for _ in range(12):
        x = rng.randrange(0, 22)
        y1 = rng.randrange(0, 26)
        y2 = clamp(y1 + rng.randrange(4, 10), 0, 25)
        pygame.draw.line(s, (255, 255, 255, rng.randint(30, 70)), (x, y1), (x, y2), 1)
    return s


def line_of_sight(g, ax, ay, bx, by):
    x0, y0 = ax, ay
    x1, y1 = bx, by
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        if is_wall(g, x0, y0) and (x0, y0) != (ax, ay) and (x0, y0) != (bx, by):
            return False
        if x0 == x1 and y0 == y1:
            return True
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


def astar(start, goal, is_walkable):
    if start == goal:
        return [start]
    open_set = []
    heappush(open_set, (0.0, start))
    g_score = {start: 0.0}
    came = {}

    def h(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    while open_set:
        _, cur = heappop(open_set)
        if cur == goal:
            path = [cur]
            while cur in came:
                cur = came[cur]
                path.append(cur)
            path.reverse()
            return path

        cx, cy = cur
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            nxt = (nx, ny)
            if not is_walkable(nxt):
                continue
            tentative = g_score[cur] + 1.0
            if tentative < g_score.get(nxt, 1e9):
                came[nxt] = cur
                g_score[nxt] = tentative
                heappush(open_set, (tentative + h(nxt, goal), nxt))
    return []


def merge_expedition_knowledge(sender, receiver):
    """Relay actionable discoveries only; never share explored map geometry."""
    shared = {
        "stairs": False,
        "monster": False,
        "weapons": 0,
        "treasure": 0,
        "fragment": False,
    }

    if sender.known_stairs is not None and receiver.known_stairs is None:
        receiver.known_stairs = sender.known_stairs
        shared["stairs"] = True

    if sender.known_monster is not None and sender.known_monster != receiver.known_monster:
        receiver.known_monster = sender.known_monster
        shared["monster"] = True

    new_weapons = sender.known_weapons - receiver.known_weapons
    if new_weapons:
        receiver.known_weapons.update(new_weapons)
        shared["weapons"] = len(new_weapons)

    new_treasure = sender.known_treasures - receiver.known_treasures
    if new_treasure:
        receiver.known_treasures.update(new_treasure)
        shared["treasure"] = len(new_treasure)

    if sender.known_fragment is not None and receiver.known_fragment != sender.known_fragment:
        receiver.known_fragment = sender.known_fragment
        shared["fragment"] = True

    return shared


def direction_word(origin_xy, target_tile):
    ox, oy = origin_xy
    tx, ty = target_tile
    dx = tx - ox
    dy = ty - oy
    if abs(dx) > abs(dy):
        return "east" if dx > 0 else "west"
    if abs(dy) > 0:
        return "south" if dy > 0 else "north"
    return "nearby"


class Player:
    def __init__(self, name, ai=False, color=(180, 220, 230), seed=0):
        self.name = name
        self.ai = ai
        self.x = 0.0
        self.y = 0.0
        self.alive = True
        self.weapons = 0
        self.treasure = 0
        self.speed = 108.0
        self.sprite = make_player_sprite(seed, color)
        self.anim_t = 0.0
        self.attack_anim_t = 0.0
        self.attack_flash_t = 0.0
        self.attack_cooldown = 0.0
        self.step_timer = 0.0
        self.swing_dir = -1 if (seed % 2) else 1

        self.vision_radius = VISION_RADIUS_TILES + (seed % 2)
        self.known_open = set()
        self.known_walls = set()
        self.known_treasures = set()
        self.known_weapons = set()
        self.known_stairs = None
        self.known_monster = None
        self.known_fragment = None
        self.last_observed_key = None
        self.ai_target = None
        self.ai_path = []
        self.stuck_time = 0.0
        self.last_tile = None

    def spawn(self, sx, sy):
        self.x = (sx + random.uniform(-0.2, 0.2) + 0.5) * TILE
        self.y = (sy + random.uniform(-0.2, 0.2) + 0.5) * TILE
        self.alive = True
        self.weapons = max(0, self.weapons)
        self.ai_target = None
        self.ai_path = []
        self.stuck_time = 0.0
        self.last_tile = None
        self.attack_cooldown = 0.0
        self.step_timer = random.uniform(0.0, 0.12)
        self.known_open.clear()
        self.known_walls.clear()
        self.known_treasures.clear()
        self.known_weapons.clear()
        self.known_stairs = None
        self.known_monster = None
        self.known_fragment = None
        self.last_observed_key = None

    def draw(self, surf, camx, camy):
        if not self.alive:
            return
        bob = int(math.sin(self.anim_t * 8.0) * 2)
        px = int(self.x - camx)
        py = int(self.y - camy)
        surf.blit(self.sprite, (px - 11, py - 13 + bob))

        if self.weapons > 0:
            wx = px + (7 * self.swing_dir)
            wy = py - 2
            pygame.draw.line(surf, (220, 220, 230), (px, py), (wx, wy), 2)
            pygame.draw.circle(surf, (245, 205, 120), (wx, wy), 2)

        if self.attack_anim_t > 0.0:
            pulse = int(18 + 12 * (self.attack_anim_t / 0.18))
            color = (255, 180, 120, 160)
            ring = pygame.Surface((pulse * 2, pulse * 2), pygame.SRCALPHA)
            pygame.draw.circle(ring, color, (pulse, pulse), pulse, 2)
            surf.blit(ring, (px - pulse, py - pulse))


CRAWLER_PROFILES = {
    "listener": {
        "label": "LISTENER",
        "hint": "footsteps draw it",
        "vision_tiles": 4.8,
        "hearing_tiles": 9.5,
        "memory_s": 5.5,
        "speed": 70.0,
        "chase_speed": 77.0,
        "aura": (210, 170, 90),
    },
    "watcher": {
        "label": "WATCHER",
        "hint": "long sightlines wake it",
        "vision_tiles": 11.0,
        "hearing_tiles": 3.8,
        "memory_s": 4.2,
        "speed": 72.0,
        "chase_speed": 79.0,
        "aura": (150, 205, 240),
    },
    "stalker": {
        "label": "STALKER",
        "hint": "it pressures isolated explorers",
        "vision_tiles": 7.5,
        "hearing_tiles": 6.2,
        "memory_s": 7.0,
        "speed": 61.0,
        "chase_speed": 82.0,
        "aura": (190, 125, 215),
    },
    "warden": {
        "label": "WARDEN",
        "hint": "it guards the stair region",
        "vision_tiles": 7.0,
        "hearing_tiles": 5.4,
        "memory_s": 4.8,
        "speed": 68.0,
        "chase_speed": 76.0,
        "territory_tiles": 10.5,
        "aura": (225, 120, 105),
    },
}


def crawler_profile_for_seed(seed):
    keys = ("listener", "watcher", "stalker", "warden")
    return keys[int(seed) % len(keys)]


def crawler_profile_summary(profile_key):
    p = CRAWLER_PROFILES[profile_key]
    return f"{p['label']}: {p['hint']}"


class Monster:
    def __init__(self, x, y, seed=0, home_tile=None):
        self.x = x
        self.y = y
        self.hp = 3
        self.seed = seed
        self.profile_key = crawler_profile_for_seed(seed)
        self.profile = CRAWLER_PROFILES[self.profile_key]
        self.v = self.profile["speed"]
        self.base = make_monster_sprite(seed)
        self.t = 0.0
        self.path = []
        self.path_target = None
        self.path_refresh = 0.0
        self.state = "idle"
        self.last_known = None
        self.awareness_t = 0.0
        self.target_name = None
        self.last_stimulus = None
        self.noise_priority = 0.0
        self.home_tile = home_tile or (int(x // TILE), int(y // TILE))
        self.home_xy = ((self.home_tile[0] + 0.5) * TILE, (self.home_tile[1] + 0.5) * TILE)

    @property
    def alive(self):
        return self.hp > 0

    def _distance_to_home_tiles(self, x, y):
        return math.hypot(x - self.home_xy[0], y - self.home_xy[1]) / TILE

    def _is_isolated(self, target, players):
        others = [p for p in players if p.alive and p is not target]
        if not others:
            return True
        nearest = min(math.hypot(target.x - p.x, target.y - p.y) for p in others)
        return nearest > TILE * 4.2

    def hear_noise(self, x, y, strength_tiles, kind="noise"):
        if not self.alive:
            return False
        px = self.profile
        propagation = min(float(strength_tiles), float(px["hearing_tiles"]))
        if self.profile_key == "listener" and kind == "step":
            propagation = min(float(strength_tiles) * 1.35, float(px["hearing_tiles"]))
        elif self.profile_key == "watcher" and kind == "step":
            propagation *= 0.55

        if self.profile_key == "warden" and kind == "step":
            territory = float(px.get("territory_tiles", 10.5))
            if self._distance_to_home_tiles(x, y) > territory:
                return False

        distance = math.hypot(self.x - x, self.y - y)
        if distance > propagation * TILE:
            return False

        proximity = max(0.0, 1.0 - distance / max(1.0, propagation * TILE))
        kind_weight = {"step": 1.0, "loot": 1.15, "attack": 2.0}.get(kind, 1.0)
        if self.profile_key == "listener" and kind == "step":
            kind_weight *= 1.35
        priority = proximity * kind_weight
        if self.awareness_t > 0.0 and priority + 0.05 < self.noise_priority:
            return True

        self.noise_priority = priority
        self.last_known = (float(x), float(y))
        self.last_stimulus = kind
        self.awareness_t = max(self.awareness_t, float(px["memory_s"]))
        if self.state != "chase":
            self.state = "investigate"
        return True

    def _visible_targets(self, players, grid):
        out = []
        vision = float(self.profile["vision_tiles"]) * TILE
        mt = (int(self.x // TILE), int(self.y // TILE))
        for p in players:
            if not p.alive:
                continue
            d = math.hypot(p.x - self.x, p.y - self.y)
            if d > vision:
                continue
            pt = (int(p.x // TILE), int(p.y // TILE))
            if line_of_sight(grid, mt[0], mt[1], pt[0], pt[1]):
                out.append((d, p))
        return out

    def _choose_visible_target(self, visible, players):
        if not visible:
            return None
        if self.profile_key == "stalker":
            ranked = sorted(
                visible,
                key=lambda item: (not self._is_isolated(item[1], players), item[0]),
            )
            return ranked[0][1]
        return min(visible, key=lambda item: item[0])[1]

    def _goal_for_state(self):
        if self.state in ("chase", "investigate", "stalk") and self.last_known is not None:
            return self.last_known
        if self.profile_key == "warden":
            return self.home_xy
        return None

    def update(self, dt, players, grid):
        if not self.alive:
            return None
        self.t += dt
        self.path_refresh = max(0.0, self.path_refresh - dt)
        self.awareness_t = max(0.0, self.awareness_t - dt)
        self.noise_priority = max(0.0, self.noise_priority - dt * 0.45)
        previous_state = self.state
        previous_target = self.target_name

        visible = self._visible_targets(players, grid)
        target = self._choose_visible_target(visible, players)
        if target is not None:
            self.target_name = target.name
            self.last_known = (target.x, target.y)
            self.last_stimulus = "sight"
            self.noise_priority = 0.0
            self.awareness_t = float(self.profile["memory_s"])
            if self.profile_key == "stalker" and not self._is_isolated(target, players):
                self.state = "stalk"
            else:
                self.state = "chase"
        elif self.awareness_t > 0.0 and self.last_known is not None:
            self.target_name = None
            if self.state == "chase":
                self.state = "investigate"
        else:
            self.target_name = None
            self.last_known = None
            self.last_stimulus = None
            self.state = "return" if self.profile_key == "warden" else "idle"

        goal_world = self._goal_for_state()
        if self.state == "stalk" and target is not None:
            distance = math.hypot(target.x - self.x, target.y - self.y)
            # A stalker shadows grouped explorers instead of charging blindly.
            if distance < TILE * 4.4:
                goal_world = None
            elif distance > TILE * 6.0:
                goal_world = (target.x, target.y)

        if self.profile_key == "warden" and self.state == "chase" and target is not None:
            territory = float(self.profile.get("territory_tiles", 10.5))
            if self._distance_to_home_tiles(target.x, target.y) > territory + 2.0:
                self.state = "return"
                self.target_name = None
                self.last_known = None
                goal_world = self.home_xy

        if goal_world is not None:
            current = (int(self.x // TILE), int(self.y // TILE))
            goal = (int(goal_world[0] // TILE), int(goal_world[1] // TILE))
            goal = (clamp(goal[0], 0, GRID_W - 1), clamp(goal[1], 0, GRID_H - 1))
            if self.path_refresh <= 0.0 or goal != self.path_target or not self.path:
                self.path_target = goal
                self.path = astar(current, goal, lambda t: in_bounds(t[0], t[1]) and not is_wall(grid, t[0], t[1]))
                if self.path and self.path[0] == current:
                    self.path = self.path[1:]
                self.path_refresh = 0.24 if self.state == "chase" else 0.34
        else:
            self.path = []
            self.path_target = None

        if self.path:
            gx, gy = self.path[0]
            wx = (gx + 0.5) * TILE
            wy = (gy + 0.5) * TILE
            dx = wx - self.x
            dy = wy - self.y
            d = math.hypot(dx, dy)
            if d < 3.0:
                self.path.pop(0)
            elif d > 1e-6:
                speed = float(self.profile["chase_speed"] if self.state == "chase" else self.profile["speed"])
                step = min(d, speed * dt)
                nx = self.x + (dx / d) * step
                ny = self.y + (dy / d) * step
                self.x, self.y = resolve_circle(nx, ny, grid, radius=8.0)

        if self.state == "return" and math.hypot(self.x - self.home_xy[0], self.y - self.home_xy[1]) < TILE * 0.7:
            self.state = "idle"
            self.path = []

        if previous_state != self.state or previous_target != self.target_name:
            return {
                "from": previous_state,
                "to": self.state,
                "target": self.target_name,
                "profile": self.profile_key,
            }
        return None

    def draw(self, surf, camx, camy):
        if not self.alive:
            return
        jx = int(math.sin(self.t * 14 + self.seed) * 2)
        jy = int(math.cos(self.t * 11 + self.seed) * 2)
        bw, bh = self.base.get_size()
        px = int(self.x - camx)
        py = int(self.y - camy)
        aura = self.profile["aura"]
        pygame.draw.circle(surf, aura, (px, py), max(12, bw // 2 + 3), 1)
        surf.blit(self.base, (px - bw // 2 + jx, py - bh // 2 + jy))
        if FONT:
            img = FONT.render(f"{self.profile['label']}  HP:{self.hp}", True, (255, 220, 220))
            surf.blit(img, (px - img.get_width() // 2, py - bh // 2 - 16))


class Game:
    def __init__(self, expedition: dict | None = None):
        # ``expedition`` is None for standalone play.  Entropy passes a dict
        # with at least ``seed`` and ``depth`` for an archive-ruin dive.
        self.expedition = dict(expedition) if expedition else None
        self.depth = max(1, int(self.expedition.get("depth", DIVE_DEFAULT_DEPTH))) if self.expedition else 0
        self.result: str | None = None
        self.fragment_tile = None
        self.fragment_holder = None
        self.ascent_tile = None
        self.entry_tile = None
        self.room_index = 0
        self.seed_base = (
            int(self.expedition.get("seed", 0)) & 0x7FFFFFF if self.expedition else random.randint(0, 9_999_999)
        )
        self.chat_lines = []
        self.chat_timer = 0.0
        self.chat_cooldowns = {}
        self.knowledge_pair_cooldowns = {}
        self.knowledge_exchange_radius = TILE * 2.35

        self.players = [
            Player("You", ai=False, color=(130, 235, 210), seed=1),
            Player("Nova", ai=True, color=(245, 180, 130), seed=2),
            Player("Kite", ai=True, color=(145, 200, 255), seed=3),
            Player("Rook", ai=True, color=(210, 210, 120), seed=4),
            Player("Mira", ai=True, color=(225, 160, 235), seed=5),
            Player("Echo", ai=True, color=(145, 235, 170), seed=6),
            Player("Vex", ai=True, color=(235, 150, 165), seed=7),
            Player("Lux", ai=True, color=(170, 185, 245), seed=8),
            Player("Drift", ai=True, color=(230, 210, 140), seed=9),
        ]
        self.human = self.players[0]

        self.grid = []
        self.stairs = (0, 0)
        self.monster = None
        self.treasures = []
        self.weapons_pickups = []
        self.weapon_pickup_types = {}
        self.weapon_type_styles = {
            "stick": ("Stick", (152, 114, 72), (210, 182, 130)),
            "spike": ("Spike", (176, 176, 192), (228, 228, 240)),
            "club": ("Club", (124, 94, 60), (200, 170, 120)),
            "shard": ("Shard", (120, 178, 205), (190, 230, 245)),
        }
        self.level_message = ""
        self.level_message_t = 0.0

        self.human_visible = set()
        self.human_explored = set()
        self.used_level_seeds = set()
        self._new_room(initial=True)

    def _log_chat(self, who, text):
        key = f"{who}:{text.lower()}"
        now = pygame.time.get_ticks() / 1000.0
        if self.chat_cooldowns.get(key, 0) > now:
            return
        self.chat_cooldowns[key] = now + 6.0
        self.chat_lines.append((who, text))
        self.chat_lines = self.chat_lines[-7:]

    @property
    def on_vault_floor(self) -> bool:
        return bool(self.expedition) and self.room_index + 1 >= self.depth

    def _new_room(self, initial=False):
        if self.expedition:
            # Deterministic per ruin + floor so a dive is reproducible in QA.
            seed = self.seed_base + self.room_index * 1171 + 97
        else:
            seed = self.seed_base + self.room_index * 1171 + random.randint(0, 999)
        attempts = 0
        while seed in self.used_level_seeds and attempts < 16:
            seed += random.randint(31, 997)
            attempts += 1
        self.used_level_seeds.add(seed)
        self.grid, (sx, sy), self.stairs = generate_grid(seed)
        self.knowledge_pair_cooldowns.clear()
        self._vis_cache = {}
        self.fragment_tile = None
        self.fragment_holder = None
        self.ascent_tile = None
        self.entry_tile = (sx, sy) if self.expedition else None

        monster_seed = seed + 77
        if self.on_vault_floor:
            # The vault floor has no stairs down: the archive fragment sits in
            # the deepest chamber and a WARDEN crawler guards it.
            vx, vy = self.stairs
            self.grid[vy][vx] = FLOOR
            self.fragment_tile = (vx, vy)
            self.ascent_tile = (sx, sy)
            self.stairs = (-10, -10)
            monster_seed = monster_seed - (monster_seed % 4) + 3  # warden profile
            home = self.fragment_tile
        else:
            home = self.stairs
        mx = (home[0] + 0.5) * TILE
        my = (home[1] + 0.5) * TILE
        self.monster = Monster(mx, my, seed=monster_seed, home_tile=home)

        for p in self.players:
            p.spawn(sx, sy)
            if not initial:
                p.weapons = 0
            self._observe_world(p)

        rng = random.Random(seed + 333)
        floor_tiles = [(x, y) for y in range(GRID_H) for x in range(GRID_W) if self.grid[y][x] == FLOOR]
        rng.shuffle(floor_tiles)
        self.treasures = floor_tiles[:rng.randint(16, 24)]
        self.weapons_pickups = floor_tiles[rng.randint(26, 34):rng.randint(42, 54)]
        self.weapon_pickup_types = {
            tile: rng.choice(tuple(self.weapon_type_styles.keys())) for tile in self.weapons_pickups
        }

        self.human_visible = set()
        self.human_explored.clear()
        self._observe_world(self.human, update_player_fog=True)

        if not self.expedition:
            self.level_message = f"Room {self.room_index + 1}: scavenge, survive, find the stairs"
        elif self.on_vault_floor:
            self.level_message = f"Floor {self.room_index + 1}/{self.depth}: archive vault — take the fragment"
        else:
            self.level_message = f"Floor {self.room_index + 1}/{self.depth}: find the stairs down to the archive vault"
        self.level_message_t = 0.0
        self._play_spatial_sfx("spawn", ((sx + 0.5) * TILE, (sy + 0.5) * TILE), 0.55)

    def _move_player(self, p, dx, dy, dt):
        if not p.alive:
            return
        mag = math.hypot(dx, dy)
        if mag > 0:
            dx /= mag
            dy /= mag
        speed = p.speed + (12 if p.ai else 0)
        old_x, old_y = p.x, p.y
        nx = p.x + dx * speed * dt
        ny = p.y + dy * speed * dt
        p.x, p.y = resolve_circle(nx, ny, self.grid)
        moved = math.hypot(p.x - old_x, p.y - old_y)
        if moved > 0.05:
            p.anim_t += dt
            p.step_timer -= dt
            if p.step_timer <= 0.0:
                self._play_spatial_sfx("step", (p.x, p.y), 0.24 if p.ai else 0.32, 10.0)
                if self.monster is not None and self.monster.alive:
                    self.monster.hear_noise(p.x, p.y, 6.2 if p.ai else 6.8, "step")
                p.step_timer = 0.28 if p.ai else 0.24
        else:
            p.step_timer = min(p.step_timer, 0.08)

    def _play_spatial_sfx(self, name: str, source_xy: tuple[float, float], base_vol: float = 0.55, max_dist_tiles: float = 16.0):
        if not self.human.alive:
            play_sfx(name, base_vol * 0.35)
            return
        hx, hy = self.human.x, self.human.y
        sx, sy = source_xy
        dist = math.hypot(hx - sx, hy - sy)
        max_dist = max(1.0, max_dist_tiles * TILE)
        atten = max(0.0, 1.0 - (dist / max_dist))
        if atten > 0.015:
            play_sfx(name, base_vol * atten)

    def _knowledge_report_text(self, sender, shared):
        parts = []
        origin = (int(sender.x // TILE), int(sender.y // TILE))
        if shared.get("stairs") and sender.known_stairs is not None:
            parts.append(f"stairs {direction_word(origin, sender.known_stairs)}")
        if shared.get("monster") and sender.known_monster is not None:
            parts.append(f"crawler last seen {direction_word(origin, sender.known_monster)}")
        if shared.get("weapons"):
            n = shared["weapons"]
            parts.append(f"{n} weapon cache{'s' if n != 1 else ''}")
        if shared.get("fragment") and sender.known_fragment is not None:
            parts.append(f"archive fragment {direction_word(origin, sender.known_fragment)}")
        if shared.get("treasure"):
            n = shared["treasure"]
            parts.append(f"{n} treasure spot{'s' if n != 1 else ''}")
        return ", ".join(parts)

    def _exchange_pair_knowledge(self, a, b):
        a_to_b = merge_expedition_knowledge(a, b)
        b_to_a = merge_expedition_knowledge(b, a)

        if b is self.human and any(a_to_b.values()):
            msg = self._knowledge_report_text(a, a_to_b)
            if msg:
                self._log_chat(a.name, f"report: {msg}")
        if a is self.human and any(b_to_a.values()):
            msg = self._knowledge_report_text(b, b_to_a)
            if msg:
                self._log_chat(b.name, f"report: {msg}")
        return any(a_to_b.values()) or any(b_to_a.values())

    def _process_knowledge_meetings(self):
        now = pygame.time.get_ticks() / 1000.0
        alive = [p for p in self.players if p.alive]
        for i, a in enumerate(alive):
            for b in alive[i + 1:]:
                if math.hypot(a.x - b.x, a.y - b.y) > self.knowledge_exchange_radius:
                    continue
                at = (int(a.x // TILE), int(a.y // TILE))
                bt = (int(b.x // TILE), int(b.y // TILE))
                if not line_of_sight(self.grid, at[0], at[1], bt[0], bt[1]):
                    continue
                key = tuple(sorted((a.name, b.name)))
                if self.knowledge_pair_cooldowns.get(key, 0.0) > now:
                    continue
                changed = self._exchange_pair_knowledge(a, b)
                self.knowledge_pair_cooldowns[key] = now + (4.5 if changed else 1.1)

    def _observe_world(self, p, update_player_fog=False):
        if not p.alive:
            return
        cx, cy = int(p.x // TILE), int(p.y // TILE)
        r = p.vision_radius
        key = (cx, cy, r)
        # Walls never change inside a room, so a tile's field of view is
        # computed once and shared by every explorer standing on it.
        visible = self._vis_cache.get(key)
        if visible is None:
            found = set()
            for yy in range(cy - r, cy + r + 1):
                for xx in range(cx - r, cx + r + 1):
                    if not in_bounds(xx, yy):
                        continue
                    if (xx - cx) * (xx - cx) + (yy - cy) * (yy - cy) > r * r:
                        continue
                    if line_of_sight(self.grid, cx, cy, xx, yy):
                        found.add((xx, yy))
            visible = frozenset(found)
            self._vis_cache[key] = visible
        if p.last_observed_key != key:
            p.last_observed_key = key
            grid = self.grid
            for xx, yy in visible:
                t = grid[yy][xx]
                if t == WALL:
                    p.known_walls.add((xx, yy))
                else:
                    p.known_open.add((xx, yy))
                    if t == STAIRS:
                        p.known_stairs = (xx, yy)
        if self.fragment_holder is None and self.fragment_tile in visible:
            p.known_fragment = self.fragment_tile

        p.known_treasures.intersection_update(self.treasures)
        p.known_weapons.intersection_update(self.weapons_pickups)

        for item in self.treasures:
            if item in visible:
                p.known_treasures.add(item)
        for item in self.weapons_pickups:
            if item in visible:
                p.known_weapons.add(item)

        if self.monster is not None:
            mtx, mty = int(self.monster.x // TILE), int(self.monster.y // TILE)
            if self.monster.alive and (mtx, mty) in visible:
                p.known_monster = (mtx, mty)
            elif p.known_monster and not self.monster.alive:
                p.known_monster = None
        elif p.known_monster:
            p.known_monster = None

        if update_player_fog:
            self.human_visible = visible
            self.human_explored.update(visible)

    def _prune_stale_knowledge(self):
        treasure_set = set(self.treasures)
        weapon_set = set(self.weapons_pickups)
        for p in self.players:
            p.known_treasures.intersection_update(treasure_set)
            p.known_weapons.intersection_update(weapon_set)
            if not self.monster.alive:
                p.known_monster = None

    def _pickup_checks(self, p):
        tx, ty = int(p.x // TILE), int(p.y // TILE)
        if self.fragment_tile is not None and self.fragment_holder is None and p.alive:
            fx, fy = self.fragment_tile
            if math.hypot(p.x - (fx + 0.5) * TILE, p.y - (fy + 0.5) * TILE) <= TILE * 0.9:
                self.fragment_holder = p
                for q in self.players:
                    q.known_fragment = None
                    q.ai_target = None
                    q.ai_path = []
                who = "You" if p is self.human else p.name
                self._log_chat("System", f"{who} secured the archive fragment — regroup at the ascent line")
                self.level_message = "FRAGMENT SECURED — BACK TO THE ASCENT LINE"
                self.level_message_t = 0.0
                self._play_spatial_sfx("exit", (p.x, p.y), 0.7)
                if self.monster is not None and self.monster.alive:
                    self.monster.hear_noise(p.x, p.y, 16.0, "attack")
        if (tx, ty) in self.treasures:
            self.treasures.remove((tx, ty))
            p.treasure += 1
            for q in self.players:
                q.known_treasures.discard((tx, ty))
            if p.ai:
                self._log_chat(p.name, "found treasure in this cavern")
            self._play_spatial_sfx("loot", (p.x, p.y), 0.36)
            self.monster.hear_noise(p.x, p.y, 4.0, "loot")
        if (tx, ty) in self.weapons_pickups:
            self.weapons_pickups.remove((tx, ty))
            weapon_kind = self.weapon_pickup_types.pop((tx, ty), "stick")
            p.weapons += 1
            for q in self.players:
                q.known_weapons.discard((tx, ty))
            if p.ai:
                label = self.weapon_type_styles.get(weapon_kind, (weapon_kind.title(),))[0]
                self._log_chat(p.name, f"grabbed a one-use {label}")
            self._play_spatial_sfx("loot", (p.x, p.y), 0.34)
            self.monster.hear_noise(p.x, p.y, 4.0, "loot")

    def _monster_combat(self, p, attack=False):
        if not p.alive or not self.monster.alive:
            return
        d = math.hypot(p.x - self.monster.x, p.y - self.monster.y)
        if attack and d < 42 and p.weapons > 0 and p.attack_cooldown <= 0.0:
            p.weapons -= 1
            p.attack_anim_t = 0.18
            p.attack_flash_t = 0.10
            p.attack_cooldown = 0.34
            self.monster.hear_noise(p.x, p.y, 13.0, "attack")
            self.monster.hp = max(0, self.monster.hp - 1)
            self._log_chat(p.name, f"hit monster ({self.monster.hp}/3 left)")
            self._play_spatial_sfx("hit", (self.monster.x, self.monster.y), 0.62)
            if self.monster.hp <= 0:
                self._log_chat("System", "monster down — stairs are clear")
                self._play_spatial_sfx("exit", (self.monster.x, self.monster.y), 0.74)
        # one boss bite downs a player until the next generated level.
        if d < 20 and self.monster.alive:
            if self.fragment_holder is p:
                self.fragment_holder = None
                self.fragment_tile = (int(p.x // TILE), int(p.y // TILE))
                self._log_chat("System", f"{p.name} dropped the archive fragment")
            p.alive = False
            self._play_spatial_sfx("caught", (p.x, p.y), 0.62)
            self._log_chat("System", f"{p.name} is down until next room")

    def _find_frontier(self, p, tx, ty):
        best = None
        bestd = 1e9
        for x, y in p.known_open:
            unknown_n = 0
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if in_bounds(nx, ny) and (nx, ny) not in p.known_open and (nx, ny) not in p.known_walls:
                    unknown_n += 1
            if unknown_n <= 0:
                continue
            d = (x - tx) * (x - tx) + (y - ty) * (y - ty)
            if d < bestd:
                bestd = d
                best = (x, y)
        return best

    @staticmethod
    def _is_frontier(p, tile):
        if tile not in p.known_open:
            return False
        x, y = tile
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if in_bounds(nx, ny) and (nx, ny) not in p.known_open and (nx, ny) not in p.known_walls:
                return True
        return False

    def _walkable_known(self, p, tile, target):
        x, y = tile
        if not in_bounds(x, y):
            return False
        if tile == target:
            return not is_wall(self.grid, x, y)
        if tile in p.known_walls:
            return False
        if tile in p.known_open:
            return True
        return False

    def _ai_update(self, p, dt):
        if not p.alive:
            return

        self._observe_world(p)
        tx, ty = int(p.x // TILE), int(p.y // TILE)

        target = None
        if self.expedition and self.fragment_holder is not None and self.ascent_tile is not None:
            target = self.ascent_tile
        elif self.expedition and p.known_fragment is not None and self.fragment_holder is None:
            target = p.known_fragment
        elif p.weapons <= 0 and p.known_weapons:
            target = min(p.known_weapons, key=lambda t: (t[0] - tx) ** 2 + (t[1] - ty) ** 2)
        elif self.monster.alive and p.known_monster:
            target = p.known_monster
        elif p.known_treasures:
            target = min(p.known_treasures, key=lambda t: (t[0] - tx) ** 2 + (t[1] - ty) ** 2)
        elif p.known_stairs and not self.monster.alive:
            target = p.known_stairs
        else:
            # Keep walking to the committed frontier while it is still unexplored
            # at its edge; re-scanning every frame made explorers dither.
            if p.ai_path and p.ai_target is not None and self._is_frontier(p, p.ai_target):
                target = p.ai_target
            else:
                target = self._find_frontier(p, tx, ty)
            if target is None:
                target = (tx, ty)

        current_tile = (tx, ty)
        if current_tile == p.last_tile:
            p.stuck_time += dt
        else:
            p.stuck_time = 0.0
            p.last_tile = current_tile

        if target != p.ai_target or not p.ai_path or p.stuck_time > 0.9:
            p.ai_target = target
            p.ai_path = astar(current_tile, target, lambda t: self._walkable_known(p, t, target))
            if p.ai_path and p.ai_path[0] == current_tile:
                p.ai_path = p.ai_path[1:]
            if p.stuck_time > 0.9 and not p.ai_path:
                dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
                random.shuffle(dirs)
                for dx, dy in dirs:
                    nx, ny = tx + dx, ty + dy
                    if in_bounds(nx, ny) and not is_wall(self.grid, nx, ny):
                        p.ai_path = [(nx, ny)]
                        break
                p.stuck_time = 0.0

        if p.ai_path:
            gx, gy = p.ai_path[0]
            wx = (gx + 0.5) * TILE
            wy = (gy + 0.5) * TILE
            dx = wx - p.x
            dy = wy - p.y
            if dx * dx + dy * dy < 16.0:
                p.ai_path.pop(0)
            else:
                self._move_player(p, dx, dy, dt)
        else:
            self._move_player(p, 0.0, 0.0, dt)

        self._pickup_checks(p)
        self._monster_combat(p, attack=True)

    def camera(self):
        camx = clamp(self.human.x - W * 0.5, 0, GRID_W * TILE - W)
        camy = clamp(self.human.y - H * 0.5, 0, GRID_H * TILE - H)
        return camx, camy

    def update(self, dt, keys, attack_pressed=False, mouse_target=None, stick=None):
        self.level_message_t += dt
        self.chat_timer += dt

        dx = dy = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1
        if dx == 0.0 and dy == 0.0 and mouse_target is not None:
            # Hold left mouse: walk toward the cursor (logical-frame coords).
            camx, camy = self.camera()
            tx = mouse_target[0] + camx - self.human.x
            ty = mouse_target[1] + camy - self.human.y
            if tx * tx + ty * ty > 36.0:
                dx, dy = tx, ty
        if dx == 0.0 and dy == 0.0 and stick is not None:
            dx, dy = stick

        self._move_player(self.human, dx, dy, dt)
        self._observe_world(self.human, update_player_fog=True)
        self._pickup_checks(self.human)
        self._monster_combat(self.human, attack=attack_pressed)

        for p in self.players[1:]:
            self._ai_update(p, dt)

        self._prune_stale_knowledge()
        self._process_knowledge_meetings()

        for p in self.players:
            if p.attack_cooldown > 0.0:
                p.attack_cooldown = max(0.0, p.attack_cooldown - dt)
            if p.attack_anim_t > 0.0:
                p.attack_anim_t = max(0.0, p.attack_anim_t - dt)
            if p.attack_flash_t > 0.0:
                p.attack_flash_t = max(0.0, p.attack_flash_t - dt)

        if self.monster.alive:
            event = self.monster.update(dt, self.players, self.grid)
            if event and event.get("to") == "chase" and event.get("target") == self.human.name:
                play_sfx("alert", 0.58)
                self._log_chat("System", f"{self.monster.profile['label'].lower()} crawler has your trail")

        if not self.human.alive:
            if self.expedition:
                self.result = "downed"
                return
            self.room_index = 0
            self._log_chat("System", "you were downed — run restarted")
            self._new_room(initial=True)
            return

        if self.expedition and self.fragment_holder is not None and self.ascent_tile is not None:
            ax, ay = self.ascent_tile
            if math.hypot(self.human.x - (ax + 0.5) * TILE, self.human.y - (ay + 0.5) * TILE) <= TILE * 1.1:
                self._play_spatial_sfx("exit", (self.human.x, self.human.y), 0.8)
                self.result = "recovered"
                return

        if not any(p.alive for p in self.players):
            self.room_index += 1
            self._log_chat("System", "party wiped, next room generated")
            self._new_room()
            return

        for p in self.players:
            if not p.alive:
                continue
            if (int(p.x // TILE), int(p.y // TILE)) == self.stairs:
                self.room_index += 1
                self._log_chat("System", f"{p.name} reached the stairs")
                self._play_spatial_sfx("exit", (p.x, p.y), 0.72)
                self._new_room()
                return

        if self.chat_timer > random.uniform(3.8, 6.6):
            self.chat_timer = 0.0
            alive_ai = [p for p in self.players[1:] if p.alive]
            if alive_ai and random.random() < 0.6:
                speaker = random.choice(alive_ai)
                line = random.choice([
                    "checking a side cavern",
                    "doubling back through this tunnel",
                    "still searching for supplies",
                    "holding this junction for a moment",
                    "moving deeper before I turn back",
                ])
                self._log_chat(speaker.name, line)

    def _build_map_layers(self):
        """Pre-render the room once; per-frame fog is a tiny tile-resolution mask."""
        world = pygame.Surface((GRID_W * TILE, GRID_H * TILE))
        for y in range(GRID_H):
            for x in range(GRID_W):
                t = self.grid[y][x]
                if t == WALL:
                    v = 28 + ((x * 11 + y * 17) % 32)
                    base = (v, v + 3, v + 6)
                elif t == STAIRS:
                    base = (84, 86, 102)
                else:
                    v = 42 + ((x * 3 + y * 5) % 18)
                    base = (v, v + 7, v + 4)
                r = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
                world.fill(base, r)
                if t == STAIRS:
                    pygame.draw.rect(world, (180, 185, 205), r.inflate(-8, -8), 2)
        fog = pygame.Surface((GRID_W, GRID_H), pygame.SRCALPHA)
        fog.fill((3, 4, 6, 255))
        for tile in self.human_explored:
            fog.set_at(tile, (0, 0, 0, 140))
        self._map_layer = world
        self._fog_layer = fog
        self._fog_visible = frozenset()

    def _sync_fog(self):
        vis = self.human_visible
        if vis is self._fog_visible:
            return
        fog = self._fog_layer
        for tile in self._fog_visible - vis:
            fog.set_at(tile, (0, 0, 0, 140))
        for tile in vis - self._fog_visible:
            fog.set_at(tile, (0, 0, 0, 0))
        self._fog_visible = vis

    def draw(self, surf):
        camx, camy = self.camera()
        icx, icy = int(camx), int(camy)
        if getattr(self, "_map_grid", None) is not self.grid:
            self._map_grid = self.grid
            self._build_map_layers()
        self._sync_fog()
        surf.blit(self._map_layer, (0, 0), pygame.Rect(icx, icy, W, H))
        y0 = max(0, icy // TILE)
        y1 = min(GRID_H, (icy + H) // TILE + 1)
        x0 = max(0, icx // TILE)
        x1 = min(GRID_W, (icx + W) // TILE + 1)
        fog_view = self._fog_layer.subsurface(pygame.Rect(x0, y0, x1 - x0, y1 - y0))
        fog_px = pygame.transform.scale(fog_view, ((x1 - x0) * TILE, (y1 - y0) * TILE))
        surf.blit(fog_px, (x0 * TILE - icx, y0 * TILE - icy))

        for x, y in self.treasures:
            if (x, y) in self.human_visible:
                px, py = int(x * TILE - camx), int(y * TILE - camy)
                pygame.draw.circle(surf, (235, 195, 90), (px + TILE // 2, py + TILE // 2), 4)

        for x, y in self.weapons_pickups:
            if (x, y) in self.human_visible:
                px, py = int(x * TILE - camx), int(y * TILE - camy)
                kind = self.weapon_pickup_types.get((x, y), "stick")
                _label, c0, c1 = self.weapon_type_styles.get(kind, ("Item", (180, 140, 100), (220, 200, 170)))
                cx = px + TILE // 2
                cy = py + TILE // 2
                if kind == "stick":
                    pygame.draw.line(surf, c0, (cx - 4, cy + 3), (cx + 4, cy - 3), 3)
                    pygame.draw.circle(surf, c1, (cx + 4, cy - 3), 2)
                elif kind == "spike":
                    pygame.draw.polygon(surf, c1, [(cx, cy - 5), (cx + 4, cy + 4), (cx - 4, cy + 4)])
                    pygame.draw.polygon(surf, c0, [(cx, cy - 3), (cx + 2, cy + 3), (cx - 2, cy + 3)])
                elif kind == "club":
                    pygame.draw.line(surf, c0, (cx - 4, cy + 4), (cx + 3, cy - 3), 3)
                    pygame.draw.circle(surf, c1, (cx + 4, cy - 4), 3)
                else:
                    pygame.draw.polygon(surf, c1, [(cx, cy - 5), (cx + 4, cy), (cx, cy + 5), (cx - 4, cy)])
                    pygame.draw.polygon(surf, c0, [(cx, cy - 2), (cx + 2, cy), (cx, cy + 2), (cx - 2, cy)])

        if self.expedition:
            self._draw_dive_markers(surf, camx, camy)

        m_tile = (int(self.monster.x // TILE), int(self.monster.y // TILE))
        if self.monster.alive and (m_tile in self.human_visible or math.hypot(self.human.x - self.monster.x, self.human.y - self.monster.y) < TILE * 1.8):
            self.monster.draw(surf, camx, camy)

        for p in self.players:
            if not p.alive:
                continue
            ptile = (int(p.x // TILE), int(p.y // TILE))
            if p is self.human or ptile in self.human_visible:
                p.draw(surf, camx, camy)

        if FONT:
            alive = sum(1 for p in self.players if p.alive)
            total_treasure = sum(p.treasure for p in self.players)
            place = f"Floor {self.room_index + 1}/{self.depth}" if self.expedition else f"Room {self.room_index + 1}"
            status = (
                f"{place} | {alive}/{len(self.players)} alive | "
                f"{self.monster.profile['label']} {self.monster.hp if self.monster.alive else 0}HP | Treasure {total_treasure}"
            )
            surf.blit(FONT.render(status, True, (235, 235, 240)), (12, H - 26))
            p = self.human
            surf.blit(FONT.render(f"You: weapons {p.weapons}  treasure {p.treasure}  (SPACE / right-click = use weapon)", True, (230, 250, 235)), (12, H - 48))

            y = 12
            for who, line in self.chat_lines[-6:]:
                surf.blit(FONT.render(f"{who}: {line}", True, (220, 220, 230)), (12, y))
                y += 18

            if self.level_message and self.level_message_t < 2.8 and BIG:
                img = BIG.render(self.level_message, True, (238, 238, 246))
                # Below the six-line chat log so the two never overlap.
                surf.blit(img, img.get_rect(center=(W // 2, 150)))

    def _draw_dive_markers(self, surf, camx, camy):
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 180.0)
        if self.fragment_tile is not None and self.fragment_holder is None:
            fx, fy = self.fragment_tile
            if (fx, fy) in self.human_explored:
                cx = int((fx + 0.5) * TILE - camx)
                cy = int((fy + 0.5) * TILE - camy)
                r = int(6 + 3 * pulse)
                pygame.draw.polygon(surf, FRAGMENT_COLOR, [(cx, cy - r - 2), (cx + r, cy), (cx, cy + r + 2), (cx - r, cy)])
                pygame.draw.polygon(surf, (10, 40, 44), [(cx, cy - r + 2), (cx + r - 4, cy), (cx, cy + r - 2), (cx - r + 4, cy)], 1)
        if self.fragment_holder is not None and self.fragment_holder.alive:
            h = self.fragment_holder
            cx, cy = int(h.x - camx), int(h.y - camy - 18)
            pygame.draw.polygon(surf, FRAGMENT_COLOR, [(cx, cy - 5), (cx + 4, cy), (cx, cy + 5), (cx - 4, cy)])
        for tile, color, label in ((self.ascent_tile, ASCENT_COLOR, "ASCENT LINE"), (self.entry_tile if not self.on_vault_floor else None, (150, 190, 210), "SURFACE")):
            if tile is None or tile not in self.human_explored:
                continue
            cx = int((tile[0] + 0.5) * TILE - camx)
            cy = int((tile[1] + 0.5) * TILE - camy)
            ring = int(10 + (4 * pulse if self.fragment_holder is not None else 0))
            pygame.draw.circle(surf, color, (cx, cy), ring, 2)
            pygame.draw.line(surf, color, (cx, cy - ring - 10), (cx, cy - ring), 2)
            if SMALL:
                img = SMALL.render(label, True, color)
                surf.blit(img, img.get_rect(midbottom=(cx, cy - ring - 12)))

    def objective_text(self) -> str:
        if not self.expedition:
            return ""
        if self.fragment_holder is not None:
            return "RETURN TO THE ASCENT LINE"
        if self.on_vault_floor:
            return "RECOVER THE ARCHIVE FRAGMENT"
        return "FIND THE STAIRS DOWN"



# ---------------------------------------------------------------------------
# Presentation: fixed 1280x720 frame, aspect-safe letterbox into any window.
# Integer scales (2560x1440, 3840x2160) use a crisp fast scale; others smooth.
# ---------------------------------------------------------------------------
def present_rect(window_size) -> pygame.Rect:
    ww, wh = max(1, int(window_size[0])), max(1, int(window_size[1]))
    scale = min(ww / W, wh / H)
    rw, rh = max(1, int(W * scale)), max(1, int(H * scale))
    return pygame.Rect((ww - rw) // 2, (wh - rh) // 2, rw, rh)


def present(window: pygame.Surface, frame: pygame.Surface) -> pygame.Rect:
    rect = present_rect(window.get_size())
    if rect.size == (W, H):
        if rect.topleft != (0, 0):
            window.fill((0, 0, 0))
        window.blit(frame, rect.topleft)
        return rect
    window.fill((0, 0, 0))
    if rect.w % W == 0 and rect.h % H == 0:
        scaled = pygame.transform.scale(frame, rect.size)
    else:
        scaled = pygame.transform.smoothscale(frame, rect.size)
    window.blit(scaled, rect.topleft)
    return rect


def window_to_frame(pos, rect: pygame.Rect):
    if rect.w <= 0 or rect.h <= 0:
        return None
    x = (pos[0] - rect.x) * W / rect.w
    y = (pos[1] - rect.y) * H / rect.h
    if x < 0 or y < 0 or x >= W or y >= H:
        return None
    return x, y


def _new_frame() -> pygame.Surface:
    frame = pygame.Surface((W, H))
    try:
        return frame.convert()
    except pygame.error:
        return frame


def _toggle_mute() -> None:
    global AUDIO_MUTED
    if not AUDIO_OK:
        return
    AUDIO_MUTED = not AUDIO_MUTED
    try:
        if AUDIO_MUTED:
            pygame.mixer.pause()
            pygame.mixer.music.pause()
        else:
            pygame.mixer.unpause()
            pygame.mixer.music.unpause()
    except pygame.error:
        pass


# ---------------------------------------------------------------------------
# Standalone launcher loop (Pass 11 behaviour, plus mouse controls).
# ---------------------------------------------------------------------------
def run_standalone() -> int:
    if FORCE_MATRIX_LAUNCH and not MATRIX_LAUNCH_OK:
        print("Dream Crawler is in MatrixOS-only mode.")
        print("Launch from MatrixOS or set DREAMCRAWLER_ALLOW_STANDALONE=1.")
        return 0
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    window = pygame.display.set_mode((W, H), pygame.RESIZABLE)
    pygame.display.set_caption("Dream Crawler")
    try:
        init_audio(own_mixer=True)
        init_fonts()
        start_music()
        game = Game()
        frame = _new_frame()
        clock = pygame.time.Clock()
        rect = present_rect(window.get_size())
        running = True
        while running:
            dt = min(0.05, clock.tick(60) / 1000.0)
            attack_pressed = False
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        running = False
                    elif e.key == pygame.K_SPACE:
                        attack_pressed = True
                    elif e.key == pygame.K_m:
                        _toggle_mute()
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
                    attack_pressed = True
                elif e.type == pygame.VIDEORESIZE:
                    window = pygame.display.set_mode((max(640, e.w), max(360, e.h)), pygame.RESIZABLE)
            window = pygame.display.get_surface() or window
            mouse_target = None
            if pygame.mouse.get_pressed()[0]:
                mouse_target = window_to_frame(pygame.mouse.get_pos(), rect)
            game.update(dt, pygame.key.get_pressed(), attack_pressed=attack_pressed, mouse_target=mouse_target)
            frame.fill((8, 10, 14))
            game.draw(frame)
            rect = present(window, frame)
            pygame.display.flip()
    finally:
        pygame.quit()
    return 0


# ---------------------------------------------------------------------------
# Hosted ruin dive (Entropy).  Runs inside the host's live window and returns.
# ---------------------------------------------------------------------------
DIVE_OUTCOMES = ("recovered", "retreat", "downed", "collapse")


def _fmt_clock(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}.{int((seconds * 10) % 10)}"


def _draw_dive_hud(frame, game, spec, remaining, rate):
    panel = pygame.Rect(W - 432, 10, 420, 118)
    shade = pygame.Surface(panel.size, pygame.SRCALPHA)
    shade.fill((4, 8, 12, 196))
    frame.blit(shade, panel.topleft)
    pygame.draw.rect(frame, (70, 120, 130), panel, 1)
    x, y = panel.x + 12, panel.y + 8
    frame.blit(SMALL.render(str(spec.get("site_label", "ARCHIVE RUIN")).upper()[:46], True, (150, 200, 210)), (x, y))
    frame.blit(FONT.render(game.objective_text(), True, FRAGMENT_COLOR if game.fragment_holder else (238, 238, 246)), (x, y + 20))
    if remaining is not None:
        critical = remaining <= 10.0
        color = (255, 96, 96) if critical else (255, 214, 112)
        clock_img = FONT.render(f"COLLAPSE  {_fmt_clock(remaining)}", True, color)
        frame.blit(clock_img, (x, y + 46))
        frame.blit(SMALL.render(f"x{rate:g} underground", True, (150, 170, 180)), (x + clock_img.get_width() + 14, y + 49))
    frame.blit(SMALL.render("ESC/B pause  LMB/stick move  RMB/SPACE/A weapon", True, (150, 170, 180)), (x, y + 76))


def _draw_pause(frame, selected, reason):
    shade = pygame.Surface((W, H), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 170))
    frame.blit(shade, (0, 0))
    title = BIG.render("DIVE PAUSED", True, (238, 238, 246))
    frame.blit(title, title.get_rect(center=(W // 2, H // 2 - 96)))
    if reason:
        sub = SMALL.render(reason, True, (170, 190, 200))
        frame.blit(sub, sub.get_rect(center=(W // 2, H // 2 - 62)))
    rects = []
    labels = ("RESUME", "RETREAT TO SURFACE (fragment stays below)")
    for i, label in enumerate(labels):
        r = pygame.Rect(0, 0, 560, 46)
        r.center = (W // 2, H // 2 - 10 + i * 58)
        active = i == selected
        pygame.draw.rect(frame, (26, 44, 52) if active else (12, 18, 22), r)
        pygame.draw.rect(frame, (120, 220, 230) if active else (60, 80, 90), r, 2)
        img = FONT.render(label, True, (240, 246, 248) if active else (170, 180, 186))
        frame.blit(img, img.get_rect(center=r.center))
        rects.append(r)
    hint = SMALL.render("Collapse clock is frozen while paused", True, (150, 170, 180))
    frame.blit(hint, hint.get_rect(center=(W // 2, H // 2 + 112)))
    return rects


def _draw_outro(frame, outcome):
    text, color = {
        "recovered": ("FRAGMENT RECOVERED — CLIMBING TO THE SURFACE", FRAGMENT_COLOR),
        "retreat": ("RETREAT — THE PARTY CLIMBS OUT EMPTY-HANDED", (238, 238, 246)),
        "downed": ("YOU WERE DOWNED — THE PARTY DRAGS YOU TO THE SURFACE", (255, 150, 130)),
        "collapse": ("COLLAPSE REACHED THE RUIN", (255, 96, 96)),
    }.get(outcome, ("RETURNING TO THE SURFACE", (238, 238, 246)))
    shade = pygame.Surface((W, H), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 150))
    frame.blit(shade, (0, 0))
    img = BIG.render(text, True, color)
    frame.blit(img, img.get_rect(center=(W // 2, H // 2)))


# Gamepad (the host has already opened its controllers).  Left stick moves,
# A uses a weapon / confirms, B or Start pauses, D-pad picks pause options.
_CONTROLLER_AXIS = getattr(pygame, "CONTROLLERAXISMOTION", -101)


def _pad_event_types() -> tuple[set, set]:
    """SDL reports a game controller as a joystick too; listen to one family only."""
    try:
        from pygame._sdl2 import controller as sdl_controller
        if sdl_controller.get_init() and any(sdl_controller.is_controller(i) for i in range(sdl_controller.get_count())):
            return {_CONTROLLER_AXIS}, {getattr(pygame, "CONTROLLERBUTTONDOWN", -102)}
    except Exception:
        pass
    return {pygame.JOYAXISMOTION}, {pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION}


def _pad_action(e) -> str | None:
    if e.type == pygame.JOYHATMOTION:
        return {1: "up", -1: "down"}.get(int(e.value[1]))
    button = int(getattr(e, "button", -1))
    if e.type == pygame.JOYBUTTONDOWN:
        return {0: "confirm", 1: "back", 6: "pause", 7: "pause"}.get(button)
    mapping = {
        getattr(pygame, "CONTROLLER_BUTTON_A", 0): "confirm",
        getattr(pygame, "CONTROLLER_BUTTON_B", 1): "pause",
        getattr(pygame, "CONTROLLER_BUTTON_START", 6): "pause",
        getattr(pygame, "CONTROLLER_BUTTON_DPAD_UP", 11): "up",
        getattr(pygame, "CONTROLLER_BUTTON_DPAD_DOWN", 12): "down",
    }
    return mapping.get(button)


def run_expedition(spec: dict, window: pygame.Surface | None = None) -> dict:
    """Run one archive-ruin dive in the host's current window.

    ``spec`` keys: ``seed`` (int), ``depth`` (floors, default 2),
    ``collapse_remaining`` (seconds or None), ``collapse_rate`` (default 0.25),
    ``site_label`` (str).

    Returns ``{"outcome", "wall_seconds", "collapse_charged", "floors_reached",
    "treasure"}``.  ``outcome`` is one of ``DIVE_OUTCOMES``.  The host decides
    what the outcome means; this function never quits pygame or the process.
    """
    window = window or pygame.display.get_surface()
    if window is None:
        raise RuntimeError("run_expedition needs an active pygame display")
    init_fonts()
    init_audio(own_mixer=False)
    rate = float(spec.get("collapse_rate", DIVE_COLLAPSE_RATE))
    start_remaining = spec.get("collapse_remaining")
    start_remaining = None if start_remaining is None else max(0.0, float(start_remaining))
    auto_frames = int(spec.get("auto_frames", 0) or 0)  # QA hook: bounded headless runs

    game = Game(expedition={"seed": spec.get("seed", 0), "depth": spec.get("depth", DIVE_DEFAULT_DEPTH)})
    frame = _new_frame()
    clock = pygame.time.Clock()
    rect = present_rect(window.get_size())
    wall_start = time.perf_counter()
    charged = 0.0
    paused = False
    pause_reason = ""
    pause_sel = 0
    pause_rects: list[pygame.Rect] = []
    pad_axes: dict[int, float] = {}
    axis_events, button_events = _pad_event_types()
    outcome = None
    frames = 0
    pygame.event.clear()
    try:
        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)
    except pygame.error:
        pass

    while outcome is None:
        dt = min(0.05, clock.tick(60) / 1000.0)
        frames += 1
        attack_pressed = False
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                # Closing the window mid-dive counts as a retreat; the host then
                # sees its own QUIT on the next frame via the re-posted event.
                outcome = "retreat"
                pygame.event.post(pygame.event.Event(pygame.QUIT))
                break
            if e.type == getattr(pygame, "WINDOWFOCUSLOST", -1) and not paused:
                paused, pause_reason, pause_sel = True, "Window focus lost", 0
            elif e.type == pygame.KEYDOWN:
                if paused:
                    if e.key in (pygame.K_ESCAPE, pygame.K_p):
                        paused = False
                    elif e.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                        pause_sel = 1 - pause_sel
                    elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_e):
                        if pause_sel == 0:
                            paused = False
                        else:
                            outcome = "retreat"
                elif e.key in (pygame.K_ESCAPE, pygame.K_p):
                    paused, pause_reason, pause_sel = True, "", 0
                elif e.key == pygame.K_SPACE:
                    attack_pressed = True
                elif e.key == pygame.K_m:
                    _toggle_mute()
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if paused and e.button == 1:
                    pos = window_to_frame(e.pos, rect)
                    for i, r in enumerate(pause_rects):
                        if pos is not None and r.collidepoint(pos):
                            if i == 0:
                                paused = False
                            else:
                                outcome = "retreat"
                elif not paused and e.button == 3:
                    attack_pressed = True
            elif e.type == pygame.MOUSEMOTION and paused:
                pos = window_to_frame(e.pos, rect)
                for i, r in enumerate(pause_rects):
                    if pos is not None and r.collidepoint(pos):
                        pause_sel = i
            elif e.type in axis_events:
                pad_axes[int(e.axis)] = float(e.value) / (32767.0 if e.type == _CONTROLLER_AXIS else 1.0)
            elif e.type in button_events:
                action = _pad_action(e)
                if paused:
                    if action == "confirm":
                        if pause_sel == 0:
                            paused = False
                        else:
                            outcome = "retreat"
                    elif action in ("back", "pause"):
                        paused = False
                    elif action in ("up", "down"):
                        pause_sel = 1 - pause_sel
                elif action == "confirm":
                    attack_pressed = True
                elif action == "pause":
                    paused, pause_reason, pause_sel = True, "", 0
        if outcome is not None:
            break

        window = pygame.display.get_surface() or window
        if not paused:
            mouse_target = None
            if pygame.mouse.get_pressed()[0]:
                mouse_target = window_to_frame(pygame.mouse.get_pos(), rect)
            sx, sy = pad_axes.get(0, 0.0), pad_axes.get(1, 0.0)
            stick = (sx, sy) if (sx * sx + sy * sy) > 0.35 * 0.35 else None
            game.update(dt, pygame.key.get_pressed(), attack_pressed=attack_pressed, mouse_target=mouse_target, stick=stick)
            charged += dt * rate
            if game.result is not None:
                outcome = game.result
            elif start_remaining is not None and charged >= start_remaining:
                outcome = "collapse"

        remaining = None if start_remaining is None else max(0.0, start_remaining - charged)
        frame.fill((8, 10, 14))
        game.draw(frame)
        _draw_dive_hud(frame, game, spec, remaining, rate)
        pause_rects = _draw_pause(frame, pause_sel, pause_reason) if paused else []
        rect = present(window, frame)
        pygame.display.flip()
        if auto_frames and frames >= auto_frames and outcome is None:
            outcome = "retreat"

    # Short outro card so the handoff back to the surface reads clearly.
    if outcome != "retreat" or not auto_frames:
        _draw_outro(frame, outcome)
        rect = present(pygame.display.get_surface() or window, frame)
        pygame.display.flip()
        if not auto_frames:
            pygame.time.wait(900)
    pygame.event.clear((pygame.KEYDOWN, pygame.KEYUP, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION))
    return {
        "outcome": outcome,
        "wall_seconds": max(0.0, time.perf_counter() - wall_start),
        "collapse_charged": charged,
        "floors_reached": game.room_index + 1,
        "treasure": sum(p.treasure for p in game.players),
    }
