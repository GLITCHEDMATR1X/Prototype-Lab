"""Infinite deterministic surface terrain for Entropy Pass 22.

The generator is intentionally engine-agnostic: terrain samples and chunk object
placements are pure functions of the planet seed, biome, and absolute world
coordinates.  Adjacent chunks therefore share the same noise field without seam
padding, while the pygame renderer can cache only the chunks currently needed.
"""
from __future__ import annotations

import colorsys
import math
from functools import lru_cache
from dataclasses import dataclass
from typing import Mapping

CHUNK_WORLD_SIZE = 64
CHUNK_CACHE_LIMIT = 42
OBJECT_CACHE_LIMIT = 72
TERRAIN_TEXELS_PER_UNIT = 4
CHUNK_SAMPLE_RESOLUTION = 48


@dataclass(frozen=True)
class GeologySample:
    height: float
    macro: float
    ridge: float
    basin: float
    fracture: float
    strata: float
    material: float
    deposit: float


def clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def smoothstep(value: float) -> float:
    value = clamp(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def _mix32(value: int) -> int:
    value &= 0xFFFFFFFF
    value ^= value >> 16
    value = (value * 0x7FEB352D) & 0xFFFFFFFF
    value ^= value >> 15
    value = (value * 0x846CA68B) & 0xFFFFFFFF
    value ^= value >> 16
    return value & 0xFFFFFFFF


def stable_hash(seed: int, x: int, y: int, salt: int = 0) -> int:
    """Return a stable unsigned hash for signed grid coordinates."""
    value = (int(seed) & 0xFFFFFFFF) ^ ((int(x) * 0x1F123BB5) & 0xFFFFFFFF)
    value ^= ((int(y) * 0x5F356495) & 0xFFFFFFFF)
    value ^= (int(salt) * 0x9E3779B1) & 0xFFFFFFFF
    return _mix32(value)


def hash01(seed: int, x: int, y: int, salt: int = 0) -> float:
    return stable_hash(seed, x, y, salt) / 4294967295.0


def _value_noise(seed: int, x: float, y: float, scale: float, salt: int) -> float:
    gx = x / scale
    gy = y / scale
    x0 = math.floor(gx)
    y0 = math.floor(gy)
    tx = smoothstep(gx - x0)
    ty = smoothstep(gy - y0)
    a = hash01(seed, x0, y0, salt)
    b = hash01(seed, x0 + 1, y0, salt)
    c = hash01(seed, x0, y0 + 1, salt)
    d = hash01(seed, x0 + 1, y0 + 1, salt)
    ab = a + (b - a) * tx
    cd = c + (d - c) * tx
    return ab + (cd - ab) * ty


def _fbm(seed: int, x: float, y: float, salt: int = 0) -> float:
    value = 0.0
    weight = 0.0
    for scale, amp, octave in ((192.0, 0.43, 0), (96.0, 0.27, 1), (48.0, 0.17, 2), (24.0, 0.09, 3), (12.0, 0.04, 4)):
        value += _value_noise(seed, x, y, scale, salt + octave * 37) * amp
        weight += amp
    return value / max(1e-9, weight)


def _cellular(seed: int, x: float, y: float, cell_size: float = 104.0, salt: int = 0) -> tuple[float, float, float]:
    """Return nearest/second-nearest cell distance and cell material value."""
    gx = math.floor(x / cell_size)
    gy = math.floor(y / cell_size)
    nearest = 1e9
    second = 1e9
    material = 0.5
    for cy in range(gy - 1, gy + 2):
        for cx in range(gx - 1, gx + 2):
            ox = 0.16 + hash01(seed, cx, cy, salt + 1) * 0.68
            oy = 0.16 + hash01(seed, cx, cy, salt + 2) * 0.68
            px = (cx + ox) * cell_size
            py = (cy + oy) * cell_size
            distance = math.hypot(x - px, y - py) / cell_size
            if distance < nearest:
                second = nearest
                nearest = distance
                material = hash01(seed, cx, cy, salt + 3)
            elif distance < second:
                second = distance
    return nearest, second, material


def _phase(seed: int, salt: int) -> float:
    return hash01(seed, salt * 17, salt * -29, salt + 911) * math.tau


@lru_cache(maxsize=64)
def _wave_params(seed: int) -> tuple[float, ...]:
    return tuple(_phase(int(seed), i) for i in range(18))


def sample_geology(seed: int, terrain: str, x: float, y: float) -> GeologySample:
    """Sample a continuous geological field at an absolute world coordinate.

    Pass 22 uses a compact spectral field rather than allocating a planet-sized
    noise image.  The waves are evaluated in absolute coordinates, so crossing
    a chunk edge does not reset phases or introduce a seam.
    """
    p = _wave_params(int(seed))
    macro = clamp(
        0.50
        + math.sin(x * 0.011 + y * 0.004 + p[0]) * 0.20
        + math.cos(x * 0.004 - y * 0.010 + p[1]) * 0.15
        + math.sin(x * 0.022 + y * 0.017 + p[2]) * 0.09
        + math.cos(x * 0.039 - y * 0.026 + p[3]) * 0.045,
        0.0, 1.0,
    )
    warp = (
        math.sin(x * 0.008 + y * 0.006 + p[4]) * 21.0
        + math.cos(x * 0.015 - y * 0.009 + p[5]) * 11.0
    )
    folded = clamp(
        0.50
        + math.sin((x + warp) * 0.018 - y * 0.006 + p[6]) * 0.24
        + math.cos(x * 0.009 + (y - warp) * 0.021 + p[7]) * 0.17
        + math.sin(x * 0.047 + y * 0.035 + p[8]) * 0.07,
        0.0, 1.0,
    )
    ridge = (1.0 - abs(2.0 * folded - 1.0)) ** (2.8 if terrain in {"ice", "crystal", "roseglass"} else 2.0)

    # Jittered cellular plates make basins and faults irregular instead of
    # forming a repeating square/diagonal wave grid.
    near, second, cell_material = _cellular(seed, x + warp * 0.18, y - warp * 0.14, 118.0, 503)
    broad_material = 0.5 + 0.5 * math.sin(x * 0.008 + y * 0.005 + p[9])
    material = clamp(cell_material * 0.74 + broad_material * 0.26, 0.0, 1.0)
    basin = smoothstep((0.52 - near) / 0.34)

    cell_edge = abs(second - near)
    cellular_fault = smoothstep((0.095 - cell_edge) / 0.075)
    branch_wave = abs(math.sin((x + warp) * 0.043 + y * 0.021 + p[13]))
    branch_fault = smoothstep((0.075 - branch_wave) / 0.060)
    fracture = clamp(cellular_fault * 0.82 + branch_fault * 0.28, 0.0, 1.0)

    strata_axis = x * (0.040 + 0.008 * math.sin(p[10])) + y * (0.022 + 0.006 * math.cos(p[11]))
    strata = 0.5 + 0.5 * math.sin(strata_axis + warp * 0.095 + p[15])
    pocket_a = 0.5 + 0.5 * math.sin(x * 0.027 - y * 0.035 + p[16] + warp * 0.045)
    pocket_b = 0.5 + 0.5 * math.cos(x * 0.044 + y * 0.024 + p[17] - warp * 0.038)
    pocket = pocket_a * pocket_b * smoothstep((material - 0.28) / 0.62)
    deposit = smoothstep((pocket - 0.72) / 0.20) * smoothstep((fracture - 0.10) / 0.68)

    base = macro * 0.48 + ridge * 0.37 + (material - 0.5) * 0.10 - basin * 0.08
    if terrain == "desert":
        dunes = math.sin((x + warp * 0.6) * 0.055 + y * 0.013) * 0.065
        height = base * 0.82 + dunes + strata * 0.05
    elif terrain == "ice":
        height = macro * 0.34 + ridge * 0.56 + fracture * 0.08 - basin * 0.05
    elif terrain == "jungle":
        height = macro * 0.52 + ridge * 0.27 + basin * 0.12 + material * 0.08
    elif terrain == "volcanic":
        caldera = basin * smoothstep((material - 0.44) / 0.32)
        height = macro * 0.31 + ridge * 0.51 + fracture * 0.16 - caldera * 0.23
    elif terrain == "crystal":
        height = macro * 0.27 + ridge * 0.62 + fracture * 0.12 + deposit * 0.10
    elif terrain == "oceanic":
        shelves = round((macro * 0.58 + ridge * 0.24) * 7.0) / 7.0
        height = shelves * 0.76 + basin * 0.08 - 0.10
    elif terrain == "fungal":
        mounds = smoothstep((0.50 - near) / 0.32)
        height = macro * 0.42 + ridge * 0.20 + mounds * 0.25 + strata * 0.05
    elif terrain == "rust":
        raw = macro * 0.38 + ridge * 0.43 + fracture * 0.08 + strata * 0.06
        height = round(raw * 10.0) / 10.0
    elif terrain == "salt":
        islands = smoothstep((material - 0.76) / 0.20) * basin
        height = 0.31 + (macro - 0.5) * 0.12 + islands * 0.40 + fracture * 0.035
    elif terrain == "abyss":
        height = macro * 0.20 + ridge ** 1.55 * 0.68 + fracture * 0.10 - basin * 0.20
    elif terrain == "storm":
        raw = macro * 0.35 + ridge * 0.43 + material * 0.12 + 0.06
        height = round(raw * 7.0) / 7.0
    elif terrain == "roseglass":
        height = macro * 0.20 + ridge ** 1.25 * 0.68 + fracture * 0.14 + deposit * 0.12
    else:
        height = base

    # Fine erosion is added after biome shaping so terraced worlds keep their
    # broad shelves while gaining chipped edges, granular slopes, and shallow
    # drainage scars.  It is continuous in absolute coordinates and therefore
    # cannot reveal chunk boundaries while the player explores.
    detail = (_value_noise(seed, x, y, 9.0, 1701) - 0.5) * 2.0
    grain = (_value_noise(seed, x, y, 4.5, 1733) - 0.5) * 2.0
    channel_field = 1.0 - abs(2.0 * _value_noise(seed, x + warp * 0.11, y - warp * 0.09, 18.0, 1777) - 1.0)
    channel = smoothstep((channel_field - 0.78) / 0.18)
    roughness = {
        "desert": 0.018, "ice": 0.016, "jungle": 0.024, "volcanic": 0.029,
        "crystal": 0.022, "oceanic": 0.011, "fungal": 0.023, "rust": 0.026,
        "salt": 0.010, "abyss": 0.030, "storm": 0.027, "roseglass": 0.024,
    }.get(terrain, 0.020)
    height += detail * roughness + grain * roughness * 0.38 - channel * roughness * 0.42

    return GeologySample(
        height=clamp(height, 0.0, 1.0),
        macro=macro,
        ridge=ridge,
        basin=basin,
        fracture=fracture,
        strata=strata,
        material=material,
        deposit=deposit,
    )


def _hsv(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s, 0.0, 1.0), clamp(v, 0.0, 1.0))
    return int(r * 255), int(g * 255), int(b * 255)


