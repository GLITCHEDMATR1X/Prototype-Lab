"""Pass 60 - the red one's crimson powers (at night only).

AT NIGHT  The red one burns crimson: its body glows, a crimson light falls on the sand round it
          (and on you), a crimson halo hangs round it. It rises with the dusk and ends at dawn.

THE CRIMSON WAVE (avoid it)
          When you or Indigo come within ~24 m of it at night - resting or awake - the crimson
          light swells for 1.8 s: its body flares and a ring on the sand shows how far the wave
          will reach (30 m). Then the wave bursts outward. Caught inside the ring:
            - you: thrown back and dazed, and hurt badly (40 life; less with Indigo's glow on you)
            - Indigo: winded (stamina) and staggered, a little hurt (its own glow softens it)
          Get out of the ring before it bursts: a jog does it, a walk does not. Inside an unbroken
          shell, or riding on Indigo's shoulder, the wave passes you by. It needs 6 s to swell again.
          Awake, it stops and raises its arms to call the wave.

THE CRIMSON WARD
          While it rests at night, or lies knocked out at night, the crimson light wards it:
            - blows glance off (and set off a wave)
            - you cannot push a pale scrap between its teeth
          You cannot beat it while it rests. By day it has no crimson power at all.
"""
from __future__ import annotations

import math

from panda3d.core import (ColorBlendAttrib, Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
                          GeomVertexWriter, Point3, TransparencyAttrib, Vec3, Vec4)

from . import glow as glowmod
from . import sky
from .survival import K, _approach, _flat_dist

CRIMSON = (1.00, 0.10, 0.13)
CRIMSON_TINT = Vec3(0.95, 0.10, 0.12)
BODY_GLOW = 0.55                   # its body at night; flaring to 1.0 as a wave swells
LIGHT = 0.80                       # the crimson light it casts
LIGHT_REACH = 26.0
AURA_SIZE = 1.1                    # halo, x its height
NIGHT_MIN = 0.5                    # the powers wake once the night is half come

TRIGGER_RANGE = 24.0               # you or Indigo this close -> a wave swells
PULSE_RADIUS = 30.0                # how far the wave reaches
CHARGE_TIME = 1.8                  # the warning: get out of the ring
WAVE_TIME = 0.45                   # the wave runs out to its edge
COOLDOWN = 6.0
HUMAN_DAMAGE = 40.0
HUMAN_DAZE = 1.2
HUMAN_THROW = 4.0                  # metres
INDIGO_STAMINA = 18.0
INDIGO_HEALTH = 4.0
INDIGO_STAGGER = 1.2
RING_SEGMENTS = 72
WARD_MSG_EVERY = 6.0


def _ring_node(name: str):
    """A soft crimson band lying on the sand (inner edge, middle, outer edge x RING_SEGMENTS)."""
    vdata = GeomVertexData(name, GeomVertexFormat.getV3c4(), Geom.UHDynamic)
    vdata.setNumRows(RING_SEGMENTS * 3)
    tris = GeomTriangles(Geom.UHStatic)
    for i in range(RING_SEGMENTS):
        j = (i + 1) % RING_SEGMENTS
        for band in (0, 1):
            a, b = band * RING_SEGMENTS + i, band * RING_SEGMENTS + j
            c, d = (band + 1) * RING_SEGMENTS + j, (band + 1) * RING_SEGMENTS + i
            tris.addVertices(a, b, c)
            tris.addVertices(a, c, d)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode(name)
    gn.addGeom(geom)
    return gn


