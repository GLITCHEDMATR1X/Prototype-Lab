from __future__ import annotations

import math
from typing import Callable

from direct.filter.FilterManager import FilterManager
from panda3d.core import ClockObject, PNMImage, Shader, Texture, Vec2


VERT_SHADER = r'''#version 150
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 v_uv;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    v_uv = p3d_MultiTexCoord0;
}
'''

# This stage is the actual datamosh simulation.  Unlike Pass 03/04 it does not
# sample a single frozen screenshot.  It consumes the PREVIOUS PROCESSED FRAME,
# warps that history using camera motion and stable macroblock velocities, then
# writes the result into the opposite feedback target.  The two targets alternate
# every rendered frame, creating temporal propagation instead of a one-shot overlay.
FEEDBACK_FRAG_SHADER = r'''#version 150
uniform sampler2D scene_tex;
uniform sampler2D history_tex;
uniform float u_time;
uniform float u_event;
uniform float u_stability;
uniform vec2 u_resolution;
uniform vec2 u_scene_pad;
uniform vec2 u_history_pad;
uniform vec2 u_motion;
uniform float u_zoom_motion;
uniform float u_null_layer;
in vec2 v_uv;
out vec4 p3d_FragColor;

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

vec3 sample_scene(vec2 uv) {
    return texture(scene_tex, clamp(uv, vec2(0.001), vec2(0.999)) * u_scene_pad).rgb;
}

vec3 sample_history(vec2 uv) {
    return texture(history_tex, clamp(uv, vec2(0.001), vec2(0.999)) * u_history_pad).rgb;
}

void main() {
    vec2 uv = v_uv;
    if (u_null_layer > 0.5) {
        p3d_FragColor = vec4(sample_scene(uv), 1.0);
        return;
    }
    float stable = clamp(u_stability, 0.0, 1.0);

    // Macroblocks have stable, spatially coherent velocity disagreement.  Their
    // vectors do NOT reshuffle every frame; the previous frame is recursively
    // carried through the same local motion field, which is the important visual
    // distinction from the old random block-glitch transition.
    vec2 block_grid = vec2(48.0, 27.0);
    vec2 block = floor(uv * block_grid);
    vec2 local_vec = vec2(
        hash12(block + vec2(7.1, 19.3)) - 0.5,
        hash12(block + vec2(31.7, 5.9)) - 0.5
    );
    float block_hold = 0.58 + hash12(block + vec2(91.0, 13.0)) * 0.42;
    float block_release = hash12(block + vec2(53.0, 71.0));

    // Predictive motion is the authority. During an encounter Python freezes the
    // last meaningful pre-contact camera vector and feeds it here, so the old
    // frame keeps travelling with the motion it already had. A teleport itself
    // is explicitly ignored instead of becoming a synthetic radial explosion.
    vec2 inherited_motion = u_motion * (0.91 + local_vec * 0.16);
    inherited_motion += local_vec * (0.0015 + 0.0055 * u_event) * (1.0 - 0.45 * stable);

    vec2 centered = uv - vec2(0.5);
    float local_zoom = u_zoom_motion * (0.76 + 0.24 * block_hold);
    vec2 hist_uv = vec2(0.5) + centered * (1.0 + local_zoom) + inherited_motion;

    // Keep inherited imagery substantially recognizable. Datamosh should look
    // like prediction being reused on the wrong picture, not Gaussian motion blur.
    vec3 h0 = sample_history(hist_uv);
    vec3 h1 = sample_history(hist_uv + inherited_motion * 1.05 + centered * local_zoom * 0.12);
    vec3 h2 = sample_history(hist_uv + inherited_motion * 1.85 + centered * local_zoom * 0.22);
    vec3 history = h0 * 0.86 + h1 * 0.10 + h2 * 0.04;

    // Current-frame sampling stays mostly clean here.  Analogue presentation is
    // performed after temporal feedback so grain/scanlines do not accumulate into
    // an unreadable fog over many frames.
    vec3 current = sample_scene(uv);

    // Unstable dream space always has a faint temporal afterimage.  During a
    // Dreamer encounter the history becomes dominant.  Stabilized data performs
    // much stronger clean-frame replacement, giving safe rooms a real optical rule.
    float idle_history = mix(0.075, 0.012, stable);
    float event_history = mix(0.92, 0.58, stable) * clamp(u_event, 0.0, 1.0);
    float difference = length(current - history);
    float disagreement_hold = smoothstep(0.18, 0.92, difference) * u_event * 0.070;
    float retain = clamp((idle_history + event_history) * block_hold + disagreement_hold, 0.0, 0.985);

    // As the event recovers, macroblocks surrender at different deterministic
    // times. This lets recognizable pieces of the previous scene persist while
    // the destination paints through, instead of applying a generic glitch mask.
    float recovery = 1.0 - clamp(u_event, 0.0, 1.0);
    float release_gate = smoothstep(0.10 + block_release * 0.56, 0.27 + block_release * 0.56, recovery);
    retain *= 1.0 - release_gate * 0.88;
    vec3 temporal = mix(current, history, retain);

    // Motion edges get a small additional predictive drag. Keep this restrained:
    // recognizable inherited imagery is the effect, not random screen tearing.
    float edge_drag = smoothstep(0.16, 0.60, difference) * u_event * (1.0 - 0.40 * stable);
    temporal = mix(temporal, h2, edge_drag * 0.10);

    p3d_FragColor = vec4(clamp(temporal, 0.0, 1.0), 1.0);
}
'''

