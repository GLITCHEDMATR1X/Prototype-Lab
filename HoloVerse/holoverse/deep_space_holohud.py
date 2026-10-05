"""HoloSpace holographic cockpit HUD (Pass 282.76).

The flight readouts are projected inside the ship instead of drawn flat on the screen: three
glowing holo panels hang in the cockpit (camera space), tilted toward the pilot, drawn additive
over the canopy with a faint scan flicker.

  bottom-left    SHIP: shield and hull
  bottom-right   FLIGHT: speed, throttle, flight mode
  top-left       SYSTEMS: boost, system / Dyson Prime distance
  top-right      COMMS: flight messages, defence-perimeter / hostile warnings

Pass 282.77: the panels are compact and sit in the canopy corners (outside the clear window),
each turned to face the pilot, so they read as part of the cockpit instead of covering the view.

Colours come from the cockpit theme (``hud`` and ``hud_warn`` in assets/config/holospace_cockpit.json).
"""
from __future__ import annotations

import math

from panda3d.core import (
    ColorBlendAttrib,
    LineSegs,
    NodePath,
    Point3,
    TextNode,
    TransparencyAttrib,
)

# Corner panel placement (camera space, the canopy glass is at y = 1.25).  At the 82 degree view
# the screen spans about x +-1.04 and z +-0.59 at this depth; the panels sit outside the clear
# octagon window, in the glass corners.
CORNER_Y = 1.20
CORNER_SCALE = 0.80                 # panels are 0.32 x 0.105 canopy units after scaling
CORNER_EDGE_X = 0.205               # panel centre inset from the screen edge
CORNER_EDGE_TOP = 0.175             # below the region label in the top-left corner
CORNER_EDGE_BOTTOM = 0.165          # leaves room for the dash below


def _additive(np_: NodePath) -> None:
    np_.setTransparency(TransparencyAttrib.MAlpha)
    np_.setDepthWrite(False)
    np_.setDepthTest(False)
    np_.setTwoSided(True)
    np_.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))


