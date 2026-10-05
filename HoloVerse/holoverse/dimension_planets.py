"""HoloVerse Pass 282.64 / 282.70: Dimension planets in HoloSpace.

Pass 282.70: every planet is generated *from its dimension*: the world type comes from
the dimension's own name and description (ice, lava, ocean, fungal/toxic, crystal or
gas), and its colours come from the dimension's icon art, so each planet reads as that
game.  Planets are now large worlds (no little orbs: moons removed) and are laid out
with real space between them; the separation accounts for each planet's size.

Gleebs' Dimension Archive used to float its linked realities as small orbs
around the hub.  They now live in HoloSpace as distant planets:

* **Out of reach.**  Planets sit in the deep-space *sky layer* (its camera only
  rotates with the ship), so no amount of flying brings them closer and the
  ship can never touch them.
* **Spread out.**  Each planet gets a stable direction from its dimension id,
  kept well apart from the other planets, from Dyson Prime and from the gas
  giant, and drawn farther away than Dyson Prime.
* **Aim and click.**  Put the crosshair on a planet: its name appears under the
  crosshair.  Left-click pauses the flight and asks whether to enter that
  dimension (ENTER / STAY, ESC = stay).  ENTER returns home first (the same
  clean exit as TAB) and then opens the dimension through the registry, the
  only launch authority.

Designs: every planet is procedural and different (gas giant, ocean world,
ice world, lava world, crystal world, toxic world), lit from Dyson Prime's red
star with a soft day/night terminator, with an atmosphere rim, and some carry
rings or a small moon.  The surface slowly turns (a texture scroll, so the
lighting stays put).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading

import numpy as np
from panda3d.core import (
    ColorBlendAttrib,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomEnums,
    GeomVertexArrayFormat,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    NodePath,
    SamplerState,
    TextNode,
    Texture,
    TextureStage,
    TransparencyAttrib,
    Vec3,
)

PLANET_MIN_DISTANCE = 85000.0      # Dyson Prime is at 60 000 sky units
PLANET_MAX_DISTANCE = 150000.0     # wider depth range: planets sit at clearly different distances
PLANET_MIN_ANG_RADIUS_DEG = 5.5    # Pass 282.70: real worlds, not little orbs
PLANET_MAX_ANG_RADIUS_DEG = 9.0
EDGE_GAP_DEG = 24.0                # empty sky kept between two planets' edges (relaxed only if crowded)
MIN_SEPARATION_DEG = 30.0          # legacy name, used as a floor for the centre spacing
DYSON_CLEARANCE_DEG = 46.0
GIANT_CLEARANCE_DEG = 32.0
ELEVATION_RANGE_DEG = (-38.0, 58.0)
AIM_SLACK = 1.18                   # aim counts within 118% of the planet's disc ...
AIM_MIN_DEG = 1.0                  # ... and never tighter than 1 degree
TEX_W, TEX_H = 512, 256
STAR_COLOR = (1.00, 0.88, 0.78)    # Dyson Prime's light: warm, but not so red it greys every planet
NIGHT = 0.06

ARCHETYPES = ("gas", "ocean", "ice", "lava", "crystal", "toxic")


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _seed(text: str) -> int:
    return int.from_bytes(hashlib.sha256(str(text or "dimension").encode("utf-8", "replace")).digest()[:8], "big")


class _Rng:
    """Small deterministic RNG (so a planet looks the same every launch)."""

    def __init__(self, seed: int):
        self.state = (seed or 1) & 0xFFFFFFFFFFFF

    def random(self) -> float:
        self.state = (self.state * 25214903917 + 11) & 0xFFFFFFFFFFFF
        return (self.state >> 17) / float(1 << 31)

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self.random()

    def choice(self, seq):
        return seq[int(self.random() * len(seq)) % len(seq)]


# ----------------------------------------------------------------------
# Pass 282.82: caches.  Building the 16 planets cost ~6 s on the frame HoloSpace opened (the
# warp froze).  Icon colours and finished surface textures are now kept on disk in the player's
# cache folder and in memory, and are prepared in the background while the player is at the hub.
# ----------------------------------------------------------------------
_CACHE_VERSION = 1
_MEM_PALETTES: dict = {}
_MEM_SURFACES: dict = {}
_CACHE_LOCK = threading.Lock()


def _cache_dir():
    try:
        from holoverse_userdata import user_data_root
        path = user_data_root() / "cache" / "planets"
        path.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:
        return None


def _atomic_write(path, writer) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        writer(tmp)
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink()
        except Exception:
            pass


def _dir(lon_deg: float, lat_deg: float) -> Vec3:
    lo, la = math.radians(lon_deg), math.radians(lat_deg)
    return Vec3(math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def _angle_deg(a: Vec3, b: Vec3) -> float:
    a = Vec3(a); b = Vec3(b)
    a.normalize(); b.normalize()
    return math.degrees(math.acos(max(-1.0, min(1.0, a.dot(b)))))


# ---- 3-D value noise on the sphere (no seams at the poles or the date line)
def _hash3(ix, iy, iz, salt):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ salt
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFF).astype(np.float32) / 65535.0


def _vnoise(x, y, z, salt):
    ix, iy, iz = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64), np.floor(z).astype(np.int64)
    fx, fy, fz = x - ix, y - iy, z - iz
    ux, uy, uz = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy), fz * fz * (3 - 2 * fz)
    out = 0.0
    for dx in (0, 1):
        wx = ux if dx else 1 - ux
        for dy in (0, 1):
            wy = uy if dy else 1 - uy
            for dz in (0, 1):
                wz = uz if dz else 1 - uz
                out = out + _hash3(ix + dx, iy + dy, iz + dz, salt) * wx * wy * wz
    return out


def _fbm(x, y, z, salt, octaves=5, freq=2.0):
    v = np.zeros_like(x, dtype=np.float32)
    amp, total = 0.5, 0.0
    for o in range(octaves):
        v = v + amp * _vnoise(x * freq, y * freq, z * freq, salt + o * 1013)
        total += amp
        amp *= 0.5
        freq *= 2.03
    return v / total


def _lerp(a, b, t):
    t = t[..., None]
    return np.asarray(a, np.float32) * (1 - t) + np.asarray(b, np.float32) * t


# ----------------------------------------------------------------------
# dimension identity: world type from its words, colours from its icon
# ----------------------------------------------------------------------
KIND_KEYWORDS = (
    ("ice", ("ice", "frost", "polar", "glacier", "snow", "cryo", "frozen", "pluto")),
    ("lava", ("lava", "fire", "hell", "crimson", "inferno", "volcan", "nemesis", "fractured", "war", "conflict", "ember")),
    ("ocean", ("ocean", "sea", "water", "coral", "aqua", "tide", "underwater", "holocore", "strata")),
    ("toxic", ("toxic", "fungal", "mushroom", "spore", "swamp", "dread", "zone", "anatomic", "matter")),
    ("crystal", ("crystal", "glyph", "shrine", "archive", "archivist", "mirror", "limbo", "map", "tactics", "utopia", "civic")),
    ("gas", ("gas", "giant", "storm", "orbit", "starfall", "space", "vector", "shell", "sky")),
)


def kind_for_record(rec) -> str | None:
    text = " ".join(str(getattr(rec, attr, "") or "") for attr in ("title", "description")).casefold()
    title = str(getattr(rec, "title", "") or "").casefold()
    import re
    for source in (title, text):               # the title decides first, then the description
        for kind, words in KIND_KEYWORDS:
            if any(re.search(r"\b" + re.escape(w), source) for w in words):   # word starts only ("shell" is not "hell")
                return kind
    return None


def icon_palette(path) -> tuple | None:
    """icon_palette_uncached, remembered in memory and on disk (keyed by the icon file's size/time)."""
    try:
        from pathlib import Path as _P
        if not path or not _P(str(path)).is_file():
            return None
        st = _P(str(path)).stat()
        key = hashlib.sha1(f"{_CACHE_VERSION}|{os.path.abspath(str(path))}|{st.st_size}|{st.st_mtime_ns}".encode("utf-8", "replace")).hexdigest()[:20]
    except Exception:
        return icon_palette_uncached(path)
    if key in _MEM_PALETTES:
        return _MEM_PALETTES[key]
    folder = _cache_dir()
    disk = folder / f"palette-{key}.json" if folder is not None else None
    if disk is not None and disk.is_file():
        try:
            data = json.loads(disk.read_text(encoding="utf-8"))
            value = None if data.get("none") else (tuple(data["a"]), tuple(data["b"]))
            _MEM_PALETTES[key] = value
            return value
        except Exception:
            pass
    value = icon_palette_uncached(path)
    _MEM_PALETTES[key] = value
    if disk is not None:
        payload = {"none": True} if value is None else {"a": list(value[0]), "b": list(value[1])}
        _atomic_write(disk, lambda t: t.write_text(json.dumps(payload), encoding="utf-8"))
    return value


def icon_palette_uncached(path) -> tuple | None:
    """Two representative colours from a dimension's icon (its most saturated hues)."""
    try:
        from pathlib import Path as _P
        from panda3d.core import Filename, PNMImage
        if not path or not _P(str(path)).is_file():
            return None
        img = PNMImage()
        if not img.read(Filename.fromOsSpecific(str(path))):
            return None
        w, h = img.getXSize(), img.getYSize()
        import colorsys
        samples = []
        steps = 28
        for yi in range(steps):
            for xi in range(steps):
                r, g, b = img.getXel(int((xi + 0.5) * w / steps), int((yi + 0.5) * h / steps))
                hh, s, v = colorsys.rgb_to_hsv(r, g, b)
                if s > 0.22 and v > 0.18:
                    samples.append((hh, s, v, (r, g, b)))
        if len(samples) < 8:
            return None
        samples.sort(key=lambda t: t[0])
        half = len(samples) // 2

        def mean(group):
            n = float(len(group))
            return tuple(sum(c[3][k] for c in group) / n for k in range(3))

        first, second = mean(samples[:half]), mean(samples[half:])
        return first, second
    except Exception:
        return None


def _apply_identity_tint(rgb: np.ndarray, palette) -> np.ndarray:
    """Re-colour the procedural surface toward the dimension's own colours, keeping its detail."""
    if not palette:
        return rgb
    a = np.asarray(palette[0], np.float32)
    b = np.asarray(palette[1], np.float32)
    lum = rgb.mean(axis=-1, keepdims=True)
    t = np.clip((lum - 0.15) / 0.7, 0, 1)
    tinted = (a * (1 - t) + b * t) * (0.45 + lum * 1.25)
    return np.clip(rgb * 0.55 + tinted * 0.45, 0, 1)


# ----------------------------------------------------------------------
# planet surface art
# ----------------------------------------------------------------------
def _surface_rgb(kind: str, rng: _Rng, accent) -> np.ndarray:
    lon = np.linspace(-math.pi, math.pi, TEX_W, endpoint=False, dtype=np.float32)
    lat = np.linspace(math.pi / 2, -math.pi / 2, TEX_H, dtype=np.float32)
    LON, LAT = np.meshgrid(lon, lat)
    X, Y, Z = np.cos(LAT) * np.cos(LON), np.cos(LAT) * np.sin(LON), np.sin(LAT)
    salt = int(rng.uniform(1, 1 << 20))
    acc = np.asarray(accent[:3], np.float32)

    if kind == "gas":
        warp = _fbm(X, Y, Z, salt, 4, 2.2)
        bands = np.sin(LAT * rng.uniform(9, 16) + warp * 5.0) * 0.5 + 0.5
        fine = _fbm(X * 3, Y * 3, Z * 6, salt + 7, 3, 3.0)
        c1 = np.asarray([rng.uniform(0.55, 0.85), rng.uniform(0.40, 0.65), rng.uniform(0.28, 0.50)], np.float32)
        c2 = np.clip(c1 * 0.55 + acc * 0.25, 0, 1)
        rgb = _lerp(c2, c1, np.clip(bands * 0.8 + fine * 0.4, 0, 1))
        # a storm eye
        sx, sy, sz = _dir(rng.uniform(-180, 180), rng.uniform(-30, 30))
        d = np.sqrt((X - sx) ** 2 + (Y - sy) ** 2 + (Z - sz) ** 2)
        storm = np.clip(1 - d / 0.18, 0, 1) ** 1.5
        rgb = _lerp(rgb, np.clip(c1 * 1.2 + 0.1, 0, 1), storm * 0.9)
    elif kind == "ocean":
        h = _fbm(X, Y, Z, salt, 6, 1.8)
        sea = rng.uniform(0.50, 0.56)
        land = h > sea
        deep, shallow = (0.03, 0.10, 0.26), (0.08, 0.34, 0.52)
        rgb = _lerp(deep, shallow, np.clip((h - 0.35) / (sea - 0.35), 0, 1))
        green, rock = (0.18, 0.40, 0.16), (0.48, 0.42, 0.30)
        land_rgb = _lerp(green, rock, np.clip((h - sea) / 0.18, 0, 1))
        rgb = np.where(land[..., None], land_rgb, rgb)
        ice = np.clip((np.abs(LAT) - 1.22) / 0.2, 0, 1)
        rgb = _lerp(rgb, (0.92, 0.95, 0.98), ice)
        clouds = np.clip((_fbm(X * 1.3, Y * 1.3, Z * 2.0, salt + 99, 5, 2.5) - 0.55) * 3.2, 0, 1)
        rgb = _lerp(rgb, (0.96, 0.97, 1.0), clouds * 0.85)
    elif kind == "ice":
        h = _fbm(X, Y, Z, salt, 5, 2.4)
        rgb = _lerp((0.58, 0.70, 0.82), (0.93, 0.96, 1.0), np.clip(h * 1.4 - 0.2, 0, 1))
        cracks = np.abs(_fbm(X, Y, Z, salt + 3, 4, 4.0) - 0.5)
        crack = np.clip(1 - cracks / 0.035, 0, 1)
        rgb = _lerp(rgb, np.clip(acc * 0.6 + np.asarray((0.2, 0.45, 0.7)) * 0.4, 0, 1), crack * 0.8)
    elif kind == "lava":
        h = _fbm(X, Y, Z, salt, 5, 2.2)
        rgb = _lerp((0.05, 0.04, 0.04), (0.20, 0.15, 0.13), np.clip(h * 1.5 - 0.3, 0, 1))
        cracks = np.abs(_fbm(X, Y, Z, salt + 11, 4, 3.4) - 0.5)
        glow = np.clip(1 - cracks / 0.05, 0, 1) ** 1.4
        rgb = _lerp(rgb, (1.0, 0.45, 0.08), glow)
    elif kind == "crystal":
        h = _fbm(X, Y, Z, salt, 3, 2.6)
        q = np.floor(h * 9.0) / 9.0                       # terraced facets
        base = np.clip(acc * 0.55 + 0.12, 0, 1)
        rgb = _lerp(base * 0.35, np.clip(base * 1.25 + 0.15, 0, 1), q)
        grid = np.maximum(np.abs(np.sin(LON * 18)) ** 60, np.abs(np.sin(LAT * 18)) ** 60)
        rgb = _lerp(rgb, np.clip(acc + 0.3, 0, 1), grid * 0.55)
    else:  # toxic
        h = _fbm(X, Y, Z, salt, 5, 2.0)
        swirl = np.sin(LAT * 7 + h * 8.0) * 0.5 + 0.5
        rgb = _lerp((0.20, 0.30, 0.04), (0.70, 0.78, 0.18), np.clip(swirl * 0.7 + h * 0.4, 0, 1))
        rgb = _lerp(rgb, (0.32, 0.10, 0.36), np.clip((h - 0.62) * 4, 0, 1))
    return np.clip(rgb, 0, 1)


def surface_bytes(kind: str, rng: _Rng, accent, palette) -> np.ndarray:
    """The finished (tinted) surface as uint8 RGB, from cache when possible.

    The planet's RNG is advanced exactly as if the surface had been generated, so rings and every
    later draw stay identical to the uncached build."""
    acc = tuple(round(float(c), 4) for c in tuple(accent)[:3])
    pal = None if not palette else tuple(tuple(round(float(c), 4) for c in col) for col in palette)
    key = hashlib.sha1(f"{_CACHE_VERSION}|{TEX_W}x{TEX_H}|{kind}|{rng.state}|{acc}|{pal}".encode()).hexdigest()[:24]
    hit = _MEM_SURFACES.get(key)
    folder = _cache_dir()
    disk = folder / f"surface-{key}.npz" if folder is not None else None
    if hit is None and disk is not None and disk.is_file():
        try:
            with np.load(disk) as data:
                hit = (data["surface"].copy(), int(data["state"][0]))
            if hit[0].shape != (TEX_H, TEX_W, 3):
                hit = None
        except Exception:
            hit = None
    if hit is not None:
        _MEM_SURFACES[key] = hit
        rng.state = hit[1]
        return hit[0]
    rgb = _apply_identity_tint(_surface_rgb(kind, rng, accent), palette)
    surface = (np.clip(rgb, 0, 1) * 255.0 + 0.5).astype(np.uint8)
    hit = (surface, int(rng.state))
    _MEM_SURFACES[key] = hit
    if disk is not None:
        _atomic_write(disk, lambda t: np.savez(open(t, "wb"), surface=surface, state=np.array([hit[1]], dtype=np.uint64)))
    return surface


def _texture_from_rgb(name: str, rgb: np.ndarray) -> Texture:
    tex = Texture(name)
    tex.setup2dTexture(TEX_W, TEX_H, Texture.T_unsigned_byte, Texture.F_rgb)
    if rgb.dtype == np.uint8:
        data = np.ascontiguousarray(np.flipud(rgb)[..., ::-1])           # Panda wants BGR, bottom row first
    else:
        data = (np.flipud(rgb)[..., ::-1] * 255.0 + 0.5).astype(np.uint8)
    tex.setRamImage(data.tobytes())
    tex.setWrapU(Texture.WM_repeat)
    tex.setWrapV(Texture.WM_clamp)
    tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
    tex.setMagfilter(SamplerState.FT_linear)
    tex.setAnisotropicDegree(4)
    return tex


# ----------------------------------------------------------------------
# meshes
# ----------------------------------------------------------------------
_FORMATS: dict = {}


def _float_format(with_uv: bool):
    """Vertex format with float32 position / colour (and uv), so numpy can fill it in one copy."""
    if with_uv in _FORMATS:
        return _FORMATS[with_uv]
    from panda3d.core import InternalName
    arr = GeomVertexArrayFormat()
    arr.addColumn(InternalName.getVertex(), 3, GeomEnums.NT_float32, GeomEnums.C_point)
    arr.addColumn(InternalName.getColor(), 4, GeomEnums.NT_float32, GeomEnums.C_color)
    if with_uv:
        arr.addColumn(InternalName.getTexcoord(), 2, GeomEnums.NT_float32, GeomEnums.C_texcoord)
    fmt = GeomVertexFormat.registerFormat(arr)
    _FORMATS[with_uv] = fmt
    return fmt


def _grid_indices(stacks: int, slices: int) -> np.ndarray:
    row = slices + 1
    i, j = np.meshgrid(np.arange(stacks), np.arange(slices), indexing="ij")
    a = i * row + j
    b, c, e = a + 1, (i + 1) * row + j + 1, (i + 1) * row + j
    return np.stack([a, e, c, a, c, b], axis=-1).reshape(-1).astype(np.uint32)


def _node_from_arrays(name: str, vertex_rows: np.ndarray, indices: np.ndarray, with_uv: bool) -> NodePath:
    """Pass 282.82: one bulk copy per array instead of a Python call per vertex (~10x faster)."""
    rows = np.ascontiguousarray(vertex_rows, dtype=np.float32)
    vdata = GeomVertexData(name, _float_format(with_uv), Geom.UHStatic)
    vdata.uncleanSetNumRows(rows.shape[0])
    memoryview(vdata.modifyArray(0)).cast("B")[:] = rows.tobytes()
    tris = GeomTriangles(Geom.UHStatic)
    tris.setIndexType(GeomEnums.NT_uint32)
    varr = tris.modifyVertices()
    varr.uncleanSetNumRows(int(indices.shape[0]))
    memoryview(varr).cast("B")[:] = np.ascontiguousarray(indices, dtype=np.uint32).tobytes()
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode(name)
    gn.addGeom(geom)
    return NodePath(gn)


def _sphere_normals(stacks: int, slices: int, lon_start: float):
    i = np.arange(stacks + 1, dtype=np.float64)[:, None]
    j = np.arange(slices + 1, dtype=np.float64)[None, :]
    lat = math.pi / 2 - math.pi * i / stacks
    lon = lon_start + math.tau * j / slices
    n = np.stack(np.broadcast_arrays(np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat) + 0 * lon), axis=-1)
    return n.reshape(-1, 3), np.broadcast_to(i, (stacks + 1, slices + 1)).reshape(-1), np.broadcast_to(j, (stacks + 1, slices + 1)).reshape(-1)