def terrain_rgb(biome: Mapping[str, object], sample: GeologySample, relief: float = 1.0, contour: float = 1.0) -> tuple[int, int, int]:
    """Convert geology to a restrained, locally varied filmic terrain color."""
    terrain = str(biome.get("terrain", "desert"))
    base_hue = float(biome.get("base_hue", 0.1))
    accent_hue = float(biome.get("accent_hue", base_hue + 0.08))

    # Large material cells choose nearby rock families.  Strata primarily alter
    # value and roughness instead of painting simple full-width color streaks.
    local_hue = base_hue + (sample.material - 0.5) * 0.055 + (sample.macro - 0.5) * 0.025
    saturation = 0.48 + sample.ridge * 0.18
    value = 0.34 + sample.height * 0.45 + (sample.strata - 0.5) * 0.055

    if terrain == "desert":
        local_hue = 0.075 + (sample.material - 0.5) * 0.035
        saturation = 0.48 + sample.strata * 0.16
        value = 0.48 + sample.height * 0.32
    elif terrain == "ice":
        local_hue = 0.56 + (sample.material - 0.5) * 0.055
        saturation = 0.18 + sample.fracture * 0.22
        value = 0.58 + sample.height * 0.29
    elif terrain == "jungle":
        local_hue = 0.30 + (sample.material - 0.5) * 0.055
        saturation = 0.56 + sample.basin * 0.18
        value = 0.31 + sample.height * 0.36
    elif terrain == "volcanic":
        local_hue = 0.018 + (sample.material - 0.5) * 0.025
        saturation = 0.36 + sample.fracture * 0.32
        value = 0.20 + sample.height * 0.31
    elif terrain == "crystal":
        local_hue = 0.69 + (sample.material - 0.5) * 0.09
        saturation = 0.30 + sample.deposit * 0.35
        value = 0.44 + sample.height * 0.34
    elif terrain == "oceanic":
        local_hue = 0.53 + (sample.material - 0.5) * 0.045
        saturation = 0.46 + sample.basin * 0.16
        value = 0.30 + sample.height * 0.31
    elif terrain == "fungal":
        local_hue = 0.82 + (sample.material - 0.5) * 0.13
        saturation = 0.50 + sample.basin * 0.24
        value = 0.27 + sample.height * 0.37
    elif terrain == "rust":
        local_hue = 0.045 + (sample.material - 0.5) * 0.035
        saturation = 0.57 + sample.strata * 0.18
        value = 0.25 + sample.height * 0.37
    elif terrain == "salt":
        local_hue = 0.66 + (sample.material - 0.5) * 0.035
        saturation = 0.07 + sample.fracture * 0.14
        value = 0.66 + sample.height * 0.21
    elif terrain == "abyss":
        local_hue = 0.55 + (sample.material - 0.5) * 0.08
        saturation = 0.58 + sample.fracture * 0.24
        value = 0.13 + sample.height * 0.42
    elif terrain == "storm":
        local_hue = 0.60 + (sample.material - 0.5) * 0.04
        saturation = 0.22 + sample.fracture * 0.18
        value = 0.31 + sample.height * 0.33
    elif terrain == "roseglass":
        local_hue = 0.92 + (sample.material - 0.5) * 0.10
        saturation = 0.43 + sample.deposit * 0.28
        value = 0.29 + sample.height * 0.39

    # Mineral color is localized to deposits and fracture intersections rather
    # than laid across the terrain as long decorative streaks.
    accent_mix = clamp(sample.deposit * 0.62 + max(0.0, sample.fracture - 0.96) * 0.08, 0.0, 0.58)
    br, bg, bb = _hsv(local_hue, saturation, value)
    ar, ag, ab = _hsv(accent_hue, min(0.88, saturation + 0.18), min(1.0, value + 0.22))
    r = br + (ar - br) * accent_mix
    g = bg + (ag - bg) * accent_mix
    b = bb + (ab - bb) * accent_mix
    film = relief * contour
    return (
        int(clamp((r - 18.0) * 0.78 * film + 9.0, 0.0, 232.0)),
        int(clamp((g - 18.0) * 0.78 * film + 11.0, 0.0, 232.0)),
        int(clamp((b - 18.0) * 0.78 * film + 15.0, 0.0, 232.0)),
    )


