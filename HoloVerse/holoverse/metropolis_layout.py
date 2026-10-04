"""Deterministic layout for the infinite Metropolis city (Pass 282.52).

Pure data and math (no Panda3D).  The same records drive rendering, the
walk height and building collision, so what you see, what you stand on and
what blocks you cannot drift apart.

City grid
---------
* World-aligned 80 m lots; a stream chunk (320 m) holds 4 x 4 lots.
* A 16 m street runs along every lot boundary (8 m each side of the line).
  The x = 0 and y = 0 lines are the HoloVerse travel corridors; there the
  street is a 32 m boulevard.
* Each lot has a raised sidewalk pad (+0.30 m) inside its streets.  Buildings,
  parks and plazas sit on pads.
* Nothing is placed inside the Urban ring (r < METROPOLIS r0 + entry gap).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

LOT_SIZE = 80.0
LOTS_PER_CHUNK = 4
CHUNK_SIZE = LOT_SIZE * LOTS_PER_CHUNK
STREET_HALF = 8.0
BOULEVARD_HALF = 16.0
PAD_HEIGHT = 0.30
GROUND_Z = 0.03
ENTRY_GAP = 36.0                # no lots this close to the Urban seam
SKYLINE_GROWTH_START = 5550.0   # past the reference band the skyline grows
SKYLINE_GROWTH_SPAN = 6000.0
SKYLINE_GROWTH_MAX = 0.65

DISTRICTS = {
    #               facade rgb            glass rgb            window rgb (lit)     accent rgb          height  density park
    "spire":       ((0.30, 0.36, 0.46), (0.10, 0.14, 0.22), (0.70, 0.90, 1.00), (0.45, 0.80, 1.00), 1.42, 0.90, 0.04),
    "commerce":    ((0.46, 0.39, 0.33), (0.13, 0.11, 0.10), (1.00, 0.80, 0.50), (1.00, 0.35, 0.80), 1.12, 0.84, 0.06),
    "garden-tech": ((0.56, 0.58, 0.53), (0.10, 0.16, 0.15), (0.60, 1.00, 0.85), (0.40, 1.00, 0.60), 0.92, 0.66, 0.26),
    "residential": ((0.50, 0.36, 0.31), (0.12, 0.10, 0.10), (1.00, 0.74, 0.46), (0.80, 0.50, 1.00), 0.76, 0.80, 0.14),
}
ROOF_RGB = (0.20, 0.20, 0.22)
PAD_RGB = (0.30, 0.30, 0.32)
PARK_RGB = (0.12, 0.30, 0.10)
PLAZA_RGB = (0.36, 0.33, 0.40)


def _hash01(*values) -> float:
    """Stable integer hash in [0, 1) (same on every Python build)."""
    h = 0x9E3779B1
    for v in values:
        h ^= (int(v) & 0xFFFFFFFF) + 0x7F4A7C15 + ((h << 6) & 0xFFFFFFFF) + (h >> 2)
        h &= 0xFFFFFFFF
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & 0xFFFFFFFF
    h ^= h >> 16
    return h / 4294967296.0


def district_name(cx: int, cy: int) -> str:
    """Same selector as world.py metropolis_district_profile (Pass 52)."""
    selector = (math.sin(cx * 0.57 + cy * 0.91) + math.cos(cx * 0.31 - cy * 0.47)) * 0.5
    if selector > 0.35:
        return "spire"
    if selector > -0.05:
        return "commerce"
    if selector > -0.42:
        return "garden-tech"
    return "residential"


def chunk_key_for_point(x: float, y: float):
    return int(math.floor(float(x) / CHUNK_SIZE)), int(math.floor(float(y) / CHUNK_SIZE))


def lot_index_for_point(x: float, y: float):
    return int(math.floor(float(x) / LOT_SIZE)), int(math.floor(float(y) / LOT_SIZE))


def lot_pad_rect(lx: int, ly: int):
    """Raised pad rectangle (x0, y0, x1, y1) for global lot (lx, ly)."""
    x0 = lx * LOT_SIZE; y0 = ly * LOT_SIZE
    x1 = x0 + LOT_SIZE; y1 = y0 + LOT_SIZE
    def inset(edge):
        return BOULEVARD_HALF if abs(edge) < 1e-6 else STREET_HALF
    return (x0 + inset(x0), y0 + inset(y0), x1 - inset(x1), y1 - inset(y1))


def lot_is_city(lx: int, ly: int, r0: float) -> bool:
    """A lot is built only when its whole pad lies outside the Urban seam band."""
    px0, py0, px1, py1 = lot_pad_rect(lx, ly)
    nearest_x = 0.0 if px0 <= 0.0 <= px1 else min(abs(px0), abs(px1))
    nearest_y = 0.0 if py0 <= 0.0 <= py1 else min(abs(py0), abs(py1))
    return math.hypot(nearest_x, nearest_y) >= float(r0) + ENTRY_GAP


def ground_offset(x: float, y: float, r0: float) -> float:
    """Walk-height offset above hub ground: +PAD_HEIGHT on city pads, else 0."""
    lx, ly = lot_index_for_point(x, y)
    if not lot_is_city(lx, ly, r0):
        return 0.0
    px0, py0, px1, py1 = lot_pad_rect(lx, ly)
    if px0 <= x <= px1 and py0 <= y <= py1:
        return PAD_HEIGHT
    return 0.0


def skyline_scale(x: float, y: float) -> float:
    r = math.hypot(x, y)
    t = max(0.0, min(1.0, (r - SKYLINE_GROWTH_START) / SKYLINE_GROWTH_SPAN))
    return 1.0 + SKYLINE_GROWTH_MAX * t


@dataclass
class Box:
    """Axis-aligned solid (centre x/y, base z, size). ``kind`` picks the material."""
    x: float
    y: float
    z0: float
    sx: float
    sy: float
    sz: float
    kind: str = "facade"     # facade | roof | plain | emissive | foliage | trunk
    rgb: tuple = (0.5, 0.5, 0.5)
    seed: float = 0.0


@dataclass
class Prism:
    """Vertical regular prism (spire sections), optionally tapered."""
    x: float
    y: float
    z0: float
    radius0: float
    radius1: float
    height: float
    sides: int = 8
    kind: str = "facade"
    rgb: tuple = (0.5, 0.5, 0.5)
    seed: float = 0.0


@dataclass
class Obstacle:
    x0: float
    y0: float
    x1: float
    y1: float
    top: float


@dataclass
class Lot:
    lx: int
    ly: int
    kind: str                    # tower | spire | slab | residential | park | plaza | clear
    pad: tuple
    pad_rgb: tuple
    height: float = 0.0


@dataclass
class ChunkLayout:
    cx: int
    cy: int
    district: str
    lots: list = field(default_factory=list)
    boxes: list = field(default_factory=list)
    prisms: list = field(default_factory=list)
    obstacles: list = field(default_factory=list)
    lights: list = field(default_factory=list)     # (x, y) street-light positions
    bridges: int = 0


def _tower(layout, pad, district, n, h_total, seed):
    facade, glass, _win, accent, *_ = DISTRICTS[district]
    px0, py0, px1, py1 = pad
    cx = (px0 + px1) * 0.5; cy = (py0 + py1) * 0.5
    w = (px1 - px0) * (0.50 + 0.30 * _hash01(seed, 3))
    d = (py1 - py0) * (0.50 + 0.30 * _hash01(seed, 4))
    z = GROUND_Z + PAD_HEIGHT
    tiers = 2 + int(_hash01(seed, 5) * 3)
    shares = [0.42, 0.30, 0.18, 0.10][:tiers]
    total_share = sum(shares)
    colour = tuple(c * (0.85 + 0.30 * _hash01(seed, 6)) for c in facade)
    first = True
    for share in shares:
        th = h_total * share / total_share
        layout.boxes.append(Box(cx, cy, z, w, d, th, "facade", colour, seed))
        if first:
            layout.obstacles.append(Obstacle(cx - w * 0.5, cy - d * 0.5, cx + w * 0.5, cy + d * 0.5, z + h_total))
            first = False
        # Thin accent band where each tier steps back.
        layout.boxes.append(Box(cx, cy, z + th - 0.6, w + 0.3, d + 0.3, 0.6, "emissive", accent, seed))
        z += th
        shrink = 0.72 + 0.12 * _hash01(seed, int(z))
        w *= shrink; d *= shrink
    layout.boxes.append(Box(cx, cy, z, w * 0.9, d * 0.9, 1.2, "roof", ROOF_RGB, seed))
    if h_total > 90.0:
        layout.boxes.append(Box(cx, cy, z + 1.2, 0.8, 0.8, 10.0 + h_total * 0.08, "plain", (0.25, 0.25, 0.28), seed))
        layout.boxes.append(Box(cx, cy, z + 11.0 + h_total * 0.08, 1.4, 1.4, 1.4, "emissive", accent, seed))
    return z


def _spire(layout, pad, district, n, h_total, seed):
    facade, glass, _win, accent, *_ = DISTRICTS[district]
    px0, py0, px1, py1 = pad
    cx = (px0 + px1) * 0.5; cy = (py0 + py1) * 0.5
    r = min(px1 - px0, py1 - py0) * (0.30 + 0.10 * _hash01(seed, 7))
    z = GROUND_Z + PAD_HEIGHT
    colour = tuple(c * (0.85 + 0.25 * _hash01(seed, 8)) for c in facade)
    lower = h_total * 0.62
    layout.prisms.append(Prism(cx, cy, z, r, r * 0.86, lower, 8, "facade", colour, seed))
    layout.prisms.append(Prism(cx, cy, z + lower - 0.7, r * 0.88, r * 0.88, 0.7, 8, "emissive", accent, seed))
    layout.prisms.append(Prism(cx, cy, z + lower, r * 0.78, r * 0.40, h_total - lower, 8, "facade", colour, seed))
    tip = z + h_total
    layout.prisms.append(Prism(cx, cy, tip, r * 0.18, 0.05, 14.0 + h_total * 0.06, 6, "emissive", accent, seed))
    k = r * 0.93
    layout.obstacles.append(Obstacle(cx - k, cy - k, cx + k, cy + k, tip))
    return tip


def _slab(layout, pad, district, n, h_total, seed):
    facade, *_ = DISTRICTS[district]
    px0, py0, px1, py1 = pad
    cx = (px0 + px1) * 0.5; cy = (py0 + py1) * 0.5
    along_x = _hash01(seed, 9) < 0.5
    w = (px1 - px0) * (0.82 if along_x else 0.42)
    d = (py1 - py0) * (0.42 if along_x else 0.82)
    h = max(18.0, h_total * 0.45)
    z = GROUND_Z + PAD_HEIGHT
    colour = tuple(c * (0.80 + 0.30 * _hash01(seed, 10)) for c in facade)
    layout.boxes.append(Box(cx, cy, z, w, d, h, "facade", colour, seed))
    layout.boxes.append(Box(cx, cy, z + h, w * 0.96, d * 0.96, 0.8, "roof", ROOF_RGB, seed))
    for k in range(2 + int(_hash01(seed, 11) * 3)):
        ox = (_hash01(seed, 20 + k) - 0.5) * w * 0.6
        oy = (_hash01(seed, 30 + k) - 0.5) * d * 0.6
        layout.boxes.append(Box(cx + ox, cy + oy, z + h + 0.8, 3.0 + 3.0 * _hash01(seed, 40 + k), 3.0 + 2.0 * _hash01(seed, 50 + k), 1.6 + 2.0 * _hash01(seed, 60 + k), "plain", (0.32, 0.32, 0.34), seed))
    layout.obstacles.append(Obstacle(cx - w * 0.5, cy - d * 0.5, cx + w * 0.5, cy + d * 0.5, z + h))
    return z + h


def _residential(layout, pad, district, n, h_total, seed):
    facade, *_ = DISTRICTS[district]
    px0, py0, px1, py1 = pad
    gap = 6.0
    bw = (px1 - px0 - gap) * 0.5
    bd = (py1 - py0 - gap) * 0.5
    z = GROUND_Z + PAD_HEIGHT
    top = z
    for i in range(2):
        for j in range(2):
            if _hash01(seed, 70 + i * 2 + j) < 0.12:
                continue
            w = bw * (0.74 + 0.20 * _hash01(seed, 80 + i * 2 + j))
            d = bd * (0.74 + 0.20 * _hash01(seed, 90 + i * 2 + j))
            cx = px0 + bw * (i + 0.5) + gap * i
            cy = py0 + bd * (j + 0.5) + gap * j
            h = 10.0 + 22.0 * _hash01(seed, 100 + i * 2 + j) * max(0.6, h_total / 60.0)
            colour = tuple(c * (0.80 + 0.35 * _hash01(seed, 110 + i * 2 + j)) for c in facade)
            layout.boxes.append(Box(cx, cy, z, w, d, h, "facade", colour, seed + i * 2 + j))
            layout.boxes.append(Box(cx, cy, z + h, w + 0.6, d + 0.6, 0.7, "roof", ROOF_RGB, seed))
            layout.obstacles.append(Obstacle(cx - w * 0.5, cy - d * 0.5, cx + w * 0.5, cy + d * 0.5, z + h))
            top = max(top, z + h)
    return top


def _park(layout, pad, district, seed):
    _f, _g, _w, accent, *_ = DISTRICTS[district]
    px0, py0, px1, py1 = pad
    z = GROUND_Z + PAD_HEIGHT
    count = 6 + int(_hash01(seed, 120) * 6)
    for k in range(count):
        tx = px0 + 6.0 + (px1 - px0 - 12.0) * _hash01(seed, 130 + k)
        ty = py0 + 6.0 + (py1 - py0 - 12.0) * _hash01(seed, 150 + k)
        th = 5.0 + 5.0 * _hash01(seed, 170 + k)
        cr = 2.6 + 2.2 * _hash01(seed, 190 + k)
        layout.boxes.append(Box(tx, ty, z, 0.7, 0.7, th, "trunk", (0.26, 0.18, 0.12), seed))
        green = (0.10 + 0.10 * _hash01(seed, 210 + k), 0.34 + 0.18 * _hash01(seed, 230 + k), 0.12)
        layout.prisms.append(Prism(tx, ty, z + th * 0.55, cr, cr * 0.25, th * 0.95, 6, "foliage", green, seed + k))
        layout.obstacles.append(Obstacle(tx - 0.6, ty - 0.6, tx + 0.6, ty + 0.6, z + th))
    cx = (px0 + px1) * 0.5; cy = (py0 + py1) * 0.5
    layout.prisms.append(Prism(cx, cy, z, 2.4, 2.4, 0.9, 12, "plain", (0.40, 0.40, 0.44), seed))
    layout.prisms.append(Prism(cx, cy, z + 0.9, 0.5, 0.2, 9.0, 6, "emissive", accent, seed))
    layout.obstacles.append(Obstacle(cx - 2.3, cy - 2.3, cx + 2.3, cy + 2.3, z + 9.9))


def _plaza(layout, pad, district, seed, holo=True):
    _f, _g, _w, accent, *_ = DISTRICTS[district]
    px0, py0, px1, py1 = pad
    cx = (px0 + px1) * 0.5; cy = (py0 + py1) * 0.5
    z = GROUND_Z + PAD_HEIGHT
    if holo:
        layout.boxes.append(Box(cx, cy, z, 6.0, 6.0, 0.5, "plain", (0.38, 0.38, 0.42), seed))
        layout.prisms.append(Prism(cx, cy, z + 0.5, 1.4, 0.1, 6.0, 4, "emissive", accent, seed))
        layout.obstacles.append(Obstacle(cx - 3.0, cy - 3.0, cx + 3.0, cy + 3.0, z + 6.5))


def generate_chunk(cx: int, cy: int, r0: float, *, clear_fn=None) -> ChunkLayout:
    """Build the full layout for stream chunk (cx, cy).

    ``clear_fn(x, y) -> str`` names a reserved spot (e.g. a guide bot plaza);
    lots it claims become open plazas.
    """
    district = district_name(cx, cy)
    facade, glass, window, accent, height_scale, density, park_share = DISTRICTS[district]
    layout = ChunkLayout(cx, cy, district)
    tall_lots = {}
    for ix in range(LOTS_PER_CHUNK):
        for iy in range(LOTS_PER_CHUNK):
            lx = cx * LOTS_PER_CHUNK + ix
            ly = cy * LOTS_PER_CHUNK + iy
            if not lot_is_city(lx, ly, r0):
                continue
            pad = lot_pad_rect(lx, ly)
            mx = (pad[0] + pad[2]) * 0.5; my = (pad[1] + pad[3]) * 0.5
            seed = int(_hash01(lx, ly, 28252) * 1e6)
            # Street lights on the pad corners facing the streets.
            for sx, sy in ((pad[0] + 1.5, pad[1] + 1.5), (pad[2] - 1.5, pad[1] + 1.5), (pad[0] + 1.5, pad[3] - 1.5), (pad[2] - 1.5, pad[3] - 1.5)):
                layout.lights.append((sx, sy))
            if clear_fn is not None and clear_fn(mx, my):
                layout.lots.append(Lot(lx, ly, "clear", pad, PLAZA_RGB))
                continue
            n = _hash01(lx, ly, 7)
            if n > density:
                kind = "park" if _hash01(lx, ly, 9) < 0.65 else "plaza"
            elif _hash01(lx, ly, 11) < park_share:
                kind = "park"
            else:
                pick = _hash01(lx, ly, 13)
                if district == "spire":
                    kind = "spire" if pick < 0.45 else ("tower" if pick < 0.85 else "slab")
                elif district == "commerce":
                    kind = "tower" if pick < 0.55 else ("slab" if pick < 0.85 else "spire")
                elif district == "garden-tech":
                    kind = "slab" if pick < 0.45 else ("tower" if pick < 0.75 else "residential")
                else:
                    kind = "residential" if pick < 0.65 else ("slab" if pick < 0.85 else "tower")
            growth = skyline_scale(mx, my)
            base = 20.0 + 24.0 * _hash01(lx, ly, 15)
            tall = (34.0 + 110.0 * _hash01(lx, ly, 17)) * (0.66 + 0.42 * height_scale) if _hash01(lx, ly, 19) > 0.42 else 0.0
            h_total = (base * height_scale + tall) * growth
            if kind == "tower":
                top = _tower(layout, pad, district, n, h_total, seed)
                tall_lots[(ix, iy)] = (mx, my, top, pad)
                lot = Lot(lx, ly, kind, pad, PAD_RGB, top)
            elif kind == "spire":
                top = _spire(layout, pad, district, n, max(h_total, 70.0), seed)
                lot = Lot(lx, ly, kind, pad, PAD_RGB, top)
            elif kind == "slab":
                top = _slab(layout, pad, district, n, h_total, seed)
                lot = Lot(lx, ly, kind, pad, PAD_RGB, top)
            elif kind == "residential":
                top = _residential(layout, pad, district, n, h_total, seed)
                lot = Lot(lx, ly, kind, pad, PAD_RGB, top)
            elif kind == "park":
                _park(layout, pad, district, seed)
                lot = Lot(lx, ly, kind, pad, PARK_RGB)
            else:
                _plaza(layout, pad, district, seed)
                lot = Lot(lx, ly, kind, pad, PLAZA_RGB)
            layout.lots.append(lot)
    # Skybridges across a street between neighbouring towers (below the
    # traffic lanes, which start at 60 m).
    for (ix, iy), (mx, my, top, pad) in tall_lots.items():
        for dx, dy in ((1, 0), (0, 1)):
            other = tall_lots.get((ix + dx, iy + dy))
            if other is None or min(top, other[2]) < 60.0:
                continue
            if _hash01(cx * 4 + ix, cy * 4 + iy, dx * 3 + dy) > 0.45:
                continue
            bz = min(28.0 + 20.0 * _hash01(ix, iy, 300), min(top, other[2]) - 12.0, 52.0)
            if dx:
                x0 = pad[2] - 2.0; x1 = other[3][0] + 2.0
                layout.boxes.append(Box((x0 + x1) * 0.5, my, bz, x1 - x0, 4.0, 3.2, "plain", (0.34, 0.36, 0.42), 0))
                layout.boxes.append(Box((x0 + x1) * 0.5, my, bz - 0.25, x1 - x0, 4.4, 0.25, "emissive", accent, 0))
            else:
                y0 = pad[3] - 2.0; y1 = other[3][1] + 2.0
                layout.boxes.append(Box(mx, (y0 + y1) * 0.5, bz, 4.0, y1 - y0, 3.2, "plain", (0.34, 0.36, 0.42), 0))
                layout.boxes.append(Box(mx, (y0 + y1) * 0.5, bz - 0.25, 4.4, y1 - y0, 0.25, "emissive", accent, 0))
            layout.bridges += 1
    return layout


def street_lines_in_chunk(cx: int, cy: int):
    """Street centre lines crossing chunk (cx, cy): (axis, coordinate) pairs.

    axis 0 = a street running along x (constant y); axis 1 = along y.
    Includes the chunk's own lower/left boundary streets.
    """
    lines = []
    for k in range(LOTS_PER_CHUNK):
        lines.append((0, (cy * LOTS_PER_CHUNK + k) * LOT_SIZE))
        lines.append((1, (cx * LOTS_PER_CHUNK + k) * LOT_SIZE))
    return lines


def resolve_move(obstacles, px: float, py: float, nx: float, ny: float, radius: float = 0.9, z=None):
    """Return the (x, y) the player ends at moving from (px,py) toward (nx,ny).

    Axis-separated resolution gives wall sliding.  Obstacles whose top is
    below ``z - 1`` (e.g. a craft flying over a roof) are ignored.
    """
    def blocked(x, y):
        for ob in obstacles:
            if z is not None and z > ob.top + 1.0:
                continue
            if ob.x0 - radius < x < ob.x1 + radius and ob.y0 - radius < y < ob.y1 + radius:
                return True
        return False

    if not blocked(nx, ny):
        return nx, ny, False
    if not blocked(nx, py):
        return nx, py, True
    if not blocked(px, ny):
        return px, ny, True
    if blocked(px, py):
        # Already inside (spawned or teleported into a solid): let them walk out.
        return nx, ny, True
    return px, py, True
