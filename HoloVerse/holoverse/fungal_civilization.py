"""Mushroom ring civilization (Pass 282.56): an alien fungal world, peaceful.

No Panda3D here, so everything can be tested headless.  ``fungal_visuals``
turns the pieces into meshes; ``world.py`` owns terrain, chunks and collision.

The ring (key 4, r 1650-2350) is an alien fungal world, not a pink one: teal
moss, violet uplands, and caps in teal, amber, violet, chartreuse, deep blue
and only now and then magenta, with bioluminescent gills and spores.

* **Sporekin hollows** - every third sector (16 towns): a huge hearth
  mushroom with round lit windows, cap houses with glowing doors, a ring of
  little glowing mushrooms round a mycelium pool, lantern stalks, and a soft
  boundary of glow stalks with two arched mycelium gates.
* **Wilds** - every sector: groves of giant mushrooms (dome, parasol, cone and
  pagoda caps, 25-60 m), coral fungi, glow-stalk fields, puffball clusters and
  a spore vent; a 90-120 m titan cap with bracket fungi in every fourth.
* **The REDACTED port** - Nyx (the giant) and Orbit's clearing: a ring of etched
  standing stones round the beam that leads into The Indigo Giant archive.
* **Life** - Sporekin walking their hollows and visiting doors, and spore
  jellies drifting over groves and towns.  Nobody fights.

Everything keeps clear of Nyx and Orbit's port, the travel
landing, the four travel corridors, the ring edges and its own sector.
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
SEED = 28256
SECTOR_COUNT = 48

SOLACE_CLEARANCE = 150.0      # kept for any drone guide posted here (Solace moved to Green Hills in 282.57)
LANDING_CLEARANCE = 60.0
PORT_CLEARANCE = 120.0        # Nyx, Orbit and the beam
PORT_ANGLE_DEG = -82.0        # the port sits ~320 m from the Mushroom travel landing
PORT_RADIUS_M = 2080.0
TOWN_SECTOR_STRIDE = 3        # towns in sectors 0, 3, 6 ...
TOWN_SECTOR_OFFSET = 0
TOWN_RADIUS = 88.0
LIFE_ACTIVE_RADIUS = 700.0

# Palette ---------------------------------------------------------------------
CAP_TONES = (
    (0.10, 0.60, 0.60),   # teal
    (0.92, 0.52, 0.16),   # amber
    (0.46, 0.26, 0.72),   # violet
    (0.62, 0.80, 0.18),   # chartreuse
    (0.18, 0.30, 0.66),   # deep blue
    (0.12, 0.48, 0.38),   # sea green
    (0.80, 0.24, 0.52),   # magenta (sparing)
)
CAP_WEIGHTS = (0.22, 0.18, 0.18, 0.12, 0.13, 0.10, 0.07)
STEM_TONES = ((0.86, 0.82, 0.72), (0.74, 0.70, 0.80), (0.60, 0.66, 0.62), (0.34, 0.28, 0.36))
GILL_GLOW = ((0.30, 0.95, 0.90), (1.00, 0.68, 0.24), (0.66, 0.46, 1.00), (0.70, 1.00, 0.36))
SPOT = (0.94, 0.92, 0.84)
MOSS = (0.16, 0.36, 0.32)
STONE = (0.18, 0.18, 0.24)
GLYPH = (0.35, 0.95, 1.00)
POOL = (0.08, 0.36, 0.40)
DOOR_GLOW = (1.00, 0.70, 0.30)
WINDOW_GLOW = (0.95, 0.80, 0.45)


@dataclass
class Town:
    key: str
    sector: int
    x: float
    y: float
    heading: float
    z: float
    doors: list = field(default_factory=list)
    house_count: int = 0


@dataclass
class Drift:
    """A cloud of spore jellies drifting over a grove or town."""
    key: str
    x: float
    y: float
    z: float
    radius: float
    count: int
    seed: int


@dataclass
class FungalSector:
    sector: int
    pieces: list = field(default_factory=list)
    obstacles: list = field(default_factory=list)
    towns: list = field(default_factory=list)
    drifts: list = field(default_factory=list)
    vents: list = field(default_factory=list)          # (x, y, z) spore vent mouths
    port: tuple | None = None                          # (x, y, z) of the beam, in the port's sector
    counts: dict = field(default_factory=dict)
    footprints: list = field(default_factory=list)
    mesh_cache: tuple | None = None
    mesh_progress: list | None = None


def _count(out, key, n=1):
    out.counts[key] = out.counts.get(key, 0) + n


def port_position():
    a = math.radians(PORT_ANGLE_DEG)
    return math.cos(a) * PORT_RADIUS_M, math.sin(a) * PORT_RADIUS_M


def port_sector(sector_count: int = SECTOR_COUNT) -> int:
    x, y = port_position()
    return int((math.atan2(y, x) % TAU) / (TAU / sector_count)) % sector_count


def default_keep_clear(landing_radius=1918.0, anchor_deg=-90.0):
    """The landing and the port (world.py adds any drone guide's post)."""
    a = math.radians(anchor_deg)
    px, py = port_position()
    return [
        (math.cos(a) * landing_radius, math.sin(a) * landing_radius, LANDING_CLEARANCE),
        (px, py, PORT_CLEARANCE),
    ]


def _cap_tone(rng):
    return rng.choices(CAP_TONES, weights=CAP_WEIGHTS, k=1)[0]


# --------------------------------------------------------------------------
# Mushrooms and fungi
# --------------------------------------------------------------------------
def _mushroom(out, x, y, height_fn, rng, h, cap_r, *, style=None, tone=None, stem=None, obstacle=True, z=None):
    style = style or rng.choice(("dome", "dome", "parasol", "cone", "pagoda"))
    tone = tone or _cap_tone(rng)
    stem = stem or rng.choice(STEM_TONES)
    glow = rng.choice(GILL_GLOW)
    sr = max(0.25, cap_r * rng.uniform(0.14, 0.22))
    z = base_z(height_fn, x, y, sr * 1.5, sink=0.5) if z is None else z
    lean = (rng.uniform(-1.0, 1.0) * h * 0.05, rng.uniform(-1.0, 1.0) * h * 0.05)
    top_x, top_y = x + lean[0], y + lean[1]
    cap_z = z + h * 0.90
    # Detail follows size: a 60 m cap gets smooth curves, a knee-high one a few facets.
    big = cap_r >= 6.0
    small = cap_r < 1.6
    rings = 7 if big else (3 if small else 5)
    sides = 18 if big else (8 if small else 12)
    if not small:
        out.pieces.append(Piece("ellipsoid", (x, y, z + sr * 0.4, sr * 1.7, sr * 1.7, sr * 1.0), stem, "plain", {"rings": 4, "sides": 10}))
    out.pieces.append(Piece("prism", (x, y, z, sr * 1.25, sr, h * 0.92, 10 if big else 6), stem, "plain", {"lean": lean}))
    if h > 8.0:
        ax, ay = x + lean[0] * 0.7, y + lean[1] * 0.7
        out.pieces.append(Piece("prism", (ax, ay, z + h * 0.62, sr * 2.1, sr * 1.15, h * 0.06, 12), stem, "plain", {"hollow": True}))
    if small and style == "pagoda":
        style = "dome"
    if style == "parasol":
        out.pieces.append(Piece("ellipsoid", (top_x, top_y, cap_z, cap_r * 1.25, cap_r * 1.25, cap_r * 0.20), tone, "plain", {"rings": max(3, rings - 1), "sides": sides}))
        under = cap_r * 1.18
    elif style == "cone":
        out.pieces.append(Piece("prism", (top_x, top_y, cap_z - cap_r * 0.15, cap_r * 0.95, 0.0, cap_r * 1.05, sides), tone, "plain"))
        under = cap_r * 0.90
    elif style == "pagoda":
        for k, (f, zf) in enumerate(((1.0, 0.0), (0.72, 0.22), (0.46, 0.42))):
            out.pieces.append(Piece("ellipsoid", (top_x, top_y, cap_z + cap_r * zf, cap_r * f, cap_r * f, cap_r * 0.16), tone, "plain", {"rings": max(3, rings - 2), "sides": sides}))
            out.pieces.append(Piece("prism", (top_x, top_y, cap_z + cap_r * zf - cap_r * 0.05, cap_r * f * 0.86, cap_r * f * 0.86, 0.25, sides), glow, "emissive", {"hollow": True}))
        under = cap_r * 0.95
    else:
        out.pieces.append(Piece("ellipsoid", (top_x, top_y, cap_z, cap_r, cap_r, cap_r * 0.48), tone, "plain", {"rings": rings, "sides": sides}))
        under = cap_r * 0.92
    # Gills: a darker underside and a glowing ring.
    out.pieces.append(Piece("ellipsoid", (top_x, top_y, cap_z - 0.02 * cap_r, under, under, cap_r * 0.10),
                            (tone[0] * 0.40, tone[1] * 0.40, tone[2] * 0.40), "plain", {"rings": 2 if small else 3, "sides": sides}))
    if not small:
        out.pieces.append(Piece("prism", (top_x, top_y, cap_z - 0.10 * cap_r, under * 0.80, under * 0.80, max(0.15, cap_r * 0.04), sides), glow, "emissive", {"hollow": True}))
    if style in ("dome", "parasol") and not small:
        flat = 0.48 if style == "dome" else 0.20
        for _ in range(rng.randint(4, 8) if big else rng.randint(2, 4)):
            a = rng.uniform(0.0, TAU)
            d = cap_r * rng.uniform(0.1, 0.75)
            sz = cap_r * rng.uniform(0.06, 0.12)
            lift = cap_r * flat * math.sqrt(max(0.0, 1.0 - (d / (cap_r * 1.0)) ** 2))
            out.pieces.append(Piece("ellipsoid", (top_x + math.cos(a) * d, top_y + math.sin(a) * d, cap_z + lift * 0.96, sz, sz, sz * 0.4),
                                    SPOT if rng.random() < 0.7 else glow, "plain" if rng.random() < 0.7 else "emissive", {"rings": 2, "sides": 6}))
    if obstacle:
        out.obstacles.append(CircleObstacle(x, y, sr * 1.5, z + h))
    _count(out, "mushrooms")
    return cap_z


def _grove(out, cx, cy, height_fn, rng):
    n = rng.randint(3, 6)
    for k in range(n):
        if k == 0:
            x, y, h = cx, cy, rng.uniform(42.0, 60.0)
        else:
            a = rng.uniform(0.0, TAU)
            d = rng.uniform(14.0, 30.0)
            x, y, h = cx + math.cos(a) * d, cy + math.sin(a) * d, rng.uniform(22.0, 40.0)
        _mushroom(out, x, y, height_fn, rng, h, h * rng.uniform(0.32, 0.42))
    for _ in range(rng.randint(8, 14)):                                     # undergrowth
        a = rng.uniform(0.0, TAU)
        d = rng.uniform(4.0, 34.0)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        h = rng.uniform(1.2, 4.5)
        _mushroom(out, x, y, height_fn, rng, h, h * rng.uniform(0.35, 0.55), obstacle=h > 3.0)
    _count(out, "groves")


def _coral(out, cx, cy, height_fn, rng):
    tone = rng.choice(((1.00, 0.46, 0.18), (0.20, 0.82, 0.78), (0.70, 0.36, 0.96), (0.86, 0.90, 0.30)))
    z0 = height_fn(cx, cy) - 0.3
    for _ in range(rng.randint(5, 9)):
        a = rng.uniform(0.0, TAU)
        reach = rng.uniform(1.2, 3.2)
        h = rng.uniform(2.5, 6.5)
        path = []
        for i in range(6):
            t = i / 5.0
            bend = math.sin(t * 2.2 + a) * 0.4
            path.append((cx + math.cos(a) * reach * t + math.cos(a + 1.6) * bend, cy + math.sin(a) * reach * t + math.sin(a + 1.6) * bend, z0 + h * t))
        out.pieces.append(Piece("sweep", (tuple(path), 0.32, 0.32), tone, "plain"))
        tx, ty, tz = path[-1]
        out.pieces.append(Piece("ellipsoid", (tx, ty, tz, 0.30, 0.30, 0.30), (min(1.0, tone[0] + 0.2), min(1.0, tone[1] + 0.2), min(1.0, tone[2] + 0.2)), "emissive", {"rings": 2, "sides": 6}))
    out.obstacles.append(CircleObstacle(cx, cy, 2.0, z0 + 6.0))
    _count(out, "corals")


def _glow_field(out, cx, cy, height_fn, rng):
    glow = rng.choice(GILL_GLOW)
    for _ in range(rng.randint(10, 18)):
        a = rng.uniform(0.0, TAU)
        d = rng.uniform(0.0, 16.0)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        h = rng.uniform(2.5, 8.5)
        z = height_fn(x, y) - 0.2
        out.pieces.append(Piece("prism", (x, y, z, 0.24, 0.12, h, 6), (0.20, 0.30, 0.28), "plain", {"lean": (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6))}))
        out.pieces.append(Piece("ellipsoid", (x, y, z + h, 0.42, 0.42, 0.60), glow, "emissive", {"rings": 3, "sides": 6}))
    _count(out, "glow_fields")


