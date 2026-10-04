"""HoloSpace holographic cockpit HUD (Pass 282.76).

The flight readouts are projected inside the ship instead of drawn flat on the screen: three
glowing holo panels hang in the cockpit (camera space), tilted toward the pilot, drawn additive
over the canopy with a faint scan flicker.

  left panel     SHIELD / HULL / BOOST bars
  right panel    speed, throttle bar, flight mode
  canopy strip   system title, flight messages, defence-perimeter / hostile warnings

Colours come from the cockpit theme (``hud`` and ``hud_warn`` in assets/config/holospace_cockpit.json).
"""
from __future__ import annotations

import math

from panda3d.core import (
    ColorBlendAttrib,
    LineSegs,
    NodePath,
    TextNode,
    TransparencyAttrib,
)


def _additive(np_: NodePath) -> None:
    np_.setTransparency(TransparencyAttrib.MAlpha)
    np_.setDepthWrite(False)
    np_.setDepthTest(False)
    np_.setTwoSided(True)
    np_.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))


class HoloHUD:
    def __init__(self, camera: NodePath, mesh_cls, font=None, line_scale: float = 1.0):
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
        self._build()
        self.root.hide()

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

    def _build(self) -> None:
        # left: ship status
        left = self._panel("holo-left", (-0.56, 1.14, -0.335), (14.0, -10.0, 0.0), 0.25, 0.115)
        left.setScale(0.82)
        for i, key in enumerate(("shield", "hull", "boost")):
            z = 0.055 - i * 0.058
            self._text(left, f"{key}_label", (-0.225, -0.002, z - 0.008), 0.026, text=key.upper())
            self._bar(left, key, -0.115, z - 0.012, 0.25, 0.026)
            self._text(left, f"{key}_pct", (0.225, -0.002, z - 0.008), 0.024, TextNode.ARight)
        # right: flight
        right = self._panel("holo-right", (0.56, 1.14, -0.335), (-14.0, -10.0, 0.0), 0.25, 0.115)
        right.setScale(0.82)
        self._text(right, "speed", (0.0, -0.002, 0.040), 0.050, TextNode.ACenter)
        self._bar(right, "throttle", -0.20, -0.010, 0.40, 0.022)
        self._text(right, "throttle_pct", (0.225, -0.002, -0.006), 0.020, TextNode.ARight)
        self._text(right, "mode", (0.0, -0.002, -0.080), 0.022, TextNode.ACenter)
        # canopy strip: title, message, threat
        top = self._panel("holo-top", (0.0, 1.20, 0.43), (0.0, 8.0, 0.0), 0.42, 0.060)
        self._text(top, "title", (0.0, -0.002, 0.024), 0.020, TextNode.ACenter, "HOLOSPACE  //  DYSON PRIME SYSTEM")
        self._text(top, "message", (0.0, -0.002, -0.012), 0.026, TextNode.ACenter)
        self._text(top, "threat", (0.0, -0.002, -0.046), 0.019, TextNode.ACenter)

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
        msg, msg_alpha = state.get("message", ""), float(state.get("message_alpha", 0.0))
        self._set_text("message", msg if msg_alpha > 0.01 else "", warn=state.get("message_warn", False), alpha=max(0.0, min(1.0, msg_alpha)))
        threat, threat_warn = state.get("threat", ""), bool(state.get("threat_warn", False))
        pulse = 0.65 + 0.35 * math.sin(self.t * 6.0) if threat_warn else 1.0
        self._set_text("threat", threat, warn=threat_warn, alpha=pulse)

    def destroy(self) -> None:
        if not self.root.isEmpty():
            self.root.removeNode()
