"""Metropolis rendering (Pass 282.52): lit merged meshes for the infinite city.

Turns a ``metropolis_layout.ChunkLayout`` into three nodes per stream chunk:

* ``metro-ground``  - asphalt with lane markings, crosswalks, raised
  sidewalk pads, park lawns and plazas (ring_ground shader, city kind 7);
* ``metro-buildings`` - every building, tree, light pole, bridge and holo
  accent of the chunk in ONE GeomNode (one draw call), drawn with the city
  shader: sun/sky lighting, procedural lit windows by floor, glowing accents
  and the scene fog;
* animated hover cars and service drones (small solid meshes).

Vertex colour alpha carries the material:
  1.0 facade (windows)  0.7 crystal  0.6 obsidian  0.5 plain lit  0.4 foliage
  0.3 sandstone  0.0 emissive
Ground alpha:  1.0 asphalt  0.6 paved pad  0.3 lawn.

Without GLSL the lighting is baked into vertex colours (no windows).
"""
from __future__ import annotations

import math

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
)

from holoverse import metropolis_layout as ML
from holoverse import ring_ground

MATERIAL_ALPHA = {"facade": 1.0, "roof": 0.5, "plain": 0.5, "trunk": 0.5, "foliage": 0.4, "crystal": 0.7, "obsidian": 0.6, "sandstone": 0.3, "emissive": 0.0}
GROUND_ALPHA = {"asphalt": 1.0, "pad": 0.6, "lawn": 0.3}
ASPHALT_RGB = (0.060, 0.062, 0.072)
ASPHALT_CELL = 16.0
LIGHT_POLE_HEIGHT = 7.5
LIGHT_RGB = (1.0, 0.86, 0.62)

_FORMAT = None


def _format():
    global _FORMAT
    if _FORMAT is None:
        array = GeomVertexArrayFormat()
        array.addColumn(InternalName.getVertex(), 3, GeomEnums.NT_float32, GeomEnums.C_point)
        array.addColumn(InternalName.getNormal(), 3, GeomEnums.NT_float32, GeomEnums.C_normal)
        array.addColumn(InternalName.getColor(), 4, GeomEnums.NT_float32, GeomEnums.C_color)
        array.addColumn(InternalName.getTexcoord(), 2, GeomEnums.NT_float32, GeomEnums.C_texcoord)
        _FORMAT = GeomVertexFormat.registerFormat(GeomVertexFormat(array))
    return _FORMAT