def _puffballs(out, cx, cy, height_fn, rng):
    for _ in range(rng.randint(4, 8)):
        a = rng.uniform(0.0, TAU)
        d = rng.uniform(0.0, 9.0)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        s = rng.uniform(0.8, 3.4)
        z = height_fn(x, y)
        out.pieces.append(Piece("ellipsoid", (x, y, z + s * 0.7, s, s, s * 0.85), rng.choice(((0.88, 0.86, 0.78), (0.78, 0.72, 0.86), (0.82, 0.88, 0.74))), "plain", {"rings": 6, "sides": 12}))
        if s > 1.8:
            out.obstacles.append(CircleObstacle(x, y, s * 0.9, z + s * 1.5))
    _count(out, "puffball_clusters")


def _spore_vent(out, x, y, height_fn, rng):
    z = height_fn(x, y) - 0.6
    out.pieces.append(Piece("prism", (x, y, z, 4.6, 1.6, 3.4, 9), (0.20, 0.52, 0.56), "crystal"))
    out.pieces.append(Piece("prism", (x, y, z + 3.2, 1.7, 1.7, 0.35, 9), (0.55, 1.00, 0.90), "emissive", {"hollow": True}))
    out.vents.append((x, y, z + 3.4))
    out.obstacles.append(CircleObstacle(x, y, 3.6, z + 3.4))
    _count(out, "vents")


