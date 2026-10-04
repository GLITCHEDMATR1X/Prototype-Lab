"""Ice ring visuals (Pass 282.54): glacier towns, ice spires and peaceful life.

* ``build_ice_node`` - one merged, lit mesh per Ice sector from the pieces in
  ``ice_civilization`` (city shader: crystal material with a fresnel rim and
  inner glow, packed-snow domes, amber lanterns and doorways).
* ``IceLifeDirector`` - Frostkin villagers, lake skaters and frost-mammoth
  herds near the player, drifting light motes in the towns, aurora curtains
  and a cold frost-haze sky dome that blends in at the ring edges.

Life is driven by pure pose functions of time, so nothing accumulates or
drifts however long the game runs.
"""
from __future__ import annotations

import math

from panda3d.core import ColorBlendAttrib, NodePath, TransparencyAttrib

from holoverse import ice_civilization as IC
from holoverse import metropolis_city as MC
from holoverse import region_mesh_kit as RMK

ICE_LIGHT = RMK.Lighting(sun=(0.78, 0.82, 0.90), sky=(0.40, 0.48, 0.62), bounce=(0.36, 0.42, 0.52))
ICE_HAZE_RGB = (0.34, 0.50, 0.66)       # fog + dome horizon
FROST_HORIZON = (0.34, 0.50, 0.66, 1.0)
FROST_MID = (0.10, 0.20, 0.36, 0.95)
FROST_ZENITH = (0.02, 0.05, 0.13, 0.80)
AURORA_RGB = ((0.25, 1.00, 0.62), (0.30, 0.85, 1.00), (0.75, 0.42, 1.00))
ROBE_TONES = ((0.20, 0.30, 0.56), (0.16, 0.42, 0.46), (0.42, 0.26, 0.48), (0.80, 0.75, 0.66))
FUR_TONES = ((0.40, 0.33, 0.29), (0.74, 0.76, 0.80), (0.52, 0.45, 0.38))
EYE_GLOW = (0.55, 0.95, 1.00)


def sector_arrays(sector_data, height_fn, gsg=None):
    return RMK.sector_arrays(sector_data, height_fn, gsg)


def build_ice_node(parent, sector_data, height_fn, gsg=None):
    rec, idx = RMK.sector_arrays(sector_data, height_fn, gsg)
    return RMK.finish_arrays(parent, f"ice-civilization-{sector_data.sector:02d}", rec, idx, gsg, ICE_LIGHT, tag="ice_triangles", shaded_tag="ice_shaded")


# --------------------------------------------------------------------------
# Creature models (built once, instanced)
# --------------------------------------------------------------------------
def _frostkin_body(tone):
    """Frostkin, facing +y, feet at z = 0 (legs are separate)."""
    mb = MC.MeshBuilder()
    robe = (*tone, 0.5)
    trim = (min(1.0, tone[0] * 1.5 + 0.15), min(1.0, tone[1] * 1.5 + 0.15), min(1.0, tone[2] * 1.5 + 0.15), 0.5)
    mb.prism(0.0, 0.0, 0.42, 0.40, 0.24, 0.98, 8, robe)
    mb.prism(0.0, 0.0, 0.42, 0.42, 0.41, 0.10, 8, trim)
    mb.prism(0.0, 0.0, 1.22, 0.36, 0.28, 0.16, 8, trim)                    # shoulder mantle
    mb.dome(0.0, 0.0, 1.36, 0.22, (0.86, 0.90, 0.96, 0.5), rings=4, sides=10)  # pale face/head
    mb.dome(0.0, -0.03, 1.40, 0.25, robe, rings=4, sides=10, squash=1.15)  # hood
    mb.prism(0.0, -0.02, 1.62, 0.12, 0.0, 0.22, 6, robe, lean=(0.0, -0.10))
    for side in (-0.075, 0.075):
        mb.box(side, 0.215, 1.47, 0.05, 0.02, 0.035, (*EYE_GLOW, 0.0))
    # Arms folded into the sleeves, one carrying a small lantern.
    for side in (-1.0, 1.0):
        mb.obox(side * 0.33, 0.06, 0.82, 0.14, 0.14, 0.40, 0.0, robe)
    mb.box(0.36, 0.14, 0.70, 0.12, 0.12, 0.14, (1.0, 0.70, 0.34, 0.0))
    return mb


def _frostkin_leg():
    mb = MC.MeshBuilder()
    mb.box(0.0, 0.0, -0.50, 0.11, 0.11, 0.50, (0.14, 0.15, 0.20, 0.5))
    mb.box(0.0, 0.04, -0.52, 0.12, 0.20, 0.08, (0.30, 0.22, 0.18, 0.5))
    return mb


