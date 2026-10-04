"""Pass 43 — day and night.

A day lasts 16 minutes: 12 minutes of daylight (06:00-18:00, one minute per hour) and a
4-minute night (18:00-06:00, 20 seconds per hour).  The sun really moves, so shadows
(and the shade they give) sweep, grow long at dawn and dusk and shrink at noon.

HEAT follows the sun: dawn and dusk are gentle (x0.45), noon is harsh (x1.15, about
4 1/2 minutes to collapse in open sun), and the night cools you.
NIGHT is blue and dim; the Red Giant sees less far (60%), so night travel is quieter
but harder to read.
SLEEP (Z) inside a shell from 17:00 until 05:00 passes the night: you wake at dawn fully
rested and cooled, Indigo is healed, the water skin fills with dew, and that shell
becomes your camp (where you wake after collapsing).  You cannot sleep while the
Red Giant is hunting close by.
"""
from __future__ import annotations

import math

from panda3d.core import CardMaker, TransparencyAttrib, Vec4

from .survival import K
from .sky import zenith_at as sky_zenith

DAY_START, DAY_END = 6.0, 18.0
SECONDS_PER_DAY_HOUR = 60.0
SECONDS_PER_NIGHT_HOUR = 20.0
START_HOUR = 7.0
SLEEP_FROM, SLEEP_UNTIL = 17.0, 5.0
WAKE_HOUR = 6.0
RED_NIGHT_SIGHT = 0.6
SLEEP_BLOCK_RANGE = 150.0
FADE_TIME = 1.3

# (hour, scene tint, fog / sky colour)
_KEYS = (
    (0.0, (0.40, 0.44, 0.60), (0.17, 0.19, 0.27)),
    (4.8, (0.40, 0.44, 0.60), (0.17, 0.19, 0.27)),
    (6.2, (1.00, 0.86, 0.78), (0.90, 0.78, 0.70)),
    (8.5, (1.00, 1.00, 1.00), (0.91, 0.88, 0.82)),
    (15.5, (1.00, 1.00, 1.00), (0.91, 0.88, 0.82)),
    (17.6, (1.00, 0.80, 0.66), (0.88, 0.68, 0.56)),
    (19.0, (0.40, 0.44, 0.60), (0.17, 0.19, 0.27)),
    (24.0, (0.40, 0.44, 0.60), (0.17, 0.19, 0.27)),
)


def _mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def palette_at(hour: float):
    for (h0, t0, f0), (h1, t1, f1) in zip(_KEYS, _KEYS[1:]):
        if h0 <= hour <= h1:
            t = (hour - h0) / max(h1 - h0, 1e-6)
            t = t * t * (3 - 2 * t)
            return _mix(t0, t1, t), _mix(f0, f1, t)
    return _KEYS[0][1], _KEYS[0][2]


def is_night(hour: float) -> bool:
    return hour >= DAY_END + 0.5 or hour < DAY_START - 0.5


def sun_heat_factor(hour: float) -> float:
    """Multiplier on the sun's heating; negative = the air cools you."""
    if DAY_START <= hour <= DAY_END:
        return 0.45 + 0.70 * math.sin(math.pi * (hour - DAY_START) / (DAY_END - DAY_START))
    return -1.2


def sun_angles(hour: float):
    """(azimuth, elevation) of the light: the sun by day, a low moon by night."""
    if DAY_START <= hour <= DAY_END:
        k = (hour - DAY_START) / (DAY_END - DAY_START)
        return 80.0 + 200.0 * k, max(6.0, 72.0 * math.sin(math.pi * k))
    k = ((hour - DAY_END) % 24.0) / 12.0
    return 260.0 - 200.0 * k, 34.0


