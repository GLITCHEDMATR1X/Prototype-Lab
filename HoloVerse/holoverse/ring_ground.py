"""Shaded, level-of-detail ground for the HoloVerse biome rings (Pass 282.51).

One call builds the ground sheet for one ring sector:

* heights come from ``terrain_field.ring_height_grid``, which matches the
  scalar ``world_height_at`` the player walks on, so the visible ground and
  the walk height agree at every vertex;
* the grid density follows a distance tier (near / mid / far) so the sector
  under the player is fine-grained and far sectors stay cheap;
* every vertex carries a normal and a palette colour (height, slope and broad
  patch variation per biome);
* a small GLSL program adds lighting, per-biome surface detail, a faint
  holographic grid near the player, and the scene's linear fog.  When GLSL is
  unavailable the lighting is baked into the vertex colours instead.

Sector edges get short skirts so neighbouring sectors at different detail
levels never show cracks.
"""
from __future__ import annotations

import math
import os

import numpy as np
from panda3d.core import (
    Geom,
    GeomEnums,
    GeomNode,
    GeomTriangles,
    GeomVertexArrayFormat,
    GeomVertexData,
    GeomVertexFormat,
    InternalName,
    Shader,
    TransparencyAttrib,
    Vec3,
    Vec4,
)

from holoverse.terrain_field import ring_height_grid

GROUND_SCHEMA = 1
# (tier name, cell size in world units, max distance in world units from the
# player to the nearest point of the sector).  The last tier has no limit.
GROUND_TIERS = (
    ("near", 8.0, 190.0),
    ("mid", 20.0, 520.0),
    ("far", 48.0, float("inf")),
)
GROUND_TIER_INDEX = {name: idx for idx, (name, _cell, _limit) in enumerate(GROUND_TIERS)}
MAX_RADIAL_STEPS = 110
MAX_ANGULAR_STEPS = 80
SKIRT_DEPTH = 2.4
NORMAL_EPSILON = 1.0

KIND_IDS = {"forest": 1.0, "hills": 2.0, "mushroom": 3.0, "desert": 4.0, "ice": 5.0, "urban": 6.0, "metropolis": 7.0}

# low / mid / high ground colours (linear-ish RGB) per biome.  Kept close to the
# accepted Pass 63 theme colours so each ring keeps its identity.
GROUND_PALETTES = {
    "forest": ((0.030, 0.150, 0.045), (0.060, 0.300, 0.090), (0.150, 0.380, 0.120)),
    "hills": ((0.150, 0.360, 0.080), (0.300, 0.600, 0.130), (0.560, 0.700, 0.260)),
    # Pass 282.56: an alien fungal floor rather than all pink - teal moss lowlands,
    # sea-green slopes and violet uplands.
    "mushroom": ((0.040, 0.120, 0.130), (0.090, 0.270, 0.250), (0.300, 0.240, 0.440)),
    "desert": ((0.330, 0.160, 0.050), (0.540, 0.300, 0.100), (0.780, 0.540, 0.250)),
    "ice": ((0.120, 0.300, 0.540), (0.360, 0.600, 0.820), (0.800, 0.910, 0.980)),
    "urban": ((0.085, 0.078, 0.074), (0.130, 0.120, 0.112), (0.200, 0.185, 0.170)),
}
# Faint holographic grid colour (rgb, strength) per biome.
GRID_COLORS = {
    "forest": (0.32, 1.00, 0.45, 0.12),
    "hills": (0.70, 1.00, 0.30, 0.10),
    "mushroom": (0.35, 1.00, 0.85, 0.12),
    "desert": (1.00, 0.70, 0.30, 0.10),
    "ice": (0.60, 0.95, 1.00, 0.12),
    "urban": (1.00, 0.30, 0.20, 0.12),
    "metropolis": (0.72, 0.44, 1.00, 0.10),
}

SUN_DIRECTION = (-0.42, -0.36, 0.83)
SUN_COLOR = (0.80, 0.77, 0.70)
SKY_AMBIENT = (0.46, 0.50, 0.60)
GROUND_BOUNCE = (0.24, 0.22, 0.21)


def _normalized(v):
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / length for c in v)


SUN_DIRECTION = _normalized(SUN_DIRECTION)


def tier_for_distance(distance: float) -> str:
    for name, _cell, limit in GROUND_TIERS:
        if float(distance) <= limit:
            return name
    return GROUND_TIERS[-1][0]


