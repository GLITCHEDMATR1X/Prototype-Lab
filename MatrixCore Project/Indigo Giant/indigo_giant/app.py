from __future__ import annotations

import argparse
import os
import sys
import hashlib
import math
import time
from collections import deque
from pathlib import Path

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.gui.OnscreenText import OnscreenText
import numpy as np
from . import settings as settings_mod
from . import survival
from .survival import SurvivalMixin
from .desert import DesertMixin
from .audio import AudioMixin
from .daycycle import DayCycleMixin
from .journey import JourneyMixin
from .places import PlacesMixin      # Pass 46: hidden places across the wide world
from .endgame import EndgameMixin    # Pass 47: the pale bloom and the Red Giant's last meal
from .wild import GiantsLifeMixin    # Pass 48: hunger, mood, tracks, crumbs and the cold night
from .fight import FightMixin        # Pass 53: giant stamina, knock-outs, a day's calm, poison
from .glow import GlowMixin          # Pass 59: Indigo's night glow, and the glow you can carry
from .crimson import CrimsonMixin    # Pass 60: the red one's crimson powers at night
from .lore import LoreMixin          # Pass 61: etchings - little notes of lore across the desert
from .gleebs import GleebsMixin      # Pass 61: the end - Gleebs comes for Nyx and Orbit
from . import fight
from .frontend import FrontendMixin  # Pass 50: title screen, settings, key rebinding
from .teach import TeachMixin        # Pass 50: first-dawn hints
from .savegame import SaveMixin
from .hud import HudMixin
from . import controls
from . import locomotion                  # Pass 52: feet that match the ground
from . import desert_world
from . import savegame
from .skinned_actor import SkinnedHumanoidActor as HumanoidActor   # Pass 45: GPU skinning
from . import paths                 # Pass 62: where the game files are
from .holoverse_host import HoloVerseHostedMixin   # Pass 63: the game as a HoloVerse dimension
from panda3d.core import (
    AmbientLight, DirectionalLight, Geom, GeomNode, GeomTriangles,
    GeomVertexData, GeomVertexFormat, GeomVertexWriter, Shader,
    ModifierButtons, PerlinNoise2, Point3, Vec3, Vec4, TextNode, TransparencyAttrib, BitMask32, loadPrcFileData,
    Filename, AntialiasAttrib,
)

SEED = 27183
CHUNK_CELLS = 32
SPACING = 1.8
CHUNK_SIZE = CHUNK_CELLS * SPACING
HUMAN_LOAD_RADIUS = 3
GIANT_NEAR_RADIUS = 3
GIANT_FAR_RADIUS = 7
# Backwards-compatible name used by the existing vision smoke test.
GIANT_LOAD_RADIUS = GIANT_FAR_RADIUS
FAR_CHUNK_CELLS = 8
CHUNKS_PER_FRAME = 1
STREAM_BUDGET_MS = 3.5          # Pass 46: per-frame time for building ground chunks
GIANT_SCALE = locomotion.GIANT_SCALE
# Pass 52: every speed comes from locomotion.GAITS, chosen so the feet match the ground
# (each clip is driven by the distance covered, never by time). See locomotion.py.
HUMAN_WALK_SPEED = locomotion.speed('human', 'walk')
HUMAN_JOG_SPEED = locomotion.speed('human', 'jog')
HUMAN_SPRINT_SPEED = locomotion.speed('human', 'sprint')
HUMAN_CROUCH_SPEED = locomotion.speed('human', 'crouch')
GIANT_HEAVY_SPEED_FACTOR = 0.82
GIANT_WALK_SPEED = locomotion.speed('giant', 'walk')
GIANT_JOG_SPEED = locomotion.speed('giant', 'jog')
GIANT_SPRINT_SPEED = locomotion.speed('giant', 'sprint')
GIANT_CROUCH_SPEED = locomotion.speed('giant', 'crouch')
# playback rates the gaits end up at (for reference / older call sites)
GIANT_WALK_ANIM_RATE = locomotion.playback_rate('Walk_Loop', GIANT_WALK_SPEED, GIANT_SCALE)
GIANT_JOG_ANIM_RATE = locomotion.playback_rate(locomotion.gait('giant', 'jog')[0], GIANT_JOG_SPEED, GIANT_SCALE)
GIANT_SPRINT_ANIM_RATE = locomotion.playback_rate(locomotion.gait('giant', 'sprint')[0], GIANT_SPRINT_SPEED, GIANT_SCALE)

HUMAN_ACCELERATION = 18.0         # Pass 58 (was 14): standing to jog in ~0.3 s at the quicker speeds
HUMAN_DECELERATION = 26.0         # (was 20)

# Interactive giant inertia. Human locomotion remains the accepted immediate-response baseline.
GIANT_ACCELERATION = 1.65
GIANT_BRAKING = 2.35
GIANT_TURN_RATE_DEG = 58.0
GIANT_PIVOT_BONUS_DEG = 52.0      # extra turn rate when standing still (pivot in place)
HUMAN_TURN_RATE_DEG = 720.0
MOUSE_ORBIT_SENSITIVITY = 0.25    # degrees per pixel while the right mouse button is held

# Red Giant hunter foundation. Detection/stealth will be expanded later; for now the
# hostile giant pursues the human when inside a broad awareness radius and attempts
# a stomp at close range. It reuses the same heavy locomotion model as the Indigo Giant.
RED_DETECTION_RANGE = 115.0
RED_STOMP_RANGE = 2.8
RED_STOMP_COOLDOWN = 2.4
HUMAN_MAX_HEALTH = 100.0
RED_STOMP_DAMAGE = 50.0
RED_STOMP_HIT_TIME = 0.38
RED_APPROACH_WALK_RANGE = 10.0
RED_SPAWN_DISTANCE = 48.0

# Giant-vs-giant melee foundation. Values are intentionally simple and inspectable.
GIANT_MELEE_RANGE = 5.4
GIANT_MELEE_DAMAGE = 25.0
GIANT_MAX_HEALTH = 100.0
GIANT_ATTACK_COOLDOWN = 0.28
# Pass 58: when each blow lands in its clip (seconds) and how hard (x a punch). The punches now
# land when the fist is out (jab 0.20 s, cross 0.30 s into the clip), not a beat later.
MELEE_HITS = {
    'Punch_Jab': ((0.24, 1.0),),
    'Punch_Cross': ((0.34, 1.0),),
    'Sword_Attack': ((0.45, 1.3), (0.92, 1.5)),     # Indigo's hammer blow: a swing, then the backhand that drives it back
}
RED_KNOCKOUT_DURATION = fight.RED_KO_TIME      # Pass 53: 150 s (was 300)
RED_RECOVERY_STAND_TIME = 1.4
RED_FLEE_SAFE_DISTANCE = 135.0
INDIGO_DEFENSE_TRIGGER_RANGE = 42.0
INDIGO_DEFENSE_STOP_RANGE = 4.8
RED_ENGAGE_INDIGO_RANGE = 12.0

# Jump foundation. World units are treated as metres for the human-scale calibration.
# The giant deliberately gets a much lower jump relative to its body height so it retains mass.
WORLD_GRAVITY = 9.81
HUMAN_JUMP_VELOCITY = 4.0
GIANT_JUMP_VELOCITY = 6.2
HUMAN_JUMP_START_TIME = 0.24
HUMAN_JUMP_LAND_TIME = 0.34
GIANT_JUMP_START_TIME = 0.42
GIANT_JUMP_LAND_TIME = 0.58

# Sand-contact tuning. Exact persistence is a gameplay abstraction: active dune winds
# can erase footprints, while larger/deeper impressions are kept longer for tracking.
HUMAN_PRINT_LIFETIME = 42.0
GIANT_PRINT_LIFETIME = 180.0
HUMAN_STEP_SPACING = 0.52
# Preserve the accepted walk footprint spacing; faster gaits get a slightly longer stride
# based on speed increase relative to the supplied animation-cycle cadence.
HUMAN_FAST_STEP_SPACING = 1.40     # Pass 52: prints now fall where the feet land; these remain for old call sites
HUMAN_CROUCH_STEP_SPACING = 0.45
GIANT_STEP_SPACING = HUMAN_STEP_SPACING * GIANT_SCALE
GIANT_FAST_STEP_SPACING = HUMAN_FAST_STEP_SPACING * GIANT_SCALE
GIANT_CROUCH_STEP_SPACING = HUMAN_CROUCH_STEP_SPACING * GIANT_SCALE
GROUND_SINK_FRACTION = 0.006
MAX_FOOTPRINTS = 240
FOOTPRINT_FADE_STEP = 0.25
STAMINA_JUMP_COST = 10.0

SKETCH_LIGHT_DIR = Vec3(-0.42, 0.22, 0.88)
FOG_COLOR = Vec4(0.91, 0.88, 0.82, 1.0)
HUMAN_FOG_DENSITY = 0.013
GIANT_FOG_DENSITY = 0.0048
FOG_TRANSITION_SPEED = 1.5
HUMAN_SOFT_START = 95.0
HUMAN_SOFT_END = 175.0
GIANT_SOFT_START = 175.0
GIANT_SOFT_END = 360.0

# Third-person camera profiles. Giant mode is intentionally offset over one shoulder.
HUMAN_CAMERA_DISTANCE = 7.5
HUMAN_CAMERA_PITCH = -15.0
HUMAN_CAMERA_FOCUS = 0.78
HUMAN_CAMERA_SIDE = 0.0
HUMAN_ZOOM_MIN = 5.5
HUMAN_ZOOM_MAX = 18.0
GIANT_CAMERA_DISTANCE = 38.0
GIANT_CAMERA_PITCH = -10.0
GIANT_CAMERA_FOCUS = 0.52
GIANT_CAMERA_SIDE = 7.5
GIANT_CAMERA_LEAD = 5.5
GIANT_ZOOM_MIN = 20.0
GIANT_ZOOM_MAX = 65.0
CAMERA_SMOOTH_RATE = 6.0
# Pass 58: look around and up. Drag with the right mouse (or the arrow keys): down to look down
# on your character, up past level to lower the camera behind it and look up at the sky, the
# giants and the towers. The camera stays anchored on your character and never goes into the sand.
CAMERA_PITCH_MIN = -70.0          # looking down (was -58)
CAMERA_PITCH_MAX = 55.0           # looking up (was -5: you could never look above the horizon)
CAMERA_ORBIT_LOW = 6.0            # past this the camera stops sinking and tilts up instead
CAMERA_LOOKUP_CLOSER = 0.35       # and comes in this much closer as you look right up
CAMERA_GROUND_CLEAR = {'human': 0.45, 'giant': 2.5}

# Sun/shadow foundation. Automatic time-of-day is intentionally deferred; these
# angles are directly mutable so the later day/night clock can drive the same system.
SUN_AZIMUTH_DEG = 70.0
SUN_ELEVATION_DEG = 48.0
SHADOW_LIFT = 0.028
SHADOW_UPDATE_HZ = 30.0          # shadow-map camera refit
SHADE_QUERY_HZ = 10.0            # Pass 44: shade proxies (heat) - plenty for walking pace
SHADOW_MAP_SIZE = 1024
SHADOW_FILM_SIZE = 110.0
SHADOW_CAMERA_DISTANCE = 90.0
SHADOW_CAMERA_MASK = BitMask32.bit(2)
TERRAIN_EDGE_INK = 0.12       # Pass 44: only a faint pencil line on the ground (1.0 inked it black at low pitch)



def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def approach(current: float, target: float, amount: float) -> float:
    if current < target:
        return min(target, current + amount)
    return max(target, current - amount)


def giant_start_xy():
    return CHUNK_SIZE * 0.95, CHUNK_SIZE * 0.80


def human_start_xy():
    """The human starts just beside the giant's nearest foot, for scale readability."""
    gx, gy = giant_start_xy()
    return gx - 1.55, gy - 0.55


def heading_toward(dx: float, dy: float) -> float:
    """Panda heading (degrees) that makes an actor face the world direction (dx, dy).

    The actors' front is local +Y and Panda's H turns +Y toward -X, so the heading is
    atan2(-dx, dy).  Pass 41: every mover uses this and heading_forward() so what an
    actor faces and where it walks always agree (W no longer walks backwards).
    """
    return math.degrees(math.atan2(-dx, dy))


def heading_forward(h_deg: float) -> Vec3:
    """Unit world direction an actor with heading h_deg faces (inverse of heading_toward)."""
    r = math.radians(h_deg)
    return Vec3(-math.sin(r), math.cos(r), 0.0)


def shortest_angle_delta_deg(current: float, target: float) -> float:
    return (target - current + 180.0) % 360.0 - 180.0


class TerrainField:
    """Rolling dune field.

    Pass 42: calmer.  The old field (42 m swells of +/-10.5 m, sharp |noise| creases) had a
    median slope of 17 deg and faces up to 45 deg.  Now: long 96 m swells of +/-6.5 m, dune
    crests rounded with a soft |x|, fine ripple only 0.25 m.  Median slope ~5 deg, 95% of
    the ground under ~10 deg, steepest ~16 deg.  Landmarks sit on levelled discs.
    """

    def __init__(self, seed: int = SEED):
        self.seed = seed
        self.macro = PerlinNoise2(96.0, 96.0, 256, seed)
        self.ridge = PerlinNoise2(40.0, 40.0, 256, seed + 31)
        self.detail = PerlinNoise2(14.0, 14.0, 256, seed + 79)
        self.flat_zones: list[tuple[float, float, float, float, float]] = []
        self._zone_grid: dict[tuple[int, int], list] = {}      # 128 m buckets -> nearby zones
        self._clear_grid: dict[tuple[int, int], list] = {}     # Pass 46: keep-clear discs (places)

    def _raw_height(self, wx: float, wy: float) -> float:
        a = self.macro(wx, wy)
        b = self.ridge(wx, wy)
        c = self.detail(wx, wy)
        broad = 6.5 * a
        crest = 2.6 * (0.52 - math.sqrt(b * b + 0.015))     # soft |b|: rounded dune crests
        ripple = 0.25 * c
        r = math.sqrt(wx * wx + wy * wy)
        shallow_basin = -1.6 * math.exp(-(((r / 58.0) - 0.58) ** 2) / 0.045)
        return broad + crest + ripple + shallow_basin

    def add_flat_zone(self, x: float, y: float, inner: float, outer: float, on_current: bool = False):
        """Level the ground to one height inside `inner`, blending back out by `outer`.
        on_current (Pass 55, shells): level to the ground as it already is (other zones included),
        so a small zone inside a levelled landmark or place stays at that level."""
        h = self.height if on_current else self._raw_height
        samples = [h(x, y)] + [
            h(x + math.cos(k * math.pi / 4) * inner, y + math.sin(k * math.pi / 4) * inner)
            for k in range(8)]
        zone = (x, y, inner, outer, sum(samples) / len(samples))
        self.flat_zones.append(zone)
        for gx in range(int(math.floor((x - outer) / 128.0)), int(math.floor((x + outer) / 128.0)) + 1):
            for gy in range(int(math.floor((y - outer) / 128.0)), int(math.floor((y + outer) / 128.0)) + 1):
                self._zone_grid.setdefault((gx, gy), []).append(zone)

    def add_clear_zone(self, x: float, y: float, radius: float):
        """Pass 46: nothing else (finds, shells, branches) is placed inside this disc."""
        for gx in range(int(math.floor((x - radius) / 128.0)), int(math.floor((x + radius) / 128.0)) + 1):
            for gy in range(int(math.floor((y - radius) / 128.0)), int(math.floor((y + radius) / 128.0)) + 1):
                self._clear_grid.setdefault((gx, gy), []).append((x, y, radius))

    def is_clear(self, wx: float, wy: float) -> bool:
        for x, y, r in self._clear_grid.get((int(math.floor(wx / 128.0)), int(math.floor(wy / 128.0))), ()):
            if (wx - x) ** 2 + (wy - y) ** 2 < r * r:
                return False
        return True

    def height(self, wx: float, wy: float) -> float:
        h = self._raw_height(wx, wy)
        zones = self._zone_grid.get((int(math.floor(wx / 128.0)), int(math.floor(wy / 128.0))))
        if not zones:
            return h
        for zx, zy, inner, outer, zh in zones:
            dx, dy = wx - zx, wy - zy
            if dx > outer or dx < -outer or dy > outer or dy < -outer:
                continue
            d = math.sqrt(dx * dx + dy * dy)
            if d >= outer:
                continue
            t = 1.0 if d <= inner else (outer - d) / (outer - inner)
            t = t * t * (3.0 - 2.0 * t)
            h += (zh - h) * t
        return h

    def normal(self, wx: float, wy: float) -> Vec3:
        e = SPACING
        dzdx = (self.height(wx + e, wy) - self.height(wx - e, wy)) / (2.0 * e)
        dzdy = (self.height(wx, wy + e) - self.height(wx, wy - e)) / (2.0 * e)
        n = Vec3(-dzdx, -dzdy, 1.0)
        n.normalize()
        return n


def terrain_color(height: float, normal: Vec3) -> Vec4:
    slope = 1.0 - normal.z
    if height < -2.0:
        base = (0.73, 0.76, 0.72)
    elif height < 2.5:
        base = (0.82, 0.76, 0.68)
    elif height < 6.0:
        base = (0.80, 0.69, 0.68)
    else:
        base = (0.84, 0.82, 0.74)
    darken = clamp(slope * 0.30, 0.0, 0.22)
    return Vec4(base[0]-darken, base[1]-darken, base[2]-darken, 1.0)


_GRID_TRIANGLES: dict = {}
SKIRT_DEPTH = {'near': 3.0, 'far': 6.0}      # Pass 46: every chunk hangs a skirt


