"""HoloVerse Pass 282.60: the MatrixCore hub rebuilt as a holographic nexus.

The start area used to be the old Observatory: a dark octagon floor, grey
"hologlass" wall cards, textured dome panels, a wireframe dome and a small
red-tinted Gleebs card, all layered over many passes so it read as broken
pieces.  It is now a place for two things: the artifacts that teleport you to
the regions, and Gleebs.

What this module draws (the old hub pieces are hidden, never deleted, so any
code that still looks them up keeps working):

* **Platform** - one solid octagon with a holographic inlay: concentric
  octagons, radial lines and bright worldway lanes from the centre to the eight
  corner gateways, where the region artifacts stand outside.
* **Walls** - a solid curb with a glowing trim and continuous holographic wall
  panels on the eight sides; open gateways at the eight corners framed by solid
  pillars and holo arches.
* **Dome** - a faint holographic lattice with a wide open oculus, so the sky
  stays visible.
* **Gleebs** - a projector at the centre (solid plinth, glowing lens, light
  cone) showing Gleebs in his own colours as a hologram: scanlines, a soft glow
  copy, a rising scan band and two orbiting rings.  The hologram turns to face
  you wherever you stand.
* **Space sky** - a sky layer (its own display region, drawn first) with stars,
  the galactic band and nebulae, a purple nebula behind a **giant Gleebs**
  looking down from space (upper body fading out of the dark, glowing eyes), and
  **Dyson Prime**, the red-star Dyson sphere, on the opposite side.  Stars,
  nebulae and Dyson Prime stay overhead everywhere in the world; the giant Gleebs
  fades out as you leave the hub's FLAT ring.
"""
from __future__ import annotations

import math
from pathlib import Path

from panda3d.core import (
    Camera,
    ColorBlendAttrib,
    LineSegs,
    NodePath,
    PerspectiveLens,
    PNMImage,
    SamplerState,
    Texture,
    TransparencyAttrib,
    Vec3,
    Vec4,
)

from holoverse import deep_space as DS

ROOT = Path(__file__).resolve().parents[1]
HUB_TEXTURES = ROOT / "assets" / "textures" / "hub"

HUB_RADIUS = 33.6                 # platform corner radius (the hub is 34)
CORNER_OFFSET_DEG = 22.5          # corners face the eight region artifacts
GATE_HALF_WIDTH = 3.2             # each corner gateway is 6.4 m wide
WALL_HEIGHT = 6.2
CURB_HEIGHT = 0.55
PROJECTOR_RADIUS = 2.6
PROJECTOR_HEIGHT = 0.9
GLEEBS_HEIGHT = 5.2               # hologram height above the projector lens
GLEEBS_ASPECT = 512.0 / 611.0     # gleebs_holo.png
GLEEBS_CENTRE_Z = PROJECTOR_HEIGHT + 0.25 + GLEEBS_HEIGHT * 0.5
RESYNC_FRAMES = 30                # re-hide old hub pieces this often

CYAN = (0.30, 0.92, 1.00)
CYAN_SOFT = (0.20, 0.70, 0.95)
AMBER = (1.00, 0.76, 0.32)
STEEL = (0.075, 0.085, 0.11)
STEEL_LIGHT = (0.13, 0.145, 0.18)
FLOOR_CENTRE = (0.060, 0.075, 0.110)
FLOOR_EDGE = (0.028, 0.032, 0.050)

# Sky layout (directions from the hub; +Y is "north", where you face on arrival)
GIANT_DIR = (0.0, 1.0, 0.22)      # giant Gleebs above the far side, behind the hologram
GIANT_DISTANCE = 70000.0
GIANT_HEIGHT_DEG = 30.0
GIANT_ASPECT = 512.0 / 430.0      # gleebs_giant.png
GIANT_EYES_UV = ((0.420, 0.477), (0.571, 0.483))
DYSON_DIR = (0.22, -1.0, 0.22)    # Dyson Prime across the other side
SKY_FULL_RADIUS = 320.0           # giant Gleebs fully visible inside the FLAT ring
SKY_GONE_RADIUS = 900.0           # ... and gone by here
HUB_SKY_RGB = (0.006, 0.006, 0.020)
BEACON_HEIGHT = 16.0              # Pass 282.62: artifact light columns
SKY_NEAR = 4000.0                 # nearest sky object is Dyson Prime at ~55 km

# Old hub visuals retired by this pass (hidden, kept for compatibility).
RETIRED_EXACT = {
    "surface-root": {"matrixcore-home-floor-authority", "panel-core", "panel-dome"},
    "line-root": {"home-navigation-ring", "home-navigation-spoke", "home-worldway-alignment-ray", "matrixcore-home-base",
                  "matrixcore-home-spine", "matrixcore-home-crown", "matrixcore-home-diamond", "matrixcore-home-approach-lane",
                  "matrixcore-home-approach-step", "lens-base"},
    "accent-root": {"matrixcore-gleebs-hologram"},
}
RETIRED_PREFIX = {
    "surface-root": ("observatory-",),
    "accent-root": ("observatory-",),
}
RETIRED_WHOLE = ("dome_root", "lens_root", "sky_root", "galaxy_root")


def _corner_angles():
    return [math.radians(CORNER_OFFSET_DEG + 45.0 * i) for i in range(8)]