def _titan(out, x, y, height_fn, rng):
    h = rng.uniform(90.0, 120.0)
    cap_r = h * 0.34
    tone = rng.choice(((0.10, 0.60, 0.60), (0.46, 0.26, 0.72), (0.92, 0.52, 0.16), (0.18, 0.30, 0.66)))
    _mushroom(out, x, y, height_fn, rng, h, cap_r, style="dome", tone=tone, stem=STEM_TONES[0])
    z = base_z(height_fn, x, y, cap_r * 0.3, sink=0.5)
    for k in range(rng.randint(5, 8)):                                      # bracket fungi up the stem
        a = rng.uniform(0.0, TAU)
        bz = z + h * rng.uniform(0.15, 0.75)
        sr = cap_r * 0.18
        out.pieces.append(Piece("ellipsoid", (x + math.cos(a) * sr * 1.1, y + math.sin(a) * sr * 1.1, bz, sr * 0.9, sr * 0.9, sr * 0.22),
                                rng.choice(CAP_TONES), "plain", {"rings": 4, "sides": 12, "heading": a}))
    _count(out, "titans")


# --------------------------------------------------------------------------
# Sporekin hollows
# --------------------------------------------------------------------------
def _cap_house(out, x, y, face, height_fn, rng, town):
    body_r = rng.uniform(3.4, 4.8)
    h = rng.uniform(3.6, 5.2)
    z = base_z(height_fn, x, y, body_r, sink=0.4)
    stem = rng.choice(STEM_TONES[:3])
    tone = _cap_tone(rng)
    out.pieces.append(Piece("prism", (x, y, z, body_r, body_r * 0.92, h, 12), stem, "plain"))
    cap_r = body_r * rng.uniform(1.45, 1.75)
    out.pieces.append(Piece("ellipsoid", (x, y, z + h, cap_r, cap_r, cap_r * 0.55), tone, "plain", {"rings": 6, "sides": 16}))
    out.pieces.append(Piece("prism", (x, y, z + h - 0.15, cap_r * 0.9, cap_r * 0.9, 0.25, 16), rng.choice(GILL_GLOW), "emissive", {"hollow": True}))
    for _ in range(rng.randint(3, 6)):
        a = rng.uniform(0.0, TAU)
        d = cap_r * rng.uniform(0.15, 0.7)
        sz = cap_r * 0.10
        out.pieces.append(Piece("ellipsoid", (x + math.cos(a) * d, y + math.sin(a) * d, z + h + cap_r * 0.5 * math.sqrt(max(0.0, 1 - (d / cap_r) ** 2)), sz, sz, sz * 0.4),
                                SPOT, "plain", {"rings": 2, "sides": 6}))
    ux, uy = math.cos(face), math.sin(face)
    dx, dy = x + ux * (body_r - 0.05), y + uy * (body_r - 0.05)
    out.pieces.append(Piece("obox", (dx, dy, z, 0.30, 1.5, 2.3, face), DOOR_GLOW, "emissive"))
    for side in (-1.0, 1.0):
        wa = face + side * 0.9
        wx, wy = x + math.cos(wa) * body_r * 0.97, y + math.sin(wa) * body_r * 0.97
        out.pieces.append(Piece("ellipsoid", (wx, wy, z + h * 0.62, 0.42, 0.42, 0.42), WINDOW_GLOW, "emissive", {"rings": 2, "sides": 6}))
    if rng.random() < 0.4:                                                  # a little mushroom on the roof
        _mushroom(out, x + ux * cap_r * 0.3, y + uy * cap_r * 0.3, height_fn, rng, 1.6, 0.8, obstacle=False, z=z + h + cap_r * 0.42)
    town.doors.append((dx + ux * 1.4, dy + uy * 1.4))
    out.obstacles.append(CircleObstacle(x, y, body_r + 0.2, z + h + cap_r * 0.5))
    town.house_count += 1