class DayCycleMixin:
    def _init_daycycle(self):
        self.day = 1
        self.hour = START_HOUR
        self.nights_slept = 0
        self.camp_shell = None
        self.water_sips = 0
        self._sun_timer = 0.0
        self._sleep = None
        self.time_frozen = False            # test hooks
        self.heat_factor_override = None
        cm = CardMaker('sleep_fade')
        cm.setFrame(-1, 1, -1, 1)
        self.fade_card = self.render2d.attachNewNode(cm.generate())
        self.fade_card.setColor(0.05, 0.05, 0.08, 1)
        self.fade_card.setTransparency(TransparencyAttrib.MAlpha)
        self.fade_card.setBin('fixed', 50)
        self.fade_card.setAlphaScale(0.0)
        self.sky = None
        if getattr(self, 'sketch_style_enabled', False):
            from . import sky
            self.sky = sky.SkyDome(self.camera, K.get('SHADOW_CAMERA_MASK'))
        self._apply_time(force=True)

    # ---------------------------------------------------------------- queries
    def sun_heat_factor(self) -> float:
        if self.heat_factor_override is not None:          # test hook
            return self.heat_factor_override
        return sun_heat_factor(self.hour)

    def is_night(self) -> bool:
        return is_night(self.hour)

    def red_detection_range(self) -> float:
        return K['RED_DETECTION_RANGE'] * (RED_NIGHT_SIGHT if self.is_night() else 1.0)

    def time_words(self) -> str:
        h = self.hour
        if h < 5.0 or h >= 19.5:
            return 'night'
        if h < 7.5:
            return 'dawn'
        if h < 11.0:
            return 'morning'
        if h < 14.0:
            return 'noon'
        if h < 17.0:
            return 'afternoon'
        return 'dusk'

    # ------------------------------------------------------------------ time
    def advance_time(self, dt: float):
        if self.time_frozen:
            return
        rate = SECONDS_PER_DAY_HOUR if DAY_START <= self.hour < DAY_END else SECONDS_PER_NIGHT_HOUR
        before = self.hour
        self.hour += dt / rate
        if self.hour >= 24.0:
            self.hour -= 24.0
        if before < DAY_START <= self.hour:
            self.day += 1

    def _apply_time(self, force: bool = False):
        az, el = sun_angles(self.hour)
        # The shade proxies are refreshed by the 30 Hz shadow task anyway, so moving the
        # sun does not rebuild them here (that cost ~4 ms per update).
        self._set_sun_angles(az, el, rebuild_shadows=force)
        tint, fog = palette_at(self.hour)
        self.render.setColorScale(tint[0], tint[1], tint[2], 1.0)
        self.render.setShaderInput('fog_color', Vec4(fog[0], fog[1], fog[2], 1.0))
        self.setBackgroundColor(fog[0], fog[1], fog[2], 1.0)
        if getattr(self, 'sky', None) is not None:
            self.sky.set_state(self.hour, self.sun_to_light_world, fog)
            z = sky_zenith(self.hour)
            self.render.setShaderInput('fog_zenith', Vec4(z[0], z[1], z[2], 1.0))   # Pass 45

    def survival_step(self, dt: float):
        if getattr(self, 'paused', False):
            return
        self._update_daycycle(dt)
        if self.sleeping():
            return
        super().survival_step(dt)

    def _update_daycycle(self, dt: float):
        if self._sleep is not None:
            self._update_sleep(dt)
            return
        self.advance_time(dt)
        self._sun_timer -= dt
        if self._sun_timer <= 0.0:
            self._sun_timer = 0.5
            self._apply_time()

    # ----------------------------------------------------------------- sleep
    def can_sleep(self):
        """(ok, reason)"""
        if self._sleep is not None:
            return False, ''
        if self.hidden_shell is None and not self.sleep_spot_beside_indigo():
            return False, 'sleep inside a shell, or curled against Nyx'
        if not (self.hour >= SLEEP_FROM or self.hour < SLEEP_UNTIL):
            return False, 'too early to sleep - rest comes at dusk'
        red_active = not (self.red_knocked_out or self.red_recovering or self.red_fleeing or self.red_lurking or self.red_dead)
        blocks = self.red_blocks_sleep() if hasattr(self, 'red_blocks_sleep') else self.red_state != 'idle'
        if red_active and self._human_red_distance() <= SLEEP_BLOCK_RANGE and blocks:
            return False, 'Crimson is too close to sleep'
        return True, ''

    def sleep_spot_beside_indigo(self) -> bool:
        return False                           # Pass 48: GiantsLifeMixin allows sleeping against Indigo

    def request_sleep(self):
        if self.input_blocked():
            return False
        ok, reason = self.can_sleep()
        if not ok:
            if reason:
                self.say(reason, 2.0)
            return False
        self._sleep = {'phase': 'out', 't': 0.0}
        return True

    def _update_sleep(self, dt: float):
        s = self._sleep
        s['t'] += dt
        if s['phase'] == 'out':
            self.fade_card.setAlphaScale(min(1.0, s['t'] / FADE_TIME))
            if s['t'] >= FADE_TIME:
                self._do_sleep()
                s.update(phase='in', t=0.0)
        else:
            self.fade_card.setAlphaScale(max(0.0, 1.0 - s['t'] / FADE_TIME))
            if s['t'] >= FADE_TIME:
                self._sleep = None
                self.fade_card.setAlphaScale(0.0)

    def _do_sleep(self):
        self.day += 1                      # Pass 44 (B9): every sleep ends a night
        self.hour = WAKE_HOUR
        self.nights_slept += 1
        self.human_health = K['HUMAN_MAX_HEALTH']
        self.stamina = 100.0
        self.heat = 0.0
        self.winded = False
        if self.giant_alive:
            self.giant_health = K['GIANT_MAX_HEALTH']
        if self.has_upgrade('waterskin'):
            self.water_sips = 3
        if self.hidden_shell is not None:  # Pass 44 (B2): sleeping in the open keeps the old camp
            self.camp_shell = self.hidden_shell
        self._apply_time(force=True)
        self.say(f'day {self.day}.  the sand is cool at dawn.', 3.5)
        if hasattr(self, 'save_game'):
            self.save_game('slept')

    def sleeping(self) -> bool:
        return self._sleep is not None