# Pass 282.61: hub holograms draw in the "fixed" bin, in the order given by
# their sort numbers.  The "transparent" bin ignores those numbers and re-sorts
# by distance every frame; the Gleebs card, its glow, the light cone and the
# scan band sit almost on top of each other, so their order kept swapping as the
# camera moved and the hologram flickered.
HOLO_BIN = "fixed"


def _additive(np_: NodePath, bin_sort: int = 20) -> NodePath:
    np_.setTransparency(TransparencyAttrib.MAlpha)
    np_.setDepthWrite(False)
    np_.setTwoSided(True)
    np_.setLightOff(1)
    np_.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
    np_.setBin(HOLO_BIN, bin_sort)
    return np_


def _load_texture(app, name: str) -> Texture | None:
    path = HUB_TEXTURES / name
    try:
        if path.is_file():
            from panda3d.core import Filename

            tex = app.loader.loadTexture(Filename.fromOsSpecific(str(path)))
            tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
            tex.setMagfilter(SamplerState.FT_linear)
            tex.setAnisotropicDegree(8)
            tex.setWrapU(Texture.WMClamp)
            tex.setWrapV(Texture.WMClamp)
            return tex
    except Exception as exc:
        print(f"hub_nexus_texture_missing name={name} err={exc.__class__.__name__}:{exc}")
    return None


def _holo_panel_texture() -> Texture:
    """Energy-wall texture: bright at the base, fading upward, with scanlines.

    Pass 282.61: the scanlines were hard 2-pixel lines with no mipmaps, so at a
    distance they shimmered (moire) as you walked.  They are now a soft wave,
    and the texture is mipmapped with anisotropic filtering.
    """
    w, h = 64, 256
    img = PNMImage(w, h, 4)
    for y in range(h):
        t = y / (h - 1.0)                      # 0 = top row, 1 = bottom row
        base = 0.06 + 0.40 * (t ** 2.2)
        scan = 0.78 + 0.22 * math.cos(y * math.tau / 8.0)
        for x in range(w):
            d = min(x, w - 1 - x) / 6.0
            edge = 1.0 + 0.8 * max(0.0, 1.0 - d)
            a = min(1.0, base * scan * edge)
            img.setXelA(x, y, 1.0, 1.0, 1.0, a)
    tex = Texture("hub-holo-panel")
    tex.load(img)
    tex.setWrapU(Texture.WMRepeat)
    tex.setWrapV(Texture.WMClamp)
    tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
    tex.setMagfilter(SamplerState.FT_linear)
    tex.setAnisotropicDegree(8)
    return tex


def _textured_quad(name: str, w: float, h: float, u_repeat: float = 1.0) -> NodePath:
    from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter

    vdata = GeomVertexData(name, GeomVertexFormat.getV3t2(), Geom.UHStatic)
    vw = GeomVertexWriter(vdata, "vertex")
    tw = GeomVertexWriter(vdata, "texcoord")
    for x, z, u, v in ((-w / 2, 0, 0, 0), (w / 2, 0, u_repeat, 0), (w / 2, h, u_repeat, 1), (-w / 2, h, 0, 1)):
        vw.addData3(x, 0, z)
        tw.addData2(u, v)
    tris = GeomTriangles(Geom.UHStatic)
    tris.addVertices(0, 1, 2)
    tris.addVertices(0, 2, 3)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode(name)
    gn.addGeom(geom)
    return NodePath(gn)


