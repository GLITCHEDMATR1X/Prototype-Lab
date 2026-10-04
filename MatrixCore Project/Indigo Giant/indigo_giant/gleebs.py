"""Pass 61 - the end: Gleebs comes for Nyx and Orbit.

When Crimson has eaten the pale branch and lain down for good, the sky answers:

ARRIVING  A beam of light falls out of the empty sky a little way ahead of you, and Gleebs
          forms in it as a hologram - tall as the sky, cyan, flickering, with scanlines that
          crawl up through it. It speaks (subtitled): it heard Nyx and Orbit; no one comes to
          REDACTED any more; the world is dying; it can take them both; Crimson stays.
WAITING   Gleebs waits in its beam for as long as you like (it is saved). Step into the light:
            - with Nyx beside you (within 30 m of the beam): hold E - "leave REDACTED with Gleebs"
            - alone: Gleebs will not take one who is alone - bring Nyx
LEAVING   A short scene (no control): Nyx and Orbit rise up the beam and are gone. Then a last
          look at Crimson, lying where it fell, left behind on REDACTED as the beam goes out.
GONE      The ending card: "they left REDACTED". A new journey, or quit. (Loading a journey that
          has ended shows the card again.)

The hologram is the Utopia Vision Gleebs model (assets/gleebs/Gleebs_Game.bam, a Panda3D
Actor with Idle / Walk). It is drawn without the sketch shader (plain additive, so it skins on
the CPU like any Actor loaded from BAM), which is also what makes it read as light.
"""
from __future__ import annotations

import math
import random

from panda3d.core import (ColorBlendAttrib, DepthTestAttrib, Filename, Geom, GeomNode, GeomTriangles, GeomVertexData,
                          GeomVertexFormat, GeomVertexWriter, Mat4, NodePath, PNMImage, Point3, TexGenAttrib,
                          Texture, TextureStage, TransformState, TransparencyAttrib, Vec3, Vec4)

from . import desert
from . import sky
from .survival import K, _flat_dist
from . import paths                 # Pass 62: where the game files are

GLEEBS_BAM = paths.GLEEBS_BAM
MODEL_HEIGHT = 1.97                    # Gleebs_Game.bam at scale 1
HOLO_OVER_NYX = 1.30                   # the hologram stands this x Nyx's height
HOLO_COLOUR = (0.42, 0.93, 1.00)       # cyan light (night)
HOLO_DAY_COLOUR = (0.08, 0.72, 1.00)   # deeper by day, so it holds against the pale sky
SCAN_METRES = 0.9                      # height of one scanline on the hologram
ARRIVE_AHEAD = 58.0                    # metres ahead of you (where the camera looks) it comes down
BEAM_TOP = 420.0                       # the beam falls from this high
BEAM_RADIUS = 7.0
LIGHT_RADIUS = 9.0                     # stand this close to the beam's middle to be "in the light"
NYX_NEAR = 30.0                        # Nyx must be this close to the beam to leave together
LEAVE_HOLD = 2.0                       # hold E
ALONE_HOLD = 0.3
LIGHT_REACH = 46.0                     # its light on the sand, on Nyx and on you
LIGHT = 0.85

BEAM_DROP = 2.5                        # seconds for the beam to reach the sand
FORM = (2.5, 6.0)                      # the hologram flickers into being
LINES = (                              # (at seconds, words, spoken by Gleebs)
    (0.3, 'The sky opens. A beam of light falls into the sand.', False),
    (4.2, 'A figure made of light stands in the beam, taller than Nyx: long ears, thin bright lines.', False),
    (9.6, '"Nyx. Orbit. I heard you, at last."', True),
    (15.2, '"No one comes to REDACTED any more. They scratched its name from every chart, so no one would look."', True),
    (22.4, '"This world is dying. I can carry you both away from it."', True),
    (28.4, '"Crimson ate what was bitter, because it was there. It was strong, but never wise. It stays with REDACTED."', True),
    (35.8, '"Step into my light together, when you are ready. I will wait."', True),
)
ARRIVE_END = 41.5
LINE_TIME = 6.2