def _lit_sphere(name: str, radius: float, centre: Vec3, sun_dir: Vec3, stacks=40, slices=72, night=NIGHT):
    """UV sphere whose vertex colours carry the star lighting (the planet never
    moves relative to the star, so this is exact and costs nothing per frame)."""
    view = Vec3(-centre)
    view.normalize()
    n, i, j = _sphere_normals(stacks, slices, -math.pi)
    sun = np.array([sun_dir.x, sun_dir.y, sun_dir.z])
    vw = np.array([view.x, view.y, view.z])
    d = n @ sun
    light = night + (1.0 - night) * np.clip(d * 1.15 + 0.08, 0.0, 1.0) ** 0.9
    rim = np.maximum(0.0, 1.0 - np.maximum(0.0, n @ vw)) ** 3 * 0.25 * np.maximum(0.0, d + 0.3)
    col = np.minimum(1.0, light[:, None] * np.array(STAR_COLOR)[None, :] + rim[:, None])
    rows = np.concatenate([n * radius, col, np.ones((n.shape[0], 1)), (j / slices)[:, None], (1.0 - i / stacks)[:, None]], axis=1)
    return _node_from_arrays(name, rows, _grid_indices(stacks, slices), True)


def _atmosphere(name: str, radius: float, centre: Vec3, sun_dir: Vec3, rgb, strength: float, stacks=24, slices=48):
    """A slightly larger shell, brightest at the limb as seen from the ship."""
    view = Vec3(-centre)
    view.normalize()
    n, _i, _j = _sphere_normals(stacks, slices, 0.0)
    facing = np.maximum(0.0, n @ np.array([view.x, view.y, view.z]))
    limb = np.where(facing > 0.0, (1.0 - facing) ** 2.2, 0.0)
    lit = 0.25 + 0.75 * np.maximum(0.0, n @ np.array([sun_dir.x, sun_dir.y, sun_dir.z]) + 0.25)
    alpha = np.minimum(1.0, limb * lit * strength)
    col = np.broadcast_to(np.array(tuple(rgb)[:3], dtype=np.float64), (n.shape[0], 3))
    rows = np.concatenate([n * radius, col, alpha[:, None]], axis=1)
    np_ = _node_from_arrays(name, rows, _grid_indices(stacks, slices), False)
    np_.setTransparency(TransparencyAttrib.MAlpha)
    np_.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
    np_.setDepthWrite(False)
    np_.setTwoSided(True)
    return np_