def tier_cell(tier: str) -> float:
    return float(GROUND_TIERS[GROUND_TIER_INDEX.get(str(tier), len(GROUND_TIERS) - 1)][1])


def sector_distance(px: float, py: float, r0: float, r1: float, a0: float, a1: float) -> float:
    """Approximate distance from (px, py) to the nearest point of an annular sector."""
    pr = math.hypot(px, py)
    pa = math.atan2(py, px)
    span = (a1 - a0)
    rel = (pa - a0) % math.tau
    if rel <= span:
        dr = 0.0 if r0 <= pr <= r1 else min(abs(pr - r0), abs(pr - r1))
        return dr
    # Outside the angular span: distance to the closer radial edge segment.
    best = float("inf")
    for edge in (a0, a1):
        ex, ey = math.cos(edge), math.sin(edge)
        t = max(r0, min(r1, px * ex + py * ey))
        best = min(best, math.hypot(px - ex * t, py - ey * t))
    return best


def grid_steps(r0: float, r1: float, a0: float, a1: float, cell: float):
    radial = max(2, min(MAX_RADIAL_STEPS, int(math.ceil((r1 - r0) / cell))))
    angular = max(2, min(MAX_ANGULAR_STEPS, int(math.ceil(abs(a1 - a0) * r1 / cell))))
    return radial, angular


def _value_noise(x, y, scale: float, seed: float):
    """Cheap smooth value noise in [0, 1] used for broad colour patches."""
    return 0.5 + 0.5 * (
        0.55 * np.sin(x * scale * 1.00 + y * scale * 0.37 + seed)
        + 0.30 * np.sin(x * scale * -0.61 + y * scale * 1.43 + seed * 1.7)
        + 0.15 * np.sin(x * scale * 2.31 + y * scale * -1.97 + seed * 2.9)
    )


def ground_colors(kind: str, x, y, z, nz, ring_height: float):
    low, mid, high = (np.asarray(c, dtype=np.float64) for c in GROUND_PALETTES.get(kind, GROUND_PALETTES["hills"]))
    peak = max(1.0, float(ring_height) * 1.55)
    ht = np.clip(z / peak, 0.0, 1.0)[..., None]
    lower = low + (mid - low) * np.clip(ht * 2.0, 0.0, 1.0)
    upper = mid + (high - mid) * np.clip((ht - 0.5) * 2.0, 0.0, 1.0)
    col = np.where(ht < 0.5, lower, upper)
    patch = _value_noise(x, y, 0.011, 1.3)[..., None]
    col = col * (0.86 + 0.28 * patch)
    slope = np.clip((1.0 - nz) * 2.4, 0.0, 1.0)[..., None]
    col = col + (low * 0.70 - col) * slope
    return np.clip(col, 0.0, 1.0)


def bake_lighting(colors, nx, ny, nz):
    sun = np.asarray(SUN_DIRECTION)
    ndl = np.clip((nx * sun[0] + ny * sun[1] + nz * sun[2] + 0.25) / 1.25, 0.0, 1.0)[..., None]
    hemi_t = (nz * 0.5 + 0.5)[..., None]
    ambient = np.asarray(GROUND_BOUNCE) + (np.asarray(SKY_AMBIENT) - np.asarray(GROUND_BOUNCE)) * hemi_t
    return np.clip(colors * (ambient + np.asarray(SUN_COLOR) * ndl), 0.0, 1.0)


_FORMAT = None


def _vertex_format():
    global _FORMAT
    if _FORMAT is None:
        array = GeomVertexArrayFormat()
        array.addColumn(InternalName.getVertex(), 3, GeomEnums.NT_float32, GeomEnums.C_point)
        array.addColumn(InternalName.getNormal(), 3, GeomEnums.NT_float32, GeomEnums.C_normal)
        array.addColumn(InternalName.getColor(), 4, GeomEnums.NT_float32, GeomEnums.C_color)
        _FORMAT = GeomVertexFormat.registerFormat(GeomVertexFormat(array))
    return _FORMAT


