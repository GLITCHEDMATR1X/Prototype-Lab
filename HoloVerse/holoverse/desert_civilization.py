"""Desert ring civilization (Pass 282.55): pure, deterministic layout and life.

No Panda3D here, so everything can be tested headless.  ``desert_visuals``
turns the pieces into meshes; ``world.py`` owns terrain, chunks and collision.

Per sector of the Desert ring (ring key 5, r 2350-3050):

* **Obsidian pyramids** - a field of three in every fourth sector (away from
  the corridor seams) and a lone pyramid in each sector between: smooth black volcanic-glass pyramids with a
  glowing gold capstone, amber glyph bands, a gold-framed entrance facing the
  hub, a sandstone plinth, a pair of obsidian obelisks and an avenue of
  lantern pylons leading in.
* **Oasis towns** - every third sector (16 towns): a palm-ringed oasis pool,
  flat-roofed adobe houses (some domed) with lit doorways and cloth awnings,
  a market of striped tents, a sandstone minaret with a gold dome, lanterns,
  and an adobe wall with two gate towers.
* **Wilds** - layered sandstone mesas, hoodoos with cap rocks, boulder
  fields, saguaro cacti and a natural sandstone arch in every other sector.
* **Life** - Dunefolk walking the plaza and visiting doorways, and camel
  caravans trekking the open sand.  Nobody fights.

Everything keeps clear of Ember's post, the Desert travel landing, the
Venus-furnace oases, the four travel corridors and the ring edges.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from holoverse.region_kit import (
    CircleObstacle, OObstacle, Piece, Villager, angle_delta, base_z, hash_key, local, make_villagers, ring_spot_is_clear,
)
from holoverse.region_kit import villager_pose as _villager_pose

TAU = math.tau
SEED = 28255
SECTOR_COUNT = 48

EMBER_CLEARANCE = 140.0       # Ember wanders 86 m round her post; the forge lineup opens 34 m ahead of the player
LANDING_CLEARANCE = 60.0
OASIS_CLEARANCE = 80.0        # the salvaged Venus-furnace mini oases
TOWN_SECTOR_OFFSET = 2        # towns in sectors 2, 5, 8 ...
FIELD_SECTOR_OFFSET = 2       # three-pyramid fields in sectors 2, 6, 10 ... (clear of the corridor seams)
TOWN_SECTOR_STRIDE = 3
TOWN_WALL_RADIUS = 86.0
POOL_RADIUS = 20.0
LIFE_ACTIVE_RADIUS = 700.0
PYRAMID_SLOPE = 1.27          # height / half-base (close to the classic 51.8 degrees)

# Palette ---------------------------------------------------------------------
SANDSTONE = (0.80, 0.58, 0.38)
SANDSTONE_DARK = (0.60, 0.40, 0.26)
SANDSTONE_PALE = (0.90, 0.74, 0.52)
ADOBE = (0.88, 0.74, 0.56)
ADOBE_SHADE = (0.74, 0.58, 0.42)
WHITEWASH = (0.92, 0.90, 0.85)
DOME_BLUE = (0.22, 0.42, 0.70)
OBSIDIAN = (0.07, 0.06, 0.09)
GOLD = (1.00, 0.74, 0.28)
GLYPH = (1.00, 0.56, 0.16)
DOORWAY = (0.04, 0.03, 0.03)
DOOR_GLOW = (0.85, 0.46, 0.18)
WATER = (0.06, 0.40, 0.46)
PALM_TRUNK = (0.46, 0.34, 0.22)
PALM_LEAF = (0.26, 0.50, 0.20)
PALM_LEAF_DARK = (0.18, 0.38, 0.16)
CACTUS = (0.28, 0.48, 0.28)
LANTERN = (0.95, 0.58, 0.22)
CLOTH = ((0.78, 0.18, 0.16), (0.16, 0.36, 0.70), (0.95, 0.72, 0.20), (0.18, 0.55, 0.45), (0.62, 0.22, 0.52))


# --------------------------------------------------------------------------
# Data records
# --------------------------------------------------------------------------
@dataclass
class Town:
    key: str
    sector: int
    x: float
    y: float
    heading: float           # local +x points outward (radial)
    z: float
    doors: list = field(default_factory=list)
    house_count: int = 0
    tent_count: int = 0
    palm_count: int = 0


@dataclass
class Caravan:
    key: str
    x: float
    y: float
    rx: float
    ry: float
    heading: float
    camels: int
    walkers: int
    seed: int


@dataclass
class DesertSector:
    sector: int
    pieces: list = field(default_factory=list)
    obstacles: list = field(default_factory=list)
    towns: list = field(default_factory=list)
    caravans: list = field(default_factory=list)
    pyramids: list = field(default_factory=list)     # (x, y, half, height)
    counts: dict = field(default_factory=dict)
    footprints: list = field(default_factory=list)
    mesh_cache: tuple | None = None
    mesh_progress: list | None = None               # partial build between pre-warm steps


def _count(out, key, n=1):
    out.counts[key] = out.counts.get(key, 0) + n


def default_keep_clear(ember_radius=2728.0, landing_radius=2672.0, anchor_deg=-90.0):
    a = math.radians(anchor_deg)
    return [
        (math.cos(a) * ember_radius, math.sin(a) * ember_radius, EMBER_CLEARANCE),
        (math.cos(a) * landing_radius, math.sin(a) * landing_radius, LANDING_CLEARANCE),
    ]


# --------------------------------------------------------------------------
# Obsidian pyramids
# --------------------------------------------------------------------------
def _pyramid(out, x, y, half, heading, height_fn, rng, *, hero=False, avenue=3):
    """One obsidian pyramid.  ``heading`` points local +x at the ring centre
    (the entrance side)."""
    h = half * PYRAMID_SLOPE
    z = base_z(height_fn, x, y, half * 0.9, sink=1.2)
    plinth = half + 6.0
    out.pieces.append(Piece("obox", (x, y, z - 0.6, plinth * 2.0, plinth * 2.0, 1.8, heading), SANDSTONE_PALE, "sandstone"))
    out.pieces.append(Piece("pyramid", (x, y, z + 1.2, half, h, heading), OBSIDIAN, "obsidian", {"top_frac": 0.93}))
    cap_z = z + 1.2 + h * 0.93
    cap_half = half * 0.07
    out.pieces.append(Piece("pyramid", (x, y, cap_z, cap_half + 0.05, h * 0.07 + 0.3, heading), GOLD, "emissive"))
    # Glowing glyph bands wrapped round the faces.
    for t in ((0.16, 0.38, 0.62) if hero else (0.22, 0.52)):
        hb = half * (1.0 - t) + 0.18
        full = hb * PYRAMID_SLOPE
        out.pieces.append(Piece("pyramid", (x, y, z + 1.2 + h * t - 0.18 * PYRAMID_SLOPE, hb, full, heading), GLYPH, "emissive",
                                {"top_frac": min(0.95, 0.55 / full)}))
    # Entrance on the +x face: dark doorway, gold pillars and lintel, a glyph above.
    ux, uy = math.cos(heading), math.sin(heading)
    door_d = half - 2.6
    dx, dy = x + ux * door_d, y + uy * door_d
    out.pieces.append(Piece("obox", (dx, dy, z + 1.2, 4.6, 5.0, 7.0, heading), DOORWAY, "plain"))
    for side in (-1.0, 1.0):
        px, py = local(dx, dy, heading, 1.4, side * 3.1)
        out.pieces.append(Piece("obox", (px, py, z + 1.2, 1.4, 1.2, 7.6, heading), GOLD, "plain"))
    lx, ly = local(dx, dy, heading, 1.4, 0.0)
    out.pieces.append(Piece("obox", (lx, ly, z + 8.6, 1.6, 7.6, 1.2, heading), GOLD, "plain"))
    out.pieces.append(Piece("obox", (lx, ly, z + 10.4, 0.3, 4.0, 0.5, heading), GLYPH, "emissive"))
    out.obstacles.append(OObstacle(x, y, half * 2.0, half * 2.0, heading, z + h))
    # Obelisks flank the approach; lantern pylons line the avenue.
    approach = half + 14.0
    for side in (-1.0, 1.0):
        ox, oy = local(x, y, heading, approach, side * 9.0)
        oz = height_fn(ox, oy) - 0.6
        oh = rng.uniform(16.0, 20.0) * (1.25 if hero else 1.0)
        out.pieces.append(Piece("obox", (ox, oy, oz - 0.3, 4.2, 4.2, 1.4, heading), SANDSTONE_PALE, "sandstone"))
        out.pieces.append(Piece("prism", (ox, oy, oz + 1.1, 1.55, 1.05, oh, 4), OBSIDIAN, "obsidian", {"twist": heading % (math.pi / 2.0)}))
        out.pieces.append(Piece("prism", (ox, oy, oz + 1.1 + oh, 1.05, 0.0, 2.2, 4), GOLD, "emissive"))
        out.obstacles.append(CircleObstacle(ox, oy, 2.4, oz + oh + 3.0))
        for k in range(avenue):
            ax, ay = local(x, y, heading, approach + 12.0 + k * 11.0, side * 7.0)
            az = height_fn(ax, ay) - 0.3
            out.pieces.append(Piece("prism", (ax, ay, az, 0.75, 0.55, 3.2, 6), SANDSTONE, "sandstone"))
            out.pieces.append(Piece("prism", (ax, ay, az + 3.2, 0.9, 0.9, 0.35, 6), SANDSTONE_DARK, "sandstone"))
            out.pieces.append(Piece("prism", (ax, ay, az + 3.55, 0.35, 0.0, 0.8, 5), LANTERN, "emissive"))
            out.obstacles.append(CircleObstacle(ax, ay, 0.8, az + 4.4))
    out.pyramids.append((x, y, half, h))
    _count(out, "pyramids")
    _count(out, "obelisks", 2)


def _pyramid_field(out, cx, cy, height_fn, rng):
    """Three pyramids stepping outward along the radius (largest nearest the hub)."""
    radial = math.atan2(cy, cx)
    facing = radial + math.pi          # entrances face the hub
    # Staggered so every entrance avenue runs past, not into, the pyramid in front.
    sizes = (rng.uniform(40.0, 44.0), rng.uniform(29.0, 32.0), rng.uniform(19.0, 22.0))
    offsets = ((-55.0, -55.0), (35.0, 8.0), (105.0, 56.0))   # local: x radial (outward), y tangential
    for i, ((ox, oy), half) in enumerate(zip(offsets, sizes)):
        px, py = local(cx, cy, radial, ox, oy)
        _pyramid(out, px, py, half, facing, height_fn, rng, hero=(i == 0), avenue=2)
    _count(out, "fields")


FIELD_RADIUS = 165.0     # bounding circle of a three-pyramid field (incl. plinths, obelisks, avenues)
LONE_RADIUS = 92.0


# --------------------------------------------------------------------------
# Oasis towns
# --------------------------------------------------------------------------
def _palm(out, x, y, z, rng, *, height=None):
    h = height or rng.uniform(8.0, 13.0)
    lean_dir = rng.uniform(0.0, TAU)
    lean = rng.uniform(0.8, 2.6)
    lx, ly = math.cos(lean_dir), math.sin(lean_dir)
    trunk = []
    for i in range(8):
        t = i / 7.0
        bend = lean * t * t
        trunk.append((x + lx * bend, y + ly * bend, z + h * t))
    out.pieces.append(Piece("sweep", (tuple(trunk), 0.62, 0.62), PALM_TRUNK, "plain"))
    tx, ty, tz = trunk[-1]
    for k in range(7):
        a = TAU * k / 7.0 + rng.uniform(-0.2, 0.2)
        ca, sa = math.cos(a), math.sin(a)
        reach = rng.uniform(3.6, 5.2)
        frond = []
        for i in range(6):
            t = i / 5.0
            frond.append((tx + ca * reach * t, ty + sa * reach * t, tz + 0.5 + 1.0 * t - 2.6 * t * t))
        out.pieces.append(Piece("sweep", (tuple(frond), 1.25, 0.14), PALM_LEAF if k % 2 else PALM_LEAF_DARK, "plain"))
    out.obstacles.append(CircleObstacle(x, y, 0.5, z + h))
    _count(out, "palms")


def _house(out, x, y, face, height_fn, rng, town):
    w, d = rng.uniform(7.0, 10.5), rng.uniform(7.0, 10.0)
    h = rng.uniform(4.0, 6.8)
    z = base_z(height_fn, x, y, max(w, d) * 0.55, sink=0.4)
    tone = ADOBE if rng.random() < 0.65 else WHITEWASH
    out.pieces.append(Piece("obox", (x, y, z, d, w, h, face), tone, "plain"))
    out.pieces.append(Piece("obox", (x, y, z + h, d + 0.5, w + 0.5, 0.55, face), ADOBE_SHADE, "plain"))
    roll = rng.random()
    if roll < 0.35:
        out.pieces.append(Piece("dome", (x, y, z + h + 0.55, min(w, d) * 0.36), rng.choice((WHITEWASH, DOME_BLUE)), "plain", {"rings": 5, "sides": 14}))
    elif roll < 0.65:
        # A smaller upper storey set back on the roof, with a lit window.
        bx, by = local(x, y, face, -d * 0.18, w * 0.15)
        uh = rng.uniform(2.6, 3.4)
        out.pieces.append(Piece("obox", (bx, by, z + h + 0.55, d * 0.55, w * 0.5, uh, face), tone, "plain"))
        out.pieces.append(Piece("obox", (bx, by, z + h + 0.55 + uh, d * 0.55 + 0.4, w * 0.5 + 0.4, 0.4, face), ADOBE_SHADE, "plain"))
        wx, wy = local(bx, by, face, d * 0.275 + 0.05, 0.0)
        out.pieces.append(Piece("obox", (wx, wy, z + h + 1.6, 0.12, 0.9, 1.0, face), DOOR_GLOW, "emissive"))
    ux, uy = math.cos(face), math.sin(face)
    fx, fy = x + ux * (d * 0.5 + 0.05), y + uy * (d * 0.5 + 0.05)
    out.pieces.append(Piece("obox", (fx, fy, z, 0.25, 1.7, 2.6, face), DOORWAY, "plain"))
    out.pieces.append(Piece("obox", (fx + ux * 0.05, fy + uy * 0.05, z + 0.1, 0.12, 1.3, 2.2, face), DOOR_GLOW, "emissive"))
    for side in (-1.0, 1.0):
        wx, wy = local(fx, fy, face, 0.06, side * w * 0.3)
        out.pieces.append(Piece("obox", (wx, wy, z + h * 0.55, 0.12, 0.9, 0.9, face), DOOR_GLOW, "emissive"))
    # Cloth awning over the door.
    a0 = local(fx, fy, face, 0.0, 0.0)
    a1 = local(fx, fy, face, 2.2, 0.0)
    cloth = CLOTH[rng.randrange(len(CLOTH))]
    out.pieces.append(Piece("sweep", (((a0[0], a0[1], z + 3.2), (a1[0], a1[1], z + 2.5)), 3.0, 0.08), cloth, "plain"))
    town.doors.append((fx + ux * 1.4, fy + uy * 1.4))
    out.obstacles.append(OObstacle(x, y, d, w, face, z + h + 0.6))
    town.house_count += 1


def _tent(out, x, y, height_fn, rng, heading):
    z = height_fn(x, y) - 0.1
    cloth = CLOTH[rng.randrange(len(CLOTH))]
    for cx_, cy_ in ((-1.8, -1.8), (1.8, -1.8), (1.8, 1.8), (-1.8, 1.8)):
        px, py = local(x, y, heading, cx_, cy_)
        out.pieces.append(Piece("obox", (px, py, z, 0.16, 0.16, 2.3, heading), PALM_TRUNK, "plain"))
    out.pieces.append(Piece("prism", (x, y, z + 2.3, 3.4, 0.0, 1.7, 4), cloth, "plain", {"twist": 0.0}))
    out.pieces.append(Piece("obox", (x, y, z, 2.6, 1.2, 0.8, heading), SANDSTONE_DARK, "plain"))
    for k in range(3):
        gx, gy = local(x, y, heading, -0.8 + k * 0.8, 0.0)
        out.pieces.append(Piece("ellipsoid", (gx, gy, z + 1.0, 0.32, 0.32, 0.3), CLOTH[(k + 2) % len(CLOTH)], "plain", {"rings": 4, "sides": 8}))
    out.obstacles.append(CircleObstacle(x, y, 2.4, z + 4.0))


def pool_bed(height_fn, x, y):
    """Ground samples over the oasis pool (centre, half radius, rim)."""
    zs = [height_fn(x, y)]
    for k in range(8):
        a = TAU * k / 8.0
        for f in (0.5, 1.0):
            zs.append(height_fn(x + math.cos(a) * POOL_RADIUS * f, y + math.sin(a) * POOL_RADIUS * f))
    return zs


def _town(out, sector, x, y, heading, height_fn, rng, keep_clear, r0, r1):
    plaza_z = height_fn(x, y)
    town = Town(f"d{sector:02d}", sector, x, y, heading, plaza_z)
    loc = lambda lx, ly: local(x, y, heading, lx, ly)  # noqa: E731

    # Oasis pool with a stone rim, ringed by palms; paving and lanterns round it.
    zs = pool_bed(height_fn, x, y)
    water_z = max(zs) - 0.10
    out.pieces.append(Piece("disc", (x, y, 33.0, 0.10), SANDSTONE_PALE, "sandstone", {"rings": 6}))
    out.pieces.append(Piece("disc", (x, y, POOL_RADIUS, 0.0), WATER, "crystal", {"flat_z": water_z, "rings": 6}))
    out.pieces.append(Piece("prism", (x, y, min(zs) - 0.6, POOL_RADIUS + 1.4, POOL_RADIUS + 0.6, water_z + 0.55 - (min(zs) - 0.6), 28), SANDSTONE, "sandstone", {"hollow": True}))
    for k in range(10):
        a = TAU * k / 10.0 + rng.uniform(-0.12, 0.12)
        d = POOL_RADIUS + rng.uniform(3.0, 7.5)
        px, py = x + math.cos(a) * d, y + math.sin(a) * d
        _palm(out, px, py, height_fn(px, py) - 0.3, rng)
    town.palm_count = 10
    for k in range(8):
        a = TAU * k / 8.0 + 0.2
        px, py = loc(math.cos(a) * 33.5, math.sin(a) * 33.5)
        g = height_fn(px, py) - 0.2
        out.pieces.append(Piece("prism", (px, py, g, 0.2, 0.15, 3.3, 6), SANDSTONE_DARK, "plain"))
        out.pieces.append(Piece("ellipsoid", (px, py, g + 3.55, 0.32, 0.32, 0.42), LANTERN, "emissive", {"rings": 4, "sides": 8}))
        out.obstacles.append(CircleObstacle(px, py, 0.35, g + 4.0))

    # Minaret at local +y, market on the -y flank.
    mx, my = loc(0.0, 40.0)
    mz = base_z(height_fn, mx, my, 5.0, sink=0.5)
    out.pieces.append(Piece("prism", (mx, my, mz, 6.0, 5.4, 3.0, 8), SANDSTONE_DARK, "sandstone"))
    out.pieces.append(Piece("prism", (mx, my, mz + 3.0, 3.6, 3.0, 22.0, 8), SANDSTONE, "sandstone"))
    out.pieces.append(Piece("prism", (mx, my, mz + 20.0, 4.4, 4.4, 0.9, 8), SANDSTONE_PALE, "sandstone"))
    out.pieces.append(Piece("prism", (mx, my, mz + 20.9, 3.2, 3.2, 0.5, 8), LANTERN, "emissive", {"hollow": True}))
    out.pieces.append(Piece("prism", (mx, my, mz + 25.0, 2.6, 2.4, 3.0, 8), SANDSTONE_PALE, "sandstone"))
    out.pieces.append(Piece("dome", (mx, my, mz + 28.0, 2.5), GOLD, "plain", {"squash": 1.25, "rings": 6, "sides": 14}))
    out.pieces.append(Piece("prism", (mx, my, mz + 31.1, 0.25, 0.0, 2.6, 6), GOLD, "emissive"))
    out.obstacles.append(CircleObstacle(mx, my, 6.0, mz + 31.0))
    for k in range(5):
        a = -math.pi * 0.5 + (k - 2) * 0.24
        tx, ty = loc(math.cos(a) * 31.0, math.sin(a) * 31.0)
        _tent(out, tx, ty, height_fn, rng, heading + a)
    town.tent_count = 5

    # Houses round the plaza, doors facing in.  Gates at local 0 and pi.
    slots = []
    for ring_d, n in ((50.0, 12), (68.0, 16)):
        for k in range(n):
            a = (k + 0.5) * TAU / n + (0.13 if ring_d > 60 else 0.0)
            if min(angle_delta(a, 0.0), angle_delta(a, math.pi)) < (0.30 if ring_d < 60 else 0.24):
                continue
            if ring_d < 60 and angle_delta(a, math.pi * 0.5) < 0.30:
                continue       # the minaret
            if ring_d < 60 and angle_delta(a, -math.pi * 0.5) < 0.45:
                continue       # the market
            slots.append((ring_d, a))
    for ring_d, a in rng.sample(slots, min(len(slots), rng.randint(14, 18))):
        hx, hy = loc(math.cos(a) * ring_d, math.sin(a) * ring_d)
        _house(out, hx, hy, heading + a + math.pi, height_fn, rng, town)

    # Adobe wall with crenellations and two gate towers on each radial gate.
    segs = 28
    for k in range(segs):
        a0, a1 = TAU * k / segs, TAU * (k + 1) / segs
        mid = (a0 + a1) * 0.5
        if min(angle_delta(mid, 0.0), angle_delta(mid, math.pi)) < 0.16:
            continue
        p0 = loc(math.cos(a0) * TOWN_WALL_RADIUS, math.sin(a0) * TOWN_WALL_RADIUS)
        p1 = loc(math.cos(a1) * TOWN_WALL_RADIUS, math.sin(a1) * TOWN_WALL_RADIUS)
        wx, wy = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
        length = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) + 0.6
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        g = base_z(height_fn, wx, wy, length * 0.5, sink=0.8)
        out.pieces.append(Piece("obox", (wx, wy, g, length, 1.8, 3.8, ang), ADOBE_SHADE, "plain"))
        for f in (-0.33, 0.0, 0.33):
            cx_, cy_ = wx + math.cos(ang) * length * f, wy + math.sin(ang) * length * f
            out.pieces.append(Piece("obox", (cx_, cy_, g + 3.8, 1.6, 1.8, 0.8, ang), ADOBE_SHADE, "plain"))
        out.obstacles.append(OObstacle(wx, wy, length, 1.8, ang, g + 4.6))
    for gate in (0.0, math.pi):
        tops = []
        for side in (-1.0, 1.0):
            a = gate + side * 0.15
            px, py = loc(math.cos(a) * TOWN_WALL_RADIUS, math.sin(a) * TOWN_WALL_RADIUS)
            g = base_z(height_fn, px, py, 3.0, sink=0.6)
            out.pieces.append(Piece("prism", (px, py, g, 3.4, 3.0, 8.5, 4), ADOBE, "plain", {"twist": 0.0}))
            for c in range(4):
                ca = TAU * c / 4.0 + math.pi / 4.0
                out.pieces.append(Piece("obox", (px + math.cos(ca) * 2.2, py + math.sin(ca) * 2.2, g + 8.5, 1.0, 1.0, 0.9, ca), ADOBE_SHADE, "plain"))
            out.pieces.append(Piece("prism", (px, py, g + 6.2, 3.15, 3.15, 0.45, 4), LANTERN, "emissive", {"hollow": True}))
            out.obstacles.append(CircleObstacle(px, py, 3.3, g + 9.5))
            tops.append((px, py, g + 6.5))
        (ax, ay, az), (bx, by, bz) = tops
        path = [(ax + (bx - ax) * (i / 10.0), ay + (by - ay) * (i / 10.0), az + (bz - az) * (i / 10.0) + math.sin(i / 10.0 * math.pi) * 3.0) for i in range(11)]
        out.pieces.append(Piece("sweep", (tuple(path), 2.2, 1.4), ADOBE, "plain"))
    out.towns.append(town)
    _count(out, "towns")
    _count(out, "houses", town.house_count)
    _count(out, "tents", town.tent_count)
    return town


TOWN_RADIUS = TOWN_WALL_RADIUS + 6.0


# --------------------------------------------------------------------------
# Wilds
# --------------------------------------------------------------------------
def _mesa(out, x, y, height_fn, rng):
    r = rng.uniform(18.0, 30.0)
    h = rng.uniform(18.0, 34.0)
    sides = rng.randint(9, 11)
    z = base_z(height_fn, x, y, r, sink=2.0)
    tiers = ((1.00, 0.88, 0.40), (0.88, 0.82, 0.35), (0.80, 0.74, 0.25))
    zz = z
    for i, (ra, rb, frac) in enumerate(tiers):
        th = h * frac
        out.pieces.append(Piece("prism", (x, y, zz, r * ra, r * rb, th + 0.3, sides), SANDSTONE if i % 2 == 0 else SANDSTONE_DARK, "sandstone", {"twist": 0.05 * i}))
        zz += th
    for k in range(rng.randint(4, 7)):
        a = rng.uniform(0.0, TAU)
        d = r * rng.uniform(1.0, 1.25)
        bx, by = x + math.cos(a) * d, y + math.sin(a) * d
        s = rng.uniform(2.0, 4.5)
        out.pieces.append(Piece("ellipsoid", (bx, by, height_fn(bx, by) - s * 0.3, s * 1.3, s, s * 0.8), SANDSTONE_DARK, "sandstone", {"heading": a, "rings": 5, "sides": 10}))
    out.obstacles.append(CircleObstacle(x, y, r * 0.95, z + h))
    _count(out, "mesas")


def _hoodoos(out, cx, cy, height_fn, rng):
    for _ in range(rng.randint(3, 5)):
        a = rng.uniform(0.0, TAU)
        d = rng.uniform(0.0, 12.0)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        r = rng.uniform(1.4, 2.6)
        h = rng.uniform(6.0, 14.0)
        z = height_fn(x, y) - 0.8
        out.pieces.append(Piece("prism", (x, y, z, r, r * 0.55, h, 7), SANDSTONE, "sandstone", {"lean": (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6))}))
        out.pieces.append(Piece("ellipsoid", (x, y, z + h + 0.4, r * 1.25, r * 1.1, r * 0.55), SANDSTONE_DARK, "sandstone", {"heading": a, "rings": 5, "sides": 10}))
        out.obstacles.append(CircleObstacle(x, y, r * 0.9, z + h + 1.0))
        _count(out, "hoodoos")


def _boulders(out, cx, cy, height_fn, rng):
    for _ in range(rng.randint(5, 9)):
        a = rng.uniform(0.0, TAU)
        d = rng.uniform(0.0, 14.0)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        s = rng.uniform(1.2, 3.6)
        out.pieces.append(Piece("ellipsoid", (x, y, height_fn(x, y) - s * 0.25, s * rng.uniform(1.0, 1.5), s, s * 0.8), rng.choice((SANDSTONE, SANDSTONE_DARK)), "sandstone",
                                {"heading": rng.uniform(0.0, TAU), "rings": 5, "sides": 10}))
        if s > 2.0:
            out.obstacles.append(CircleObstacle(x, y, s, height_fn(x, y) + s))
    _count(out, "boulder_fields")


def _cactus(out, x, y, height_fn, rng):
    h = rng.uniform(3.5, 7.0)
    z = height_fn(x, y) - 0.2
    out.pieces.append(Piece("prism", (x, y, z, 0.42, 0.36, h, 8), CACTUS, "plain"))
    out.pieces.append(Piece("dome", (x, y, z + h, 0.36), CACTUS, "plain", {"rings": 3, "sides": 8}))
    for _ in range(rng.randint(1, 3)):
        a = rng.uniform(0.0, TAU)
        ux, uy = math.cos(a), math.sin(a)
        ah = rng.uniform(h * 0.35, h * 0.6)
        reach = rng.uniform(0.9, 1.4)
        up = rng.uniform(1.2, 2.2)
        path = ((x, y, z + ah), (x + ux * reach, y + uy * reach, z + ah + 0.1), (x + ux * reach, y + uy * reach, z + ah + up))
        out.pieces.append(Piece("sweep", (path, 0.5, 0.5), CACTUS, "plain"))
    out.obstacles.append(CircleObstacle(x, y, 0.5, z + h))
    _count(out, "cacti")


def _sand_arch(out, cx, cy, height_fn, rng):
    span = rng.uniform(40.0, 62.0)
    rise = rng.uniform(18.0, 28.0)
    heading = rng.uniform(0.0, TAU)
    ux, uy = math.cos(heading), math.sin(heading)
    ax, ay = cx - ux * span * 0.5, cy - uy * span * 0.5
    bx, by = cx + ux * span * 0.5, cy + uy * span * 0.5
    za, zb = height_fn(ax, ay) - 2.0, height_fn(bx, by) - 2.0
    path = []
    for i in range(17):
        t = i / 16.0
        path.append((ax + (bx - ax) * t, ay + (by - ay) * t, za + (zb - za) * t + math.sin(t * math.pi) * rise))
    thick = rng.uniform(6.5, 9.0)
    out.pieces.append(Piece("sweep", (tuple(path), thick + 3.0, thick), SANDSTONE, "sandstone"))
    for x, y, z in ((ax, ay, za), (bx, by, zb)):
        out.pieces.append(Piece("ellipsoid", (x, y, z, thick * 1.1, thick * 1.0, rise * 0.30), SANDSTONE_DARK, "sandstone", {"rings": 5, "sides": 10}))
        out.obstacles.append(CircleObstacle(x, y, thick * 0.8, z + rise * 0.45))
    _count(out, "arches")


# --------------------------------------------------------------------------
# Sector layout
# --------------------------------------------------------------------------
def desert_sector(sector: int, r0: float, r1: float, height_fn, sector_count: int = SECTOR_COUNT, keep_clear=None) -> DesertSector:
    """Deterministic structures, obstacles, towns and caravans for one Desert sector."""
    sector = int(sector) % int(sector_count)
    keep = list(default_keep_clear() if keep_clear is None else keep_clear)
    rng = random.Random(SEED * 1000 + sector * 7919)
    out = DesertSector(sector)
    step = TAU / sector_count
    a0 = sector * step
    mid_r = (r0 + r1) * 0.5

    def candidate(radius, tries=14):
        for _ in range(tries):
            lo, hi = r0 + 45.0 + radius, r1 - 45.0 - radius
            if hi <= lo:
                return None
            rr = rng.uniform(lo, hi)
            pad_a = min(step * 0.45, radius / rr)
            a = rng.uniform(a0 + pad_a, a0 + step - pad_a)
            x, y = math.cos(a) * rr, math.sin(a) * rr
            if ring_spot_is_clear(x, y, radius, r0, r1, keep, out.footprints):
                return x, y
        return None

    def centred(radius, offsets):
        for off in offsets:
            rr = mid_r + off
            a = a0 + step * 0.5
            x, y = math.cos(a) * rr, math.sin(a) * rr
            if ring_spot_is_clear(x, y, radius, r0, r1, keep, out.footprints):
                return x, y, a
        return None

    if sector % TOWN_SECTOR_STRIDE == TOWN_SECTOR_OFFSET:
        # An oasis sits in a hollow: of the clear sites, take the flattest pool bed.
        best = None
        for off in range(-200, 201, 40):
            for da in (-0.010, 0.0, 0.010):
                rr = mid_r + off
                a = a0 + step * 0.5 + da
                x, y = math.cos(a) * rr, math.sin(a) * rr
                if not ring_spot_is_clear(x, y, TOWN_RADIUS, r0, r1, keep, out.footprints):
                    continue
                zs = pool_bed(height_fn, x, y)
                score = max(zs) - min(zs)
                if best is None or score < best[0] - 1e-9:
                    best = (score, (x, y, a))
        spot = best[1] if best is not None else None
        if spot is not None:
            out.footprints.append((spot[0], spot[1], TOWN_RADIUS))
            _town(out, sector, spot[0], spot[1], spot[2], height_fn, rng, keep, r0, r1)
    if sector % 4 == FIELD_SECTOR_OFFSET:
        spot = centred(FIELD_RADIUS, (130.0, -130.0, 60.0, -60.0, 0.0, 170.0, -170.0))
        if spot is not None:
            out.footprints.append((spot[0], spot[1], FIELD_RADIUS))
            _pyramid_field(out, spot[0], spot[1], height_fn, rng)
    else:
        spot = candidate(LONE_RADIUS, tries=24)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], LONE_RADIUS))
            facing = math.atan2(spot[1], spot[0]) + math.pi
            _pyramid(out, spot[0], spot[1], rng.uniform(22.0, 32.0), facing, height_fn, rng)
    if sector % 2 == 1:
        rx, ry = rng.uniform(80.0, 120.0), rng.uniform(34.0, 52.0)
        spot = candidate(rx + 8.0, tries=24)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], rx + 8.0))
            out.caravans.append(Caravan(f"c{sector:02d}", spot[0], spot[1], rx, ry, rng.uniform(0.0, TAU), rng.randint(3, 5), rng.randint(1, 2), sector * 37 + 11))
    for _ in range(rng.randint(1, 2)):
        spot = candidate(38.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 38.0))
            _mesa(out, spot[0], spot[1], height_fn, rng)
    for _ in range(2):
        spot = candidate(16.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 16.0))
            _hoodoos(out, spot[0], spot[1], height_fn, rng)
    spot = candidate(18.0)
    if spot is not None:
        out.footprints.append((spot[0], spot[1], 18.0))
        _boulders(out, spot[0], spot[1], height_fn, rng)
    if sector % 2 == 1:
        spot = candidate(36.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 36.0))
            _sand_arch(out, spot[0], spot[1], height_fn, rng)
    for _ in range(rng.randint(6, 10)):
        spot = candidate(2.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 2.0))
            _cactus(out, spot[0], spot[1], height_fn, rng)
    out.counts["caravans"] = len(out.caravans)
    out.counts["pieces"] = len(out.pieces)
    out.counts["obstacles"] = len(out.obstacles)
    return out


# --------------------------------------------------------------------------
# Peaceful life
# --------------------------------------------------------------------------
def town_villagers(town: Town, count: int = 10):
    return make_villagers(town.key, town.doors, count, ((26.0, 29.0), (36.0, 39.0)))


def villager_pose(town: Town, v: Villager, t: float):
    """(x, y, heading, walking) for a Dunefolk villager at time t."""
    return _villager_pose(town.x, town.y, v, t, plaza_ring=28.0)


CARAVAN_SPEED = 1.6          # m/s, a camel's walk
CARAVAN_SPACING = 7.5        # metres between animals


def caravan_pose(caravan: Caravan, index: int, t: float):
    """(x, y, heading) of member ``index`` (camels first, then walkers) on the
    caravan's loop.  Members follow the leader at a fixed spacing."""
    rng = random.Random(hash_key(caravan.key))
    phase0 = rng.uniform(0.0, TAU)
    perim = math.pi * (3.0 * (caravan.rx + caravan.ry) - math.sqrt((3.0 * caravan.rx + caravan.ry) * (caravan.rx + 3.0 * caravan.ry)))
    w = TAU * CARAVAN_SPEED / perim
    lag = TAU * CARAVAN_SPACING / perim
    ang = phase0 + w * t - index * lag
    lx, ly = math.cos(ang) * caravan.rx, math.sin(ang) * caravan.ry
    tx, ty = -math.sin(ang) * caravan.rx, math.cos(ang) * caravan.ry
    c, s = math.cos(caravan.heading), math.sin(caravan.heading)
    x, y = caravan.x + lx * c - ly * s, caravan.y + lx * s + ly * c
    heading = math.atan2(tx * s + ty * c, tx * c - ty * s)
    return x, y, heading
