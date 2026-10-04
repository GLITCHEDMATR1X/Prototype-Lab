"""Pass 50 — the first dawn: a few quiet hints for a new journey.

One line at the top of the screen, one thing at a time, each gone the moment you have
done it (and never shown again): walk and look, call Indigo, dig, ask for shade, ride on
Indigo's shoulder, walk into a shell, then the journal / making / controls keys.
Indigo turns its head toward the buried find and the nearest whole shell when those
steps come up. Turn the hints off in settings ("first-dawn hints"). Saved with the journey.
"""
from __future__ import annotations

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import Point3, TextNode

from . import controls
from . import desert
from .survival import _flat_dist

TEACH_Y = 0.78
CHECK_EVERY = 0.25
LAST_STEP_SECONDS = 12.0


class TeachMixin:
    teach_step = None
    teach_headless = False

    def _init_teach(self):
        self._teach_t = 0.0
        self._teach_alpha = 0.0
        self._teach_shown = None
        self._teach_hold = 0.0
        self._teach_from = Point3(self.human.getPos(self.render))
        font = getattr(self, 'font_ui', None)
        self.hud_teach = OnscreenText(text='', pos=(0.0, TEACH_Y), align=TextNode.ACenter, scale=0.036,
                                      font=font, fg=(0.13, 0.11, 0.12, 0.0), mayChange=True)
        if self.teach_step is None:              # not set by a loaded journey
            fresh = getattr(self, 'new_game', False) or not getattr(self, 'loaded_from_save', False)
            # headless runs (the check scripts) only teach when asked to (teach_headless=True)
            if getattr(self, 'offscreen', False) and not getattr(self, 'teach_headless', False):
                fresh = False
            self.teach_step = 0 if fresh else len(self.teach_steps())

    def teach_steps(self):
        b = self.bindings
        L = lambda a: controls.label(b, a)       # noqa: E731
        move = f'{L("move_forward")} {L("move_left")} {L("move_back")} {L("move_right")}'
        return (
            ('walk', f'{move}  walk   ·   hold right mouse  look around'),
            ('come', f'Nyx waits for you.   {L("come")}  call it'),
            ('dig', f'Something is buried close by.   hold {L("use")} beside it to dig'),
            ('shade', f'The sun is heavy.   {L("shade")}  ask Nyx for shade  ·  or stand in its shadow'),
            ('lift', f'{L("lift")}  Nyx lifts you onto its shoulder   ·   {L("lift")} again to get down'),
            ('shell', f'Shells are shelter from sun, cold and Crimson.   walk into an unbroken shell (or {L("use")} at its mouth)'),
            ('more', f'{L("journal")}  journal   ·   {L("craft")}  make things   ·   {L("controls_help")}  every control'),
        )

    def _teach_done(self, key) -> bool:
        if key == 'walk':
            return _flat_dist(self.human.getPos(self.render), self._teach_from) >= 8.0
        if key == 'come':
            return self.comp.get('mode') == 'follow'
        if key == 'dig':
            return self.stats['finds_dug'] >= 1
        if key == 'shade':
            return self.comp.get('mode') == 'shade' or self.shelter_word in ('shade', 'riding shaded')
        if key == 'lift':
            return bool(self.carried)
        if key == 'shell':
            return self.hidden_shell is not None
        if key == 'more':
            return self._teach_hold >= LAST_STEP_SECONDS
        return True

    def _teach_gaze(self, key):
        """Indigo turns its head toward what the hint is about."""
        hp = self.human.getPos(self.render)
        target = None
        if key == 'dig':
            f = self.finds.nearest(hp, 200.0)
            target = f.pos if f is not None else None
        elif key == 'shell':
            s = self.shells.nearest(hp, 400.0, states=('intact',))
            target = s.pos if s is not None else None
        if target is not None:
            self.notice = {'pos': Point3(target), 't': desert.NOTICE_TIME}

    def survival_step(self, dt: float):
        super().survival_step(dt)
        if getattr(self, 'hud_teach', None) is None:
            return
        steps = self.teach_steps()
        active = (self.settings.get('hints', True) and self.teach_step < len(steps) and self.human_alive
                  and self.panel_name is None and not self.world_frozen())
        if active:
            self._teach_t -= dt
            key, text = steps[self.teach_step]
            if key == 'more':
                self._teach_hold += dt
            if self._teach_t <= 0.0:
                self._teach_t = CHECK_EVERY
                if self._teach_done(key):
                    self.teach_step += 1
                    self._teach_shown = None
                    self._teach_hold = 0.0
                    return
            if self._teach_shown != key:
                self._teach_shown = key
                self.hud_teach.setText(text)
                self._teach_gaze(key)
        target = 0.85 if active else 0.0
        self._teach_alpha += (target - self._teach_alpha) * min(1.0, dt * 3.0)
        ink = self._ink_now() if hasattr(self, '_ink_now') else (0.13, 0.11, 0.12)
        self._sf(self.hud_teach, (*ink, round(self._teach_alpha, 2)))     # only touched when it changes