def _ring(name: str, r0: float, r1: float, rgb, rng: _Rng, segs=128, bands=10):
    vdata = GeomVertexData(name, GeomVertexFormat.getV3c4(), Geom.UHStatic)
    vw, cw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)
    edges = [r0 + (r1 - r0) * k / bands for k in range(bands + 1)]
    alphas = [rng.uniform(0.10, 0.55) if rng.random() > 0.18 else 0.03 for _ in range(bands)]
    base = 0
    for b in range(bands):
        for k in range(segs + 1):
            a = math.tau * k / segs
            for r in (edges[b], edges[b + 1]):
                vw.addData3(math.cos(a) * r, math.sin(a) * r, 0.0)
                shade = 0.75 + 0.25 * math.sin(r * 0.0009 + b)
                cw.addData4(rgb[0] * shade, rgb[1] * shade, rgb[2] * shade, alphas[b])
        for k in range(segs):
            i0 = base + k * 2
            tris.addVertices(i0, i0 + 1, i0 + 3)
            tris.addVertices(i0, i0 + 3, i0 + 2)
        base += (segs + 1) * 2
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode(name)
    gn.addGeom(geom)
    np_ = NodePath(gn)
    np_.setTransparency(TransparencyAttrib.MAlpha)
    np_.setDepthWrite(False)
    np_.setTwoSided(True)
    return np_


