"""HoloVerse Pass 282.59: HoloSpace rebuilt as open deep-space flight.

HoloSpace used to be a small slab of space beside the hub world, around 400 m
from a wireframe Dyson cage (whose inspector drones circled inside it).  This
module replaces what the player sees and flies while ``holospace_active``:

* **Sky layer** - a second display region drawn first, with its own camera that
  copies the main camera's rotation only.  It holds the starfield, the galactic
  band, nebulae, a ringed gas giant and **Dyson Prime**: a massive, finished
  Dyson sphere around a red star.  Because the sky has no translation it can never
  be reached; flying toward it only shrinks its listed distance toward a floor
  (an asymptote), so it grows in the canopy and then stops growing.
* **Local space** - streamed 3 km cells of asteroid clusters and nav beacons
  (solid rock, holo accents), plus world-fixed space dust drawn as streaks along
  the ship's velocity.  A floating origin keeps every placed node near the
  camera, so float precision never jitters, however far the ship travels.
* **Flight** - Elite Dangerous style: a held throttle, mouse as a self-centring
  virtual stick for pitch and yaw, roll on A/D, thrusters on Space/Ctrl and the
  arrow keys, Shift boost with cooldown, Z flight assist (on: the ship holds the
  throttle speed; off: Newtonian drift) and J supercruise (charge, then km/s
  cruising with dust streaks; J again drops back to normal space).
* **Cockpit and HUD** - a solid canopy frame with holo panels, reticle, stick
  marker, throttle bar, speed, mode, and a Dyson Prime marker that follows the
  sphere on screen (or points to it from the screen edge).

Controls are polled (``mouseWatcherNode.isButtonDown``) so nothing here
rebinds a HoloVerse key; TAB, ESC and H keep their host meaning.  The whole
system hides itself when HoloSpace ends, however it ends.
"""
from __future__ import annotations

import math
from random import Random

from panda3d.core import (
    AmbientLight,
    Camera,
    ColorBlendAttrib,
    DirectionalLight,
    Geom,
    GeomLines,
    GeomNode,
    GeomPoints,
    GeomTriangles,
    GeomVertexArrayFormat,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    InternalName,
    KeyboardButton,
    LineSegs,
    NodePath,
    PerspectiveLens,
    PNMImage,
    Point2,
    Point3,
    Shader,
    Texture,
    TextNode,
    TransparencyAttrib,
    Vec3,
    Vec4,
)

# ----------------------------------------------------------------------
# Tuning
# ----------------------------------------------------------------------
MAX_SPEED = 320.0                # m/s at full throttle, normal space
REVERSE_FRACTION = 0.5           # throttle can go to -50%
THRUSTER_SPEED = 95.0            # lateral / vertical thruster target speed
ACCEL = 170.0                    # m/s^2 with flight assist on
FA_OFF_ACCEL = 120.0             # m/s^2 with flight assist off
BOOST_MULT = 1.75
BOOST_TIME = 2.6
BOOST_COOLDOWN = 4.5
THROTTLE_RATE = 0.65             # throttle change per second while W/S held
PITCH_RATE = 46.0                # deg/s at full stick
YAW_RATE = 30.0
ROLL_RATE = 92.0
ANGULAR_RESPONSE = 5.5           # how quickly turn rates follow the stick (FA on)
STICK_GAIN = 0.0045              # stick travel per pixel of mouse motion
STICK_RECENTER = 1.6             # stick self-centring per second (relative mouse)
STICK_DEADZONE = 0.04
SC_CHARGE_TIME = 3.0
SC_MIN_SPEED = 2000.0            # m/s once supercruise engages
SC_MAX_SPEED = 30000.0           # m/s at full throttle in supercruise
SC_RESPONSE = 0.45               # speed blend per second in supercruise
SC_TURN_SCALE = 0.55
SHIP_RADIUS = 6.0

CELL_SIZE = 3000.0
CELL_RADIUS = 2                  # 5 x 5 x 5 cells around the ship
CELL_BUILDS_PER_FRAME = 2
CLUSTER_CHANCE = 0.20           # Pass 282.70: emptier, more open space between rock fields
BEACON_CHANCE = 0.04

DUST_TILE = 160.0
DUST_PER_TILE = 52             # lighter dust: speed still reads, the view stays clean
DUST_RANGE = 230.0

SKY_FAR = 400000.0
STAR_RADIUS = 200000.0
DYSON_SKY_DISTANCE = 60000.0
DYSON_SHELL_RADIUS = 6200.0      # sky units; about 6 degrees across at the start
DYSON_DIRECTION = Vec3(0.30, 0.92, 0.24)
DYSON_START_AU = 40.0
DYSON_FLOOR_AU = 12.0            # it never gets closer than this (about 3x its starting size)
DYSON_APPROACH_LENGTH = 2.6e6    # metres of travel toward it per e-fold of the gap
AU_METRES = 1.496e11

SPACE_RGB = (0.004, 0.006, 0.016)
STAR_RGBA = (1.0, 0.40, 0.26, 1.0)   # Dyson Prime's star is a red giant
HUD_CYAN = (0.40, 0.95, 1.00)
HUD_AMBER = (1.00, 0.72, 0.28)
HUD_RED = (1.00, 0.35, 0.30)

_DUST_VERT = """#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform vec3 u_streak;
uniform float u_alpha;
uniform float u_range;
attribute vec4 p3d_Vertex;
attribute vec4 p3d_Color;
attribute float streak;
varying vec4 v_color;
void main() {
    vec4 p = p3d_Vertex;
    p.xyz += u_streak * streak;
    vec4 eye = p3d_ModelViewMatrix * p;
    float fade = clamp(1.0 - length(eye.xyz) / u_range, 0.0, 1.0);
    v_color = vec4(p3d_Color.rgb, p3d_Color.a * fade * fade * u_alpha * (1.0 - 0.55 * streak));
    gl_Position = p3d_ModelViewProjectionMatrix * p;
}
"""
_DUST_FRAG = """#version 120
varying vec4 v_color;
void main() {
    gl_FragColor = v_color;
}
"""


# ----------------------------------------------------------------------
# Small geometry helpers
# ----------------------------------------------------------------------
def _fmt_c4() -> GeomVertexFormat:
    return GeomVertexFormat.getV3c4()


def _fmt_n3c4() -> GeomVertexFormat:
    return GeomVertexFormat.getV3n3c4()