def build_sector_arrays(ring: dict, r0: float, r1: float, a0: float, a1: float, cell: float, *, bake: bool = False):
    """Return (vertex_records float32[N,10], indices uint32[M], steps) for one sector."""
    kind = str(ring.get("kind", ""))
    rs, as_ = grid_steps(r0, r1, a0, a1, cell)
    radii = np.linspace(r0, r1, rs + 1)
    angles = np.linspace(a0, a1, as_ + 1)
    rr, aa = np.meshgrid(radii, angles, indexing="ij")
    x = np.cos(aa) * rr
    y = np.sin(aa) * rr
    z = ring_height_grid(x, y, ring)
    # Normals are sampled at the mesh's own scale: a coarse far sheet with
    # fine-scale normals shows streaks where the lighting changes inside one
    # big triangle.
    e = max(NORMAL_EPSILON, float(cell) * 0.5)
    dzdx = (ring_height_grid(x + e, y, ring) - ring_height_grid(x - e, y, ring)) / (2.0 * e)
    dzdy = (ring_height_grid(x, y + e, ring) - ring_height_grid(x, y - e, ring)) / (2.0 * e)
    inv = 1.0 / np.sqrt(dzdx * dzdx + dzdy * dzdy + 1.0)
    nx, ny, nz = -dzdx * inv, -dzdy * inv, inv
    colors = ground_colors(kind, x, y, z, nz, float(ring.get("height", 1.0)))
    if bake:
        colors = bake_lighting(colors, nx, ny, nz)

    rows, cols = rs + 1, as_ + 1
    count = rows * cols
    rec = np.empty((count, 10), dtype=np.float32)
    rec[:, 0] = x.ravel(); rec[:, 1] = y.ravel(); rec[:, 2] = (z - 0.02).ravel()
    rec[:, 3] = nx.ravel(); rec[:, 4] = ny.ravel(); rec[:, 5] = nz.ravel()
    rec[:, 6:9] = colors.reshape(-1, 3); rec[:, 9] = 1.0

    idx = np.arange(count, dtype=np.uint32).reshape(rows, cols)
    i0 = idx[:-1, :-1]; i1 = idx[:-1, 1:]; i2 = idx[1:, :-1]; i3 = idx[1:, 1:]
    tris = [np.stack([i0, i2, i1], axis=-1).reshape(-1, 3), np.stack([i1, i2, i3], axis=-1).reshape(-1, 3)]

    # Skirts: a lowered copy of every border vertex, joined to the border.
    borders = (idx[0, :], idx[-1, :], idx[:, 0], idx[:, -1])
    skirt_records = []
    base = count
    for border in borders:
        border = np.asarray(border, dtype=np.uint32)
        lowered = rec[border].copy()
        lowered[:, 2] -= SKIRT_DEPTH
        skirt_records.append(lowered)
        low = np.arange(base, base + len(border), dtype=np.uint32)
        a, b = border[:-1], border[1:]
        la, lb = low[:-1], low[1:]
        tris.append(np.stack([a, la, b], axis=-1))
        tris.append(np.stack([b, la, lb], axis=-1))
        base += len(border)
    rec = np.concatenate([rec] + skirt_records, axis=0)
    indices = np.concatenate(tris, axis=0).astype(np.uint32).ravel()
    return rec, indices, (rs, as_)


def make_ground_node(name: str, rec, indices):
    vdata = GeomVertexData(name, _vertex_format(), Geom.UHStatic)
    vdata.uncleanSetNumRows(int(rec.shape[0]))
    memoryview(vdata.modifyArray(0)).cast("B")[:] = np.ascontiguousarray(rec, dtype=np.float32).tobytes()
    prim = GeomTriangles(Geom.UHStatic)
    prim.setIndexType(GeomEnums.NT_uint32)
    handle = prim.modifyVertices()
    handle.uncleanSetNumRows(int(indices.shape[0]))
    memoryview(handle).cast("B")[:] = np.ascontiguousarray(indices, dtype=np.uint32).tobytes()
    geom = Geom(vdata)
    geom.addPrimitive(prim)
    node = GeomNode(name)
    node.addGeom(geom)
    return node


# --------------------------------------------------------------------------
# GLSL program
# --------------------------------------------------------------------------
_VERTEX_SHADER = """
#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 p3d_Color;
out vec3 v_pos;
out vec3 v_normal;
out vec4 v_color;
out float v_dist;
void main() {
    v_pos = p3d_Vertex.xyz;
    v_normal = p3d_Normal;
    v_color = p3d_Color;
    v_dist = length((p3d_ModelViewMatrix * p3d_Vertex).xyz);
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
"""