def _placements(records, dyson: Vec3):
    giant = Vec3(-0.78, 0.42, -0.10)
    placed = []
    out = []
    # Pass 282.70: sizes are chosen first so the spacing can respect each planet's edge;
    # if the sky gets crowded the edge gap relaxes step by step instead of overlapping.
    sizes = []
    for rec in records:
        rng = _Rng(_seed(getattr(rec, "dimension_id", "")))
        sizes.append((rng, rng.uniform(PLANET_MIN_ANG_RADIUS_DEG, PLANET_MAX_ANG_RADIUS_DEG)))
    for rng, ang_r in sizes:
        best, best_score = None, -1e9
        for gap in (EDGE_GAP_DEG, EDGE_GAP_DEG * 0.7, EDGE_GAP_DEG * 0.45, 4.0):
            found = None
            for attempt in range(260):
                lon = rng.uniform(-180.0, 180.0)
                lat = rng.uniform(*ELEVATION_RANGE_DEG)
                d = _dir(lon, lat)
                clear = min([_angle_deg(d, p) - max(MIN_SEPARATION_DEG * 0.6, pr + ang_r + gap) for p, pr in placed] + [999.0])
                clear = min(clear, _angle_deg(d, dyson) - DYSON_CLEARANCE_DEG - ang_r,
                            _angle_deg(d, giant) - GIANT_CLEARANCE_DEG - ang_r)
                if clear >= 0.0:
                    found = d
                    break
                if clear > best_score:
                    best, best_score = d, clear
            if found is not None:
                best = found
                break
        placed.append((best, ang_r))
        out.append((best, rng, ang_r))
    return out