def _perimeter(cells: int) -> np.ndarray:
    """Grid indices around the chunk edge, in order (closed loop)."""
    verts = cells + 1
    ring = [(x, 0) for x in range(verts)] + [(cells, y) for y in range(1, verts)] \
        + [(x, cells) for x in range(cells - 1, -1, -1)] + [(0, y) for y in range(cells - 1, 0, -1)]
    return np.array([y * verts + x for x, y in ring], dtype=np.int64)


def _grid_triangles(cells: int) -> GeomTriangles:
    """Index list for a cells x cells grid plus its edge skirt; identical for every chunk.

    Pass 46: the skirt (a band of vertices hanging below the edge) now goes on near chunks
    too, drawn from both sides, so no crack between chunks or LODs can ever show the sky.
    """
    tris = _GRID_TRIANGLES.get(cells)
    if tris is None:
        verts = cells + 1
        y, x = np.meshgrid(np.arange(cells), np.arange(cells), indexing='ij')
        i = (y * verts + x).reshape(-1)
        grid = np.stack([i, i + 1, i + verts, i + 1, i + verts + 1, i + verts], axis=1).reshape(-1)
        top = _perimeter(cells)
        low = verts * verts + np.arange(len(top))
        nxt = np.roll(np.arange(len(top)), -1)
        a, b, al, bl = top, top[nxt], low, low[nxt]
        skirt = np.stack([a, b, al, b, bl, al,          # one side
                          a, al, b, b, al, bl], axis=1).reshape(-1)   # and the other
        inds = np.concatenate([grid, skirt])
        tris = GeomTriangles(Geom.UHStatic)
        tris.setIndexType(Geom.NT_uint16)
        array = tris.modifyVertices()
        array.setNumRows(len(inds))
        memoryview(array).cast('B')[:] = inds.astype(np.uint16).tobytes()
        _GRID_TRIANGLES[cells] = tris
    return tris


def _terrain_color_bytes(heights: np.ndarray, normal_z: np.ndarray) -> np.ndarray:
    """Vectorised terrain_color(): same bands and slope darkening, as 8-bit RGBA."""
    base = np.empty((len(heights), 3), dtype=np.float64)
    base[:] = (0.84, 0.82, 0.74)
    base[heights < 6.0] = (0.80, 0.69, 0.68)
    base[heights < 2.5] = (0.82, 0.76, 0.68)
    base[heights < -2.0] = (0.73, 0.76, 0.72)
    darken = np.clip((1.0 - normal_z) * 0.30, 0.0, 0.22)[:, None]
    rgb = (base - darken).astype(np.float32)
    rgba = np.concatenate([rgb, np.ones((len(heights), 1), dtype=np.float32)], axis=1)
    return np.floor(np.clip(rgba, 0.0, 1.0) * np.float32(255.0)).astype(np.uint8)


class ChunkBuild:
    """Pass 54: one ground chunk, built a few rows at a time.

    Sampling the terrain height is the slow part (~8 us a point, ~10 ms for a near chunk), so
    the streaming task works on it in slices of at most STREAM_BUDGET_MS per frame instead of
    stalling one frame for the whole chunk. The finished chunk is identical to building it
    in one go (build_chunk)."""

    def __init__(self, field: TerrainField, cx: int, cy: int, cells: int = CHUNK_CELLS, far_lod: bool = False):
        self.field, self.cx, self.cy, self.cells, self.far_lod = field, cx, cy, cells, far_lod
        self.coord, self.lod = (cx, cy), ('far' if far_lod else 'near')
        self.verts = verts = cells + 1
        self.spacing = CHUNK_SIZE / cells
        self.ox, self.oy = cx * CHUNK_SIZE, cy * CHUNK_SIZE
        # Pass 37: each height sampled once. Near chunks: the vertex spacing equals the normal's
        # finite-difference step, so the neighbours come from the same padded grid. Far chunks
        # keep the exact SPACING step for their normals.
        self.reuse_grid = abs(self.spacing - SPACING) < 1e-9
        if self.reuse_grid:
            self.rows = verts + 2
            self.grid = np.empty((self.rows, self.rows), dtype=np.float64)
        else:
            self.rows = verts
            self.heights = np.empty(verts * verts, dtype=np.float64)
            self.nx = np.empty(verts * verts)
            self.ny = np.empty(verts * verts)
        self.row = 0

    def step(self, deadline: float) -> bool:
        """Sample rows until the deadline (time.perf_counter()). True once every row is done."""
        field, sp = self.field, self.spacing
        while self.row < self.rows:
            if self.reuse_grid:
                gy = self.row
                wy = self.oy + (gy - 1) * sp
                row = self.grid[gy]
                ox = self.ox - sp
                for gx in range(self.rows):
                    row[gx] = field.height(ox + gx * sp, wy)
            else:
                y = self.row
                wy = self.oy + y * sp
                k = y * self.verts
                for x in range(self.verts):
                    wx = self.ox + x * sp
                    self.heights[k] = field.height(wx, wy)
                    n = field.normal(wx, wy)
                    self.nx[k], self.ny[k] = n.x / n.z, n.y / n.z
                    k += 1
            self.row += 1
            if time.perf_counter() >= deadline:
                break
        return self.row >= self.rows

    def finish(self):
        cells, verts, tag = self.cells, self.verts, self.lod
        if self.reuse_grid:
            grid = self.grid
            core = grid[1:-1, 1:-1]
            dzdx = (grid[1:-1, 2:] - grid[1:-1, :-2]) / (2.0 * SPACING)
            dzdy = (grid[2:, 1:-1] - grid[:-2, 1:-1]) / (2.0 * SPACING)
            heights = core.reshape(-1).copy()
            nx, ny = -dzdx.reshape(-1), -dzdy.reshape(-1)
        else:
            heights, nx, ny = self.heights, self.nx, self.ny
        fmt = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData(f"chunk_{tag}_{self.cx}_{self.cy}", fmt, Geom.UHStatic)
        perim = _perimeter(cells)
        vdata.setNumRows(verts * verts + len(perim))
        block = np.empty(verts * verts, dtype=_FRAME_VERTEX_DTYPE)
        inv_len = 1.0 / np.sqrt(nx * nx + ny * ny + 1.0)
        normals = np.stack([nx * inv_len, ny * inv_len, inv_len], axis=1)
        xs = np.tile(np.arange(verts) * self.spacing, verts)
        ys = np.repeat(np.arange(verts) * self.spacing, verts)
        block["p"] = np.stack([xs, ys, heights], axis=1)
        block["n"] = normals
        block["c"] = _terrain_color_bytes(heights, normals[:, 2])
        skirt = block[perim].copy()                      # the edge, dropped straight down
        skirt["p"][:, 2] -= SKIRT_DEPTH[tag]
        memoryview(vdata.modifyArray(0)).cast('B')[:] = block.tobytes() + skirt.tobytes()
        signature = hashlib.sha256("".join(f"{z:.6f};" for z in heights.tolist()).encode("ascii"))
        geom = Geom(vdata)
        geom.addPrimitive(_grid_triangles(cells))
        node = GeomNode(f"chunk_{tag}_{self.cx}_{self.cy}")
        node.addGeom(geom)
        return node, signature.hexdigest()


def build_chunk(field: TerrainField, cx: int, cy: int, cells: int = CHUNK_CELLS, far_lod: bool = False):
    """Build one deterministic chunk in one go. Far LOD samples the same global field with fewer cells."""
    job = ChunkBuild(field, cx, cy, cells, far_lod)
    job.step(float('inf'))
    return job.finish()


def world_to_chunk(v: float) -> int:
    return math.floor(v / CHUNK_SIZE)


# Pass 58: the outline of a sole, heel to toe: (along the foot -0.5 heel .. 0.5 toe, across it in
# half-widths, + = the outer edge). The arch on the inner side is narrow, the ball is wide, the
# big-toe side reaches furthest. Mirrored for the left foot.
SOLE_OUTLINE = (
    (-0.50, 0.00), (-0.47, 0.42), (-0.40, 0.66), (-0.29, 0.72), (-0.14, 0.66), (0.02, 0.74),
    (0.17, 0.92), (0.30, 0.95), (0.39, 0.80), (0.45, 0.55), (0.49, 0.22), (0.50, -0.12),
    (0.47, -0.48), (0.38, -0.78), (0.24, -0.88), (0.10, -0.74), (-0.02, -0.46), (-0.15, -0.40),
    (-0.29, -0.60), (-0.41, -0.60), (-0.48, -0.34),
)
SOLE_HEEL = (-0.30, 0.04)          # the deepest points of a print: heel and ball...
SOLE_BALL = (0.24, 0.02)
SOLE_ARCH = (-0.05, 0.12)          # ...with the shallow arch between them (toward the outer edge)
SOLE_FROM_ANKLE = 0.25             # prints are stamped at the ankle joint, a quarter of a foot behind its middle


def _sole_part(u: float) -> int:
    """Which pad an outline point belongs to: 0 heel, 1 arch, 2 ball."""
    return 0 if u < -0.17 else (2 if u > 0.08 else 1)


class SandFootprint:
    """A shallow foot-shaped imprint that fades as wind restores the surface.

    Pass 58: shaped like a sole (heel, arch, ball, toes; left and right feet mirrored) and laid
    along the way the walker faces. It used to be an oval laid with a mirrored heading, so at
    a diagonal it lay across the path."""
    def __init__(self, parent, field: TerrainField, center: Point3, heading_deg: float,
                 length: float, width: float, depth: float, lifetime: float, owner: str, side: str = 'left'):
        self.age = 0.0
        self.lifetime = lifetime
        self.owner = owner
        self.depth = depth
        self.root = parent.attachNewNode(f"{owner}_footprint")
        self.root.hide(SHADOW_CAMERA_MASK)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.root.setTwoSided(True)
        self.root.setDepthOffset(1)
        self.root.setBin('fixed', 20)
        self.root.setPos(center.x, center.y, center.z)
        node = self._build(field, center, heading_deg, length, width, depth, owner, side)
        self.geom_np = self.root.attachNewNode(node)

    def _build(self, field, center, heading_deg, length, width, depth, owner, side='left'):
        # A low-detail sole: two dark pads (heel and ball) inside an inner and an outer ring
        # following the sole's outline. Vertex positions sample the underlying terrain so the
        # print follows slopes instead of floating flat.
        segments = len(SOLE_OUTLINE)
        fmt = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData(f"{owner}_footprint_geom", fmt, Geom.UHDynamic)
        rows = 3 + segments * 2
        vdata.setNumRows(rows)
        vw = GeomVertexWriter(vdata, 'vertex')
        nw = GeomVertexWriter(vdata, 'normal')
        cw = GeomVertexWriter(vdata, 'color')
        h = math.radians(heading_deg)
        fwd = Vec3(-math.sin(h), math.cos(h), 0)          # the game's heading convention (heading_forward)
        right = Vec3(math.cos(h), math.sin(h), 0)
        outer_side = 1.0 if side == 'right' else -1.0     # the outer edge of a right foot is on its right
        base_z = field.height(center.x, center.y)
        large_owner = owner in ('giant', 'red')
        dark = Vec4(0.34, 0.29, 0.30, 0.78 if large_owner else 0.66)
        mid = Vec4(0.49, 0.42, 0.41, 0.64 if large_owner else 0.52)
        rim = Vec4(0.61, 0.54, 0.51, 0.34)

        def place(u, v, lift):
            # u along the sole (heel -0.5 .. toe 0.5), v across it in half-widths (+ = outer edge)
            local_f = (u + SOLE_FROM_ANKLE) * length
            local_r = v * outer_side * width * 0.5
            wx = center.x + fwd.x * local_f + right.x * local_r
            wy = center.y + fwd.y * local_f + right.y * local_r
            vw.addData3(wx - center.x, wy - center.y, field.height(wx, wy) - base_z + lift)
            nw.addData3(field.normal(wx, wy))

        # Render just above the sampled sand surface and use a concave color gradient.
        # This avoids z-fighting/occlusion while keeping the formation visually shallow.
        pads = (SOLE_HEEL, SOLE_ARCH, SOLE_BALL)
        arch = mid + (rim - mid) * 0.55              # the arch barely touches the sand
        for k, pad in enumerate(pads):
            place(pad[0], pad[1], 0.020)
            cw.addData4(arch if k == 1 else dark)
        for ring_i, scale in enumerate((0.58, 1.0)):
            for u, v in SOLE_OUTLINE:
                # the inner ring shrinks toward the pad under it (heel, arch or ball)
                cu, cv = pads[_sole_part(u)]
                place(cu + (u - cu) * scale, cv + (v - cv) * scale, 0.019 if ring_i == 0 else 0.018)
                cw.addData4((arch if _sole_part(u) == 1 else mid) if ring_i == 0 else rim)

        tris = GeomTriangles(Geom.UHDynamic)
        inner_start = 3
        outer_start = 3 + segments
        for i in range(segments):
            j = (i + 1) % segments
            pad_i = _sole_part(SOLE_OUTLINE[i][0])
            pad_j = _sole_part(SOLE_OUTLINE[j][0])
            tris.addVertices(pad_i, inner_start + i, inner_start + j)
            if pad_i != pad_j:                       # where two pads' fans meet
                tris.addVertices(pad_i, inner_start + j, pad_j)
            tris.addVertices(inner_start + i, outer_start + i, outer_start + j)
            tris.addVertices(inner_start + i, outer_start + j, inner_start + j)
        tris.closePrimitive()
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode(f"{owner}_footprint_node")
        node.addGeom(geom)
        return node

    def update(self, dt: float):
        self.age += max(0.0, dt)
        p = clamp(self.age / self.lifetime, 0.0, 1.0)
        # Wind restoration is communicated as gradual loss of contrast.
        alpha = (1.0 - p) ** 1.35
        self.root.setColorScale(1, 1, 1, alpha)
        if p >= 1.0:
            self.root.removeNode()
            return False
        return True



_FRAME_VERTEX_DTYPE = np.dtype([("p", "<f4", 3), ("n", "<f4", 3), ("c", "u1", 4)])
assert _FRAME_VERTEX_DTYPE.itemsize == GeomVertexFormat.getV3n3c4().getArray(0).getStride()

class StylizedActorShadow:
    """Low-cost sketch shadow projected from animated joints along a sun ray."""
    SEGMENTS = (
        ('Head', 'neck_01', 0.18),
        ('neck_01', 'spine_03', 0.20),
        ('spine_03', 'pelvis', 0.34),
        ('clavicle_l', 'upperarm_l', 0.14), ('upperarm_l', 'lowerarm_l', 0.13), ('lowerarm_l', 'hand_l', 0.11),
        ('clavicle_r', 'upperarm_r', 0.14), ('upperarm_r', 'lowerarm_r', 0.13), ('lowerarm_r', 'hand_r', 0.11),
        ('pelvis', 'thigh_l', 0.18), ('thigh_l', 'calf_l', 0.16), ('calf_l', 'foot_l', 0.13),
        ('pelvis', 'thigh_r', 0.18), ('thigh_r', 'calf_r', 0.16), ('calf_r', 'foot_r', 0.13),
    )

    def __init__(self, parent, field: TerrainField, actor: HumanoidActor, owner: str):
        self.parent = parent
        self.field = field
        self.actor = actor
        self.owner = owner
        self.root = parent.attachNewNode(f'{owner}_sun_shadow')
        self.root.hide(SHADOW_CAMERA_MASK)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.root.setDepthOffset(2)
        self.root.setBin('transparent', 30)
        self.root.setDepthWrite(False)
        self.capsules = []
        self.last_extent = 0.0
        self._seg_index = None

    def clear(self):
        for child in self.root.getChildren():
            child.removeNode()
        self.capsules = []

    def _project(self, p: Point3, ray: Vec3) -> Point3:
        # Solve the ray/height-field intersection iteratively. This follows hills instead
        # of assuming a flat ground plane, while remaining cheap for our handful of joints.
        if ray.z >= -0.05:
            return Point3(p.x, p.y, self.field.height(p.x, p.y) + SHADOW_LIFT)
        t = max(0.0, (p.z - self.field.height(p.x, p.y)) / (-ray.z))
        t = min(t, 240.0)
        for _ in range(4):
            x = p.x + ray.x * t
            y = p.y + ray.y * t
            ground = self.field.height(x, y)
            nt = max(0.0, (p.z - ground) / (-ray.z))
            t = min(nt, 240.0)
        x = p.x + ray.x * t
        y = p.y + ray.y * t
        return Point3(x, y, self.field.height(x, y) + SHADOW_LIFT)

    def _capsule_geom(self, a: Point3, b: Point3, radius: float, alpha: float, index: int):
        dx, dy = b.x - a.x, b.y - a.y
        length = math.hypot(dx, dy)
        if length < 1e-5:
            dx, dy, length = 0.0, 1.0, 1.0
        rx, ry = -dy / length * radius, dx / length * radius
        # Slightly tapered quad. Overlap between limb pieces gives a hand-drawn darkening
        # without adding chaotic hatch lines.
        points = [
            (a.x + rx, a.y + ry), (b.x + rx, b.y + ry),
            (b.x - rx, b.y - ry), (a.x - rx, a.y - ry),
        ]
        fmt = GeomVertexFormat.getV3n3c4()
        vd = GeomVertexData(f'{self.owner}_shadow_{index}', fmt, Geom.UHDynamic)
        vd.setNumRows(4)
        vw, nw, cw = GeomVertexWriter(vd, 'vertex'), GeomVertexWriter(vd, 'normal'), GeomVertexWriter(vd, 'color')
        col = Vec4(0.055, 0.055, 0.065, alpha)
        for x, y in points:
            z = self.field.height(x, y) + SHADOW_LIFT
            vw.addData3(x, y, z)
            nw.addData3(self.field.normal(x, y))
            cw.addData4(col)
        tri = GeomTriangles(Geom.UHDynamic)
        tri.addVertices(0, 1, 2); tri.addVertices(0, 2, 3); tri.closePrimitive()
        geom = Geom(vd); geom.addPrimitive(tri)
        node = GeomNode(f'{self.owner}_shadow_piece_{index}'); node.addGeom(geom)
        return node

    def update(self, sun_ray: Vec3):
        # Pass 37: the visible shadow is the real shadow map; this proxy is kept for the
        # shade query (contains_xy).  While hidden, only the capsule data is refreshed
        # instead of rebuilding 15 dynamic GeomNodes per actor every shadow tick.
        build_geometry = not self.root.isHidden()
        if not build_geometry:
            self._update_fast(sun_ray)
            return
        self.clear()
        clip_t = self.actor.last_clip_time
        scale = self.actor.scale
        alpha = 0.16 if self.owner == 'human' else 0.28
        max_extent = 0.0
        actor_pos = self.actor.root.getPos(self.parent)
        for i, (ja, jb, width_scale) in enumerate(self.SEGMENTS):
            pa = self.actor.joint_world_point(ja, clip_t, self.parent)
            pb = self.actor.joint_world_point(jb, clip_t, self.parent)
            sa, sb = self._project(pa, sun_ray), self._project(pb, sun_ray)
            radius = max(0.025, width_scale * scale * 0.5)
            if build_geometry:
                self.root.attachNewNode(self._capsule_geom(sa, sb, radius, alpha, i))
            self.capsules.append((sa, sb, radius))
            max_extent = max(max_extent, math.hypot(sa.x - actor_pos.x, sa.y - actor_pos.y),
                             math.hypot(sb.x - actor_pos.x, sb.y - actor_pos.y))
        self.last_extent = max_extent

    def _update_fast(self, sun_ray: Vec3):
        """Pass 44: the shade-query capsules only (no geometry), all joints in one numpy pass
        and one ground sample.  ~20x cheaper than projecting 30 joints through the heightfield."""
        if self._seg_index is None:
            idx = self.actor.skin.node_index
            self._seg_index = (np.array([idx[a] for a, _b, _w in self.SEGMENTS]),
                               np.array([idx[b] for _a, b, _w in self.SEGMENTS]),
                               [max(0.025, w * self.actor.scale * 0.5) for _a, _b, w in self.SEGMENTS])
        ia, ib, radii = self._seg_index
        local = self.actor.joint_local_points(self.actor.last_clip_time)
        m = self.actor.root.getMat(self.parent)
        mat = np.array([[m.getCell(r, c) for c in range(4)] for r in range(4)])
        world = local @ mat[:3, :3] + mat[3, :3]
        root = self.actor.root.getPos(self.parent)
        ground = self.field.height(root.x, root.y)
        if sun_ray.z < -0.05:
            t = np.clip((world[:, 2] - ground) / (-sun_ray.z), 0.0, 240.0)
            px = world[:, 0] + sun_ray.x * t
            py = world[:, 1] + sun_ray.y * t
        else:
            px, py = world[:, 0], world[:, 1]
        self.capsules = [((float(px[a]), float(py[a])), (float(px[b]), float(py[b])), r)
                         for a, b, r in zip(ia, ib, radii)]
        ext = np.hypot(px - root.x, py - root.y)
        self.last_extent = float(ext.max())

    def contains_xy(self, point: Point3) -> bool:
        px, py = point.x, point.y
        for a, b, radius in self.capsules:
            ax, ay = a[0], a[1]
            vx, vy = b[0] - ax, b[1] - ay
            wx, wy = px - ax, py - ay
            denom = vx*vx + vy*vy
            u = 0.0 if denom < 1e-10 else clamp((wx*vx + wy*vy) / denom, 0.0, 1.0)
            cx, cy = ax + u*vx, ay + u*vy
            if (px-cx)*(px-cx) + (py-cy)*(py-cy) <= radius*radius:
                return True
        return False