def build_chunk_pixels(
    seed: int,
    biome: Mapping[str, object],
    chunk_x: int,
    chunk_y: int,
    size: int = CHUNK_WORLD_SIZE,
    resolution: int = CHUNK_SAMPLE_RESOLUTION,
) -> list[list[tuple[int, int, int]]]:
    """Build a compact relief tile sampled in absolute world coordinates."""
    resolution = max(8, int(resolution))
    step = float(size) / float(resolution)
    origin_x = int(chunk_x) * size
    origin_y = int(chunk_y) * size
    samples: list[list[GeologySample]] = []
    for py in range(-1, resolution + 1):
        row = []
        wy = origin_y + py * step
        for px in range(-1, resolution + 1):
            row.append(sample_geology(seed, str(biome.get("terrain", "desert")), origin_x + px * step, wy))
        samples.append(row)

    light_x, light_y = -0.72, -0.42
    pixels: list[list[tuple[int, int, int]]] = []
    for py in range(resolution):
        row = []
        for px in range(resolution):
            center = samples[py + 1][px + 1]
            dx = samples[py + 1][px + 2].height - samples[py + 1][px].height
            dy = samples[py + 2][px + 1].height - samples[py][px + 1].height
            relief = clamp(1.03 - (dx * light_x + dy * light_y) * 2.25, 0.62, 1.38)
            band = int(center.height * 9.0)
            neighbor_band = int(samples[py + 1][px].height * 9.0)
            contour = 0.94 if band != neighbor_band else 1.0
            row.append(terrain_rgb(biome, center, relief, contour))
        pixels.append(row)
    return pixels