_FRAGMENT_SHADER = """
#version 130
uniform struct p3d_FogParameters {
    vec4 color;
    float density;
    float start;
    float end;
    float scale;
} p3d_Fog;
uniform float u_kind;
uniform vec3 u_sun_dir;
uniform vec3 u_sun_color;
uniform vec3 u_sky_ambient;
uniform vec3 u_ground_bounce;
uniform vec4 u_grid_color;
uniform float u_fog_enabled;
in vec3 v_pos;
in vec3 v_normal;
in vec4 v_color;
in float v_dist;

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}
float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash12(i);
    float b = hash12(i + vec2(1.0, 0.0));
    float c = hash12(i + vec2(0.0, 1.0));
    float d = hash12(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; ++i) {
        v += a * vnoise(p);
        p = p * 2.03 + vec2(17.1, 9.7);
        a *= 0.5;
    }
    return v;
}

void main() {
    vec2 p = v_pos.xy;
    vec3 base = v_color.rgb;
    float near_fade = 1.0 - smoothstep(30.0, 140.0, v_dist);
    float micro_fade = 1.0 - smoothstep(12.0, 60.0, v_dist);
    float macro = fbm(p * 0.018);
    float meso = fbm(p * 0.11);
    base *= 0.84 + 0.30 * macro;
    base *= mix(1.0, 0.90 + 0.20 * meso, near_fade);
    vec3 emissive = vec3(0.0);
    int kind = int(u_kind + 0.5);
    if (kind == 1) {            // forest: leaf litter and moss
        float litter = smoothstep(0.52, 0.70, fbm(p * 0.21 + 3.1));
        base = mix(base, base * vec3(1.25, 0.95, 0.55), litter * 0.55);
        base *= 1.0 + (vnoise(p * 1.9) - 0.5) * 0.30 * micro_fade;
    } else if (kind == 2) {     // hills: grass tones and blade streaks
        float tone = fbm(p * 0.045 + 7.0);
        base = mix(base, base * vec3(1.18, 1.12, 0.62), smoothstep(0.55, 0.80, tone) * 0.55);
        float blades = vnoise(p * 1.6) * 0.6 + vnoise(p * 4.1 + 3.0) * 0.4;
        base *= 1.0 + (blades - 0.5) * 0.22 * micro_fade;
        float flowers = smoothstep(0.965, 0.995, vnoise(p * 2.2 + 11.0)) * micro_fade;
        base = mix(base, vec3(1.0, 0.92, 0.55), flowers * 0.45);
    } else if (kind == 3) {     // mushroom: spongy cells and spore glints
        float n = fbm(p * 0.08);
        float cells = abs(sin(p.x * 0.42 + n * 4.0) * sin(p.y * 0.42 + n * 4.0));
        base *= mix(1.0, 0.90 + 0.16 * smoothstep(0.15, 0.85, cells), near_fade * 0.8 + 0.2);
        float spore = smoothstep(0.90, 0.99, vnoise(p * 2.6 + 5.0)) * smoothstep(0.55, 0.75, fbm(p * 0.05 + 9.0));
        // Spores glow cyan in the moss and amber on the violet uplands.
        vec3 spore_rgb = mix(vec3(0.30, 1.0, 0.85), vec3(1.0, 0.62, 0.25), smoothstep(0.45, 0.75, fbm(p * 0.03 + 2.0)));
        emissive += spore_rgb * spore * 0.55 * micro_fade;
        // Mycelium threads: faint glowing veins between the spongy cells.
        float vein = 1.0 - smoothstep(0.0, 0.05, abs(fbm(p * 0.11 + 4.0) - 0.5));
        emissive += vec3(0.25, 0.85, 0.75) * vein * 0.10 * near_fade;
    } else if (kind == 4) {     // desert: wind ripples and grains
        float warp = fbm(p * 0.06) * 7.0;
        float ripple = sin(dot(p, vec2(0.83, 0.55)) * 1.35 + warp);
        base *= 1.0 + ripple * 0.07 * near_fade;
        base *= 1.0 + (vnoise(p * 7.0) - 0.5) * 0.10 * micro_fade;
    } else if (kind == 5) {     // ice: crack lines and sparkle
        float c1 = abs(vnoise(p * 0.065) * 2.0 - 1.0);
        float c2 = abs(vnoise(p * 0.19 + 4.0) * 2.0 - 1.0);
        float crack = (1.0 - smoothstep(0.0, 0.035, c1)) + 0.6 * (1.0 - smoothstep(0.0, 0.025, c2));
        base = mix(base, base * vec3(0.45, 0.62, 0.85), clamp(crack, 0.0, 1.0) * 0.6);
        float sparkle = smoothstep(0.975, 0.998, vnoise(p * 5.5 + 2.0));
        emissive += vec3(0.85, 0.95, 1.0) * sparkle * micro_fade * 0.45;
    } else if (kind == 7) {     // metropolis: streets, lane markings, crosswalks, paving, lawns
        float m = v_color.a;
        if (m > 0.8) {
            base *= 1.0 + (vnoise(p * 6.0) - 0.5) * 0.18 * micro_fade;
            vec2 q = mod(p, 80.0);
            vec2 d = min(q, 80.0 - q);                     // distance to the street centre lines
            vec2 ap = abs(p);
            vec2 half_w = vec2(ap.x < 40.0 ? 16.0 : 8.0, ap.y < 40.0 ? 16.0 : 8.0);
            bool along_x = d.y < half_w.y;                 // street running along x
            bool along_y = d.x < half_w.x;
            vec2 aa = fwidth(p) * 1.5;
            float marks = 0.0;
            if (along_x && !along_y) {
                float dash = step(0.5, fract(p.x / 6.0));
                marks += dash * (1.0 - smoothstep(0.12, 0.12 + aa.y, d.y));
                marks += 1.0 - smoothstep(0.10, 0.10 + aa.y, abs(d.y - (half_w.y - 1.0)));
            }
            if (along_y && !along_x) {
                float dash = step(0.5, fract(p.y / 6.0));
                marks += dash * (1.0 - smoothstep(0.12, 0.12 + aa.x, d.x));
                marks += 1.0 - smoothstep(0.10, 0.10 + aa.x, abs(d.x - (half_w.x - 1.0)));
            }
            if (along_x && along_y) {
                // Intersection box: crosswalk stripes at its edges.
                float cx = step(half_w.x - 3.5, d.x) * step(0.5, fract(p.y / 1.4));
                float cy = step(half_w.y - 3.5, d.y) * step(0.5, fract(p.x / 1.4));
                marks += max(cx, cy) * 0.9;
            }
            base = mix(base, vec3(0.78, 0.76, 0.70), clamp(marks, 0.0, 1.0) * 0.85 * (1.0 - smoothstep(60.0, 260.0, v_dist)));
        } else if (m > 0.45) {
            vec2 t = abs(fract(p / 2.0) - 0.5);
            float seam = 1.0 - smoothstep(0.44, 0.48, max(t.x, t.y));
            base *= mix(0.82, 1.0, mix(1.0, seam, micro_fade));
            base *= 0.92 + 0.16 * vnoise(p * 0.7);
        } else {
            float blades = vnoise(p * 1.6) * 0.6 + vnoise(p * 4.1 + 3.0) * 0.4;
            base *= 0.86 + 0.32 * blades * mix(0.6, 1.0, micro_fade);
        }
    } else if (kind == 6) {     // urban: scorched, cracked, debris-strewn war ground
        base *= 1.0 + (vnoise(p * 6.0) - 0.5) * 0.16 * micro_fade;
        base *= 0.80 + 0.32 * smoothstep(0.30, 0.70, fbm(p * 0.05 + 2.0));
        vec2 slab = abs(fract(p / 14.0) - 0.5);
        float seam = 1.0 - smoothstep(0.47, 0.49, max(slab.x, slab.y));
        base *= mix(0.72, 1.0, seam);
        float c1 = abs(vnoise(p * 0.09 + 3.0) * 2.0 - 1.0);
        float c2 = abs(vnoise(p * 0.31 + 8.0) * 2.0 - 1.0);
        float crack = (1.0 - smoothstep(0.0, 0.03, c1)) + 0.7 * (1.0 - smoothstep(0.0, 0.025, c2)) * near_fade;
        base = mix(base, base * 0.35, clamp(crack, 0.0, 1.0));
        float scorch = smoothstep(0.58, 0.80, fbm(p * 0.022 + 11.0));
        base = mix(base, vec3(0.025, 0.020, 0.018), scorch * 0.85);
        float ember = smoothstep(0.80, 0.92, fbm(p * 0.022 + 11.0)) * smoothstep(0.6, 0.9, vnoise(p * 0.9 + 4.0));
        emissive += vec3(0.9, 0.25, 0.05) * ember * 0.35 * near_fade;
        float debris = smoothstep(0.88, 0.96, vnoise(p * 2.3 + 1.0)) * micro_fade;
        base = mix(base, vec3(0.30, 0.27, 0.24), debris * 0.7);
        base *= vec3(1.08, 0.97, 0.90);
    }

    vec3 n = normalize(v_normal);
    float ndl = clamp((dot(n, normalize(u_sun_dir)) + 0.25) / 1.25, 0.0, 1.0);
    vec3 ambient = mix(u_ground_bounce, u_sky_ambient, n.z * 0.5 + 0.5);
    vec3 lit = base * (ambient + u_sun_color * ndl) + emissive;

    // Holographic grid: a soft world-space lattice that only appears near the viewer.
    vec2 cellp = p / 6.0;
    vec2 gdist = abs(fract(cellp - 0.5) - 0.5) / max(fwidth(cellp), vec2(1e-4));
    float line = 1.0 - clamp(min(gdist.x, gdist.y) * 0.8, 0.0, 1.0);
    float grid_fade = 1.0 - smoothstep(6.0, 34.0, v_dist);
    lit += u_grid_color.rgb * line * grid_fade * u_grid_color.a;

    float fog = 1.0;
    if (u_fog_enabled > 0.5 && p3d_Fog.end > p3d_Fog.start) {
        fog = clamp((p3d_Fog.end - v_dist) / (p3d_Fog.end - p3d_Fog.start), 0.0, 1.0);
    }
    gl_FragColor = vec4(mix(p3d_Fog.color.rgb, lit, fog), 1.0);
}
"""