class StreamingTerrainWithGiant(HoloVerseHostedMixin, FrontendMixin, TeachMixin, HudMixin, SaveMixin, GleebsMixin, EndgameMixin, JourneyMixin,
                                CrimsonMixin, FightMixin, GlowMixin, LoreMixin, PlacesMixin, GiantsLifeMixin, DayCycleMixin,
                                AudioMixin, DesertMixin, SurvivalMixin, ShowBase):
    def __init__(self, offscreen: bool = False, seed: int = SEED, giant_glb: Path | None = None,
                 vsync: bool | None = None, show_fps: bool = False, new_game: bool = False,
                 persist: bool | None = None, save_dir: Path | None = None, show_title: bool | None = None,
                 host=None, host_hooks: dict | None = None):
        # Pass 63: host = a running HoloVerse app. The game then shares its window (no second
        # ShowBase, no PRC data) and keeps its world under its own node (holoverse_host.py).
        if host is not None:
            self._hosted_begin(host, host_hooks)
        self.persist = (not offscreen) if persist is None else bool(persist)
        self.save_dir = savegame.save_folder(save_dir)
        # Pass 50: display / sound / mouse settings, applied before the window opens
        self.settings = settings_mod.load(self.save_dir) if self.persist else dict(settings_mod.DEFAULTS)
        if vsync is not None:
            self.settings['vsync'] = bool(vsync)          # --no-vsync (benchmarking) wins for this run
        if self.hosted:
            pass                                       # the window and its settings are HoloVerse's
        elif offscreen:
            loadPrcFileData('', 'window-type offscreen')
            loadPrcFileData('', 'audio-library-name null')
            loadPrcFileData('', 'win-size 1280 720')
            loadPrcFileData('', f"sync-video {'true' if self.settings['vsync'] else 'false'}")
        else:
            for line in settings_mod.prc_lines(self.settings):
                loadPrcFileData('', line)
            loadPrcFileData('', 'window-title The Indigo Giant')
        # Pass 54: keep every sound decoded in memory. The default cache holds 15, the game has ~70
        # files, so a sound falling out of the cache was re-read and decoded from disk when it
        # played - a 100 ms stall on a punch or a footstep.
        if not self.hosted:
            loadPrcFileData('', 'audio-cache-limit 256')
            loadPrcFileData('', 'framebuffer-srgb true')
            loadPrcFileData('', 'show-frame-rate-meter false')
            super().__init__()
            self.disableMouse()
        if not offscreen and not self.hosted and self.settings['msaa']:
            self.render.setAntialias(AntialiasAttrib.MMultisample)
        self.offscreen = offscreen
        self.show_title = (not offscreen) if show_title is None else bool(show_title)
        # Pass 43: plain key events.  Without this, holding SHIFT turned 'w' into 'shift-w',
        # so W was ignored if SHIFT (jog) was pressed first, and keys could stick.
        if self.mouseWatcherNode is not None:          # no input devices when offscreen
            self.mouseWatcherNode.setModifierButtons(ModifierButtons())
        for thrower in (self.buttonThrowers or []):
            thrower.node().setModifierButtons(ModifierButtons())
        self.bindings = controls.load(paths.ROOT, self.save_dir if self.persist else None)
        if self.hosted:                                # Pass 63: TAB always means "home" in HoloVerse
            self._hosted_lent_keys = self._hosted_key_rules()
            for action, (_original, lent_as) in self._hosted_lent_keys.items():
                self.bindings[action] = lent_as
        self._action_handlers: dict = {}               # Pass 50: action -> (handler, extra) for rebinding
        self.new_game = new_game
        self.pending_save = None if (new_game or not self.persist) else savegame.read_save(self.save_dir)
        self.seed = seed
        self.setBackgroundColor(FOG_COLOR)

        self.field = TerrainField(seed)
        # Pass 42: level the ground under the landmarks before any terrain is built
        # (Pass 43: also the rings of the trail a saved game had already opened).
        sx, sy = human_start_xy()
        sites = desert_world.landmark_sites(seed, sx, sy)
        chapters = int((self.pending_save or {}).get('chapter', 1))
        idx = len(sites)
        for chapter in range(2, chapters + 1):
            more = desert_world.chapter_sites(seed, sx, sy, chapter, idx)
            idx += len(more)
            sites = sites + more
        for zone in desert_world.landmark_flat_zones(sites):
            self.field.add_flat_zone(*zone)
        self.loaded: dict[tuple[int, int], object] = {}
        self.loaded_lod: dict[tuple[int, int], str] = {}
        self.chunk_signatures: dict[tuple[int, int], str] = {}
        self.load_count = 0
        self.unload_count = 0
        self.center_chunk = None
        self.desired_coords: set[tuple[int, int]] = set()
        self.desired_lods: dict[tuple[int, int], str] = {}
        self.pending_loads: deque[tuple[tuple[int, int], str]] = deque()

        amb = AmbientLight('ambient')
        amb.setColor((0.40, 0.40, 0.42, 1.0))
        self.render.setLight(self.render.attachNewNode(amb))
        self.sun = DirectionalLight('sun')
        self.sun.setColor((0.92, 0.84, 0.72, 1.0))
        self.sun_np = self.render.attachNewNode(self.sun)
        self.sun.setShadowCaster(True, SHADOW_MAP_SIZE, SHADOW_MAP_SIZE)
        self.sun.setCameraMask(SHADOW_CAMERA_MASK)
        self.sun.getLens().setFilmSize(SHADOW_FILM_SIZE, SHADOW_FILM_SIZE)
        self.sun.getLens().setNearFar(1.0, 260.0)
        self.render.setLight(self.sun_np)
        self.sun_azimuth_deg = SUN_AZIMUTH_DEG
        self.sun_elevation_deg = SUN_ELEVATION_DEG
        self.sun_ray_world = Vec3(0, 0, -1)
        self.sun_to_light_world = Vec3(0, 0, 1)
        self._set_sun_angles(self.sun_azimuth_deg, self.sun_elevation_deg, rebuild_shadows=False)

        self.sketch_style_enabled = False
        self.current_fog_density = HUMAN_FOG_DENSITY
        self.target_fog_density = HUMAN_FOG_DENSITY
        self._setup_sketch_style()

        self.cam_target = Vec3(CHUNK_SIZE * 0.9, CHUNK_SIZE * 0.75, 10)
        self.distance = HUMAN_CAMERA_DISTANCE
        self.heading = 48.0
        self.pitch = HUMAN_CAMERA_PITCH
        self.camera_side_offset = HUMAN_CAMERA_SIDE
        self.camera_render_target = Vec3(self.cam_target)
        self.keys = {k: False for k in ('left', 'right', 'up', 'down', 'w', 'a', 's', 'd', 'shift', 'control', 'c')}
        self.controlled_name = 'human'
        self.move_clocks = {'human': 0.0, 'giant': 0.0}
        self.move_phase = {'human': 0.0, 'giant': 0.0, 'red': 0.0}     # Pass 52: walk-cycle phase
        self.human_motion_speed = 0.0
        self.footprints = []
        self.step_distance = {'human': 0.0, 'giant': 0.0}
        self.next_foot = {'human': 'left', 'giant': 'left'}
        self.giant_motion_speed = 0.0
        self.giant_motion_heading = 205.0
        self.giant_motion_gait = 'walk'
        self.jump_states = {
            'human': {'active': False, 'phase': 'ground', 'elapsed': 0.0, 'vz': 0.0},
            'giant': {'active': False, 'phase': 'ground', 'elapsed': 0.0, 'vz': 0.0},
        }
        # Giant-only prototype kneel state. Uses the stable low section of Fixing_Kneeling
        # rather than looping its task-specific hand motion.
        self.kneel_state = {'phase': 'standing', 'elapsed': 0.0}
        self.red_motion_speed = 0.0
        self.red_motion_heading = 180.0
        self.red_motion_clock = 0.0
        self.red_state = 'idle'
        self.red_stomp_cooldown = 0.0
        self.red_stomp_elapsed = 0.0
        self.red_last_distance = 0.0
        self.red_stomp_attempts = 0
        self.red_stomp_hit_done = False
        self.human_health = HUMAN_MAX_HEALTH
        self.human_alive = True
        self.human_stomp_hits = 0
        self.red_step_distance = 0.0
        self.red_next_foot = 'left'
        self.giant_health = GIANT_MAX_HEALTH
        self.red_health = GIANT_MAX_HEALTH
        self.giant_alive = True
        self.red_alive = True
        self.red_knocked_out = False
        self.red_dead = False              # Pass 47: the endgame - it ate the poisoned branch
        self.red_knockout_remaining = 0.0
        self.red_knockout_elapsed = 0.0
        self.red_recovering = False
        self.red_recovery_elapsed = 0.0
        self.red_fleeing = False
        self.red_flee_elapsed = 0.0
        self.red_knockout_count = 0
        self.red_recovery_count = 0
        self.combat_hits = {'giant': 0, 'red': 0}
        self.attack_states = {
            'giant': {'active': False, 'elapsed': 0.0, 'clip': 'Punch_Jab', 'hit_done': False, 'cooldown': 0.0},
            'red': {'active': False, 'elapsed': 0.0, 'clip': 'Punch_Jab', 'hit_done': False, 'cooldown': 0.0},
        }
        self.attack_toggle = {'giant': False, 'red': False}
        self.indigo_defending = False
        self.keys['e'] = False
        for flag, action in controls.HELD_FLAGS.items():
            self.bind_held(action, flag)
        # Pass 41: hold the right mouse button and move the mouse to orbit the camera.
        self._orbit_drag = None
        self.accept('mouse3', self._begin_orbit)
        self.accept('mouse3-up', self._end_orbit)
        self.accept('wheel_up', self._zoom, [-8])
        self.accept('wheel_down', self._zoom, [8])
        self.bind_action('camera_reset', self._reset_camera)
        self.bind_action('switch_character', self._toggle_control)
        self.bind_action('jump', self._request_jump)
        self.bind_action('kneel', self._toggle_kneel)
        self.keys['punch'] = self.keys['attack_mouse'] = False
        self.bind_held('punch', 'punch')                  # Pass 58: tap = punch, hold = hammer blow
        self.bind_action('punch', self.attack_press, ['key'])
        self.accept('mouse1-up', self._set_key, ['attack_mouse', False])
        self.bind_action('retry', self._retry_after_human_down)
        self.bind_action('fps', self._toggle_frame_meter)
        if show_fps and not self.hosted:
            self.setFrameRateMeter(True)

        self._update_stream(force=True)
        self.drain_stream_queue()

        self.giant_glb = giant_glb
        self.giant = None
        self.giant_height = 0.0
        self.human = None
        self.human_height = 0.0
        self.red_giant = None
        self.red_giant_height = 0.0
        self.actor_shadows = {}
        self._shadow_accum = 0.0
        if giant_glb:
            self._spawn_giant_and_human(giant_glb)
            self.actor_shadows['human'] = StylizedActorShadow(self.render, self.field, self.human_actor, 'human')
            self.actor_shadows['giant'] = StylizedActorShadow(self.render, self.field, self.giant_actor, 'giant')
            self.actor_shadows['red'] = StylizedActorShadow(self.render, self.field, self.red_giant_actor, 'red')
            self._update_actor_shadows()
            # Proxy geometry is retained only for the future shade query; the visible shadow is now a real shadow map.
            self.actor_shadows['human'].root.hide()
            self.actor_shadows['giant'].root.hide()
            self.actor_shadows['red'].root.hide()
            self._init_survival(seed)
            self._init_desert(seed)
            self._init_audio()
            self._init_journey(seed)
            self._init_daycycle()
            self._init_save()
            self._init_endgame()
            self._init_giants_life()
            self._init_fight()             # Pass 53
            self._init_glow()              # Pass 59
            self._init_crimson()           # Pass 60
            self._init_lore()              # Pass 61
            self._init_gleebs()            # Pass 61

        self.control_text = OnscreenText(text='', pos=(-1.30, 0.90), align=TextNode.ALeft, scale=0.040, fg=(0.10,0.10,0.12,0.88), mayChange=True)
        self.help_text = OnscreenText(text='[WASD]  [SHIFT >>]  [SPACE ^]  [1 come 2 stay 3 lift 4 go 5 shade Q whistle]  [RMB look]  [MMB wheel]  [E use / hold E]  [G eat]  [T/Y give/take]  [TAB <>]  [F3 fps]', pos=(-1.30, 0.845), align=TextNode.ALeft, scale=0.027, fg=(0.16,0.16,0.18,0.68), mayChange=True)
        self.down_text = OnscreenText(text='', pos=(0.0, -0.82), align=TextNode.ACenter, scale=0.052, fg=(0.13,0.08,0.08,0.90), mayChange=True)
        self._update_control_text()
        if giant_glb:
            self._init_hud()               # Pass 43: replaces the debug-style text HUD
            self.apply_pending_save()
            self._init_teach()             # Pass 50
            self._init_frontend()
        self._snap_camera_to_controlled(immediate=True)
        if not offscreen:
            self.taskMgr.add(self._movement_task, 'shared_actor_movement', sort=5)
            self.taskMgr.add(self._indigo_defender_task, 'indigo_defender', sort=6)
            self.taskMgr.add(self._red_giant_task, 'red_giant_hunter', sort=7)
            self.taskMgr.add(self._survival_task, 'companion_survival', sort=8)
            self.taskMgr.add(self._camera_task, 'camera_controls', sort=9)
            self.taskMgr.add(self._stream_task, 'terrain_stream_queue', sort=10)
            self.taskMgr.add(self._visibility_task, 'visibility_profile', sort=11)
            self.taskMgr.add(self._shadow_task, 'stylized_sun_shadows', sort=12)
            self.taskMgr.add(self._giant_idle_task, 'giant_idle', sort=20)

    def _shadow_focus_point(self):
        if getattr(self, 'giant', None) is not None and getattr(self, 'human', None) is not None:
            gx, gy, gz = self.giant.getPos(self.render)
            hx, hy, hz = self.human.getPos(self.render)
            if getattr(self, 'red_giant', None) is not None:
                rx, ry, rz = self.red_giant.getPos(self.render)
                return Point3((gx + hx + rx) / 3.0, (gy + hy + ry) / 3.0, max(gz, hz, rz) + self.giant_height * 0.28)
            return Point3((gx + hx) * 0.5, (gy + hy) * 0.5, max(gz, hz) + self.giant_height * 0.28)
        return Point3(getattr(self, 'cam_target', Point3(0, 0, 0)))

    def _fit_shadow_camera(self):
        focus = self._shadow_focus_point()
        pos = focus + self.sun_to_light_world * SHADOW_CAMERA_DISTANCE
        self.sun_np.setPos(self.render, pos)
        self.sun_np.lookAt(self.render, focus)

    def _set_sun_angles(self, azimuth_deg: float, elevation_deg: float, rebuild_shadows: bool = True):
        self.sun_azimuth_deg = float(azimuth_deg)
        self.sun_elevation_deg = clamp(float(elevation_deg), 4.0, 89.0)
        az = math.radians(self.sun_azimuth_deg)
        el = math.radians(self.sun_elevation_deg)
        # Vector from the surface toward the sun; azimuth 0 points +Y.
        to_sun = Vec3(math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))
        to_sun.normalize()
        self.sun_to_light_world = to_sun
        self.sun_ray_world = -to_sun
        self._fit_shadow_camera()
        self.sun.setDirection(self.sun_ray_world)
        self._sync_sun_shader()
        if rebuild_shadows and getattr(self, 'actor_shadows', None):
            self._update_actor_shadows()

    def set_sun_angles(self, azimuth_deg: float, elevation_deg: float):
        """Public hook for the later day/night clock."""
        self._set_sun_angles(azimuth_deg, elevation_deg, rebuild_shadows=True)

    def _sync_sun_shader(self):
        if not getattr(self, 'sketch_style_enabled', False):
            return
        # Shader normals are in view space, so transform the world sun vector into camera space.
        # Pass 44 fix: GLSL view space is OpenGL's (x right, y up, z toward the viewer), not
        # Panda's camera space (y forward, z up).  Without this swap the light followed the
        # camera pitch, so ground seen near the horizon always fell into the darkest band.
        q = self.camera.getQuat(self.render)
        v = q.conjugate().xform(self.sun_to_light_world)
        self.render.setShaderInput('sketch_light_dir_view', Vec3(v.x, v.z, -v.y))
        u = q.conjugate().xform(Vec3(0, 0, 1))          # world up, same view-space convention
        self.render.setShaderInput('view_up', Vec3(u.x, u.z, -u.y))
        if hasattr(self, 'sync_glow_shader'):
            self.sync_glow_shader()                       # Pass 59: the glow lights follow the camera too
        if hasattr(self, 'sync_crimson_shader'):
            self.sync_crimson_shader()                    # Pass 60

    def _update_actor_shadows(self):
        # Pass 44: only Indigo's and the Red Giant's shadows are used (shade for the human);
        # the Red Giant's is skipped while it is far away.
        shadows = getattr(self, 'actor_shadows', {})
        for owner in ('giant', 'red'):
            sh = shadows.get(owner)
            if sh is None:
                continue
            if owner == 'red' and self.human is not None and self._human_red_distance() > 160.0:
                sh.capsules = []
                continue
            sh.update(self.sun_ray_world)

    def giant_shadow_contains(self, world_point: Point3) -> bool:
        """Future heat-system hook: geometric shade query, no cooling gameplay yet."""
        shadow = getattr(self, 'actor_shadows', {}).get('giant')
        return bool(shadow and shadow.contains_xy(world_point))

    def _shadow_task(self, task):
        dt = min(globalClock.getDt(), 0.05)
        self._shadow_accum += dt
        self._proxy_accum = getattr(self, '_proxy_accum', 0.0) + dt
        if self._shadow_accum >= (1.0 / SHADOW_UPDATE_HZ):
            self._shadow_accum = 0.0
            self._fit_shadow_camera()
        if self._proxy_accum >= (1.0 / SHADE_QUERY_HZ):
            self._proxy_accum = 0.0
            self._update_actor_shadows()
        return Task.cont

    def _setup_sketch_style(self):
        shader_dir = paths.SHADERS
        vertex_shader = shader_dir / 'sketch.vert'
        fragment_shader = shader_dir / 'sketch.frag'
        # Panda3D wants its own path syntax; raw Windows paths fail with
        # "Could not find shader file" (seen in indigo_diagnostic.log).
        shader = Shader.load(Shader.SL_GLSL,
                             vertex=Filename.fromOsSpecific(str(vertex_shader)),
                             fragment=Filename.fromOsSpecific(str(fragment_shader)))
        if shader is None:
            raise RuntimeError(
                'Panda3D could not load the required Indigo Giant sketch shader files. '
                f'Vertex: {vertex_shader} | Fragment: {fragment_shader}. '
                'Restore both shader files from the same accepted build before launching again.'
            )
        self.render.setShader(shader)
        self.render.setShaderInput('sketch_light_dir_view', SKETCH_LIGHT_DIR)
        self.render.setShaderInput('shadow_texel_size', 1.0 / SHADOW_MAP_SIZE)
        self.render.setShaderInput('shadow_softness', 1.20)
        self.render.setShaderInput('fog_density', self.current_fog_density)
        self.render.setShaderInput('fog_color', FOG_COLOR)
        self.render.setShaderInput('soft_start', HUMAN_SOFT_START)
        self.render.setShaderInput('soft_end', HUMAN_SOFT_END)
        self.render.setShaderInput('edge_ink', 1.0)
        self.render.setShaderInput('fog_zenith', FOG_COLOR)
        self.render.setShaderInput('view_up', Vec3(0, 1, 0))
        self.render.setShaderInput('fog_floor', 0.0)
        self.render.setShaderInput('fog_end', HUMAN_LOAD_RADIUS * CHUNK_SIZE)
        for name in ('glow_pos_view', 'glow_color', 'glow2_pos_view', 'glow2_color',    # Pass 59: off until night
                     'glow3_pos_view', 'glow3_color'):                                   # Pass 60: the red one's
            self.render.setShaderInput(name, Vec4(0.0, 0.0, 0.0, 0.0) if 'color' in name else Vec4(0.0, 0.0, 0.0, 1.0))
        self.render.setShaderInput('glow_self', 0.0)
        self.render.setShaderInput('glow_receive', Vec3(1.0, 1.0, 1.0))
        self.render.setShaderInput('glow_tint', Vec3(0.30, 0.30, 0.95))              # indigo
        self.sketch_style_enabled = True
        self._sync_sun_shader()

    def _controlled_actor(self):
        if self.controlled_name == 'human':
            return (self.human_actor, self.human)
        return (self.giant_actor, self.giant)

    def _locomotion_profile(self, gait: str | None = None):
        if gait is None:
            # Crouch overrides faster gaits; otherwise SHIFT jogs and CTRL+SHIFT sprints.
            if self.keys.get('c'):
                gait = 'crouch'
            elif self.keys.get('shift') and self.keys.get('control'):
                gait = 'sprint'
            elif self.keys.get('shift'):
                gait = 'jog'
            else:
                gait = 'walk'
        gait = gait if gait in ('walk', 'jog', 'sprint', 'crouch') else 'walk'
        # Pass 39: a winded human can only walk.
        if self.controlled_name == 'human' and gait in ('jog', 'sprint') and getattr(self, 'winded', False):
            gait = 'walk'
        body = 'human' if self.controlled_name == 'human' else 'giant'
        clip, speed = locomotion.gait(body, gait)          # Pass 52: one table for every body
        if self.controlled_name == 'giant' and hasattr(self, 'giant_pace'):
            speed *= self.giant_pace()            # Pass 48: a cold, tired Indigo is slower
        if self.controlled_name == 'human' and hasattr(self, 'heat'):
            speed *= self.heat_speed_factor()     # heat-struck humans slow down
        scale = 1.0 if body == 'human' else GIANT_SCALE
        return gait, clip, speed, locomotion.playback_rate(clip, speed, scale), 0.0

    def _update_control_text(self):
        label = 'HUMAN' if self.controlled_name == 'human' else 'INDIGO GIANT'
        marker = 'o' if self.controlled_name == 'human' else '#'
        if self.controlled_name == 'human' and not self.human_alive:
            self.control_text.setText('x  HUMAN DOWNED')
            self.help_text.setText('[ENTER] RETRY')
        else:
            self.control_text.setText(f'{marker}  {label}')
            if self.controlled_name == 'giant':
                self.help_text.setText('[WASD]   [RMB look]   [SHIFT >>]   [CTRL+SHIFT >>>]   [click / F punch, hold: hammer]   [E lift / set down shell]   [K kneel]   [SPACE ^]   [TAB <>]   [F3 fps]')
            elif getattr(self, 'carried', False):
                self.help_text.setText('riding:  [W walk where you look]   [click / 4 go there]   [2 stop]   [3 set me down]   [TAB take the reins]   [G eat]   [T/Y give/take]')
            else:
                self.help_text.setText('[WASD]  [SHIFT >>]  [SPACE ^]  [1 come 2 stay 3 lift 4 go 5 shade Q whistle]  [RMB look]  [MMB wheel]  [E use / hold E]  [G eat]  [T/Y give/take]  [TAB <>]  [F3 fps]')
        # The Red Giant can down the human while Indigo is controlled. TAB intentionally
        # cannot switch to a downed human, so keep the encounter retry discoverable there too.
        self.down_text.setText('[ENTER]  RETRY' if not self.human_alive else '')

    def _camera_profile(self):
        if self.controlled_name == 'human' and getattr(self, 'carried', False):
            # Riding on the shoulder: pull back so the giant's head and the path ahead read.
            return {
                'distance': 13.0,
                'pitch': -13.0,
                'focus': HUMAN_CAMERA_FOCUS,
                'side': 0.0,
                'lead': 0.0,
                'zoom_min': 8.0,
                'zoom_max': 30.0,
            }
        if self.controlled_name == 'human':
            return {
                'distance': HUMAN_CAMERA_DISTANCE,
                'pitch': HUMAN_CAMERA_PITCH,
                'focus': HUMAN_CAMERA_FOCUS,
                'side': HUMAN_CAMERA_SIDE,
                'lead': 0.0,
                'zoom_min': HUMAN_ZOOM_MIN,
                'zoom_max': HUMAN_ZOOM_MAX,
            }
        return {
            'distance': GIANT_CAMERA_DISTANCE,
            'pitch': GIANT_CAMERA_PITCH,
            'focus': GIANT_CAMERA_FOCUS,
            'side': GIANT_CAMERA_SIDE,
            'lead': GIANT_CAMERA_LEAD,
            'zoom_min': GIANT_ZOOM_MIN,
            'zoom_max': GIANT_ZOOM_MAX,
        }

    def _controlled_focus(self):
        _actor_obj, node = self._controlled_actor()
        profile = self._camera_profile()
        height = self.human_height if self.controlled_name == 'human' else self.giant_height
        pos = node.getPos()
        h = math.radians(self.heading)
        forward = Vec3(math.sin(h), math.cos(h), 0)
        return Vec3(pos.x, pos.y, pos.z + height * profile['focus']) + forward * profile['lead']

    def _snap_camera_to_controlled(self, immediate: bool = False):
        profile = self._camera_profile()
        self.cam_target = self._controlled_focus()
        self.distance = profile['distance']
        self.pitch = profile['pitch']
        self.camera_side_offset = profile['side']
        self._update_stream(force=True)
        self._place_camera(immediate=immediate)

    def _toggle_control(self):
        if self.input_blocked():
            return
        # Do not strand an actor mid-air or mid-kneel transition by handing control away.
        if self.jump_states[self.controlled_name]['active']:
            return
        if self.controlled_name == 'giant' and self.kneel_state['phase'] != 'standing':
            return
        if self.controlled_name == 'giant' and self.giant_action is not None:
            return
        if self.controlled_name == 'giant' and not self.human_alive:
            return
        # A defeated Indigo Giant is not a valid control target. If Indigo was defeated
        # while already controlled, TAB remains available to hand control back to the human.
        if self.controlled_name == 'human' and not self.giant_alive:
            return
        # Pass 38: never hand over mid-lift / mid-set-down (the giant is kneeling for it).
        if self.controlled_name == 'human' and self.comp['mode'] in ('pickup', 'setdown'):
            return
        # Park the actor we are leaving before handing input to the other actor. A downed
        # human must remain downed during the TAB handoff instead of flashing back to idle.
        if self.controlled_name == 'human':
            if self.carried:
                pass  # rider keeps sitting; TAB takes the reins of the giant
            elif self.human_alive:
                self.human_actor.apply_clip('Idle_Loop', 0.0, force=True)
            else:
                self._ensure_human_downed_clip()
                self.human_actor.apply_clip(
                    'Death01', self.human_actor.clips['Death01']['duration'] - 1e-4, force=True, loop=False
                )
            self.controlled_name = 'giant'
            self.giant_motion_speed = 0.0
            self.giant_motion_heading = self.giant.getH()
            self.giant_motion_gait = 'walk'
        else:
            if self.giant_alive:
                self.giant_actor.apply_clip('Idle_Loop', 0.0, force=True)
            else:
                self.giant_actor.apply_clip(
                    'Death01', self.giant_actor.clips['Death01']['duration'] - 1e-4, force=True, loop=False
                )
            self.giant_motion_speed = 0.0
            self.controlled_name = 'human'
            # Handing the reins back: the giant simply stops and waits (or carries on carrying).
            self.comp.update({'mode': 'carry' if self.carried else 'stay', 'moving': False, 'target': None})
        self._update_control_text()
        # Giant visibility still waits for its larger terrain ring before opening.
        self.target_fog_density = HUMAN_FOG_DENSITY
        self._snap_camera_to_controlled(immediate=False)

    def _toggle_kneel(self):
        if self.input_blocked():
            return False
        # Kneeling is currently a giant-only reach posture. Human controls remain unchanged.
        if self.controlled_name != 'giant' or not self.giant_alive:
            return False
        if self.jump_states['giant']['active']:
            return False
        phase = self.kneel_state['phase']
        if phase == 'standing':
            self.giant_motion_speed = 0.0
            self.giant_motion_gait = 'walk'
            self.kneel_state.update({'phase': 'enter', 'elapsed': 0.0})
            self.giant_actor.apply_clip('Fixing_Kneeling', 0.0, force=True, loop=False)
            return True
        if phase == 'kneeling':
            self.kneel_state.update({'phase': 'exit', 'elapsed': 0.0})
            return True
        return False

    def _update_kneel(self, dt: float):
        phase = self.kneel_state['phase']
        if phase == 'standing':
            return False
        # The supplied clip reaches a stable low posture around 1.2 s. Hold at 2.4 s
        # (same low body height) and reverse 1.2->0 to stand.
        ENTER_TIME = 1.20
        HOLD_SAMPLE = 2.40
        if phase == 'exit' and self.kneel_state['elapsed'] == 0.0:
            self.sfx('stand_giant', self.giant.getPos(self.render))
        self.kneel_state['elapsed'] += dt
        e = self.kneel_state['elapsed']
        if phase == 'enter':
            sample = min(ENTER_TIME, e)
            self.giant_actor.apply_clip('Fixing_Kneeling', sample, loop=False)
            if e >= ENTER_TIME:
                self.kneel_state.update({'phase': 'kneeling', 'elapsed': 0.0})
                self.sfx('kneel_giant', self.giant.getPos(self.render))
                self.giant_actor.apply_clip('Fixing_Kneeling', HOLD_SAMPLE, force=True, loop=False)
            return True
        if phase == 'kneeling':
            self.giant_actor.apply_clip('Fixing_Kneeling', HOLD_SAMPLE, loop=False)
            return True
        if phase == 'exit':
            sample = max(0.0, ENTER_TIME - e)
            self.giant_actor.apply_clip('Fixing_Kneeling', sample, loop=False)
            if e >= ENTER_TIME:
                self.kneel_state.update({'phase': 'standing', 'elapsed': 0.0})
                self.giant_actor.apply_clip('Idle_Loop', 0.0, force=True)
            return True
        return False

    def _request_jump(self):
        if self.input_blocked():
            return False
        owner = self.controlled_name
        if owner == 'human' and (not self.human_alive or self.carried or self.gesture is not None
                                 or self.hidden_shell is not None or self.human_dazed > 0.0
                                 or self.shells.inside(self.human.getPos(self.render), limit=1.0) is not None):
            return False
        if owner == 'giant' and not self.giant_alive:
            return False
        if self.keys.get('c'):
            return False
        if owner == 'giant' and self.kneel_state['phase'] != 'standing':
            return False
        state = self.jump_states[owner]
        if state['active']:
            return False
        actor_obj, node = self._controlled_actor()
        sink = actor_obj.height_world * GROUND_SINK_FRACTION
        ground = self.field.height(node.getX(), node.getY()) - sink
        if abs(node.getZ() - ground) > max(0.08, actor_obj.height_world * 0.01):
            return False
        if owner == 'human' and not self.spend_stamina(STAMINA_JUMP_COST):
            return False
        state.update({
            'active': True,
            'phase': 'start',
            'elapsed': 0.0,
            'vz': HUMAN_JUMP_VELOCITY if owner == 'human' else GIANT_JUMP_VELOCITY,
        })
        actor_obj.apply_clip('Jump_Start', 0.0, force=True, loop=False)
        return True

    def _jump_profile(self, owner: str):
        if owner == 'human':
            return HUMAN_JUMP_START_TIME, HUMAN_JUMP_LAND_TIME
        return GIANT_JUMP_START_TIME, GIANT_JUMP_LAND_TIME

    def _update_jump(self, owner: str, dt: float):
        state = self.jump_states[owner]
        if not state['active']:
            return False
        actor_obj = self.human_actor if owner == 'human' else self.giant_actor
        node = self.human if owner == 'human' else self.giant
        start_time, land_time = self._jump_profile(owner)
        phase = state['phase']
        state['elapsed'] += dt

        if phase in ('start', 'air'):
            pos = node.getPos()
            state['vz'] -= WORLD_GRAVITY * dt
            pos.z += state['vz'] * dt
            sink = actor_obj.height_world * GROUND_SINK_FRACTION
            ground = self.field.height(pos.x, pos.y) - sink
            if pos.z <= ground and state['vz'] < 0.0 and state['elapsed'] > 0.12:
                pos.z = ground
                node.setPos(pos)
                state.update({'phase': 'land', 'elapsed': 0.0, 'vz': 0.0})
                actor_obj.apply_clip('Jump_Land', 0.0, force=True, loop=False)
                self.sfx('land_' + owner, node.getPos(self.render))
                return True
            node.setPos(pos)
            if phase == 'start' and state['elapsed'] < start_time:
                clip = actor_obj.clips['Jump_Start']
                sample = (state['elapsed'] / start_time) * clip['duration']
                actor_obj.apply_clip('Jump_Start', sample, loop=False)
            else:
                if phase == 'start':
                    state['phase'] = 'air'
                    state['elapsed'] = 0.0
                actor_obj.apply_clip('Jump_Loop', state['elapsed'], loop=True)
            return True

        if phase == 'land':
            clip = actor_obj.clips['Jump_Land']
            sample = (state['elapsed'] / land_time) * clip['duration']
            actor_obj.apply_clip('Jump_Land', sample, loop=False)
            if state['elapsed'] >= land_time:
                state.update({'active': False, 'phase': 'ground', 'elapsed': 0.0, 'vz': 0.0})
                actor_obj.apply_clip('Idle_Loop', 0.0, force=True)
            return True
        return False

    def _ground_idle_clip(self, gait_name: str | None = None):
        if gait_name == 'crouch' or (gait_name is None and self.keys.get('c')):
            return 'Crouch_Idle_Loop'
        return 'Idle_Loop'

    def _apply_passive_human_pose(self, clock_t: float):
        # Indigo-controlled movement must not visually revive a downed human.
        if self.carried:
            return  # rider pose: survival._update_rider
        if self.human_alive:
            self.human_actor.apply_clip('Idle_Loop', clock_t)
            return
        self._ensure_human_downed_clip()
        self.human_actor.apply_clip(
            'Death01', self.human_actor.clips['Death01']['duration'] - 1e-4, loop=False
        )

    def _apply_controlled_move(self, move: Vec3, dt: float, clock_t: float, gait: str | None = None):
        if self.controlled_name == 'human' and not self.human_alive:
            self._ensure_human_downed_clip()
            self.human_actor.apply_clip('Death01', self.human_actor.clips['Death01']['duration'] - 1e-4, loop=False)
            self._update_footprints(dt)
            self.cam_target = self._controlled_focus()
            self._update_stream()
            return
        if self.controlled_name == 'human' and (self.carried or self.human_dazed > 0.0
                                                or self._update_gesture(dt) or self.human_is_smashing()):
            # Riding, dazed, gesturing or busy with E: the human stays put.  While riding, W is
            # read by the companion (walk where you look) instead.  Pass 55: inside a shell you
            # walk about freely (and walk out through its mouth).
            self.human_effort = 'idle'
            if self.carried:
                self._update_gesture(dt)
            self._update_footprints(dt)
            self.cam_target = self._controlled_focus()
            self._update_stream()
            return
        if self.controlled_name == 'giant' and self._update_melee_state('giant', dt, clock_t):
            self.giant_motion_speed = 0.0
            self._update_footprints(dt)
            self.cam_target = self._controlled_focus()
            self._update_stream()
            return
        if self.controlled_name == 'giant' and self.kneel_state['phase'] != 'standing':
            self.giant_motion_speed = 0.0
            self._update_kneel(dt)
            self._apply_passive_human_pose(clock_t)
            self._update_footprints(dt)
            self.cam_target = self._controlled_focus()
            self._update_stream()
            return
        actor_obj, node = self._controlled_actor()
        gait_name, move_clip, speed, move_anim_rate, step_spacing = self._locomotion_profile(gait)
        moving = move.length_squared() > 1e-8
        if self.controlled_name == 'human':
            self.human_effort = gait_name if moving else 'idle'
        if moving:
            move = Vec3(move)
            move.normalize()
            old_pos = node.getPos()
            if self.controlled_name == 'human':
                # Pass 52: a quick, not instant, change of pace between walk / jog / sprint
                # (0 -> jog in ~0.3 s); letting go of the keys still stops you at once.
                cur = self.human_motion_speed
                rate = HUMAN_ACCELERATION if speed >= cur else HUMAN_DECELERATION
                self.human_motion_speed = speed = approach(cur, speed, rate * dt)
            pos = old_pos + move * speed * dt
            if self.controlled_name == 'human' and hasattr(self, 'shells'):
                pos = self.shells.collide(old_pos, pos)      # Pass 55: shell walls; in and out by the mouth
            if not self.jump_states[self.controlled_name]['active']:
                sink = actor_obj.height_world * GROUND_SINK_FRACTION
                pos.z = self.field.height(pos.x, pos.y) - sink
            else:
                pos.z = old_pos.z
            node.setPos(pos)
            # Face travel direction; the supplied standard library has a forward walk, not strafe/backpedal clips.
            # Pass 41: walk exactly where the keys point (camera-relative) and turn the body
            # to face it quickly instead of snapping, so diagonals and reversals read cleanly.
            want = heading_toward(move.x, move.y)
            turn = HUMAN_TURN_RATE_DEG * dt
            new_h = node.getH() + clamp(shortest_angle_delta_deg(node.getH(), want), -turn, turn)
            node.setH((new_h + 180.0) % 360.0 - 180.0)
            if not self.jump_states[self.controlled_name]['active']:
                traveled = Vec3(pos.x - old_pos.x, pos.y - old_pos.y, 0).length()
                self.stride(self.controlled_name, move_clip, traveled)        # Pass 52
        else:
            if self.controlled_name == 'human':
                self.human_motion_speed = 0.0
            if not self.jump_states[self.controlled_name]['active']:
                actor_obj.apply_clip(self._ground_idle_clip(gait_name), clock_t)
        self._update_jump(self.controlled_name, dt)
        if self.controlled_name == 'human' and hasattr(self, '_update_shell_presence'):
            self._update_shell_presence()
        if self.controlled_name == 'human':
            # Pass 38: the companion AI animates the giant in every mode except a plain STAY.
            if (not self.indigo_defending and not self.attack_states['giant']['active'] and self.giant_alive
                    and self.comp['mode'] == 'stay' and self.kneel_state['phase'] == 'standing'):
                self.giant_actor.apply_clip('Idle_Loop', clock_t)
        else:
            self._apply_passive_human_pose(clock_t)
        self._update_footprints(dt)
        self.cam_target = self._controlled_focus()
        self._update_stream()

    def stride(self, owner: str, clip: str, distance: float):
        """Pass 52: advance a walk cycle by the ground actually covered, so the planted foot
        stays planted at any speed; a footprint and a step sound at each real touchdown.
        owner: 'human', 'giant' or 'red'."""
        actor_obj, node = {'human': (self.human_actor, self.human), 'giant': (self.giant_actor, self.giant),
                           'red': (self.red_giant_actor, self.red_giant)}[owner]
        if clip not in actor_obj.clips:
            clip = 'Walk_Loop'
        duration = actor_obj.clips[clip]['duration']
        phase0 = self.move_phase.get(owner, 0.0)
        phase1 = phase0 + locomotion.phase_advance(clip, duration, distance, actor_obj.scale)
        self.move_phase[owner] = phase1 % 1.0
        t = self.move_phase[owner] * duration
        if owner == 'red':
            self.red_motion_clock = t
        else:
            self.move_clocks[owner] = t
        actor_obj.apply_clip(clip, t)
        for side, at in locomotion.contacts_crossed(clip, phase0, phase1):
            if owner == 'red':
                self._stamp_red_footprint(side, at * duration)
            else:
                self._stamp_controlled_footprint(actor_obj, node, owner=owner, side=side, clip_time=at * duration)

    def _stamp_controlled_footprint(self, actor_obj, node, owner: str | None = None, side: str | None = None,
                                    clip_time: float | None = None):
        owner = owner or self.controlled_name
        if side is None:
            side = self.next_foot[owner]
        self.next_foot[owner] = 'right' if side == 'left' else 'left'
        t = self.move_clocks[owner] if clip_time is None else clip_time
        world_foot = actor_obj.foot_world_point(side, t, self.render)
        world_foot.z = self.field.height(world_foot.x, world_foot.y)
        if owner == 'human':
            loud = {'crouch': 0.45, 'walk': 0.75, 'jog': 0.95, 'sprint': 1.1}.get(getattr(self, 'human_effort', 'walk'), 0.75)
        else:
            loud = 0.55 + 0.5 * clamp(self.giant_motion_speed / GIANT_JOG_SPEED, 0.0, 1.0)
        self.sfx('footstep_' + owner, world_foot, loud)
        if owner == 'human':
            length, width, depth, lifetime = 0.28, 0.125, 0.018, HUMAN_PRINT_LIFETIME     # Pass 58: a real foot's proportions
        else:
            length, width, depth, lifetime = 2.95, 1.30, 0.20, GIANT_PRINT_LIFETIME
        fp = SandFootprint(self.render, self.field, world_foot, node.getH(), length, width, depth, lifetime, owner,
                           side)
        self.footprints.append(fp)
        # Hard cap keeps old trail geometry bounded even during long wandering sessions.
        if len(self.footprints) > 160:
            old = self.footprints.pop(0)
            old.root.removeNode()

    def _update_footprints(self, dt: float):
        # Pass 44: footprints fade slowly (42-180 s), so fade them in 0.25 s batches
        # instead of touching up to 240 nodes every frame.
        self._fp_accum = getattr(self, '_fp_accum', 0.0) + dt
        if not self.footprints or self._fp_accum < FOOTPRINT_FADE_STEP:
            return
        dt, self._fp_accum = self._fp_accum, 0.0
        self.footprints = [fp for fp in self.footprints if fp.update(dt)]
        # Pass 37 safety cap: long giant sprints could accumulate hundreds of
        # transparent nodes (180 s lifetime).  Retire the oldest beyond the cap.
        excess = len(self.footprints) - MAX_FOOTPRINTS
        if excess > 0:
            for fp in self.footprints[:excess]:
                fp.root.removeNode()
            del self.footprints[:excess]

    def advance_wind(self, seconds: float, step: float = 0.25):
        """Smoke-test helper: age existing prints without moving either character."""
        remaining = max(0.0, seconds)
        while remaining > 1e-9:
            dt = min(step, remaining)
            self._update_footprints(dt)
            remaining -= dt

    def simulate_move(self, local_x: float, local_y: float, seconds: float, steps: int = 30, gait: str = 'walk'):
        h = math.radians(self.heading)
        forward = Vec3(math.sin(h), math.cos(h), 0)
        right = Vec3(math.cos(h), -math.sin(h), 0)
        move = right * local_x + forward * local_y
        dt = seconds / max(1, steps)
        for i in range(steps):
            self._apply_controlled_move(move, dt, i * dt, gait=gait)

    def _apply_giant_heavy_input(self, move: Vec3, dt: float, clock_t: float, gait: str | None = None):
        """Interactive giant-only inertial locomotion; preserves the same gait/clip mapping."""
        if self._update_giant_action(dt):
            # Pass 39: lifting a shell (PickUp_Table) plays out before the giant moves again.
            self.giant_motion_speed = 0.0
            self._apply_passive_human_pose(clock_t)
            self._update_footprints(dt)
            self.cam_target = self._controlled_focus()
            self._update_stream()
            return
        if self.kneel_state['phase'] != 'standing':
            # Pass 38 fix: K used to start the kneel, but nothing advanced it while the
            # giant was player-controlled, so the next frame snapped straight back to idle.
            self.giant_motion_speed = 0.0
            self._update_kneel(dt)
            self._apply_passive_human_pose(clock_t)
            self._update_footprints(dt)
            self.cam_target = self._controlled_focus()
            self._update_stream()
            return
        if self._update_melee_state('giant', dt, clock_t):
            self.giant_motion_speed = 0.0
            self._apply_passive_human_pose(clock_t)
            return
        if hasattr(self, 'update_attack_input') and self.update_attack_input(dt):
            self._apply_passive_human_pose(clock_t)     # Pass 58: winding up a hammer blow
            self._update_footprints(dt)
            return
        requested = move.length_squared() > 1e-8
        if requested:
            gait_name, move_clip, target_speed, move_anim_rate, step_spacing = self._locomotion_profile(gait)
            self.giant_motion_gait = gait_name
            desired = Vec3(move)
            desired.normalize()
            desired_heading = heading_toward(desired.x, desired.y)
            delta = shortest_angle_delta_deg(self.giant_motion_heading, desired_heading)
            # Pass 41: a heavy body turns faster when nearly stopped, and slows down for a
            # sharp turn instead of striding on in the old direction (what made A/S/D feel
            # like they went the wrong way).
            slow = 1.0 - clamp(self.giant_motion_speed / max(target_speed, 1e-6), 0.0, 1.0)
            max_turn = (GIANT_TURN_RATE_DEG + GIANT_PIVOT_BONUS_DEG * slow) * dt
            self.giant_motion_heading += clamp(delta, -max_turn, max_turn)
            align = clamp(math.cos(math.radians(delta)), 0.0, 1.0)
            goal_speed = target_speed * max(0.12, align * align)
            rate = GIANT_ACCELERATION if goal_speed >= self.giant_motion_speed else GIANT_BRAKING
            self.giant_motion_speed = approach(self.giant_motion_speed, goal_speed, rate * dt)
        else:
            crouch_held = (gait == 'crouch') or (gait is None and self.keys.get('c'))
            coast_gait = 'crouch' if crouch_held else (gait if gait in ('walk', 'jog', 'sprint') else self.giant_motion_gait)
            gait_name, move_clip, target_speed, move_anim_rate, step_spacing = self._locomotion_profile(coast_gait)
            if gait_name == 'crouch':
                self.giant_motion_gait = 'crouch'
            self.giant_motion_speed = approach(self.giant_motion_speed, 0.0, GIANT_BRAKING * dt)
            if self.giant_motion_speed <= 0.035 and not crouch_held:
                gait_name, move_clip, target_speed, move_anim_rate, step_spacing = self._locomotion_profile('walk')
                self.giant_motion_gait = 'walk'

        moving = self.giant_motion_speed > 0.035
        if moving:
            travel = heading_forward(self.giant_motion_heading)
            old_pos = self.giant.getPos()
            pos = old_pos + travel * self.giant_motion_speed * dt
            if not self.jump_states['giant']['active']:
                sink = self.giant_actor.height_world * GROUND_SINK_FRACTION
                pos.z = self.field.height(pos.x, pos.y) - sink
            else:
                pos.z = old_pos.z
            if hasattr(self, 'giant_clear_of_shells') and not self.jump_states['giant']['active']:
                pos = self.giant_clear_of_shells(self.giant_actor, old_pos, pos)      # Pass 55
            self.giant.setPos(pos)
            self.giant.setH(self.giant_motion_heading)
            if not self.jump_states['giant']['active']:
                traveled = Vec3(pos.x-old_pos.x, pos.y-old_pos.y, 0).length()
                self.stride('giant', move_clip, traveled)                      # Pass 52
        else:
            if not self.jump_states['giant']['active']:
                self.giant_actor.apply_clip(self._ground_idle_clip(gait_name), clock_t)

        self._update_jump('giant', dt)
        self._apply_passive_human_pose(clock_t)
        self._update_footprints(dt)
        self.cam_target = self._controlled_focus()
        self._update_stream()

    def simulate_giant_heavy_move(self, local_x: float, local_y: float, seconds: float, steps: int = 120, gait: str = 'sprint'):
        """Smoke helper that runs the same inertial path as interactive giant input."""
        if self.controlled_name != 'giant':
            self._toggle_control()
        h = math.radians(self.heading)
        forward = Vec3(math.sin(h), math.cos(h), 0)
        right = Vec3(math.cos(h), -math.sin(h), 0)
        move = right * local_x + forward * local_y
        dt = seconds / max(1, steps)
        for i in range(steps):
            self._apply_giant_heavy_input(move, dt, i*dt, gait=gait)

    def simulate_giant_brake(self, seconds: float, steps: int = 60, gait: str = 'sprint'):
        if self.controlled_name != 'giant':
            self._toggle_control()
        dt = seconds / max(1, steps)
        for i in range(steps):
            self._apply_giant_heavy_input(Vec3(0,0,0), dt, i*dt, gait=gait)

    def _giant_flat_distance(self):
        if self.giant is None or self.red_giant is None:
            return 1e9
        d = self.red_giant.getPos(self.render) - self.giant.getPos(self.render)
        return math.hypot(d.x, d.y)

    def _human_red_distance(self):
        if self.human is None or self.red_giant is None:
            return 1e9
        d = self.red_giant.getPos(self.render) - self.human.getPos(self.render)
        return math.hypot(d.x, d.y)

    def _combat_actor(self, owner: str):
        return (self.giant_actor, self.giant) if owner == 'giant' else (self.red_giant_actor, self.red_giant)

    def _combat_alive(self, owner: str):
        if owner == 'giant':
            return self.giant_alive
        return self.red_alive and not self.red_knocked_out and not self.red_recovering

    def _combat_health(self, owner: str):
        return self.giant_health if owner == 'giant' else self.red_health

    def _set_combat_health(self, owner: str, value: float):
        value = clamp(value, 0.0, GIANT_MAX_HEALTH)
        if owner == 'giant':
            self.giant_health = value
            self.giant_alive = value > 0.0
        else:
            if value < self.red_health and hasattr(self, 'red_provoked_t'):
                self.red_provoked_t = 30.0         # Pass 49: hit while busy, it fights back
            self.red_health = value
            # Red Giants do not die at zero health. Zero transitions into knockout.
            self.red_alive = True

    def _knock_out_red(self):
        if self.red_knocked_out:
            return
        self.red_health = 0.0
        self.red_alive = True
        self.red_knocked_out = True
        self.red_recovering = False
        self.red_fleeing = False
        self.red_knockout_remaining = RED_KNOCKOUT_DURATION
        self.red_knockout_elapsed = 0.0
        self.red_recovery_elapsed = 0.0
        self.red_flee_elapsed = 0.0
        self.red_knockout_count += 1
        self.red_anger += 1
        self.red_lurking = False
        self.red_returning = False
        self.red_state = 'knocked_out'
        self.red_motion_speed = 0.0
        self.red_stamina = 0.0
        self.red_calm_until = None
        self.attack_states['red'].update({'active': False, 'elapsed': 0.0, 'hit_done': False, 'cooldown': 0.0})
        # Death01 is reused strictly as a fall/knockout pose; the Red Giant remains alive.
        self.red_giant_actor.apply_clip('Death01', 0.0, force=True, loop=False)
        self.sfx('giant_fall', self.red_giant.getPos(self.render), 1.0, 0.9)    # Pass 54: it hits the sand

    def _red_safe_distance(self):
        if self.red_giant is None:
            return 1e9
        rp = self.red_giant.getPos(self.render)
        distances = []
        for node in (self.human, self.giant):
            if node is None:
                continue
            d = node.getPos(self.render) - rp
            distances.append(math.hypot(d.x, d.y))
        return min(distances) if distances else 1e9

    def _update_red_knockout_and_flee(self, dt: float, clock_t: float):
        if self.red_knocked_out:
            self.red_state = 'knocked_out'
            self.red_motion_speed = 0.0
            self.red_knockout_elapsed += dt
            self.red_knockout_remaining = max(0.0, self.red_knockout_remaining - dt)
            duration = self.red_giant_actor.clips['Death01']['duration']
            sample = min(self.red_knockout_elapsed, duration - 1e-4)
            self.red_giant_actor.apply_clip('Death01', sample, loop=False)
            if self.red_knockout_remaining <= 0.0:
                self.red_knocked_out = False
                self.red_recovering = True
                self.red_recovery_elapsed = 0.0
                self.red_recovery_count += 1
                self.red_health = GIANT_MAX_HEALTH
                self.red_state = 'recovering'
            return True

        if self.red_recovering:
            self.red_state = 'recovering'
            self.red_motion_speed = 0.0
            self.red_recovery_elapsed += dt
            duration = self.red_giant_actor.clips['Death01']['duration']
            p = clamp(self.red_recovery_elapsed / RED_RECOVERY_STAND_TIME, 0.0, 1.0)
            sample = max(0.0, (duration - 1e-4) * (1.0 - p))
            self.red_giant_actor.apply_clip('Death01', sample, loop=False)
            if p >= 1.0:
                # Pass 53: it gets up dazed and has lost you for a whole day (no flight, no lurk)
                self.red_recovering = False
                self.red_stamina = self.stamina_max('red') * 0.5
                self.begin_red_calm()
                self.red_state = 'dazed'
                self.red_giant_actor.apply_clip('Idle_Loop', clock_t, force=True)
            return True

        if self.red_fleeing:
            self.red_state = 'flee'
            self.red_flee_elapsed += dt
            # Run directly away from the nearer of the human / Indigo Giant.
            rp = self.red_giant.getPos(self.render)
            threats = [n for n in (self.human, self.giant) if n is not None]
            if threats:
                threat = min(threats, key=lambda n: (n.getX()-rp.x)**2 + (n.getY()-rp.y)**2)
                away = rp - threat.getPos(self.render)
                flat = Vec3(away.x, away.y, 0)
            else:
                flat = Vec3(0, 1, 0)
            if flat.length_squared() > 1e-8:
                flat.normalize()
                target_heading = heading_toward(flat.x, flat.y)
                delta = shortest_angle_delta_deg(self.red_motion_heading, target_heading)
                self.red_motion_heading += clamp(delta, -GIANT_TURN_RATE_DEG * dt, GIANT_TURN_RATE_DEG * dt)
                self.red_giant.setH(self.red_motion_heading)
                self.red_motion_speed = approach(self.red_motion_speed, GIANT_SPRINT_SPEED, GIANT_ACCELERATION * dt)
                forward = heading_forward(self.red_motion_heading)
                old = self.red_giant.getPos()
                pos = old + forward * self.red_motion_speed * dt
                sink = self.red_giant_actor.height_world * GROUND_SINK_FRACTION
                pos.z = self.field.height(pos.x, pos.y) - sink
                self.red_giant.setPos(pos)
                self.stride('red', locomotion.gait('giant', 'sprint')[0],
                            Vec3(pos.x-old.x, pos.y-old.y, 0).length())               # Pass 52
            if self._red_safe_distance() >= RED_FLEE_SAFE_DISTANCE:
                self.red_fleeing = False
                self.red_motion_speed = 0.0
                self.red_giant_actor.apply_clip('Idle_Loop', clock_t, force=True)
                # Pass 38: it never leaves for good — it lurks, recovers, and comes back.
                self.red_begin_lurk()
            return True
        return False

    def _request_giant_melee(self):
        if self.input_blocked():
            return False
        # Manual attack only while the player actually controls the Indigo Giant.
        if self.controlled_name != 'giant' or not self.giant_alive:
            return False
        if self.kneel_state['phase'] != 'standing' or self.jump_states['giant']['active']:
            return False
        # Pass 38: F smashes a nearby blood branch unless the Red Giant is within reach.
        red_in_reach = self._combat_alive('red') and self._giant_flat_distance() <= GIANT_MELEE_RANGE
        branch = None if red_in_reach else self.giant_smash_target()
        if branch is not None:
            if self._start_melee('giant'):
                self.pending_smash = branch
                return True
            return False
        return self._start_melee('giant')

    def _start_melee(self, owner: str, clip: str | None = None, cost: float | None = None, start: float = 0.0):
        """Throw a blow. Pass 58: clip None = the next of jab / cross; `start` skips a wind-up
        already shown (Indigo's charged hammer blow)."""
        if owner == 'giant' and not self.giant_alive:
            return False
        if owner == 'red' and not self._combat_alive('red'):
            return False
        if not self._combat_alive(owner):
            return False
        state = self.attack_states[owner]
        if state['active'] or state['cooldown'] > 0.0:
            return False
        cost = fight.PUNCH_COST if cost is None else cost
        if self.fight_stamina(owner) < cost:
            return False                           # Pass 53: out of breath - no punch until it recovers
        self.fight_spend(owner, cost)
        if clip is None:
            self.attack_toggle[owner] = not self.attack_toggle[owner]
            clip = 'Punch_Cross' if self.attack_toggle[owner] else 'Punch_Jab'
        state.update({'active': True, 'elapsed': start, 'clip': clip, 'hit_done': False, 'hits': MELEE_HITS[clip],
                      'hit_i': 0, 'queued': None})
        actor, node = self._combat_actor(owner)
        actor.apply_clip(clip, start, force=True, loop=False)
        p = node.getPos(self.render)
        self.sfx('punch_swing', Point3(p.x, p.y, p.z + actor.height_world * 0.6))
        if owner == 'giant':
            self.giant_motion_speed = 0.0
        else:
            self.red_motion_speed = 0.0
        return True

    def _apply_melee_hit(self, attacker: str, power: float = 1.0):
        if attacker == 'giant' and self.pending_smash is not None:
            branch, self.pending_smash = self.pending_smash, None
            if not branch.smashed:
                self.flora.smash(branch)
                self.sfx('branch_smash', branch.pos, 1.3)
                self.on_branch_smashed(branch, 'giant')
            return True
        defender = 'red' if attacker == 'giant' else 'giant'
        if not self._combat_alive(defender):
            return False
        if self._giant_flat_distance() > GIANT_MELEE_RANGE:
            return False
        if attacker == 'giant' and self.controlled_name == 'giant' and not self.giant_faces_red():
            return False                           # Pass 58: your blows land where Indigo faces
        # Pass 53: a hit takes stamina and leaves a small wound; it only knocks a giant down
        # when it lands on an exhausted one (or its life is gone).
        result = self.resolve_hit(attacker, defender, power)
        if result == 'warded':
            return False                           # Pass 60: it glanced off the red one's crimson ward
        self.combat_hits[attacker] += 1
        actor, dnode = self._combat_actor(defender)
        dp = dnode.getPos(self.render)
        self.sfx('punch_hit', Point3(dp.x, dp.y, dp.z + actor.height_world * 0.6))
        if result == 'ko':
            if defender == 'red':
                self._knock_out_red()
            else:
                # Knocked out during a jump or kneel: clear those locks so nothing soft-locks.
                self.jump_states['giant'].update({'active': False, 'phase': 'ground', 'elapsed': 0.0, 'vz': 0.0})
                self.kneel_state.update({'phase': 'standing', 'elapsed': 0.0})
                self.knock_out_indigo()
        else:
            actor.apply_clip('Hit_Chest', 0.12, force=True, loop=False)
            if defender == 'red':
                self.red_scare_check()
                if power >= fight.HEAVY_KNOCKBACK_POWER:
                    self.knock_back_red()          # Pass 58: a hammer blow drives it back, staggered
        return True

    def _update_melee_state(self, owner: str, dt: float, clock_t: float):
        state = self.attack_states[owner]
        state['cooldown'] = max(0.0, state['cooldown'] - dt)
        if owner == 'red' and (self.red_knocked_out or self.red_recovering):
            return True
        if not self._combat_alive(owner):
            actor, _node = self._combat_actor(owner)
            actor.apply_clip('Death01', min(clock_t, actor.clips['Death01']['duration'] - 1e-4), loop=False)
            return True
        if not state['active']:
            return False
        actor, _node = self._combat_actor(owner)
        state['elapsed'] += dt
        clip = state['clip']
        duration = actor.clips[clip]['duration']
        actor.apply_clip(clip, state['elapsed'], loop=False)
        if owner == 'giant' and hasattr(self, 'melee_assist'):
            self.melee_assist(dt, state)           # Pass 58: turn to the red one, step in
        hits = state.get('hits') or MELEE_HITS.get(clip, ((0.3, 1.0),))
        while state.get('hit_i', 0) < len(hits) and state['elapsed'] >= hits[state.get('hit_i', 0)][0]:
            power = hits[state.get('hit_i', 0)][1]
            state['hit_i'] = state.get('hit_i', 0) + 1
            self._apply_melee_hit(owner, power)
        state['hit_done'] = state.get('hit_i', 0) >= len(hits)
        if owner == 'giant' and hasattr(self, 'melee_chain') and self.melee_chain(state, hits):
            return True                            # Pass 58: the next blow of a combo cut in
        if state['elapsed'] >= duration:
            state.update({'active': False, 'elapsed': 0.0, 'hit_done': False, 'cooldown': GIANT_ATTACK_COOLDOWN})
            if self._combat_alive(owner):
                actor.apply_clip('Idle_Loop', clock_t, force=True)
            return False
        return True

    def _face_actor(self, owner: str, target_node, dt: float):
        actor, node = self._combat_actor(owner)
        d = target_node.getPos(self.render) - node.getPos(self.render)
        flat = Vec3(d.x, d.y, 0)
        if flat.length_squared() <= 1e-8:
            return
        target_heading = heading_toward(flat.x, flat.y)
        current = node.getH()
        delta = shortest_angle_delta_deg(current, target_heading)
        node.setH(current + clamp(delta, -GIANT_TURN_RATE_DEG * dt, GIANT_TURN_RATE_DEG * dt))
        if owner == 'giant':
            self.giant_motion_heading = node.getH()
        else:
            self.red_motion_heading = node.getH()

    def _update_indigo_defender(self, dt: float, clock_t: float):
        # If Red defeats AI-controlled Indigo, keep the corpse in a stable downed pose.
        # The lethal-hit helper starts Death01 at frame 0, but a dead defender no longer
        # enters the normal melee updater that would advance/hold that animation.
        if self._update_giant_ko(dt):               # Pass 53: knocked out, or getting up
            self.indigo_defending = False
            return
        if self.controlled_name == 'human' and not self.giant_alive:
            self.indigo_defending = False
            self.giant_actor.apply_clip(
                'Death01', self.giant_actor.clips['Death01']['duration'] - 1e-4, loop=False
            )
            return
        # AI defense is only active while the player is the small human.
        if (self.controlled_name != 'human' or not self.red_alive or self.red_is_calm()
                or self.red_knocked_out or self.red_recovering or self.red_fleeing or self.red_lurking or self.red_dead
                or self.red_state in ('bait', 'eating', 'sick')      # Pass 47: it is not hunting you now
                or self.kneel_state['phase'] != 'standing'):
            self.indigo_defending = False
            return
        red_to_human = self._human_red_distance()
        # Pass 39: Indigo only defends when it is aware of the danger — close by and able to
        # see you, carrying you, or called with a whistle (which also widens its reach).
        if red_to_human > self.defense_trigger_range() or not self.indigo_aware():
            self.indigo_defending = False
            return
        self.indigo_defending = True
        if self._update_melee_state('giant', dt, clock_t):
            return
        distance = self._giant_flat_distance()
        self._face_actor('giant', self.red_giant, dt)
        if distance <= GIANT_MELEE_RANGE:
            self.giant_motion_speed = approach(self.giant_motion_speed, 0.0, GIANT_BRAKING * dt)
            self._start_melee('giant')
            return
        # Intercept with a heavy jog; a whistle makes it sprint while still far off.
        rush = self.whistle_alert > 0.0 and distance > 20.0
        run_speed = GIANT_SPRINT_SPEED if rush else GIANT_JOG_SPEED
        self.giant_motion_speed = approach(self.giant_motion_speed, run_speed, GIANT_ACCELERATION * dt)
        travel = heading_forward(self.giant.getH())
        old = self.giant.getPos()
        pos = old + travel * self.giant_motion_speed * dt
        sink = self.giant_actor.height_world * GROUND_SINK_FRACTION
        pos.z = self.field.height(pos.x, pos.y) - sink
        if hasattr(self, 'giant_clear_of_shells'):
            pos = self.giant_clear_of_shells(self.giant_actor, old, pos)              # Pass 55
        self.giant.setPos(pos)
        self.stride('giant', locomotion.gait('giant', 'sprint' if rush else 'jog')[0],
                    Vec3(pos.x - old.x, pos.y - old.y, 0).length())                  # Pass 52

    def _indigo_defender_task(self, task):
        if self.world_frozen():
            return Task.cont
        dt = min(globalClock.getDt(), 0.05)
        self._update_indigo_defender(dt, task.time)
        # Pass 38: companion orders (follow / stay / go there / lift / carry) when not defending.
        self._update_companion(dt)
        return Task.cont

    def simulate_giant_combat(self, seconds: float, steps: int = 240):
        dt = seconds / max(1, steps)
        for i in range(steps):
            clock_t = i * dt
            self._update_indigo_defender(dt, clock_t)
            self._update_red_giant(dt, clock_t)

    def _stamp_red_footprint(self, side: str | None = None, clip_time: float | None = None):
        if side is None:
            side = self.red_next_foot
        self.red_next_foot = 'right' if side == 'left' else 'left'
        t = self.red_motion_clock if clip_time is None else clip_time
        world_foot = self.red_giant_actor.foot_world_point(side, t, self.render)
        world_foot.z = self.field.height(world_foot.x, world_foot.y)
        self.sfx('footstep_red', world_foot, 0.7 + 0.4 * clamp(self.red_motion_speed / GIANT_SPRINT_SPEED, 0.0, 1.0))
        fp = SandFootprint(self.render, self.field, world_foot, self.red_giant.getH(),
                           2.95, 1.30, 0.20, GIANT_PRINT_LIFETIME, 'red', side)
        self.footprints.append(fp)
        if len(self.footprints) > 160:
            old = self.footprints.pop(0)
            old.root.removeNode()

    def _red_target_vector(self):
        if self.red_giant is None or self.human is None:
            return Vec3(0, 0, 0), 1e9, 'human'
        # When the Indigo Giant has intercepted, the Red Giant fights it instead of walking through it.
        # Pass 40: a defending Indigo only draws Red's attention once it is within Red's sight;
        # a whistle can now send Indigo in from far away, and Red should keep hunting meanwhile.
        indigo_in_sight = self._giant_flat_distance() <= RED_DETECTION_RANGE
        engage_indigo = self.giant_alive and ((self.indigo_defending and indigo_in_sight) or self.red_target_is_human_blocked()
                                              or self.hidden_shell is not None
                                              or self._giant_flat_distance() <= RED_ENGAGE_INDIGO_RANGE)
        target = self.giant if engage_indigo else self.human
        target_name = 'giant' if engage_indigo else 'human'
        delta = target.getPos(self.render) - self.red_giant.getPos(self.render)
        flat = Vec3(delta.x, delta.y, 0)
        return flat, flat.length(), target_name

    def _ensure_human_downed_clip(self):
        self.human_actor._load_clip(self.giant_glb, 'Death01')

    def _apply_red_stomp_hit(self):
        if not self.human_alive or self.carried or self.hidden_shell is not None:
            return False
        if self._human_red_distance() > RED_STOMP_RANGE + 0.45:
            return False
        self.human_health = max(0.0, self.human_health - RED_STOMP_DAMAGE * self.blow_scale('red')
                                * self.human_damage_scale())          # Pass 59: the glow you carry
        self.human_stomp_hits += 1
        self.sfx('human_hurt', self.human.getPos(self.render))
        if self.human_health <= 0.0:
            self._down_human()
        return True

    def _down_human(self):
        """The human is down (stomped, or the heat).  ENTER retries."""
        if hasattr(self, 'abort_carry') and (self.carried or self.comp.get('mode') in ('pickup', 'setdown', 'carry')):
            self.abort_carry()          # Pass 44 (B6): fall off Indigo's shoulder, not ride it dead
        self.human_health = 0.0
        self.human_alive = False
        self.sfx('human_down', self.human.getPos(self.render))
        self._ensure_human_downed_clip()
        self.human_actor.apply_clip('Death01', self.human_actor.clips['Death01']['duration'] - 1e-4, force=True, loop=False)
        self._update_control_text()

    def _retry_after_human_down(self):
        """Local prototype retry: restore the three-character encounter without restarting the app."""
        if self.human_alive or getattr(self, 'paused', False):
            return False

        # Pass 38: drop companion/carry state; inventories and plants persist.
        self.reset_survival_after_retry()
        # Human: restore the safe starting location and normal control state.
        self.human_health = HUMAN_MAX_HEALTH
        self.human_alive = True
        self.human_stomp_hits = 0
        if hasattr(self, 'chill'):
            self.chill = 0.0                     # Pass 48: you wake warm
        if hasattr(self, 'red_meal'):
            self.red_meal = None                 # Pass 49: no half-finished meal after a retry
        self.human.setPos(self.human_base_pos)
        self.human.setH(28)
        self.human_actor.apply_clip('Idle_Loop', 0.0, force=True)
        self.jump_states['human'].update({'active': False, 'phase': 'ground', 'elapsed': 0.0, 'vz': 0.0})
        self.move_clocks['human'] = 0.0
        self.step_distance['human'] = 0.0
        self.next_foot['human'] = 'left'

        # Indigo Giant: restore the encounter ally so retry is not immediately stranded.
        # Clear locomotion/jump state too; otherwise a retry during Indigo movement can carry
        # an old airborne/footstep state into the freshly restored encounter.
        self.giant_health = GIANT_MAX_HEALTH
        self.giant_alive = True
        self.giant_knocked_out = False              # Pass 53
        self.giant_getup = -1.0
        self.giant_stamina = fight.STAMINA_MAX['giant']
        self.giant.setPos(self.giant_base_pos)
        self.giant.setH(205)
        self.giant_actor.apply_clip('Idle_Loop', 0.0, force=True)
        self.giant_motion_speed = 0.0
        self.giant_motion_heading = 205.0
        self.giant_motion_gait = 'walk'
        self.jump_states['giant'].update({'active': False, 'phase': 'ground', 'elapsed': 0.0, 'vz': 0.0})
        self.move_clocks['giant'] = 0.0
        self.step_distance['giant'] = 0.0
        self.next_foot['giant'] = 'left'
        self.kneel_state.update({'phase': 'standing', 'elapsed': 0.0})

        # Red Giant: return to its original encounter position and clear combat/KO/flee state.
        if not self.red_dead:              # Pass 47: the poisoned Red Giant never gets up again
            self.red_stamina = self.stamina_max('red')     # Pass 54: a fresh encounter
            self.red_calm_until = None
            self.red_health = GIANT_MAX_HEALTH
            self.red_alive = True
            self.red_knocked_out = False
            self.red_knockout_remaining = 0.0
            self.red_knockout_elapsed = 0.0
            self.red_recovering = False
            self.red_recovery_elapsed = 0.0
            self.red_fleeing = False
            self.red_flee_elapsed = 0.0
            self.red_state = 'idle'
            self.red_motion_speed = 0.0
            self.red_motion_heading = 180.0
            self.red_motion_clock = 0.0
            self.red_step_distance = 0.0
            self.red_next_foot = 'left'
            self.red_last_distance = 0.0
            self.red_stomp_elapsed = 0.0
            self.red_stomp_cooldown = 0.0
            self.red_stomp_hit_done = False
            self.red_giant.setPos(self.red_giant_base_pos)
            self.red_giant.setH(180)
            self.red_giant_actor.apply_clip('Idle_Loop', 0.0, force=True)

        # Clear in-progress melee state on both giants.
        for who in ('giant', 'red'):
            self.attack_states[who].update({'active': False, 'elapsed': 0.0, 'clip': 'Punch_Jab', 'hit_done': False, 'cooldown': 0.0})
        self.indigo_defending = False

        self.controlled_name = 'human'
        self.target_fog_density = HUMAN_FOG_DENSITY
        # Pass 43: wake at camp (the last shell you slept in), with Indigo beside you.
        camp, heading = self.respawn_point()
        if camp is not None:
            self.human.setPos(camp)
            self.human.setH(heading)
            g = camp + heading_forward(heading) * 9.0
            self.giant.setPos(g.x, g.y, self.field.height(g.x, g.y) - self.giant_actor.height_world * GROUND_SINK_FRACTION)
            self.giant.setH(heading + 180.0)
            self.giant_motion_heading = self.giant.getH()
            r = camp - heading_forward(heading) * 260.0
            self.red_giant.setPos(r.x, r.y, self.field.height(r.x, r.y))
        self.heat = 0.0
        self.stamina = 100.0
        self.say('you wake at camp, sand in your mouth.' if camp is not None else 'you wake where it began.', 3.0)
        self._update_control_text()
        self._snap_camera_to_controlled(immediate=True)
        return True

    def _update_red_giant(self, dt: float, clock_t: float):
        """Autonomous hostile pursuit using the same heavy giant locomotion rules."""
        if self.red_giant is None:
            return
        self.red_stomp_cooldown = max(0.0, self.red_stomp_cooldown - dt)
        if self.red_dead:                  # Pass 47: it lies where it fell
            self.red_state = 'dead'
            return
        if hasattr(self, 'update_crimson') and self.update_crimson(dt, clock_t):
            return                         # Pass 60: at night, awake, calling a crimson wave
        if self._update_red_knockout_and_flee(dt, clock_t):
            return
        if self._update_red_endgame(dt, clock_t):   # Pass 47: drawn to a poisoned blood branch
            return
        if self._update_red_calm(dt, clock_t):      # Pass 53: the day after a knock-out
            return
        if self._update_red_lurk(dt, clock_t):
            return
        if hasattr(self, '_update_red_life') and self._update_red_life(dt, clock_t):
            return                         # Pass 48: resting, eating, foraging, or following your tracks
        if not self.red_alive:
            self.red_state = 'dead'
            return
        if self._update_melee_state('red', dt, clock_t):
            self.red_state = 'melee'
            return
        if not self.human_alive and not self.indigo_defending:
            self.red_state = 'idle'
            self.red_motion_speed = approach(self.red_motion_speed, 0.0, GIANT_BRAKING * dt)
            self.red_giant_actor.apply_clip('Idle_Loop', clock_t)
            return
        # Pass 39: the human is hiding in a shell — search, or heave it over.
        if self._update_red_vs_shell(dt, clock_t):
            return
        to_human, distance, target_name = self._red_target_vector()
        self.red_last_distance = distance
        if self.red_returning and distance <= RED_DETECTION_RANGE * 0.6:
            self.red_returning = False

        if target_name == 'giant' and self.giant_alive and distance <= GIANT_MELEE_RANGE:
            self.red_state = 'melee'
            self.red_motion_speed = approach(self.red_motion_speed, 0.0, GIANT_BRAKING * dt)
            self._face_actor('red', self.giant, dt)
            self._start_melee('red')
            return

        if self.red_state == 'stomp':
            self.red_motion_speed = approach(self.red_motion_speed, 0.0, GIANT_BRAKING * dt)
            self.red_stomp_elapsed += dt
            # Jump_Land gives a short downward/weight-bearing action without inventing a new clip.
            sample = min(self.red_stomp_elapsed, self.red_giant_actor.clips['Jump_Land']['duration'] - 1e-4)
            self.red_giant_actor.apply_clip('Jump_Land', sample, loop=False)
            if not self.red_stomp_hit_done and self.red_stomp_elapsed >= RED_STOMP_HIT_TIME:
                self.red_stomp_hit_done = True
                self.sfx('stomp_red', self.red_giant.getPos(self.render))
                self._apply_red_stomp_hit()
            if self.red_stomp_elapsed >= 0.72:
                self.red_state = 'pursue' if distance <= self.red_detection_range() else 'idle'
                self.red_stomp_elapsed = 0.0
                self.red_stomp_cooldown = self.red_stomp_cooldown_value()
                self.red_giant_actor.apply_clip('Idle_Loop', clock_t, force=True)
            return

        if distance > self.red_detection_range() and not self.red_returning:
            self.red_state = 'idle'
            self.red_motion_speed = approach(self.red_motion_speed, 0.0, GIANT_BRAKING * dt)
            self.red_giant_actor.apply_clip('Idle_Loop', clock_t)
            return

        if target_name == 'human' and distance <= RED_STOMP_RANGE and self.red_stomp_cooldown <= 0.0:
            self.red_state = 'stomp'
            self.red_stomp_elapsed = 0.0
            self.red_stomp_hit_done = False
            self.red_stomp_attempts += 1
            self.red_giant_actor.apply_clip('Jump_Land', 0.0, force=True, loop=False)
            return

        self.red_state = 'pursue'
        if to_human.length_squared() <= 1e-8:
            self.red_giant_actor.apply_clip('Idle_Loop', clock_t)
            return

        to_human.normalize()
        target_heading = heading_toward(to_human.x, to_human.y)
        heading_delta = ((target_heading - self.red_motion_heading + 180.0) % 360.0) - 180.0
        max_turn = GIANT_TURN_RATE_DEG * dt
        self.red_motion_heading += clamp(heading_delta, -max_turn, max_turn)
        self.red_giant.setH(self.red_motion_heading)

        # Pass 48: its mood decides how it comes - sprinting (aggressive), creeping (sneaky),
        # or standing very still while you look at it.
        style = self.red_pursuit_style(distance) if hasattr(self, 'red_pursuit_style') else (
            'walk' if distance <= RED_APPROACH_WALK_RANGE else 'sprint')
        if style == 'freeze':
            self.red_state = 'watching'
            self.red_motion_speed = approach(self.red_motion_speed, 0.0, GIANT_BRAKING * dt)
            self.red_giant_actor.apply_clip('Idle_Loop', clock_t)
            return
        pace = self.red_pace() if hasattr(self, 'red_pace') else 1.0
        if style == 'sprint':
            clip, target_speed = locomotion.gait('giant', 'sprint')
            target_speed *= pace
        else:
            k = 0.6 if style == 'sneak' else 1.0     # Pass 49: sneaky creeps (~2.2 m/s)
            clip, target_speed = locomotion.gait('giant', 'walk')
            target_speed *= pace * k
        self.red_motion_speed = approach(self.red_motion_speed, target_speed, GIANT_ACCELERATION * dt)
        forward = heading_forward(self.red_motion_heading)
        pos = self.red_giant.getPos() + forward * self.red_motion_speed * dt
        sink = self.red_giant_actor.height_world * GROUND_SINK_FRACTION
        pos.z = self.field.height(pos.x, pos.y) - sink
        old_pos = self.red_giant.getPos()
        self.red_giant.setPos(pos)
        self.stride('red', clip, Vec3(pos.x-old_pos.x, pos.y-old_pos.y, 0).length())   # Pass 52

    def simulate_red_hunt(self, seconds: float, steps: int = 180):
        dt = seconds / max(1, steps)
        for i in range(steps):
            self._update_red_giant(dt, i * dt)

    def _red_giant_task(self, task):
        if self.world_frozen():
            return Task.cont
        self._update_red_giant(min(globalClock.getDt(), 0.05), task.time)
        return Task.cont

    def _movement_task(self, task):
        if self.world_frozen():
            return Task.cont
        dt = min(globalClock.getDt(), 0.05)
        h = math.radians(self.heading)
        forward = Vec3(math.sin(h), math.cos(h), 0)
        right = Vec3(math.cos(h), -math.sin(h), 0)
        move = Vec3(0,0,0)
        if self.keys['w']: move += forward
        if self.keys['s']: move -= forward
        if self.keys['d']: move += right
        if self.keys['a']: move -= right
        if self.controlled_name == 'giant':
            self._apply_giant_heavy_input(move, dt, task.time)
        else:
            self._apply_controlled_move(move, dt, task.time)
        return Task.cont

    def _set_key(self, key, value):
        self.keys[key] = value

    def _zoom(self, amount):
        profile = self._camera_profile()
        self.distance = clamp(self.distance + amount, profile['zoom_min'], profile['zoom_max'])

    def _reset_camera(self):
        self._snap_camera_to_controlled(immediate=False)

    def _active_load_radius(self):
        return GIANT_FAR_RADIUS if self.controlled_name == 'giant' else HUMAN_LOAD_RADIUS

    def _desired_lod_map(self, cx, cy):
        if self.controlled_name == 'human':
            radius = HUMAN_LOAD_RADIUS
            return {(cx+dx, cy+dy): 'near'
                    for dy in range(-radius, radius+1)
                    for dx in range(-radius, radius+1)}
        desired = {}
        for dy in range(-GIANT_FAR_RADIUS, GIANT_FAR_RADIUS+1):
            for dx in range(-GIANT_FAR_RADIUS, GIANT_FAR_RADIUS+1):
                coord = (cx+dx, cy+dy)
                desired[coord] = 'near' if max(abs(dx), abs(dy)) <= GIANT_NEAR_RADIUS else 'far'
        return desired

    def _desired_coords(self, cx, cy):
        return set(self._desired_lod_map(cx, cy))

    def _load_chunk(self, coord, lod='near'):
        cx, cy = coord
        cells = CHUNK_CELLS if lod == 'near' else FAR_CHUNK_CELLS
        node, sig = build_chunk(self.field, cx, cy, cells=cells, far_lod=(lod == 'far'))
        self._attach_chunk(coord, lod, node, sig)

    def _attach_chunk(self, coord, lod, node, sig):
        cx, cy = coord
        np = self.render.attachNewNode(node)
        np.setPos(cx * CHUNK_SIZE, cy * CHUNK_SIZE, 0)
        np.hide(SHADOW_CAMERA_MASK)
        np.setShaderInput('edge_ink', TERRAIN_EDGE_INK)
        old = self.loaded.get(coord)
        self.loaded[coord] = np
        self.loaded_lod[coord] = lod
        self.chunk_signatures[coord] = sig
        self.load_count += 1
        if old is not None:
            old.removeNode()
            self.unload_count += 1

    def _chunk_wanted(self, coord, lod) -> bool:
        return self.desired_lods.get(coord) == lod and self.loaded_lod.get(coord) != lod

    def _advance_chunk_job(self, deadline: float) -> bool:
        """Pass 54: work on the chunk being built until the deadline. True when one was finished.
        The chunk stays in pending_loads until it is done (so 'still loading' checks hold)."""
        job = getattr(self, '_chunk_job', None)
        if job is not None and not self._chunk_wanted(job.coord, job.lod):
            job = self._chunk_job = None                  # the player moved on: not needed any more
        if job is None:
            while self.pending_loads and not self._chunk_wanted(*self.pending_loads[0]):
                self.pending_loads.popleft()
            if not self.pending_loads:
                return False
            coord, lod = self.pending_loads[0]
            cells = CHUNK_CELLS if lod == 'near' else FAR_CHUNK_CELLS
            job = self._chunk_job = ChunkBuild(self.field, coord[0], coord[1], cells, lod == 'far')
        if not job.step(deadline):
            return False
        node, sig = job.finish()
        self._attach_chunk(job.coord, job.lod, node, sig)
        self._chunk_job = None
        try:
            self.pending_loads.remove((job.coord, job.lod))
        except ValueError:
            pass
        return True

    def _update_stream(self, force=False):
        cx, cy = world_to_chunk(self.cam_target.x), world_to_chunk(self.cam_target.y)
        if not force and self.center_chunk == (cx, cy):
            return
        self.center_chunk = (cx, cy)
        self.desired_lods = self._desired_lod_map(cx, cy)
        self.desired_coords = set(self.desired_lods)
        need = []
        for coord, lod in self.desired_lods.items():
            if coord not in self.loaded or self.loaded_lod.get(coord) != lod:
                need.append((coord, lod))
        # Near replacements first, then closest far chunks.
        need.sort(key=lambda item: (0 if item[1] == 'near' else 1,
                                    (item[0][0]-cx)**2 + (item[0][1]-cy)**2,
                                    item[0][1], item[0][0]))
        self.pending_loads = deque(need)

    def service_stream_queue(self, max_chunks: int = CHUNKS_PER_FRAME):
        """Build up to max_chunks chunks completely (finishing any half-built one first)."""
        built = 0
        while built < max_chunks and self._advance_chunk_job(float('inf')):
            built += 1
        if not self.pending_loads and getattr(self, '_chunk_job', None) is None:
            stale = sorted(set(self.loaded) - self.desired_coords)
            for coord in stale:
                self.loaded.pop(coord).removeNode()
                self.loaded_lod.pop(coord, None)
                self.chunk_signatures.pop(coord, None)
                self.unload_count += 1
        return built

    def finalizeExit(self):
        """Quit cleanly.  The journey is already saved (SaveMixin.userExit) and audio stopped.
        Skipping Python's interpreter teardown avoids an OpenAL crash seen at exit after
        streamed music has played (and makes quitting instant)."""
        try:
            self.destroy()
        except Exception:
            pass
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)

    def invalidate_terrain_near(self, circles):
        """Rebuild loaded chunks touching any (x, y, radius) circle - after the ground there changed."""
        for coord in list(self.loaded):
            x0, y0 = coord[0] * CHUNK_SIZE, coord[1] * CHUNK_SIZE
            for cx, cy, r in circles:
                nx = clamp(cx, x0, x0 + CHUNK_SIZE)
                ny = clamp(cy, y0, y0 + CHUNK_SIZE)
                if (nx - cx) ** 2 + (ny - cy) ** 2 <= r * r:
                    self.loaded_lod[coord] = 'stale'
                    break
        self._update_stream(force=True)

    # ------------------------------------------------------------ Pass 50: rebindable actions
    def bind_action(self, action: str, handler, extra=None):
        """Accept the key bound to `action`, remembering it so it can be rebound in game."""
        entries = [e for e in self._action_handlers.get(action, []) if e[0] != 'press']
        entries.append(('press', handler, list(extra or [])))
        self._action_handlers[action] = entries
        self._accept_entries(action)

    def bind_held(self, action: str, flag: str):
        entries = [e for e in self._action_handlers.get(action, []) if e[0] != 'held']
        self._action_handlers[action] = [('held', flag, None)] + entries
        self._accept_entries(action)

    def _accept_entries(self, action: str):
        key = self.bindings[action]
        if not key:
            return                                     # Pass 63: unbound (TAB while hosted)
        for kind, target, extra in self._action_handlers.get(action, []):
            if kind == 'held':
                self.accept(key, self._held_key, [target, True])
                self.accept(key + '-up', self._set_key, [target, False])
            else:
                # a press handler wins over the held flag's key-down
                self.accept(key, self._pressed_key, [target, list(extra or [])])

    def _key_capture_busy(self) -> bool:
        """Pass 54: while a key is being chosen in Settings > keys (and on the frame it is chosen),
        that key press must not also do its old job (J opening the journal, F5 saving ...)."""
        return (getattr(self, '_capturing_key', None) is not None
                or getattr(self, '_capture_end_frame', -1) == globalClock.getFrameCount())

    def _pressed_key(self, handler, extra):
        if not self._key_capture_busy():
            handler(*extra)

    def _held_key(self, flag, value):
        if not self._key_capture_busy():
            self._set_key(flag, value)

    def rebind(self, action: str, key: str):
        """Move `action` to `key` right now (the caller resolves clashes)."""
        old = self.bindings.get(action)
        if old:
            self.ignore(old)
            self.ignore(old + '-up')
            for kind, target, _extra in self._action_handlers.get(action, []):
                if kind == 'held':
                    self._set_key(target, False)
        self.bindings[action] = key
        self._accept_entries(action)

    def input_blocked(self) -> bool:
        """Pass 44: no actions while paused (Esc menu), falling asleep or waking."""
        return self.world_frozen() or getattr(self, 'panel_name', None) in ('menu',)

    def world_frozen(self) -> bool:
        return (getattr(self, 'paused', False) or (hasattr(self, 'sleeping') and self.sleeping())
                or getattr(self, 'gleebs_state', None) in ('leaving', 'gone'))      # Pass 61: the last scene

    def drain_stream_queue(self):
        while self.pending_loads:
            self.service_stream_queue(max_chunks=max(1, len(self.pending_loads)))
        self.service_stream_queue(max_chunks=0)

    def _update_visibility(self, dt: float):
        # Giant fog only opens once all giant-ring chunks exist. If new far chunks are
        # queued after movement, tighten the fog again until the replacement ring is ready.
        if self.controlled_name == 'giant':
            self.target_fog_density = GIANT_FOG_DENSITY if not self.pending_loads else HUMAN_FOG_DENSITY
        else:
            self.target_fog_density = HUMAN_FOG_DENSITY
        alpha = clamp(max(0.0, dt) * FOG_TRANSITION_SPEED, 0.0, 1.0)
        self.current_fog_density += (self.target_fog_density - self.current_fog_density) * alpha
        self.render.setShaderInput('fog_density', self.current_fog_density)
        self.render.setShaderInput('fog_end', self._fog_end(dt))
        if self.controlled_name == 'giant':
            self.render.setShaderInput('soft_start', GIANT_SOFT_START)
            self.render.setShaderInput('soft_end', GIANT_SOFT_END)
        else:
            self.render.setShaderInput('soft_start', HUMAN_SOFT_START)
            self.render.setShaderInput('soft_end', HUMAN_SOFT_END)

    def ground_radius(self) -> float:
        """Pass 46: how far out from the focus the ground is certainly built (metres)."""
        cx, cy = getattr(self, 'center_chunk', None) or (0, 0)
        desired = getattr(self, 'desired_coords', None) or ()
        loaded = getattr(self, 'loaded', {})
        missing = [max(abs(x - cx), abs(y - cy)) for x, y in desired if (x, y) not in loaded]
        ring = min(missing) if missing else self._active_load_radius() + 1
        return max(1.0, ring - 1) * CHUNK_SIZE

    def _fog_end(self, dt: float = 0.0) -> float:
        """Pass 46: distance at which the fog is total - always inside the built ground, so
        the edge of the streamed world is never visible.  Pulls in at once, eases back out."""
        target = self.ground_radius()
        cur = getattr(self, '_fog_end_now', target)
        cur = target if target < cur or dt <= 0.0 else cur + (target - cur) * clamp(dt * 1.2, 0.0, 1.0)
        self._fog_end_now = cur
        return cur

    def settle_visibility(self, seconds: float = 3.0, step: float = 0.05):
        remaining = max(0.0, seconds)
        while remaining > 1e-9:
            dt = min(step, remaining)
            self._update_visibility(dt)
            remaining -= dt

    def _stream_task(self, task):
        # Pass 46: build ground for up to STREAM_BUDGET_MS each frame, so riding Indigo at full
        # stride never outruns it. Pass 54: a chunk is built in slices across frames, so no
        # single frame stalls for a whole chunk (it used to cost ~10 ms at once).
        deadline = time.perf_counter() + STREAM_BUDGET_MS / 1000.0
        while self.pending_loads and time.perf_counter() < deadline:
            if not self._advance_chunk_job(deadline):
                break
        if not self.pending_loads:
            self.service_stream_queue(0)
        return Task.cont

    def _visibility_task(self, task):
        self._update_visibility(min(globalClock.getDt(), 0.05))
        return Task.cont

    def set_target(self, x: float, y: float, z: float = 0.0, drain: bool = False):
        self.cam_target = Vec3(x, y, z)
        self._update_stream()
        if drain:
            self.drain_stream_queue()
        self._place_camera()

    def _place_camera(self, immediate: bool = True, dt: float = 0.0):
        if getattr(self, 'gleebs_state', None) == 'leaving' and self.place_scene_camera():
            return                                 # Pass 61: the leaving scene frames its own shots
        # Pass 58: pitch below CAMERA_ORBIT_LOW orbits the camera round the anchor as before;
        # above it the camera holds low behind the anchor and tilts up by the rest.
        look_up = max(0.0, self.pitch - CAMERA_ORBIT_LOW)
        orbit = min(self.pitch, CAMERA_ORBIT_LOW)
        h, p = math.radians(self.heading), math.radians(orbit)
        dist = self.distance * (1.0 - CAMERA_LOOKUP_CLOSER * clamp(look_up / (CAMERA_PITCH_MAX - CAMERA_ORBIT_LOW), 0.0, 1.0))
        planar = dist * math.cos(p)
        right = Vec3(math.cos(h), -math.sin(h), 0)
        desired_pos = self.cam_target + Vec3(-math.sin(h) * planar,
                                             -math.cos(h) * planar,
                                             -math.sin(p) * dist)
        desired_pos += right * self.camera_side_offset
        if immediate:
            new_pos = desired_pos
            self.camera_render_target = Vec3(self.cam_target)
            self._look_up = look_up
        else:
            alpha = 1.0 - math.exp(-CAMERA_SMOOTH_RATE * max(0.0, dt))
            cur = self.camera.getPos()
            new_pos = cur + (desired_pos - cur) * alpha
            self.camera_render_target += (self.cam_target - self.camera_render_target) * alpha
            self._look_up = getattr(self, '_look_up', 0.0) + (look_up - getattr(self, '_look_up', 0.0)) * alpha
        field = getattr(self, 'field', None)
        if field is not None:                      # never under the sand (dunes behind you, looking up)
            floor = field.height(new_pos.x, new_pos.y) + CAMERA_GROUND_CLEAR.get(self.controlled_name, 0.45)
            if new_pos.z < floor:
                new_pos = Point3(new_pos.x, new_pos.y, floor)
        self.camera.setPos(new_pos)
        self.camera.lookAt(self.camera_render_target)
        if self._look_up > 1e-3:
            self.camera.setP(self.camera.getP() + self._look_up)
        self._sync_sun_shader()

    def settle_camera(self, seconds: float = 1.0, step: float = 1.0 / 60.0):
        remaining = max(0.0, seconds)
        while remaining > 1e-9:
            dt = min(step, remaining)
            self.cam_target = self._controlled_focus()
            self._place_camera(immediate=False, dt=dt)
            remaining -= dt

    def _pointer_xy(self):
        win = getattr(self, 'win', None)
        if win is None or not hasattr(win, 'getPointer'):
            return None
        p = win.getPointer(0)
        return (p.getX(), p.getY()) if p.getInWindow() else None

    def _begin_orbit(self):
        self._orbit_drag = self._pointer_xy()

    def _end_orbit(self):
        self._orbit_drag = None

    def _update_mouse_orbit(self):
        if self._orbit_drag is None:
            return
        cur = self._pointer_xy()
        if cur is None:
            return
        dx, dy = cur[0] - self._orbit_drag[0], cur[1] - self._orbit_drag[1]
        self._orbit_drag = cur
        sens = MOUSE_ORBIT_SENSITIVITY * self.settings.get('mouse_sensitivity', 1.0)   # Pass 50
        if self.settings.get('invert_y'):
            dy = -dy
        self.heading += dx * sens
        self.pitch = clamp(self.pitch - dy * sens, CAMERA_PITCH_MIN, CAMERA_PITCH_MAX)

    def _camera_task(self, task):
        dt = min(globalClock.getDt(), 0.05)
        self._update_mouse_orbit()
        orbit = 36.0 * dt
        if self.keys['left']:
            self.heading -= orbit
        if self.keys['right']:
            self.heading += orbit
        if self.keys['up']:
            self.pitch = clamp(self.pitch + orbit, CAMERA_PITCH_MIN, CAMERA_PITCH_MAX)     # Pass 58: up looks up
        if self.keys['down']:
            self.pitch = clamp(self.pitch - orbit, CAMERA_PITCH_MIN, CAMERA_PITCH_MAX)
        self.cam_target = self._controlled_focus()
        self._place_camera(immediate=False, dt=dt)
        return Task.cont

    def _spawn_giant_and_human(self, giant_glb: Path):
        giant_palette = [Vec4(0.27, 0.54, 0.92, 1.0), Vec4(0.12, 0.29, 0.63, 1.0)]
        human_palette = [Vec4(0.77, 0.73, 0.70, 1.0), Vec4(0.53, 0.48, 0.45, 1.0)]
        self.giant_actor = HumanoidActor(self.render, giant_glb, GIANT_SCALE, name='indigo_giant', palette=giant_palette)
        for _combat_clip in ('Punch_Jab', 'Punch_Cross', 'Hit_Chest', 'Death01'):
            self.giant_actor._load_clip(giant_glb, _combat_clip)
        self.giant = self.giant_actor.root
        self.giant_height = self.giant_actor.height_world
        gx, gy = giant_start_xy()
        gz = self.field.height(gx, gy) - self.giant_actor.height_world * GROUND_SINK_FRACTION
        self.giant_base_pos = Point3(gx, gy, gz)
        self.giant.setPos(self.giant_base_pos)
        self.giant.setH(205)

        self.human_actor = HumanoidActor(self.render, giant_glb, 1.0, name='small_human', palette=human_palette)
        self.human = self.human_actor.root
        self.human_height = self.human_actor.height_world
        # Place the human just beside the giant's nearest foot for scale readability.
        hx, hy = human_start_xy()
        hz = self.field.height(hx, hy) - self.human_actor.height_world * GROUND_SINK_FRACTION
        self.human_base_pos = Point3(hx, hy, hz)
        self.human.setPos(self.human_base_pos)
        self.human.setH(28)
        self.human_actor.apply_clip('Idle_Loop', 0.15, force=True)

        # Hostile Red Giant: same rig/scale/animation foundation, autonomous only.
        red_palette = [Vec4(0.73, 0.16, 0.14, 1.0), Vec4(0.42, 0.055, 0.045, 1.0)]
        self.red_giant_actor = HumanoidActor(self.render, giant_glb, GIANT_SCALE, name='red_giant', palette=red_palette, clip_names=['Idle_Loop','Walk_Loop','Sprint_Loop','Jump_Land','Punch_Jab','Punch_Cross','Hit_Chest','Death01'])
        self.red_giant = self.red_giant_actor.root
        self.red_giant_height = self.red_giant_actor.height_world
        # Spawn well away from the player but inside the initial awareness range.
        rx = hx + RED_SPAWN_DISTANCE
        ry = hy + 10.0
        rz = self.field.height(rx, ry) - self.red_giant_actor.height_world * GROUND_SINK_FRACTION
        self.red_giant_base_pos = Point3(rx, ry, rz)
        self.red_giant.setPos(self.red_giant_base_pos)
        self.red_giant.setH(self.red_motion_heading)
        self.red_giant_actor.apply_clip('Idle_Loop', 0.0, force=True)

    def _toggle_frame_meter(self):
        self.setFrameRateMeter(not bool(getattr(self, 'frameRateMeter', None)))

    def _giant_idle_task(self, task):
        return Task.cont

    def capture(self, output: Path):
        for _ in range(6):
            self.graphicsEngine.renderFrame()
        return bool(self.win.saveScreenshot(str(output)))


