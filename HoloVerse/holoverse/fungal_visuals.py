"""Mushroom ring visuals (Pass 282.56): the alien fungal world and its life.

* ``build_fungal_node`` - one merged, lit mesh per Mushroom sector from the
  pieces in ``fungal_civilization`` (city shader; glowing gills, spots and
  windows are emissive, the mycelium pools use the crystal sheen).
* ``FungalLifeDirector`` - Sporekin villagers in their hollows, spore jellies
  drifting over groves and towns, spores rising from vents, the cyan beam of
  the REDACTED port, and an alien sky: a teal-to-violet dome with a ringed
  gas giant and two small moons, blended in at the ring edges.

Life is driven by pure pose functions of time, so nothing accumulates or
drifts however long the game runs.
"""
from __future__ import annotations

import math

from panda3d.core import ColorBlendAttrib, NodePath, TransparencyAttrib

from holoverse import fungal_civilization as FC
from holoverse import metropolis_city as MC
from holoverse import region_mesh_kit as RMK

FUNGAL_LIGHT = RMK.Lighting(sun=(0.78, 0.84, 0.80), sky=(0.34, 0.44, 0.48), bounce=(0.22, 0.34, 0.32))
FUNGAL_HAZE_RGB = (0.14, 0.30, 0.31)        # fog + dome horizon
SKY_HORIZON = (0.14, 0.30, 0.31, 1.0)
SKY_MID = (0.16, 0.12, 0.28, 0.95)
SKY_ZENITH = (0.03, 0.03, 0.10, 0.80)
FOLK_TONES = ((0.86, 0.48, 0.20), (0.20, 0.62, 0.60), (0.56, 0.36, 0.80), (0.70, 0.82, 0.30))
FOLK_HIPS = ((-0.10, 0.0, 0.42, 0.0), (0.10, 0.0, 0.42, 1.0))


def build_fungal_node(parent, sector_data, height_fn, gsg=None):
    rec, idx = RMK.sector_arrays(sector_data, height_fn, gsg)
    return RMK.finish_arrays(parent, f"fungal-civilization-{sector_data.sector:02d}", rec, idx, gsg, FUNGAL_LIGHT,
                             tag="fungal_triangles", shaded_tag="fungal_shaded")


# --------------------------------------------------------------------------
# Models (built once, instanced)
# --------------------------------------------------------------------------
def _sporekin_body(tone):
    """A Sporekin: a pale soft body under a broad cap with glowing gills."""
    mb = MC.MeshBuilder()
    body = (0.84, 0.82, 0.74, 0.5)
    cap = (*tone, 0.5)
    mb.ellipsoid(0.0, 0.0, 0.80, 0.30, 0.26, 0.48, body, rings=5, sides=10)
    mb.ellipsoid(0.0, 0.0, 1.36, 0.50, 0.50, 0.26, cap, rings=5, sides=12)
    mb.prism(0.0, 0.0, 1.20, 0.42, 0.42, 0.06, 12, (tone[0] * 0.5 + 0.5, tone[1] * 0.5 + 0.5, tone[2] * 0.5 + 0.5, 0.0), cap=False, double=True)
    for side in (-0.09, 0.09):
        mb.ellipsoid(side, 0.24, 1.06, 0.05, 0.03, 0.05, (0.55, 1.0, 0.95, 0.0), rings=2, sides=6)
    for side in (-1.0, 1.0):
        mb.obox(side * 0.30, 0.04, 0.70, 0.10, 0.10, 0.36, 0.0, body)
    mb.ellipsoid(0.34, 0.12, 0.66, 0.08, 0.08, 0.10, (1.0, 0.70, 0.30, 0.0), rings=2, sides=6)    # a glow bulb
    return mb


def _sporekin_leg():
    mb = MC.MeshBuilder()
    mb.box(0.0, 0.0, -0.40, 0.09, 0.09, 0.40, (0.62, 0.58, 0.52, 0.5))
    return mb