_SHADER = None
_SHADER_STATUS = "unchecked"


def shader_disabled_by_environment() -> bool:
    return str(os.environ.get("HOLOVERSE_RING_GROUND_SHADER", "1")).strip().lower() in {"0", "off", "false", "no"}


def ground_shader(gsg=None):
    """Return the shared ground Shader, or None when GLSL is unavailable."""
    global _SHADER, _SHADER_STATUS
    if shader_disabled_by_environment():
        _SHADER_STATUS = "disabled_by_environment"
        return None
    if gsg is not None:
        try:
            if not bool(gsg.getSupportsBasicShaders()) or not bool(gsg.getSupportsGlsl()):
                _SHADER_STATUS = "gsg_without_glsl"
                return None
        except Exception:
            pass
    if _SHADER is None:
        try:
            _SHADER = Shader.make(Shader.SL_GLSL, vertex=_VERTEX_SHADER, fragment=_FRAGMENT_SHADER)
        except Exception:
            _SHADER = None
        _SHADER_STATUS = "ready" if _SHADER is not None else "make_failed"
    return _SHADER


def shader_status() -> str:
    return _SHADER_STATUS


def apply_ground_shader(np_, kind: str, shader, fog_enabled: bool = True):
    np_.setShader(shader, 50)
    np_.setShaderInput("u_kind", float(KIND_IDS.get(kind, 0.0)))
    np_.setShaderInput("u_sun_dir", Vec3(*SUN_DIRECTION))
    np_.setShaderInput("u_sun_color", Vec3(*SUN_COLOR))
    np_.setShaderInput("u_sky_ambient", Vec3(*SKY_AMBIENT))
    np_.setShaderInput("u_ground_bounce", Vec3(*GROUND_BOUNCE))
    np_.setShaderInput("u_grid_color", Vec4(*GRID_COLORS.get(kind, (0.5, 0.8, 1.0, 0.18))))
    np_.setShaderInput("u_fog_enabled", 1.0 if fog_enabled else 0.0)


def build_sector_ground(parent, ring: dict, r0: float, r1: float, a0: float, a1: float, tier: str, *, name: str, gsg=None):
    """Attach one sector ground sheet under ``parent`` and return its NodePath."""
    kind = str(ring.get("kind", ""))
    shader = ground_shader(gsg)
    rec, indices, steps = build_sector_arrays(ring, r0, r1, a0, a1, tier_cell(tier), bake=shader is None)
    np_ = parent.attachNewNode(make_ground_node(name, rec, indices))
    np_.setTextureOff(10)
    np_.setTransparency(TransparencyAttrib.MNone)
    np_.setDepthWrite(True)
    np_.setDepthTest(True)
    np_.setTwoSided(False)
    if shader is not None:
        apply_ground_shader(np_, kind, shader)
    else:
        np_.setLightOff(1)
    np_.setPythonTag("ring_ground_schema", GROUND_SCHEMA)
    np_.setPythonTag("ring_ground_tier", str(tier))
    np_.setPythonTag("ring_ground_steps", tuple(int(v) for v in steps))
    np_.setPythonTag("ring_ground_triangles", int(indices.shape[0] // 3))
    np_.setPythonTag("ring_ground_shaded", 1 if shader is not None else 0)
    return np_