class CrimsonMixin:
    # ------------------------------------------------------------ state
    def _init_crimson(self):
        self.crimson_phase = 'idle'                # idle / charge / wave
        self.crimson_t = 0.0
        self.crimson_cool = 0.0
        self.crimson_hit = set()
        self._crimson_level = 0.0
        self._crimson_msg_t = 0.0
        for clip in ('Spell_Simple_Idle_Loop', 'Spell_Simple_Shoot', 'Crouch_Idle_Loop'):
            self.red_giant_actor._load_clip(self.red_giant_actor.glb_path, clip)
        self.red_giant.setShaderInput('glow_tint', CRIMSON_TINT)
        self.red_giant.setShaderInput('glow_receive', Vec3(1.0, 1.0, 0.0))   # not lit by its own light
        self.red_aura = glowmod._aura_card(self.render, glowmod._aura_texture(), self.red_giant_height * AURA_SIZE)
        self.crimson_ring = self.render.attachNewNode(_ring_node('crimson_ring'))
        r = self.crimson_ring
        r.setShaderOff(10)
        r.setLightOff(10)
        r.setTwoSided(True)
        r.setTransparency(TransparencyAttrib.MAlpha)
        r.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        r.setDepthWrite(False)
        r.setBin('fixed', 31)
        r.hide(K['SHADOW_CAMERA_MASK'])
        r.hide()

    # ------------------------------------------------------------ when
    def crimson_level(self) -> float:
        """How strongly the red one burns: 0 by day, up to 1 in deep night (0 once it is dead)."""
        if getattr(self, 'red_dead', False) or getattr(self, 'red_giant', None) is None:
            level = 0.0
        else:
            level = sky.night_amount(getattr(self, 'hour', 12.0))
        self._crimson_level = level
        return level

    def crimson_active(self) -> bool:
        return self.crimson_level() >= NIGHT_MIN

    def crimson_ward_active(self) -> bool:
        """At night, resting or knocked out, it cannot be beaten."""
        return self.crimson_active() and (getattr(self, 'red_resting', False) or self.red_knocked_out)

    def crimson_charging(self) -> bool:
        return getattr(self, 'crimson_phase', 'idle') == 'charge'

    # ------------------------------------------------------------ the ward
    def resolve_hit(self, attacker: str, defender: str, power: float = 1.0) -> str:
        if defender == 'red' and self.crimson_ward_active():
            rp = self.red_giant.getPos(self.render)
            self.sfx('punch_hit', Point3(rp.x, rp.y, rp.z + self.red_giant_height * 0.5), 0.6)
            self.say("Nyx's blow glances off the crimson light.", 2.5)
            self.crimson_retaliate()
            return 'warded'
        return super().resolve_hit(attacker, defender, power)

    def can_feed_red(self) -> bool:
        if not super().can_feed_red():
            return False
        return not self.crimson_ward_active()

    def crimson_retaliate(self):
        """Struck while warded: a wave swells at once (if one is not already under way)."""
        if self.crimson_phase == 'idle':
            self._begin_charge()

    # ------------------------------------------------------------ the wave
    def _crimson_targets(self):
        """(name, flat distance) of who the wave could reach."""
        rp = self.red_giant.getPos(self.render)
        out = []
        if self.human_alive:
            out.append(('human', _flat_dist(self.human.getPos(self.render), rp)))
        if self.giant_alive:
            out.append(('giant', _flat_dist(self.giant.getPos(self.render), rp)))
        return out

    def _begin_charge(self):
        self.crimson_phase = 'charge'
        self.crimson_t = 0.0
        self.crimson_hit = set()
        rp = self.red_giant.getPos(self.render)
        self.sfx('roar_red_heave', Point3(rp.x, rp.y, rp.z + self.red_giant_height * 0.8), 1.2)
        if self.human_alive and _flat_dist(self.human.getPos(self.render), rp) <= PULSE_RADIUS + 20.0:
            self.say("Crimson's light swells - get away from it!", 2.2)

    def update_crimson(self, dt: float, clock_t: float) -> bool:
        """Every frame, from the red one's update. True while an awake red one is calling a wave
        (it stands still, arms raised); False otherwise (its other states carry on)."""
        if not hasattr(self, 'crimson_phase') or self.world_frozen():
            return False
        level = self.crimson_level()
        self.crimson_cool = max(0.0, self.crimson_cool - dt)
        self._crimson_msg_t = max(0.0, self._crimson_msg_t - dt)
        if level < NIGHT_MIN:
            # night only: as the night ends any wave dies away unspent
            self.crimson_phase, self.crimson_t = 'idle', 0.0
            self._update_crimson_visuals()
            return False
        if level >= NIGHT_MIN and not self.stats.get('crimson_told') and self.human_alive \
                and self._human_red_distance() < 150.0:
            self.stats['crimson_told'] = 1
            self.say('At night Crimson burns with a crimson light. When its light swells, get away from it.', 6.0)
        awake = not (self.red_knocked_out or getattr(self, 'red_resting', False) or self.red_recovering)
        if self.crimson_phase == 'idle':
            if self.crimson_cool <= 0.0 and level >= NIGHT_MIN:
                if any(d <= TRIGGER_RANGE for _n, d in self._crimson_targets()):
                    self._begin_charge()
            self._ward_notice()
        elif self.crimson_phase == 'charge':
            self.crimson_t += dt
            if self.crimson_t >= CHARGE_TIME:
                self.crimson_phase, self.crimson_t = 'wave', 0.0
                rp = self.red_giant.getPos(self.render)
                self.sfx('stomp_red', rp, 1.4)
        elif self.crimson_phase == 'wave':
            self.crimson_t += dt
            reach = PULSE_RADIUS * min(1.0, self.crimson_t / WAVE_TIME)
            for name, d in self._crimson_targets():
                if name not in self.crimson_hit and d <= reach:
                    self.crimson_hit.add(name)
                    self._crimson_strike(name)
            if self.crimson_t >= WAVE_TIME + 0.35:
                self.crimson_phase, self.crimson_t = 'idle', 0.0
                self.crimson_cool = COOLDOWN
        self._update_crimson_visuals()
        if awake and self.crimson_phase in ('charge', 'wave'):
            # awake, it stands and calls the wave
            self.red_state = 'crimson'
            self.red_motion_speed = _approach(self.red_motion_speed, 0.0, K['GIANT_BRAKING'] * dt)
            if self.crimson_phase == 'charge':
                self.red_giant_actor.apply_clip('Spell_Simple_Idle_Loop', clock_t)
            else:
                shoot = self.red_giant_actor.clips['Spell_Simple_Shoot']['duration']
                self.red_giant_actor.apply_clip('Spell_Simple_Shoot', min(self.crimson_t, shoot - 1e-4), loop=False)
            return True
        return False

    def _crimson_strike(self, name: str):
        rp = self.red_giant.getPos(self.render)
        if name == 'human':
            if self.carried or self.hidden_shell is not None:
                return                              # riding high on Indigo, or inside a shell: it passes by
            hp = self.human.getPos(self.render)
            self.human_health = max(0.0, self.human_health - HUMAN_DAMAGE * self.human_damage_scale())
            self.human_dazed = max(self.human_dazed, HUMAN_DAZE)
            away = Vec3(hp.x - rp.x, hp.y - rp.y, 0)
            if away.lengthSquared() < 1e-6:
                away = Vec3(0, 1, 0)
            away.normalize()
            p = hp + away * HUMAN_THROW
            if hasattr(self, 'shells'):
                p = self.shells.collide(hp, p)
            p.z = self.field.height(p.x, p.y) - self.human_actor.height_world * K['GROUND_SINK_FRACTION']
            self.human.setPos(p)
            self.sfx('human_hurt', hp)
            self.stats['crimson_hits'] = self.stats.get('crimson_hits', 0) + 1
            if self.human_health <= 0.0:
                self.say('The crimson wave takes you.', 3.0)
                self._down_human()
            else:
                self.say('The crimson wave throws you down.', 2.5)
        else:
            k = self.indigo_hit_scale() if hasattr(self, 'indigo_hit_scale') else 1.0
            self.fight_spend('giant', INDIGO_STAMINA * k)
            self.giant_health = max(1.0, self.giant_health - INDIGO_HEALTH * k)
            st = self.attack_states['giant']
            st.update({'active': False, 'elapsed': 0.0, 'hit_done': False,
                       'cooldown': max(st.get('cooldown', 0.0), INDIGO_STAGGER)})
            self.giant_actor.apply_clip('Hit_Chest', 0.12, force=True, loop=False)

    def _ward_notice(self):
        """Near the warded red one with a pale scrap in hand: say why it will not work."""
        if self._crimson_msg_t > 0.0 or not self.crimson_ward_active() or not self.red_knocked_out:
            return
        if self.pooled_count('bane') <= 0 or not self.human_alive:
            return
        if self._near_body(self.red_giant_actor, self.red_giant, self.human.getPos(self.render), 18.0):
            self._crimson_msg_t = WARD_MSG_EVERY
            self.say('The crimson light keeps you back from its mouth. By day it will lie still.', 3.5)

    # ------------------------------------------------------------ what you see
    def _update_crimson_visuals(self):
        level = self._crimson_level
        rg = self.red_giant
        flare = 0.0
        if self.crimson_phase == 'charge':
            flare = min(1.0, self.crimson_t / CHARGE_TIME)
        elif self.crimson_phase == 'wave':
            flare = max(0.0, 1.0 - self.crimson_t / (WAVE_TIME + 0.35))
        body = level * (BODY_GLOW + (1.0 - BODY_GLOW) * flare)
        rg.setShaderInput('glow_self', body)
        if level > 0.01:
            chest = rg.getPos(self.render) + Vec3(0, 0, self.red_giant_height * 0.55)
            self.red_aura.setPos(chest)
            cam_d = (self.camera.getPos(self.render) - chest).length()
            fade = 1.0 - min(1.0, max(0.0, (cam_d - glowmod.AURA_FADE[0]) / (glowmod.AURA_FADE[1] - glowmod.AURA_FADE[0])))
            self.red_aura.setColor(*CRIMSON, (0.35 + 0.45 * flare) * level * fade)
            self.red_aura.show()
        else:
            self.red_aura.hide()
        # the ring on the sand: the reach of the wave while it swells, then the wave itself
        ring = self.crimson_ring
        if self.crimson_phase == 'charge':
            k = self.crimson_t / CHARGE_TIME
            pulse = 0.55 + 0.45 * math.sin(self.crimson_t * (6.0 + 10.0 * k))
            self._shape_ring(PULSE_RADIUS, 1.2 + 1.3 * k, (0.35 + 0.55 * k) * pulse)
            ring.show()
        elif self.crimson_phase == 'wave':
            reach = PULSE_RADIUS * min(1.0, self.crimson_t / WAVE_TIME)
            fade = 1.0 if self.crimson_t < WAVE_TIME else max(0.0, 1.0 - (self.crimson_t - WAVE_TIME) / 0.35)
            self._shape_ring(max(1.0, reach), 3.5, 0.95 * fade)
            ring.show()
        else:
            ring.hide()

    def _shape_ring(self, radius: float, width: float, alpha: float):
        rp = self.red_giant.getPos(self.render)
        vdata = self.crimson_ring.node().modifyGeom(0).modifyVertexData()
        vw = GeomVertexWriter(vdata, 'vertex')
        cw = GeomVertexWriter(vdata, 'color')
        for band, (dr, a) in enumerate(((-width, 0.0), (0.0, alpha), (width * 0.5, 0.0))):
            r = max(0.2, radius + dr)
            for i in range(RING_SEGMENTS):
                t = 2.0 * math.pi * i / RING_SEGMENTS
                x, y = rp.x + math.cos(t) * r, rp.y + math.sin(t) * r
                vw.setData3(x, y, self.field.height(x, y) + 0.25)
                cw.setData4(CRIMSON[0], CRIMSON[1], CRIMSON[2], a)

    def sync_crimson_shader(self):
        if not getattr(self, 'sketch_style_enabled', False) or not hasattr(self, 'crimson_phase'):
            return
        level = self._crimson_level
        if level > 0.0:
            p = self.red_giant.getPos(self.render) + Vec3(0, 0, self.red_giant_height * 0.45)
            v = self.camera.getRelativePoint(self.render, p)
            self.render.setShaderInput('glow3_pos_view', Vec4(v.x, v.z, -v.y, LIGHT_REACH))
            flare = min(1.0, self.crimson_t / CHARGE_TIME) if self.crimson_phase == 'charge' else 0.0
            k = LIGHT * level * (1.0 + 0.8 * flare)
            self.render.setShaderInput('glow3_color', Vec4(CRIMSON[0] * k, CRIMSON[1] * k, CRIMSON[2] * k, 1.0))
        else:
            self.render.setShaderInput('glow3_color', Vec4(0, 0, 0, 0))

    # ------------------------------------------------------------ words
    def _red_word(self) -> str:
        if self.crimson_charging():
            return 'crimson light rising - get away!'
        if self.crimson_ward_active() and getattr(self, 'red_resting', False):
            return 'resting in its crimson light'
        return super()._red_word()

    def red_blocks_sleep(self) -> bool:
        return self.crimson_charging() or super().red_blocks_sleep()
