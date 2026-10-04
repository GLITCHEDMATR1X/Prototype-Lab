"""Pass 59 - Indigo's night glow.

AT NIGHT  Indigo radiates a soft indigo light (it comes up with the dusk and fades at dawn):
            - its body glows and shows through the night haze
            - the light falls on the sand around it and on you (the side of you facing it)
            - it PROTECTS Indigo: hits cost it 40% less stamina, the cold drains it half as fast
            - it WARMS you: near Indigo (inside its light) the cold eases, stronger the closer
          Knocked out, Indigo's glow sinks to an ember.

DRAWING   At night, beside Indigo, hold E to cup some of its light in your hands. It settles on
THE GLOW  your skin (a faint indigo shimmer; the "glow" bar). Each draw dims Indigo a little for a
          while (its light, protection and warmth are a little weaker until it recovers).

WHILE YOU CARRY IT (a perk)
          - strength: effort costs you less breath (x0.6) and you work faster (dig, smash,
            search, patch... in 0.7 of the time)
          - health: you heal slowly, and heat, cold and blows hurt you less (x0.65)
          - at night it also keeps some of the cold off you
          It is spent as you spend breath by day, and a little with each passing minute. If you
          run out of breath (winded) by day, what is left of it fades away at once.
"""
from __future__ import annotations

import math

from panda3d.core import (CardMaker, ColorBlendAttrib, PNMImage, Point3, TransparencyAttrib, Texture, Vec3,
                          Vec4)

from . import sky
from .survival import K, _flat_dist

# ---------------------------------------------------------------- Indigo's glow
GLOW_COLOUR = (0.34, 0.33, 1.00)       # radiant indigo
GLOW_LIGHT = 0.95                     # strength of the light it casts at full glow
GLOW_REACH = 30.0                     # metres its light reaches (on the sand, on you)
GLOW_SELF = 0.85                      # how much its body radiates at full glow
GLOW_KO = 0.15                        # knocked out: an ember
GLOW_GUARD = 0.40                     # hits cost Indigo this much less at full glow
GLOW_COLD_GUARD = 0.50                # and the cold drains its energy half as fast (it still tires by dawn)
GLOW_WARM_RANGE = 24.0                # inside this, its light warms you (beyond the 14 m of its body heat)
GLOW_WARM = 9.0                       # chill eased per second at full glow, right beside it
RESERVE_REGEN = 1.0 / 240.0           # Indigo's glow recovers fully in 4 minutes after a draw
AURA_SIZE = 1.25                      # the halo is this x Indigo's height across
AURA_FADE = (160.0, 420.0)            # the halo fades out with distance from the camera

# ---------------------------------------------------------------- the glow you carry
DRAW_RANGE = 12.0                     # metres from Indigo to draw on it
DRAW_TIME = 1.4                       # hold E
DRAW_AMOUNT = 60.0                    # of 100
DRAW_COST = 0.30                      # of Indigo's reserve
DRAW_MIN_GLOW = 0.30                  # Indigo must be glowing at least this much
CHARGE_MAX = 100.0
STAMINA_SCALE = 0.6                   # effort costs x0.6 breath while you carry it
WORK_SPEED = 1.0 / 0.7                # hold-E work in 0.7 of the time
DAMAGE_SCALE = 0.65                   # heat, cold and blows hurt x0.65
HEAL_RATE = 0.35                      # life per second
NIGHT_CHILL_SCALE = 0.6               # the cold creeps in slower at night while you carry it
SPEND_PER_BREATH = 0.45               # glow spent for each point of breath spent by day
DAY_DECAY = 100.0 / 900.0             # and a little with each passing minute by day (15 min from full)
WINDED_FADE = 45.0                    # winded by day: what is left fades in ~2 s
PLAYER_LIGHT = 0.30                   # the faint light around you while you carry it
PLAYER_LIGHT_REACH = 3.5
PLAYER_SELF = 0.45
PLAYER_AURA = 2.4                     # the shimmer around you, metres across