class MeshBuilder:
    """Collects quads/triangles as flat float records: pos3 nrm3 rgba4 uv2."""

    def __init__(self):
        self.rec = []
        self.idx = []
        self.count = 0

    def quad(self, p0, p1, p2, p3, normal, rgba, uv0=(0, 0), uv1=(1, 1)):
        """p0..p3 counter-clockwise seen from the normal side."""
        u0, v0 = uv0
        u1, v1 = uv1
        for p, (u, v) in zip((p0, p1, p2, p3), ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
            self.rec.append((p[0], p[1], p[2], normal[0], normal[1], normal[2], rgba[0], rgba[1], rgba[2], rgba[3], u, v))
        b = self.count
        self.idx.extend((b, b + 1, b + 2, b, b + 2, b + 3))
        self.count += 4

    def tri(self, p0, p1, p2, normal, rgba):
        for p in (p0, p1, p2):
            self.rec.append((p[0], p[1], p[2], normal[0], normal[1], normal[2], rgba[0], rgba[1], rgba[2], rgba[3], 0.0, 0.0))
        b = self.count
        self.idx.extend((b, b + 1, b + 2))
        self.count += 3

    def box(self, cx, cy, z0, sx, sy, sz, rgba, *, uv_seed=0.0, bottom=False):
        x0, x1 = cx - sx * 0.5, cx + sx * 0.5
        y0, y1 = cy - sy * 0.5, cy + sy * 0.5
        z1 = z0 + sz
        v0, v1 = z0 - ML.GROUND_Z, z1 - ML.GROUND_Z
        s = float(uv_seed)
        # -y face (front), +x, +y, -x: u runs along the face in metres.
        self.quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0), rgba, (s, v0), (s + sx, v1))
        self.quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (1, 0, 0), rgba, (s + sx, v0), (s + sx + sy, v1))
        self.quad((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (0, 1, 0), rgba, (s + sx + sy, v0), (s + 2 * sx + sy, v1))
        self.quad((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (-1, 0, 0), rgba, (s + 2 * sx + sy, v0), (s + 2 * sx + 2 * sy, v1))
        top_rgba = rgba if rgba[3] < 0.2 else (rgba[0], rgba[1], rgba[2], min(rgba[3], 0.5))
        self.quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1), top_rgba)
        if bottom:
            self.quad((x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0), (0, 0, -1), top_rgba)

    def obox(self, cx, cy, z0, sx, sy, sz, heading, rgba, *, uv_seed=0.0, bottom=False):
        """Box rotated by ``heading`` (radians) about its vertical centre line."""
        start = self.count
        rec_start = len(self.rec)
        self.box(0.0, 0.0, z0, sx, sy, sz, rgba, uv_seed=uv_seed, bottom=bottom)
        c, s = math.cos(heading), math.sin(heading)
        for k in range(rec_start, len(self.rec)):
            r = list(self.rec[k])
            x, y = r[0], r[1]
            r[0], r[1] = cx + x * c - y * s, cy + x * s + y * c
            nx, ny = r[3], r[4]
            r[3], r[4] = nx * c - ny * s, nx * s + ny * c
            self.rec[k] = tuple(r)
        return start

    def prism(self, cx, cy, z0, r0, r1, h, sides, rgba, *, uv_seed=0.0, lean=(0.0, 0.0), twist=0.0, cap=True, double=False):
        """Vertical prism (optionally tapered, leaning by ``lean`` at the top,
        twisted; ``cap=False`` leaves the top open, ``double`` adds back faces)."""
        if lean != (0.0, 0.0) or twist or not cap or double:
            return self._prism_general(cx, cy, z0, r0, r1, h, sides, rgba, uv_seed, lean, twist, cap, double)
        z1 = z0 + h
        perim = 0.0
        step = math.tau / sides
        top = []
        slope = (r0 - r1) / max(1e-6, h)
        for k in range(sides):
            a0 = k * step + step * 0.5
            a1 = a0 + step
            p0 = (cx + math.cos(a0) * r0, cy + math.sin(a0) * r0, z0)
            p1 = (cx + math.cos(a1) * r0, cy + math.sin(a1) * r0, z0)
            p2 = (cx + math.cos(a1) * r1, cy + math.sin(a1) * r1, z1)
            p3 = (cx + math.cos(a0) * r1, cy + math.sin(a0) * r1, z1)
            am = (a0 + a1) * 0.5
            n = (math.cos(am), math.sin(am), slope)
            nl = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
            n = (n[0] / nl, n[1] / nl, n[2] / nl)
            width = 2.0 * r0 * math.sin(step * 0.5)
            self.quad(p0, p1, p2, p3, n, rgba, (uv_seed + perim, z0 - ML.GROUND_Z), (uv_seed + perim + width, z1 - ML.GROUND_Z))
            perim += width
            top.append(p3)
        if r1 > 0.06:
            cap = rgba if rgba[3] < 0.2 else (rgba[0], rgba[1], rgba[2], min(rgba[3], 0.5))
            centre = (cx, cy, z1)
            for k in range(sides):
                self.tri(centre, top[k], top[(k + 1) % sides], (0, 0, 1), cap)

    def _flat_quad(self, p0, p1, p2, p3, rgba, uv0=(0, 0), uv1=(1, 1)):
        ux, uy, uz = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        vx, vy, vz = (p3[0] - p0[0], p3[1] - p0[1], p3[2] - p0[2])
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        nl = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        self.quad(p0, p1, p2, p3, (n[0] / nl, n[1] / nl, n[2] / nl), rgba, uv0, uv1)

    def _prism_general(self, cx, cy, z0, r0, r1, h, sides, rgba, uv_seed, lean, twist, cap=True, double=False):
        step = math.tau / sides
        tx, ty = cx + lean[0], cy + lean[1]
        z1 = z0 + h
        bottom = [(cx + math.cos(k * step) * r0, cy + math.sin(k * step) * r0, z0) for k in range(sides)]
        top = [(tx + math.cos(k * step + twist) * r1, ty + math.sin(k * step + twist) * r1, z1) for k in range(sides)]
        perim = 0.0
        width = 2.0 * r0 * math.sin(step * 0.5)
        for k in range(sides):
            j = (k + 1) % sides
            self._flat_quad(bottom[k], bottom[j], top[j], top[k], rgba, (uv_seed + perim, z0 - ML.GROUND_Z), (uv_seed + perim + width, z1 - ML.GROUND_Z))
            if double:
                self._flat_quad(bottom[j], bottom[k], top[k], top[j], rgba)
            perim += width
        if cap and r1 > 0.06:
            cap = rgba if rgba[3] < 0.2 else (rgba[0], rgba[1], rgba[2], min(rgba[3], 0.5) if rgba[3] > 0.9 else rgba[3])
            centre = (tx, ty, z1)
            for k in range(sides):
                self.tri(centre, top[k], top[(k + 1) % sides], (0, 0, 1), cap)

    def dome(self, cx, cy, z0, radius, rgba, *, rings=6, sides=16, squash=1.0):
        """Hemispherical dome (smooth normals) sitting on z0."""
        pts = []
        for i in range(rings + 1):
            lat = (math.pi * 0.5) * i / rings
            row = []
            for k in range(sides + 1):
                lon = math.tau * k / sides
                nx, ny, nz = math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)
                row.append(((cx + nx * radius, cy + ny * radius, z0 + nz * radius * squash), (nx, ny, nz)))
            pts.append(row)
        for i in range(rings):
            for k in range(sides):
                quad = (pts[i][k], pts[i][k + 1], pts[i + 1][k + 1], pts[i + 1][k])
                b = self.count
                for (p, n), (u, v) in zip(quad, ((k, i), (k + 1, i), (k + 1, i + 1), (k, i + 1))):
                    self.rec.append((p[0], p[1], p[2], n[0], n[1], n[2], rgba[0], rgba[1], rgba[2], rgba[3], u * 2.0, v * 2.0))
                self.idx.extend((b, b + 1, b + 2, b, b + 2, b + 3))
                self.count += 4

    def ellipsoid(self, cx, cy, cz, rx, ry, rz, rgba, *, rings=8, sides=14, heading=0.0):
        """Closed ellipsoid with smooth normals (creatures, snow drifts), turned by ``heading``."""
        ch, sh = math.cos(heading), math.sin(heading)
        rows = []
        for i in range(rings + 1):
            lat = -math.pi * 0.5 + math.pi * i / rings
            row = []
            for k in range(sides + 1):
                lon = math.tau * k / sides
                ux, uy, uz = math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)
                nx, ny, nz = ux / max(rx, 1e-6), uy / max(ry, 1e-6), uz / max(rz, 1e-6)
                nl = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
                lx, ly = ux * rx, uy * ry
                nx, ny = nx * ch - ny * sh, nx * sh + ny * ch
                row.append(((cx + lx * ch - ly * sh, cy + lx * sh + ly * ch, cz + uz * rz), (nx / nl, ny / nl, nz / nl)))
            rows.append(row)
        for i in range(rings):
            for k in range(sides):
                quad = (rows[i][k], rows[i][k + 1], rows[i + 1][k + 1], rows[i + 1][k])
                b = self.count
                for (p, n), (u, v) in zip(quad, ((k, i), (k + 1, i), (k + 1, i + 1), (k, i + 1))):
                    self.rec.append((p[0], p[1], p[2], n[0], n[1], n[2], rgba[0], rgba[1], rgba[2], rgba[3], u * 2.0, v * 2.0))
                self.idx.extend((b, b + 1, b + 2, b, b + 2, b + 3))
                self.count += 4

    def sweep(self, path, width, height, rgba):
        """Rectangular beam swept along a 3-D polyline (bridges, arches).

        ``width`` is measured sideways (horizontal), ``height`` in the plane of
        the path's bend, so an arch keeps its thickness down its legs."""
        if len(path) < 2:
            return
        sections = []
        for i, p in enumerate(path):
            a = path[max(0, i - 1)]
            b = path[min(len(path) - 1, i + 1)]
            tx, ty, tz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
            tl = math.sqrt(tx * tx + ty * ty + tz * tz) or 1.0
            tx, ty, tz = tx / tl, ty / tl, tz / tl
            # side = t x z (horizontal); up = side x t
            sx, sy = ty, -tx
            sl = math.hypot(sx, sy)
            if sl < 1e-6:
                sx, sy = 1.0, 0.0
            else:
                sx, sy = sx / sl, sy / sl
            ux, uy, uz = sy * tz, -sx * tz, sx * ty - sy * tx
            hw, hh = width * 0.5, height * 0.5
            # corners: 0 right-bottom, 1 left-bottom, 2 left-top, 3 right-top ("left" = -side)
            sections.append(tuple((p[0] + sx * cs * hw + ux * cu * hh, p[1] + sy * cs * hw + uy * cu * hh, p[2] + uz * cu * hh)
                                  for cs, cu in ((1, -1), (-1, -1), (-1, 1), (1, 1))))
        for i in range(len(sections) - 1):
            a, b = sections[i], sections[i + 1]
            self._flat_quad(a[3], b[3], b[2], a[2], rgba)   # top
            self._flat_quad(a[1], b[1], b[0], a[0], rgba)   # bottom
            self._flat_quad(a[0], b[0], b[3], a[3], rgba)   # right side
            self._flat_quad(a[2], b[2], b[1], a[1], rgba)   # left side

    def arrays(self):
        rec = np.asarray(self.rec, dtype=np.float32).reshape(-1, 12)
        idx = np.asarray(self.idx, dtype=np.uint32)
        return rec, idx