def _town(out, sector, x, y, heading, height_fn, rng):
    z0 = height_fn(x, y)
    town = Town(f"f{sector:02d}", sector, x, y, heading, z0)
    loc = lambda lx, ly: local(x, y, heading, lx, ly)  # noqa: E731

    # The hearth: a huge dwelling mushroom with round lit windows spiralling up.
    hx, hy = loc(0.0, 0.0)
    hz = base_z(height_fn, hx, hy, 6.0, sink=0.6)
    _mushroom(out, hx, hy, height_fn, rng, 34.0, 15.0, style="dome", tone=rng.choice(CAP_TONES[:5]), stem=STEM_TONES[0], obstacle=False, z=hz)
    out.obstacles.append(CircleObstacle(hx, hy, 6.4, hz + 34.0))
    for k in range(9):
        a = k * 1.1
        out.pieces.append(Piece("ellipsoid", (hx + math.cos(a) * 5.0, hy + math.sin(a) * 5.0, hz + 3.0 + k * 2.6, 0.7, 0.7, 0.7), WINDOW_GLOW, "emissive", {"rings": 2, "sides": 6}))
    dx, dy = loc(5.3, 0.0)
    out.pieces.append(Piece("obox", (dx, dy, hz, 0.3, 2.4, 3.4, heading), DOOR_GLOW, "emissive"))

    # Mycelium pool ringed by little glowing mushrooms.
    px, py = loc(-20.0, 0.0)
    pz = max(height_fn(px + math.cos(a) * 8.0, py + math.sin(a) * 8.0) for a in (0.0, 1.57, 3.14, 4.71)) + 0.05
    out.pieces.append(Piece("disc", (px, py, 8.5, 0.0), POOL, "crystal", {"flat_z": pz, "rings": 5}))
    out.pieces.append(Piece("prism", (px, py, pz - 1.4, 9.6, 8.6, 1.6, 20), MOSS, "plain", {"hollow": True}))
    for k in range(14):
        a = TAU * k / 14.0
        mx, my = px + math.cos(a) * 11.0, py + math.sin(a) * 11.0
        _mushroom(out, mx, my, height_fn, rng, rng.uniform(0.9, 1.8), 0.7, obstacle=False)
    out.pieces.append(Piece("disc", (x, y, 30.0, 0.08), MOSS, "plain", {"rings": 6}))

    # Lantern stalks round the plaza.
    for k in range(8):
        a = TAU * k / 8.0 + 0.2
        lx, ly = loc(math.cos(a) * 30.0, math.sin(a) * 30.0)
        g = height_fn(lx, ly) - 0.2
        out.pieces.append(Piece("prism", (lx, ly, g, 0.22, 0.14, 4.2, 6), (0.28, 0.24, 0.30), "plain"))
        out.pieces.append(Piece("ellipsoid", (lx, ly, g + 4.4, 0.55, 0.55, 0.70), rng.choice(GILL_GLOW), "emissive", {"rings": 3, "sides": 6}))
        out.obstacles.append(CircleObstacle(lx, ly, 0.35, g + 5.0))

    # Cap houses on two rings, doors facing the hearth.  Gates at local 0 and pi.
    slots = []
    for ring_d, n in ((44.0, 11), (63.0, 15)):
        for k in range(n):
            a = (k + 0.5) * TAU / n + (0.14 if ring_d > 50 else 0.0)
            if min(angle_delta(a, 0.0), angle_delta(a, math.pi)) < (0.30 if ring_d < 50 else 0.22):
                continue
            slots.append((ring_d, a))
    for ring_d, a in rng.sample(slots, min(len(slots), rng.randint(12, 16))):
        cx_, cy_ = loc(math.cos(a) * ring_d, math.sin(a) * ring_d)
        _cap_house(out, cx_, cy_, heading + a + math.pi, height_fn, rng, town)

    # Soft boundary of glow stalks with two mycelium gate arches.
    for k in range(40):
        a = TAU * k / 40.0
        if min(angle_delta(a, 0.0), angle_delta(a, math.pi)) < 0.14:
            continue
        sx, sy = loc(math.cos(a) * 82.0, math.sin(a) * 82.0)
        g = height_fn(sx, sy) - 0.2
        h = rng.uniform(4.5, 7.5)
        out.pieces.append(Piece("prism", (sx, sy, g, 0.32, 0.16, h, 6), (0.22, 0.34, 0.32), "plain"))
        out.pieces.append(Piece("ellipsoid", (sx, sy, g + h, 0.48, 0.48, 0.65), rng.choice(GILL_GLOW), "emissive", {"rings": 3, "sides": 6}))
        out.obstacles.append(CircleObstacle(sx, sy, 0.45, g + h))
    for gate in (0.0, math.pi):
        ends = []
        for side in (-1.0, 1.0):
            a = gate + side * 0.12
            ex, ey = loc(math.cos(a) * 82.0, math.sin(a) * 82.0)
            ends.append((ex, ey, height_fn(ex, ey) - 0.5))
        (ax, ay, az), (bx, by, bz) = ends
        for strand, (w, lift) in enumerate(((1.0, 9.0), (0.6, 10.2), (0.4, 8.0))):
            path = [(ax + (bx - ax) * (i / 12.0), ay + (by - ay) * (i / 12.0), az + (bz - az) * (i / 12.0) + math.sin(i / 12.0 * math.pi) * lift) for i in range(13)]
            out.pieces.append(Piece("sweep", (tuple(path), w, w), (0.84, 0.80, 0.70) if strand == 0 else GILL_GLOW[strand], "plain" if strand == 0 else "emissive"))
        for ex, ey, ez in ends:
            out.pieces.append(Piece("ellipsoid", (ex, ey, ez + 1.0, 1.4, 1.4, 1.6), (0.80, 0.76, 0.66), "plain", {"rings": 5, "sides": 10}))
            out.obstacles.append(CircleObstacle(ex, ey, 1.3, ez + 3.0))
    out.towns.append(town)
    out.drifts.append(Drift(f"{town.key}j", x, y, z0 + 26.0, 55.0, 8, sector * 17 + 3))
    _count(out, "towns")
    _count(out, "houses", town.house_count)
    return town


