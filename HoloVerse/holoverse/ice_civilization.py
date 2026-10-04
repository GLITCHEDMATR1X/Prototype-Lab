"""Ice ring civilization (Pass 282.54): pure, deterministic layout and life.

No Panda3D here, so everything can be tested headless.  ``ice_visuals`` turns
the pieces into meshes; ``world.py`` owns terrain, chunks and collision.

Per sector of the Ice ring (ring key 6, r 3050-3750):

* **Frost towns** - every third sector (16 towns): a walled glacier town of the
  peaceful Frostkin.  A stepped crystal temple with a great glowing crystal
  in the plaza, snow-dome halls with lit doorways, tall crystal towers joined
  by arched ice bridges, amber lantern posts round the plaza, a crystal wall
  with two gates, and a frozen skating lake just outside.
* **Wilds** - every sector: clusters of leaning ice spires (12-65 m) with
  base shards and floating shards, smooth snow-buried glacier ridges with
  crystal fins, Frostkin waystone shrines with lanterns, a natural ice arch in
  every other sector and a 90-130 m landmark spire in every fourth.
* **Life** - Frostkin walking the plaza and visiting the halls, skaters on the
  lakes and frost-mammoth herds grazing the open ice.  Nobody fights.

Everything keeps clear of the Frost Circuit course (true segment distance to
its centreline), Mirror's post, the Ice travel landing, the four travel
corridors and the ring edges.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from holoverse.frost_track import sampled_world_centerline
from holoverse.region_kit import RING_EDGE_MARGIN, CircleObstacle, OObstacle, Piece, Villager, hash_key, make_villagers, ring_spot_is_clear
from holoverse.region_kit import villager_pose as _villager_pose
from holoverse.region_kit import angle_delta as _angle_delta
from holoverse.region_kit import base_z as _base
from holoverse.region_kit import local as _local

TAU = math.tau
SEED = 28254
SECTOR_COUNT = 48

TRACK_CLEARANCE = 165.0       # centreline -> structure edge: beyond the race reset envelope (160 m)
MIRROR_CLEARANCE = 120.0
LANDING_CLEARANCE = 60.0
TOWN_SECTOR_STRIDE = 3        # sectors 1, 4, 7 ... hold a town
TOWN_WALL_RADIUS = 96.0
LAKE_RADIUS = 36.0
LIFE_ACTIVE_RADIUS = 700.0
RIDGE_MAX_LENGTH = 34.0       # half-length of a glacier ridge

# Palette ---------------------------------------------------------------------
SNOW = (0.80, 0.87, 0.94)
SNOW_SHADE = (0.66, 0.76, 0.86)
PACKED_ICE = (0.55, 0.68, 0.82)
GLACIER_BLUE = (0.46, 0.62, 0.84)
GLACIER_TOP = (0.68, 0.80, 0.93)
CRYSTAL = (0.40, 0.70, 0.98)
CRYSTAL_PALE = (0.62, 0.86, 1.00)
CRYSTAL_DEEP = (0.22, 0.46, 0.86)
FROST_STONE = (0.30, 0.36, 0.46)
LANTERN = (0.92, 0.56, 0.24)
DOOR_GLOW = (0.88, 0.50, 0.20)
ICE_GLOW = (0.42, 0.78, 0.92)
LAKE_ICE = (0.16, 0.32, 0.54)
PLAZA = (0.60, 0.70, 0.82)


# --------------------------------------------------------------------------
# Data records
# --------------------------------------------------------------------------
@dataclass
class Lake:
    x: float
    y: float
    r: float
    z: float


@dataclass
class Town:
    key: str
    sector: int
    x: float
    y: float
    heading: float           # local +x points outward (radial)
    z: float
    lake: Lake | None = None
    doors: list = field(default_factory=list)       # (x, y) hall doorways
    plaza_radius: float = 34.0
    tower_count: int = 0
    hall_count: int = 0


@dataclass
class Herd:
    key: str
    x: float
    y: float
    radius: float
    count: int
    seed: int


@dataclass
class IceSector:
    sector: int
    pieces: list = field(default_factory=list)
    obstacles: list = field(default_factory=list)
    towns: list = field(default_factory=list)
    herds: list = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    footprints: list = field(default_factory=list)  # (x, y, r) of everything placed
    mesh_cache: tuple | None = None                 # (rec, idx) filled by region_mesh_kit
    mesh_progress: list | None = None               # partial build between pre-warm steps


# --------------------------------------------------------------------------
# Keep-clear rules
# --------------------------------------------------------------------------
_TRACK_SEGMENTS = None
_TRACK_BBOX = None


def _track_segments():
    global _TRACK_SEGMENTS, _TRACK_BBOX
    if _TRACK_SEGMENTS is None:
        pts = sampled_world_centerline(160)
        _TRACK_SEGMENTS = [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        _TRACK_BBOX = (min(xs), min(ys), max(xs), max(ys))
    return _TRACK_SEGMENTS, _TRACK_BBOX


def track_distance(x: float, y: float) -> float:
    """True distance to the Frost Circuit centreline (segment projection)."""
    segs, (x0, y0, x1, y1) = _track_segments()
    # Outside the padded bounding box the course cannot be the closest thing.
    outside = max(x0 - x, 0.0, x - x1) ** 2 + max(y0 - y, 0.0, y - y1) ** 2
    if outside > 500.0 ** 2:
        return math.sqrt(outside)
    best = 1e30
    for (ax, ay), (bx, by) in segs:
        vx, vy = bx - ax, by - ay
        den = vx * vx + vy * vy
        t = 0.0 if den <= 1e-9 else max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / den))
        dx, dy = x - (ax + vx * t), y - (ay + vy * t)
        d2 = dx * dx + dy * dy
        if d2 < best:
            best = d2
    return math.sqrt(best)


def default_keep_clear(mirror_radius=3484.0, landing_radius=3428.0, anchor_deg=-90.0):
    a = math.radians(anchor_deg)
    return [
        (math.cos(a) * mirror_radius, math.sin(a) * mirror_radius, MIRROR_CLEARANCE),
        (math.cos(a) * landing_radius, math.sin(a) * landing_radius, LANDING_CLEARANCE),
    ]


def spot_is_clear(x, y, radius, r0, r1, keep_clear=(), placed=(), pad=6.0):
    if not ring_spot_is_clear(x, y, radius, r0, r1, keep_clear, placed, pad):
        return False
    return track_distance(x, y) >= TRACK_CLEARANCE + radius


# --------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------
def _spire(out, x, y, z, r, h, rng, rgb, *, lean_dir=None, lean=0.0, sides=None, obstacle=True):
    sides = sides or rng.choice((5, 6, 6, 7))
    ld = rng.uniform(0.0, TAU) if lean_dir is None else lean_dir
    lx, ly = math.cos(ld) * lean, math.sin(ld) * lean
    twist = rng.uniform(-0.35, 0.35)
    body_h = h * 0.78
    out.pieces.append(Piece("prism", (x, y, z, r, r * 0.42, body_h, sides), rgb, "crystal", {"lean": (lx * 0.78, ly * 0.78), "twist": twist * 0.7}))
    out.pieces.append(Piece("prism", (x + lx * 0.78, y + ly * 0.78, z + body_h, r * 0.42, 0.0, h - body_h, sides), CRYSTAL_PALE, "crystal", {"lean": (lx * 0.22, ly * 0.22), "twist": twist * 0.3}))
    if obstacle:
        out.obstacles.append(CircleObstacle(x, y, r * 0.9, z + h))


def _spire_cluster(out, cx, cy, height_fn, rng, tall=(12.0, 65.0)):
    n = rng.randint(4, 8)
    hero = rng.uniform(tall[1] * 0.7, tall[1])
    for k in range(n):
        if k == 0:
            x, y, h = cx, cy, hero
        else:
            a = rng.uniform(0.0, TAU)
            d = rng.uniform(6.0, 22.0)
            x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
            h = rng.uniform(tall[0], hero * 0.7)
        r = max(1.4, h * rng.uniform(0.07, 0.10))
        z = _base(height_fn, x, y, r, sink=1.2)
        away = math.atan2(y - cy, x - cx) if k else rng.uniform(0.0, TAU)
        rgb = rng.choice((CRYSTAL, CRYSTAL_PALE, CRYSTAL_DEEP, CRYSTAL))
        _spire(out, x, y, z, r, h, rng, rgb, lean_dir=away, lean=h * rng.uniform(0.02, 0.16))
    # Shards at the foot and a few floating overhead (the holo accent).
    for _ in range(rng.randint(6, 10)):
        a = rng.uniform(0.0, TAU)
        d = rng.uniform(4.0, 26.0)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        h = rng.uniform(1.8, 6.0)
        _spire(out, x, y, height_fn(x, y) - 0.4, h * 0.22, h, rng, CRYSTAL_PALE, lean_dir=a, lean=h * 0.35, sides=4, obstacle=False)
    for _ in range(rng.randint(2, 4)):
        a = rng.uniform(0.0, TAU)
        d = rng.uniform(4.0, 18.0)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        z = height_fn(x, y) + hero * rng.uniform(0.35, 0.75)
        s = rng.uniform(1.0, 2.4)
        out.pieces.append(Piece("prism", (x, y, z, 0.05, s, s * 1.2, 4), ICE_GLOW, "emissive"))
        out.pieces.append(Piece("prism", (x, y, z + s * 1.2, s, 0.05, s * 1.2, 4), ICE_GLOW, "emissive"))
    out.counts["spires"] = out.counts.get("spires", 0) + n
    out.counts["clusters"] = out.counts.get("clusters", 0) + 1


def _ice_arch(out, cx, cy, height_fn, rng):
    span = rng.uniform(44.0, 70.0)
    rise = rng.uniform(22.0, 34.0)
    heading = rng.uniform(0.0, TAU)
    ux, uy = math.cos(heading), math.sin(heading)
    ax, ay = cx - ux * span * 0.5, cy - uy * span * 0.5
    bx, by = cx + ux * span * 0.5, cy + uy * span * 0.5
    za, zb = height_fn(ax, ay) - 1.5, height_fn(bx, by) - 1.5
    path = []
    steps = 16
    for i in range(steps + 1):
        t = i / steps
        x, y = ax + (bx - ax) * t, ay + (by - ay) * t
        z = za + (zb - za) * t + math.sin(t * math.pi) * rise
        path.append((x, y, z))
    thick = rng.uniform(5.0, 7.0)
    out.pieces.append(Piece("sweep", (tuple(path), thick + 1.5, thick), CRYSTAL, "crystal"))
    out.pieces.append(Piece("sweep", (tuple((p[0], p[1], p[2] + thick * 0.55) for p in path), thick * 0.7, 1.4), SNOW, "snow"))
    for x, y, z in ((ax, ay, za), (bx, by, zb)):
        out.pieces.append(Piece("prism", (x, y, z - 1.0, thick * 0.95, thick * 0.6, rise * 0.30, 6), CRYSTAL_DEEP, "crystal"))
        out.obstacles.append(CircleObstacle(x, y, thick * 0.75, z + rise * 0.4))
    out.counts["arches"] = out.counts.get("arches", 0) + 1


def _glacier_ridge(out, cx, cy, height_fn, rng):
    """A long, smooth snow-buried glacier ridge with crystal fins along its crest."""
    length = rng.uniform(18.0, RIDGE_MAX_LENGTH)
    width = rng.uniform(6.0, 11.0)
    rise = rng.uniform(7.0, 14.0)
    heading = rng.uniform(0.0, TAU)
    ux, uy = math.cos(heading), math.sin(heading)
    z = min(height_fn(cx + ux * length * f, cy + uy * length * f) for f in (-0.8, 0.0, 0.8))
    out.pieces.append(Piece("ellipsoid", (cx, cy, z - rise * 0.45, length, width, rise), GLACIER_BLUE, "snow", {"heading": heading, "rings": 6, "sides": 12}))
    out.pieces.append(Piece("ellipsoid", (cx + ux * length * 0.15, cy + uy * length * 0.15, z - rise * 0.25, length * 0.62, width * 0.55, rise * 0.95), GLACIER_TOP, "snow", {"heading": heading + 0.05, "rings": 5, "sides": 12}))
    out.pieces.append(Piece("ellipsoid", (cx - ux * length * 0.3, cy - uy * length * 0.3, z - rise * 0.5, length * 0.5, width * 0.8, rise * 0.85), CRYSTAL_DEEP, "crystal", {"heading": heading - 0.08, "rings": 5, "sides": 10}))
    crest = z + rise * 0.50
    fins = rng.randint(3, 6)
    for k in range(fins):
        f = -0.6 + 1.2 * k / max(1, fins - 1)
        fx, fy = cx + ux * length * f * 0.8, cy + uy * length * f * 0.8
        fh = rng.uniform(3.0, 9.0)
        side = rng.choice((-1.0, 1.0))
        _spire(out, fx, fy, crest - 1.2, fh * 0.16, fh, rng, rng.choice((CRYSTAL, CRYSTAL_PALE)), lean_dir=heading + side * math.pi * 0.5, lean=fh * 0.3, sides=5, obstacle=False)
    out.obstacles.append(OObstacle(cx, cy, length * 1.5, width * 1.2, heading, z + rise * 0.55))
    out.counts["ridges"] = out.counts.get("ridges", 0) + 1


def _waystone(out, x, y, height_fn, rng):
    """A Frostkin roadside shrine: stacked snow stones, a crystal and a lantern."""
    z = height_fn(x, y) - 0.3
    out.pieces.append(Piece("ellipsoid", (x, y, z + 0.5, 1.3, 1.1, 0.75), FROST_STONE, "plain", {"heading": rng.uniform(0.0, TAU), "rings": 5, "sides": 10}))
    out.pieces.append(Piece("ellipsoid", (x, y, z + 1.45, 0.95, 0.8, 0.55), SNOW_SHADE, "snow", {"heading": rng.uniform(0.0, TAU), "rings": 5, "sides": 10}))
    out.pieces.append(Piece("prism", (x, y, z + 1.8, 0.45, 0.0, 2.6, 5), CRYSTAL_PALE, "crystal"))
    lx, ly = x + 1.6, y
    out.pieces.append(Piece("prism", (lx, ly, z, 0.12, 0.10, 2.6, 5), FROST_STONE, "plain"))
    out.pieces.append(Piece("obox", (lx, ly, z + 2.6, 0.36, 0.36, 0.45, 0.0), LANTERN, "emissive"))
    out.obstacles.append(CircleObstacle(x, y, 1.3, z + 4.4))
    out.counts["waystones"] = out.counts.get("waystones", 0) + 1


def _landmark(out, x, y, height_fn, rng):
    h = rng.uniform(90.0, 130.0)
    r = h * 0.075
    z = _base(height_fn, x, y, r, sink=2.0)
    _spire(out, x, y, z, r, h, rng, CRYSTAL_DEEP, lean=h * 0.05, sides=7)
    for k in range(5):
        a = TAU * k / 5.0 + rng.uniform(-0.3, 0.3)
        d = r * 1.3
        sx, sy = x + math.cos(a) * d, y + math.sin(a) * d
        sh = h * rng.uniform(0.22, 0.42)
        _spire(out, sx, sy, height_fn(sx, sy) - 1.0, r * 0.45, sh, rng, CRYSTAL, lean_dir=a, lean=sh * 0.25)
    # A slow glowing halo ring two thirds up (one emissive band).
    out.pieces.append(Piece("prism", (x + math.cos(0.0) * 0.0, y, z + h * 0.62, r * 2.6, r * 2.6, 0.6, 24), ICE_GLOW, "emissive", {"hollow": True}))
    out.counts["landmarks"] = out.counts.get("landmarks", 0) + 1


def _town(out, sector, x, y, heading, height_fn, rng, keep_clear, r0, r1):
    plaza_z = height_fn(x, y)
    town = Town(f"t{sector:02d}", sector, x, y, heading, plaza_z)
    loc = lambda lx, ly: _local(x, y, heading, lx, ly)  # noqa: E731

    # Plaza paving and the stepped temple with its great crystal.
    out.pieces.append(Piece("disc", (x, y, 31.0, 0.10), PLAZA, "snow", {"rings": 6}))
    tz = _base(height_fn, x, y, 22.0, sink=0.8)
    tiers = ((23.0, 21.5, 6.0, SNOW_SHADE, "snow"), (16.5, 15.0, 5.0, CRYSTAL, "crystal"), (10.5, 9.5, 5.0, SNOW, "snow"))
    z = tz
    for r_a, r_b, h, rgb, mat in tiers:
        out.pieces.append(Piece("prism", (x, y, z, r_a, r_b, h, 8), rgb, mat, {"twist": math.pi / 8.0}))
        out.pieces.append(Piece("prism", (x, y, z + h - 0.35, r_b + 0.25, r_b + 0.25, 0.35, 8), ICE_GLOW, "emissive", {"twist": math.pi / 8.0, "hollow": True}))
        z += h
    for side in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):        # stairs on four sides
        for step in range(8):
            d = 23.0 + 4.2 - step * 0.6
            sx, sy = loc(math.cos(side) * d, math.sin(side) * d)
            out.pieces.append(Piece("obox", (sx, sy, tz, 0.6, 6.4, 0.75 * (step + 1), heading + side), SNOW if step % 2 else PACKED_ICE, "snow"))
    out.pieces.append(Piece("prism", (x, y, z, 3.8, 2.8, 13.0, 6), CRYSTAL_PALE, "crystal"))
    out.pieces.append(Piece("prism", (x, y, z + 13.0, 2.8, 0.0, 7.0, 6), CRYSTAL_PALE, "crystal"))
    out.pieces.append(Piece("prism", (x, y, z + 2.0, 1.1, 0.6, 15.0, 6), ICE_GLOW, "emissive"))
    for k in range(4):
        a = TAU * k / 4.0 + math.pi / 4.0
        px, py = x + math.cos(a) * 7.0, y + math.sin(a) * 7.0
        out.pieces.append(Piece("prism", (px, py, z + 6.0, 0.05, 1.1, 1.4, 4), ICE_GLOW, "emissive"))
        out.pieces.append(Piece("prism", (px, py, z + 7.4, 1.1, 0.05, 1.4, 4), ICE_GLOW, "emissive"))
    out.obstacles.append(CircleObstacle(x, y, 26.5, z + 20.0))

    # Lantern posts ring the plaza path.
    for k in range(10):
        a = TAU * k / 10.0 + 0.16
        px, py = loc(math.cos(a) * 33.0, math.sin(a) * 33.0)
        g = height_fn(px, py) - 0.2
        out.pieces.append(Piece("prism", (px, py, g, 0.22, 0.16, 3.4, 5), FROST_STONE, "plain"))
        out.pieces.append(Piece("obox", (px, py, g + 3.4, 0.46, 0.46, 0.62, heading + a), LANTERN, "emissive"))
        out.pieces.append(Piece("prism", (px, py, g + 4.1, 0.5, 0.0, 0.6, 4), FROST_STONE, "plain"))
        out.obstacles.append(CircleObstacle(px, py, 0.35, g + 4.6))

    # Crystal towers stand in pairs on each flank (placed after the halls).
    flank_sets = ((math.pi * 0.5 - 0.42, math.pi * 0.5 + 0.42), (-math.pi * 0.5 - 0.42, -math.pi * 0.5 + 0.42))
    flanks = [flank_sets[0]] + ([flank_sets[1]] if rng.random() < 0.75 else [])
    tower_angles = [a % TAU for pair in flanks for a in pair]

    # Snow-dome halls with doorways facing the plaza.  Gates sit at local 0 and pi.
    # 14 slots round the plaza (0.449 rad apart keeps 11 m domes 3 m apart);
    # the gate paths and the tower feet knock some out.
    slots = []
    for k in range(14):
        a = (0.2245 + k * TAU / 14.0) % TAU
        if min(_angle_delta(a, 0.0), _angle_delta(a, math.pi)) < 0.33:
            continue
        if any(_angle_delta(a, b) < 0.17 for b in tower_angles):
            continue
        slots.append(a)
    n_halls = min(len(slots), rng.randint(5, 7))
    hall_angles = sorted(rng.sample(slots, n_halls))
    for a in hall_angles:
        a = a + rng.uniform(-0.03, 0.03)
        dr = rng.uniform(9.0, 11.0)
        d = 58.0 + rng.uniform(-1.5, 1.5)
        hx, hy = loc(math.cos(a) * d, math.sin(a) * d)
        g = _base(height_fn, hx, hy, dr, sink=0.9)
        inward = heading + a + math.pi
        out.pieces.append(Piece("dome", (hx, hy, g, dr), SNOW, "snow", {"squash": 0.78}))
        out.pieces.append(Piece("prism", (hx, hy, g, dr + 0.35, dr + 0.25, 1.4, 18), CRYSTAL, "crystal"))
        out.pieces.append(Piece("prism", (hx, hy, g + dr * 0.78 - 0.2, 1.3, 1.1, 0.5, 8), DOOR_GLOW, "emissive"))
        tx, ty = hx + math.cos(inward) * (dr + 1.2), hy + math.sin(inward) * (dr + 1.2)
        out.pieces.append(Piece("obox", (tx, ty, g, 5.0, 4.0, 3.6, inward), SNOW_SHADE, "snow"))
        out.pieces.append(Piece("dome", (tx + math.cos(inward) * 2.5, ty + math.sin(inward) * 2.5, g + 3.0, 2.0), SNOW, "snow", {"squash": 0.6, "rings": 3, "sides": 10}))
        dx, dy = tx + math.cos(inward) * 2.52, ty + math.sin(inward) * 2.52
        out.pieces.append(Piece("obox", (dx, dy, g + 0.6, 0.12, 2.2, 2.6, inward), DOOR_GLOW, "emissive"))
        town.doors.append((dx + math.cos(inward) * 1.6, dy + math.sin(inward) * 1.6))
        out.obstacles.append(CircleObstacle(hx, hy, dr * 0.92, g + dr * 0.8))
        out.obstacles.append(OObstacle(tx, ty, 5.0, 4.0, inward, g + 3.6))
    town.hall_count = len(hall_angles)

    # The towers, joined by arched ice bridges.
    for pair in flanks:
        tops = []
        for a in pair:
            d = 76.0
            tx, ty = loc(math.cos(a) * d, math.sin(a) * d)
            h = rng.uniform(28.0, 42.0)
            g = _base(height_fn, tx, ty, 7.0, sink=0.8)
            out.pieces.append(Piece("prism", (tx, ty, g, 7.2, 6.4, 3.2, 8), SNOW_SHADE, "snow"))
            out.pieces.append(Piece("prism", (tx, ty, g + 3.2, 5.4, 3.5, h, 8), CRYSTAL, "crystal"))
            for bz in range(int(h // 6.0)):
                t = (bz * 6.0 + 4.0) / h
                if t > 0.95:
                    break
                rr = 5.4 + (3.5 - 5.4) * t + 0.08
                out.pieces.append(Piece("prism", (tx, ty, g + 3.2 + t * h, rr, rr, 0.45, 8), LANTERN, "emissive", {"hollow": True}))
            top = g + 3.2 + h
            out.pieces.append(Piece("prism", (tx, ty, top, 3.5, 0.0, 9.0, 8), CRYSTAL_PALE, "crystal"))
            for k in range(4):
                ka = TAU * k / 4.0
                out.pieces.append(Piece("prism", (tx + math.cos(ka) * 2.6, ty + math.sin(ka) * 2.6, top - 0.5, 0.9, 0.0, 4.5, 4), CRYSTAL_PALE, "crystal", {"lean": (math.cos(ka) * 1.6, math.sin(ka) * 1.6)}))
            out.pieces.append(Piece("prism", (tx, ty, top + 9.0, 0.05, 0.8, 0.9, 4), ICE_GLOW, "emissive"))
            out.pieces.append(Piece("prism", (tx, ty, top + 9.9, 0.8, 0.05, 0.9, 4), ICE_GLOW, "emissive"))
            out.obstacles.append(CircleObstacle(tx, ty, 6.6, top + 9.0))
            tops.append((tx, ty, g + 3.2 + h * 0.62))
            town.tower_count += 1
        (ax, ay, az), (bx, by, bz2) = tops
        path = []
        for i in range(13):
            t = i / 12.0
            path.append((ax + (bx - ax) * t, ay + (by - ay) * t, az + (bz2 - az) * t + math.sin(t * math.pi) * 6.0))
        out.pieces.append(Piece("sweep", (tuple(path), 3.2, 1.0), CRYSTAL_PALE, "crystal"))
        out.pieces.append(Piece("sweep", (tuple((p[0], p[1], p[2] + 1.1) for p in path), 0.25, 0.25), LANTERN, "emissive"))

    # Crystal perimeter wall with radial gates (local angle 0 = outward, pi = inward).
    segs = 30
    for k in range(segs):
        a0 = TAU * k / segs
        a1 = TAU * (k + 1) / segs
        mid = (a0 + a1) * 0.5
        if min(_angle_delta(mid, 0.0), _angle_delta(mid, math.pi)) < 0.17:
            continue
        p0 = loc(math.cos(a0) * TOWN_WALL_RADIUS, math.sin(a0) * TOWN_WALL_RADIUS)
        p1 = loc(math.cos(a1) * TOWN_WALL_RADIUS, math.sin(a1) * TOWN_WALL_RADIUS)
        wx, wy = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
        length = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) + 0.8
        wh = rng.uniform(4.2, 5.6)
        g = _base(height_fn, wx, wy, length * 0.5, sink=1.0)
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        out.pieces.append(Piece("obox", (wx, wy, g, length, 2.4, wh, ang), CRYSTAL_DEEP, "crystal"))
        out.pieces.append(Piece("obox", (wx, wy, g + wh, length, 2.8, 0.5, ang), SNOW, "snow"))
        for f in (-0.25, 0.25):
            sx, sy = wx + math.cos(ang) * length * f, wy + math.sin(ang) * length * f
            out.pieces.append(Piece("prism", (sx, sy, g + wh + 0.4, 0.9, 0.0, rng.uniform(2.0, 3.6), 4), CRYSTAL_PALE, "crystal"))
        out.obstacles.append(OObstacle(wx, wy, length, 2.4, ang, g + wh + 0.5))
    for gate in (0.0, math.pi):
        ends = []
        for side in (-1.0, 1.0):
            a = gate + side * 0.17
            px, py = loc(math.cos(a) * TOWN_WALL_RADIUS, math.sin(a) * TOWN_WALL_RADIUS)
            g = _base(height_fn, px, py, 2.4, sink=0.8)
            out.pieces.append(Piece("prism", (px, py, g, 2.6, 1.8, 11.0, 6), SNOW_SHADE, "snow"))
            out.pieces.append(Piece("prism", (px, py, g + 6.0, 2.3, 2.3, 0.6, 6), ICE_GLOW, "emissive", {"hollow": True}))
            out.pieces.append(Piece("prism", (px, py, g + 11.0, 1.8, 0.0, 4.5, 6), CRYSTAL_PALE, "crystal"))
            out.obstacles.append(CircleObstacle(px, py, 2.6, g + 15.0))
            ends.append((px, py, g + 10.0))
        (ax, ay, az), (bx, by, bz2) = ends
        path = [(ax + (bx - ax) * (i / 10.0), ay + (by - ay) * (i / 10.0), az + (bz2 - az) * (i / 10.0) + math.sin(i / 10.0 * math.pi) * 4.0) for i in range(11)]
        out.pieces.append(Piece("sweep", (tuple(path), 2.4, 1.6), CRYSTAL, "crystal"))

    # Frozen skating lake just outside one flank.
    for side in (1.0, -1.0):
        lx, ly = loc(0.0, side * (TOWN_WALL_RADIUS + LAKE_RADIUS + 18.0))
        if spot_is_clear(lx, ly, LAKE_RADIUS + 4.0, r0, r1, keep_clear, out.footprints):
            zs = [height_fn(lx + math.cos(a) * LAKE_RADIUS * f, ly + math.sin(a) * LAKE_RADIUS * f) for a in (0.0, 1.57, 3.14, 4.71) for f in (0.0, 0.6, 1.0)]
            lz = max(zs) + 0.12
            low = min(zs) - 0.4
            town.lake = Lake(lx, ly, LAKE_RADIUS, lz)
            out.pieces.append(Piece("disc", (lx, ly, LAKE_RADIUS + 0.4, 0.0), LAKE_ICE, "crystal", {"flat_z": lz, "rings": 8}))
            # A low snow bank round the shore hides where the flat ice meets the slope.
            out.pieces.append(Piece("prism", (lx, ly, low, LAKE_RADIUS + 3.2, LAKE_RADIUS + 0.2, lz + 0.35 - low, 36), SNOW, "snow", {"hollow": True}))
            out.footprints.append((lx, ly, LAKE_RADIUS + 4.0))
            break
    out.towns.append(town)
    out.counts["towns"] = out.counts.get("towns", 0) + 1
    out.counts["halls"] = out.counts.get("halls", 0) + town.hall_count
    out.counts["towers"] = out.counts.get("towers", 0) + town.tower_count
    return town


def ice_sector(sector: int, r0: float, r1: float, height_fn, sector_count: int = SECTOR_COUNT, keep_clear=None) -> IceSector:
    """Deterministic structures, obstacles, towns and herds for one Ice sector."""
    sector = int(sector) % int(sector_count)
    keep = list(default_keep_clear() if keep_clear is None else keep_clear)
    rng = random.Random(SEED * 1000 + sector * 7919)
    out = IceSector(sector)
    step = TAU / sector_count
    a0 = sector * step
    mid_r = (r0 + r1) * 0.5

    def candidate(radius, tries=14):
        for _ in range(tries):
            rr = rng.uniform(r0 + RING_EDGE_MARGIN + radius, r1 - RING_EDGE_MARGIN - radius)
            pad_a = min(step * 0.45, radius / rr)
            a = rng.uniform(a0 + pad_a, a0 + step - pad_a)
            x, y = math.cos(a) * rr, math.sin(a) * rr
            if spot_is_clear(x, y, radius, r0, r1, keep, out.footprints):
                return x, y
        return None

    if sector % TOWN_SECTOR_STRIDE == 1:
        town_r = TOWN_WALL_RADIUS + 4.0
        spot = None
        for _ in range(10):
            rr = mid_r + rng.uniform(-110.0, 110.0)
            a = a0 + step * 0.5 + rng.uniform(-0.012, 0.012)
            x, y = math.cos(a) * rr, math.sin(a) * rr
            if spot_is_clear(x, y, town_r, r0, r1, keep, out.footprints):
                spot = (x, y, a)
                break
        if spot is not None:
            out.footprints.append((spot[0], spot[1], town_r))
            _town(out, sector, spot[0], spot[1], spot[2], height_fn, rng, keep, r0, r1)

    for _ in range(2):
        spot = candidate(30.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 30.0))
            _spire_cluster(out, spot[0], spot[1], height_fn, rng)
    if sector % 2 == 0:
        spot = candidate(38.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 38.0))
            _ice_arch(out, spot[0], spot[1], height_fn, rng)
    if sector % 4 == 2:
        spot = candidate(22.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 22.0))
            _landmark(out, spot[0], spot[1], height_fn, rng)
    for _ in range(rng.randint(4, 6)):
        spot = candidate(RIDGE_MAX_LENGTH + 2.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], RIDGE_MAX_LENGTH + 2.0))
            _glacier_ridge(out, spot[0], spot[1], height_fn, rng)
    for _ in range(3):
        spot = candidate(4.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 4.0))
            _waystone(out, spot[0], spot[1], height_fn, rng)
    if sector % 4 == 3 or (sector % TOWN_SECTOR_STRIDE != 1 and sector % 4 == 0):
        spot = candidate(55.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 55.0))
            out.herds.append(Herd(f"h{sector:02d}", spot[0], spot[1], 42.0, rng.randint(3, 5), sector * 31 + 7))
    out.counts["herds"] = len(out.herds)
    out.counts["pieces"] = len(out.pieces)
    out.counts["obstacles"] = len(out.obstacles)
    return out


# --------------------------------------------------------------------------
# Peaceful life (deterministic poses; no state to drift or save)
# --------------------------------------------------------------------------
def town_villagers(town: Town, count: int = 9):
    return make_villagers(town.key, town.doors, count, ((29.5, 31.2), (35.0, 37.0)))


def villager_pose(town: Town, v: Villager, t: float):
    """(x, y, heading, walking) for a Frostkin villager at time t."""
    return _villager_pose(town.x, town.y, v, t, plaza_ring=30.0)


def skater_pose(lake: Lake, index: int, t: float):
    rng = random.Random(hash_key(f"{lake.x:.1f}:{index}"))
    a_r = lake.r * rng.uniform(0.45, 0.82)
    b_r = a_r * rng.uniform(0.55, 0.95)
    speed = rng.uniform(3.5, 6.0)
    spin = rng.uniform(0.0, TAU)
    sign = -1.0 if index % 2 else 1.0
    w = sign * speed / max(4.0, (a_r + b_r) * 0.5)
    ang = rng.uniform(0.0, TAU) + w * t
    lx, ly = math.cos(ang) * a_r, math.sin(ang) * b_r
    vx, vy = -math.sin(ang) * a_r * w, math.cos(ang) * b_r * w
    c, s = math.cos(spin), math.sin(spin)
    x, y = lake.x + lx * c - ly * s, lake.y + lx * s + ly * c
    heading = math.atan2(vx * s + vy * c, vx * c - vy * s)
    lean = -sign * 0.22
    return x, y, heading, lean


def mammoth_pose(herd: Herd, index: int, t: float):
    """Slow grazing wander inside the herd's circle: (x, y, heading, walking)."""
    rng = random.Random(herd.seed * 13 + index)
    fx, fy = rng.uniform(0.010, 0.020), rng.uniform(0.012, 0.024)
    px_, py_ = rng.uniform(0.0, TAU), rng.uniform(0.0, TAU)
    rad = herd.radius * rng.uniform(0.35, 0.85)
    graze = 0.5 + 0.5 * math.sin(t * 0.07 + index * 1.7)       # periods of standing still
    tt = t - 10.0 * math.sin(t * 0.07 + index * 1.7)
    x = herd.x + math.sin(tt * fx * TAU + px_) * rad
    y = herd.y + math.sin(tt * fy * TAU + py_) * rad
    dt = 0.5
    t2 = tt + dt
    x2 = herd.x + math.sin(t2 * fx * TAU + px_) * rad
    y2 = herd.y + math.sin(t2 * fy * TAU + py_) * rad
    return x, y, math.atan2(y2 - y, x2 - x), graze < 0.75