def _jelly():
    """A spore jelly: a glowing bell with trailing strands (additive, unlit)."""
    mb = MC.MeshBuilder()
    mb.dome(0.0, 0.0, 0.0, 1.0, (1.0, 1.0, 1.0, 1.0), rings=4, sides=12, squash=0.7)
    for k in range(6):
        a = math.tau * k / 6.0
        path = [(math.cos(a) * 0.55, math.sin(a) * 0.55, 0.0), (math.cos(a) * 0.62, math.sin(a) * 0.62, -0.9),
                (math.cos(a) * 0.48, math.sin(a) * 0.48, -1.8), (math.cos(a) * 0.58, math.sin(a) * 0.58, -2.6)]
        mb.sweep(path, 0.08, 0.08, (1.0, 1.0, 1.0, 0.6))
    return mb


def _beam():
    """The port beam: two open cylinders fading upward (additive)."""
    mb = MC.MeshBuilder()
    for radius, alpha in ((1.0, 0.55), (0.55, 0.85)):
        sides = 24
        for k in range(sides):
            a0, a1 = math.tau * k / sides, math.tau * (k + 1) / sides
            p = [(math.cos(a0) * radius, math.sin(a0) * radius, 0.0), (math.cos(a1) * radius, math.sin(a1) * radius, 0.0),
                 (math.cos(a1) * radius, math.sin(a1) * radius, 1.0), (math.cos(a0) * radius, math.sin(a0) * radius, 1.0)]
            base = mb.count
            for q, al in zip(p, (alpha, alpha, 0.0, 0.0)):
                mb.rec.append((q[0], q[1], q[2], 0.0, 0.0, 1.0, 0.45, 0.95, 1.0, al, 0.0, 0.0))
            mb.idx.extend((base, base + 1, base + 2, base, base + 2, base + 3))
            mb.count += 4
    return mb


def _gas_giant():
    """A banded gas giant (unit sphere) and its ring (separate)."""
    mb = MC.MeshBuilder()
    rings, sides = 16, 28
    bands = ((0.62, 0.42, 0.68), (0.80, 0.56, 0.52), (0.46, 0.34, 0.62), (0.86, 0.70, 0.60), (0.52, 0.40, 0.70))
    for i in range(rings):
        la0 = -math.pi * 0.5 + math.pi * i / rings
        la1 = -math.pi * 0.5 + math.pi * (i + 1) / rings
        c = bands[i % len(bands)]
        for k in range(sides):
            a0, a1 = math.tau * k / sides, math.tau * (k + 1) / sides
            quad = [(math.cos(la) * math.cos(a), math.cos(la) * math.sin(a), math.sin(la)) for la, a in ((la0, a0), (la0, a1), (la1, a1), (la1, a0))]
            base = mb.count
            for q in quad:
                shade = 0.55 + 0.45 * max(0.0, q[0] * 0.6 + q[2] * 0.4 + 0.3)     # lit from one side
                mb.rec.append((q[0], q[1], q[2], 0.0, 0.0, 1.0, c[0] * shade, c[1] * shade, c[2] * shade, 1.0, 0.0, 0.0))
            mb.idx.extend((base, base + 1, base + 2, base, base + 2, base + 3))
            mb.count += 4
    return mb, _gas_giant_ring_halves()


# Where the gas giant hangs in the fungal sky (the sky follows the player, so the view
# direction to the planet never changes).
GIANT_POS = (-170.0, 260.0, 170.0)
GIANT_HPR = (30.0, 0.0, 14.0)
GIANT_SCALE = 46.0
GIANT_RING_HPR = (0.0, 18.0, 12.0)