def plan_planets(records, dyson: Vec3) -> list:
    """(record, direction, rng, angular radius, world kind) for every planet, in build order.

    Shared by the scene build and the background cache warm-up so both draw identical planets."""
    # Every planet gets a different world type (stable order from the record ids).
    order = list(ARCHETYPES)
    shuffle = _Rng(_seed("|".join(str(getattr(r, "dimension_id", "")) for r in records)))
    for i in range(len(order) - 1, 0, -1):
        j = int(shuffle.random() * (i + 1)) % (i + 1)
        order[i], order[j] = order[j], order[i]
    used: dict[str, int] = {}
    kinds = []
    for rec in records:                       # the dimension's own world type first
        k = kind_for_record(rec)
        if k and used.get(k, 0) >= 2:         # keep the sky varied: at most two of a type by keyword
            k = None
        kinds.append(k)
        if k:
            used[k] = used.get(k, 0) + 1
    spare = sorted(order, key=lambda k: (used.get(k, 0), order.index(k)))
    for i, k in enumerate(kinds):
        if not k:
            kinds[i] = spare[i % len(spare)]
    return [(rec, direction, rng, ang_r, kinds[idx]) for idx, ((direction, rng, ang_r), rec) in enumerate(zip(_placements(records, dyson), records))]


def _prepare_planet_data(records, dyson: Vec3) -> int:
    """Background warm-up: icon colours and surface textures into the caches (no scene graph)."""
    done = 0
    for rec, _direction, rng, _ang_r, kind in plan_planets(records, dyson):
        rng.uniform(PLANET_MIN_DISTANCE, PLANET_MAX_DISTANCE)          # the distance draw in _build_one
        palette = icon_palette(getattr(rec, "preview", None))
        accent = tuple(palette[0]) if palette else tuple(getattr(rec, "accent", (0.3, 0.9, 1.0)))[:3]
        surface_bytes(kind, rng, accent, palette)
        done += 1
    return done