RISE_TIME = 9.0                        # the leaving scene: rising up the beam
RISE_HEIGHT = 70.0
CRIMSON_SHOT = (9.0, 16.5)             # then a last look at Crimson
BEAM_OUT = (12.5, 15.0)                # the beam goes out
LEAVE_END = 16.5
desert.HOLD_TIMES.setdefault('leave', LEAVE_HOLD)
desert.HOLD_TIMES.setdefault('alone', ALONE_HOLD)


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _scan_texture() -> Texture:
    """Horizontal scanlines: solid bands with a soft see-through gap (in the alpha)."""
    img = PNMImage(4, 64, 2)
    for y in range(64):
        v = 0.55 + 0.45 * math.cos(2.0 * math.pi * y / 64.0)
        v = 0.30 + 0.70 * v ** 3
        for x in range(4):
            img.setGray(x, y, 1.0)
            img.setAlpha(x, y, v)
    tex = Texture('gleebs_scan')
    tex.load(img)
    tex.setWrapV(Texture.WMRepeat)
    tex.setWrapU(Texture.WMClamp)
    tex.setMagfilter(Texture.FTLinear)
    tex.setMinfilter(Texture.FTLinearMipmapLinear)      # far away the lines blend instead of shimmering
    return tex


def _world_scan(np_: NodePath, tex: Texture, metres_per_line: float, sort: int = 20) -> TextureStage:
    """Scanlines fixed in the world (v = height / metres_per_line), whatever the model's UVs."""
    ts = TextureStage('gleebs_scan')
    np_.setTexture(ts, tex, sort)
    np_.setTexGen(ts, TexGenAttrib.MWorldPosition, sort)
    _scroll_scan(np_, ts, metres_per_line, 0.0)
    return ts


def _scroll_scan(np_: NodePath, ts: TextureStage, metres_per_line: float, offset: float):
    k = 1.0 / metres_per_line
    # row vectors: (x, y, z, 1) * M  ->  u = 0.5, v = z * k + offset
    m = Mat4(0, 0, 0, 0,
             0, 0, 0, 0,
             0, k, 0, 0,
             0.5, offset, 0, 1)
    np_.setTexTransform(ts, TransformState.makeMat(m))


def _light_look(np_: NodePath, sort: int = 20, bin_sort: int = 32, solid: bool = False):
    """Drawn as light, without the sketch shader. Plain alpha blending (not additive) so it still
    reads as cyan against a bright noon sky. solid: writes depth and hides its own far side."""
    np_.setShaderOff(sort)
    np_.setLightOff(sort)
    np_.setTransparency(TransparencyAttrib.MAlpha, sort)
    np_.setDepthWrite(solid, sort)
    np_.setTwoSided(not solid, sort)
    np_.setBin('fixed', bin_sort, sort)
    np_.hide(K['SHADOW_CAMERA_MASK'])


def _beam_geom(radius0: float, radius1: float, sides: int = 28) -> NodePath:
    """An open cylinder from z=-1 (the sand) to z=0 (the sky), bright at the foot, fading up."""
    vdata = GeomVertexData('gleebs_beam', GeomVertexFormat.getV3c4(), Geom.UHStatic)
    vw, cw = GeomVertexWriter(vdata, 'vertex'), GeomVertexWriter(vdata, 'color')
    rows = ((-1.0, radius0, 1.0), (-0.92, radius0 * 1.02, 0.75), (-0.6, (radius0 + radius1) * 0.5, 0.35),
            (0.0, radius1, 0.0))
    for z, r, a in rows:
        for i in range(sides + 1):
            t = 2.0 * math.pi * i / sides
            vw.addData3(math.cos(t) * r, math.sin(t) * r, z)
            cw.addData4(1.0, 1.0, 1.0, a)
    tris = GeomTriangles(Geom.UHStatic)
    n = sides + 1
    for ring in range(len(rows) - 1):
        for i in range(sides):
            a, b = ring * n + i, ring * n + i + 1
            c, d = a + n, b + n
            tris.addVertices(a, b, d)
            tris.addVertices(a, d, c)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode('gleebs_beam')
    gn.addGeom(geom)
    return NodePath(gn)