def _gas_giant_ring_halves():
    """Pass 282.75: the ring as a far half and a near half.

    The sky bin draws without depth testing, so a single ring drawn after the planet showed its
    far side through the planet.  Splitting it lets the far half draw before the planet (which
    covers it) and the near half after."""
    from panda3d.core import NodePath as _NP, Vec3 as _V3

    sky = _NP("ring-split-sky")
    planet = sky.attachNewNode("planet")
    planet.setPos(*GIANT_POS)
    planet.setHpr(*GIANT_HPR)
    planet.setScale(GIANT_SCALE)
    ring_np = planet.attachNewNode("ring")
    ring_np.setHpr(*GIANT_RING_HPR)
    mat = ring_np.getMat(sky)
    centre = _V3(*GIANT_POS)
    view = _V3(centre)
    view.normalize()
    far, near = MC.MeshBuilder(), MC.MeshBuilder()
    sides = 48
    for k in range(sides):
        a0, a1 = math.tau * k / sides, math.tau * (k + 1) / sides
        mid = mat.xformPoint(_V3(math.cos((a0 + a1) * 0.5) * 1.75, math.sin((a0 + a1) * 0.5) * 1.75, 0.0))
        target = far if (_V3(mid) - centre).dot(view) > 0.0 else near
        for r_in, r_out, al in ((1.35, 1.75, 0.45), (1.80, 2.15, 0.30)):
            quad = [(math.cos(a0) * r_in, math.sin(a0) * r_in, 0.0), (math.cos(a1) * r_in, math.sin(a1) * r_in, 0.0),
                    (math.cos(a1) * r_out, math.sin(a1) * r_out, 0.0), (math.cos(a0) * r_out, math.sin(a0) * r_out, 0.0)]
            base = target.count
            for q in quad:
                target.rec.append((q[0], q[1], q[2], 0.0, 0.0, 1.0, 0.86, 0.78, 0.70, al, 0.0, 0.0))
            target.idx.extend((base, base + 1, base + 2, base, base + 2, base + 3))
            target.count += 4
    return far, near


def _moon(rgb):
    mb = MC.MeshBuilder()
    mb.ellipsoid(0.0, 0.0, 0.0, 1.0, 1.0, 1.0, (*rgb, 1.0), rings=8, sides=14)
    return mb


_MODEL_CACHE = {}


def _models(gsg):
    key = MC.city_shader(gsg) is not None
    if key not in _MODEL_CACHE:
        L = FUNGAL_LIGHT
        planet, ring = _gas_giant()
        _MODEL_CACHE[key] = {
            "folk": [RMK.bake_model(f"sporekin-{i}", _sporekin_body(t), gsg, L) for i, t in enumerate(FOLK_TONES)],
            "folk_leg": RMK.bake_model("sporekin-leg", _sporekin_leg(), gsg, L),
            "arrays": {
                "dome": RMK.sky_dome(SKY_HORIZON, SKY_MID, SKY_ZENITH).arrays(),
                "planet": planet.arrays(), "planet_ring_far": ring[0].arrays(), "planet_ring_near": ring[1].arrays(),
                "moon_a": _moon((0.80, 0.86, 0.90)).arrays(), "moon_b": _moon((0.92, 0.70, 0.46)).arrays(),
                "jelly": _jelly().arrays(), "beam": _beam().arrays(), "mote": RMK.mote().arrays(),
            },
        }
    return _MODEL_CACHE[key]


def _additive(np_):
    np_.setLightOff(1)
    np_.setShaderOff(100)
    np_.setTextureOff(10)
    np_.setDepthWrite(False)
    np_.setTwoSided(True)
    np_.setTransparency(TransparencyAttrib.MAlpha)
    np_.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))


VENT_MOTES = 10
PORT_BEAM_HEIGHT = 140.0