# --------------------------------------------------------------------------
# The REDACTED port (Nyx and Orbit's clearing)
# --------------------------------------------------------------------------
def _port(out, height_fn):
    x, y = port_position()
    z = height_fn(x, y)
    out.pieces.append(Piece("disc", (x, y, 34.0, 0.10), (0.16, 0.22, 0.26), "plain", {"rings": 6}))
    out.pieces.append(Piece("disc", (x, y, 6.0, 0.16), (0.40, 0.95, 1.00), "emissive", {"rings": 3}))
    for k in range(7):                                    # etched standing stones (the archive's etchings)
        a = TAU * k / 7.0 + 0.3
        sx, sy = x + math.cos(a) * 24.0, y + math.sin(a) * 24.0
        g = height_fn(sx, sy) - 0.4
        h = 5.5 + (k % 3) * 1.2
        face = a + math.pi * 0.5
        out.pieces.append(Piece("obox", (sx, sy, g, 2.4, 0.9, h, face), STONE, "plain"))
        for row in range(3):
            out.pieces.append(Piece("obox", (sx + math.cos(a) * 0.47, sy + math.sin(a) * 0.47, g + 1.4 + row * 1.3, 1.5 - row * 0.3, 0.05, 0.22, face), GLYPH, "emissive"))
            out.pieces.append(Piece("obox", (sx - math.cos(a) * 0.47, sy - math.sin(a) * 0.47, g + 1.4 + row * 1.3, 1.5 - row * 0.3, 0.05, 0.22, face), GLYPH, "emissive"))
        out.obstacles.append(OObstacle(sx, sy, 2.4, 0.9, face, g + h))
    out.port = (x, y, z)
    _count(out, "ports")