def _aura_texture() -> Texture:
    img = PNMImage(128, 128, 4)
    for y in range(128):
        for x in range(128):
            r = math.hypot((x - 63.5) / 63.5, (y - 63.5) / 63.5)
            a = max(0.0, 1.0 - r) ** 2.2
            img.setXelA(x, y, 1.0, 1.0, 1.0, a)
    tex = Texture('indigo_aura')
    tex.load(img)
    return tex


def _aura_card(parent, tex, size: float):
    cm = CardMaker('aura')
    cm.setFrame(-0.5, 0.5, -0.5, 0.5)
    np_ = parent.attachNewNode(cm.generate())
    np_.setTexture(tex)
    np_.setScale(size)
    np_.setBillboardPointEye()
    np_.setShaderOff(10)                   # a plain textured card, not the sketch shader
    np_.setLightOff(10)
    np_.setTransparency(TransparencyAttrib.MAlpha)
    np_.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
    np_.setDepthWrite(False)
    np_.setBin('fixed', 30)
    np_.hide(K['SHADOW_CAMERA_MASK'])
    np_.setColor(*GLOW_COLOUR, 0.0)
    np_.hide()
    return np_


class GlowMixin:
    # ------------------------------------------------------------ state
    def _init_glow(self):
        self.glow_charge = 0.0                     # the glow you carry, 0..100
        self.indigo_glow_reserve = 1.0             # 1 = Indigo's full glow; draws dim it for a while
        self._glow_level = 0.0
        self.giant.setShaderInput('glow_receive', Vec3(0.0, 1.0, 1.0))     # Indigo does not light its own body
        tex = _aura_texture()
        self.indigo_aura = _aura_card(self.render, tex, self.giant_height * AURA_SIZE)
        self.player_aura = _aura_card(self.render, tex, PLAYER_AURA)
        self.glow_level()

    # ------------------------------------------------------------ how strong
    def glow_night(self) -> float:
        return sky.night_amount(getattr(self, 'hour', 12.0))

    def glow_level(self) -> float:
        """How brightly Indigo glows now: 0 by day, up to 1 in deep night."""
        night = self.glow_night()
        if night <= 0.0 or getattr(self, 'giant_actor', None) is None:
            level = 0.0
        elif getattr(self, 'giant_knocked_out', False) or not self.giant_alive:
            level = night * GLOW_KO
        else:
            level = night * (0.4 + 0.6 * self.indigo_glow_reserve)
        self._glow_level = level
        return level

    def glow_charged(self) -> bool:
        return getattr(self, 'glow_charge', 0.0) > 0.0

    # ------------------------------------------------------------ the perk (hooks in desert / wild / main)
    def stamina_cost_scale(self) -> float:
        return STAMINA_SCALE if self.glow_charged() else super().stamina_cost_scale()

    def work_speed(self) -> float:
        return WORK_SPEED if self.glow_charged() else super().work_speed()

    def human_damage_scale(self) -> float:
        return DAMAGE_SCALE if self.glow_charged() else super().human_damage_scale()

    def on_stamina_spent(self, amount: float):
        super().on_stamina_spent(amount)
        if self.glow_charged() and not self.is_night():
            self.glow_charge = max(0.0, self.glow_charge - amount * SPEND_PER_BREATH)
            if self.glow_charge <= 0.0:
                self._glow_gone()

    def indigo_hit_scale(self) -> float:
        """Hits on Indigo cost this much of their usual stamina (its glow shields it)."""
        return 1.0 - GLOW_GUARD * self._glow_level

    def indigo_cold_scale(self) -> float:
        return 1.0 - GLOW_COLD_GUARD * self._glow_level

    def _update_chill(self, dt: float, night: bool):
        before = getattr(self, 'chill', 0.0)
        super()._update_chill(dt, night)
        if not self.human_alive or not night:
            return
        if self.chill > before and self.glow_charged():
            self.chill = before + (self.chill - before) * NIGHT_CHILL_SCALE
        # inside Indigo's light (beyond the 14 m of its body warmth) the cold eases too
        if self.giant_alive and self._glow_level > 0.0 and not self.carried:
            d = _flat_dist(self.human.getPos(self.render), self.giant.getPos(self.render))
            if d <= GLOW_WARM_RANGE:
                k = 1.0 - d / GLOW_WARM_RANGE
                self.chill = max(0.0, self.chill - GLOW_WARM * self._glow_level * k * dt)

    def glow_warming(self) -> bool:
        if not self.giant_alive or self._glow_level <= 0.05 or not self.human_alive:
            return False
        return _flat_dist(self.human.getPos(self.render), self.giant.getPos(self.render)) <= GLOW_WARM_RANGE

    # ------------------------------------------------------------ drawing the glow (hold E)
    def can_draw_glow(self) -> bool:
        if self.controlled_name != 'human' or not self.human_alive or self.carried or not self.giant_alive:
            return False
        if self.glow_charge >= CHARGE_MAX - 5.0 or self._glow_level < DRAW_MIN_GLOW:
            return False
        return _flat_dist(self.human.getPos(self.render), self.giant.getPos(self.render)) <= DRAW_RANGE

    def _e_target(self):
        kind, target = super()._e_target()
        if kind is None and self.can_draw_glow():
            return 'glow', None
        return kind, target

    def place_prompt(self, kind, target) -> str:
        if kind == 'glow':
            return "draw some of Nyx's glow"
        return super().place_prompt(kind, target)

    def _complete_e(self, kind, target):
        if kind != 'glow':
            return super()._complete_e(kind, target)
        if not self.can_draw_glow():
            return None
        first = self.glow_charge <= 0.0
        self.glow_charge = min(CHARGE_MAX, self.glow_charge + DRAW_AMOUNT)
        self.indigo_glow_reserve = max(0.0, self.indigo_glow_reserve - DRAW_COST)
        self.glow_level()
        self.stats['glow_draws'] = self.stats.get('glow_draws', 0) + 1
        gp = self.giant.getPos(self.render)
        self.sfx('hum_indigo_sense', Point3(gp.x, gp.y, gp.z + self.giant_height * 0.6))
        self.say("you cup your hands in Nyx's light. it settles on your skin, warm." if first
                 else 'more of the light settles on you.', 3.0)
        return None

    def _glow_gone(self):
        self.glow_charge = 0.0
        self.say('the indigo glow fades from your skin.', 2.5)

    # ------------------------------------------------------------ per frame
    def survival_step(self, dt: float):
        super().survival_step(dt)
        if not hasattr(self, 'indigo_glow_reserve') or self.world_frozen():
            return
        self.indigo_glow_reserve = min(1.0, self.indigo_glow_reserve + RESERVE_REGEN * dt)
        self.glow_level()
        if (self._glow_level > 0.6 and not self.stats.get('glow_told') and self.human_alive and self.giant_alive
                and _flat_dist(self.human.getPos(self.render), self.giant.getPos(self.render)) < 80.0):
            self.stats['glow_told'] = 1           # once per journey: the first night
            use = self.bindings.get('use', 'e').upper()
            self.say(f'In the dark, Nyx glows. Its light is warm.  Hold {use} beside it to take a little.', 6.0)
        if self.glow_charged() and self.human_alive:
            self.human_health = min(K['HUMAN_MAX_HEALTH'], self.human_health + HEAL_RATE * dt)
            if not self.is_night():
                if self.winded:
                    self.glow_charge = max(0.0, self.glow_charge - WINDED_FADE * dt)
                else:
                    self.glow_charge = max(0.0, self.glow_charge - DAY_DECAY * dt)
                if self.glow_charge <= 0.0:
                    self._glow_gone()
        self._update_glow_visuals()

    def _update_glow_visuals(self):
        level = self._glow_level
        g = self.giant
        # Indigo's body radiates; its halo hangs round its chest
        g.setShaderInput('glow_self', GLOW_SELF * level)
        if level > 0.01:
            chest = g.getPos(self.render) + Vec3(0, 0, self.giant_height * 0.55)
            self.indigo_aura.setPos(chest)
            cam_d = (self.camera.getPos(self.render) - chest).length()
            fade = 1.0 - min(1.0, max(0.0, (cam_d - AURA_FADE[0]) / (AURA_FADE[1] - AURA_FADE[0])))
            self.indigo_aura.setColor(*GLOW_COLOUR, 0.55 * level * fade)
            self.indigo_aura.show()
        else:
            self.indigo_aura.hide()
        # the glow you carry
        c = self.glow_charge / CHARGE_MAX if self.human_alive else 0.0
        self.human.setShaderInput('glow_self', PLAYER_SELF * c)
        if c > 0.01 and not self.human.isHidden():
            self.player_aura.setPos(self.human.getPos(self.render) + Vec3(0, 0, self.human_height * 0.55))
            pulse = 0.85 + 0.15 * math.sin(self._glow_clock() * 2.2)
            dark = 0.3 + 0.7 * self.glow_night()          # a shimmer by day, a soft light at night
            self.player_aura.setColor(*GLOW_COLOUR, 0.35 * c * pulse * dark)
            self.player_aura.show()
        else:
            self.player_aura.hide()
        self.sync_glow_shader()

    def _glow_clock(self) -> float:
        return getattr(self, '_fight_clock', 0.0)

    def _view_pos(self, p: Point3):
        """A world point in the shader's view space (OpenGL's: x right, y up, z toward the viewer)."""
        v = self.camera.getRelativePoint(self.render, p)
        return v.x, v.z, -v.y

    def sync_glow_shader(self):
        if not getattr(self, 'sketch_style_enabled', False) or not hasattr(self, 'indigo_glow_reserve'):
            return
        level = self._glow_level
        if level > 0.0:
            x, y, z = self._view_pos(self.giant.getPos(self.render) + Vec3(0, 0, self.giant_height * 0.45))
            self.render.setShaderInput('glow_pos_view', Vec4(x, y, z, GLOW_REACH))
            k = GLOW_LIGHT * level
            self.render.setShaderInput('glow_color', Vec4(GLOW_COLOUR[0] * k, GLOW_COLOUR[1] * k, GLOW_COLOUR[2] * k, 1.0))
        else:
            self.render.setShaderInput('glow_color', Vec4(0, 0, 0, 0))
        c = self.glow_charge / CHARGE_MAX if self.human_alive else 0.0
        if c > 0.0 and not self.human.isHidden():
            x, y, z = self._view_pos(self.human.getPos(self.render) + Vec3(0, 0, self.human_height * 0.6))
            self.render.setShaderInput('glow2_pos_view', Vec4(x, y, z, PLAYER_LIGHT_REACH))
            k = PLAYER_LIGHT * c * (0.5 + 0.5 * self.glow_night())     # faint by day, clearer at night
            self.render.setShaderInput('glow2_color', Vec4(GLOW_COLOUR[0] * k, GLOW_COLOUR[1] * k, GLOW_COLOUR[2] * k, 1.0))
        else:
            self.render.setShaderInput('glow2_color', Vec4(0, 0, 0, 0))

    # ------------------------------------------------------------ saves
    def glow_snapshot(self) -> dict:
        return {'charge': round(self.glow_charge, 2), 'reserve': round(self.indigo_glow_reserve, 3)}

    def apply_glow(self, d: dict):
        self.glow_charge = max(0.0, min(CHARGE_MAX, float(d.get('charge', 0.0))))
        self.indigo_glow_reserve = max(0.0, min(1.0, float(d.get('reserve', 1.0))))
        self.glow_level()

    def reset_survival_after_retry(self):
        super().reset_survival_after_retry()
        self.glow_charge = 0.0
