"""Urban ring visuals (Pass 282.53): ruins, war robots, Sable's rig and effects.

* ``build_ruin_node`` - one merged, lit mesh per Urban sector (city shader:
  dark scorched facades, a few burning windows, glowing warning beacons).
* ``UrbanWarDirector`` - spawns the battles near the player, animates the
  robots (walk cycles, aiming, collapse, drop-in respawn), draws tracers,
  muzzle flashes, explosions and smoke, fits Sable with twin cannons and a
  shield that flares when she is hit, and drives her strafing fight.

Effects are unlit, additive (glow) or alpha (smoke) geometry from small
pools, so the frame cost stays flat however long the war runs.
"""
from __future__ import annotations

import math

from panda3d.core import ColorBlendAttrib, TransparencyAttrib, Vec3

from holoverse import metropolis_city as MC
from holoverse import urban_conflict as UC

URBAN_WINDOW_RGB = (1.0, 0.42, 0.10)     # the few "lit" windows read as fires
URBAN_GLASS_RGB = (0.05, 0.05, 0.06)
URBAN_LIT_SHARE = 0.05
KIND_ALPHA = {"facade": 1.0, "plain": 0.5, "emissive": 0.0, "fire": 0.0}

SCRAP_HULL = (0.46, 0.25, 0.12)
SCRAP_DARK = (0.16, 0.12, 0.10)
SCRAP_VISOR = (1.0, 0.62, 0.10)
CHOIR_HULL = (0.27, 0.29, 0.32)
CHOIR_DARK = (0.10, 0.11, 0.13)
CHOIR_EYE = (0.20, 0.95, 1.00)
TRACER_RGB = {UC.SCRAP: (1.0, 0.62, 0.15), UC.CHOIR: (0.25, 0.90, 1.0), UC.SABLE: (1.0, 0.18, 0.22)}
SABLE_SCALE_FALLBACK = 2.3


def _apply_urban_shader(np_, shader):
    from holoverse import ring_ground as RG
    np_.setShader(shader, 50)
    np_.setShaderInput("u_sun_dir", Vec3(*RG.SUN_DIRECTION))
    np_.setShaderInput("u_sun_color", Vec3(0.95, 0.78, 0.62))
    np_.setShaderInput("u_sky_ambient", Vec3(0.52, 0.42, 0.38))
    np_.setShaderInput("u_ground_bounce", Vec3(0.34, 0.20, 0.14))
    np_.setShaderInput("u_window_rgb", Vec3(*URBAN_WINDOW_RGB))
    np_.setShaderInput("u_glass_rgb", Vec3(*URBAN_GLASS_RGB))
    np_.setShaderInput("u_lit_share", URBAN_LIT_SHARE)