class HoloHUD:
    def __init__(self, camera: NodePath, mesh_cls, font=None, line_scale: float = 1.0, lens=None):
        self.font = font
        self.line_scale = float(line_scale)
        self._mesh_cls = mesh_cls
        self.root = camera.attachNewNode("holospace-holo-hud")
        _additive(self.root)
        self.root.setLightOff(1)
        self.root.setFogOff(1)
        self.root.setShaderOff(10)
        self.root.setBin("fixed", 34)
        self.themed: list = []          # nodes tinted with the theme's hud colour
        self.bars: dict = {}
        self.texts: dict = {}
        self.hud_rgb = (0.40, 0.95, 1.00)
        self.warn_rgb = (1.00, 0.45, 0.32)
        self.t = 0.0
        self._cache: dict = {}
        self._corners: list = []        # (panel, x sign, top?) so a window resize can move them
        self.layout_key = None
        self._compute_corners(lens)
        self._build()
        self.root.hide()

    def _compute_corners(self, lens) -> None:
        """Corner positions from the real lens, so the panels stay in the corners at any FOV / aspect."""
        fov, aspect = 82.0, 16.0 / 9.0
        try:
            if lens is not None:
                fov = float(lens.getFov()[0])
                aspect = float(lens.getAspectRatio())
        except Exception:
            pass
        half_w = math.tan(math.radians(fov * 0.5)) * CORNER_Y
        half_h = half_w / max(1.0, aspect)
        self.corner_x = half_w - CORNER_EDGE_X
        self.corner_high_z = half_h - CORNER_EDGE_TOP
        self.corner_low_z = -(half_h - CORNER_EDGE_BOTTOM)
        self.layout_key = (round(fov, 2), round(aspect, 3))

    def relayout(self, lens) -> None:
        """Pass 282.83: move the corner panels after the window changes shape."""
        self._compute_corners(lens)
        for panel, sign_x, top in self._corners:
            if not panel.isEmpty():
                panel.setPos(sign_x * self.corner_x, CORNER_Y, self.corner_high_z if top else self.corner_low_z)

    # ------------------------------------------------------------------ building blocks
    def _panel(self, name, pos, hpr, w, h) -> NodePath:
        panel = self.root.attachNewNode(name)
        panel.setPos(*pos)
        panel.setHpr(*hpr)
        bg = self._mesh_cls(f"{name}-bg")
        bg.quad((-w, 0, -h), (w, 0, -h), (w, 0, h), (-w, 0, h), (1, 1, 1, 0.07))
        bg_np = panel.attachNewNode(bg.node().node())
        frame = LineSegs(f"{name}-frame")
        frame.setThickness(1.3 * self.line_scale)
        frame.setColor(1, 1, 1, 0.55)
        c = min(w, h) * 0.18
        pts = [(-w + c, h), (w - c, h), (w, h - c), (w, -h + c), (w - c, -h), (-w + c, -h), (-w, -h + c), (-w, h - c), (-w + c, h)]
        frame.moveTo(pts[0][0], 0, pts[0][1])
        for x, z in pts[1:]:
            frame.drawTo(x, 0, z)
        frame_np = panel.attachNewNode(frame.create())
        self.themed += [bg_np, frame_np]
        return panel

    def _text(self, parent, key, pos, scale, align=TextNode.ALeft, text="") -> NodePath:
        tn = TextNode(f"holo-text-{key}")
        if self.font is not None:
            tn.setFont(self.font)
        tn.setAlign(align)
        tn.setTextColor(1, 1, 1, 0.95)
        tn.setText(text)
        np_ = parent.attachNewNode(tn)
        np_.setPos(*pos)
        np_.setScale(scale)
        self.texts[key] = (tn, np_)
        self.themed.append(np_)
        return np_

    def _bar(self, parent, key, x0, z0, width, height) -> None:
        frame = LineSegs(f"holo-bar-{key}")
        frame.setThickness(1.0 * self.line_scale)
        frame.setColor(1, 1, 1, 0.45)
        frame.moveTo(x0, 0, z0)
        for x, z in ((x0 + width, z0), (x0 + width, z0 + height), (x0, z0 + height), (x0, z0)):
            frame.drawTo(x, 0, z)
        frame_np = parent.attachNewNode(frame.create())
        fill = self._mesh_cls(f"holo-bar-fill-{key}")
        fill.quad((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1), (1, 1, 1, 0.75))
        fill_np = parent.attachNewNode(fill.node().node())
        fill_np.setPos(x0 + 0.003, -0.001, z0 + 0.003)
        self.bars[key] = (fill_np, width - 0.006, height - 0.006)
        self.themed += [frame_np, fill_np]

    def _corner(self, name, x, z, w=0.20, h=0.066) -> NodePath:
        """A small panel in one corner of the canopy, outside the clear window."""
        # Parallel to the screen: at an 82 degree view a panel turned toward the eye is stretched
        # by perspective near the edges, while a flat one stays a clean, level rectangle.
        panel = self._panel(name, (x, CORNER_Y, z), (0.0, 0.0, 0.0), w, h)
        panel.setScale(CORNER_SCALE)
        self._corners.append((panel, 1.0 if x >= 0 else -1.0, z >= 0))
        return panel

    def _build(self) -> None:
        # Pass 282.77: four compact corner panels in the canopy corners, outside the clear
        # window, instead of two large panels over the view.
        bl = self._corner("holo-ship", -self.corner_x, self.corner_low_z)
        self._text(bl, "ship_head", (-0.182, -0.002, 0.040), 0.013, text="SHIP")
        for i, key in enumerate(("shield", "hull")):
            z = 0.006 - i * 0.040
            self._text(bl, f"{key}_label", (-0.182, -0.002, z - 0.006), 0.016, text=key.upper())
            self._bar(bl, key, -0.090, z - 0.010, 0.190, 0.018)
            self._text(bl, f"{key}_pct", (0.186, -0.002, z - 0.006), 0.015, TextNode.ARight)
        br = self._corner("holo-flight", self.corner_x, self.corner_low_z)
        self._text(br, "flight_head", (-0.182, -0.002, 0.040), 0.013, text="FLIGHT")
        self._text(br, "speed", (0.186, -0.002, 0.030), 0.030, TextNode.ARight)
        self._bar(br, "throttle", -0.182, -0.012, 0.300, 0.014)
        self._text(br, "throttle_pct", (0.186, -0.002, -0.010), 0.014, TextNode.ARight)
        self._text(br, "mode", (-0.182, -0.002, -0.050), 0.014)
        tl = self._corner("holo-systems", -self.corner_x, self.corner_high_z)
        self._text(tl, "title", (-0.182, -0.002, 0.036), 0.013, text="HOLOSPACE  //  DYSON PRIME")
        self._text(tl, "boost_label", (-0.182, -0.002, -0.006), 0.016, text="BOOST")
        self._bar(tl, "boost", -0.090, -0.010, 0.190, 0.018)
        self._text(tl, "boost_pct", (0.186, -0.002, -0.006), 0.015, TextNode.ARight)
        self._text(tl, "systems", (-0.182, -0.002, -0.046), 0.0135)
        tr = self._corner("holo-comms", self.corner_x, self.corner_high_z)
        self._text(tr, "comms_head", (-0.182, -0.002, 0.036), 0.013, text="COMMS")
        msg = self._text(tr, "message", (-0.182, -0.002, 0.000), 0.0145)
        self.texts["message"][0].setWordwrap(25.0)
        self._text(tr, "threat", (-0.182, -0.002, -0.046), 0.0135)

    # ------------------------------------------------------------------ theme / visibility
    def set_theme(self, hud_rgb, warn_rgb) -> None:
        self.hud_rgb = tuple(hud_rgb)
        self.warn_rgb = tuple(warn_rgb)
        for np_ in self.themed:
            np_.setColorScale(*self.hud_rgb, 1.0)

    def show(self) -> None:
        self.root.show()

    def hide(self) -> None:
        self.root.hide()

    def _set_text(self, key, text, warn=False, alpha=1.0) -> None:
        # Only touch Panda state when something changed (keeps the per-frame cost tiny).
        tn, np_ = self.texts[key]
        state = (text, bool(warn), round(float(alpha), 2), self.hud_rgb, self.warn_rgb)
        if self._cache.get(key) == state:
            return
        self._cache[key] = state
        if tn.getText() != text:
            tn.setText(text)
        rgb = self.warn_rgb if warn else self.hud_rgb
        np_.setColorScale(*rgb, state[2])

    def _set_bar(self, key, frac, warn=False) -> None:
        fill, w, h = self.bars[key]
        frac = round(max(0.0, min(1.0, float(frac))), 3)
        state = (frac, bool(warn), self.hud_rgb, self.warn_rgb)
        if self._cache.get(("bar", key)) == state:
            return
        self._cache[("bar", key)] = state
        if frac <= 0.001:
            fill.hide()
            return
        fill.show()
        fill.setScale(w * frac, 1.0, h)
        rgb = self.warn_rgb if warn else self.hud_rgb
        fill.setColorScale(*rgb, 1.0)

    # ------------------------------------------------------------------ per frame
    def update(self, dt: float, state: dict) -> None:
        self.t += dt
        # faint holographic flicker
        self.root.setAlphaScale(0.90 + 0.06 * math.sin(self.t * 11.0) + 0.04 * math.sin(self.t * 37.0))
        shield, hull, boost = state["shield"], state["hull"], state["boost"]
        self._set_bar("shield", shield, warn=shield < 0.25)
        self._set_text("shield_pct", f"{int(round(shield * 100))}%", warn=shield < 0.25)
        self._set_bar("hull", hull, warn=hull < 0.35)
        self._set_text("hull_pct", f"{int(round(hull * 100))}%", warn=hull < 0.35)
        self._set_bar("boost", boost, warn=False)
        self._set_text("boost_pct", "ON" if state.get("boosting") else f"{int(round(boost * 100))}%")
        self._set_text("speed", state["speed_text"])
        throttle = state["throttle"]
        self._set_bar("throttle", abs(throttle), warn=throttle < 0.0)
        self._set_text("throttle_pct", f"{int(round(throttle * 100))}%", warn=throttle < 0.0)
        self._set_text("mode", state["mode_text"], warn=state.get("mode_warn", False))
        self._set_text("systems", state.get("systems_text", ""))
        msg, msg_alpha = state.get("message", ""), float(state.get("message_alpha", 0.0))
        self._set_text("message", msg if msg_alpha > 0.01 else "", warn=state.get("message_warn", False), alpha=max(0.0, min(1.0, msg_alpha)))
        threat, threat_warn = state.get("threat", ""), bool(state.get("threat_warn", False))
        pulse = 0.65 + 0.35 * math.sin(self.t * 6.0) if threat_warn else 1.0
        self._set_text("threat", threat, warn=threat_warn, alpha=pulse)

    def destroy(self) -> None:
        if not self.root.isEmpty():
            self.root.removeNode()