_WARM_THREAD = None


def warm_planet_cache(records, dyson) -> bool:
    """Start preparing the planet textures in a background thread (once at a time)."""
    global _WARM_THREAD
    if _WARM_THREAD is not None and _WARM_THREAD.is_alive():
        return False
    recs = list(records)
    dyson_vec = Vec3(dyson)

    def run():
        import time as _t
        started = _t.monotonic()
        try:
            n = _prepare_planet_data(recs, dyson_vec)
            print(f"dimension_planets_cache_ready count={n} seconds={_t.monotonic() - started:.2f}")
        except Exception as exc:
            print(f"dimension_planets_cache_warm_failed err={exc.__class__.__name__}:{exc}")

    _WARM_THREAD = threading.Thread(target=run, name="holospace-planet-warmup", daemon=True)
    _WARM_THREAD.start()
    return True


def records_for_app(app):
    registry = getattr(app, "dimension_registry", None)
    # Pass 282.75: every linked dimension is a planet, including the ones a guide bot
    # hosts in the world (The Indigo Giant, Mirror's Limbo, Afterlife of IO, ...), which
    # the archive list keeps out of ``records``.
    pool = list(getattr(registry, "records", []) or []) + list(getattr(registry, "hosted_records", []) or [])
    records, seen = [], set()
    for r in pool:
        key = str(getattr(r, "dimension_id", ""))
        if str(getattr(r, "origin", "")) != "linked" or not key or key in seen:
            continue
        seen.add(key)
        records.append(r)
    records.sort(key=lambda r: str(getattr(r, "dimension_id", "")))
    return records


def warm_for_app(app) -> bool:
    """Called from the hub: prepare HoloSpace's planet textures before the player warps."""
    try:
        from holoverse.deep_space import DYSON_DIRECTION
        dyson = Vec3(DYSON_DIRECTION)
        dyson.normalize()
        records = records_for_app(app)
        if not records:
            return False
        return warm_planet_cache(records, dyson)
    except Exception as exc:
        print(f"dimension_planets_cache_warm_skipped err={exc.__class__.__name__}:{exc}")
        return False