class _Mesh:
    """Accumulates coloured triangles (optionally with normals) into one Geom."""

    def __init__(self, name: str, normals: bool = False):
        self.name = name
        self.normals = normals
        self.vdata = GeomVertexData(name, _fmt_n3c4() if normals else _fmt_c4(), Geom.UHStatic)
        self.vw = GeomVertexWriter(self.vdata, "vertex")
        self.nw = GeomVertexWriter(self.vdata, "normal") if normals else None
        self.cw = GeomVertexWriter(self.vdata, "color")
        self.tris = GeomTriangles(Geom.UHStatic)
        self.count = 0

    def vertex(self, p, color, n=None) -> int:
        self.vw.addData3(float(p[0]), float(p[1]), float(p[2]))
        if self.nw is not None:
            n = n or (0.0, 0.0, 1.0)
            self.nw.addData3(float(n[0]), float(n[1]), float(n[2]))
        self.cw.addData4(*color)
        self.count += 1
        return self.count - 1

    def tri(self, a, b, c) -> None:
        self.tris.addVertices(a, b, c)

    def quad(self, p0, p1, p2, p3, color, n=None) -> None:
        a, b, c, d = (self.vertex(p, color, n) for p in (p0, p1, p2, p3))
        self.tri(a, b, c)
        self.tri(a, c, d)

    def box(self, centre, size, color) -> None:
        cx, cy, cz = centre
        hx, hy, hz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
        c = [(cx + sx * hx, cy + sy * hy, cz + sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        # c index: (sx, sy, sz) -> 4*ix + 2*iy + iz
        faces = (
            ((0, 1, 3, 2), (-1, 0, 0)), ((4, 6, 7, 5), (1, 0, 0)),
            ((0, 4, 5, 1), (0, -1, 0)), ((2, 3, 7, 6), (0, 1, 0)),
            ((0, 2, 6, 4), (0, 0, -1)), ((1, 5, 7, 3), (0, 0, 1)),
        )
        for idx, n in faces:
            self.quad(*(c[i] for i in idx), color, n)

    def node(self) -> NodePath:
        self.tris.closePrimitive()
        geom = Geom(self.vdata)
        geom.addPrimitive(self.tris)
        gn = GeomNode(self.name)
        gn.addGeom(geom)
        return NodePath(gn)


def _points_node(name: str, pts, colors) -> NodePath:
    vdata = GeomVertexData(name, _fmt_c4(), Geom.UHStatic)
    vw = GeomVertexWriter(vdata, "vertex")
    cw = GeomVertexWriter(vdata, "color")
    prim = GeomPoints(Geom.UHStatic)
    for i, (p, c) in enumerate(zip(pts, colors)):
        vw.addData3(*p)
        cw.addData4(*c)
        prim.addVertex(i)
    prim.closePrimitive()
    geom = Geom(vdata)
    geom.addPrimitive(prim)
    gn = GeomNode(name)
    gn.addGeom(geom)
    return NodePath(gn)


def _radial_texture(name: str, size: int = 128, falloff: float = 2.2, core: float = 0.0) -> Texture:
    img = PNMImage(size, size, 4)
    half = (size - 1) * 0.5
    for y in range(size):
        for x in range(size):
            r = math.hypot(x - half, y - half) / half
            a = max(0.0, 1.0 - r) ** falloff
            if core > 0.0:
                a = min(1.0, a + core * max(0.0, 1.0 - r * 6.0))
            img.setXelA(x, y, 1.0, 1.0, 1.0, a)
    tex = Texture(name)
    tex.load(img)
    tex.setWrapU(Texture.WMClamp)
    tex.setWrapV(Texture.WMClamp)
    return tex


def _billboard(parent: NodePath, name: str, tex: Texture, radius: float, color, pos) -> NodePath:
    """A camera-facing textured quad.  The sky camera sits at the origin, so a
    quad that looks at the origin always faces it."""
    vdata = GeomVertexData(name, GeomVertexFormat.getV3t2(), Geom.UHStatic)
    vw = GeomVertexWriter(vdata, "vertex")
    tw = GeomVertexWriter(vdata, "texcoord")
    for x, z, u, v in ((-1, -1, 0, 0), (1, -1, 1, 0), (1, 1, 1, 1), (-1, 1, 0, 1)):
        vw.addData3(x * radius, 0.0, z * radius)
        tw.addData2(u, v)
    tris = GeomTriangles(Geom.UHStatic)
    tris.addVertices(0, 1, 2)
    tris.addVertices(0, 2, 3)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode(name)
    gn.addGeom(geom)
    np_ = parent.attachNewNode(gn)
    np_.setTexture(tex)
    np_.setColor(*color)
    np_.setPos(*pos)
    np_.setBillboardPointEye()
    np_.setTransparency(TransparencyAttrib.MAlpha)
    np_.setDepthWrite(False)
    np_.setTwoSided(True)
    np_.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
    return np_


def _sphere_dir(lat: float, lon: float) -> tuple[float, float, float]:
    cl = math.cos(lat)
    return (cl * math.cos(lon), cl * math.sin(lon), math.sin(lat))


def _line_scale(app) -> float:
    try:
        rows = float(app.win.getYSize())
        return max(1.0, min(2.2, rows / 1080.0))
    except Exception:
        return 1.0


# ----------------------------------------------------------------------
# The flight system
# ----------------------------------------------------------------------
class DeepSpaceFlight:
    def __init__(self, app):
        self.app = app
        self.built = False
        self.active = False
        self.shader_ok = False
        self.ship = NodePath("deep-space-ship-orientation")   # orientation holder, not drawn
        self.pos = [0.0, 0.0, 0.0]                            # ship position (Python floats)
        self.vel = Vec3(0, 0, 0)
        self.ang = Vec3(0, 0, 0)                              # current turn rates (h, p, r) deg/s
        self.stick = [0.0, 0.0]
        self.throttle = 0.0
        self.flight_assist = True
        self.boost_left = 0.0
        self.boost_cooldown = 0.0
        self.mode = "normal"                                  # normal | charging | supercruise
        self.charge = 0.0
        self.approach = 0.0
        self.anchor = Vec3(0, 0, 0)
        self.cells: dict = {}
        self.cell_queue: list = []
        self.cell_centre = None
        self.rocks_near: list = []
        self.hidden_scene: list = []
        self.prev_keys: dict = {}
        self.shake = 0.0
        self.message = ""
        self.message_time = 0.0
        self.distance_travelled = 0.0
        self.frames = 0

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    def build(self) -> None:
        if self.built:
            return
        app = self.app
        ls = _line_scale(app)
        self.line_scale = ls
        self.dyson_dir = Vec3(DYSON_DIRECTION)
        self.dyson_dir.normalize()

        # --- sky layer: own scene graph, own camera, drawn first --------------
        self.sky_scene = NodePath("deep-space-sky-scene")
        self.sky_lens = PerspectiveLens()
        self.sky_lens.setNearFar(50.0, SKY_FAR)
        cam = Camera("deep-space-sky-camera", self.sky_lens)
        self.sky_cam = self.sky_scene.attachNewNode(cam)
        self.sky_region = app.win.makeDisplayRegion()
        self.sky_region.setSort(-20)
        self.sky_region.setCamera(self.sky_cam)
        self.sky_region.setClearColorActive(True)
        self.sky_region.setClearColor(Vec4(*SPACE_RGB, 1.0))
        self.sky_region.setClearDepthActive(True)
        self.sky_region.setActive(False)
        self.sky_scene.setLightOff(1)
        self.sky_scene.setFogOff(1)
        self.sky_scene.setShaderOff(10)
        self._build_stars()
        # Pass 282.70: the decorative gas giant is gone; every planet in the sky is a dimension.
        self._build_dyson()

        # --- local space under render ------------------------------------------
        self.local_root = app.render.attachNewNode("deep-space-local-root")
        self.local_root.setFogOff(1)
        self.local_root.setShaderOff(1)
        self.local_root.setLightOff(1)
        sun = DirectionalLight("deep-space-dyson-light")
        sun.setColor(Vec4(1.45, 0.58, 0.42, 1.0))   # red star light
        self.sun_np = self.local_root.attachNewNode(sun)
        self.sun_np.lookAt(-self.dyson_dir)
        amb = AmbientLight("deep-space-ambient")
        amb.setColor(Vec4(0.10, 0.11, 0.15, 1.0))
        self.amb_np = self.local_root.attachNewNode(amb)
        self.cells_root = self.local_root.attachNewNode("deep-space-cells")
        self.cells_root.setLight(self.sun_np)
        self.cells_root.setLight(self.amb_np)
        self._build_dust()
        self.local_root.hide()

        # --- cockpit (camera child) and HUD (aspect2d) -------------------------
        self._build_cockpit()
        self._build_hud()
        # Pass 282.64: the Dimension Archive's realities as distant planets.
        try:
            from holoverse.dimension_planets import DimensionPlanets
            self.planets = DimensionPlanets(app, self)
        except Exception as exc:
            self.planets = None
            print(f"dimension_planets_unavailable:{exc.__class__.__name__}:{exc}")
        self.built = True

    def _build_stars(self) -> None:
        rng = Random(0x5EA5)
        root = self.sky_scene.attachNewNode("deep-space-stars")
        root.setDepthWrite(False)
        root.setBin("background", 0)
        bright_pts, bright_cols, dim_pts, dim_cols = [], [], [], []
        palette = ((0.75, 0.85, 1.0), (1.0, 1.0, 1.0), (1.0, 0.92, 0.75), (1.0, 0.76, 0.55), (0.70, 0.80, 1.0))
        for i in range(5200):
            z = rng.uniform(-1.0, 1.0)
            t = rng.uniform(0.0, math.tau)
            r = math.sqrt(max(0.0, 1.0 - z * z))
            p = (r * math.cos(t) * STAR_RADIUS, r * math.sin(t) * STAR_RADIUS, z * STAR_RADIUS)
            c = palette[rng.randrange(len(palette))]
            if rng.random() < 0.10:
                bright_pts.append(p)
                bright_cols.append((*c, rng.uniform(0.75, 1.0)))
            else:
                dim_pts.append(p)
                dim_cols.append((*c, rng.uniform(0.25, 0.75)))
        # galactic band: a tilted great circle, dense and faint
        tilt = math.radians(62.0)
        for i in range(6500):
            lon = rng.uniform(0.0, math.tau)
            lat = rng.gauss(0.0, 0.07)
            x, y, z = _sphere_dir(lat, lon)
            y, z = y * math.cos(tilt) - z * math.sin(tilt), y * math.sin(tilt) + z * math.cos(tilt)
            dim_pts.append((x * STAR_RADIUS, y * STAR_RADIUS, z * STAR_RADIUS))
            warm = rng.random()
            dim_cols.append((0.70 + 0.3 * warm, 0.72 + 0.2 * warm, 1.0 - 0.25 * warm, rng.uniform(0.10, 0.42)))
        dim = root.attachNewNode(_points_node("deep-space-stars-dim", dim_pts, dim_cols).node())
        dim.setRenderModeThickness(1.4 * self.line_scale)
        bright = root.attachNewNode(_points_node("deep-space-stars-bright", bright_pts, bright_cols).node())
        bright.setRenderModeThickness(2.6 * self.line_scale)
        root.setTransparency(TransparencyAttrib.MAlpha)
        # Pass 282.70: depth. A far shell of very faint stars behind the main field and a few
        # distant galaxies, so the sky has layers instead of one flat sheet of points.
        far_pts, far_cols = [], []
        for i in range(9000):
            z = rng.uniform(-1.0, 1.0)
            t = rng.uniform(0.0, math.tau)
            r = math.sqrt(max(0.0, 1.0 - z * z))
            far_pts.append((r * math.cos(t) * STAR_RADIUS * 1.25, r * math.sin(t) * STAR_RADIUS * 1.25, z * STAR_RADIUS * 1.25))
            c = palette[rng.randrange(len(palette))]
            far_cols.append((*c, rng.uniform(0.06, 0.22)))
        far = root.attachNewNode(_points_node("deep-space-stars-far", far_pts, far_cols).node())
        far.setRenderModeThickness(1.0 * self.line_scale)
        galaxy_tex = _radial_texture("deep-space-galaxy", 128, 2.6, 0.12)
        for i in range(5):
            gx, gy, gz = _sphere_dir(rng.uniform(-1.1, 1.1), rng.uniform(0.0, math.tau))
            d = STAR_RADIUS * 0.95
            g = _billboard(root, f"deep-space-galaxy-{i}", galaxy_tex, rng.uniform(5200.0, 9000.0),
                           (0.80, 0.78, 1.0, rng.uniform(0.18, 0.30)), (gx * d, gy * d, gz * d))
            g.setScale(1.0, 1.0, rng.uniform(0.28, 0.45))
        # nebulae: soft additive clouds along the band
        neb_tex = _radial_texture("deep-space-nebula", 128, 1.6)
        for i, (lon, lat, col, size) in enumerate((
            (0.6, 0.05, (0.30, 0.12, 0.45, 0.30), 52000.0),
            (1.4, -0.08, (0.10, 0.30, 0.50, 0.26), 64000.0),
            (2.9, 0.10, (0.45, 0.16, 0.20, 0.22), 46000.0),
            (4.3, -0.02, (0.12, 0.38, 0.42, 0.24), 70000.0),
            (5.4, 0.06, (0.36, 0.20, 0.50, 0.20), 50000.0),
            (0.2, -0.45, (0.08, 0.16, 0.34, 0.12), 110000.0),   # Pass 282.70: broad, faint off-band haze
            (3.6, 0.52, (0.26, 0.10, 0.30, 0.10), 120000.0),
        )):
            x, y, z = _sphere_dir(lat, lon)
            y, z = y * math.cos(tilt) - z * math.sin(tilt), y * math.sin(tilt) + z * math.cos(tilt)
            d = STAR_RADIUS * 0.9
            _billboard(root, f"deep-space-nebula-{i}", neb_tex, size, col, (x * d, y * d, z * d))

    def _build_gas_giant(self) -> None:
        """A ringed gas giant off to one side, lit by Dyson Prime's star."""
        d = Vec3(-0.78, 0.42, -0.10)
        d.normalize()
        centre = d * 90000.0
        radius = 7200.0
        root = self.sky_scene.attachNewNode("deep-space-gas-giant")
        root.setPos(centre)
        root.setBin("background", 2)
        sun = Vec3(self.dyson_dir * DYSON_SKY_DISTANCE) - centre
        sun.normalize()
        mesh = _Mesh("deep-space-gas-giant-body")
        stacks, slices = 24, 48
        rows = []
        for i in range(stacks + 1):
            lat = -math.pi / 2 + math.pi * i / stacks
            row = []
            for j in range(slices + 1):
                lon = math.tau * j / slices
                n = Vec3(*_sphere_dir(lat, lon))
                band = 0.5 + 0.5 * math.sin(lat * 11.0 + 0.6 * math.sin(lon * 2.0))
                base = (0.62 + 0.18 * band, 0.46 + 0.14 * band, 0.34 + 0.08 * band)
                light = max(0.03, n.dot(sun)) ** 0.8
                col = (base[0] * light, base[1] * light, base[2] * light, 1.0)
                row.append(mesh.vertex(n * radius, col))
            rows.append(row)
        for i in range(stacks):
            for j in range(slices):
                a, b, c, e = rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]
                mesh.tri(a, b, c)
                mesh.tri(a, c, e)
        body = root.attachNewNode(mesh.node().node())
        body.setTwoSided(False)
        ring = _Mesh("deep-space-gas-giant-ring")
        segs = 96
        for k in range(segs):
            a0, a1 = math.tau * k / segs, math.tau * (k + 1) / segs
            for r0, r1, alpha in ((1.45, 1.75, 0.34), (1.80, 2.25, 0.22)):
                pts = [(math.cos(a0) * r0 * radius, math.sin(a0) * r0 * radius, 0.0), (math.cos(a1) * r0 * radius, math.sin(a1) * r0 * radius, 0.0),
                       (math.cos(a1) * r1 * radius, math.sin(a1) * r1 * radius, 0.0), (math.cos(a0) * r1 * radius, math.sin(a0) * r1 * radius, 0.0)]
                ring.quad(*pts, (0.78, 0.68, 0.55, alpha))
        rnode = root.attachNewNode(ring.node().node())
        rnode.setHpr(20.0, 18.0, 6.0)
        rnode.setTwoSided(True)
        rnode.setTransparency(TransparencyAttrib.MAlpha)
        rnode.setDepthWrite(False)

    def _build_dyson(self) -> None:
        """Dyson Prime: a finished shell around its star, with a habitat ring and
        a collector swarm.  Solid dark panels, warm-lit inside, holo seams."""
        R = DYSON_SHELL_RADIUS
        rng = Random(0xD150)
        self.dyson_root = self.sky_scene.attachNewNode("dyson-prime")
        self.dyson_root.setPos(self.dyson_dir * DYSON_SKY_DISTANCE)
        self.dyson_root.setHpr(25.0, 12.0, 0.0)
        self.dyson_root.setBin("background", 5)
        self.dyson_spin = self.dyson_root.attachNewNode("dyson-prime-spin")
        # star
        star = _Mesh("dyson-prime-star")
        rows = []
        for i in range(13):
            lat = -math.pi / 2 + math.pi * i / 12
            row = [star.vertex(Vec3(*_sphere_dir(lat, math.tau * j / 24)) * (R * 0.30), STAR_RGBA) for j in range(25)]
            rows.append(row)
        for i in range(12):
            for j in range(24):
                star.tri(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1])
                star.tri(rows[i][j], rows[i + 1][j + 1], rows[i + 1][j])
        self.dyson_spin.attachNewNode(star.node().node())
        # shell panels: outer faces dark metal, inner faces lit by the star
        outer = _Mesh("dyson-prime-shell-outer")
        inner = _Mesh("dyson-prime-shell-inner")
        seams = LineSegs("dyson-prime-seams")
        seams.setThickness(1.0 * self.line_scale)
        bands, slices = 16, 32
        gap = 0.06
        self.dyson_panel_count = 0
        for i in range(bands):
            lat0 = -math.pi / 2 + math.pi * i / bands
            lat1 = -math.pi / 2 + math.pi * (i + 1) / bands
            if abs((lat0 + lat1) * 0.5) < math.radians(7.0):
                continue  # the equator is open where the habitat ring runs
            for j in range(slices):
                if rng.random() > (0.90 if abs(lat0) > 0.5 else 0.82):
                    continue  # unfinished panel: starlight escapes here
                lon0 = math.tau * j / slices
                lon1 = math.tau * (j + 1) / slices
                la0, la1 = lat0 + (lat1 - lat0) * gap, lat1 - (lat1 - lat0) * gap
                lo0, lo1 = lon0 + (lon1 - lon0) * gap, lon1 - (lon1 - lon0) * gap
                corners = [Vec3(*_sphere_dir(la, lo)) for la, lo in ((la0, lo0), (la0, lo1), (la1, lo1), (la1, lo0))]
                shade = rng.uniform(0.85, 1.15)
                oc = (0.050 * shade, 0.056 * shade, 0.070 * shade, 1.0)
                warm = rng.uniform(0.55, 0.9)
                ic = (0.82 * warm, 0.22 * warm, 0.11 * warm, 1.0)  # red starlight inside
                o = [c * R for c in corners]
                outer.quad(o[0], o[1], o[2], o[3], oc)
                ii = [c * (R * 0.995) for c in corners]
                inner.quad(ii[3], ii[2], ii[1], ii[0], ic)
                self.dyson_panel_count += 1
                if rng.random() < 0.38:
                    # holo seams on some panels only: accents, not a grid
                    accent = (0.45, 0.92, 1.0, 0.30) if rng.random() < 0.75 else (1.0, 0.78, 0.32, 0.40)
                    seams.setColor(*accent)
                    s = [c * (R * 1.003) for c in corners]
                    seams.moveTo(s[0])
                    for p in s[1:] + [s[0]]:
                        seams.drawTo(p)
        for mesh in (outer, inner):
            np_ = self.dyson_spin.attachNewNode(mesh.node().node())
            np_.setTwoSided(False)
        seam_np = self.dyson_spin.attachNewNode(seams.create())
        seam_np.setTransparency(TransparencyAttrib.MAlpha)
        seam_np.setDepthWrite(False)
        # habitat ring: a solid band with city lights
        ring = _Mesh("dyson-prime-habitat-ring")
        segs = 128
        r_out, r_in, half_h = R * 1.20, R * 1.12, R * 0.035
        lights_pts, lights_cols = [], []
        for k in range(segs):
            a0, a1 = math.tau * k / segs, math.tau * (k + 1) / segs
            c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
            dark = (0.060, 0.064, 0.078, 1.0)
            ring.quad((c0 * r_out, s0 * r_out, -half_h), (c1 * r_out, s1 * r_out, -half_h), (c1 * r_out, s1 * r_out, half_h), (c0 * r_out, s0 * r_out, half_h), dark)
            ring.quad((c0 * r_in, s0 * r_in, half_h), (c1 * r_in, s1 * r_in, half_h), (c1 * r_in, s1 * r_in, -half_h), (c0 * r_in, s0 * r_in, -half_h), (0.58, 0.18, 0.10, 1.0))
            ring.quad((c0 * r_in, s0 * r_in, half_h), (c0 * r_out, s0 * r_out, half_h), (c1 * r_out, s1 * r_out, half_h), (c1 * r_in, s1 * r_in, half_h), (0.08, 0.085, 0.10, 1.0))
            ring.quad((c1 * r_in, s1 * r_in, -half_h), (c1 * r_out, s1 * r_out, -half_h), (c0 * r_out, s0 * r_out, -half_h), (c0 * r_in, s0 * r_in, -half_h), (0.08, 0.085, 0.10, 1.0))
            for _ in range(5):
                a = rng.uniform(a0, a1)
                lights_pts.append((math.cos(a) * r_out * 1.002, math.sin(a) * r_out * 1.002, rng.uniform(-half_h, half_h) * 0.8))
                lights_cols.append((1.0, 0.85, 0.55, rng.uniform(0.5, 1.0)) if rng.random() < 0.7 else (0.5, 0.95, 1.0, 0.9))
        ring_np = self.dyson_spin.attachNewNode(ring.node().node())
        ring_np.setTwoSided(False)
        lights = self.dyson_spin.attachNewNode(_points_node("dyson-prime-ring-lights", lights_pts, lights_cols).node())
        lights.setRenderModeThickness(1.6 * self.line_scale)
        lights.setTransparency(TransparencyAttrib.MAlpha)
        lights.setDepthWrite(False)
        # collector swarm: two tilted rings of dark collectors catching light
        self.dyson_swarms = []
        for idx, (radius, tilt, count) in enumerate(((1.48, 18.0, 220), (1.78, -27.0, 260))):
            sw = self.dyson_root.attachNewNode(f"dyson-prime-swarm-{idx}")
            sw.setP(tilt)
            sw.setR(tilt * 0.6)
            m = _Mesh(f"dyson-prime-swarm-mesh-{idx}")
            glints, glint_cols = [], []
            for k in range(count):
                a = math.tau * k / count + rng.uniform(-0.01, 0.01)
                rr = R * radius * rng.uniform(0.985, 1.015)
                cx, cy = math.cos(a) * rr, math.sin(a) * rr
                tx, ty = -math.sin(a), math.cos(a)
                w, h = R * 0.035, R * 0.020
                pts = [(cx - tx * w, cy - ty * w, -h), (cx + tx * w, cy + ty * w, -h), (cx + tx * w, cy + ty * w, h), (cx - tx * w, cy - ty * w, h)]
                m.quad(*pts, (0.10, 0.11, 0.14, 1.0))
                if rng.random() < 0.35:
                    glints.append((cx * 1.002, cy * 1.002, 0.0))
                    glint_cols.append((1.0, 0.9, 0.7, rng.uniform(0.4, 1.0)))
            mn = sw.attachNewNode(m.node().node())
            mn.setTwoSided(True)
            gl = sw.attachNewNode(_points_node(f"dyson-prime-swarm-glints-{idx}", glints, glint_cols).node())
            gl.setRenderModeThickness(1.4 * self.line_scale)
            gl.setTransparency(TransparencyAttrib.MAlpha)
            gl.setDepthWrite(False)
            self.dyson_swarms.append(sw)
        # star glow: drawn after the solid parts, so panels in front occlude it
        glow_tex = _radial_texture("dyson-prime-glow", 128, 2.4, core=0.6)
        self.dyson_glows = [
            _billboard(self.dyson_root, "dyson-prime-glow-wide", glow_tex, R * 3.2, (1.0, 0.24, 0.12, 0.60), (0, 0, 0)),
            _billboard(self.dyson_root, "dyson-prime-glow-core", glow_tex, R * 1.25, (1.0, 0.50, 0.34, 0.95), (0, 0, 0)),
        ]
        for g in self.dyson_glows:
            g.setBin("fixed", 10)

    def _build_dust(self) -> None:
        rng = Random(0xD057)
        arr = GeomVertexArrayFormat()
        arr.addColumn(InternalName.getVertex(), 3, Geom.NTFloat32, Geom.CPoint)
        arr.addColumn(InternalName.getColor(), 4, Geom.NTFloat32, Geom.CColor)
        arr.addColumn(InternalName.make("streak"), 1, Geom.NTFloat32, Geom.COther)
        fmt = GeomVertexFormat.registerFormat(arr)
        vdata = GeomVertexData("deep-space-dust", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")
        sw = GeomVertexWriter(vdata, "streak")
        lines = GeomLines(Geom.UHStatic)
        for i in range(DUST_PER_TILE):
            p = (rng.uniform(0, DUST_TILE), rng.uniform(0, DUST_TILE), rng.uniform(0, DUST_TILE))
            b = rng.uniform(0.55, 1.0)
            for s in (0.0, 1.0):
                vw.addData3(*p)
                cw.addData4(0.75 * b, 0.88 * b, 1.0 * b, rng.uniform(0.45, 0.9))
                sw.addData1(s)
            lines.addVertices(2 * i, 2 * i + 1)
        lines.closePrimitive()
        geom = Geom(vdata)
        geom.addPrimitive(lines)
        gn = GeomNode("deep-space-dust-tile")
        gn.addGeom(geom)
        tile = NodePath(gn)
        self.dust_root = self.local_root.attachNewNode("deep-space-dust")
        self.dust_root.setLightOff(1)
        self.dust_root.setTransparency(TransparencyAttrib.MAlpha)
        self.dust_root.setDepthWrite(False)
        self.dust_root.setBin("transparent", 5)
        self.dust_root.setRenderModeThickness(1.6 * self.line_scale)
        self.dust_root.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        try:
            shader = Shader.make(Shader.SL_GLSL, _DUST_VERT, _DUST_FRAG)
            if shader is not None:
                self.dust_root.setShader(shader, 20)
                self.dust_root.setShaderInput("u_streak", Vec3(0, 0.6, 0))
                self.dust_root.setShaderInput("u_alpha", 1.0)
                self.dust_root.setShaderInput("u_range", float(DUST_RANGE))
                self.shader_ok = True
        except Exception as exc:
            print(f"deep_space_dust_shader_fallback err={exc.__class__.__name__}:{exc}")
            self.shader_ok = False
        self.dust_tiles = []
        for _ in range(27):
            holder = self.dust_root.attachNewNode("deep-space-dust-slot")
            tile.instanceTo(holder)
            self.dust_tiles.append(holder)

    def _build_cockpit(self) -> None:
        """Solid canopy frame and dash with holo panels, parented to the camera."""
        root = self.app.camera.attachNewNode("deep-space-cockpit")
        m = _Mesh("deep-space-cockpit-frame")
        frame = (0.035, 0.040, 0.050, 1.0)
        trim = (0.07, 0.08, 0.10, 1.0)
        # dash slab and lower sill (the bottom edge of the view)
        m.box((0.0, 1.05, -0.64), (2.6, 0.55, 0.12), frame)
        m.box((0.0, 1.30, -0.575), (2.6, 0.05, 0.035), trim)
        # slim canopy: pillars and a roof bow at the edges of the view
        for side in (-1.0, 1.0):
            pillar = _Mesh("deep-space-pillar")
            pillar.box((0.0, 0.0, 0.0), (0.028, 0.028, 1.30), frame)
            pnp = root.attachNewNode(pillar.node().node())
            pnp.setPos(side * 1.06, 1.25, -0.02)   # at the view edge with the 82 degree FOV
        m.box((0.0, 1.25, 0.64), (2.2, 0.03, 0.03), frame)
        frame_np = root.attachNewNode(m.node().node())
        holo = LineSegs("deep-space-cockpit-holo")
        holo.setThickness(1.2 * self.line_scale)
        holo.setColor(*HUD_CYAN, 0.55)
        # two dash screens, outlined, tilted toward the pilot
        for x0 in (-0.85, 0.35):
            holo.moveTo(x0, 0.95, -0.555)
            for x, y, z in ((x0 + 0.5, 0.95, -0.555), (x0 + 0.5, 1.10, -0.47), (x0, 1.10, -0.47), (x0, 0.95, -0.555)):
                holo.drawTo(x, y, z)
        holo.setColor(*HUD_AMBER, 0.45)
        holo.moveTo(-0.97, 1.24, -0.62)
        holo.drawTo(-0.97, 1.24, 0.40)
        holo.moveTo(0.97, 1.24, -0.62)
        holo.drawTo(0.97, 1.24, 0.40)
        holo_np = root.attachNewNode(holo.create())
        holo_np.setTransparency(TransparencyAttrib.MAlpha)
        root.setLightOff(1)
        root.setFogOff(1)
        root.setShaderOff(10)
        root.setBin("fixed", 30)
        root.setDepthOffset(1)
        self.cockpit = root
        self.cockpit_frame = frame_np
        root.hide()

    def _build_hud(self) -> None:
        from direct.gui.OnscreenText import OnscreenText

        app = self.app
        a2d = app.aspect2d
        self.hud = a2d.attachNewNode("deep-space-hud")
        self.hud.setTransparency(TransparencyAttrib.MAlpha)
        th = 1.4 * self.line_scale
        # reticle
        ret = LineSegs("deep-space-reticle")
        ret.setThickness(th)
        ret.setColor(*HUD_CYAN, 0.75)
        for k in range(33):
            a = math.tau * k / 32
            (ret.moveTo if k == 0 else ret.drawTo)(math.cos(a) * 0.030, 0, math.sin(a) * 0.030)
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ret.moveTo(dx * 0.040, 0, dz * 0.040)
            ret.drawTo(dx * 0.060, 0, dz * 0.060)
        self.hud.attachNewNode(ret.create())
        stick = LineSegs("deep-space-stick-marker")
        stick.setThickness(th * 1.4)
        stick.setColor(*HUD_AMBER, 0.9)
        for k in range(13):
            a = math.tau * k / 12
            (stick.moveTo if k == 0 else stick.drawTo)(math.cos(a) * 0.008, 0, math.sin(a) * 0.008)
        self.stick_marker = self.hud.attachNewNode(stick.create())
        # throttle bar (bottom left)
        # Anchored to the bottom-left corner so it stays put at any aspect ratio.
        corner = getattr(app, "a2dBottomLeft", None) or a2d
        self.throttle_root = corner.attachNewNode("deep-space-throttle")
        self.throttle_root.setTransparency(TransparencyAttrib.MAlpha)
        bar = LineSegs("deep-space-throttle-frame")
        bar.setThickness(th)
        bar.setColor(*HUD_CYAN, 0.7)
        bx0, bx1, bz0, bz1 = 0.10, 0.15, 0.12, 0.72
        bar.moveTo(bx0, 0, bz0)
        for x, z in ((bx1, bz0), (bx1, bz1), (bx0, bz1), (bx0, bz0)):
            bar.drawTo(x, 0, z)
        zero_z = bz0 + (bz1 - bz0) * (REVERSE_FRACTION / (1.0 + REVERSE_FRACTION))
        bar.setColor(*HUD_AMBER, 0.8)
        bar.moveTo(bx0 - 0.015, 0, zero_z)
        bar.drawTo(bx1 + 0.015, 0, zero_z)
        self.throttle_root.attachNewNode(bar.create())
        fill = _Mesh("deep-space-throttle-fill")
        fill.quad((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1), (1, 1, 1, 1))
        self.throttle_fill = self.throttle_root.attachNewNode(fill.node().node())
        self.throttle_fill.setTwoSided(True)
        self.throttle_fill.setTransparency(TransparencyAttrib.MAlpha)
        self.throttle_geom = (bx0 + 0.006, bx1 - 0.006, zero_z, bz0, bz1)
        kw = dict(parent=self.hud, align=TextNode.ACenter, mayChange=True, shadow=(0, 0, 0, 0.8))
        self.speed_text = OnscreenText(text="", pos=(0, -0.66), scale=0.050, fg=(*HUD_CYAN, 0.95), **kw)
        self.mode_text = OnscreenText(text="", pos=(0, -0.72), scale=0.036, fg=(*HUD_AMBER, 0.95), **kw)
        self.msg_text = OnscreenText(text="", pos=(0, 0.62), scale=0.042, fg=(*HUD_AMBER, 0.0), **kw)
        self.title_text = OnscreenText(text="HOLOSPACE  //  DYSON PRIME SYSTEM", pos=(0, 0.90), scale=0.036, fg=(*HUD_CYAN, 0.75), **kw)
        self.throttle_text = OnscreenText(text="", parent=self.throttle_root, pos=(0.125, 0.76), scale=0.032,
                                          fg=(*HUD_CYAN, 0.9), align=TextNode.ACenter, mayChange=True, shadow=(0, 0, 0, 0.8))
        # Dyson Prime marker
        mk = LineSegs("deep-space-dyson-marker")
        mk.setThickness(th)
        mk.setColor(*HUD_AMBER, 0.9)
        s = 1.0   # unit bracket; scaled to the sphere's size on screen each frame
        for (x0, z0), (x1, z1), (x2, z2) in (((-s, s * 0.5), (-s, s), (-s * 0.5, s)), ((s * 0.5, s), (s, s), (s, s * 0.5)),
                                             ((s, -s * 0.5), (s, -s), (s * 0.5, -s)), ((-s * 0.5, -s), (-s, -s), (-s, -s * 0.5))):
            mk.moveTo(x0, 0, z0)
            mk.drawTo(x1, 0, z1)
            mk.drawTo(x2, 0, z2)
        self.dyson_marker = self.hud.attachNewNode(mk.create())
        self.dyson_label = OnscreenText(text="", parent=self.hud, pos=(0, 0), scale=0.032,
                                        fg=(*HUD_AMBER, 0.95), align=TextNode.ALeft, mayChange=True, shadow=(0, 0, 0, 0.8))
        arrow = LineSegs("deep-space-dyson-arrow")
        arrow.setThickness(th * 1.3)
        arrow.setColor(*HUD_AMBER, 0.95)
        arrow.moveTo(-0.025, 0, -0.02)
        arrow.drawTo(0.03, 0, 0.0)
        arrow.drawTo(-0.025, 0, 0.02)
        self.dyson_arrow = self.hud.attachNewNode(arrow.create())
        self.hud.hide()
        self.throttle_root.hide()

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------
    def activate(self, anchor) -> None:
        self.build()
        app = self.app
        self.anchor = Vec3(anchor)
        if not self.active:
            self.pos = [0.0, 0.0, 0.0]
            self.vel = Vec3(0, 0, 0)
            self.ang = Vec3(0, 0, 0)
            self.stick = [0.0, 0.0]
            self.throttle = 0.0
            self.flight_assist = True
            self.mode = "normal"
            self.charge = 0.0
            self.boost_left = self.boost_cooldown = 0.0
            # Face Dyson Prime, a little off-centre so the first view shows it
            # beside the canopy frame rather than behind the reticle.
            look = Vec3(self.dyson_dir)
            look = look + Vec3(-0.18, 0.0, -0.10)
            self.ship.lookAt(Point3(look))
            self._clear_cells()
        self.active = True
        self.sky_region.setActive(True)
        if getattr(self, "planets", None) is not None:
            try:
                self.planets.sync()
            except Exception as exc:
                print(f"dimension_planets_sync_warning:{exc.__class__.__name__}:{exc}")
        try:
            self.main_region = app.cam.node().getDisplayRegion(0)
            self.main_clear_depth = bool(self.main_region.getClearDepthActive())
            self.main_region.setClearDepthActive(True)
        except Exception:
            self.main_region = None
        self.local_root.show()
        self.cockpit.show()
        self.hud.show()
        self.throttle_root.show()
        try:
            app.camLens.setNearFar(0.05, 20000.0)
        except Exception:
            pass
        self._hide_world()
        self._sync_cells(force=True)
        self.update(0.0)
        self.flash("DYSON PRIME  //  40 AU  //  FAR BEYOND REACH", 4.0)

    def deactivate(self) -> None:
        if not self.active:
            return
        self.active = False
        if getattr(self, "planets", None) is not None:
            self.planets.hide_ui()
        if self.built:
            self.sky_region.setActive(False)
            if getattr(self, "main_region", None) is not None:
                try:
                    self.main_region.setClearDepthActive(self.main_clear_depth)
                except Exception:
                    pass
            self.local_root.hide()
            self.cockpit.hide()
            self.hud.hide()
            self.throttle_root.hide()
        self._restore_world()

    def _hide_world(self) -> None:
        """Hide every top-level scene node except this system and the camera.
        Nodes created while in space (shell refreshes) are caught each frame."""
        app = self.app
        keep = {self.local_root, app.camera}
        for child in app.render.getChildren():
            if child in keep or child.isHidden():
                continue
            if child.node().isOfType(DirectionalLight.getClassType()) or child.node().isOfType(AmbientLight.getClassType()):
                continue
            child.hide()
            self.hidden_scene.append(child)

    def _restore_world(self) -> None:
        for node in self.hidden_scene:
            try:
                if not node.isEmpty():
                    node.show()
            except Exception:
                pass
        self.hidden_scene = []

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def _down(self, key) -> bool:
        try:
            mw = self.app.mouseWatcherNode
            if isinstance(key, str):
                return bool(mw.isButtonDown(KeyboardButton.asciiKey(key)))
            return bool(mw.isButtonDown(key))
        except Exception:
            return False

    def _pressed(self, name: str, down: bool) -> bool:
        was = self.prev_keys.get(name, False)
        self.prev_keys[name] = down
        return down and not was

    def _input_blocked(self) -> bool:
        app = self.app
        return bool(getattr(app, "menu_open", False) or getattr(app, "core_console_open", False)
                    or getattr(app, "bot_dialogue_open", False))

    def _read_mouse(self) -> tuple[float, float]:
        app = self.app
        try:
            if app.win is None or not hasattr(app.win, "getPointer"):
                return 0.0, 0.0
            import time as _time

            if _time.monotonic() < float(getattr(app, "mouse_look_resume_at", 0.0)):
                app.recenter_mouse(force=True)
                return 0.0, 0.0
            cx = app.win.getXSize() // 2
            cy = app.win.getYSize() // 2
            md = app.win.getPointer(0)
            dx, dy = md.getX() - cx, md.getY() - cy
            app.recenter_mouse()
            # Same hand movement at 1080p and 4K: deltas are in 1080p pixels.
            norm = 1080.0 / max(1.0, float(app.win.getYSize()))
            return float(dx) * norm, float(dy) * norm
        except Exception:
            return 0.0, 0.0

    def flash(self, text: str, seconds: float = 2.5) -> None:
        self.message = text
        self.message_time = float(seconds)

    # ------------------------------------------------------------------
    # Frame update
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        if not self.active:
            return
        dt = max(0.0, min(0.05, float(dt or 0.0)))
        self.frames += 1
        planets = getattr(self, "planets", None)
        if planets is not None and planets.prompt_open:
            # Pass 282.64: the "enter this dimension?" prompt pauses the flight.
            self._update_hud(0.0)
            planets.update(dt)
            return
        blocked = self._input_blocked()
        if not blocked and dt > 0.0:
            self._fly(dt)
        self._catch_new_world_nodes()
        self._place(dt)
        self._update_hud(dt)
        if planets is not None:
            planets.update(dt)
        try:
            self.app.center_hint["text"] = "H  FLIGHT HELP   //   TAB  HOME"
        except Exception:
            pass

    def _catch_new_world_nodes(self) -> None:
        if self.frames % 15 != 0:
            return
        app = self.app
        hidden = set(self.hidden_scene)
        for child in app.render.getChildren():
            if child == self.local_root or child == app.camera or child in hidden or child.isHidden():
                continue
            node = child.node()
            if node.isOfType(DirectionalLight.getClassType()) or node.isOfType(AmbientLight.getClassType()):
                continue
            child.hide()
            self.hidden_scene.append(child)

    def _fly(self, dt: float) -> None:
        dx, dy = self._read_mouse()
        # Virtual stick: mouse motion deflects it, it slowly self-centres.
        self.stick[0] = max(-1.0, min(1.0, self.stick[0] + dx * STICK_GAIN))
        self.stick[1] = max(-1.0, min(1.0, self.stick[1] + dy * STICK_GAIN))
        mag = math.hypot(*self.stick)
        if mag > 1.0:
            self.stick = [self.stick[0] / mag, self.stick[1] / mag]
        decay = math.exp(-STICK_RECENTER * dt)
        self.stick = [self.stick[0] * decay, self.stick[1] * decay]
        sx = 0.0 if abs(self.stick[0]) < STICK_DEADZONE else self.stick[0]
        sy = 0.0 if abs(self.stick[1]) < STICK_DEADZONE else self.stick[1]

        shift = self._down(KeyboardButton.shift())
        roll = float(self._down("d")) - float(self._down("a"))
        lateral = float(self._down(KeyboardButton.right())) - float(self._down(KeyboardButton.left()))
        vertical = float(self._down(KeyboardButton.space())) - float(self._down(KeyboardButton.control()))
        throttle_in = float(self._down("w")) - float(self._down("s"))
        if self._pressed("x", self._down("x")):
            self.throttle = 0.0
        if self._pressed("z", self._down("z")):
            self.flight_assist = not self.flight_assist
            self.flash("FLIGHT ASSIST " + ("ON" if self.flight_assist else "OFF"), 1.6)
        if self._pressed("j", self._down("j")):
            self._toggle_supercruise()
        self.throttle = max(-REVERSE_FRACTION, min(1.0, self.throttle + throttle_in * THROTTLE_RATE * dt))
        if abs(self.throttle) < 0.02 and throttle_in == 0.0:
            self.throttle = 0.0

        # Boost (normal space only)
        self.boost_cooldown = max(0.0, self.boost_cooldown - dt)
        self.boost_left = max(0.0, self.boost_left - dt)
        if shift and self.mode == "normal" and self.boost_left <= 0.0 and self.boost_cooldown <= 0.0:
            self.boost_left = BOOST_TIME
            self.boost_cooldown = BOOST_TIME + BOOST_COOLDOWN
            self.shake = max(self.shake, 0.35)

        # Rotation
        turn = SC_TURN_SCALE if self.mode == "supercruise" else 1.0
        target = Vec3(-sx * YAW_RATE * turn, -sy * PITCH_RATE * turn, roll * ROLL_RATE * turn)
        if self.flight_assist or self.mode == "supercruise":
            k = min(1.0, ANGULAR_RESPONSE * dt)
            self.ang = self.ang + (target - self.ang) * k
        else:
            self.ang = self.ang + target * (dt * 1.6)
            lim = Vec3(YAW_RATE * 1.4, PITCH_RATE * 1.4, ROLL_RATE * 1.4)
            self.ang = Vec3(max(-lim.x, min(lim.x, self.ang.x)), max(-lim.y, min(lim.y, self.ang.y)), max(-lim.z, min(lim.z, self.ang.z)))
        self.ship.setHpr(self.ship, self.ang.x * dt, self.ang.y * dt, self.ang.z * dt)
        q = self.ship.getQuat()
        fwd, right, up = q.getForward(), q.getRight(), q.getUp()

        # Translation
        if self.mode == "charging":
            self.charge += dt
            if self.charge >= SC_CHARGE_TIME:
                self.mode = "supercruise"
                self.vel = fwd * max(SC_MIN_SPEED, self.vel.length())
                self.flash("SUPERCRUISE ENGAGED", 1.8)
                self.shake = 0.6
                self.cells_root.hide()
                self._clear_cells()
        if self.mode == "supercruise":
            speed = self.vel.length()
            want = max(SC_MIN_SPEED, max(0.05, self.throttle) * SC_MAX_SPEED)
            speed += (want - speed) * min(1.0, SC_RESPONSE * dt)
            self.vel = fwd * speed
        else:
            vmax = MAX_SPEED * (BOOST_MULT if self.boost_left > 0.0 else 1.0)
            desired = fwd * (self.throttle * vmax) + right * (lateral * THRUSTER_SPEED) + up * (vertical * THRUSTER_SPEED)
            if self.flight_assist:
                delta = desired - self.vel
                step = (ACCEL * (1.6 if self.boost_left > 0.0 else 1.0)) * dt
                if delta.length() > step:
                    delta.normalize()
                    delta *= step
                self.vel = self.vel + delta
            else:
                thrust = fwd * self.throttle + right * lateral * 0.6 + up * vertical * 0.6
                self.vel = self.vel + thrust * (FA_OFF_ACCEL * (1.6 if self.boost_left > 0.0 else 1.0) * dt)
                cap = vmax * 1.15
                if self.vel.length() > cap:
                    self.vel.normalize()
                    self.vel *= cap
        step_vec = self.vel * dt
        self.pos[0] += step_vec.x
        self.pos[1] += step_vec.y
        self.pos[2] += step_vec.z
        self.distance_travelled += step_vec.length()
        self.approach = max(0.0, self.approach + step_vec.dot(self.dyson_dir))
        if self.mode != "supercruise":
            self._collide()

    def _toggle_supercruise(self) -> None:
        if self.mode == "normal":
            self.mode = "charging"
            self.charge = 0.0
            self.flash("FRAME SHIFT CHARGING", SC_CHARGE_TIME)
        elif self.mode == "charging":
            self.mode = "normal"
            self.flash("CHARGE CANCELLED", 1.4)
        else:
            self.mode = "normal"
            fwd = self.ship.getQuat().getForward()
            self.vel = fwd * (MAX_SPEED * max(0.25, self.throttle))
            self.flash("DROPPED FROM SUPERCRUISE", 1.8)
            self.shake = 0.5
            self.cells_root.show()
            self._clear_cells()
            self._sync_cells(force=True)

    def _collide(self) -> None:
        sx, sy, sz = self.pos
        for cx, cy, cz, r in self.rocks_near:
            dx, dy, dz = sx - cx, sy - cy, sz - cz
            d2 = dx * dx + dy * dy + dz * dz
            lim = r + SHIP_RADIUS
            if d2 < lim * lim:
                d = math.sqrt(max(1e-6, d2))
                n = Vec3(dx / d, dy / d, dz / d)
                push = lim - d
                self.pos = [sx + n.x * push, sy + n.y * push, sz + n.z * push]
                vn = self.vel.dot(n)
                if vn < 0.0:
                    self.vel = (self.vel - n * vn * 1.6) * 0.55
                    self.shake = max(self.shake, min(1.0, -vn / 120.0))
                    self.flash("COLLISION", 1.0)
                return

    # ------------------------------------------------------------------
    # Placement: floating origin, sky, dust, cells
    # ------------------------------------------------------------------
    def _place(self, dt: float) -> None:
        app = self.app
        q = self.ship.getQuat()
        cam_pos = Vec3(self.anchor)
        if self.shake > 0.0:
            self.shake = max(0.0, self.shake - dt * 1.4)
            amp = 0.06 * self.shake
            t = self.frames * 0.9
            cam_pos += Vec3(math.sin(t * 1.7) * amp, math.sin(t * 2.3) * amp, math.sin(t * 2.9) * amp)
        app.camera.setPos(cam_pos)
        app.camera.setQuat(app.render, q)
        try:
            app.player_pos = Vec3(self.anchor)
        except Exception:
            pass
        # sky camera: rotation only, same field of view
        self.sky_cam.setQuat(q)
        try:
            self.sky_lens.setFov(app.camLens.getFov())
            self.sky_lens.setAspectRatio(app.camLens.getAspectRatio())
        except Exception:
            pass
        self._place_dyson(dt)
        # dust tiles around the ship, world-fixed
        bx = math.floor(self.pos[0] / DUST_TILE)
        by = math.floor(self.pos[1] / DUST_TILE)
        bz = math.floor(self.pos[2] / DUST_TILE)
        i = 0
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                for oz in (-1, 0, 1):
                    self.dust_tiles[i].setPos(self.anchor.x + (bx + ox) * DUST_TILE - self.pos[0],
                                              self.anchor.y + (by + oy) * DUST_TILE - self.pos[1],
                                              self.anchor.z + (bz + oz) * DUST_TILE - self.pos[2])
                    i += 1
        if self.shader_ok:
            speed = self.vel.length()
            if self.mode == "supercruise":
                length = 90.0
            else:
                length = max(0.5, min(45.0, speed * 0.05))
            tail = Vec3(self.vel)
            if tail.lengthSquared() > 1e-6:
                tail.normalize()
            else:
                tail = Vec3(q.getForward())
            self.dust_root.setShaderInput("u_streak", -tail * length)
            self.dust_root.setShaderInput("u_alpha", 1.0 if self.mode != "supercruise" else 0.8)
        # cells
        if self.mode != "supercruise":
            self._sync_cells()
            builds = CELL_BUILDS_PER_FRAME
            while builds > 0 and self.cell_queue:
                self._build_cell(self.cell_queue.pop(0))
                builds -= 1
        for key, cell in self.cells.items():
            node = cell["node"]
            ox, oy, oz = key[0] * CELL_SIZE, key[1] * CELL_SIZE, key[2] * CELL_SIZE
            node.setPos(self.anchor.x + ox - self.pos[0], self.anchor.y + oy - self.pos[1], self.anchor.z + oz - self.pos[2])
            for beacon in cell.get("blinks", ()):
                beacon.setAlphaScale(0.25 + 0.75 * (1.0 if (self.frames // 20) % 3 == 0 else 0.0))

    def dyson_distance_au(self) -> float:
        gap = DYSON_START_AU - DYSON_FLOOR_AU
        return DYSON_FLOOR_AU + gap * math.exp(-self.approach / DYSON_APPROACH_LENGTH)

    def _place_dyson(self, dt: float) -> None:
        au = self.dyson_distance_au()
        self.dyson_root.setScale(DYSON_START_AU / au)
        self.dyson_spin.setH(self.dyson_spin.getH() + dt * 0.35)
        for i, sw in enumerate(self.dyson_swarms):
            sw.setH(sw.getH() + dt * (0.8 if i == 0 else -0.55))
        flicker = 0.92 + 0.08 * math.sin(self.frames * 0.07)
        self.dyson_glows[0].setAlphaScale(flicker)

    # ------------------------------------------------------------------
    # Streaming cells: asteroid clusters and nav beacons
    # ------------------------------------------------------------------
    def _clear_cells(self) -> None:
        for cell in self.cells.values():
            if not cell["node"].isEmpty():
                cell["node"].removeNode()
        self.cells = {}
        self.cell_queue = []
        self.cell_centre = None
        self.rocks_near = []

    def _sync_cells(self, force: bool = False) -> None:
        centre = (math.floor(self.pos[0] / CELL_SIZE), math.floor(self.pos[1] / CELL_SIZE), math.floor(self.pos[2] / CELL_SIZE))
        if centre == self.cell_centre and not force:
            return
        self.cell_centre = centre
        want = set()
        for dx in range(-CELL_RADIUS, CELL_RADIUS + 1):
            for dy in range(-CELL_RADIUS, CELL_RADIUS + 1):
                for dz in range(-CELL_RADIUS, CELL_RADIUS + 1):
                    want.add((centre[0] + dx, centre[1] + dy, centre[2] + dz))
        for key in list(self.cells):
            if key not in want:
                node = self.cells.pop(key)["node"]
                if not node.isEmpty():
                    node.removeNode()
        self.cell_queue = sorted((k for k in want if k not in self.cells),
                                 key=lambda k: (k[0] - centre[0]) ** 2 + (k[1] - centre[1]) ** 2 + (k[2] - centre[2]) ** 2)
        if force:
            for _ in range(min(len(self.cell_queue), 27)):
                self._build_cell(self.cell_queue.pop(0))
        self._refresh_rocks_near()

    def _refresh_rocks_near(self) -> None:
        rocks = []
        for cell in self.cells.values():
            rocks.extend(cell["rocks"])
        self.rocks_near = rocks

    @staticmethod
    def _cell_seed(key) -> int:
        return ((key[0] * 73856093) ^ (key[1] * 19349663) ^ (key[2] * 83492791) ^ 0x5A5E) & 0xFFFFFFFF

    def _build_cell(self, key) -> None:
        rng = Random(self._cell_seed(key))
        node = self.cells_root.attachNewNode(f"deep-space-cell-{key[0]}_{key[1]}_{key[2]}")
        cell = {"node": node, "rocks": [], "blinks": []}
        spawn_cell = key == (0, 0, 0)
        ox, oy, oz = key[0] * CELL_SIZE, key[1] * CELL_SIZE, key[2] * CELL_SIZE
        if spawn_cell or rng.random() < CLUSTER_CHANCE:
            if spawn_cell:
                # A field just ahead of the arrival point, on the way to Dyson Prime.
                c = self.dyson_dir * 1400.0 + Vec3(260.0, 0.0, -120.0)
                centre = (c.x, c.y, c.z)
            else:
                centre = (rng.uniform(300, CELL_SIZE - 300), rng.uniform(300, CELL_SIZE - 300), rng.uniform(300, CELL_SIZE - 300))
            self._build_cluster(node, cell, rng, centre, (ox, oy, oz), dense=spawn_cell)
        if spawn_cell or rng.random() < BEACON_CHANCE:
            if spawn_cell:
                b = self.dyson_dir * 520.0 + Vec3(-90.0, 0.0, 40.0)
                bpos = (b.x, b.y, b.z)
            else:
                bpos = (rng.uniform(200, CELL_SIZE - 200), rng.uniform(200, CELL_SIZE - 200), rng.uniform(200, CELL_SIZE - 200))
            self._build_beacon(node, cell, bpos, (ox, oy, oz), rng)
        self.cells[key] = cell
        self._refresh_rocks_near()

    def _build_cluster(self, parent, cell, rng: Random, centre, origin, dense: bool = False) -> None:
        mesh = _Mesh("deep-space-asteroids", normals=True)
        tags = LineSegs("deep-space-asteroid-tags")
        tags.setThickness(1.2 * self.line_scale)
        count = rng.randint(12, 18) if dense else rng.randint(5, 12)
        spread = rng.uniform(380.0, 760.0)
        biggest = None
        for _ in range(count):
            r = rng.uniform(6.0, 28.0) if rng.random() < 0.8 else rng.uniform(40.0, 120.0)
            p = (centre[0] + rng.gauss(0, spread), centre[1] + rng.gauss(0, spread), centre[2] + rng.gauss(0, spread * 0.5))
            self._rock(mesh, rng, p, r)
            cell["rocks"].append((origin[0] + p[0], origin[1] + p[1], origin[2] + p[2], r * 0.9))
            if biggest is None or r > biggest[1]:
                biggest = (p, r)
        rock_np = parent.attachNewNode(mesh.node().node())
        rock_np.setTwoSided(False)
        if biggest is not None:
            # holo survey ring around the largest rock
            (px, py, pz), r = biggest
            tags.setColor(*HUD_CYAN, 0.55)
            rr = r * 1.6
            for k in range(49):
                a = math.tau * k / 48
                (tags.moveTo if k == 0 else tags.drawTo)(px + math.cos(a) * rr, py + math.sin(a) * rr, pz)
            tag_np = parent.attachNewNode(tags.create())
            tag_np.setLightOff(1)
            tag_np.setTransparency(TransparencyAttrib.MAlpha)
            tag_np.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
            tag_np.setDepthWrite(False)

    @staticmethod
    def _rock(mesh: _Mesh, rng: Random, centre, radius: float) -> None:
        """Lumpy low-poly rock: an icosahedron, subdivided once, displaced, flat shaded."""
        t = (1.0 + 5 ** 0.5) / 2.0
        verts = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
                 (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
        faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
                 (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
        vs = [Vec3(*v) / Vec3(*v).length() for v in verts]
        mids = {}

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in mids:
                m = (vs[a] + vs[b]) * 0.5
                m.normalize()
                vs.append(m)
                mids[key] = len(vs) - 1
            return mids[key]

        sub = []
        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            sub += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        stretch = Vec3(rng.uniform(0.7, 1.3), rng.uniform(0.7, 1.3), rng.uniform(0.6, 1.1))
        disp = [radius * rng.uniform(0.78, 1.12) for _ in vs]
        pts = [Vec3(v.x * stretch.x * d, v.y * stretch.y * d, v.z * stretch.z * d) + Vec3(*centre) for v, d in zip(vs, disp)]
        tone = rng.uniform(0.85, 1.15)
        base = (0.30 * tone, 0.28 * tone, 0.26 * tone) if rng.random() < 0.7 else (0.26 * tone, 0.24 * tone, 0.30 * tone)
        for a, b, c in sub:
            pa, pb, pc = pts[a], pts[b], pts[c]
            n = (pb - pa).cross(pc - pa)
            if n.lengthSquared() <= 0:
                continue
            n.normalize()
            g = rng.uniform(0.85, 1.1)
            col = (base[0] * g, base[1] * g, base[2] * g, 1.0)
            ia = mesh.vertex(pa, col, n)
            ib = mesh.vertex(pb, col, n)
            ic = mesh.vertex(pc, col, n)
            mesh.tri(ia, ib, ic)

    def _build_beacon(self, parent, cell, pos, origin, rng: Random) -> None:
        mesh = _Mesh("deep-space-beacon", normals=True)
        px, py, pz = pos
        mesh.box((px, py, pz), (6.0, 6.0, 44.0), (0.16, 0.17, 0.20, 1.0))
        mesh.box((px, py, pz + 24.0), (12.0, 12.0, 4.0), (0.22, 0.23, 0.27, 1.0))
        mesh.box((px, py, pz - 24.0), (10.0, 10.0, 4.0), (0.22, 0.23, 0.27, 1.0))
        parent.attachNewNode(mesh.node().node())
        ring = LineSegs("deep-space-beacon-ring")
        ring.setThickness(1.6 * self.line_scale)
        ring.setColor(*HUD_AMBER, 0.8)
        for z, rr in ((pz + 10.0, 16.0), (pz - 10.0, 16.0), (pz, 22.0)):
            for k in range(41):
                a = math.tau * k / 40
                (ring.moveTo if k == 0 else ring.drawTo)(px + math.cos(a) * rr, py + math.sin(a) * rr, z)
        ring_np = parent.attachNewNode(ring.create())
        ring_np.setLightOff(1)
        ring_np.setTransparency(TransparencyAttrib.MAlpha)
        ring_np.setDepthWrite(False)
        blink = parent.attachNewNode(_points_node("deep-space-beacon-light", [(px, py, pz + 27.0)], [(1.0, 0.6, 0.3, 1.0)]).node())
        blink.setRenderModeThickness(7.0 * self.line_scale)
        blink.setLightOff(1)
        blink.setTransparency(TransparencyAttrib.MAlpha)
        cell["blinks"].append(blink)
        cell["rocks"].append((origin[0] + px, origin[1] + py, origin[2] + pz, 24.0))

    # ------------------------------------------------------------------
    # HUD
    # ------------------------------------------------------------------
    def _update_hud(self, dt: float) -> None:
        app = self.app
        self.stick_marker.setPos(self.stick[0] * 0.10, 0, -self.stick[1] * 0.10)
        bx0, bx1, zero_z, bz0, bz1 = self.throttle_geom
        span = (bz1 - bz0) / (1.0 + REVERSE_FRACTION)
        h = self.throttle * span
        if abs(h) < 1e-4:
            self.throttle_fill.hide()
        else:
            self.throttle_fill.show()
            self.throttle_fill.setPos(bx0, 0, zero_z if h > 0 else zero_z + h)
            self.throttle_fill.setScale(bx1 - bx0, 1, abs(h))
            col = HUD_CYAN if h > 0 else HUD_RED
            if self.boost_left > 0.0:
                col = HUD_AMBER
            self.throttle_fill.setColor(*col, 0.75)
        self.throttle_text.setText(f"{int(round(self.throttle * 100))}%")
        speed = self.vel.length()
        if self.mode == "supercruise":
            self.speed_text.setText(f"{speed / 1000.0:,.1f} km/s")
        else:
            self.speed_text.setText(f"{int(round(speed))} m/s")
        parts = []
        if self.mode == "charging":
            parts.append(f"FRAME SHIFT  {max(0.0, SC_CHARGE_TIME - self.charge):.1f}")
        elif self.mode == "supercruise":
            parts.append("SUPERCRUISE  //  J DROP")
        if self.boost_left > 0.0:
            parts.append("BOOST")
        elif self.boost_cooldown > 0.0 and self.mode == "normal":
            parts.append("BOOST RECHARGING")
        parts.append("FA ON" if self.flight_assist else "FA OFF")
        self.mode_text.setText("   //   ".join(parts))
        self.mode_text.setFg((*(HUD_RED if not self.flight_assist else HUD_AMBER), 0.95))
        # message
        if self.message_time > 0.0:
            self.message_time = max(0.0, self.message_time - dt)
            self.msg_text.setText(self.message)
            self.msg_text.setFg((*HUD_AMBER, min(1.0, self.message_time / 0.5) * 0.95))
        else:
            self.msg_text.setFg((*HUD_AMBER, 0.0))
        # Dyson Prime marker
        au = self.dyson_distance_au()
        cam_space = self.sky_cam.getRelativeVector(self.sky_scene, self.dyson_dir)
        near_floor = au - DYSON_FLOOR_AU < 0.6
        label = f"DYSON PRIME\n{au:,.1f} AU" + ("\nBEYOND REACH" if near_floor else "")
        projected = Point2()
        shown = False
        aspect = app.camLens.getAspectRatio() if hasattr(app, "camLens") else 1.777
        # Pass 282.63: no target lock on the sphere itself (bracket + label
        # removed).  Only a small edge arrow shows the way when it is off-screen.
        del label
        if not self.dyson_marker.isHidden():
            self.dyson_marker.hide()
        if not self.dyson_label.isHidden():
            self.dyson_label.hide()
        if cam_space.y > 0.0 and self.sky_lens.project(Point3(cam_space * 1000.0), projected):
            self.dyson_arrow.hide()
            shown = True
        if not shown:
            self.dyson_arrow.show()
            ang = math.atan2(cam_space.z, cam_space.x if abs(cam_space.x) > 1e-6 else 1e-6)
            aspect = app.camLens.getAspectRatio() if hasattr(app, "camLens") else 1.777
            self.dyson_arrow.setPos(math.cos(ang) * min(aspect - 0.15, 0.85 * aspect), 0, math.sin(ang) * 0.82)
            self.dyson_arrow.setR(-math.degrees(ang))

    # ------------------------------------------------------------------
    def report(self) -> dict:
        return {
            "active": bool(self.active),
            "mode": self.mode,
            "flight_assist": bool(self.flight_assist),
            "throttle": round(self.throttle, 3),
            "speed": round(self.vel.length(), 2),
            "position": [round(v, 1) for v in self.pos],
            "distance_travelled": round(self.distance_travelled, 1),
            "dyson_au": round(self.dyson_distance_au(), 3),
            "dyson_floor_au": DYSON_FLOOR_AU,
            "dyson_panels": int(getattr(self, "dyson_panel_count", 0)),
            "cells": len(self.cells),
            "rocks_near": len(self.rocks_near),
            "dust_shader": bool(self.shader_ok),
            "hidden_world_nodes": len(self.hidden_scene),
        }

    def destroy(self) -> None:
        self.deactivate()
        if not self.built:
            return
        for np_ in (self.local_root, self.cockpit, self.hud, self.throttle_root):
            if np_ is not None and not np_.isEmpty():
                np_.removeNode()
        try:
            self.app.win.removeDisplayRegion(self.sky_region)
        except Exception:
            pass
        self.built = False


class SpaceBackdrop:
    """Pass 282.60: the same sky (stars, galactic band, nebulae, ringed gas giant
    and Dyson Prime) built into any sky scene, e.g. the hub's space sky.

    It reuses DeepSpaceFlight's sky builders, which only need ``sky_scene``,
    ``line_scale`` and ``dyson_dir``, so both places show the same Dyson Prime.
    """

    def __init__(self, scene: NodePath, line_scale: float, dyson_direction, gas_giant: bool = True, dyson_scale: float = 1.0):
        self.sky_scene = scene
        self.line_scale = float(line_scale)
        self.dyson_dir = Vec3(dyson_direction)
        self.dyson_dir.normalize()
        DeepSpaceFlight._build_stars(self)
        if gas_giant:
            DeepSpaceFlight._build_gas_giant(self)
        DeepSpaceFlight._build_dyson(self)
        self.dyson_root.setScale(float(dyson_scale))
        self.frames = 0

    def animate(self, dt: float) -> None:
        self.frames += 1
        self.dyson_spin.setH(self.dyson_spin.getH() + dt * 0.35)
        for i, sw in enumerate(self.dyson_swarms):
            sw.setH(sw.getH() + dt * (0.8 if i == 0 else -0.55))
        self.dyson_glows[0].setAlphaScale(0.92 + 0.08 * math.sin(self.frames * 0.07))


__all__ = ["DeepSpaceFlight", "SpaceBackdrop", "DYSON_FLOOR_AU", "DYSON_START_AU", "MAX_SPEED", "SC_MAX_SPEED"]