survival.bind_constants(globals())


def _validate_required_runtime_files(giant_glb: Path):
    base_dir = paths.ROOT
    required = (
        ('Indigo Giant animation GLB', Path(giant_glb)),
        ('sketch vertex shader', base_dir / 'shaders' / 'sketch.vert'),
        ('sketch fragment shader', base_dir / 'shaders' / 'sketch.frag'),
    )
    bad = []
    for label, path in required:
        if not path.is_file():
            bad.append(f'{label}: MISSING: {path}')
        elif path.stat().st_size <= 0:
            bad.append(f'{label}: EMPTY: {path}')
    if bad:
        raise FileNotFoundError(
            'The Indigo Giant cannot start because required files are missing or empty:\n'
            + '\n'.join(bad)
            + '\nRestore these files from the same accepted build; do not continue from an incomplete package.'
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--offscreen', action='store_true')
    ap.add_argument('--screenshot', type=Path)
    ap.add_argument('--seed', type=int, default=SEED)
    ap.add_argument('--no-vsync', action='store_true', help='Uncapped frame rate (benchmarking only)')
    ap.add_argument('--fps', action='store_true', help='Show the frame-rate meter at launch (F3 toggles it)')
    ap.add_argument('--new', action='store_true', help='Start a new journey (the old save is kept as a backup)')
    ap.add_argument('--no-title', action='store_true', help='Skip the title screen (straight into the journey)')
    ap.add_argument('--giant-glb', type=Path, default=paths.GIANT_GLB)
    args = ap.parse_args()
    _validate_required_runtime_files(args.giant_glb)
    app = StreamingTerrainWithGiant(offscreen=args.offscreen, seed=args.seed, giant_glb=args.giant_glb,
                                    vsync=False if args.no_vsync else None, show_fps=args.fps, new_game=args.new,
                                    show_title=False if (args.no_title or args.offscreen) else None)
    print('SEED', args.seed)
    print('CHUNK_SIZE', CHUNK_SIZE)
    print('ACTIVE_CHUNKS', len(app.loaded))
    print('CENTER_CHUNK', app.center_chunk)
    print('LOAD_COUNT', app.load_count)
    print('UNLOAD_COUNT', app.unload_count)
    if app.giant:
        print('GIANT_SCALE', GIANT_SCALE)
        print('GIANT_HEIGHT_WORLD', round(app.giant_height, 3))
        print('GIANT_POSITION', tuple(round(v, 3) for v in (app.giant_base_pos.x, app.giant_base_pos.y, app.giant_base_pos.z)))
    if app.red_giant:
        print('RED_GIANT_HEIGHT_WORLD', round(app.red_giant_height, 3))
        print('RED_GIANT_POSITION', tuple(round(v, 3) for v in app.red_giant.getPos()))
        print('RED_GIANT_STATE', app.red_state)
        print('INDIGO_HEALTH', round(app.giant_health, 1))
        print('RED_HEALTH', round(app.red_health, 1))
        print('RED_KNOCKED_OUT', app.red_knocked_out)
        print('RED_KO_REMAINING', round(app.red_knockout_remaining, 2))
        print('RED_FLEEING', app.red_fleeing)
        print('COMBAT_HITS', app.combat_hits)
    if app.human:
        print('HUMAN_HEIGHT_WORLD', round(app.human_height, 3))
        print('HUMAN_POSITION', tuple(round(v, 3) for v in (app.human_base_pos.x, app.human_base_pos.y, app.human_base_pos.z)))
        print('HEIGHT_RATIO', round(app.giant_height / max(app.human_height, 1e-6), 3))
    print('SKETCH_STYLE_ENABLED', app.sketch_style_enabled)
    print('SUN_AZIMUTH_DEG', app.sun_azimuth_deg)
    print('SUN_ELEVATION_DEG', app.sun_elevation_deg)
    if getattr(app, 'actor_shadows', None):
        print('GIANT_SHADOW_EXTENT', round(app.actor_shadows['giant'].last_extent, 3))
    print('SHADOW_MAP_SIZE', SHADOW_MAP_SIZE)
    print('ACTIVE_LOAD_RADIUS', app._active_load_radius())
    print('FOG_DENSITY', round(app.current_fog_density, 6))
    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        if app.giant:
            app.giant_actor.apply_clip('Idle_Loop', 0.85, force=True)
            if app.human:
                app.human_actor.apply_clip('Idle_Loop', 0.15, force=True)
            app.cam_target = Vec3(app.giant_base_pos.x - 0.7, app.giant_base_pos.y - 0.25, app.giant_base_pos.z + app.giant_height * 0.26)
            app.distance = 56.0
            app.heading = 82.0
            app.pitch = -10.5
            app._place_camera()
        if not app.capture(args.screenshot):
            raise SystemExit('Screenshot capture failed')
        print('SCREENSHOT', args.screenshot)
        app.destroy()
    else:
        app.run()


if __name__ == '__main__':
    main()