def _mammoth_body(tone):
    """Frost mammoth, facing +y, ~3.4 m at the shoulder.  Legs separate (hips z 1.7)."""
    mb = MC.MeshBuilder()
    fur = (*tone, 0.5)
    dark = (tone[0] * 0.62, tone[1] * 0.62, tone[2] * 0.62, 0.5)
    ivory = (0.92, 0.88, 0.78, 0.5)
    mb.ellipsoid(0.0, -0.1, 2.15, 1.35, 2.30, 1.30, fur)                   # barrel body
    mb.ellipsoid(0.0, 0.75, 3.05, 1.05, 1.25, 0.85, fur, rings=6, sides=12)  # shoulder hump
    mb.ellipsoid(0.0, -0.1, 1.45, 1.42, 2.15, 0.62, dark, rings=6, sides=14)  # shaggy under-fur
    mb.ellipsoid(0.0, 2.25, 2.55, 0.82, 0.95, 0.95, fur, rings=6, sides=12)  # head
    mb.ellipsoid(0.0, 2.10, 3.30, 0.55, 0.60, 0.42, fur, rings=5, sides=10)  # crown dome
    trunk = [(0.0, 3.00, 2.45), (0.0, 3.30, 1.90), (0.0, 3.40, 1.25), (0.0, 3.30, 0.65), (0.0, 3.48, 0.32)]
    mb.sweep(trunk, 0.40, 0.40, dark)
    for side in (-1.0, 1.0):
        tusk = [(side * 0.42, 2.95, 2.00), (side * 0.60, 3.55, 1.50), (side * 0.72, 4.15, 1.50), (side * 0.62, 4.55, 1.95), (side * 0.42, 4.60, 2.40)]
        mb.sweep(tusk, 0.17, 0.17, ivory)
        mb.box(side * 0.62, 2.92, 2.75, 0.08, 0.04, 0.06, (*EYE_GLOW, 0.0))
        mb.ellipsoid(side * 0.86, 1.95, 2.55, 0.12, 0.55, 0.65, dark, rings=4, sides=8)   # ears
    mb.sweep([(0.0, -2.30, 2.40), (0.0, -2.60, 1.80), (0.0, -2.62, 1.30)], 0.14, 0.14, dark)
    return mb


def _mammoth_leg(tone):
    mb = MC.MeshBuilder()
    mb.prism(0.0, 0.0, -1.70, 0.40, 0.50, 1.75, 10, (*tone, 0.5))
    mb.ellipsoid(0.0, 0.0, -0.35, 0.56, 0.56, 0.50, (*tone, 0.5), rings=5, sides=10)     # fur at the thigh
    mb.prism(0.0, 0.0, -1.70, 0.50, 0.46, 0.25, 10, (tone[0] * 0.5, tone[1] * 0.5, tone[2] * 0.5, 0.5))
    return mb


def _frost_dome():
    return RMK.sky_dome(FROST_HORIZON, FROST_MID, FROST_ZENITH)


def _aurora():
    """Three wavy curtains on a unit-ish sky shell (scaled by the director)."""
    mb = MC.MeshBuilder()
    for c, (rgb, a_mid, spread, lo, hi) in enumerate(((AURORA_RGB[0], 0.6, 1.9, 0.30, 0.62), (AURORA_RGB[1], 2.9, 1.5, 0.36, 0.70), (AURORA_RGB[2], 4.6, 1.4, 0.40, 0.66))):
        cols = 64
        for k in range(cols):
            t0, t1 = k / cols, (k + 1) / cols
            quad = []
            for t, z in ((t0, lo), (t1, lo), (t1, hi), (t0, hi)):
                a = a_mid + (t - 0.5) * spread
                wob = 0.92 + 0.06 * math.sin(t * 17.0 + c) + 0.04 * math.sin(t * 41.0 + c * 2.0)
                quad.append((math.cos(a) * wob, math.sin(a) * wob, z + 0.05 * math.sin(t * 9.0 + c)))
            fade = math.sin(min(t0, 1.0) * math.pi) ** 0.8
            fade1 = math.sin(min(t1, 1.0) * math.pi) ** 0.8
            base = mb.count
            for q, f, top in zip(quad, (fade, fade1, fade1, fade), (0, 0, 1, 1)):
                alpha = (0.55 if not top else 0.0) * f
                tint = rgb if not top else (rgb[2] * 0.6 + 0.3, rgb[0] * 0.3, rgb[1])
                mb.rec.append((q[0], q[1], q[2], 0.0, 0.0, 1.0, tint[0], tint[1], tint[2], alpha, 0.0, 0.0))
            mb.idx.extend((base, base + 1, base + 2, base, base + 2, base + 3))
            mb.count += 4
    return mb


