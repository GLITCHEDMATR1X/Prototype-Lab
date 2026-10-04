"""Desert ring visuals (Pass 282.55): obsidian pyramids, oasis towns and life.

* ``build_desert_node`` - one merged, lit mesh per Desert sector from the
  pieces in ``desert_civilization`` (city shader: obsidian glass with a sun
  glint and violet sheen, layered sandstone, adobe, palms, glowing glyphs).
* ``DesertLifeDirector`` - Dunefolk villagers in the towns, camel caravans on
  the open sand, lantern motes over the towns, drifting dust near the player
  and a warm dusk sky dome that blends in at the ring edges.

Life is driven by pure pose functions of time, so nothing accumulates or
drifts however long the game runs.
"""
from __future__ import annotations

import math

from panda3d.core import ColorBlendAttrib, NodePath, TransparencyAttrib

from holoverse import desert_civilization as DC
from holoverse import metropolis_city as MC
from holoverse import region_mesh_kit as RMK

DESERT_LIGHT = RMK.Lighting(sun=(0.98, 0.84, 0.64), sky=(0.46, 0.38, 0.36), bounce=(0.50, 0.36, 0.24))
DESERT_HAZE_RGB = (0.62, 0.40, 0.25)        # fog + dome horizon
DUSK_HORIZON = (0.62, 0.40, 0.25, 1.0)
DUSK_MID = (0.32, 0.18, 0.20, 0.95)
DUSK_ZENITH = (0.07, 0.05, 0.14, 0.80)
ROBE_TONES = ((0.86, 0.80, 0.68), (0.20, 0.24, 0.52), (0.70, 0.30, 0.18), (0.88, 0.62, 0.20))
WRAP_TONES = ((0.18, 0.30, 0.62), (0.90, 0.86, 0.76), (0.86, 0.66, 0.26), (0.60, 0.16, 0.18))
CAMEL_TONES = ((0.74, 0.56, 0.36), (0.62, 0.45, 0.28), (0.82, 0.68, 0.48))
SADDLE_CLOTH = ((0.72, 0.16, 0.14), (0.16, 0.34, 0.66), (0.92, 0.70, 0.18))


def build_desert_node(parent, sector_data, height_fn, gsg=None):
    rec, idx = RMK.sector_arrays(sector_data, height_fn, gsg)
    return RMK.finish_arrays(parent, f"desert-civilization-{sector_data.sector:02d}", rec, idx, gsg, DESERT_LIGHT,
                             tag="desert_triangles", shaded_tag="desert_shaded")


# --------------------------------------------------------------------------
# Creature models (built once, instanced)
# --------------------------------------------------------------------------
def _dunefolk_body(tone, wrap):
    """Dunefolk, facing +y, feet at z = 0 (legs are separate)."""
    mb = MC.MeshBuilder()
    robe = (*tone, 0.5)
    sash = (*wrap, 0.5)
    mb.prism(0.0, 0.0, 0.40, 0.38, 0.25, 1.00, 10, robe)
    mb.prism(0.0, 0.0, 0.95, 0.31, 0.30, 0.14, 10, sash)                      # sash
    mb.prism(0.0, 0.0, 1.20, 0.33, 0.26, 0.16, 10, robe)                      # shoulders
    mb.ellipsoid(0.0, 0.0, 1.50, 0.17, 0.18, 0.20, (0.56, 0.40, 0.30, 0.5), rings=5, sides=10)   # face
    mb.ellipsoid(0.0, -0.03, 1.60, 0.22, 0.23, 0.15, sash, rings=5, sides=10)  # head wrap
    mb.obox(0.0, -0.20, 1.40, 0.10, 0.28, 0.42, 0.0, sash)                    # wrap tail
    for side in (-0.065, 0.065):
        mb.box(side, 0.17, 1.53, 0.04, 0.02, 0.03, (0.05, 0.04, 0.04, 0.5))
    for side in (-1.0, 1.0):
        mb.obox(side * 0.32, 0.05, 0.80, 0.13, 0.13, 0.42, 0.0, robe)
    mb.ellipsoid(-0.36, 0.12, 0.68, 0.09, 0.09, 0.11, (0.95, 0.58, 0.22, 0.0), rings=4, sides=8)   # small lantern
    return mb


def _dunefolk_leg():
    mb = MC.MeshBuilder()
    mb.box(0.0, 0.0, -0.48, 0.11, 0.11, 0.48, (0.30, 0.22, 0.16, 0.5))
    mb.box(0.0, 0.05, -0.50, 0.12, 0.22, 0.07, (0.36, 0.24, 0.14, 0.5))
    return mb