class HubNexus:
    def __init__(self, app):
        self.app = app
        self.root = None
        self.sky_built = False
        self.sky_active = False
        self.frames = 0
        self.elapsed = 0.0
        self.retired_count = 0
        self.giant_alpha = 1.0

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    def build(self) -> None:
        app = self.app
        parent = getattr(app, "root_3d", None) or app.render
        if self.root is not None and not self.root.isEmpty():
            self.root.removeNode()
        self.line_scale = DS._line_scale(app)
        self.root = parent.attachNewNode("matrixcore-hub-nexus")
        self.root.setLightOff(1)
        self.root.setFogOff(1)
        self.root.setShaderOff(1)
        self._build_platform()
        self._build_walls()
        self._build_dome()
        self._build_projector()
        self._build_gleebs()
        if not self.sky_built:
            self._build_sky()
        self._build_artifact_beacons()
        self.retire_old_hub()
        print(f"hub_nexus_built retired={self.retired_count} sky={int(self.sky_built)}")

    def _build_platform(self) -> None:
        mesh = DS._Mesh("hub-nexus-floor")
        corners = _corner_angles()
        rings = (0.0, 0.18, 0.55, 1.0)
        for i in range(8):
            a0, a1 = corners[i], corners[(i + 1) % 8]
            for r0, r1 in zip(rings, rings[1:]):
                def col(t):
                    return (*(FLOOR_CENTRE[k] + (FLOOR_EDGE[k] - FLOOR_CENTRE[k]) * t for k in range(3)), 1.0)
                p = [Vec3(math.cos(a) * r * HUB_RADIUS, math.sin(a) * r * HUB_RADIUS, 0.02) for a, r in ((a0, r0), (a1, r0), (a1, r1), (a0, r1))]
                ids = [mesh.vertex(p[0], col(r0)), mesh.vertex(p[1], col(r0)), mesh.vertex(p[2], col(r1)), mesh.vertex(p[3], col(r1))]
                mesh.tri(ids[0], ids[1], ids[2])
                mesh.tri(ids[0], ids[2], ids[3])
        floor = self.root.attachNewNode(mesh.node().node())
        floor.setTwoSided(True)
        # holographic inlay
        inlay = LineSegs("hub-nexus-inlay")
        inlay.setThickness(1.2 * self.line_scale)
        for r, alpha in ((6.0, 0.55), (12.0, 0.30), (19.0, 0.26), (26.0, 0.30), (32.2, 0.55)):
            inlay.setColor(*CYAN, alpha)
            for k in range(9):
                a = corners[k % 8]
                (inlay.moveTo if k == 0 else inlay.drawTo)(math.cos(a) * r, math.sin(a) * r, 0.045)
        inlay.setColor(*CYAN_SOFT, 0.16)
        for k in range(16):
            a = math.radians(11.25 + 22.5 * k)
            inlay.moveTo(math.cos(a) * 6.0, math.sin(a) * 6.0, 0.045)
            inlay.drawTo(math.cos(a) * 32.0, math.sin(a) * 32.0, 0.045)
        inlay_np = _additive(self.root.attachNewNode(inlay.create()), 6)
        # worldway lanes: bright twin lines from the projector to each gateway
        lanes = LineSegs("hub-nexus-worldway-lanes")
        lanes.setThickness(1.8 * self.line_scale)
        for a in corners:
            rx, ry = math.cos(a), math.sin(a)
            tx, ty = -ry, rx
            for side in (-1.0, 1.0):
                lanes.setColor(*CYAN, 0.75)
                lanes.moveTo(rx * 4.0 + tx * side * 0.9, ry * 4.0 + ty * side * 0.9, 0.05)
                lanes.drawTo(rx * (HUB_RADIUS - 0.3) + tx * side * 1.6, ry * (HUB_RADIUS - 0.3) + ty * side * 1.6, 0.05)
            # chevrons pointing out toward the artifact
            lanes.setColor(*AMBER, 0.60)
            for d in (13.0, 18.0, 23.0, 28.0):
                cx, cy = rx * d, ry * d
                lanes.moveTo(cx - rx * 0.8 + tx * 1.0, cy - ry * 0.8 + ty * 1.0, 0.055)
                lanes.drawTo(cx, cy, 0.055)
                lanes.drawTo(cx - rx * 0.8 - tx * 1.0, cy - ry * 0.8 - ty * 1.0, 0.055)
        self.lanes = _additive(self.root.attachNewNode(lanes.create()), 7)
        self.inlay = inlay_np

    def _build_walls(self) -> None:
        corners = _corner_angles()
        solid = DS._Mesh("hub-nexus-curb-and-pillars")
        trim = LineSegs("hub-nexus-trim")
        trim.setThickness(1.6 * self.line_scale)
        tex = _holo_panel_texture()
        self.wall_panels = self.root.attachNewNode("hub-nexus-holo-walls")
        _additive(self.wall_panels, 12)
        self.wall_panels.setTexture(tex)
        for i in range(8):
            a0, a1 = corners[i], corners[(i + 1) % 8]
            c0 = Vec3(math.cos(a0), math.sin(a0), 0) * HUB_RADIUS
            c1 = Vec3(math.cos(a1), math.sin(a1), 0) * HUB_RADIUS
            side = c1 - c0
            side.normalize()
            # wall runs between the two corner gateways
            s0 = c0 + side * GATE_HALF_WIDTH
            s1 = c1 - side * GATE_HALF_WIDTH
            inward = Vec3(-side.y, side.x, 0)
            if inward.dot(-(s0 + s1) * 0.5) < 0:
                inward = -inward
            t = 0.30
            o0, o1 = s0 - inward * t, s1 - inward * t
            n0, n1 = s0 + inward * t, s1 + inward * t
            top = CURB_HEIGHT
            solid.quad(o0, o1, o1 + Vec3(0, 0, top), o0 + Vec3(0, 0, top), (*STEEL, 1.0))
            solid.quad(n1, n0, n0 + Vec3(0, 0, top), n1 + Vec3(0, 0, top), (*STEEL_LIGHT, 1.0))
            solid.quad(o0 + Vec3(0, 0, top), o1 + Vec3(0, 0, top), n1 + Vec3(0, 0, top), n0 + Vec3(0, 0, top), (*STEEL_LIGHT, 1.0))
            trim.setColor(*CYAN, 0.85)
            trim.moveTo(n0 + Vec3(0, 0, top + 0.02))
            trim.drawTo(n1 + Vec3(0, 0, top + 0.02))
            trim.setColor(*CYAN, 0.45)
            trim.moveTo(s0 + Vec3(0, 0, WALL_HEIGHT))
            trim.drawTo(s1 + Vec3(0, 0, WALL_HEIGHT))
            # one continuous holo panel over the curb
            mid = (s0 + s1) * 0.5
            span = (s1 - s0).length()
            panel = _textured_quad(f"hub-nexus-wall-{i}", span, WALL_HEIGHT - top, u_repeat=span / 3.0)
            panel.reparentTo(self.wall_panels)
            panel.setPos(mid.x, mid.y, top)
            panel.setH(math.degrees(math.atan2(side.y, side.x)))
            panel.setColor(*CYAN_SOFT, 0.45)
        # gateway pillars and arches at each corner
        arches = LineSegs("hub-nexus-gate-arches")
        arches.setThickness(1.8 * self.line_scale)
        for a in corners:
            r = Vec3(math.cos(a), math.sin(a), 0)
            tng = Vec3(-r.y, r.x, 0)
            c = r * HUB_RADIUS
            for sgn in (-1.0, 1.0):
                p = c + tng * sgn * (GATE_HALF_WIDTH + 0.35) - r * 0.3
                solid.box((p.x, p.y, WALL_HEIGHT * 0.5 + 0.4), (0.8, 0.8, WALL_HEIGHT + 0.8), (*STEEL, 1.0))
                solid.box((p.x, p.y, WALL_HEIGHT + 0.95), (1.1, 1.1, 0.3), (*STEEL_LIGHT, 1.0))
                trim.setColor(*AMBER, 0.80)
                face = p - r * 0.42
                trim.moveTo(face.x, face.y, 0.6)
                trim.drawTo(face.x, face.y, WALL_HEIGHT)
            arches.setColor(*CYAN, 0.80)
            steps = 18
            for k in range(steps + 1):
                t = k / steps
                ang = math.pi * t
                x = math.cos(ang) * (GATE_HALF_WIDTH + 0.35)
                z = WALL_HEIGHT + 0.95 + math.sin(ang) * 1.6
                p = c + tng * x - r * 0.3
                (arches.moveTo if k == 0 else arches.drawTo)(p.x, p.y, z)
        self.root.attachNewNode(solid.node().node()).setTwoSided(False)
        self.trim = _additive(self.root.attachNewNode(trim.create()), 14)
        self.arches = _additive(self.root.attachNewNode(arches.create()), 14)

    def _build_dome(self) -> None:
        dome = LineSegs("hub-nexus-dome-lattice")
        dome.setThickness(1.0 * self.line_scale)
        corners = _corner_angles()
        top_z, base_z = 24.0, WALL_HEIGHT + 0.9
        oculus = 9.5
        rings = 5
        for k in range(1, rings):
            t = k / rings
            r = HUB_RADIUS + (oculus - HUB_RADIUS) * t
            z = base_z + (top_z - base_z) * math.sin(t * math.pi * 0.5)
            dome.setColor(*CYAN_SOFT, 0.16 - 0.02 * k)
            for j in range(9):
                a = corners[j % 8]
                (dome.moveTo if j == 0 else dome.drawTo)(math.cos(a) * r, math.sin(a) * r, z)
        for a in corners:
            dome.setColor(*CYAN_SOFT, 0.20)
            for k in range(13):
                t = k / 12
                r = HUB_RADIUS + (oculus - HUB_RADIUS) * t
                z = base_z + (top_z - base_z) * math.sin(t * math.pi * 0.5)
                (dome.moveTo if k == 0 else dome.drawTo)(math.cos(a) * r, math.sin(a) * r, z)
        dome.setColor(*CYAN, 0.42)
        for j in range(9):
            a = corners[j % 8]
            (dome.moveTo if j == 0 else dome.drawTo)(math.cos(a) * oculus, math.sin(a) * oculus, top_z)
        self.dome = _additive(self.root.attachNewNode(dome.create()), 8)

    def _build_projector(self) -> None:
        mesh = DS._Mesh("hub-nexus-projector")
        corners = _corner_angles()
        r0, r1, h = PROJECTOR_RADIUS, PROJECTOR_RADIUS * 0.82, PROJECTOR_HEIGHT
        for i in range(8):
            a0, a1 = corners[i], corners[(i + 1) % 8]
            b0 = Vec3(math.cos(a0) * r0, math.sin(a0) * r0, 0.02)
            b1 = Vec3(math.cos(a1) * r0, math.sin(a1) * r0, 0.02)
            t0 = Vec3(math.cos(a0) * r1, math.sin(a0) * r1, h)
            t1 = Vec3(math.cos(a1) * r1, math.sin(a1) * r1, h)
            mesh.quad(b0, b1, t1, t0, (*STEEL, 1.0))
            mesh.quad(Vec3(0, 0, h), t0, t1, Vec3(0, 0, h), (*STEEL_LIGHT, 1.0))
        self.root.attachNewNode(mesh.node().node()).setTwoSided(True)
        ring = LineSegs("hub-nexus-projector-ring")
        ring.setThickness(2.0 * self.line_scale)
        for rr, z, col in ((PROJECTOR_RADIUS * 0.82, PROJECTOR_HEIGHT + 0.01, (*CYAN, 0.95)), (PROJECTOR_RADIUS * 0.55, PROJECTOR_HEIGHT + 0.012, (*CYAN, 0.6)),
                           (PROJECTOR_RADIUS + 0.05, 0.08, (*AMBER, 0.6))):
            ring.setColor(*col)
            for k in range(41):
                a = math.tau * k / 40
                (ring.moveTo if k == 0 else ring.drawTo)(math.cos(a) * rr, math.sin(a) * rr, z)
        self.projector_ring = _additive(self.root.attachNewNode(ring.create()), 16)
        # light cone from the lens up through the hologram
        cone = DS._Mesh("hub-nexus-light-cone")
        segs = 32
        top_r, bot_r = 2.3, 0.85
        z0, z1 = PROJECTOR_HEIGHT + 0.02, PROJECTOR_HEIGHT + GLEEBS_HEIGHT + 0.8
        for k in range(segs):
            a0, a1 = math.tau * k / segs, math.tau * (k + 1) / segs
            p0 = Vec3(math.cos(a0) * bot_r, math.sin(a0) * bot_r, z0)
            p1 = Vec3(math.cos(a1) * bot_r, math.sin(a1) * bot_r, z0)
            p2 = Vec3(math.cos(a1) * top_r, math.sin(a1) * top_r, z1)
            p3 = Vec3(math.cos(a0) * top_r, math.sin(a0) * top_r, z1)
            ia = cone.vertex(p0, (*CYAN, 0.22))
            ib = cone.vertex(p1, (*CYAN, 0.22))
            ic = cone.vertex(p2, (*CYAN, 0.0))
            idd = cone.vertex(p3, (*CYAN, 0.0))
            cone.tri(ia, ib, ic)
            cone.tri(ia, ic, idd)
        self.cone = _additive(self.root.attachNewNode(cone.node().node()), 17)
        lens_tex = DS._radial_texture("hub-nexus-lens-glow", 64, 1.8, core=0.5)
        self.lens_glow = DS._billboard(self.root, "hub-nexus-lens-glow", lens_tex, 1.4, (0.45, 0.95, 1.0, 0.85), (0, 0, PROJECTOR_HEIGHT + 0.06))
        self.lens_glow.setBin(HOLO_BIN, 18)

    def _build_gleebs(self) -> None:
        """Gleebs as a hologram over the projector, turning to face the player."""
        # The name keeps "gleebs" so the hub's Gleebs-interaction search finds it.
        self.gleebs_root = self.root.attachNewNode("matrixcore-gleebs-holo-display")
        self.gleebs_root.setPos(0, 0, GLEEBS_CENTRE_Z)
        # Turned toward the camera every frame (an upright billboard you can query).
        self.gleebs_face = self.gleebs_root.attachNewNode("matrixcore-gleebs-holo-facing")
        tex = _load_texture(self.app, "gleebs_holo.png")
        h = GLEEBS_HEIGHT
        w = h * GLEEBS_ASPECT
        card = _textured_quad("matrixcore-gleebs-holo-card", w, h)
        card.reparentTo(self.gleebs_face)
        card.setPos(0, 0, -h * 0.5)
        card.setTransparency(TransparencyAttrib.MAlpha)
        card.setDepthWrite(False)
        card.setTwoSided(True)
        card.setLightOff(1)
        card.setBin(HOLO_BIN, 30)
        glow = _textured_quad("matrixcore-gleebs-holo-glow", w * 1.07, h * 1.05)
        glow.reparentTo(self.gleebs_face)
        glow.setPos(0, 0.02, -h * 0.525)
        _additive(glow, 31)
        if tex is not None:
            card.setTexture(tex)
            glow.setTexture(tex)
        card.setColorScale(0.90, 1.0, 1.0, 0.86)
        glow.setColorScale(0.35, 0.95, 1.0, 0.30)
        self.gleebs_card = card
        self.gleebs_glow = glow
        # rising scan band
        band = _textured_quad("matrixcore-gleebs-holo-scan", w * 1.02, 0.07)
        band.reparentTo(self.gleebs_face)
        band.setY(-0.02)
        _additive(band, 32)
        band.setColor(0.45, 1.0, 1.0, 0.22)
        self.gleebs_scan = band
        # two orbiting rings
        self.gleebs_rings = []
        for idx, (rr, z, tilt) in enumerate(((2.25, -h * 0.40, 7.0), (1.65, h * 0.42, -11.0))):
            ls = LineSegs(f"matrixcore-gleebs-holo-ring-{idx}")
            ls.setThickness(1.6 * self.line_scale)
            for k in range(61):
                a = math.tau * k / 60
                fade = 0.35 + 0.65 * (0.5 + 0.5 * math.cos(a * 2))
                ls.setColor(*CYAN, 0.75 * fade)
                (ls.moveTo if k == 0 else ls.drawTo)(math.cos(a) * rr, math.sin(a) * rr, 0)
            holder = self.gleebs_root.attachNewNode(f"matrixcore-gleebs-holo-ring-holder-{idx}")
            holder.setZ(z)
            holder.setP(tilt)
            ring_np = _additive(holder.attachNewNode(ls.create()), 33)
            self.gleebs_rings.append((holder, ring_np))

    # ------------------------------------------------------------------
    # Artifact beacons (Pass 282.62)
    # ------------------------------------------------------------------
    def _build_artifact_beacons(self) -> None:
        """A soft light column and a glowing ground ring at every artifact.

        The artifacts are thin wireframes on bright ground, so from the hub some
        looked like they were not there.  The beacon marks each one from across
        the hub and shows the column you can aim at to activate it."""
        old = getattr(self, "beacon_root", None)
        if old is not None and not old.isEmpty():
            old.removeNode()
        self.beacon_root = self.root.attachNewNode("hub-nexus-artifact-beacons")
        self.beacons = []
        self._beacon_source = list(getattr(self.app, "artifacts", None) or [])
        glow_tex = DS._radial_texture("hub-artifact-beacon-glow", 64, 1.6, core=0.35)
        for artifact in self._beacon_source:
            try:
                base = artifact.get("pedestal_pos", artifact.get("pos"))
                mode_id = artifact.get("dimension_mode_id", "")
                try:
                    col = tuple(self.app.artifact_color_for_mode(mode_id, 1.0, "primary"))[:3]
                except Exception:
                    col = CYAN
                holder = self.beacon_root.attachNewNode(f"hub-artifact-beacon-{artifact.get('id')}")
                holder.setPos(float(base.x), float(base.y), 0.0)
                column = DS._Mesh("hub-artifact-beacon-column")
                segs, radius, height = 18, 0.75, BEACON_HEIGHT
                for k in range(segs):
                    a0, a1 = math.tau * k / segs, math.tau * (k + 1) / segs
                    p0 = Vec3(math.cos(a0) * radius, math.sin(a0) * radius, 0.0)
                    p1 = Vec3(math.cos(a1) * radius, math.sin(a1) * radius, 0.0)
                    ia = column.vertex(p0, (*col, 0.30))
                    ib = column.vertex(p1, (*col, 0.30))
                    ic = column.vertex(p1 + Vec3(0, 0, height), (*col, 0.0))
                    idd = column.vertex(p0 + Vec3(0, 0, height), (*col, 0.0))
                    column.tri(ia, ib, ic)
                    column.tri(ia, ic, idd)
                col_np = _additive(holder.attachNewNode(column.node().node()), 10)
                ring = LineSegs("hub-artifact-beacon-ring")
                ring.setThickness(2.0 * self.line_scale)
                ring.setColor(*col, 0.85)
                for k in range(41):
                    ang = math.tau * k / 40
                    (ring.moveTo if k == 0 else ring.drawTo)(math.cos(ang) * 2.3, math.sin(ang) * 2.3, 0.07)
                ring_np = _additive(holder.attachNewNode(ring.create()), 9)
                glow = _textured_quad("hub-artifact-beacon-floor-glow", 6.0, 6.0)
                glow.reparentTo(holder)
                glow.setP(-90.0)
                glow.setPos(0.0, 3.0, 0.06)
                glow.setTexture(glow_tex)
                glow.setColor(*col, 0.55)
                _additive(glow, 8)
                self.beacons.append((col_np, ring_np, glow))
            except Exception as exc:
                print(f"hub_nexus_beacon_warning id={artifact.get('id')} err={exc.__class__.__name__}:{exc}")

    # ------------------------------------------------------------------
    # Sky layer
    # ------------------------------------------------------------------
    def _build_sky(self) -> None:
        app = self.app
        try:
            self.sky_scene = NodePath("hub-space-sky-scene")
            self.sky_scene.setLightOff(1)
            self.sky_scene.setFogOff(1)
            self.sky_scene.setShaderOff(10)
            self.sky_scene.setTransparency(TransparencyAttrib.MAlpha)
            self.sky_lens = PerspectiveLens()
            # Pass 282.61: near was 50, which left only metres of depth precision at
            # Dyson Prime (~50 km); its panels and seams z-fought as the view turned.
            self.sky_lens.setNearFar(SKY_NEAR, DS.SKY_FAR)
            self.sky_cam = self.sky_scene.attachNewNode(Camera("hub-space-sky-camera", self.sky_lens))
            self.sky_region = app.win.makeDisplayRegion()
            self.sky_region.setSort(-21)
            self.sky_region.setCamera(self.sky_cam)
            self.sky_region.setClearColorActive(True)
            self.sky_region.setClearColor(Vec4(*HUB_SKY_RGB, 1.0))
            self.sky_region.setClearDepthActive(True)
            # The main scene must not depth-test against the sky layer's depth.
            main_region = app.cam.node().getDisplayRegion(0)
            main_region.setClearDepthActive(True)
            self.backdrop = DS.SpaceBackdrop(self.sky_scene, self.line_scale, Vec3(*DYSON_DIR), gas_giant=True, dyson_scale=0.85)
            self._build_purple_nebula()
            self._build_giant_gleebs()
            self.sky_built = True
            self.sky_active = True
            # Pass 282.61: copy the camera's final rotation just before the frame
            # renders (igLoop is sort 50).  Copying it mid-frame let the sky lag a
            # frame behind any later camera change, so it swam while turning.
            try:
                app.taskMgr.remove("hub-space-sky-camera-sync")
                app.taskMgr.add(self._sky_cam_task, "hub-space-sky-camera-sync", sort=49)
            except Exception as exc:
                print(f"hub_nexus_sky_sync_warning:{exc.__class__.__name__}:{exc}")
        except Exception as exc:
            self.sky_built = False
            print(f"hub_nexus_sky_error:{exc.__class__.__name__}:{exc}")

    def _sky_pos(self, direction, distance: float) -> Vec3:
        d = Vec3(*direction)
        d.normalize()
        return d * distance

    def _build_purple_nebula(self) -> None:
        tex = _load_texture(self.app, "nebula_purple.png") or DS._radial_texture("hub-nebula-fallback", 128, 1.6)
        self.nebulae = []
        base = Vec3(*GIANT_DIR)
        base.normalize()
        right = Vec3(1, 0, 0)
        up = base.cross(right)
        up.normalize()
        for idx, (dx, dz, size_deg, col) in enumerate((
            (0.00, 0.02, 78.0, (0.85, 0.45, 1.00, 0.75)),
            (-0.34, -0.08, 46.0, (0.55, 0.35, 1.00, 0.55)),
            (0.30, 0.10, 52.0, (1.00, 0.40, 0.85, 0.45)),
            (0.05, 0.28, 40.0, (0.60, 0.50, 1.00, 0.40)),
        )):
            d = base + right * dx + up * dz
            d.normalize()
            dist = GIANT_DISTANCE * 1.3
            half = dist * math.tan(math.radians(size_deg) * 0.5)
            neb = DS._billboard(self.sky_scene, f"hub-purple-nebula-{idx}", tex, half, col, tuple(d * dist))
            neb.setBin("background", 1)
            neb.setR(idx * 47.0)
            self.nebulae.append(neb)

    def _build_giant_gleebs(self) -> None:
        tex = _load_texture(self.app, "gleebs_giant.png")
        d = Vec3(*GIANT_DIR)
        d.normalize()
        h = 2.0 * GIANT_DISTANCE * math.tan(math.radians(GIANT_HEIGHT_DEG) * 0.5)
        w = h * GIANT_ASPECT
        self.giant_root = self.sky_scene.attachNewNode("hub-giant-gleebs")
        self.giant_root.setPos(d * GIANT_DISTANCE)
        self.giant_root.lookAt(0, 0, 0)
        self.giant_root.setH(self.giant_root.getH() + 180.0)   # face the hub
        self.giant_root.setBin("background", 3)
        card = _textured_quad("hub-giant-gleebs-card", w, h)
        card.reparentTo(self.giant_root)
        card.setPos(0, 0, -h * 0.5)
        card.setTransparency(TransparencyAttrib.MAlpha)
        card.setDepthWrite(False)
        card.setTwoSided(True)
        card.setBin("background", 3)
        if tex is not None:
            card.setTexture(tex)
        card.setColorScale(1.0, 1.0, 1.0, 0.92)
        self.giant_card = card
        # glowing eyes
        glow_tex = DS._radial_texture("hub-giant-eye-glow", 64, 2.0, core=0.7)
        self.giant_eyes = []
        for u, v in GIANT_EYES_UV:
            x = (u - 0.5) * w
            z = -h * 0.5 + v * h
            for radius, col in ((h * 0.055, (0.45, 1.0, 0.40, 0.55)), (h * 0.018, (0.85, 1.0, 0.75, 0.95))):
                eye = _textured_quad("hub-giant-gleebs-eye", radius * 2, radius * 2)
                eye.reparentTo(self.giant_root)
                eye.setPos(x, -h * 0.002, z - radius)
                eye.setTexture(glow_tex)
                _additive(eye, 0)
                eye.setBin("background", 4)
                eye.setColor(*col)
                self.giant_eyes.append((eye, col))

    # ------------------------------------------------------------------
    # Old hub pieces
    # ------------------------------------------------------------------
    def retire_old_hub(self) -> int:
        app = self.app
        count = 0
        for attr in ("surface_root", "line_root", "accent_root"):
            node = getattr(app, attr, None)
            if node is None or node.isEmpty():
                continue
            name = node.getName()
            exact = RETIRED_EXACT.get(name, set())
            prefixes = RETIRED_PREFIX.get(name, ())
            for child in node.getChildren():
                cname = child.getName()
                if cname in exact or any(cname.startswith(p) for p in prefixes):
                    if not child.isHidden():
                        child.hide()
                    count += 1
        # The old Observatory lens box floats over the centre (line-root boxes at z 9-11).
        line_root = getattr(app, "line_root", None)
        if line_root is not None and not line_root.isEmpty():
            if getattr(self, "_lens_scan_root", None) != line_root:
                self._lens_scan_root = line_root
                self._lens_nodes = []
                for child in line_root.getChildren():
                    if child.getName() in ("box-infill", "box-edge"):
                        b = child.getTightBounds(line_root)
                        if b:
                            c = (b[0] + b[1]) * 0.5
                            if math.hypot(c.x, c.y) < 3.0 and c.z > 8.0:
                                self._lens_nodes.append(child)
            for child in self._lens_nodes:
                if not child.isEmpty() and not child.isHidden():
                    child.hide()
                count += 1
        for attr in RETIRED_WHOLE:
            node = getattr(app, attr, None)
            if node is not None and not node.isEmpty():
                if not node.isHidden():
                    node.hide()
                count += 1
        self.retired_count = count
        return count

    # ------------------------------------------------------------------
    # Per frame
    # ------------------------------------------------------------------
    def _sky_should_draw(self) -> bool:
        app = self.app
        if getattr(app, "active_native_mode", None) is not None or bool(getattr(app, "external_suspended", False)):
            return False
        if bool(getattr(app, "native_mode_isolated", False)):
            return False
        if bool(getattr(app, "world_unlocked", False)) or float(getattr(app, "transition_target", 0.0) or 0.0) > 0.0:
            return False
        try:
            if app.deep_space_active():
                return False
        except Exception:
            pass
        return True

    def _sync_sky_camera(self) -> None:
        app = self.app
        try:
            self.sky_cam.setQuat(app.camera.getQuat(app.render))
            self.sky_lens.setFov(app.camLens.getFov())
            self.sky_lens.setAspectRatio(app.camLens.getAspectRatio())
        except Exception:
            pass

    def set_sky_active(self, active: bool) -> None:
        if not self.sky_built:
            return
        active = bool(active)
        if active != self.sky_active:
            try:
                self.sky_region.setActive(active)
            except Exception:
                pass
            self.sky_active = active

    def _sky_cam_task(self, task):
        # Pass 282.62: decide visibility here too.  This task keeps running while
        # a native dimension (HoloCore) freezes the host update, which is why the
        # HoloVerse sky used to stay drawn behind the dimension.
        if self.sky_built:
            self.set_sky_active(self._sky_should_draw())
            if self.sky_active:
                self._sync_sky_camera()
        return task.cont

    def update(self, dt: float) -> None:
        if self.root is None or self.root.isEmpty():
            self.build()
        self.frames += 1
        self.elapsed += max(0.0, float(dt or 0.0))
        t = self.elapsed
        fill_moving = abs(float(getattr(self.app, "hub_fill_alpha", 0.0)) - float(getattr(self.app, "hub_fill_target", 0.0))) > 0.001
        if fill_moving or self.frames % RESYNC_FRAMES == 0:
            self.retire_old_hub()  # old hub code may re-show its pieces
        old = getattr(self.app, "gleebs_hologram_root", None)
        if old is not None and not old.isEmpty() and not old.isHidden():
            old.hide()  # the old card still runs its proximity fade; keep it out of sight
        # Gleebs hologram: turn to face the camera (upright, about Z only)
        try:
            cam = self.app.camera.getPos(self.app.render)
            centre = self.gleebs_root.getPos(self.app.render)
            dx, dy = float(cam.x - centre.x), float(cam.y - centre.y)
            if dx * dx + dy * dy > 1e-6:
                self.gleebs_face.setH(self.app.render, math.degrees(math.atan2(dx, -dy)))
        except Exception:
            pass
        # Pass 282.61: a gentle shimmer only.  The old one-frame 25% drop every 97
        # frames read as a texture flicker.
        flicker = 0.94 + 0.04 * math.sin(t * 9.0) * math.sin(t * 2.3)
        self.gleebs_card.setColorScale(0.90, 1.0, 1.0, 0.86 * flicker)
        self.gleebs_glow.setColorScale(0.35, 0.95, 1.0, 0.36 + 0.08 * math.sin(t * 2.2))
        self.gleebs_root.setZ(GLEEBS_CENTRE_Z + 0.08 * math.sin(t * 1.2))
        band_t = (t * 0.32) % 1.0
        self.gleebs_scan.setZ(-GLEEBS_HEIGHT * 0.5 + band_t * GLEEBS_HEIGHT)
        self.gleebs_scan.setAlphaScale(math.sin(band_t * math.pi))
        for idx, (holder, ring_np) in enumerate(self.gleebs_rings):
            ring_np.setH(ring_np.getH() + dt * (14.0 if idx == 0 else -19.0))
        self.cone.setAlphaScale(0.85 + 0.15 * math.sin(t * 2.6))
        self.lanes.setAlphaScale(0.80 + 0.20 * math.sin(t * 1.4))
        self.wall_panels.setAlphaScale(0.82 + 0.10 * math.sin(t * 0.9))
        arts = getattr(self.app, "artifacts", None) or []
        if len(arts) != len(getattr(self, "_beacon_source", [])) or any(x is not y for x, y in zip(arts, self._beacon_source)):
            self._build_artifact_beacons()
        for idx, (col_np, ring_np, glow) in enumerate(getattr(self, "beacons", [])):
            pulse = 0.80 + 0.20 * math.sin(t * 1.8 + idx * 0.7)
            col_np.setAlphaScale(pulse)
            glow.setAlphaScale(0.75 + 0.25 * pulse)
        # sky
        if not self.sky_built:
            return
        draw = self._sky_should_draw()
        self.set_sky_active(draw)
        if not draw:
            return
        app = self.app
        self._sync_sky_camera()
        try:
            bg = app.win.getClearColor()
            self.sky_region.setClearColor(Vec4(bg[0] * 0.4 + HUB_SKY_RGB[0] * 0.6, bg[1] * 0.4 + HUB_SKY_RGB[1] * 0.6,
                                               bg[2] * 0.4 + HUB_SKY_RGB[2] * 0.6, 1.0))
        except Exception:
            pass
        self.backdrop.animate(dt)
        try:
            p = app.player_pos
            r = math.hypot(float(p.x), float(p.y))
        except Exception:
            r = 0.0
        a = 1.0 if r <= SKY_FULL_RADIUS else max(0.0, 1.0 - (r - SKY_FULL_RADIUS) / (SKY_GONE_RADIUS - SKY_FULL_RADIUS))
        self.giant_alpha = a
        if a <= 0.001:
            if not self.giant_root.isHidden():
                self.giant_root.hide()
        else:
            if self.giant_root.isHidden():
                self.giant_root.show()
            breathe = 1.0 + 0.012 * math.sin(t * 0.35)
            self.giant_root.setScale(breathe)
            self.giant_card.setColorScale(1.0, 1.0, 1.0, 0.85 * a)
            pulse = 0.75 + 0.25 * math.sin(t * 1.1)
            for eye, col in self.giant_eyes:
                eye.setColor(col[0], col[1], col[2], col[3] * pulse * a)

    def report(self) -> dict:
        return {
            "built": bool(self.root is not None and not self.root.isEmpty()),
            "retired_old_pieces": int(self.retired_count),
            "sky_built": bool(self.sky_built),
            "sky_active": bool(self.sky_active),
            "giant_alpha": round(float(self.giant_alpha), 3),
            "dyson_panels": int(getattr(getattr(self, "backdrop", None), "dyson_panel_count", 0)),
            "gleebs_display": bool(getattr(self, "gleebs_root", None) is not None),
        }


__all__ = ["HubNexus"]