def make_node(name: str, rec, idx):
    vdata = GeomVertexData(name, _format(), Geom.UHStatic)
    vdata.uncleanSetNumRows(int(rec.shape[0]))
    memoryview(vdata.modifyArray(0)).cast("B")[:] = np.ascontiguousarray(rec, dtype=np.float32).tobytes()
    prim = GeomTriangles(Geom.UHStatic)
    prim.setIndexType(GeomEnums.NT_uint32)
    handle = prim.modifyVertices()
    handle.uncleanSetNumRows(int(idx.shape[0]))
    memoryview(handle).cast("B")[:] = np.ascontiguousarray(idx, dtype=np.uint32).tobytes()
    geom = Geom(vdata)
    geom.addPrimitive(prim)
    node = GeomNode(name)
    node.addGeom(geom)
    return node


def bake(rec):
    """Fallback lighting baked into vertex colours (emissive stays bright)."""
    sun = np.asarray(ring_ground.SUN_DIRECTION, dtype=np.float32)
    n = rec[:, 3:6]
    ndl = np.clip((n @ sun + 0.25) / 1.25, 0.0, 1.0)[:, None]
    hemi = (n[:, 2:3] * 0.5 + 0.5)
    ambient = np.asarray(ring_ground.GROUND_BOUNCE) + (np.asarray(ring_ground.SKY_AMBIENT) - np.asarray(ring_ground.GROUND_BOUNCE)) * hemi
    lit = rec[:, 6:9] * (ambient + np.asarray(ring_ground.SUN_COLOR) * ndl)
    emissive = rec[:, 9:10] < 0.2
    out = rec.copy()
    out[:, 6:9] = np.clip(np.where(emissive, rec[:, 6:9] * 1.3, lit), 0.0, 1.0)
    out[:, 9] = 1.0
    return out


