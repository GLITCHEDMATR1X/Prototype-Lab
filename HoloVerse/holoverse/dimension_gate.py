"""HoloVerse Pass 282.57: dimension gates beside the guides that open them.

A gate is a solid stone portal (plinth, two pillars, a lintel and a round
frame) with holo accents: glowing glyph strips, a softly pulsing membrane and
a light beam rising behind it.  The guide who stands beside it opens the
dimension from their dialogue (``archive_visibility.json`` ``bot_hosted``),
so the dimension no longer needs an orb in Gleebs' archive.

Gates are visual only.  They are placed on open ground the ring layouts keep
clear for the guide, and the membrane is walk-through.

Pass 282.57 added IO's (Afterlife of IO, at the start) and Mirror's (Mirror's
Limbo, in Metropolis); Pass 282.58 added Vanta (Glyphbound), Solace (Anomaly
Sequence), Ember (Vector Wars), the Archivist (The Archivist), Sable (Anatomic)
and Orbit (HoloMap, in Nyx's clearing).  Nyx's REDACTED port in the Mushroom
ring is part of that ring's own layout (``fungal_civilization._port``).
"""
from __future__ import annotations

import math

from panda3d.core import ColorBlendAttrib, TransparencyAttrib

from holoverse import metropolis_city as MC
from holoverse import region_mesh_kit as RMK

GATE_LIGHT = RMK.Lighting(sun=(0.92, 0.90, 0.86), sky=(0.36, 0.40, 0.48), bounce=(0.22, 0.22, 0.24))
STONE = (0.16, 0.17, 0.21)
STONE_LIGHT = (0.30, 0.31, 0.36)
BEAM_HEIGHT = 140.0
PORTAL_RADIUS = 3.6
PORTAL_CENTRE_Z = 5.0
VISIBLE_RANGE = 1600.0        # the beam: a landmark from far away
SOLID_RANGE = 500.0           # the stone frame and membrane: only up close

# Accent colour per dimension title.
GATE_STYLES = {
    "Mirror's Limbo": {"accent": (0.78, 0.90, 1.00), "membrane": (0.62, 0.78, 1.00)},
    "Afterlife of IO": {"accent": (1.00, 0.86, 0.56), "membrane": (1.00, 0.92, 0.72)},
    # Pass 282.58: the rest of the guide-hosted dimensions.
    "The Archivist": {"accent": (0.60, 0.90, 1.00), "membrane": (0.70, 0.92, 1.00)},
    "Anatomic": {"accent": (1.00, 0.32, 0.30), "membrane": (1.00, 0.45, 0.40)},
    "Anomaly Sequence": {"accent": (0.95, 0.38, 1.00), "membrane": (0.55, 1.00, 1.00)},
    "Vector Wars": {"accent": (0.45, 1.00, 0.45), "membrane": (0.55, 1.00, 0.60)},
    "HoloMap": {"accent": (0.40, 0.66, 1.00), "membrane": (0.50, 0.75, 1.00)},
    "Glyphbound": {"accent": (0.86, 1.00, 0.44), "membrane": (0.92, 1.00, 0.62)},
}
DEFAULT_STYLE = {"accent": (0.45, 0.95, 1.00), "membrane": (0.45, 0.95, 1.00)}


def style_for(title: str) -> dict:
    return dict(GATE_STYLES.get(str(title), DEFAULT_STYLE))


def _additive(np_):
    np_.setLightOff(1)
    np_.setShaderOff(100)
    np_.setTextureOff(10)
    np_.setFogOff(1)
    np_.setDepthWrite(False)
    np_.setTwoSided(True)
    np_.setTransparency(TransparencyAttrib.MAlpha)
    np_.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
    np_.setBin("fixed", 40)


def _solid_mesh(accent):
    """Stone frame in gate space: the opening faces +y/-y, centred on x = 0."""
    mb = MC.MeshBuilder()
    plain, emissive = 0.5, 0.0
    mb.prism(0.0, 0.0, -0.6, 7.2, 7.2, 1.0, 18, (*STONE, plain))                          # plinth
    mb.prism(0.0, 0.0, 0.35, 6.4, 6.4, 0.08, 18, (*accent, emissive), cap=False, double=True)  # glowing rim
    for side in (-1.0, 1.0):
        x = side * 4.6
        mb.obox(x, 0.0, 0.3, 1.5, 1.5, 9.6, 0.0, (*STONE, plain))                           # pillars
        mb.obox(x, 0.0, 9.9, 2.0, 2.0, 0.6, 0.0, (*STONE_LIGHT, plain))                     # pillar caps
        for row in range(4):                                                                 # glyph strips
            z = 1.6 + row * 1.9
            mb.obox(x, 0.78, z, 0.9 - row * 0.12, 0.06, 0.28, 0.0, (*accent, emissive))
            mb.obox(x, -0.78, z, 0.9 - row * 0.12, 0.06, 0.28, 0.0, (*accent, emissive))
    mb.obox(0.0, 0.0, 10.5, 11.4, 1.8, 1.1, 0.0, (*STONE_LIGHT, plain))                     # lintel
    mb.obox(0.0, 0.92, 10.85, 7.0, 0.06, 0.24, 0.0, (*accent, emissive))
    mb.obox(0.0, -0.92, 10.85, 7.0, 0.06, 0.24, 0.0, (*accent, emissive))
    # Round frame inside the pillars, in the x-z plane.
    ring = [(math.cos(a) * PORTAL_RADIUS, 0.0, PORTAL_CENTRE_Z + math.sin(a) * PORTAL_RADIUS)
            for a in (math.tau * k / 20.0 for k in range(21))]
    mb.sweep(ring, 0.55, 0.55, (*STONE_LIGHT, plain))
    inner = [(math.cos(a) * (PORTAL_RADIUS - 0.36), 0.0, PORTAL_CENTRE_Z + math.sin(a) * (PORTAL_RADIUS - 0.36))
             for a in (math.tau * k / 20.0 for k in range(21))]
    mb.sweep(inner, 0.62, 0.12, (*accent, emissive))
    return mb