def _bake_model(name, mb, gsg):
    return RMK.bake_model(name, mb, gsg, ICE_LIGHT)


_Walker = RMK.Walker


_MODEL_CACHE = {}


def _models(gsg):
    """Creature templates, built once per process (re-entering Ice is free)."""
    key = MC.city_shader(gsg) is not None
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = {
            "kin_bodies": [_bake_model(f"frostkin-{i}", _frostkin_body(t), gsg) for i, t in enumerate(ROBE_TONES)],
            "kin_leg": _bake_model("frostkin-leg", _frostkin_leg(), gsg),
            "mammoth_bodies": [_bake_model(f"mammoth-{i}", _mammoth_body(t), gsg) for i, t in enumerate(FUR_TONES)],
            "mammoth_legs": [_bake_model(f"mammoth-leg-{i}", _mammoth_leg(t), gsg) for i, t in enumerate(FUR_TONES)],
            "sky": (_frost_dome().arrays(), _aurora().arrays(), RMK.mote().arrays()),
        }
    return _MODEL_CACHE[key]


class IceLifeDirector:
    """Owns the visible life of the Ice ring around the player."""

    def __init__(self, world_root, gsg=None):
        self.root = world_root.attachNewNode("ice-life-root")
        self.gsg = gsg
        models = _models(gsg)
        self.kin_bodies = models["kin_bodies"]
        self.kin_leg = models["kin_leg"]
        self.mammoth_bodies = models["mammoth_bodies"]
        self.mammoth_legs = models["mammoth_legs"]
        dome_arrays, aurora_arrays, mote_arrays = models["sky"]
        self.towns = {}      # key -> dict(town, villagers, views, skaters, motes)
        self.herds = {}      # key -> (herd, views)
        # Glow motes (additive, unlit).
        self.fx_root = self.root.attachNewNode("ice-fx")
        self.fx_root.setLightOff(1)
        self.fx_root.setShaderOff(100)
        self.fx_root.setTextureOff(10)
        self.fx_root.setDepthWrite(False)
        self.fx_root.setTwoSided(True)
        self.fx_root.setBin("fixed", 40)
        self.fx_root.setTransparency(TransparencyAttrib.MAlpha)
        self.fx_root.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        rec, idx = mote_arrays
        self.mote_template = NodePath(MC.make_node("ice-mote", rec, idx))
        sky_parent = world_root.getParent() if not world_root.getParent().isEmpty() else self.root
        rec, idx = dome_arrays
        self.dome = sky_parent.attachNewNode(MC.make_node("ice-frost-dome", rec, idx))
        self.dome.setScale(395.0)
        rec, idx = aurora_arrays
        self.aurora = sky_parent.attachNewNode(MC.make_node("ice-aurora", rec, idx))
        self.aurora.setScale(380.0, 380.0, 330.0)
        for i, sky in enumerate((self.dome, self.aurora)):
            RMK.setup_sky_node(sky, 11 + i)
        self.aurora.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        self.elapsed = 0.0

    # -- spawning -----------------------------------------------------------------
    def _spawn_town(self, town):
        villagers = IC.town_villagers(town)
        views = [_Walker(self.root, self.kin_bodies[v.tint % len(self.kin_bodies)], self.kin_leg, ((-0.12, 0.0, 0.52, 0.0), (0.12, 0.0, 0.52, 1.0))) for v in villagers]
        skaters = []
        if town.lake is not None:
            for i in range(4):
                skaters.append(_Walker(self.root, self.kin_bodies[(i + 1) % len(self.kin_bodies)], self.kin_leg, ((-0.12, 0.0, 0.52, 0.0), (0.12, 0.0, 0.52, 1.0))))
        motes = []
        for i in range(14):
            m = self.mote_template.instanceTo(self.fx_root)
            m.setScale(0.22 + 0.10 * (i % 3))
            rgb = (1.0, 0.78, 0.45) if i % 3 == 0 else (0.55, 0.92, 1.0)
            m.setColorScale(rgb[0], rgb[1], rgb[2], 0.55)
            motes.append(m)
        self.towns[town.key] = {"town": town, "villagers": villagers, "views": views, "skaters": skaters, "motes": motes}

    def _spawn_herd(self, herd):
        views = []
        for i in range(herd.count):
            tone = (herd.seed + i) % len(FUR_TONES)
            hips = ((-0.8, 1.3, 1.7, 0.0), (0.8, 1.3, 1.7, 1.0), (-0.8, -1.3, 1.7, 1.0), (0.8, -1.3, 1.7, 0.0))
            w = _Walker(self.root, self.mammoth_bodies[tone], self.mammoth_legs[tone], hips)
            scale = 0.85 + 0.12 * ((herd.seed + i * 3) % 3)
            w.root.setScale(scale if i else 1.1)
            views.append(w)
        self.herds[herd.key] = (herd, views)

    def _despawn_town(self, key):
        entry = self.towns.pop(key)
        for w in entry["views"] + entry["skaters"]:
            w.destroy()
        for m in entry["motes"]:
            m.removeNode()

    def _despawn_herd(self, key):
        for w in self.herds.pop(key)[1]:
            w.destroy()

    # -- frame --------------------------------------------------------------------
    def update(self, dt, *, player, sectors, ground, elapsed, sky=1.0, eye_z=None):
        dt = max(0.0, min(0.1, float(dt)))
        self.elapsed = float(elapsed)
        px, py = float(player[0]), float(player[1])
        ez = float(eye_z) if eye_z is not None else ground(px, py) + 3.0
        sky = max(0.0, min(1.0, float(sky)))
        self.dome.setPos(px, py, ez)
        self.dome.setColorScale(1.0, 1.0, 1.0, sky)
        self.aurora.setPos(px, py, ez)
        self.aurora.setH((self.elapsed * 0.6) % 360.0)
        pulse = 0.75 + 0.25 * math.sin(self.elapsed * 0.21) * math.sin(self.elapsed * 0.13 + 1.0)
        self.aurora.setColorScale(1.0, 1.0, 1.0, sky * pulse)

        want_towns, want_herds = {}, {}
        for data in sectors:
            for town in data.towns:
                if math.hypot(town.x - px, town.y - py) <= IC.LIFE_ACTIVE_RADIUS:
                    want_towns[town.key] = town
            for herd in data.herds:
                if math.hypot(herd.x - px, herd.y - py) <= IC.LIFE_ACTIVE_RADIUS:
                    want_herds[herd.key] = herd
        for key in [k for k in self.towns if k not in want_towns]:
            self._despawn_town(key)
        for key in [k for k in self.herds if k not in want_herds]:
            self._despawn_herd(key)
        for key, town in want_towns.items():
            if key not in self.towns:
                self._spawn_town(town)
        for key, herd in want_herds.items():
            if key not in self.herds:
                self._spawn_herd(herd)

        t = self.elapsed
        for entry in self.towns.values():
            town = entry["town"]
            for v, w in zip(entry["villagers"], entry["views"]):
                x, y, heading, walking = IC.villager_pose(town, v, t)
                w.pose(x, y, w.ground(ground, x, y, dt), heading, walking, dt)
            if town.lake is not None:
                for i, w in enumerate(entry["skaters"]):
                    x, y, heading, lean = IC.skater_pose(town.lake, i, t)
                    w.pose(x, y, town.lake.z, heading, True, dt, stride=0.9, swing=16.0, roll=lean, bob=0.0)
            for i, m in enumerate(entry["motes"]):
                a = i * 2.399 + t * (0.05 + 0.01 * (i % 5))
                rr = 8.0 + (i * 7.3) % 52.0
                m.setPos(town.x + math.cos(a) * rr, town.y + math.sin(a) * rr, town.z + 2.5 + (i % 4) * 1.6 + math.sin(t * 0.7 + i) * 0.8)
        for herd, views in self.herds.values():
            for i, w in enumerate(views):
                x, y, heading, walking = IC.mammoth_pose(herd, i, t)
                w.pose(x, y, w.ground(ground, x, y, dt), heading, walking, dt, stride=0.7, swing=14.0, bob=0.06)

    def counts(self):
        return {
            "towns": len(self.towns),
            "villagers": sum(len(e["views"]) for e in self.towns.values()),
            "skaters": sum(len(e["skaters"]) for e in self.towns.values()),
            "mammoths": sum(len(v[1]) for v in self.herds.values()),
            "motes": sum(len(e["motes"]) for e in self.towns.values()),
        }

    def destroy(self):
        for key in list(self.towns):
            self._despawn_town(key)
        for key in list(self.herds):
            self._despawn_herd(key)
        for sky in (self.dome, self.aurora):
            if sky is not None and not sky.isEmpty():
                sky.removeNode()
        self.root.removeNode()