# --------------------------------------------------------------------------
# Chunk meshes
# --------------------------------------------------------------------------
def _clamp_out(x, y, r_min):
    r = math.hypot(x, y)
    if r >= r_min or r < 1e-6:
        return x, y
    s = r_min / r
    return x * s, y * s


def build_ground_mesh(layout, r0: float) -> MeshBuilder:
    mb = MeshBuilder()
    size = ML.CHUNK_SIZE
    x0 = layout.cx * size
    y0 = layout.cy * size
    steps = int(size / ASPHALT_CELL)
    z = ML.GROUND_Z
    asphalt = (*ASPHALT_RGB, GROUND_ALPHA["asphalt"])
    for i in range(steps):
        for j in range(steps):
            ax0 = x0 + i * ASPHALT_CELL; ax1 = ax0 + ASPHALT_CELL
            ay0 = y0 + j * ASPHALT_CELL; ay1 = ay0 + ASPHALT_CELL
            corners = [(ax0, ay0), (ax1, ay0), (ax1, ay1), (ax0, ay1)]
            if max(math.hypot(px, py) for px, py in corners) < r0:
                continue  # wholly inside the Urban ring
            pts = [_clamp_out(px, py, r0) + (z,) for px, py in corners]
            mb.quad(pts[0], pts[1], pts[2], pts[3], (0, 0, 1), asphalt)
    curb = (0.34, 0.34, 0.36, GROUND_ALPHA["pad"])
    for lot in layout.lots:
        px0, py0, px1, py1 = lot.pad
        kind_alpha = GROUND_ALPHA["lawn"] if lot.kind == "park" else GROUND_ALPHA["pad"]
        rgba = (*lot.pad_rgb, kind_alpha)
        ztop = z + ML.PAD_HEIGHT
        mb.quad((px0, py0, ztop), (px1, py0, ztop), (px1, py1, ztop), (px0, py1, ztop), (0, 0, 1), rgba)
        # Curb faces.
        mb.quad((px0, py0, z), (px1, py0, z), (px1, py0, ztop), (px0, py0, ztop), (0, -1, 0), curb)
        mb.quad((px1, py0, z), (px1, py1, z), (px1, py1, ztop), (px1, py0, ztop), (1, 0, 0), curb)
        mb.quad((px1, py1, z), (px0, py1, z), (px0, py1, ztop), (px1, py1, ztop), (0, 1, 0), curb)
        mb.quad((px0, py1, z), (px0, py0, z), (px0, py0, ztop), (px0, py1, ztop), (-1, 0, 0), curb)
    return mb