def _camel_body(tone, cloth):
    """Dromedary, facing +y, ~2.1 m at the shoulder.  Legs separate (hips z 1.55)."""
    mb = MC.MeshBuilder()
    hide = (*tone, 0.5)
    dark = (tone[0] * 0.7, tone[1] * 0.7, tone[2] * 0.7, 0.5)
    mb.ellipsoid(0.0, 0.0, 1.85, 0.55, 1.15, 0.50, hide)                      # barrel
    mb.ellipsoid(0.0, -0.05, 2.35, 0.45, 0.55, 0.50, hide, rings=6, sides=12)  # hump
    mb.ellipsoid(0.0, -0.05, 2.30, 0.58, 0.72, 0.22, (*cloth, 0.5), rings=5, sides=12)   # saddle cloth
    neck = [(0.0, 0.95, 1.95), (0.0, 1.40, 2.10), (0.0, 1.62, 2.55), (0.0, 1.72, 2.85)]
    mb.sweep(neck, 0.34, 0.40, hide)
    mb.ellipsoid(0.0, 1.95, 2.90, 0.17, 0.40, 0.19, hide, rings=5, sides=10)  # head
    for side in (-1.0, 1.0):
        mb.box(side * 0.13, 2.05, 3.00, 0.04, 0.03, 0.04, (0.05, 0.04, 0.03, 0.5))
        mb.obox(side * 0.12, 1.80, 3.10, 0.05, 0.08, 0.14, 0.0, dark)          # ears
        mb.ellipsoid(side * 0.62, -0.05, 1.85, 0.14, 0.32, 0.26, (*cloth, 0.5), rings=4, sides=8)   # packs
    mb.sweep([(0.0, -1.10, 1.95), (0.0, -1.25, 1.60), (0.0, -1.25, 1.25)], 0.10, 0.10, dark)
    return mb


def _camel_leg(tone):
    mb = MC.MeshBuilder()
    mb.prism(0.0, 0.0, -1.55, 0.10, 0.17, 1.55, 8, (*tone, 0.5))
    mb.ellipsoid(0.0, 0.0, -0.75, 0.13, 0.13, 0.12, (*tone, 0.5), rings=4, sides=8)   # knee
    mb.ellipsoid(0.0, 0.05, -1.52, 0.15, 0.20, 0.06, (tone[0] * 0.6, tone[1] * 0.6, tone[2] * 0.6, 0.5), rings=3, sides=8)
    return mb


_MODEL_CACHE = {}


def _models(gsg):
    """Creature templates, built once per process (re-entering the Desert is free)."""
    key = MC.city_shader(gsg) is not None
    if key not in _MODEL_CACHE:
        L = DESERT_LIGHT
        _MODEL_CACHE[key] = {
            "folk": [RMK.bake_model(f"dunefolk-{i}", _dunefolk_body(t, w), gsg, L) for i, (t, w) in enumerate(zip(ROBE_TONES, WRAP_TONES))],
            "folk_leg": RMK.bake_model("dunefolk-leg", _dunefolk_leg(), gsg, L),
            "camels": [RMK.bake_model(f"camel-{i}", _camel_body(t, SADDLE_CLOTH[i % len(SADDLE_CLOTH)]), gsg, L) for i, t in enumerate(CAMEL_TONES)],
            "camel_legs": [RMK.bake_model(f"camel-leg-{i}", _camel_leg(t), gsg, L) for i, t in enumerate(CAMEL_TONES)],
            "sky": (RMK.sky_dome(DUSK_HORIZON, DUSK_MID, DUSK_ZENITH).arrays(), RMK.mote().arrays()),
        }
    return _MODEL_CACHE[key]


FOLK_HIPS = ((-0.11, 0.0, 0.50, 0.0), (0.11, 0.0, 0.50, 1.0))
CAMEL_HIPS = ((-0.35, 0.85, 1.55, 0.0), (0.35, 0.85, 1.55, 1.0), (-0.35, -0.75, 1.55, 1.0), (0.35, -0.75, 1.55, 0.0))
DUST_COUNT = 36