# This stage is deliberately presentational only.  It keeps the analogue-horror
# viewing language from Pass 03/04 while leaving temporal history to the feedback
# stage above.
PRESENT_FRAG_SHADER = r'''#version 150
uniform sampler2D display_tex;
uniform sampler2D depth_tex;
uniform float u_time;
uniform float u_event;
uniform float u_stability;
uniform vec2 u_resolution;
uniform vec2 u_display_pad;
uniform vec2 u_depth_pad;
uniform float u_near;
uniform float u_far;
uniform float u_focus_assist;
uniform float u_darkness;
uniform float u_null_layer;
in vec2 v_uv;
out vec4 p3d_FragColor;

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

vec3 sample_display(vec2 uv) {
    return texture(display_tex, clamp(uv, vec2(0.001), vec2(0.999)) * u_display_pad).rgb;
}

float linear_depth_m(vec2 uv) {
    float d = texture(depth_tex, clamp(uv, vec2(0.001), vec2(0.999)) * u_depth_pad).r;
    float z = d * 2.0 - 1.0;
    return (2.0 * u_near * u_far) / max(0.0001, (u_far + u_near - z * (u_far - u_near)));
}

void main() {
    vec2 uv = v_uv;
    if (u_null_layer > 0.5) {
        p3d_FragColor = vec4(sample_display(uv), 1.0);
        return;
    }
    float aspect = max(u_resolution.x / max(u_resolution.y, 1.0), 1.0);
    float stable = clamp(u_stability, 0.0, 1.0);
    float base_amount = mix(1.0, 0.42, stable);

    float slow_wobble = sin(uv.y * 31.0 + u_time * 0.83) * 0.00105 * base_amount;
    float tape_wave = sin(uv.y * 92.0 + u_time * 1.9) * 0.00030 * base_amount;

    // Sparse tracking slips remain coherent across a short interval rather than
    // turning the event into full-screen random static.
    float row = floor(uv.y * 120.0);
    float row_hash = hash12(vec2(row, floor(u_time * 3.0)));
    float tracking_gate = step(0.972, row_hash);
    float tracking = tracking_gate * (hash12(vec2(row, 19.7)) - 0.5) * 0.016 * base_amount;

    vec2 warped = uv;
    warped.x += slow_wobble + tape_wave + tracking;

    float chroma = 0.00085 * base_amount + 0.00075 * u_event;
    vec2 ca = vec2(chroma / aspect, 0.0);
    vec3 color;
    color.r = sample_display(warped + ca).r;
    color.g = sample_display(warped).g;
    color.b = sample_display(warped - ca).b;

    // Soft recorded-image quality without destroying navigational silhouettes.
    vec2 px = vec2(1.0 / max(u_resolution.x, 1.0), 1.0 / max(u_resolution.y, 1.0));
    vec3 soft = sample_display(warped + vec2(px.x * 1.6, 0.0));
    soft += sample_display(warped - vec2(px.x * 1.6, 0.0));
    soft += sample_display(warped + vec2(0.0, px.y * 1.20));
    soft += sample_display(warped - vec2(0.0, px.y * 1.20));
    soft *= 0.25;
    color = mix(color, soft, 0.115 * base_amount + 0.010 * u_event);

    // Andrew's baseline dream vision is near-sighted.  This uses real scene depth
    // rather than a radial screen blur: nearby geometry stays readable while
    // distant rooms lose high-frequency detail.  Stability calms corruption but
    // does not cure eyesight.  The hidden glasses nearly cancel the effect.
    float dist_m = linear_depth_m(uv);
    float drift = (sin(u_time * 0.29) * 0.72 + sin(u_time * 0.113 + 1.7) * 0.24) * (1.0 - stable);
    float blur_start = 3.6 + drift;
    float blur_end = 11.2 + drift * 1.25;
    float distance_blur = smoothstep(blur_start, blur_end, dist_m);
    distance_blur *= (1.0 - 0.96 * clamp(u_focus_assist, 0.0, 1.0));
    float radius_px = mix(0.0, 16.0, distance_blur);
    vec2 br = px * radius_px;
    vec3 dof = sample_display(warped) * 0.22;
    dof += sample_display(warped + vec2(br.x, 0.0)) * 0.12;
    dof += sample_display(warped - vec2(br.x, 0.0)) * 0.12;
    dof += sample_display(warped + vec2(0.0, br.y)) * 0.12;
    dof += sample_display(warped - vec2(0.0, br.y)) * 0.12;
    dof += sample_display(warped + br) * 0.075;
    dof += sample_display(warped - br) * 0.075;
    dof += sample_display(warped + vec2(br.x, -br.y)) * 0.075;
    dof += sample_display(warped + vec2(-br.x, br.y)) * 0.075;
    color = mix(color, dof, distance_blur * 0.94);

    // Room exposure is authored independently from fog.  This creates uneven
    // darkness while preserving doorway silhouettes and emissive landmarks.
    color *= mix(1.0, 0.56, clamp(u_darkness, 0.0, 1.0));

    float scan = sin((uv.y * u_resolution.y) * 1.70 + u_time * 3.1) * 0.5 + 0.5;
    float luma = dot(color, vec3(0.299, 0.587, 0.114));
    color = mix(color, vec3(luma) * vec3(1.02, 0.98, 1.05), 0.044 * base_amount);
    color *= mix(0.975, 1.018, scan * base_amount);

    float grain = hash12(gl_FragCoord.xy + floor(u_time * 24.0)) - 0.5;
    color += grain * (0.010 * base_amount + 0.003 * u_event);

    float dropout_y = fract(u_time * 0.071 + 0.173);
    float dropout = smoothstep(0.0055, 0.0, abs(uv.y - dropout_y)) * (0.048 * base_amount + 0.018 * u_event);
    color *= 1.0 - dropout;

    vec2 centered = uv * 2.0 - 1.0;
    centered.x *= aspect;
    float vignette = smoothstep(1.35, 0.43, length(centered));
    color *= mix(0.76, 1.0, vignette);

    // No event-only posterization here. The encounter must read from inherited
    // frames in the feedback stage, not from a generic compression overlay.

    p3d_FragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
}
'''