def build_structure_mesh(layout) -> MeshBuilder:
    mb = MeshBuilder()
    for b in layout.boxes:
        rgba = (*b.rgb, MATERIAL_ALPHA.get(b.kind, 0.5))
        mb.box(b.x, b.y, b.z0, b.sx, b.sy, b.sz, rgba, uv_seed=(b.seed % 997) * 3.1)
    for p in layout.prisms:
        rgba = (*p.rgb, MATERIAL_ALPHA.get(p.kind, 0.5))
        mb.prism(p.x, p.y, p.z0, p.radius0, p.radius1, p.height, p.sides, rgba, uv_seed=(p.seed % 991) * 2.7)
    pole = (0.22, 0.23, 0.26, MATERIAL_ALPHA["plain"])
    lamp = (*LIGHT_RGB, MATERIAL_ALPHA["emissive"])
    zb = ML.GROUND_Z + ML.PAD_HEIGHT
    for lx, ly in layout.lights:
        mb.box(lx, ly, zb, 0.28, 0.28, LIGHT_POLE_HEIGHT, pole)
        mb.box(lx, ly, zb + LIGHT_POLE_HEIGHT, 0.9, 0.9, 0.35, lamp, bottom=True)
    return mb


def build_vehicle_mesh(rgb, accent) -> MeshBuilder:
    mb = MeshBuilder()
    body = (*rgb, MATERIAL_ALPHA["plain"])
    mb.box(0.0, 0.0, -0.7, 6.2, 2.6, 1.3, body, bottom=True)
    mb.box(0.6, 0.0, 0.6, 3.0, 2.0, 0.8, (0.08, 0.10, 0.14, MATERIAL_ALPHA["plain"]))
    mb.box(-3.15, 0.0, -0.4, 0.15, 2.2, 0.5, (1.0, 0.18, 0.22, 0.0))       # tail lights
    mb.box(3.15, 0.0, -0.4, 0.15, 2.0, 0.35, (0.95, 0.98, 1.0, 0.0))      # head lights
    mb.box(0.0, 0.0, -0.85, 5.6, 2.8, 0.12, (*accent, 0.0), bottom=True)  # under-glow strip
    return mb


def build_drone_mesh(rgb, accent) -> MeshBuilder:
    mb = MeshBuilder()
    shell = (*rgb, MATERIAL_ALPHA["plain"])
    mb.prism(0.0, 0.0, -0.5, 0.9, 0.9, 1.0, 8, shell)
    mb.prism(0.0, 0.0, 0.5, 0.9, 0.2, 0.5, 8, shell)
    mb.prism(0.0, 0.0, -0.15, 1.05, 1.05, 0.22, 8, (*accent, 0.0))
    mb.box(0.85, 0.0, 0.0, 0.2, 0.5, 0.3, (0.6, 1.0, 1.0, 0.0))
    return mb