class FungalLifeDirector:
    """Owns the visible life and sky of the Mushroom ring around the player."""

    def __init__(self, world_root, gsg=None):
        self.root = world_root.attachNewNode("fungal-life-root")
        models = _models(gsg)
        self.folk = models["folk"]
        self.folk_leg = models["folk_leg"]
        arrays = models["arrays"]
        self.fx_root = self.root.attachNewNode("fungal-fx")
        _additive(self.fx_root)
        self.fx_root.setBin("fixed", 40)
        self.jelly_template = NodePath(MC.make_node("spore-jelly", *arrays["jelly"]))
        self.mote_template = NodePath(MC.make_node("spore-mote", *arrays["mote"]))
        self.towns = {}
        self.drifts = {}
        self.vents = {}
        self.port_beam = None
        self.port_pos = None
        sky_parent = world_root.getParent() if not world_root.getParent().isEmpty() else self.root
        self.sky = sky_parent.attachNewNode("fungal-sky")
        self.dome = self.sky.attachNewNode(MC.make_node("fungal-sky-dome", *arrays["dome"]))
        self.dome.setScale(395.0)
        RMK.setup_sky_node(self.dome, 11)
        self.dome.setColorScale(1.0, 1.0, 1.0, 1.0)     # the sky group's colour scale does the blending
        self.planet = self.sky.attachNewNode("fungal-gas-giant")
        body = self.planet.attachNewNode(MC.make_node("gas-giant", *arrays["planet"]))
        ring_far = self.planet.attachNewNode(MC.make_node("gas-giant-ring-far", *arrays["planet_ring_far"]))
        ring_near = self.planet.attachNewNode(MC.make_node("gas-giant-ring-near", *arrays["planet_ring_near"]))
        for ring in (ring_far, ring_near):
            ring.setHpr(*GIANT_RING_HPR)
        self.planet.setPos(*GIANT_POS)
        self.planet.setScale(GIANT_SCALE)
        self.planet.setHpr(*GIANT_HPR)
        self.moons = []
        for name, pos, scale in (("moon_a", (210.0, 220.0, 120.0), 9.0), ("moon_b", (260.0, -120.0, 210.0), 5.0)):
            moon = self.sky.attachNewNode(MC.make_node(f"fungal-{name}", *arrays[name]))
            moon.setPos(*pos)
            moon.setScale(scale)
            self.moons.append(moon)
        # far ring half, then the planet over it, then the near half in front (no depth test here)
        for i, node in enumerate([ring_far, body, ring_near] + self.moons):
            RMK.setup_sky_node(node, 12 + i)
            node.setColorScale(1.0, 1.0, 1.0, 1.0)
        for sphere in [body] + self.moons:
            sphere.setTwoSided(False)       # no depth test in the sky bin: cull the far side instead
        self.sky.setColorScale(1.0, 1.0, 1.0, 0.0)
        self.beam_arrays = arrays["beam"]
        self.elapsed = 0.0

    # -- spawning -----------------------------------------------------------------
    def _spawn_town(self, town):
        villagers = FC.town_villagers(town)
        views = [RMK.Walker(self.root, self.folk[v.tint % len(self.folk)], self.folk_leg, FOLK_HIPS) for v in villagers]
        self.towns[town.key] = {"town": town, "villagers": villagers, "views": views}

    def _spawn_drift(self, drift):
        jellies = []
        for i in range(drift.count):
            j = self.jelly_template.instanceTo(self.fx_root)
            tone = FC.GILL_GLOW[(drift.seed + i) % len(FC.GILL_GLOW)]
            j.setPythonTag("tone", tone)
            j.setScale(1.2 + 0.5 * ((drift.seed + i * 3) % 3))
            jellies.append(j)
        self.drifts[drift.key] = (drift, jellies)

    def _spawn_vent(self, key, pos):
        motes = []
        for i in range(VENT_MOTES):
            m = self.mote_template.instanceTo(self.fx_root)
            m.setScale(0.18 + 0.08 * (i % 3))
            motes.append(m)
        self.vents[key] = (pos, motes)

    def _ensure_port(self, pos):
        if self.port_beam is not None:
            return
        self.port_pos = pos
        self.port_beam = self.fx_root.attachNewNode(MC.make_node("redacted-port-beam", *self.beam_arrays))
        self.port_beam.setPos(pos[0], pos[1], pos[2] - 0.5)
        self.port_beam.setScale(4.0, 4.0, PORT_BEAM_HEIGHT)

    # -- frame --------------------------------------------------------------------
    def update(self, dt, *, player, sectors, ground, elapsed, sky=1.0, eye_z=None):
        dt = max(0.0, min(0.1, float(dt)))
        self.elapsed = float(elapsed)
        px, py = float(player[0]), float(player[1])
        ez = float(eye_z) if eye_z is not None else ground(px, py) + 3.0
        sky = max(0.0, min(1.0, float(sky)))
        self.sky.setPos(px, py, ez)
        self.sky.setColorScale(1.0, 1.0, 1.0, sky)
        self.planet.setH((30.0 + self.elapsed * 0.4) % 360.0)
        t = self.elapsed

        want_towns, want_drifts, want_vents = {}, {}, {}
        for data in sectors:
            for town in data.towns:
                if math.hypot(town.x - px, town.y - py) <= FC.LIFE_ACTIVE_RADIUS:
                    want_towns[town.key] = town
            for drift in data.drifts:
                if math.hypot(drift.x - px, drift.y - py) <= FC.LIFE_ACTIVE_RADIUS:
                    want_drifts[drift.key] = drift
            for i, vent in enumerate(data.vents):
                if math.hypot(vent[0] - px, vent[1] - py) <= 450.0:
                    want_vents[f"v{data.sector}:{i}"] = vent
            if data.port is not None:
                self._ensure_port(data.port)
        for key in [k for k in self.towns if k not in want_towns]:
            for w in self.towns.pop(key)["views"]:
                w.destroy()
        for key in [k for k in self.drifts if k not in want_drifts]:
            for j in self.drifts.pop(key)[1]:
                j.removeNode()
        for key in [k for k in self.vents if k not in want_vents]:
            for m in self.vents.pop(key)[1]:
                m.removeNode()
        for key, town in want_towns.items():
            if key not in self.towns:
                self._spawn_town(town)
        for key, drift in want_drifts.items():
            if key not in self.drifts:
                self._spawn_drift(drift)
        for key, vent in want_vents.items():
            if key not in self.vents:
                self._spawn_vent(key, vent)

        for entry in self.towns.values():
            town = entry["town"]
            for v, w in zip(entry["villagers"], entry["views"]):
                x, y, heading, walking = FC.villager_pose(town, v, t)
                w.pose(x, y, w.ground(ground, x, y, dt), heading, walking, dt, stride=2.2, swing=20.0, bob=0.05)
        for drift, jellies in self.drifts.values():
            for i, j in enumerate(jellies):
                x, y, z, pulse = FC.jelly_pose(drift, i, t)
                j.setPos(x, y, z)
                j.setSz(j.getSx() * (0.85 + 0.25 * pulse))
                r, g, b = j.getPythonTag("tone")
                j.setColorScale(r, g, b, 0.22 + 0.30 * pulse)
        for (vx, vy, vz), motes in self.vents.values():
            for i, m in enumerate(motes):
                f = ((t * 0.18 + i / VENT_MOTES) % 1.0)
                m.setPos(vx + math.sin(i * 2.1 + t * 0.7) * (0.6 + f * 3.0), vy + math.cos(i * 1.7 + t * 0.6) * (0.6 + f * 3.0), vz + f * 22.0)
                m.setColorScale(0.55, 1.0, 0.90, 0.65 * (1.0 - f))
        if self.port_beam is not None:
            near = math.hypot(self.port_pos[0] - px, self.port_pos[1] - py) < 1400.0
            if near:
                self.port_beam.show()
                pulse = 0.75 + 0.25 * math.sin(t * 1.6)
                self.port_beam.setColorScale(1.0, 1.0, 1.0, pulse)
            else:
                self.port_beam.hide()

    def counts(self):
        return {
            "towns": len(self.towns),
            "villagers": sum(len(e["views"]) for e in self.towns.values()),
            "jellies": sum(len(d[1]) for d in self.drifts.values()),
            "vents": len(self.vents),
            "port_beam": self.port_beam is not None,
        }

    def destroy(self):
        for entry in self.towns.values():
            for w in entry["views"]:
                w.destroy()
        self.towns.clear()
        self.drifts.clear()
        self.vents.clear()
        if self.sky is not None and not self.sky.isEmpty():
            self.sky.removeNode()
        self.root.removeNode()