class NightmareVision:
    """Analogue nightmare presentation with true ping-pong temporal feedback."""

    def __init__(self, base, world, player):
        self.base = base
        self.world = world
        self.player = player
        self.available = False
        self.manager = None
        self.final_quad = None
        self.scene_tex = Texture("nightmare-scene")
        self.depth_tex = Texture("nightmare-depth")
        self.feedback_tex = [Texture("mosh-feedback-a"), Texture("mosh-feedback-b")]
        self.feedback_quad = []
        self.feedback_buffer = []
        self.feedback_index = 0
        self.feedback_frames = 0
        self.temporal_feedback = False

        self.event = 0.0
        self.event_elapsed = 0.0
        self.event_duration = 1.85
        self.teleport_time = 0.62
        self.teleported = False
        self._midpoint: Callable[[], None] | None = None
        self._complete: Callable[[], None] | None = None
        self._forced_debug = False
        self.focus_assist = 0.0
        self.null_layer = False

        self._last_heading = float(getattr(self.player, "heading", 0.0))
        self._last_pitch = float(getattr(self.player, "pitch", 0.0))
        p = self.player.root.getPos(self.base.render)
        self._last_pos = (float(p.x), float(p.y))
        self._screen_motion = Vec2(0.0, 0.0)
        self._zoom_motion = 0.0
        self._recent_motion = Vec2(0.0, 0.0)
        self._recent_zoom = 0.0
        self._event_motion = Vec2(0.0, 0.0)
        self._event_zoom = 0.0

        self._init_texture(self.scene_tex)
        for tex in self.feedback_tex:
            self._init_texture(tex)

        if self.base.win and self.base.cam:
            try:
                self.manager = FilterManager(self.base.win, self.base.cam)
                self.final_quad = self.manager.renderSceneInto(colortex=self.scene_tex, depthtex=self.depth_tex)
                if not self.final_quad:
                    raise RuntimeError("renderSceneInto returned no quad")

                feedback_shader = Shader.make(Shader.SL_GLSL, VERT_SHADER, FEEDBACK_FRAG_SHADER)
                for idx in range(2):
                    quad = self.manager.renderQuadInto(name=f"temporal-feedback-{idx}", colortex=self.feedback_tex[idx])
                    if not quad:
                        raise RuntimeError(f"renderQuadInto failed for feedback target {idx}")
                    buffer = self.manager.buffers[-1]
                    quad.setShader(feedback_shader)
                    quad.setShaderInput("scene_tex", self.scene_tex)
                    quad.setShaderInput("history_tex", self.feedback_tex[1 - idx])
                    quad.setShaderInput("u_time", 0.0)
                    quad.setShaderInput("u_event", 0.0)
                    quad.setShaderInput("u_stability", 0.0)
                    quad.setShaderInput("u_resolution", Vec2(1920.0, 1080.0))
                    quad.setShaderInput("u_scene_pad", Vec2(1.0, 1.0))
                    quad.setShaderInput("u_history_pad", Vec2(1.0, 1.0))
                    quad.setShaderInput("u_motion", Vec2(0.0, 0.0))
                    quad.setShaderInput("u_zoom_motion", 0.0)
                    quad.setShaderInput("u_null_layer", 0.0)
                    buffer.setActive(False)
                    self.feedback_quad.append(quad)
                    self.feedback_buffer.append(buffer)

                present_shader = Shader.make(Shader.SL_GLSL, VERT_SHADER, PRESENT_FRAG_SHADER)
                self.final_quad.setShader(present_shader)
                self.final_quad.setShaderInput("display_tex", self.feedback_tex[0])
                self.final_quad.setShaderInput("depth_tex", self.depth_tex)
                self.final_quad.setShaderInput("u_time", 0.0)
                self.final_quad.setShaderInput("u_event", 0.0)
                self.final_quad.setShaderInput("u_stability", 0.0)
                self.final_quad.setShaderInput("u_resolution", Vec2(1920.0, 1080.0))
                self.final_quad.setShaderInput("u_display_pad", Vec2(1.0, 1.0))
                self.final_quad.setShaderInput("u_depth_pad", Vec2(1.0, 1.0))
                self.final_quad.setShaderInput("u_near", 0.05)
                self.final_quad.setShaderInput("u_far", 75.0)
                self.final_quad.setShaderInput("u_focus_assist", 0.0)
                self.final_quad.setShaderInput("u_darkness", 0.0)
                self.final_quad.setShaderInput("u_null_layer", 0.0)

                self.available = True
                self.temporal_feedback = True
            except Exception as exc:
                print(f"NIGHTMARE_VISION_DISABLED={exc!r}")
                if self.manager:
                    try:
                        self.manager.cleanup()
                    except Exception:
                        pass
                self.manager = None
                self.final_quad = None
                self.feedback_quad = []
                self.feedback_buffer = []

        self.base.taskMgr.add(self._update, "nightmare-vision", sort=45)

    @staticmethod
    def _init_texture(tex: Texture):
        tex.setWrapU(Texture.WMClamp)
        tex.setWrapV(Texture.WMClamp)
        tex.setMinfilter(Texture.FTLinear)
        tex.setMagfilter(Texture.FTLinear)
        img = PNMImage(4, 4, 4)
        img.fill(0.0, 0.0, 0.0)
        img.alphaFill(1.0)
        tex.load(img)

    @property
    def active(self) -> bool:
        return self.event_elapsed > 0.0 and self.event_elapsed < self.event_duration

    def _current_stability(self) -> float:
        pos = self.player.root.getPos(self.base.render)
        return self.world.stability_at(pos.x, pos.y)

    @staticmethod
    def _angle_delta(current: float, previous: float) -> float:
        return (current - previous + 180.0) % 360.0 - 180.0

    def _measure_camera_motion(self):
        heading = float(getattr(self.player, "heading", self.player.root.getH()))
        pitch = float(getattr(self.player, "pitch", self.base.camera.getP()))
        pos = self.player.root.getPos(self.base.render)
        x, y = float(pos.x), float(pos.y)

        dh = self._angle_delta(heading, self._last_heading)
        dp = pitch - self._last_pitch
        dx = x - self._last_pos[0]
        dy = y - self._last_pos[1]

        # Resolve translation into the player's local right/forward axes.  It is
        # only an approximate screen flow; the recursive feedback is the actual
        # temporal mechanism and does not depend on perfect optical flow.
        rad = math.radians(heading)
        right_x, right_y = math.cos(rad), -math.sin(rad)
        fwd_x, fwd_y = math.sin(rad), math.cos(rad)
        strafe = dx * right_x + dy * right_y
        forward = dx * fwd_x + dy * fwd_y
        travel = math.hypot(dx, dy)

        # A DreamCatcher relocation is not camera motion. If the player position
        # jumps several metres in one frame, reset the tracker so the teleport
        # cannot create the old fake radial-zoom explosion.
        if travel > 1.45 or abs(dh) > 70.0:
            self._last_heading = heading
            self._last_pitch = pitch
            self._last_pos = (x, y)
            return

        mx = max(-0.055, min(0.055, dh * 0.00110 + strafe * 0.0042))
        my = max(-0.042, min(0.042, -dp * 0.00095 - forward * 0.0015))
        zoom = max(0.0, min(0.032, travel * 0.0048))

        self._screen_motion = Vec2(
            self._screen_motion.x * 0.48 + mx * 0.52,
            self._screen_motion.y * 0.48 + my * 0.52,
        )
        self._zoom_motion = self._zoom_motion * 0.46 + zoom * 0.54

        # Hold onto the last meaningful pre-contact vector for a short time.
        # Datamoshing then continues that prediction after the scene changes.
        if abs(self._screen_motion.x) + abs(self._screen_motion.y) > 0.00045:
            self._recent_motion = Vec2(self._screen_motion)
        else:
            self._recent_motion = Vec2(self._recent_motion.x * 0.985, self._recent_motion.y * 0.985)
        if self._zoom_motion > 0.00010:
            self._recent_zoom = self._zoom_motion
        else:
            self._recent_zoom *= 0.985

        self._last_heading = heading
        self._last_pitch = pitch
        self._last_pos = (x, y)

    def capture_memory(self) -> bool:
        """Compatibility hook: temporal history is now continuous, not a snapshot.

        Returning True tells old QA callers that history is available.  No GPU→CPU
        readback occurs; the previous processed frame already lives in the inactive
        feedback target.
        """
        return bool(self.available and self.temporal_feedback and self.feedback_frames > 0)

    def set_focus_assist(self, value: float):
        self.focus_assist = max(0.0, min(1.0, float(value)))

    def set_null_layer(self, enabled: bool):
        self.null_layer = bool(enabled)
        if self.null_layer:
            self.event_elapsed = 0.0
            self.event = 0.0
            self._forced_debug = False
            self.focus_assist = 1.0

    def trigger_datamosh(self, midpoint: Callable[[], None], complete: Callable[[], None] | None = None) -> bool:
        if self.active:
            return False
        self.event_elapsed = 0.0001
        self.event = 0.0
        self.teleported = False
        self._midpoint = midpoint
        self._complete = complete
        self._forced_debug = False
        self._event_motion = Vec2(self._recent_motion)
        self._event_zoom = float(self._recent_zoom)
        return True

    def force_debug_mosh(self, event: float = 0.94):
        self.event_elapsed = self.teleport_time + 0.20
        self.event = float(event)
        self.teleported = True
        self._forced_debug = True
        self._event_motion = Vec2(-0.0105, 0.0018)
        self._event_zoom = 0.0015

    def _texture_pad(self, tex: Texture, w: float, h: float) -> Vec2:
        tw = float(tex.getXSize()) if tex.getXSize() > 0 else w
        th = float(tex.getYSize()) if tex.getYSize() > 0 else h
        return Vec2(min(1.0, w / max(tw, 1.0)), min(1.0, h / max(th, 1.0)))

    def _activate_feedback_target(self, time_s: float):
        if not self.available or not self.feedback_buffer or not self.final_quad:
            return
        self._measure_camera_motion()

        win = self.base.win
        w = float(win.getXSize()) if win and win.getXSize() > 0 else 1920.0
        h = float(win.getYSize()) if win and win.getYSize() > 0 else 1080.0
        stable = float(self._current_stability())
        pos = self.player.root.getPos(self.base.render)
        darkness = float(self.world.darkness_at(pos.x, pos.y))

        write_idx = self.feedback_index
        read_idx = 1 - write_idx
        for i, buf in enumerate(self.feedback_buffer):
            buf.setActive(i == write_idx)

        quad = self.feedback_quad[write_idx]
        quad.setShaderInput("history_tex", self.feedback_tex[read_idx])
        quad.setShaderInput("u_time", float(time_s))
        quad.setShaderInput("u_event", float(self.event))
        quad.setShaderInput("u_stability", stable)
        quad.setShaderInput("u_resolution", Vec2(w, h))
        quad.setShaderInput("u_scene_pad", self._texture_pad(self.scene_tex, w, h))
        quad.setShaderInput("u_history_pad", self._texture_pad(self.feedback_tex[read_idx], w, h))
        predictive_motion = self._event_motion if (self.active or self.event > 0.0 or self._forced_debug) else self._screen_motion
        predictive_zoom = self._event_zoom if (self.active or self.event > 0.0 or self._forced_debug) else self._zoom_motion
        quad.setShaderInput("u_motion", predictive_motion)
        quad.setShaderInput("u_zoom_motion", float(predictive_zoom))
        quad.setShaderInput("u_null_layer", 1.0 if self.null_layer else 0.0)

        self.final_quad.setShaderInput("display_tex", self.feedback_tex[write_idx])
        self.final_quad.setShaderInput("u_time", float(time_s))
        self.final_quad.setShaderInput("u_event", float(self.event))
        self.final_quad.setShaderInput("u_stability", stable)
        self.final_quad.setShaderInput("u_resolution", Vec2(w, h))
        self.final_quad.setShaderInput("u_display_pad", self._texture_pad(self.feedback_tex[write_idx], w, h))
        self.final_quad.setShaderInput("depth_tex", self.depth_tex)
        self.final_quad.setShaderInput("u_depth_pad", self._texture_pad(self.depth_tex, w, h))
        self.final_quad.setShaderInput("u_near", float(self.base.camLens.getNear()))
        self.final_quad.setShaderInput("u_far", float(self.base.camLens.getFar()))
        self.final_quad.setShaderInput("u_focus_assist", float(self.focus_assist))
        self.final_quad.setShaderInput("u_darkness", darkness)
        self.final_quad.setShaderInput("u_null_layer", 1.0 if self.null_layer else 0.0)

        self.feedback_index = read_idx
        self.feedback_frames += 1

    def _update_event(self, dt: float):
        if self._forced_debug or not self.active:
            return
        self.event_elapsed += dt
        t = self.event_elapsed
        if t < self.teleport_time:
            phase = min(1.0, t / self.teleport_time)
            # Before the instance switch, the picture only begins to lose lock.
            # The severe prediction failure starts when the new scene arrives.
            self.event = 0.34 * math.sin(phase * math.pi * 0.5)
        else:
            if not self.teleported:
                self.teleported = True
                self.event = 1.0
                if self._midpoint:
                    self._midpoint()
            decay = min(1.0, (t - self.teleport_time) / max(0.001, self.event_duration - self.teleport_time))
            # Keep history strong immediately after relocation, then allow the new
            # room to repaint the screen progressively rather than cutting cleanly.
            self.event = max(0.0, 1.0 - decay * 0.96)

        if self.event_elapsed >= self.event_duration:
            self.event_elapsed = 0.0
            self.event = 0.0
            cb = self._complete
            self._midpoint = None
            self._complete = None
            if cb:
                cb()

    def _update(self, task):
        dt = min(ClockObject.getGlobalClock().getDt(), 0.05)
        self._update_event(dt)
        qa_fixed = bool(getattr(getattr(self.base, "args", None), "qa_shot", None))
        time_s = 3.25 + self.feedback_frames / 60.0 if qa_fixed else ClockObject.getGlobalClock().getFrameTime()
        self._activate_feedback_target(time_s)
        return task.cont