# --------------------------------------------------------------------------
# City shader
# --------------------------------------------------------------------------
_VERTEX = """
#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 p3d_Color;
in vec2 p3d_MultiTexCoord0;
uniform mat3 p3d_NormalMatrix;
out vec3 v_normal;
out vec3 v_eye_normal;
out vec3 v_eye_pos;
out float v_height;
out vec4 v_color;
out vec2 v_uv;
out float v_dist;
void main() {
    v_normal = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
    v_eye_normal = normalize(p3d_NormalMatrix * p3d_Normal);
    v_eye_pos = (p3d_ModelViewMatrix * p3d_Vertex).xyz;
    v_height = (p3d_ModelMatrix * p3d_Vertex).z;
    v_color = p3d_Color;
    v_uv = p3d_MultiTexCoord0;
    v_dist = length((p3d_ModelViewMatrix * p3d_Vertex).xyz);
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
"""

_FRAGMENT = """
#version 130
uniform struct p3d_FogParameters {
    vec4 color;
    float density;
    float start;
    float end;
    float scale;
} p3d_Fog;
uniform vec3 u_sun_dir;
uniform vec3 u_sun_color;
uniform vec3 u_sky_ambient;
uniform vec3 u_ground_bounce;
uniform vec3 u_window_rgb;
uniform vec3 u_glass_rgb;
uniform float u_lit_share;
uniform mat4 p3d_ViewMatrix;
in vec3 v_normal;
in vec3 v_eye_normal;
in vec3 v_eye_pos;
in float v_height;
in vec4 v_color;
in vec2 v_uv;
in float v_dist;

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float band(float x, float lo, float hi, float aa) {
    return smoothstep(lo - aa, lo + aa, x) * (1.0 - smoothstep(hi - aa, hi + aa, x));
}

void main() {
    float mat = v_color.a;
    vec3 colour;
    if (mat < 0.2) {
        colour = v_color.rgb * 1.55;
    } else {
        vec3 n = normalize(v_normal);
        float ndl = clamp((dot(n, normalize(u_sun_dir)) + 0.25) / 1.25, 0.0, 1.0);
        vec3 ambient = mix(u_ground_bounce, u_sky_ambient, n.z * 0.5 + 0.5);
        vec3 base = v_color.rgb;
        vec3 emissive = vec3(0.0);
        if (mat > 0.9 && abs(n.z) < 0.6) {
            // Facade: floors 3.8 m, window bays 2.6 m; ground floor is a storefront.
            vec2 cell = vec2(v_uv.x / 2.6, v_uv.y / 3.8);
            vec2 f = fract(cell);
            vec2 id = floor(cell);
            vec2 aa = fwidth(cell) * 1.2;
            float storefront = 1.0 - step(1.0, cell.y);
            float wx = band(f.x, mix(0.16, 0.04, storefront), mix(0.84, 0.96, storefront), aa.x);
            float wy = band(f.y, mix(0.28, 0.10, storefront), mix(0.86, 0.78, storefront), aa.y);
            float glass = wx * wy;
            float lit = step(hash12(id + vec2(17.0, 3.0)), u_lit_share + storefront * 0.35);
            float flicker = 0.65 + 0.35 * hash12(id * 1.37 + 5.1);
            // Far away the window grid is sub-pixel: blend to its average.
            float far_t = smoothstep(220.0, 520.0, v_dist);
            float glass_avg = 0.40;
            glass = mix(glass, glass_avg, far_t);
            lit = mix(lit, u_lit_share, far_t);
            base = mix(base, u_glass_rgb, glass);
            emissive = u_window_rgb * glass * lit * flicker;
        }
        if (mat > 0.65 && mat < 0.75) {
            // Glacial crystal: cold core glow rising with height, bright fresnel rim, sparkle.
            vec3 view = normalize(-v_eye_pos);
            float fres = pow(1.0 - clamp(abs(dot(view, normalize(v_eye_normal))), 0.0, 1.0), 2.6);
            float sheen = 0.5 + 0.5 * sin(v_uv.y * 0.35 + v_uv.x * 0.5);
            emissive += v_color.rgb * (0.08 + 0.10 * sheen) + vec3(0.60, 0.85, 1.0) * fres * 0.55;
            float glint = step(0.997, hash12(floor(v_uv * 3.0)));
            emissive += vec3(0.9, 0.97, 1.0) * glint * (1.0 - smoothstep(30.0, 140.0, v_dist));
            base *= 0.70;
        }
        if (mat > 0.35 && mat < 0.45) {
            base *= 0.85 + 0.30 * hash12(floor(v_uv * 2.0));
        }
        if (mat > 0.55 && mat < 0.65) {
            // Obsidian: near-black volcanic glass with a sharp sun glint and a violet sheen.
            vec3 view = normalize(-v_eye_pos);
            vec3 ne = normalize(v_eye_normal);
            vec3 sun_eye = normalize(mat3(p3d_ViewMatrix) * u_sun_dir);
            float spec = pow(max(dot(reflect(-sun_eye, ne), view), 0.0), 42.0);
            float fres = pow(1.0 - clamp(abs(dot(view, ne)), 0.0, 1.0), 3.0);
            emissive += u_sun_color * spec * 1.4 + vec3(0.36, 0.24, 0.58) * fres * 0.45;
            emissive += mix(u_ground_bounce, u_sky_ambient, n.z * 0.5 + 0.5) * (0.06 + 0.30 * fres);   // glassy sky reflection
            base *= 0.55;
        }
        if (mat > 0.25 && mat < 0.35) {
            // Sandstone: layered strata by height plus a fine grain.
            float strata = 0.5 + 0.5 * sin(v_height * 1.15 + 1.7 * sin(v_height * 0.23));
            base *= 0.84 + 0.20 * strata + 0.08 * (hash12(floor(v_uv * 3.0)) - 0.5);
        }
        colour = base * (ambient + u_sun_color * ndl) + emissive;
    }
    float fog = 1.0;
    if (p3d_Fog.end > p3d_Fog.start) {
        fog = clamp((p3d_Fog.end - v_dist) / (p3d_Fog.end - p3d_Fog.start), 0.0, 1.0);
    }
    gl_FragColor = vec4(mix(p3d_Fog.color.rgb, colour, fog), 1.0);
}
"""