# --------------------------------------------------------------------------
# Sector layout
# --------------------------------------------------------------------------
def fungal_sector(sector: int, r0: float, r1: float, height_fn, sector_count: int = SECTOR_COUNT, keep_clear=None) -> FungalSector:
    """Deterministic structures, obstacles, towns and drifts for one Mushroom sector."""
    sector = int(sector) % int(sector_count)
    keep = list(default_keep_clear() if keep_clear is None else keep_clear)
    rng = random.Random(SEED * 1000 + sector * 7919)
    out = FungalSector(sector)
    step = TAU / sector_count
    a0 = sector * step
    mid_r = (r0 + r1) * 0.5

    def candidate(radius, tries=16):
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

    if sector == port_sector(sector_count):
        _port(out, height_fn)
        px, py = port_position()
        out.footprints.append((px, py, PORT_CLEARANCE))
    if sector % TOWN_SECTOR_STRIDE == TOWN_SECTOR_OFFSET:
        for off in (0.0, -110.0, 110.0, -180.0, 180.0, -60.0, 60.0):
            rr = mid_r + off
            a = a0 + step * 0.5
            x, y = math.cos(a) * rr, math.sin(a) * rr
            if ring_spot_is_clear(x, y, TOWN_RADIUS, r0, r1, keep, out.footprints):
                out.footprints.append((x, y, TOWN_RADIUS))
                _town(out, sector, x, y, a, height_fn, rng)
                break
    if sector % 4 == 2:
        spot = candidate(46.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 46.0))
            _titan(out, spot[0], spot[1], height_fn, rng)
    for _ in range(2):
        spot = candidate(46.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 46.0))
            _grove(out, spot[0], spot[1], height_fn, rng)
            if rng.random() < 0.6:
                out.drifts.append(Drift(f"g{sector:02d}{len(out.drifts)}", spot[0], spot[1], height_fn(spot[0], spot[1]) + 30.0, 40.0, 6, sector * 31 + len(out.drifts)))
    for _ in range(2):
        spot = candidate(6.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 6.0))
            _coral(out, spot[0], spot[1], height_fn, rng)
    for _ in range(rng.randint(1, 2)):
        spot = candidate(18.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 18.0))
            _glow_field(out, spot[0], spot[1], height_fn, rng)
    spot = candidate(12.0)
    if spot is not None:
        out.footprints.append((spot[0], spot[1], 12.0))
        _puffballs(out, spot[0], spot[1], height_fn, rng)
    spot = candidate(6.0)
    if spot is not None:
        out.footprints.append((spot[0], spot[1], 6.0))
        _spore_vent(out, spot[0], spot[1], height_fn, rng)
    for _ in range(rng.randint(10, 16)):                                    # scattered small fungi
        spot = candidate(3.0)
        if spot is not None:
            out.footprints.append((spot[0], spot[1], 3.0))
            h = rng.uniform(1.5, 7.0)
            _mushroom(out, spot[0], spot[1], height_fn, rng, h, h * rng.uniform(0.35, 0.55), obstacle=h > 3.0)
    out.counts["drifts"] = len(out.drifts)
    out.counts["pieces"] = len(out.pieces)
    out.counts["obstacles"] = len(out.obstacles)
    return out