def _finish(parent, name, mb, gsg, *, shaded=True):
    rec, idx = mb.arrays()
    if rec.shape[0] == 0:
        return None
    shader = MC.city_shader(gsg) if shaded else None
    if shader is None:
        rec = MC.bake(rec)
    np_ = parent.attachNewNode(MC.make_node(name, rec, idx))
    np_.setTextureOff(10)
    np_.setTransparency(TransparencyAttrib.MNone)
    if shader is not None:
        _apply_urban_shader(np_, shader)
    else:
        np_.setLightOff(1)
    np_.setPythonTag("urban_triangles", int(idx.shape[0] // 3))
    np_.setPythonTag("urban_shaded", 1 if shader is not None else 0)
    return np_


def build_ruin_node(parent, ruins, gsg=None):
    mb = MC.MeshBuilder()
    for b in ruins.boxes:
        rgba = (*b.rgb, KIND_ALPHA.get(b.kind, 0.5))
        mb.obox(b.x, b.y, b.z0, b.sx, b.sy, b.sz, b.heading, rgba, uv_seed=(b.seed % 997) * 3.3)
    return _finish(parent, f"urban-ruins-{ruins.sector:02d}", mb, gsg)


# --------------------------------------------------------------------------
# Robot models (built once, instanced per robot)
# --------------------------------------------------------------------------
def _walker_parts():
    """SCRAP walker, facing +y.  Returns (upper, leg) builders; hips at z = 1.7."""
    upper = MC.MeshBuilder()
    hull = (*SCRAP_HULL, 0.5)
    dark = (*SCRAP_DARK, 0.5)
    upper.box(0.0, 0.0, 1.55, 1.3, 0.8, 0.45, dark)                 # pelvis
    upper.box(0.0, 0.05, 2.0, 1.7, 1.1, 1.25, hull)                 # torso
    upper.box(0.0, 0.25, 2.2, 1.2, 0.8, 0.8, dark)                  # chest plate
    upper.box(0.0, 0.10, 3.25, 0.8, 0.75, 0.55, hull)               # head
    upper.box(0.0, 0.48, 3.38, 0.62, 0.10, 0.16, (*SCRAP_VISOR, 0.0))  # visor
    upper.box(-1.05, 0.0, 2.75, 0.55, 0.9, 0.45, hull)              # shoulders
    upper.box(1.05, 0.0, 2.75, 0.55, 0.9, 0.45, hull)
    upper.box(1.15, 0.55, 2.1, 0.42, 1.9, 0.42, dark)               # arm cannon
    upper.box(1.15, 1.52, 2.1, 0.28, 0.12, 0.28, (*SCRAP_VISOR, 0.0))
    upper.box(-1.1, 0.15, 1.9, 0.35, 0.5, 0.9, dark)                # left arm
    upper.box(0.0, -0.62, 2.3, 0.9, 0.35, 0.9, dark)                # back pack
    upper.box(0.2, -0.75, 3.1, 0.12, 0.12, 0.9, (0.25, 0.25, 0.25, 0.5))  # antenna
    upper.box(0.2, -0.75, 4.0, 0.16, 0.16, 0.16, (1.0, 0.15, 0.10, 0.0))  # antenna light
    upper.box(-0.45, 0.62, 2.55, 0.30, 0.06, 0.30, (*SCRAP_VISOR, 0.0))  # chest vents
    upper.box(0.45, 0.62, 2.55, 0.30, 0.06, 0.30, (*SCRAP_VISOR, 0.0))
    upper.box(-1.05, 0.0, 3.2, 0.60, 0.95, 0.10, (0.30, 0.16, 0.08, 0.5))  # rusted pauldron caps
    upper.box(1.05, 0.0, 3.2, 0.60, 0.95, 0.10, (0.30, 0.16, 0.08, 0.5))
    upper.box(-1.1, 0.55, 1.55, 0.25, 0.5, 0.25, (0.55, 0.55, 0.58, 0.5))  # claw
    leg = MC.MeshBuilder()
    leg.box(0.0, 0.0, -0.85, 0.42, 0.5, 0.85, hull)                 # thigh (pivot at hip, z = 0)
    leg.box(0.0, 0.05, -1.62, 0.34, 0.42, 0.80, dark)               # shin
    leg.box(0.0, 0.18, -1.70, 0.55, 0.85, 0.16, dark, bottom=True)  # foot
    return upper, leg


def _spider_parts():
    """CHOIR spider tank, facing +y.  Returns (body, turret, leg)."""
    body = MC.MeshBuilder()
    hull = (*CHOIR_HULL, 0.5)
    dark = (*CHOIR_DARK, 0.5)
    body.prism(0.0, 0.0, 0.0, 1.35, 1.1, 0.75, 6, hull)
    body.prism(0.0, 0.0, -0.35, 1.0, 1.35, 0.35, 6, dark)
    body.box(0.0, 1.0, 0.25, 1.1, 0.12, 0.16, (*CHOIR_EYE, 0.0))
    body.box(0.0, 0.0, 0.75, 1.5, 1.2, 0.12, (0.20, 0.22, 0.24, 0.5))     # armour plate
    body.box(-1.15, -0.2, 0.25, 0.10, 0.9, 0.12, (*CHOIR_EYE, 0.0))       # flank light strips
    body.box(1.15, -0.2, 0.25, 0.10, 0.9, 0.12, (*CHOIR_EYE, 0.0))
    body.box(0.0, -1.05, 0.15, 0.9, 0.35, 0.45, (0.08, 0.09, 0.10, 0.5))  # rear power cell
    body.box(0.0, -1.24, 0.25, 0.6, 0.06, 0.18, (1.0, 0.25, 0.15, 0.0))
    turret = MC.MeshBuilder()
    turret.box(0.0, 0.0, 0.0, 1.0, 1.1, 0.5, hull)
    turret.box(-0.25, 1.05, 0.18, 0.16, 1.4, 0.16, dark)
    turret.box(0.25, 1.05, 0.18, 0.16, 1.4, 0.16, dark)
    turret.box(0.0, 0.58, 0.32, 0.5, 0.08, 0.10, (*CHOIR_EYE, 0.0))
    turret.box(-0.25, 1.78, 0.18, 0.22, 0.10, 0.22, (*CHOIR_EYE, 0.0))
    turret.box(0.25, 1.78, 0.18, 0.22, 0.10, 0.22, (*CHOIR_EYE, 0.0))
    turret.box(0.38, -0.30, 0.5, 0.08, 0.08, 1.1, (0.30, 0.30, 0.32, 0.5))  # sensor mast
    turret.box(0.38, -0.30, 1.6, 0.20, 0.20, 0.12, (*CHOIR_EYE, 0.0))
    leg = MC.MeshBuilder()
    leg.box(0.9, 0.0, 0.0, 1.8, 0.28, 0.28, dark)                   # upper leg out along +x
    leg.box(1.85, 0.0, -0.75, 0.26, 0.26, 1.5, hull)                # lower leg down to the ground
    return body, turret, leg


def _cone():
    """Searchlight beam: unit-length cone along +y, apex at the origin."""
    mb = MC.MeshBuilder()
    sides = 10
    step = math.tau / sides
    for k in range(sides):
        a0, a1 = k * step, (k + 1) * step
        p0 = (math.cos(a0), 1.0, math.sin(a0))
        p1 = (math.cos(a1), 1.0, math.sin(a1))
        mb.tri((0.0, 0.0, 0.0), p1, p0, (0, 0, 1), (1.0, 1.0, 1.0, 1.0))
    return mb


SMOG_HORIZON = (0.42, 0.15, 0.07, 1.0)
SMOG_MID = (0.17, 0.065, 0.04, 0.92)
SMOG_ZENITH = (0.05, 0.02, 0.02, 0.70)


def _smog_dome():
    """Burning-smog sky dome: hot red-brown horizon fading to a dark zenith."""
    mb = MC.MeshBuilder()
    lats = (-0.25, 0.0, 0.12, 0.30, 0.60, 1.0, 1.5708)
    def colour(lat):
        if lat <= 0.12:
            return SMOG_HORIZON
        if lat <= 0.60:
            t = (lat - 0.12) / 0.48
            return tuple(SMOG_HORIZON[i] + (SMOG_MID[i] - SMOG_HORIZON[i]) * t for i in range(4))
        t = min(1.0, (lat - 0.60) / 0.97)
        return tuple(SMOG_MID[i] + (SMOG_ZENITH[i] - SMOG_MID[i]) * t for i in range(4))
    lons = 32
    for i in range(len(lats) - 1):
        la0, la1 = lats[i], lats[i + 1]
        c0, c1 = colour(la0), colour(la1)
        for k in range(lons):
            a0 = math.tau * k / lons
            a1 = math.tau * (k + 1) / lons
            p = [(math.cos(la) * math.cos(a), math.cos(la) * math.sin(a), math.sin(la)) for la, a in ((la0, a0), (la0, a1), (la1, a1), (la1, a0))]
            cols = (c0, c0, c1, c1)
            base = mb.count
            for q, c in zip(p, cols):
                mb.rec.append((q[0], q[1], q[2], 0.0, 0.0, 1.0, c[0], c[1], c[2], c[3], 0.0, 0.0))
            mb.idx.extend((base, base + 1, base + 2, base, base + 2, base + 3))
            mb.count += 4
    return mb


def _unit_box():
    mb = MC.MeshBuilder()
    mb.box(0.0, 0.5, -0.5, 1.0, 1.0, 1.0, (1.0, 1.0, 1.0, 1.0), bottom=True)   # spans y 0..1
    return mb


def _octa():
    mb = MC.MeshBuilder()
    mb.prism(0.0, 0.0, -0.5, 0.05, 0.6, 0.5, 6, (1.0, 1.0, 1.0, 1.0))
    mb.prism(0.0, 0.0, 0.0, 0.6, 0.05, 0.5, 6, (1.0, 1.0, 1.0, 1.0))
    return mb


def _bake_node(name, mb, gsg=None, shaded=False):
    rec, idx = mb.arrays()
    shader = MC.city_shader(gsg) if shaded else None
    if shader is None:
        rec = MC.bake(rec) if shaded else rec
    node = MC.make_node(name, rec, idx)
    return node, shader


class _Effect:
    __slots__ = ("np", "life", "age", "kind", "grow", "rise", "base_scale", "rgba")


class EffectPool:
    def __init__(self, root, name, mb, *, additive: bool, size: int):
        from panda3d.core import NodePath
        self.root = root.attachNewNode(f"urban-fx-{name}")
        self.root.setLightOff(1)
        self.root.setShaderOff(100)
        self.root.setTextureOff(10)
        self.root.setDepthWrite(False)
        self.root.setTwoSided(True)
        self.root.setBin("fixed", 40)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        if additive:
            self.root.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        rec, idx = mb.arrays()
        self.template = NodePath(MC.make_node(f"fx-{name}", rec, idx))
        self.free = []
        self.live = []
        for _ in range(size):
            e = _Effect()
            e.np = self.template.instanceTo(self.root)
            e.np.hide()
            e.life = e.age = 0.0
            self.free.append(e)

    def spawn(self, pos, *, life, rgba, scale=1.0, grow=0.0, rise=0.0, look_to=None, length=None, width=0.12):
        if not self.free:
            if not self.live:
                return None
            e = self.live.pop(0)
        else:
            e = self.free.pop()
        e.life, e.age, e.grow, e.rise, e.base_scale, e.rgba = float(life), 0.0, float(grow), float(rise), float(scale), rgba
        e.np.show()
        e.np.setPos(pos)
        if look_to is not None:
            e.np.lookAt(look_to)
            e.np.setScale(width, max(0.1, float(length)), width)
        else:
            e.np.setHpr(0, 0, 0)
            e.np.setScale(scale)
        e.np.setColorScale(*rgba)
        self.live.append(e)
        return e

    def update(self, dt):
        keep = []
        for e in self.live:
            e.age += dt
            if e.age >= e.life:
                e.np.hide()
                self.free.append(e)
                continue
            t = e.age / e.life
            if e.grow:
                e.np.setScale(e.base_scale * (1.0 + e.grow * t))
            if e.rise:
                e.np.setZ(e.np.getZ() + e.rise * dt)
            r, g, b, a = e.rgba
            e.np.setColorScale(r, g, b, a * (1.0 - t))
            keep.append(e)
        self.live = keep

    def destroy(self):
        self.root.removeNode()


ROBOT_SCALE = {UC.SCRAP: 1.5, UC.CHOIR: 1.6}   # 6 m war walkers, 4 m spider tanks


class _RobotView:
    def __init__(self, parent, unit, models):
        self.uid = unit.uid
        self.team = unit.team
        self.root = parent.attachNewNode(f"urban-robot-{unit.uid}")
        self.root.setScale(ROBOT_SCALE.get(unit.team, 1.0))
        self.legs = []
        if unit.team == UC.SCRAP:
            self.body = models["walker_upper"].instanceTo(self.root)
            for side in (-0.48, 0.48):
                pivot = self.root.attachNewNode("hip")
                pivot.setPos(side, 0.0, 1.7)
                models["walker_leg"].instanceTo(pivot)
                self.legs.append(pivot)
            self.turret = self.body
        else:
            self.body_root = self.root.attachNewNode("spider-body")
            self.body_root.setZ(1.25)
            models["spider_body"].instanceTo(self.body_root)
            self.turret = self.body_root.attachNewNode("turret")
            self.turret.setZ(0.95)
            models["spider_turret"].instanceTo(self.turret)
            for k, h in enumerate((45.0, 135.0, 225.0, 315.0)):
                pivot = self.body_root.attachNewNode("leg")
                pivot.setH(h)
                models["spider_leg"].instanceTo(pivot)
                self.legs.append(pivot)
            self.body = self.body_root
        self.drop = 0.0
        self.dead_age = 0.0

    def sync(self, unit, ground_z, dt):
        if unit.state == "dead":
            self.root.hide()
            return
        self.root.show()
        z = ground_z
        if self.drop > 0.0:
            self.drop = max(0.0, self.drop - dt * 14.0)
            z += self.drop
        self.root.setPos(unit.x, unit.y, z)
        self.root.setH(math.degrees(unit.heading) - 90.0)
        stride = unit.walked * (1.6 if self.team == UC.SCRAP else 2.4)
        if self.team == UC.SCRAP:
            swing = math.sin(stride) * 26.0
            self.legs[0].setP(swing)
            self.legs[1].setP(-swing)
            self.body.setZ(abs(math.cos(stride)) * 0.12)
            self.body.setH(math.degrees(unit.aim - unit.heading) * 0.6)
        else:
            for k, leg in enumerate(self.legs):
                leg.setR(math.sin(stride + k * 1.57) * 9.0)
            self.body_root.setZ(1.25 + math.sin(stride * 2.0) * 0.05)
            self.turret.setH(math.degrees(unit.aim - unit.heading))
        if unit.state == "dying":
            t = 1.0 - max(0.0, unit.timer) / UC.DYING_SECONDS
            self.root.setR(70.0 * min(1.0, t * 1.6))
            self.root.setZ(z - 1.2 * t)
        else:
            self.root.setR(0.0)

    def destroy(self):
        self.root.removeNode()


class _BattleView:
    def __init__(self, parent, battle, models):
        self.battle = battle
        self.root = parent.attachNewNode(f"urban-battle-{battle.site.key}")
        self.views = {u.uid: _RobotView(self.root, u, models) for u in battle.units}

    def destroy(self):
        self.root.removeNode()


class UrbanWarDirector:
    """Owns the visible war around the player."""

    def __init__(self, world_root, gsg=None):
        self.root = world_root.attachNewNode("urban-war-root")
        self.gsg = gsg
        models = {}
        from panda3d.core import NodePath
        for name, mb in zip(("walker_upper", "walker_leg"), _walker_parts()):
            node, shader = _bake_node(f"urban-{name}", mb, gsg, shaded=True)
            models[name] = NodePath(node)
            if shader is not None:
                _apply_robot_shader(models[name], shader, SCRAP_VISOR)
            else:
                models[name].setLightOff(1)
        for name, mb in zip(("spider_body", "spider_turret", "spider_leg"), _spider_parts()):
            node, shader = _bake_node(f"urban-{name}", mb, gsg, shaded=True)
            models[name] = NodePath(node)
            if shader is not None:
                _apply_robot_shader(models[name], shader, CHOIR_EYE)
            else:
                models[name].setLightOff(1)
        self.models = models
        self.fx_root = self.root.attachNewNode("urban-fx")
        self.tracers = EffectPool(self.fx_root, "tracer", _unit_box(), additive=True, size=48)
        self.flashes = EffectPool(self.fx_root, "flash", _octa(), additive=True, size=40)
        self.smoke = EffectPool(self.fx_root, "smoke", _octa(), additive=False, size=60)
        self.shields = EffectPool(self.fx_root, "shield", _octa(), additive=True, size=6)
        self.battles = {}
        self.searchlights = {}
        beam_root = self.fx_root.attachNewNode("urban-searchlights")
        beam_root.setLightOff(1)
        beam_root.setShaderOff(100)
        beam_root.setDepthWrite(False)
        beam_root.setTwoSided(True)
        beam_root.setBin("fixed", 35)
        beam_root.setTransparency(TransparencyAttrib.MAlpha)
        beam_root.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        from panda3d.core import NodePath
        rec, idx = _cone().arrays()
        self.beam_template = NodePath(MC.make_node("searchlight-beam", rec, idx))
        self.beam_root = beam_root
        rec, idx = _smog_dome().arrays()
        self.smog = world_root.getParent().attachNewNode(MC.make_node("urban-smog-dome", rec, idx)) if not world_root.getParent().isEmpty() else self.root.attachNewNode(MC.make_node("urban-smog-dome", rec, idx))
        self.smog.setScale(395.0)
        self.smog.setLightOff(1)
        self.smog.setShaderOff(100)
        self.smog.setFogOff(1)
        self.smog.setTwoSided(True)
        self.smog.setDepthWrite(False)
        self.smog.setDepthTest(False)
        self.smog.setBin("background", 11)
        self.smog.setTransparency(TransparencyAttrib.MAlpha)
        self.smog.setColorScale(1.0, 1.0, 1.0, 0.0)
        self.sable_rig = None
        self.sable_node = None
        self.smoke_clock = 0.0
        self.stats = {"shots": 0, "deaths": 0, "shield_hits": 0, "sable_kills": 0}

    # -- Sable -----------------------------------------------------------------
    def _ensure_sable_rig(self, sable):
        if self.sable_node is sable and self.sable_rig is not None and not self.sable_rig.isEmpty():
            return
        if self.sable_rig is not None and not self.sable_rig.isEmpty():
            self.sable_rig.removeNode()
        self.sable_node = sable
        mb = MC.MeshBuilder()
        dark = (0.10, 0.10, 0.12, 0.5)
        for side in (-1.0, 1.0):
            mb.box(side * 1.05, 0.25, 1.12, 0.20, 0.95, 0.20, dark)
            mb.box(side * 1.05, 0.76, 1.12, 0.14, 0.08, 0.14, (1.0, 0.20, 0.25, 0.0))
        mb.box(0.0, -0.55, 1.95, 0.5, 0.25, 0.18, (1.0, 0.15, 0.20, 0.0))   # shield emitter
        node, shader = _bake_node("sable-war-rig", mb, self.gsg, shaded=True)
        self.sable_rig = sable.attachNewNode(node)
        if shader is not None:
            _apply_robot_shader(self.sable_rig, shader, (1.0, 0.2, 0.25))
        else:
            self.sable_rig.setLightOff(1)

    # -- frame -----------------------------------------------------------------------
    def _update_searchlights(self, towers, px, py, elapsed):
        wanted = {}
        for x, y, z in towers:
            if math.hypot(x - px, y - py) <= 650.0:
                wanted[(round(x, 1), round(y, 1))] = (x, y, z)
        for key in list(self.searchlights.keys()):
            if key not in wanted:
                self.searchlights.pop(key).removeNode()
        for key, (x, y, z) in wanted.items():
            beam = self.searchlights.get(key)
            if beam is None:
                beam = self.beam_template.instanceTo(self.beam_root)
                beam.setPos(x, y, z)
                beam.setScale(9.0, 70.0, 9.0)
                beam.setColorScale(1.0, 0.86, 0.70, 0.10)
                self.searchlights[key] = beam
            phase = (x * 0.013 + y * 0.007)
            beam.setHpr((elapsed * 18.0 + phase * 57.0) % 360.0, -32.0 + 8.0 * math.sin(elapsed * 0.4 + phase), 0.0)

    def update(self, dt, *, player, r0, r1, ground, sites, sable=None, sable_paused=False, fires=(), elapsed=0.0, towers=(), smog=1.0, eye_z=None):
        dt = max(0.0, min(0.1, float(dt)))
        px, py = float(player[0]), float(player[1])
        self.smog.setPos(px, py, float(eye_z) if eye_z is not None else ground(px, py) + 4.0)
        self.smog.setColorScale(1.0, 1.0, 1.0, max(0.0, min(1.0, float(smog))))
        wanted = {}
        for site in sites:
            if math.hypot(site.x - px, site.y - py) <= UC.SITE_ACTIVE_RADIUS or site.sable:
                wanted[site.key] = site
        for key in list(self.battles.keys()):
            if key not in wanted:
                self.battles.pop(key).destroy()
        for key, site in wanted.items():
            if key not in self.battles:
                seed = abs(int(site.x * 13.0) ^ int(site.y * 7.0)) % 100000
                self.battles[key] = _BattleView(self.root, UC.Battle(site, seed), self.models)

        sable_pos = None
        if sable is not None and not sable.isEmpty():
            self._ensure_sable_rig(sable)
            bx = float(sable.getPythonTag("named_region_bot_base_x") or sable.getX())
            by = float(sable.getPythonTag("named_region_bot_base_y") or sable.getY())
            bz = float(sable.getPythonTag("named_region_bot_base_z") or sable.getZ())
            scale = max(0.5, float(sable.getScale().x) or SABLE_SCALE_FALLBACK)
            sable_battle = next((bv.battle for bv in self.battles.values() if bv.battle.site.sable), None)
            if sable_battle is not None and not sable_paused:
                ox, oy = sable_battle.sable_offset(elapsed)
                hover = math.sin(elapsed * 1.7) * 0.8
                sable.setPos(bx + ox, by + oy, bz + hover)
                sable.setHpr(math.degrees(sable_battle.sable_heading) - 90.0, math.sin(elapsed * 1.3) * 3.0, math.sin(elapsed * 0.9) * 6.0)
            p = sable.getPos()
            sable_pos = (p.x, p.y, p.z + 1.5 * scale)

        for bv in self.battles.values():
            events = bv.battle.update(dt, sable_pos=sable_pos if bv.battle.site.sable else None, sable_active=not sable_paused, ground=ground)
            for unit in bv.battle.units:
                view = bv.views.get(unit.uid)
                if view is not None:
                    view.sync(unit, ground(unit.x, unit.y), dt)
            for ev in events:
                self._event(bv, ev)
        # Smoke from burning ruins near the player.
        self.smoke_clock += dt
        if self.smoke_clock >= 0.35:
            self.smoke_clock = 0.0
            for fx, fy, fz in fires:
                if math.hypot(fx - px, fy - py) < 320.0:
                    j = (math.sin(elapsed * 3.1 + fx) * 1.5, math.cos(elapsed * 2.3 + fy) * 1.5)
                    self.smoke.spawn(Vec3(fx + j[0], fy + j[1], fz + 1.0), life=6.0, rgba=(0.10, 0.09, 0.09, 0.55), scale=3.0, grow=3.5, rise=4.5)
        for pool in (self.tracers, self.flashes, self.smoke, self.shields):
            pool.update(dt)
        self._update_searchlights(towers, px, py, elapsed)

    def _event(self, bv, ev):
        kind = ev[0]
        if kind == "shot":
            _k, shooter, start, end, hit, _target = ev
            team = UC.SABLE if shooter == UC.SABLE else bv.battle.unit(shooter).team
            a, b = Vec3(*start), Vec3(*end)
            rgb = TRACER_RGB[team]
            self.tracers.spawn(a, life=0.12, rgba=(*rgb, 1.0), look_to=b, length=(b - a).length(), width=0.22 if team == UC.SABLE else 0.14)
            self.flashes.spawn(a, life=0.10, rgba=(*rgb, 0.9), scale=0.9)
            if hit:
                self.flashes.spawn(b, life=0.18, rgba=(1.0, 0.85, 0.5, 0.8), scale=0.8, grow=1.0)
            self.stats["shots"] += 1
        elif kind == "death":
            u = bv.battle.unit(ev[1])
            if u is not None:
                p = Vec3(u.x, u.y, bv.views[u.uid].root.getZ() + 1.5)
                self.flashes.spawn(p, life=0.55, rgba=(1.0, 0.55, 0.15, 1.0), scale=2.5, grow=2.4)
                for k in range(3):
                    self.smoke.spawn(p + Vec3(k - 1.0, 0.5 - k * 0.5, 0.5), life=4.0, rgba=(0.12, 0.10, 0.09, 0.6), scale=2.0, grow=3.0, rise=3.0)
            self.stats["deaths"] += 1
            if bv.battle.site.sable:
                self.stats["sable_kills"] = bv.battle.sable_kills + 0
        elif kind == "respawn":
            view = bv.views.get(ev[1])
            if view is not None:
                view.drop = 14.0
        elif kind == "shield":
            if self.sable_node is not None and not self.sable_node.isEmpty():
                p = self.sable_node.getPos()
                scale = max(0.5, float(self.sable_node.getScale().x))
                self.shields.spawn(Vec3(p.x, p.y, p.z + 1.5 * scale), life=0.28, rgba=(1.0, 0.25, 0.30, 0.55), scale=4.2 * scale / 2.3, grow=0.25)
            self.stats["shield_hits"] += 1

    def counts(self):
        return {
            "battles": len(self.battles),
            "robots": sum(len(bv.views) for bv in self.battles.values()),
            "live_effects": len(self.tracers.live) + len(self.flashes.live) + len(self.smoke.live) + len(self.shields.live),
            "searchlights": len(self.searchlights),
            **self.stats,
        }

    def destroy(self):
        for bv in self.battles.values():
            bv.destroy()
        self.battles.clear()
        if self.sable_rig is not None and not self.sable_rig.isEmpty():
            self.sable_rig.removeNode()
        self.sable_rig = None
        if self.smog is not None and not self.smog.isEmpty():
            self.smog.removeNode()
        self.root.removeNode()


def _apply_robot_shader(np_, shader, eye_rgb):
    from holoverse import ring_ground as RG
    np_.setShader(shader, 50)
    np_.setShaderInput("u_sun_dir", Vec3(*RG.SUN_DIRECTION))
    np_.setShaderInput("u_sun_color", Vec3(*RG.SUN_COLOR))
    np_.setShaderInput("u_sky_ambient", Vec3(0.42, 0.38, 0.38))
    np_.setShaderInput("u_ground_bounce", Vec3(0.26, 0.18, 0.14))
    np_.setShaderInput("u_window_rgb", Vec3(*eye_rgb))
    np_.setShaderInput("u_glass_rgb", Vec3(0.05, 0.05, 0.05))
    np_.setShaderInput("u_lit_share", 0.0)