_SHADER = None


def city_shader(gsg=None):
    global _SHADER
    if ring_ground.ground_shader(gsg) is None:
        return None   # same GLSL availability rules as the ring ground
    if _SHADER is None:
        try:
            _SHADER = Shader.make(Shader.SL_GLSL, vertex=_VERTEX, fragment=_FRAGMENT)
        except Exception:
            _SHADER = None
    return _SHADER


def apply_city_shader(np_, shader, district: str):
    facade, glass, window, accent, *_ = ML.DISTRICTS.get(district, ML.DISTRICTS["commerce"])
    np_.setShader(shader, 50)
    np_.setShaderInput("u_sun_dir", Vec3(*ring_ground.SUN_DIRECTION))
    np_.setShaderInput("u_sun_color", Vec3(*ring_ground.SUN_COLOR))
    np_.setShaderInput("u_sky_ambient", Vec3(*ring_ground.SKY_AMBIENT))
    np_.setShaderInput("u_ground_bounce", Vec3(*ring_ground.GROUND_BOUNCE))
    np_.setShaderInput("u_window_rgb", Vec3(*window))
    np_.setShaderInput("u_glass_rgb", Vec3(*glass))
    np_.setShaderInput("u_lit_share", 0.36 if district != "residential" else 0.46)


def _attach(parent, name, mb, gsg, district, *, ground=False):
    rec, idx = mb.arrays()
    if rec.shape[0] == 0:
        return None
    shader = ring_ground.ground_shader(gsg) if ground else city_shader(gsg)
    if shader is None:
        rec = bake(rec)
    # The ring-ground shader reads pos/normal/colour and ignores the uv column.
    np_ = parent.attachNewNode(make_node(name, rec, idx))
    np_.setTextureOff(10)
    np_.setTransparency(TransparencyAttrib.MNone)
    np_.setDepthWrite(True)
    np_.setDepthTest(True)
    if shader is None:
        np_.setLightOff(1)
    elif ground:
        ring_ground.apply_ground_shader(np_, "metropolis", shader)
    else:
        apply_city_shader(np_, shader, district)
    np_.setPythonTag("metro_triangles", int(idx.shape[0] // 3))
    np_.setPythonTag("metro_shaded", 1 if shader is not None else 0)
    return np_


def build_chunk_nodes(parent, layout, r0: float, gsg=None):
    """Attach ground + structure meshes for one chunk; returns (ground, structures)."""
    ground = _attach(parent, f"metro-ground-{layout.cx}-{layout.cy}", build_ground_mesh(layout, r0), gsg, layout.district, ground=True)
    structures = _attach(parent, f"metro-buildings-{layout.cx}-{layout.cy}", build_structure_mesh(layout), gsg, layout.district)
    return ground, structures


def build_mover_node(parent, name, mb, gsg, district):
    return _attach(parent, name, mb, gsg, district)