class DesertLifeDirector:
    """Owns the visible life of the Desert ring around the player."""

    def __init__(self, world_root, gsg=None):
        self.root = world_root.attachNewNode("desert-life-root")
        self.gsg = gsg
        models = _models(gsg)
        self.folk = models["folk"]
        self.folk_leg = models["folk_leg"]
        self.camels = models["camels"]
        self.camel_legs = models["camel_legs"]
        dome_arrays, mote_arrays = models["sky"]
        self.towns = {}       # key -> dict(town, villagers, views, motes)
        self.caravans = {}    # key -> (caravan, [(kind, walker)])
        self.fx_root = self.root.attachNewNode("desert-fx")
        self.fx_root.setLightOff(1)
        self.fx_root.setShaderOff(100)
        self.fx_root.setTextureOff(10)
        self.fx_root.setDepthWrite(False)
        self.fx_root.setTwoSided(True)
        self.fx_root.setBin("fixed", 40)
        self.fx_root.setTransparency(TransparencyAttrib.MAlpha)
        self.fx_root.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        rec, idx = mote_arrays
        self.mote_template = NodePath(MC.make_node("desert-mote", rec, idx))
        self.dust = []
        for i in range(DUST_COUNT):
            m = self.mote_template.instanceTo(self.fx_root)
            m.setScale(0.10 + 0.06 * (i % 3))
            m.setColorScale(1.0, 0.82, 0.58, 0.22)
            self.dust.append(m)
        sky_parent = world_root.getParent() if not world_root.getParent().isEmpty() else self.root
        rec, idx = dome_arrays
        self.dome = sky_parent.attachNewNode(MC.make_node("desert-dusk-dome", rec, idx))
        self.dome.setScale(395.0)
        RMK.setup_sky_node(self.dome, 11)
        self.elapsed = 0.0

    # -- spawning -----------------------------------------------------------------
    def _spawn_town(self, town):
        villagers = DC.town_villagers(town)
        views = [RMK.Walker(self.root, self.folk[v.tint % len(self.folk)], self.folk_leg, FOLK_HIPS) for v in villagers]
        motes = []
        for i in range(12):
            m = self.mote_template.instanceTo(self.fx_root)
            m.setScale(0.22 + 0.08 * (i % 3))
            m.setColorScale(1.0, 0.66, 0.30, 0.55)
            motes.append(m)
        self.towns[town.key] = {"town": town, "villagers": villagers, "views": views, "motes": motes}

    def _spawn_caravan(self, caravan):
        members = []
        for i in range(caravan.camels):
            tone = (caravan.seed + i) % len(CAMEL_TONES)
            members.append(("camel", RMK.Walker(self.root, self.camels[tone], self.camel_legs[tone], CAMEL_HIPS)))
        for i in range(caravan.walkers):
            members.append(("folk", RMK.Walker(self.root, self.folk[(caravan.seed + i) % len(self.folk)], self.folk_leg, FOLK_HIPS)))
        # The guide walks at the front: put walkers first in the line.
        members.sort(key=lambda m: 0 if m[0] == "folk" else 1)
        self.caravans[caravan.key] = (caravan, members)

    def _despawn_town(self, key):
        entry = self.towns.pop(key)
        for w in entry["views"]:
            w.destroy()
        for m in entry["motes"]:
            m.removeNode()

    def _despawn_caravan(self, key):
        for _kind, w in self.caravans.pop(key)[1]:
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

        want_towns, want_caravans = {}, {}
        for data in sectors:
            for town in data.towns:
                if math.hypot(town.x - px, town.y - py) <= DC.LIFE_ACTIVE_RADIUS:
                    want_towns[town.key] = town
            for caravan in data.caravans:
                if math.hypot(caravan.x - px, caravan.y - py) <= DC.LIFE_ACTIVE_RADIUS:
                    want_caravans[caravan.key] = caravan
        for key in [k for k in self.towns if k not in want_towns]:
            self._despawn_town(key)
        for key in [k for k in self.caravans if k not in want_caravans]:
            self._despawn_caravan(key)
        for key, town in want_towns.items():
            if key not in self.towns:
                self._spawn_town(town)
        for key, caravan in want_caravans.items():
            if key not in self.caravans:
                self._spawn_caravan(caravan)

        t = self.elapsed
        for entry in self.towns.values():
            town = entry["town"]
            for v, w in zip(entry["villagers"], entry["views"]):
                x, y, heading, walking = DC.villager_pose(town, v, t)
                w.pose(x, y, w.ground(ground, x, y, dt), heading, walking, dt)
            for i, m in enumerate(entry["motes"]):
                a = i * 2.399 + t * (0.04 + 0.01 * (i % 4))
                rr = 10.0 + (i * 6.1) % 60.0
                m.setPos(town.x + math.cos(a) * rr, town.y + math.sin(a) * rr, town.z + 4.0 + (i % 4) * 1.8 + math.sin(t * 0.6 + i) * 0.9)
        for caravan, members in self.caravans.values():
            for i, (kind, w) in enumerate(members):
                x, y, heading = DC.caravan_pose(caravan, i, t)
                if kind == "camel":
                    w.pose(x, y, w.ground(ground, x, y, dt), heading, True, dt, stride=0.9, swing=18.0, bob=0.08)
                else:
                    w.pose(x, y, w.ground(ground, x, y, dt), heading, True, dt, stride=1.6)
        # Dust drifting on the wind round the player (wraps in a 60 m box).
        gz = ez - 3.0
        for i, m in enumerate(self.dust):
            ox = ((i * 37.3 + t * (2.2 + (i % 5) * 0.4)) % 60.0) - 30.0
            oy = ((i * 53.9 + t * (0.6 + (i % 3) * 0.3)) % 60.0) - 30.0
            m.setPos(px + ox, py + oy, gz + 0.6 + (i % 7) * 0.7 + math.sin(t * 1.3 + i) * 0.3)
        self.fx_root.setColorScale(1.0, 1.0, 1.0, sky)

    def counts(self):
        return {
            "towns": len(self.towns),
            "villagers": sum(len(e["views"]) for e in self.towns.values()),
            "caravans": len(self.caravans),
            "camels": sum(1 for c in self.caravans.values() for k, _w in c[1] if k == "camel"),
            "motes": sum(len(e["motes"]) for e in self.towns.values()),
            "dust": len(self.dust),
        }

    def destroy(self):
        for key in list(self.towns):
            self._despawn_town(key)
        for key in list(self.caravans):
            self._despawn_caravan(key)
        if self.dome is not None and not self.dome.isEmpty():
            self.dome.removeNode()
        self.root.removeNode()
