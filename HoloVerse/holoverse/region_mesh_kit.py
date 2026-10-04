"""Shared mesh and creature helpers for the HoloVerse ring civilizations.

Turns ``region_kit.Piece`` records into one merged, lit mesh per sector
(the Pass 282.52 city shader), caches the arrays on the sector data, and
provides the walking-creature rig, sky domes and glow motes used by the Ice
(Pass 282.54) and Desert (Pass 282.55) life directors.

Vertex alpha selects the shader material:
  1.0 facade  0.7 crystal  0.6 obsidian  0.5 plain/snow  0.4 foliage
  0.3 sandstone  0.0 emissive
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
from panda3d.core import NodePath, TransparencyAttrib, Vec3

from holoverse import metropolis_city as MC

MAT_ALPHA = {"crystal": 0.7, "obsidian": 0.6, "snow": 0.5, "plain": 0.5, "foliage": 0.4, "sandstone": 0.3, "emissive": 0.0}


@dataclass(frozen=True)
class Lighting:
    sun: tuple
    sky: tuple
    bounce: tuple
    window: tuple = (1.0, 0.7, 0.35)


def apply_lit_shader(np_, shader, light: Lighting):
    from holoverse import ring_ground as RG
    np_.setShader(shader, 50)
    np_.setShaderInput("u_sun_dir", Vec3(*RG.SUN_DIRECTION))
    np_.setShaderInput("u_sun_color", Vec3(*light.sun))
    np_.setShaderInput("u_sky_ambient", Vec3(*light.sky))
    np_.setShaderInput("u_ground_bounce", Vec3(*light.bounce))
    np_.setShaderInput("u_window_rgb", Vec3(*light.window))
    np_.setShaderInput("u_glass_rgb", Vec3(0.05, 0.06, 0.08))
    np_.setShaderInput("u_lit_share", 0.0)


def bake_lit(rec):
    """No-GLSL fallback: bake the light; crystal keeps a glow, obsidian a sheen."""
    alpha = rec[:, 9]
    crystal = (alpha > 0.65) & (alpha < 0.75)
    obsidian = (alpha > 0.55) & (alpha < 0.65)
    out = MC.bake(rec)
    out[crystal, 6:9] = np.clip(out[crystal, 6:9] + rec[crystal, 6:9] * 0.25, 0.0, 1.0)
    out[obsidian, 6:9] = np.clip(out[obsidian, 6:9] + 0.04, 0.0, 1.0)
    return out


def disc(mb, x, y, r, offset, rgba, height_fn, *, flat_z=None, rings=6, sides=28):
    """Disc conforming to the ground (or flat at ``flat_z``), smooth up normals."""
    rows = []
    for i in range(rings + 1):
        rr = r * i / rings
        row = []
        for k in range(sides if i else 1):
            a = math.tau * k / sides
            px, py = x + math.cos(a) * rr, y + math.sin(a) * rr
            pz = flat_z if flat_z is not None else height_fn(px, py) + offset
            row.append((px, py, pz))
        rows.append(row)

    def emit(p):
        mb.rec.append((p[0], p[1], p[2], 0.0, 0.0, 1.0, rgba[0], rgba[1], rgba[2], rgba[3], p[0] * 0.25, p[1] * 0.25))
        mb.count += 1
        return mb.count - 1
    ids = [[emit(p) for p in row] for row in rows]
    centre = ids[0][0]
    for k in range(sides):
        mb.idx.extend((centre, ids[1][k], ids[1][(k + 1) % sides]))
    for i in range(1, rings):
        for k in range(sides):
            j = (k + 1) % sides
            a, b, c, d = ids[i][k], ids[i][j], ids[i + 1][j], ids[i + 1][k]
            mb.idx.extend((a, d, c, a, c, b))


def pyramid(mb, cx, cy, z0, half, h, heading, rgba, *, top_frac=1.0):
    """Square pyramid (flat faces), optionally truncated at ``top_frac`` of its height."""
    c, s = math.cos(heading), math.sin(heading)

    def corner(lx, ly, z):
        return (cx + lx * c - ly * s, cy + lx * s + ly * c, z)
    zt = z0 + h * top_frac
    ht = half * (1.0 - top_frac)
    base = [corner(-half, -half, z0), corner(half, -half, z0), corner(half, half, z0), corner(-half, half, z0)]
    if ht > 1e-3:
        top = [corner(-ht, -ht, zt), corner(ht, -ht, zt), corner(ht, ht, zt), corner(-ht, ht, zt)]
        for k in range(4):
            j = (k + 1) % 4
            mb._flat_quad(base[k], base[j], top[j], top[k], rgba, (0.0, 0.0), (half * 2.0, h * top_frac))
        mb.quad(top[0], top[1], top[2], top[3], (0.0, 0.0, 1.0), rgba, (0, 0), (1, 1))
    else:
        apex = corner(0.0, 0.0, z0 + h)
        for k in range(4):
            j = (k + 1) % 4
            p0, p1 = base[k], base[j]
            ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
            vx, vy, vz = apex[0] - p0[0], apex[1] - p0[1], apex[2] - p0[2]
            n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
            nl = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
            mb.tri(p0, p1, apex, (n[0] / nl, n[1] / nl, n[2] / nl), rgba)


def emit_pieces(mb, pieces, height_fn):
    for p in pieces:
        rgba = (*p.rgb, MAT_ALPHA.get(p.mat, 0.5))
        kw = p.kw or {}
        if p.op == "prism":
            x, y, z, r0, r1, h, sides = p.args
            hollow = bool(kw.get("hollow"))
            mb.prism(x, y, z, r0, r1, h, int(sides), rgba, lean=kw.get("lean", (0.0, 0.0)), twist=kw.get("twist", 0.0),
                     cap=not hollow, double=hollow, uv_seed=(x * 0.37 + y * 0.11) % 97.0)
        elif p.op == "dome":
            x, y, z, r = p.args
            mb.dome(x, y, z, r, rgba, rings=int(kw.get("rings", 6)), sides=int(kw.get("sides", 16)), squash=float(kw.get("squash", 1.0)))
        elif p.op == "sweep":
            path, width, height = p.args
            mb.sweep(list(path), width, height, rgba)
        elif p.op == "obox":
            x, y, z, sx, sy, sz, heading = p.args
            mb.obox(x, y, z, sx, sy, sz, heading, rgba)
        elif p.op == "ellipsoid":
            x, y, z, rx, ry, rz = p.args
            mb.ellipsoid(x, y, z, rx, ry, rz, rgba, rings=int(kw.get("rings", 7)), sides=int(kw.get("sides", 16)), heading=float(kw.get("heading", 0.0)))
        elif p.op == "disc":
            x, y, r, offset = p.args
            disc(mb, x, y, r, offset, rgba, height_fn, flat_z=kw.get("flat_z"), rings=int(kw.get("rings", 6)))
        elif p.op == "pyramid":
            x, y, z, half, h, heading = p.args
            pyramid(mb, x, y, z, half, h, heading, rgba, top_frac=float(kw.get("top_frac", 1.0)))


def sector_arrays(sector_data, height_fn, gsg=None):
    """Vertex/index arrays for one sector, cached on the sector data so a
    rebuild (ring re-entry, chunk reload) or a pre-warm costs nothing twice."""
    cached = getattr(sector_data, "mesh_cache", None)
    if cached is not None:
        return cached
    mb = MC.MeshBuilder()
    emit_pieces(mb, sector_data.pieces, height_fn)
    rec, idx = mb.arrays()
    if rec.shape[0] and MC.city_shader(gsg) is None:
        rec = bake_lit(rec)
    sector_data.mesh_cache = (rec, idx)
    return sector_data.mesh_cache


def sector_arrays_step(sector_data, height_fn, gsg=None, budget_s: float = 0.010) -> bool:
    """Build the sector's mesh arrays a slice at a time (about ``budget_s`` of
    work per call) so a pre-warm never stalls a frame.  True once cached."""
    if getattr(sector_data, "mesh_cache", None) is not None:
        return True
    progress = getattr(sector_data, "mesh_progress", None)
    if progress is None:
        progress = [MC.MeshBuilder(), 0]
    mb, i = progress
    pieces = sector_data.pieces
    t0 = time.perf_counter()
    while i < len(pieces):
        emit_pieces(mb, pieces[i:i + 12], height_fn)
        i += 12
        if time.perf_counter() - t0 >= budget_s:
            break
    if i < len(pieces):
        sector_data.mesh_progress = [mb, i]
        return False
    rec, idx = mb.arrays()
    if rec.shape[0] and MC.city_shader(gsg) is None:
        rec = bake_lit(rec)
    sector_data.mesh_cache = (rec, idx)
    sector_data.mesh_progress = None
    return True


def finish_arrays(parent, name, rec, idx, gsg, light: Lighting, *, tag: str, shaded_tag: str):
    if rec.shape[0] == 0:
        return None
    shader = MC.city_shader(gsg)
    np_ = parent.attachNewNode(MC.make_node(name, rec, idx))
    np_.setTextureOff(10)
    np_.setTransparency(TransparencyAttrib.MNone)
    if shader is not None:
        apply_lit_shader(np_, shader, light)
    else:
        np_.setLightOff(1)
    np_.setPythonTag(tag, int(idx.shape[0] // 3))
    np_.setPythonTag(shaded_tag, 1 if shader is not None else 0)
    return np_


def bake_model(name, mb, gsg, light: Lighting):
    rec, idx = mb.arrays()
    shader = MC.city_shader(gsg)
    if shader is None:
        rec = bake_lit(rec)
    np_ = NodePath(MC.make_node(name, rec, idx))
    if shader is not None:
        apply_lit_shader(np_, shader, light)
    else:
        np_.setLightOff(1)
    return np_


def mote():
    mb = MC.MeshBuilder()
    mb.prism(0.0, 0.0, -0.5, 0.05, 0.5, 0.5, 4, (1.0, 1.0, 1.0, 1.0))
    mb.prism(0.0, 0.0, 0.0, 0.5, 0.05, 0.5, 4, (1.0, 1.0, 1.0, 1.0))
    return mb


def sky_dome(horizon, mid, zenith):
    """Unit sky dome: ``horizon`` below 0.1 rad, blending to ``mid`` and ``zenith``."""
    mb = MC.MeshBuilder()
    lats = (-0.25, 0.0, 0.10, 0.28, 0.60, 1.0, 1.5708)

    def colour(lat):
        if lat <= 0.10:
            return horizon
        if lat <= 0.60:
            t = (lat - 0.10) / 0.50
            return tuple(horizon[i] + (mid[i] - horizon[i]) * t for i in range(4))
        t = min(1.0, (lat - 0.60) / 0.97)
        return tuple(mid[i] + (zenith[i] - mid[i]) * t for i in range(4))
    lons = 32
    for i in range(len(lats) - 1):
        c0, c1 = colour(lats[i]), colour(lats[i + 1])
        for k in range(lons):
            a0, a1 = math.tau * k / lons, math.tau * (k + 1) / lons
            quad = [(math.cos(la) * math.cos(a), math.cos(la) * math.sin(a), math.sin(la)) for la, a in ((lats[i], a0), (lats[i], a1), (lats[i + 1], a1), (lats[i + 1], a0))]
            base = mb.count
            for q, c in zip(quad, (c0, c0, c1, c1)):
                mb.rec.append((q[0], q[1], q[2], 0.0, 0.0, 1.0, c[0], c[1], c[2], c[3], 0.0, 0.0))
            mb.idx.extend((base, base + 1, base + 2, base, base + 2, base + 3))
            mb.count += 4
    return mb


def setup_sky_node(sky, order: int):
    """Background-bin, unlit, fog-free sky geometry that follows the player."""
    sky.setLightOff(1)
    sky.setShaderOff(100)
    sky.setTextureOff(10)
    sky.setFogOff(1)
    sky.setTwoSided(True)
    sky.setDepthWrite(False)
    sky.setDepthTest(False)
    sky.setBin("background", order)
    sky.setTransparency(TransparencyAttrib.MAlpha)
    sky.setColorScale(1.0, 1.0, 1.0, 0.0)


class Walker:
    """A body with swinging legs (two for people, four for animals)."""

    def __init__(self, parent, body, leg, hips):
        self.root = parent.attachNewNode("region-walker")
        body.instanceTo(self.root)
        self.legs = []
        for hx, hy, hz, phase in hips:
            pivot = self.root.attachNewNode("leg")
            pivot.setPos(hx, hy, hz)
            leg.instanceTo(pivot)
            self.legs.append((pivot, phase))
        self.gait = 0.0
        self.ground_z = None
        self.ground_clock = 0.0

    def pose(self, x, y, z, heading, walking, dt, *, stride=2.6, swing=24.0, roll=0.0, bob=0.04):
        if walking:
            self.gait += dt * stride
        self.root.setPos(x, y, z + (abs(math.sin(self.gait * math.pi)) * bob if walking else 0.0))
        self.root.setHpr(math.degrees(heading) - 90.0, 0.0, math.degrees(roll))
        amp = swing if walking else 0.0
        for pivot, phase in self.legs:
            pivot.setP(math.sin((self.gait + phase) * math.pi) * amp)

    def ground(self, ground_fn, x, y, dt):
        """Ground under a slow walker changes little: sample every 0.2 s."""
        self.ground_clock -= dt
        if self.ground_z is None or self.ground_clock <= 0.0:
            self.ground_z = float(ground_fn(x, y))
            self.ground_clock = 0.2
        return self.ground_z

    def destroy(self):
        self.root.removeNode()
