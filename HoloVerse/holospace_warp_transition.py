from __future__ import annotations

"""HoloSpace warp transition (Pass 282.82).

The old warp was a translucent, very bright swirl drawn over the frozen world, and HoloSpace was
built on the frame the warp ended, which froze the game for several seconds.

Now the warp is a full-screen overlay in three phases:

  cover   0.45 s  the view darkens to deep space while star streaks start; the world is hidden
                   before anything heavy happens
  switch           behind full cover the host enters HoloSpace (``covered`` turns True)
  reveal  ~1.5 s   the host is already running HoloSpace; the streaks slow and fade, and the
                   overlay clears to show the cockpit

Brightness is capped: thin streaks on a dark field, no white core, no flashes.
"""

import math
from panda3d.core import CardMaker, Shader, TransparencyAttrib

WARP_VERTEX = """
#version 150
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 v_uv;
void main() {
    v_uv = p3d_MultiTexCoord0;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
"""

WARP_FRAGMENT = """
#version 150
uniform float time_sec;
uniform float cover;      // 0 = clear, 1 = the view is fully hidden
uniform float streak;     // star streak strength 0..1
uniform float speed;      // streak travel speed
uniform float aspect;
in vec2 v_uv;
out vec4 fragColor;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

void main() {
    vec2 uv = v_uv * 2.0 - 1.0;
    uv.x *= aspect;
    float r = length(uv);
    float ang = atan(uv.y, uv.x) / 6.2831853 + 0.5;

    // deep-space field: almost black with a faint blue pull toward the centre
    vec3 col = vec3(0.004, 0.008, 0.020) + vec3(0.010, 0.026, 0.060) * (1.0 - smoothstep(0.0, 1.3, r));

    // radial star streaks (two layers of lanes so they don't line up)
    float lit = 0.0;
    vec3 tint = vec3(0.0);
    for (int layer = 0; layer < 2; layer++) {
        float lanes = layer == 0 ? 180.0 : 113.0;
        float a = ang * lanes + float(layer) * 0.37;
        float lane = floor(a);
        float f = fract(a);
        float h1 = hash(vec2(lane, 3.1 + float(layer)));
        float h2 = hash(vec2(lane, 9.7 + float(layer)));
        float on = step(0.45, h2);                                   // about half the lanes carry a star
        float head = fract(h1 + time_sec * speed * (0.35 + 0.9 * h2));
        float head_r = head * head * 1.9;                            // accelerates outward
        float len = 0.02 + 0.55 * streak * head;
        float d = head_r - r;
        float body = step(0.0, d) * (1.0 - smoothstep(0.0, len, d));
        float width = 1.0 - smoothstep(0.0, 0.28 + 0.12 * (1.0 - head), abs(f - 0.5));
        float s = on * body * width * smoothstep(0.04, 0.35, r);     // nothing in the very centre
        lit += s;
        tint += s * mix(vec3(0.55, 0.82, 1.0), vec3(0.72, 0.66, 1.0), h1);
    }
    col += tint * 0.55 * streak;                                     // capped: never near white

    float alpha = clamp(cover + lit * 0.5 * streak * (1.0 - cover), 0.0, 1.0);
    fragColor = vec4(min(col, vec3(0.62)), alpha);
}
"""

COVER_SECONDS = 0.45
REVEAL_SECONDS = 1.5


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