def _membrane_mesh(rgb):
    """A fan in the x-z plane: bright at the edge, clearer in the middle."""
    mb = MC.MeshBuilder()
    r = PORTAL_RADIUS - 0.5
    centre = mb.count
    mb.rec.append((0.0, 0.0, 0.0, 0.0, 1.0, 0.0, rgb[0], rgb[1], rgb[2], 0.08, 0.0, 0.0))
    mb.count += 1
    sides = 32
    for k in range(sides):
        a = math.tau * k / sides
        mb.rec.append((math.cos(a) * r, 0.0, math.sin(a) * r, 0.0, 1.0, 0.0, rgb[0], rgb[1], rgb[2], 0.42, 0.0, 0.0))
        mb.count += 1
    for k in range(sides):
        mb.idx.extend((centre, centre + 1 + k, centre + 1 + (k + 1) % sides))
    return mb


def _beam_mesh(rgb):
    mb = MC.MeshBuilder()
    for radius, alpha in ((1.0, 0.45), (0.5, 0.80)):
        sides = 20
        for k in range(sides):
            a0, a1 = math.tau * k / sides, math.tau * (k + 1) / sides
            pts = [(math.cos(a0) * radius, math.sin(a0) * radius, 0.0), (math.cos(a1) * radius, math.sin(a1) * radius, 0.0),
                   (math.cos(a1) * radius, math.sin(a1) * radius, 1.0), (math.cos(a0) * radius, math.sin(a0) * radius, 1.0)]
            base = mb.count
            for q, al in zip(pts, (alpha, alpha, 0.0, 0.0)):
                mb.rec.append((q[0], q[1], q[2], 0.0, 0.0, 1.0, rgb[0], rgb[1], rgb[2], al, 0.0, 0.0))
            mb.idx.extend((base, base + 1, base + 2, base, base + 2, base + 3))
            mb.count += 4
    return mb


class DimensionGate:
    """One gate.  ``heading`` is in degrees (Panda H); the opening faces along
    the heading's +y, so a gate turned towards the player shows its membrane."""

    def __init__(self, parent, title: str, pos, heading: float, gsg=None):
        self.title = str(title)
        style = style_for(title)
        self.root = parent.attachNewNode(f"dimension-gate-{self.title.lower().replace(' ', '-').replace(chr(39), '')}")
        self.root.setPos(float(pos[0]), float(pos[1]), float(pos[2]))
        self.root.setH(float(heading))
        self.root.setPythonTag("dimension_gate_title", self.title)
        self.solid = RMK.bake_model("dimension-gate-stone", _solid_mesh(style["accent"]), gsg, GATE_LIGHT)
        self.solid.reparentTo(self.root)
        self.solid.setTextureOff(10)
        self.fx = self.root.attachNewNode("dimension-gate-fx")
        _additive(self.fx)
        self.membrane = self.fx.attachNewNode(MC.make_node("dimension-gate-membrane", *_membrane_mesh(style["membrane"]).arrays()))
        self.membrane.setPos(0.0, 0.0, PORTAL_CENTRE_Z)
        self.beam = self.fx.attachNewNode(MC.make_node("dimension-gate-beam", *_beam_mesh(style["accent"]).arrays()))
        self.beam.setPos(0.0, -2.6, 0.0)
        self.beam.setScale(2.2, 2.2, BEAM_HEIGHT)
        self.shaded = MC.city_shader(gsg) is not None
        self.root.setPythonTag("dimension_gate_shaded", 1 if self.shaded else 0)

    def update(self, elapsed: float, player_xy=None):
        if self.root.isEmpty():
            return
        if player_xy is not None:
            p = self.root.getPos()
            far = math.hypot(p.x - player_xy[0], p.y - player_xy[1]) > VISIBLE_RANGE
            if far:
                if not self.root.isHidden():
                    self.root.hide()
                return
            if self.root.isHidden():
                self.root.show()
            near = math.hypot(p.x - player_xy[0], p.y - player_xy[1]) <= SOLID_RANGE
            for part in (self.solid, self.membrane):
                if near and part.isHidden():
                    part.show()
                elif not near and not part.isHidden():
                    part.hide()
        pulse = 0.78 + 0.22 * math.sin(float(elapsed) * 1.6)
        self.membrane.setColorScale(1.0, 1.0, 1.0, pulse)
        self.membrane.setR(float(elapsed) * 12.0 % 360.0)
        self.beam.setColorScale(1.0, 1.0, 1.0, 0.85 + 0.15 * math.sin(float(elapsed) * 0.9))

    def destroy(self):
        if not self.root.isEmpty():
            self.root.removeNode()


def gate_position(anchor, outward_angle: float, along: float = 0.0, outward: float = 0.0):
    """Offset from a guide's anchor, measured along the ring and outward."""
    rx, ry = math.cos(outward_angle), math.sin(outward_angle)
    tx, ty = -ry, rx
    return (float(anchor[0]) + tx * along + rx * outward, float(anchor[1]) + ty * along + ry * outward)


__all__ = ["DimensionGate", "gate_position", "style_for", "GATE_STYLES"]