# --------------------------------------------------------------------------
# Peaceful life
# --------------------------------------------------------------------------
def town_villagers(town: Town, count: int = 10):
    return make_villagers(town.key, town.doors, count, ((24.0, 27.0), (33.0, 37.0)))


def villager_pose(town: Town, v: Villager, t: float):
    """(x, y, heading, walking) for a Sporekin villager at time t."""
    return _villager_pose(town.x, town.y, v, t, plaza_ring=28.0)


def jelly_pose(drift: Drift, index: int, t: float):
    """(x, y, z, pulse 0..1) of a spore jelly drifting in its cloud."""
    rng = random.Random(hash_key(f"{drift.key}:{index}"))
    fx, fy = rng.uniform(0.006, 0.014), rng.uniform(0.007, 0.016)
    px_, py_ = rng.uniform(0.0, TAU), rng.uniform(0.0, TAU)
    r = drift.radius * rng.uniform(0.3, 1.0)
    x = drift.x + math.sin(t * fx * TAU + px_) * r
    y = drift.y + math.sin(t * fy * TAU + py_) * r
    z = drift.z + rng.uniform(-8.0, 8.0) + math.sin(t * 0.4 + px_) * 2.5
    pulse = 0.5 + 0.5 * math.sin(t * rng.uniform(1.2, 2.0) + py_)
    return x, y, z, pulse