class HoloSpaceWarpTransition:
    """Full-screen warp overlay drawn on top of everything (render2d)."""

    def __init__(self, app, duration: float = 2.0) -> None:
        self.app = app
        self.duration = max(0.6, float(duration))
        self.elapsed = 0.0
        self.active = False
        self.phase = "idle"          # idle -> cover -> hold -> reveal -> idle
        self.covered = False
        self.root = None
        self.card = None
        self.shader = None
        self.reveal_elapsed = 0.0
        self.source = ""
        self._hold_frames = 0

    # ------------------------------------------------------------------ setup
    def build(self) -> None:
        if self.root is not None and not self.root.isEmpty():
            return
        cm = CardMaker("holospace-warp-card")
        cm.setFrame(-1.0, 1.0, -1.0, 1.0)
        cm.setUvRange((0.0, 0.0), (1.0, 1.0))
        self.root = self.app.render2d.attachNewNode("holospace-warp-overlay")
        self.root.setDepthWrite(False)
        self.root.setDepthTest(False)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.root.setBin("fixed", 1000)        # above the world, the cockpit and the HUD
        self.root.setLightOff(1)
        self.card = self.root.attachNewNode(cm.generate())
        try:
            self.shader = Shader.make(Shader.SL_GLSL, WARP_VERTEX, WARP_FRAGMENT)
            self.card.setShader(self.shader)
        except Exception:
            self.shader = None
        self.root.hide()

    def _aspect(self) -> float:
        try:
            return float(self.app.getAspectRatio())
        except Exception:
            return 16.0 / 9.0

    def _draw(self, cover: float, streak: float, speed: float) -> None:
        if self.card is None or self.card.isEmpty():
            return
        if self.shader is not None:
            try:
                self.card.setShaderInput("time_sec", float(self.elapsed))
                self.card.setShaderInput("cover", float(cover))
                self.card.setShaderInput("streak", float(streak))
                self.card.setShaderInput("speed", float(speed))
                self.card.setShaderInput("aspect", self._aspect())
                return
            except Exception:
                pass
        self.card.setColor(0.004, 0.008, 0.020, float(cover))     # no shaders: a plain dark fade

    # ------------------------------------------------------------------ control
    def start(self, *, duration: float | None = None, source: str = "") -> None:
        self.build()
        if duration is not None:
            self.duration = max(0.6, float(duration))
        self.elapsed = 0.0
        self.reveal_elapsed = 0.0
        self.active = True
        self.covered = False
        self.phase = "cover"
        self._hold_frames = 0
        self.source = str(source or "warp")
        if self.root is not None:
            self.root.show()
        self._draw(0.0, 0.2, 0.25)

    def update(self, dt: float) -> bool:
        """Advance the cover phase.  True once the screen is fully covered."""
        if not self.active:
            return False
        step = max(0.0, min(0.05, float(dt)))      # a long frame never makes the effect jump
        self.elapsed += step
        if self.phase == "cover":
            t = _smooth(self.elapsed / COVER_SECONDS)
            self._draw(t, 0.25 + 0.65 * t, 0.25 + 0.55 * t)
            if self.elapsed >= COVER_SECONDS:
                self.phase = "hold"
        if self.phase == "hold":
            self._draw(1.0, 0.9, 0.8)
            # one full frame of black on screen before the host does the heavy switch
            self._hold_frames += 1
            if self._hold_frames >= 2:
                self.covered = True
        return self.covered

    def begin_reveal(self) -> None:
        self.phase = "reveal"
        self.reveal_elapsed = 0.0

    def update_reveal(self, dt: float) -> bool:
        """Fade the overlay away over the live HoloSpace view.  True when finished."""
        if not self.active:
            return True
        step = max(0.0, min(0.05, float(dt)))
        self.elapsed += step
        self.reveal_elapsed += step
        t = _smooth(self.reveal_elapsed / REVEAL_SECONDS)
        cover = 1.0 - t
        self._draw(cover, 0.9 * (1.0 - t) ** 1.5, 0.8 - 0.6 * t)
        if self.reveal_elapsed >= REVEAL_SECONDS:
            self.stop()
            return True
        return False

    def stop(self) -> None:
        self.active = False
        self.phase = "idle"
        if self.root is not None and not self.root.isEmpty():
            self.root.hide()

    # Compatibility with older callers.
    def set_dimension_preset(self, index: int) -> bool:
        return True


# Compatibility alias for existing imports/callers.
HoloSpaceTravelSequence = HoloSpaceWarpTransition