# ----------------------------------------------------------------------
# the planet field
# ----------------------------------------------------------------------
class DimensionPlanets:
    def __init__(self, app, flight):
        self.app = app
        self.flight = flight            # holoverse.deep_space.DeepSpaceFlight
        self.root = None
        self.planets: list[dict] = []
        self._signature = ()
        self.hover = None
        self.prompt_open = False
        self.prompt_planet = None
        self._label = None
        self._prompt_root = None
        self._launch_pending = None

    # ---- records -------------------------------------------------------
    def _records(self):
        return records_for_app(self.app)

    def sync(self, force: bool = False) -> None:
        records = self._records()
        sig = tuple((str(getattr(r, "dimension_id", "")), str(getattr(r, "title", "")), bool(getattr(r, "launchable", False))) for r in records)
        if not force and sig == self._signature and self.root is not None:
            return
        self._signature = sig
        self._build(records)

    # ---- layout ----------------------------------------------------------
    def _placements(self, records):
        return _placements(records, Vec3(self.flight.dyson_dir))

    # ---- build -------------------------------------------------------------
    def _build(self, records) -> None:
        if self.root is not None and not self.root.isEmpty():
            self.root.removeNode()
        self.planets = []
        scene = getattr(self.flight, "sky_scene", None)
        if scene is None:
            return
        self.root = scene.attachNewNode("dimension-planets")
        self.root.setLightOff(1)
        self.root.setFogOff(1)
        self.root.setShaderOff(10)
        self.root.setBin("background", 4)
        star_pos = Vec3(self.flight.dyson_dir) * 60000.0
        for rec, direction, rng, ang_r, kind in plan_planets(records, Vec3(self.flight.dyson_dir)):
            try:
                self.planets.append(self._build_one(rec, direction, rng, star_pos, kind, ang_r))
            except Exception as exc:
                print(f"dimension_planet_build_failed id={getattr(rec, 'dimension_id', '?')} err={exc.__class__.__name__}:{exc}")
        print(f"dimension_planets_built count={len(self.planets)}")

    def _build_one(self, rec, direction: Vec3, rng: _Rng, star_pos: Vec3, kind: str, ang_r_deg: float | None = None) -> dict:
        dist = rng.uniform(PLANET_MIN_DISTANCE, PLANET_MAX_DISTANCE)
        if ang_r_deg is None:
            ang_r_deg = rng.uniform(PLANET_MIN_ANG_RADIUS_DEG, PLANET_MAX_ANG_RADIUS_DEG)
        ang_r = math.radians(ang_r_deg)
        radius = dist * math.tan(ang_r)
        centre = Vec3(direction) * dist
        sun_dir = star_pos - centre
        sun_dir.normalize()
        palette = icon_palette(getattr(rec, "preview", None))
        accent = tuple(palette[0]) if palette else tuple(getattr(rec, "accent", (0.3, 0.9, 1.0)))[:3]
        holder = self.root.attachNewNode(f"dimension-planet-{getattr(rec, 'dimension_id', 'x')}")
        holder.setPos(centre)
        # surface
        body = _lit_sphere("dimension-planet-body", radius, centre, sun_dir)
        body.reparentTo(holder)
        surface = surface_bytes(kind, rng, accent, palette)
        tex = _texture_from_rgb(f"dimension-planet-tex-{kind}", surface)
        stage = TextureStage("dimension-planet-surface")
        stage.setMode(TextureStage.M_modulate)
        body.setTexture(stage, tex)
        body.setTwoSided(False)
        # atmosphere (none for the airless crystal world)
        atmo_rgb = {
            "gas": (1.0, 0.80, 0.60), "ocean": (0.45, 0.70, 1.0), "ice": (0.70, 0.88, 1.0),
            "lava": (1.0, 0.45, 0.20), "crystal": accent, "toxic": (0.70, 1.0, 0.35),
        }[kind]
        atmo = _atmosphere("dimension-planet-atmosphere", radius * (1.06 if kind != "gas" else 1.04), centre, sun_dir, atmo_rgb,
                           0.55 if kind != "crystal" else 0.30)
        atmo.reparentTo(holder)
        # rings and moons
        ring = None
        if kind in ("gas", "ice", "crystal") and rng.random() < 0.70 or rng.random() < 0.15:
            ring_rgb = {"gas": (0.85, 0.74, 0.58), "ice": (0.80, 0.88, 0.96), "crystal": accent}.get(kind, (0.7, 0.7, 0.7))
            ring = _ring("dimension-planet-ring", radius * 1.45, radius * rng.uniform(2.0, 2.5), ring_rgb, rng)
            ring.reparentTo(holder)
            ring.setHpr(rng.uniform(0, 360), rng.uniform(55, 80), rng.uniform(-20, 20))
        moon = None   # Pass 282.70: no small orbs beside the planets; each dimension is one world
        return {
            "record": rec, "holder": holder, "body": body, "atmo": atmo, "ring": ring, "moon": moon,
            "dir": Vec3(direction), "ang_radius_deg": math.degrees(ang_r), "kind": kind,
            "stage": stage, "spin": rng.uniform(0.004, 0.012) * (1 if rng.random() > 0.3 else -1), "u": 0.0,
        }

    # ---- per frame ----------------------------------------------------------
    def update(self, dt: float) -> None:
        if not self.planets:
            return
        for p in self.planets:
            p["u"] = (p["u"] + p["spin"] * dt) % 1.0
            p["body"].setTexOffset(p["stage"], p["u"], 0.0)
        if self.prompt_open:
            return
        self.hover = self.aimed_planet()
        self._show_hover(self.hover)

    def aimed_planet(self):
        cam = getattr(self.flight, "sky_cam", None)
        if cam is None or cam.isEmpty():
            return None
        fwd = cam.getQuat(self.flight.sky_scene).getForward()
        best, best_err = None, 1e9
        for p in self.planets:
            ang = _angle_deg(fwd, p["dir"])
            limit = max(AIM_MIN_DEG, p["ang_radius_deg"] * AIM_SLACK)
            if ang <= limit and ang / limit < best_err:
                best, best_err = p, ang / limit
        return best

    # ---- UI ------------------------------------------------------------------
    def _font_kw(self):
        try:
            return self.app._core_text_kw()
        except Exception:
            return {}

    def _show_hover(self, planet) -> None:
        from direct.gui.DirectGui import DirectLabel

        if self._label is None:
            self._label = DirectLabel(parent=self.app.aspect2d, text="", text_align=TextNode.ACenter, text_scale=0.030,
                                      text_fg=(0.94, 0.97, 1.0, 1.0), text_shadow=(0, 0, 0, 0.8), frameColor=(0, 0, 0, 0),
                                      pos=(0, 0, -0.235), textMayChange=True, **self._font_kw())
        if planet is None:
            self._label.hide()
            return
        title = str(getattr(planet["record"], "title", "DIMENSION")).upper()
        sub = "LEFT-CLICK TO ENTER" if bool(getattr(planet["record"], "launchable", False)) else "SIGNAL UNAVAILABLE"
        self._label["text"] = f"{title}\n{sub}"
        self._label.show()

    def click(self) -> bool:
        """Left-click in HoloSpace.  True when a planet consumed the click."""
        if self.prompt_open:
            return True
        planet = self.aimed_planet()
        if planet is None:
            return False
        self.open_prompt(planet)
        return True

    def open_prompt(self, planet) -> None:
        from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel

        self.prompt_open = True
        self.prompt_planet = planet
        app = self.app
        if self._label is not None:
            self._label.hide()
        if self._prompt_root is not None:
            self._prompt_root.removeNode()
        root = app.aspect2d.attachNewNode("dimension-planet-prompt")
        root.setBin("fixed", 300)          # above the flight HUD
        root.setDepthTest(False)
        root.setDepthWrite(False)
        for name in ("hud", "throttle_root"):
            node = getattr(self.flight, name, None)
            if node is not None:
                node.hide()                # the reticle and gauges would draw through the prompt
        self._prompt_root = root
        rec = planet["record"]
        launchable = bool(getattr(rec, "launchable", False))
        kw = self._font_kw()
        ink, dim, amber = (0.94, 0.97, 1.0, 1.0), (0.62, 0.76, 0.84, 0.96), (1.0, 0.76, 0.36, 1.0)
        DirectFrame(parent=root, frameColor=(0.0, 0.004, 0.008, 0.45), frameSize=(-3.0, 3.0, -1.2, 1.2))
        DirectFrame(parent=root, frameColor=(0.016, 0.028, 0.040, 0.94), frameSize=(-0.62, 0.62, -0.25, 0.27))
        DirectFrame(parent=root, frameColor=(0.40, 0.90, 1.0, 0.85), frameSize=(-0.62, 0.62, 0.155, 0.159))
        DirectLabel(parent=root, text="DIMENSION SIGNAL", text_scale=0.022, text_fg=(0.40, 0.90, 1.0, 1.0), frameColor=(0, 0, 0, 0), pos=(0, 0, 0.195), **kw)
        DirectLabel(parent=root, text=str(getattr(rec, "title", "Dimension")), text_scale=0.050, text_fg=amber, frameColor=(0, 0, 0, 0), pos=(0, 0, 0.065), **kw)
        question = "Enter this dimension?" if launchable else "This dimension's files are not linked yet."
        DirectLabel(parent=root, text=question, text_scale=0.028, text_fg=ink, frameColor=(0, 0, 0, 0), pos=(0, 0, -0.025), **kw)
        DirectLabel(parent=root, text="You will leave HoloSpace. TAB inside the dimension returns to MatrixCore.", text_scale=0.019,
                    text_fg=dim, frameColor=(0, 0, 0, 0), pos=(0, 0, -0.080), text_wordwrap=40, **kw)
        enter = DirectButton(parent=root, text="ENTER", command=self._prompt_enter, pos=(-0.20, 0, -0.175), scale=0.05,
                             frameSize=(-3.0, 3.0, -0.6, 0.8), text_scale=0.56, text_pos=(0, -0.13), relief=1,
                             rolloverSound=None, clickSound=None, **kw)
        stay = DirectButton(parent=root, text="STAY (ESC)", command=self.close_prompt, pos=(0.20, 0, -0.175), scale=0.05,
                            frameSize=(-3.0, 3.0, -0.6, 0.8), text_scale=0.56, text_pos=(0, -0.13), relief=1,
                            rolloverSound=None, clickSound=None, **kw)
        style = getattr(app, "apply_core_button_style", None)
        if callable(style):
            style(enter, role="yellow", available=launchable)
            style(stay, role="white", available=True)
        if not launchable:
            enter["state"] = "disabled"
        app.mouse_captured = False
        try:
            app.core_console_set_cursor(True)
        except Exception:
            pass
        try:
            app.crosshair_root.hide()
        except Exception:
            pass
        print(f"dimension_planet_prompt id={getattr(rec, 'dimension_id', '?')} title={getattr(rec, 'title', '?')!r}")

    def close_prompt(self) -> None:
        self.prompt_open = False
        self.prompt_planet = None
        if self._prompt_root is not None:
            self._prompt_root.removeNode()
            self._prompt_root = None
        app = self.app
        if getattr(self.flight, "active", False):
            for name in ("hud", "throttle_root"):
                node = getattr(self.flight, name, None)
                if node is not None:
                    node.show()
        try:
            app.crosshair_root.show()
        except Exception:
            pass
        capture = getattr(app, "capture_gameplay_mouse", None)
        if callable(capture):
            capture()
        app.mouse_look_resume_at = __import__("time").monotonic() + 0.15   # swallow the jump from the cursor

    def _prompt_enter(self) -> None:
        planet = self.prompt_planet
        if planet is None:
            return
        rec = planet["record"]
        self.close_prompt()
        app = self.app
        registry = getattr(app, "dimension_registry", None)
        if registry is None:
            return
        print(f"dimension_planet_enter id={getattr(rec, 'dimension_id', '?')} title={getattr(rec, 'title', '?')!r}")
        try:
            # Pass 282.75: entering a planet unlocks that reality in Gleebs' archive list (saved).
            unlock = getattr(registry, "unlock_from_planet", None)
            if callable(unlock):
                unlock(rec)
            else:
                registry._mark_seen(rec)
        except Exception:
            pass
        # Leave HoloSpace through the normal home exit, then open the dimension
        # once deep space has shut down (next frames).
        try:
            app.handle_tab_action()
        except Exception as exc:
            print(f"dimension_planet_exit_warning:{exc.__class__.__name__}:{exc}")
        try:
            if self.flight.active:
                self.flight.deactivate()
        except Exception:
            pass

        def _launch(task):
            try:
                registry._launch(rec)
            except Exception as exc:
                print(f"dimension_planet_launch_failed id={getattr(rec, 'dimension_id', '?')} err={exc.__class__.__name__}:{exc}")
            return task.done

        app.taskMgr.doMethodLater(0.12, _launch, "dimension-planet-launch")

    def hide_ui(self) -> None:
        if self._label is not None:
            self._label.hide()
        if self.prompt_open:
            self.close_prompt()

    def report(self) -> dict:
        return {"planets": len(self.planets), "kinds": [p["kind"] for p in self.planets], "prompt_open": self.prompt_open}


__all__ = ["DimensionPlanets"]