def _object_counts(terrain: str, prop_density: int) -> tuple[int, int, int]:
    tree_mult = {
        "desert": 0.0, "volcanic": 0.0, "jungle": 1.0, "ice": 0.52, "crystal": 0.38,
        "oceanic": 0.45, "fungal": 0.75, "rust": 0.10, "salt": 0.01, "abyss": 0.08,
        "storm": 0.16, "roseglass": 0.06,
    }.get(terrain, 0.35)
    plant_mult = {
        "volcanic": 0.22, "jungle": 0.90, "desert": 0.48, "ice": 0.45, "crystal": 0.64,
        "oceanic": 0.68, "fungal": 1.0, "rust": 0.28, "salt": 0.14, "abyss": 0.74,
        "storm": 0.30, "roseglass": 0.50,
    }.get(terrain, 0.45)
    return int(round(7 * tree_mult)), int(round(13 * plant_mult)), max(1, int(round(prop_density / 28.0)))


def generate_chunk_objects(seed: int, biome: Mapping[str, object], chunk_x: int, chunk_y: int, size: int = CHUNK_WORLD_SIZE) -> dict[str, tuple[dict, ...]]:
    """Generate stable recoverable exploration objects for one terrain chunk."""
    terrain = str(biome.get("terrain", "desert"))
    tree_count, plant_count, prop_count = _object_counts(terrain, int(biome.get("prop_density", 48)))
    counts = (("tree", tree_count, 1101), ("plant", plant_count, 1201), ("prop", prop_count, 1301))
    origin_x = int(chunk_x) * size
    origin_y = int(chunk_y) * size
    result: dict[str, list[dict]] = {"trees": [], "plants": [], "props": []}
    target_key = {"tree": "trees", "plant": "plants", "prop": "props"}
    for category, count, salt in counts:
        for index in range(count):
            hx = stable_hash(seed, chunk_x, chunk_y, salt + index * 11)
            hy = stable_hash(seed, chunk_x, chunk_y, salt + index * 11 + 1)
            x = origin_x + 3.0 + (hx / 4294967295.0) * (size - 6.0)
            y = origin_y + 3.0 + (hy / 4294967295.0) * (size - 6.0)
            geology = sample_geology(seed, terrain, x, y)
            # Keep objects out of the harshest voids and needle ridges while
            # preserving a varied distribution on every explored chunk.
            if geology.height < 0.10 or geology.height > 0.94:
                x = origin_x + size * (0.30 + 0.40 * hash01(seed, chunk_x, chunk_y, salt + index * 17 + 5))
                y = origin_y + size * (0.30 + 0.40 * hash01(seed, chunk_x, chunk_y, salt + index * 17 + 6))
            item_seed = stable_hash(seed ^ 0xA5A5A5A5, chunk_x, chunk_y, salt + index * 97)
            result[target_key[category]].append({
                "x": float(x),
                "y": float(y),
                "seed": int(item_seed),
                "kind": "surface object" if category == "prop" else category,
                "procedural": True,
                "chunk": (int(chunk_x), int(chunk_y)),
            })
    return {key: tuple(value) for key, value in result.items()}