class GleebsMixin:
    # ------------------------------------------------------------ state
    def _init_gleebs(self):
        self.gleebs_state = None               # None, 'arriving', 'waiting', 'leaving', 'gone'
        self.gleebs_t = 0.0
        self.gleebs_pos = None
        self.gleebs_heading = 0.0
        self._gleebs_arrive_in = None          # a journey saved with Crimson dead before Pass 61
        self._gleebs_line = 0
        self._gleebs_rng = random.Random(61)
        self._gleebs_glitch = 0.0
        self._gleebs_leave = None              # the leaving scene's starting points
        self._gleebs_hud_hidden = []
        self.gleebs_root = None
        self.gleebs_actor = None

    def _build_gleebs(self):
        """Made the first time Gleebs comes (so a journey that never ends never loads the model)."""
        if self.gleebs_root is not None:
            return
        root = self.render.attachNewNode('gleebs')
        scan = _scan_texture()
        # the beam: a wide soft column and a bright core
        beam = root.attachNewNode('beam')
        for r0, r1, a, name in ((BEAM_RADIUS * 1.5, BEAM_RADIUS * 2.2, 0.13, 'outer'), (2.4, 3.2, 0.20, 'core')):
            b = _beam_geom(r0, r1)
            b.setName(name)
            b.reparentTo(beam)
            _light_look(b)
            b.setColor(*HOLO_COLOUR, a)
            b.setTag('alpha', str(a))
        self._gleebs_beam_scan = _world_scan(beam, scan, 1.6)
        # a pool of light on the sand
        from .glow import _aura_card, _aura_texture
        pool = _aura_card(root, _aura_texture(), LIGHT_RADIUS * 2.8)
        pool.clearBillboard()                  # lie flat on the sand
        pool.setP(-90.0)
        pool.setZ(0.25)
        pool.setColor(*HOLO_COLOUR, 0.0)
        pool.show()
        # Gleebs itself
        holo = root.attachNewNode('hologram')
        # two layers share one animated model (an instance, so it is skinned once):
        #   body - plain alpha blending, so Gleebs reads as cyan even against a bright noon sky
        #   glow - additive light over it, strong at night
        body = holo.attachNewNode('body')
        _light_look(body, 25, 31, solid=True)                # drawn before the beam round it
        glow_layer = holo.attachNewNode('glow')
        _light_look(glow_layer, 25, 33)
        glow_layer.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha,
                                                   ColorBlendAttrib.OOne), 25)
        glow_layer.setAttrib(DepthTestAttrib.make(DepthTestAttrib.MLessEqual), 25)   # lies exactly on the body
        actor = None
        try:
            from direct.actor.Actor import Actor
            if GLEEBS_BAM.is_file():
                actor = Actor(Filename.fromOsSpecific(str(GLEEBS_BAM)))
                actor.reparentTo(body)
                actor.setScale(HOLO_OVER_NYX * self.giant_height / MODEL_HEIGHT)
                actor.setH(180.0)              # authored facing -Y
                actor.loop('Idle')
                actor.setShaderOff(20)         # an Actor from a BAM skins on the CPU without the shader
                actor.setLightOff(20)
                actor.setTextureOff(20)        # its own textures give way to the scanlines
                actor.setColor(1.0, 1.0, 1.0, 1.0, 20)
                self._gleebs_scan = _world_scan(actor, scan, SCAN_METRES, 26)
                actor.instanceTo(glow_layer)
        except Exception as exc:               # a missing or broken model: the beam still comes
            print(f'[gleebs] could not load the hologram model: {exc}')
            actor = None
        self.gleebs_body, self.gleebs_glow = body, glow_layer
        halo = _aura_card(holo, _aura_texture(), self.giant_height * HOLO_OVER_NYX * 1.25)
        halo.setZ(self.giant_height * HOLO_OVER_NYX * 0.55)        # a soft glow round it (most at night)
        halo.show()
        self.gleebs_halo = halo
        self.gleebs_actor = actor
        self.gleebs_holo, self.gleebs_beam, self.gleebs_pool = holo, beam, pool
        self.gleebs_root = root
        root.hide()

    # ------------------------------------------------------------ the end begins
    def show_ending(self):
        """Pass 61: Crimson is gone - instead of the old card, Gleebs comes."""
        self.ending_shown = True
        if self.gleebs_state is None:
            self.begin_gleebs()
        if hasattr(self, 'save_game'):
            self.save_game('gleebs')

    def begin_gleebs(self, pos: Point3 | None = None, heading: float | None = None, state: str = 'arriving'):
        self._build_gleebs()
        if pos is None:
            pos, heading = self._gleebs_spot()
        self.gleebs_pos = Point3(pos.x, pos.y, self.field.height(pos.x, pos.y))
        self.gleebs_heading = heading if heading is not None else 0.0
        self.gleebs_state = state
        self.gleebs_t = 0.0 if state == 'arriving' else ARRIVE_END
        self._gleebs_line = 0 if state == 'arriving' else len(LINES)
        self._gleebs_arrive_in = None
        self.gleebs_root.setPos(self.gleebs_pos)
        self.gleebs_holo.setH(self.gleebs_heading)
        self.gleebs_root.show()
        self.red_giant.setShaderInput('glow_receive', Vec3(1.0, 1.0, 1.0))    # its light falls on Crimson too
        if state == 'arriving':
            self.stats['gleebs'] = 1
            self.sfx('gleebs_arrive')
            line = 'A beam of light fell out of the sky, and Gleebs stood in it.'
            if line not in self.lore_log:
                self.lore_log.append(line)
        self._update_gleebs_visuals(0.0)

    def _gleebs_spot(self):
        """Ahead of you (where you are looking), on clear, open sand; Gleebs faces you."""
        hp = self.human.getPos(self.render)
        base = self.heading
        for k in range(24):
            off = (k + 1) // 2 * 20.0 * (1 if k % 2 else -1)
            dist = ARRIVE_AHEAD * (1.0 + 0.15 * (k // 6))
            h = math.radians(base + off)
            x, y = hp.x + math.sin(h) * dist, hp.y + math.cos(h) * dist
            if self._gleebs_spot_ok(x, y):
                break
        face = K['heading_toward'](hp.x - x, hp.y - y)
        return Point3(x, y, 0.0), face

    def _gleebs_spot_ok(self, x: float, y: float) -> bool:
        p = Point3(x, y, 0.0)
        if hasattr(self.field, 'is_clear') and not self.field.is_clear(x, y):
            return False
        if any(_flat_dist(s.pos, p) < LIGHT_RADIUS + 6.0 for s in self.shells.shells.values()):
            return False
        pf = getattr(self, 'places', None)
        if pf is not None:
            layout = pf.layout
            if next(iter(layout.places_within(x, y, 35.0)), None) is not None:
                return False
            d0 = math.hypot(x - layout.start.x, y - layout.start.y)
            if any(math.hypot(x - tx, y - ty) < 35.0 for tx, ty in layout._trail_sites(d0)):
                return False
        return True

    # ------------------------------------------------------------ in the light
    def in_gleebs_light(self, p: Point3, radius: float = LIGHT_RADIUS) -> bool:
        return self.gleebs_state == 'waiting' and _flat_dist(p, self.gleebs_pos) <= radius

    def nyx_can_leave(self) -> bool:
        return (self.giant_alive and not getattr(self, 'giant_knocked_out', False)
                and self.in_gleebs_light(self.giant.getPos(self.render), NYX_NEAR))

    def _e_target(self):
        kind, target = super()._e_target()
        if (kind is None and self.gleebs_state == 'waiting' and self.controlled_name == 'human' and self.human_alive
                and self.hidden_shell is None and self.in_gleebs_light(self.human.getPos(self.render))):
            # riding on Nyx's shoulder into the light counts as together
            return ('leave' if self.nyx_can_leave() else 'alone'), None
        return kind, target

    def place_prompt(self, kind, target) -> str:
        if kind == 'leave':
            return 'leave REDACTED with Gleebs'
        if kind == 'alone':
            return 'step into the light'
        return super().place_prompt(kind, target)

    def _complete_e(self, kind, target):
        if kind == 'alone':
            self.sfx('gleebs_voice')
            self.say('GLEEBS:  "Not alone. Bring Nyx into the light with you."', 4.5)
            return None
        if kind == 'leave':
            if self.gleebs_state == 'waiting' and self.nyx_can_leave():
                self.begin_leaving()
            return None
        return super()._complete_e(kind, target)

    # ------------------------------------------------------------ leaving
    def begin_leaving(self):
        hp, gp = self.human.getPos(self.render), self.giant.getPos(self.render)
        self._gleebs_leave = {'human': Point3(hp), 'giant': Point3(gp), 'cam': Point3(self.camera.getPos(self.render))}
        self.gleebs_state = 'leaving'
        self.gleebs_t = 0.0
        self.stats['left_redacted'] = 1
        self.lore_log.append('Nyx and Orbit went up into the light with Gleebs.')
        self.sfx('gleebs_depart')
        self.say('Nyx and Orbit step into the light together.', 4.0)
        self.comp.update({'mode': 'stay', 'moving': False})
        self.keys['e'] = False
        self._hide_hud_for_scene(True)

    def _hide_hud_for_scene(self, hide: bool):
        if hide:
            keep = {self.lore_text}
            self._gleebs_hud_hidden = []
            for parent in (self.a2dBottomLeft, self.a2dBottomRight, self.a2dTopRight, self.aspect2d):
                for child in parent.getChildren():
                    if child in keep or child.isHidden() or child.getName().startswith('a2d'):
                        continue
                    if getattr(self, 'panel', None) is not None and child == self.panel:
                        continue
                    child.hide()
                    self._gleebs_hud_hidden.append(child)
        else:
            for child in self._gleebs_hud_hidden:
                if not child.isEmpty():
                    child.show()
            self._gleebs_hud_hidden = []

    def _update_leaving(self, dt: float):
        t = self.gleebs_t
        L = self._gleebs_leave
        c = self.gleebs_pos
        rise = _smooth(t / RISE_TIME)
        for node, start, height, actor in ((self.human, L['human'], self.human_height, self.human_actor),
                                           (self.giant, L['giant'], self.giant_height, self.giant_actor)):
            if t >= RISE_TIME:
                node.hide()
                continue
            pull = _smooth(t / (RISE_TIME * 0.7)) * 0.65            # drawn in toward the middle of the beam
            x = start.x + (c.x - start.x) * pull
            y = start.y + (c.y - start.y) * pull
            node.setPos(x, y, start.z + rise * RISE_HEIGHT * (1.0 if node is self.human else 0.9))
            clip = 'Idle_Loop'
            dur = actor.clips[clip]['duration'] if clip in actor.clips else 1.0
            actor.apply_clip(clip, (t * 0.6) % dur, loop=True)
        if t >= RISE_TIME and self._gleebs_line >= 0:
            self._gleebs_line = -1
            self.say('Crimson stays behind, lying where it fell. It was strong, but it was never wise enough '
                     'to follow.', 7.0)
        if t >= LEAVE_END:
            self.finish_gleebs()

    def finish_gleebs(self):
        self.gleebs_state = 'gone'
        self.gleebs_root.hide()
        self.human.hide()
        self.giant.hide()
        self._hide_hud_for_scene(True)
        if hasattr(self, 'save_game'):
            self.save_game('left REDACTED')
        if hasattr(self, 'toggle_panel') and getattr(self, 'panel_name', None) != 'ending':
            self.toggle_panel('ending')

    # ------------------------------------------------------------ the camera in the leaving scene
    def place_scene_camera(self) -> bool:
        """Called from _place_camera while the leaving scene plays (world_frozen() is True then too)."""
        if self.gleebs_state != 'leaving' or self._gleebs_leave is None:
            return False
        t = self.gleebs_t
        c = self.gleebs_pos
        if t < CRIMSON_SHOT[0]:
            start = self._gleebs_leave['cam']
            away = Vec3(start.x - c.x, start.y - c.y, 0.0)
            if away.length() < 1.0:
                away = Vec3(0, -1, 0)
            away.normalize()
            dist = 46.0 + 10.0 * _smooth(t / RISE_TIME)
            pos = Point3(c.x + away.x * dist, c.y + away.y * dist, 0.0)
            pos.z = self.field.height(pos.x, pos.y) + 5.0
            look = Point3(c.x, c.y, c.z + 8.0 + _smooth(t / RISE_TIME) * RISE_HEIGHT * 0.75)
        else:
            rp = self.red_giant.getPos(self.render)
            toward = Vec3(c.x - rp.x, c.y - rp.y, 0.0)
            if toward.length() < 1.0:
                toward = Vec3(1, 0, 0)
            toward.normalize()
            side = Vec3(-toward.y, toward.x, 0.0)
            k = _smooth((t - CRIMSON_SHOT[0]) / (CRIMSON_SHOT[1] - CRIMSON_SHOT[0]))
            pos = rp - toward * (26.0 + 8.0 * k) + side * 9.0
            pos.z = self.field.height(pos.x, pos.y) + 6.0 + 4.0 * k
            look = Point3(rp.x, rp.y, rp.z + 3.0 + 12.0 * k)
        self.camera.setPos(pos)
        self.camera.lookAt(look)
        self._sync_sun_shader()
        return True

    # ------------------------------------------------------------ per frame
    def survival_step(self, dt: float):
        super().survival_step(dt)
        if self._gleebs_arrive_in is not None and not self.world_frozen():
            self._gleebs_arrive_in -= dt
            if self._gleebs_arrive_in <= 0.0:
                self.begin_gleebs()
        state = self.gleebs_state
        if state is None:
            return
        if state == 'gone':
            if getattr(self, 'panel_name', None) is None and hasattr(self, 'toggle_panel'):
                self.toggle_panel('ending')     # the journey is over (also after loading it)
            return
        if getattr(self, 'paused', False):
            return
        self.gleebs_t += dt
        if state == 'arriving':
            while self._gleebs_line < len(LINES) and self.gleebs_t >= LINES[self._gleebs_line][0]:
                _at, words, spoken = LINES[self._gleebs_line]
                self._gleebs_line += 1
                if spoken:
                    self.sfx('gleebs_voice')
                    words = 'GLEEBS:  ' + words
                self.say(words, LINE_TIME)
            if self.gleebs_t >= ARRIVE_END:
                self.gleebs_state = 'waiting'
                use = self.bindings.get('use', 'e').upper()
                self.say(f'Gleebs waits in its light. Walk into it with Nyx beside you, and hold {use}.', 6.0)
                if hasattr(self, 'save_game'):
                    self.save_game('gleebs waits')
        elif state == 'leaving':
            self._update_leaving(dt)
        self._update_gleebs_visuals(dt)

    def _update_gleebs_visuals(self, dt: float):
        if self.gleebs_root is None or self.gleebs_state in (None, 'gone'):
            return
        t = self.gleebs_t
        rng = self._gleebs_rng
        drop = _smooth(t / BEAM_DROP) if self.gleebs_state == 'arriving' else 1.0
        out = 1.0
        if self.gleebs_state == 'leaving':
            out = 1.0 - _smooth((t - BEAM_OUT[0]) / (BEAM_OUT[1] - BEAM_OUT[0]))
        # the beam falls from the sky (its foot reaches the sand at BEAM_DROP)
        length = max(1.0, BEAM_TOP * drop)
        self.gleebs_beam.setPos(0, 0, BEAM_TOP)
        self.gleebs_beam.setScale(1.0, 1.0, length)
        flare = 1.0 + (0.8 if self.gleebs_state == 'leaving' and t < RISE_TIME else 0.0) * math.sin(math.pi * min(1.0, t / RISE_TIME))
        for b in self.gleebs_beam.getChildren():
            b.setColor(*HOLO_COLOUR, float(b.getTag('alpha')) * out * flare)
        _scroll_scan(self.gleebs_beam, self._gleebs_beam_scan, 1.6, -t * 0.9)
        self.gleebs_pool.setColor(*HOLO_COLOUR, 0.45 * drop * out)
        # the hologram flickers into being, glitches now and then, and scanlines crawl up it
        if self.gleebs_state == 'arriving':
            form = _smooth((t - FORM[0]) / (FORM[1] - FORM[0]))
            stutter = 1.0 if form >= 1.0 else (0.35 + 0.65 * (rng.random() > 0.35))
        else:
            form, stutter = 1.0, 1.0
        self._gleebs_glitch = max(0.0, self._gleebs_glitch - dt)
        if self._gleebs_glitch <= 0.0 and rng.random() < dt * 0.35:
            self._gleebs_glitch = rng.uniform(0.06, 0.16)
        glitch = self._gleebs_glitch > 0.0
        shimmer = 0.82 + 0.10 * math.sin(t * 7.3) + 0.08 * math.sin(t * 23.0)
        a = form * stutter * shimmer * out * (0.45 if glitch else 1.0)
        night = sky.night_amount(self.hour) if hasattr(self, 'hour') else 0.0
        day = HOLO_DAY_COLOUR
        col = [day[i] + (HOLO_COLOUR[i] - day[i]) * night for i in range(3)]
        self.gleebs_body.setColorScale(col[0], col[1], col[2], (0.85 - 0.45 * night) * a)
        self.gleebs_glow.setColorScale(col[0], col[1], col[2], (0.12 + 0.50 * night) * a)
        self.gleebs_halo.setColor(*HOLO_COLOUR, (0.10 + 0.30 * night) * a)
        self.gleebs_holo.setX(rng.uniform(-0.6, 0.6) if glitch else 0.0)
        self.gleebs_holo.setZ(1.5 + 0.6 * math.sin(t * 0.8))           # it hangs just above the sand, breathing
        if self.gleebs_actor is not None:
            _scroll_scan(self.gleebs_actor, self._gleebs_scan, SCAN_METRES, -t * 0.7)
        self._gleebs_light = 0.0 if self.gleebs_state is None else max(drop * 0.4, form) * out

    # ------------------------------------------------------------ its light
    def sync_crimson_shader(self):
        super().sync_crimson_shader()
        level = getattr(self, '_gleebs_light', 0.0) if getattr(self, 'gleebs_state', None) not in (None, 'gone') else 0.0
        if level <= 0.0 or not getattr(self, 'sketch_style_enabled', False) or getattr(self, '_crimson_level', 0.0) > 0.0:
            return
        p = self.gleebs_pos + Vec3(0, 0, 10.0)
        v = self.camera.getRelativePoint(self.render, p)
        self.render.setShaderInput('glow3_pos_view', Vec4(v.x, v.z, -v.y, LIGHT_REACH))
        k = LIGHT * level
        self.render.setShaderInput('glow3_color', Vec4(HOLO_COLOUR[0] * k, HOLO_COLOUR[1] * k, HOLO_COLOUR[2] * k, 1.0))

    # ------------------------------------------------------------ the ending card
    def ending_title(self) -> str:
        return 'they left REDACTED'

    def ending_story(self):
        return ('Nyx and Orbit went up into the light with Gleebs.',
                'Crimson stayed. It was strong, but never wise, and it perished with REDACTED.',
                'No one will look for this world again.')

    # ------------------------------------------------------------ saves
    def gleebs_snapshot(self) -> dict:
        if self.gleebs_state is None:
            return {}
        state = 'gone' if self.gleebs_state == 'leaving' else self.gleebs_state     # saved mid-scene: they have gone
        if getattr(self, 'gleebs_pos', None) is None:                                  # Pass 63: never placed
            return {'state': state}
        return {'state': state, 'pos': [round(self.gleebs_pos.x, 2), round(self.gleebs_pos.y, 2)],
                'heading': round(self.gleebs_heading, 1)}

    def apply_gleebs(self, d: dict):
        state = (d or {}).get('state')
        if state in ('arriving', 'waiting', 'gone') and self.red_dead:
            x, y = d.get('pos', [self.human.getX() + 40.0, self.human.getY()])
            # saved while it was still speaking: it comes down again, in the same place
            self.begin_gleebs(Point3(float(x), float(y), 0.0), float(d.get('heading', 0.0)),
                              'arriving' if state == 'arriving' else 'waiting')
            if state == 'gone':
                self.gleebs_state = 'gone'
                self.gleebs_root.hide()
                self.human.hide()
                self.giant.hide()
                self._hide_hud_for_scene(True)
        elif self.red_dead and self.ending_shown:
            self._gleebs_arrive_in = 6.0       # an older journey whose Crimson already lies dead
