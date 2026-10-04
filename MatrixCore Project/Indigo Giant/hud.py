"""Pass 43 — a quiet, minimal HUD in the game's own hand.

Only what matters, only when it matters:
  bottom-left    life / breath / heat - three hairline bars that fade away when you are fine
  bottom-right   Indigo (what it is doing, its health) and the Red Giant when it is near
  top-right      the day and a small sun / moon arc
  bottom-centre  what E (or Z) does right here, with a hold-progress line
  centre         words: what you find, what Indigo notices, lore
Panels: B make, J journal, F1 controls, Esc menu (pauses).  Everything is anchored to the
screen corners and scales with the window, so it reads the same at 1080p and 4K.
Fonts (SIL Open Font License, see ui/fonts/*-OFL.txt): Jura, Lora Italic, Italiana.
"""
from __future__ import annotations

import math
from pathlib import Path

from direct.gui.DirectGui import DGG, DirectButton, DirectFrame
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import CardMaker, Filename, LineSegs, NodePath, SamplerState, TextNode, TransparencyAttrib

import controls
from fight import STAMINA_MAX as _FIGHT_MAX
import desert
from survival import K

FONT_DIR = Path(__file__).resolve().parent / 'ui' / 'fonts'
INK_DAY = (0.13, 0.11, 0.12)
INK_NIGHT = (0.90, 0.88, 0.83)
PAPER = (0.95, 0.92, 0.86)
LIFE = (0.62, 0.17, 0.14)
BREATH = (0.66, 0.58, 0.42)
HEAT = (0.88, 0.47, 0.17)
INDIGO = (0.30, 0.38, 0.78)
INDIGO_PALE = (0.55, 0.62, 0.88)            # Pass 53: Indigo's stamina line
RUST = (0.66, 0.20, 0.15)
COLD = (0.40, 0.62, 0.86)     # Pass 48: the night's cold
BAR_W = 0.36
BAR_H = 0.010
HINT_SECONDS = 25.0
# Pass 45: bottom-centre text, clear of the player (who stands around the screen centre)
PROMPT_Y = -0.925             # hold-E prompt: the lowest line
LORE_BOTTOM_Y = -0.815        # messages: last line here, extra lines grow upward
LORE_SCALE = 0.044
LORE_WRAP = 46


def _lerp(a, b, t):
    return a + (b - a) * t


def fight_max(owner):
    return _FIGHT_MAX[owner]


class _Bar:
    def __init__(self, parent, x, y, label, colour, font, width=BAR_W, align_right=False):
        self.root = parent.attachNewNode(f'bar_{label}')
        self.root.setPos(x, 0, y)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        cm = CardMaker('bg')
        x0, x1 = (-width, 0.0) if align_right else (0.0, width)
        cm.setFrame(x0, x1, 0, BAR_H)
        self.bg = self.root.attachNewNode(cm.generate())
        self.bg.setColor(0, 0, 0, 0.16)
        cm = CardMaker('fill')
        cm.setFrame(0, width, 0, BAR_H)
        self.fill = self.root.attachNewNode(cm.generate())
        self.fill.setColor(*colour, 1.0)
        if align_right:
            self.fill.setX(-width)
        self.label = OnscreenText(text=label, parent=self.root, pos=(x0 if not align_right else x1, BAR_H + 0.012),
                                  align=TextNode.ARight if align_right else TextNode.ALeft,
                                  scale=0.034, font=font, fg=(*INK_DAY, 1.0), mayChange=True)
        self.value = 1.0

    def set(self, value):
        v = max(0.0, min(1.0, value))
        if abs(v - self.value) > 1e-4:
            self.value = v
            self.fill.setSx(max(v, 1e-4))


class HudMixin:
    # ------------------------------------------------------------------ setup
    def _load_font(self, name, ppu=56):
        path = FONT_DIR / name
        font = self.loader.loadFont(Filename.fromOsSpecific(str(path)).getFullpath()) if path.is_file() else None
        if font is not None and font.isValid():
            # Glyph texture sized for UI text at 1080p-4K, mip-mapped so thin strokes do not
            # drop out when text is drawn smaller than the texture (they did at 720p).
            if font.getNumPages() == 0:        # the font pool shares fonts; configure once
                font.setPixelsPerUnit(ppu)
                font.setPageSize(1024, 1024)
                font.setMinfilter(SamplerState.FT_linear_mipmap_linear)
                font.setMagfilter(SamplerState.FT_linear)
            return font
        return None           # falls back to Panda's default font

    def _init_hud(self):
        self.font_ui = self._load_font('Jura-Medium.ttf')
        self.font_light = self.font_ui                     # Jura Light was too thin to read small
        self.font_lore = self._load_font('Lora-Italic.ttf')
        self.font_title = self._load_font('Italiana-Regular.ttf', 80)
        # retire the old debug text
        for name in ('control_text', 'help_text', 'status_text', 'down_text'):
            node = getattr(self, name, None)
            if node is not None:
                node.hide()
        if self.font_lore:
            self.lore_text.setFont(self.font_lore)
        self.lore_text.setScale(LORE_SCALE)
        self.lore_text.setWordwrap(LORE_WRAP)
        self._place_lore()
        if self.font_ui:
            self.gesture_text.setFont(self.font_ui)
            for t in self._wheel_labels.values():
                t.setFont(self.font_ui)
        self.gesture_text.setScale(0.042)

        bl, br, tr = self.a2dBottomLeft, self.a2dBottomRight, self.a2dTopRight
        self.hud_vitals = bl.attachNewNode('vitals')
        self.hud_vitals.setTransparency(TransparencyAttrib.MAlpha)
        self.bar_life = _Bar(self.hud_vitals, 0.09, 0.235, 'life', LIFE, self.font_light)
        self.bar_breath = _Bar(self.hud_vitals, 0.09, 0.165, 'breath', BREATH, self.font_light)
        self.bar_heat = _Bar(self.hud_vitals, 0.09, 0.095, 'heat', HEAT, self.font_light)
        self.bar_glow = _Bar(self.hud_vitals, 0.09, 0.025, 'glow', INDIGO, self.font_light)    # Pass 59
        self.bar_glow.root.setAlphaScale(0.0)
        self.hud_bag = OnscreenText(text='', parent=bl, pos=(0.09, 0.315), align=TextNode.ALeft, scale=0.032,
                                    font=self.font_light, fg=(*INK_DAY, 0.0), mayChange=True)

        self.hud_indigo = br.attachNewNode('indigo')
        self.hud_indigo.setTransparency(TransparencyAttrib.MAlpha)
        self.bar_indigo = _Bar(self.hud_indigo, -0.09, 0.165, 'indigo', INDIGO, self.font_light, width=0.28,
                               align_right=True)
        self.hud_red = OnscreenText(text='', parent=br, pos=(-0.09, 0.095), align=TextNode.ARight, scale=0.034,
                                    font=self.font_light, fg=(*RUST, 0.0), mayChange=True)
        # Pass 53: fight stamina - a thin line under Indigo's life bar, and under the red one's line
        self.bar_indigo_st = _Bar(self.hud_indigo, -0.09, 0.150, '', INDIGO_PALE, self.font_light, width=0.28,
                                  align_right=True)
        self.bar_indigo_st.root.setSz(0.45)
        self.bar_red_st = _Bar(br, -0.09, 0.080, '', RUST, self.font_light, width=0.20, align_right=True)
        self.bar_red_st.root.setSz(0.45)
        self.bar_red_st.root.setAlphaScale(0.0)
        self.hud_gbag = OnscreenText(text='', parent=br, pos=(-0.09, 0.245), align=TextNode.ARight, scale=0.032,
                                     font=self.font_light, fg=(*INK_DAY, 0.0), mayChange=True)

        self.hud_day = OnscreenText(text='', parent=tr, pos=(-0.09, -0.115), align=TextNode.ARight, scale=0.062,
                                    font=self.font_title, fg=(*INK_DAY, 0.85), mayChange=True)
        self.hud_time = OnscreenText(text='', parent=tr, pos=(-0.09, -0.17), align=TextNode.ARight, scale=0.034,
                                     font=self.font_light, fg=(*INK_DAY, 0.7), mayChange=True)
        self.hud_saved = OnscreenText(text='', parent=tr, pos=(-0.09, -0.21), align=TextNode.ARight, scale=0.026,
                                      font=self.font_light, fg=(*INK_DAY, 0.0), mayChange=True)
        self.hud_arc = tr.attachNewNode('sun_arc')
        self.hud_arc.setPos(-0.44, 0, -0.14)
        ls = LineSegs('arc')
        ls.setThickness(1.2)
        ls.setColor(*INK_DAY, 0.45)
        for i in range(25):
            a = math.pi * i / 24
            (ls.moveTo if i == 0 else ls.drawTo)(math.cos(a) * 0.075, 0, math.sin(a) * 0.05)
        self.hud_arc.attachNewNode(ls.create())
        self.hud_arc.setTransparency(TransparencyAttrib.MAlpha)
        dot = CardMaker('dot')
        dot.setFrame(-0.009, 0.009, -0.009, 0.009)
        self.hud_sun = self.hud_arc.attachNewNode(dot.generate())

        self.hud_prompt = OnscreenText(text='', pos=(0.0, PROMPT_Y), align=TextNode.ACenter, scale=0.044,
                                       font=self.font_ui, fg=(*INK_DAY, 0.0), mayChange=True)
        cm = CardMaker('hold')
        cm.setFrame(-0.12, 0.12, 0, 0.004)
        self.hud_hold = self.aspect2d.attachNewNode(cm.generate())
        self.hud_hold.setPos(0, 0, PROMPT_Y - 0.030)
        self.hud_hold.setTransparency(TransparencyAttrib.MAlpha)
        self.hud_hold.setColor(*INK_DAY, 0.7)
        self.hud_hold.hide()
        self.hud_mode = OnscreenText(text='', pos=(0.0, 0.90), align=TextNode.ACenter, scale=0.034,
                                     font=self.font_light, fg=(*INK_DAY, 0.0), mayChange=True)
        self.hud_down = OnscreenText(text='', pos=(0.0, 0.50), align=TextNode.ACenter, scale=0.075,
                                     font=self.font_title, fg=(*INK_DAY, 0.0), mayChange=True)
        self.hud_down_sub = OnscreenText(text='', pos=(0.0, 0.42), align=TextNode.ACenter, scale=0.034,
                                         font=self.font_ui, fg=(*INK_DAY, 0.0), mayChange=True)
        self.hud_hint = OnscreenText(text=f'{controls.label(self.bindings, "controls_help")}  controls      '
                                          f'{controls.label(self.bindings, "craft")}  make      '
                                          f'{controls.label(self.bindings, "journal")}  journal',
                                     parent=self.a2dTopLeft, pos=(0.09, -0.10), align=TextNode.ALeft, scale=0.034,
                                     font=self.font_light, fg=(*INK_DAY, 0.8), mayChange=True)
        self._hud_t = 0.0
        self._alpha = {'glow_bar': 0.0, 'vitals': 1.0, 'indigo': 1.0, 'bag': 0.0, 'gbag': 0.0, 'prompt': 0.0, 'mode': 0.0,
                       'red': 0.0, 'saved': 0.0, 'down': 0.0}
        self._last_bag = self._last_gbag = ''
        self._last_mode = None
        self._vitals_seen = 0.0
        self._ink = INK_DAY
        self.panel = None
        self.panel_name = None
        self._panel_stack: list = []
        self._panel_sig = None
        self._menu_confirm_new = False
        self.bind_action('craft', self.toggle_panel, ['craft'])
        self.bind_action('journal', self.toggle_panel, ['journal'])
        self.bind_action('controls_help', self.toggle_panel, ['help'])
        self.bind_action('menu', self._on_menu_key)
        self.bind_action('sleep', self.request_sleep)
        self._update_hud(0.0)

    # ------------------------------------------------------------------ frame
    # Pass 45: messages sit at the bottom of the screen, below the player, growing upward
    def say(self, text: str, seconds: float = 4.0):
        super().say(text, seconds)
        self._place_lore()

    def _place_lore(self):
        tn = self.lore_text.textNode
        rows = max(1, tn.getNumRows()) if tn.getText() else 1
        line = tn.getLineHeight() * LORE_SCALE
        self.lore_text.setPos(0.0, LORE_BOTTOM_Y + (rows - 1) * line)

    def _update_survival_hud(self):
        # Pass 44: the old debug text HUD is hidden, so stop rebuilding it every frame
        if getattr(self, 'hud_vitals', None) is None:
            super()._update_survival_hud()

    def survival_step(self, dt: float):
        super().survival_step(dt)
        if getattr(self, 'hud_vitals', None) is not None:
            self._update_hud(dt)

    def _fade(self, key, target, dt, rate=2.5):
        a = self._alpha[key]
        a += max(-rate * dt, min(rate * dt, target - a))
        self._alpha[key] = a
        return a

    def _ink_now(self):
        night = self.is_night() if hasattr(self, 'is_night') else False
        return INK_NIGHT if night else INK_DAY

    def _update_hud(self, dt: float):
        self._hud_t += dt
        ink = self._ink_now()
        if ink != self._ink:
            self._ink = ink
            for bar in (self.bar_life, self.bar_breath, self.bar_heat, self.bar_indigo, self.bar_glow):
                bar.label.setFg((*ink, 1.0))
            self._sf(self.lore_text, (*ink, 0.0))
            self.hud_hold.setColor(*ink, 0.7)

        # ---- vitals: visible while anything needs attention
        life = self.human_health / K['HUMAN_MAX_HEALTH'] if self.human_alive else 0.0
        cap = self.stamina_cap() if hasattr(self, 'stamina_cap') else 100.0
        self.bar_life.set(life)
        self.bar_breath.set(self.stamina / 100.0)
        chill = getattr(self, 'chill', 0.0)
        cold = chill > self.heat                      # Pass 48: the heat bar is your temperature
        if cold != getattr(self, '_bar_cold', None):
            self._bar_cold = cold
            self.bar_heat.fill.setColor(*(COLD if cold else HEAT), 1.0)
        self.bar_heat.set((chill if cold else self.heat) / desert.HEAT_MAX)
        self._st(self.bar_breath.label, 'breath  ·  winded' if self.winded else 'breath')
        where = {'sun': '', 'shade': 'shade', 'shell': 'in a shell', 'riding': 'riding in the sun',
                 'riding shaded': 'riding, shaded'}.get(self.shelter_word, '')
        cooling = self.shelter_word in ('shade', 'shell', 'riding shaded') or self.sun_heat_factor() < 0.0
        if cold:
            warm = self.warm_beside_indigo() if hasattr(self, 'warm_beside_indigo') else False
            lit = self.glow_warming() if hasattr(self, 'glow_warming') else False       # Pass 59
            self._st(self.bar_heat.label, 'cold' + ('  ·  warming against Nyx' if warm else
                                                    "  ·  warming in Nyx's light" if lit else
                                                    '  ·  frozen' if chill >= 99.0 else ''))
        else:
            self._st(self.bar_heat.label, 'heat' + (f'  ·  {where}' if where else '')
                                        + ('  ·  cooling' if cooling and self.heat > 1.0 and not where else ''))
        charge = getattr(self, 'glow_charge', 0.0)                     # Pass 59: the glow you carry
        self.bar_glow.set(charge / 100.0)
        self.bar_glow.root.setAlphaScale(self._fade('glow_bar', 1.0 if charge > 0.0 else 0.0, dt, 2.0))
        self._st(self.bar_glow.label, 'glow  ·  stronger, tougher' if charge > 0.0 else 'glow')
        needs = (life < 0.999 or self.stamina < cap - 0.5 or self.stamina < 99.0 or self.heat > 12.0
                 or chill > 12.0 or not self.human_alive or charge > 0.0)
        if needs:
            self._vitals_seen = 3.0
        else:
            self._vitals_seen = max(0.0, self._vitals_seen - dt)
        a = self._fade('vitals', 1.0 if self._vitals_seen > 0.0 else 0.12, dt, 1.5)
        self.hud_vitals.setAlphaScale(a)

        # ---- bags: show briefly when they change
        bag = self._bag_text('human')
        if bag != self._last_bag:
            self._last_bag = bag
            self._alpha['bag'] = 1.0
            self._bag_hold = 4.0
        self._bag_hold = max(0.0, getattr(self, '_bag_hold', 0.0) - dt)
        self._st(self.hud_bag, bag)
        self._sf(self.hud_bag, (*ink, self._fade('bag', 0.85 if self._bag_hold > 0 else 0.0, dt, 1.0)))
        gbag = self._bag_text('giant')
        if gbag != self._last_gbag:
            self._last_gbag = gbag
            self._gbag_hold = 4.0
        self._gbag_hold = max(0.0, getattr(self, '_gbag_hold', 0.0) - dt)
        self._st(self.hud_gbag, gbag)
        self._sf(self.hud_gbag, (*ink, self._fade('gbag', 0.8 if self._gbag_hold > 0 else 0.0, dt, 1.0)))

        # ---- Indigo and the Red Giant
        self.bar_indigo.set(self.giant_health / K['GIANT_MAX_HEALTH'])
        word = self._companion_word()
        self._st(self.bar_indigo.label, f'nyx  ·  {word}')
        busy = word not in ('staying', 'following') or self.giant_health < K['GIANT_MAX_HEALTH']
        self.hud_indigo.setAlphaScale(self._fade('indigo', 0.95 if busy else 0.35, dt, 1.2))
        if hasattr(self, 'giant_stamina'):
            self.bar_indigo_st.set(self.giant_stamina / fight_max('giant'))
        red_d = self._human_red_distance()
        red_word = self.red_shell_word() or self._red_word()
        show_red = red_d < 220.0 and not (self.red_lurking or self.red_state == 'idle')   # Pass 54: by state
        if show_red:
            self._st(self.hud_red, f'crimson  ·  {red_word}  ·  {int(red_d)} m')
        red_a = self._fade('red', 0.95 if show_red else 0.0, dt, 2.0)
        self._sf(self.hud_red, (*RUST, red_a))
        if hasattr(self, 'red_stamina'):
            fighting = self.red_state in ('melee', 'knocked_out') or self.red_stamina < self.stamina_max('red') * 0.95
            self.bar_red_st.set(self.red_stamina / fight_max('red'))
            self.bar_red_st.root.setAlphaScale(red_a if fighting else 0.0)

        # ---- day, time of day, sun arc
        self._st(self.hud_day, f'day {self.day}')
        self._st(self.hud_time, self.time_words())
        self._sf(self.hud_day, (*ink, 0.85))
        self._sf(self.hud_time, (*ink, 0.7))
        h = self.hour
        if 6.0 <= h <= 18.0:
            k = (h - 6.0) / 12.0
            self.hud_sun.setColor(*HEAT, 1.0)
        else:
            k = ((h - 18.0) % 24.0) / 12.0
            self.hud_sun.setColor(*INK_NIGHT, 1.0)
        a = math.pi * (1.0 - k)
        self.hud_sun.setPos(math.cos(a) * 0.075, 0, math.sin(a) * 0.05)
        self._sf(self.hud_saved, (*ink, self._fade('saved', 0.0, dt, 0.5)))

        # ---- the one prompt that matters here
        prompt, progress = self._prompt_and_progress()
        if prompt:
            self._st(self.hud_prompt, prompt)
        self._sf(self.hud_prompt, (*ink, self._fade('prompt', 0.9 if prompt else 0.0, dt, 4.0)))
        if progress > 0.0:
            self.hud_hold.show()
            self.hud_hold.setSx(progress)
        else:
            self.hud_hold.hide()

        # ---- who you are
        mode = 'you are Nyx' if self.controlled_name == 'giant' else ('riding Nyx' if self.carried else '')
        if mode != self._last_mode:
            self._last_mode = mode
            self._mode_hold = 3.0
            if mode:
                self._st(self.hud_mode, mode)
        self._mode_hold = max(0.0, getattr(self, '_mode_hold', 0.0) - dt)
        target = (0.9 if self._mode_hold > 0 else 0.35) if mode else 0.0
        self._sf(self.hud_mode, (*ink, self._fade('mode', target, dt, 1.5)))

        # ---- downed
        if not self.human_alive:
            self._st(self.hud_down, 'you fall to the sand')
            self._st(self.hud_down_sub, f'{controls.label(self.bindings, "retry")}   wake at camp'
                                      if getattr(self, 'camp_shell', None) is not None else
                                      f'{controls.label(self.bindings, "retry")}   wake')
        da = self._fade('down', 1.0 if not self.human_alive else 0.0, dt, 1.0)
        self._sf(self.hud_down, (*ink, da))
        self._sf(self.hud_down_sub, (*ink, da * 0.9))

        # ---- first-minutes hint
        self._sf(self.hud_hint, (*ink, max(0.0, 0.8 - max(0.0, self._hud_t - HINT_SECONDS) * 0.3)))
        if self.panel_name in ('craft', 'journal') and int(self._hud_t * 2) != int((self._hud_t - dt) * 2):
            sig = self._panel_signature()
            if sig != self._panel_sig:            # Pass 44 (B10): rebuild only when the content changed
                self._rebuild_panel()

    # OnscreenText rebuilds its geometry on every setText / setFg, so only touch it on change.
    def _st(self, node, text):
        if getattr(node, '_last_text', None) != text:
            node._last_text = text
            node.setText(text)

    def _sf(self, node, colour):
        c = tuple(round(v, 3) for v in colour)
        if getattr(node, '_last_fg', None) != c:
            node._last_fg = c
            node.setFg(c)

    def _bag_text(self, owner):
        bag = self.bag(owner)
        items = [f'{bag[i]} {desert.ITEM_LABEL.get(i, i)}' for i in list(desert.ITEM_ORDER) + ['seed'] if bag[i]]
        cap = desert.HUMAN_BAG if owner == 'human' else desert.GIANT_BAG
        who = 'your bag' if owner == 'human' else "Nyx's bag"
        return f'{who}  {self.bag_count(owner)}/{cap}' + ('   ' + '  ·  '.join(items) if items else '')

    def flash_saved(self):
        if getattr(self, 'hud_saved', None) is not None:
            self.hud_saved.setText('saved')
            self._alpha['saved'] = 0.8

    def _prompt_and_progress(self):
        b = self.bindings
        if not self.human_alive or self.panel is not None:
            return '', 0.0
        use = controls.label(b, 'use')
        if self.controlled_name == 'giant':
            if not self.giant_alive:
                return '', 0.0
            if self.giant_held_shell is not None:
                return f'{use}   set the shell down', 0.0
            if self._combat_alive('red') and self._giant_flat_distance() <= 30.0:
                # Pass 58: fighting as Indigo
                return (f'left click · {controls.label(b, "punch")}   punch      '
                        f'hold, then let go   hammer blow'), 0.0
            if self.shells.nearest(self.giant.getPos(self.render), desert.GIANT_SHELL_REACH) is not None:
                return f'{use}   lift the shell', 0.0
            if self.giant_smash_target() is not None:
                return f'{controls.label(b, "punch")}   smash the branch', 0.0
            return '', 0.0
        if self.carried:
            if getattr(self, 'gleebs_state', None) == 'waiting' and self._e_target()[0] == 'leave':
                h = self.e_hold                              # Pass 61: ride Nyx into Gleebs' light
                progress = min(1.0, h['t'] / desert.HOLD_TIMES['leave']) if h['kind'] == 'leave' else 0.0
                return f'hold {use}   {self.place_prompt("leave", None)}', progress
            ok, _ = self.can_sleep()
            sleep = f'      {controls.label(b, "sleep")}   sleep' if ok else ''
            return (f'{controls.label(b, "move_forward")}   walk where you look      '
                    f'{controls.label(b, "lift")}   set me down{sleep}'), 0.0
        if self.hidden_shell is not None:
            ok, _ = self.can_sleep()
            sleep = f'      {controls.label(b, "sleep")}   sleep' if ok else ''
            return f'walk out through the mouth{sleep}      {controls.label(b, "whistle")}   whistle', 0.0
        kind, target = self._e_target()
        words = {'hide': 'step into the shell', 'dig': 'dig', 'smash': 'smash the branch',
                 'patch': 'patch the shell  (3 scraps, 1 resin)', 'plant': 'plant a seed'}
        text = words.get(kind, '')
        if not text and kind and hasattr(self, 'place_prompt'):
            text = self.place_prompt(kind, target)          # Pass 46: search / drink / rest / uproot
        if kind == 'study':
            text = f'study the {target.kind}'
        progress = 0.0
        if kind in desert.HOLD_TIMES:
            text = f'hold {use}   {text}'
            h = self.e_hold
            if h['t'] > 0.0 and h['kind'] == kind:
                progress = min(1.0, h['t'] / desert.HOLD_TIMES[kind])
        elif text:
            text = f'{use}   {text}'
        pz = self.poison_prompt() if hasattr(self, 'poison_prompt') else None
        if pz is not None:                                   # Pass 49: X, its own key
            text = (text + '      ' if text else '') + f'{controls.label(b, "poison")}   {pz[0]}'
            progress = max(progress, pz[1])
        chill = getattr(self, 'chill', 0.0)
        wants_food = self.heat >= 45.0 or self.stamina < 40.0 or self.human_health < 60.0 or chill >= 50.0
        sips = getattr(self, 'water_sips', 0) and self.heat >= 45.0       # sips only help when hot
        has_food = self.pooled_count('pod') or self.pooled_count('gourd') or sips or self.pooled_count('scraps')
        if wants_food and has_food:
            text = (text + '      ' if text else '') + f'{controls.label(b, "eat")}   eat'
        if not text and self.is_night() and self.can_sleep()[0]:        # Pass 48: beside Indigo
            text = f'{controls.label(b, "sleep")}   sleep curled against Nyx'
        return text, progress

    # ------------------------------------------------------------------ panels
    # Pass 50: panels open from "hub" panels (Esc menu, title, settings) stack on them and
    # return to them when closed; any stacked or hub panel keeps the world paused.
    HUB_PANELS = ('menu', 'title', 'settings', 'keys')
    PAUSING_PANELS = ('menu', 'title', 'settings', 'keys', 'ending')

    def _on_menu_key(self):
        if getattr(self, '_capturing_key', None):
            return                                      # Esc cancels a key capture instead
        if self.panel_name == 'title' and not self._panel_stack:
            return                                      # the title stays until you choose
        if self.panel is not None and self.panel_name != 'menu':
            self.close_panel()
        else:
            self.toggle_panel('menu')

    def toggle_panel(self, name):
        if self.panel_name == name:
            self.close_panel()
            return
        if self.panel_name == 'title' and name in ('craft', 'journal', 'help', 'menu'):
            return                                      # nothing opens over the title but its own pages
        if self.panel_name in self.HUB_PANELS and name != self.panel_name:
            self._panel_stack.append(self.panel_name)
        self._destroy_panel()
        self.panel_name = name
        self._menu_confirm_new = False
        self.paused = name in self.PAUSING_PANELS or bool(self._panel_stack)
        self._rebuild_panel()

    def close_panel(self):
        self._destroy_panel()
        self.panel_name = None
        if self._panel_stack:
            self.panel_name = self._panel_stack.pop()
            self.paused = True
            self._rebuild_panel()
        else:
            self.paused = False
            if hasattr(self, 'on_panels_closed'):
                self.on_panels_closed()

    def _destroy_panel(self):
        if self.panel is not None:
            self.panel.destroy()
        self.panel = None
        self._panel_sig = None

    def _panel_signature(self):
        name = self.panel_name
        if name == 'craft':
            from journey import RECIPES
            items = sorted({i for r in RECIPES for i in r[2]})
            return (name, tuple(self.pooled_count(i) for i in items), tuple(sorted(self.upgrades)))
        if name == 'journal':
            lines, lore = self.journal_lines()
            atlas = self.atlas_lines() if self.journal_page == 'places' and hasattr(self, 'atlas_lines') else None
            notes = self.notes_lines() if self.journal_page == 'notes' and hasattr(self, 'notes_lines') else None
            return (name, self.journal_page, tuple(lines), tuple(lore), repr(atlas), repr(notes))
        return (name, self._menu_confirm_new)

    def _card(self, title, width=0.66, height=0.46):
        frame = DirectFrame(frameColor=(*PAPER, 0.985), frameSize=(-width, width, -height, height), pos=(0, 0, 0.02),
                            relief=DGG.FLAT)
        ls = LineSegs('edge')
        ls.setThickness(1.0)
        ls.setColor(*INK_DAY, 0.35)
        w, h = width - 0.02, height - 0.02
        ls.moveTo(-w, 0, -h)
        for x, z in ((w, -h), (w, h), (-w, h), (-w, -h)):
            ls.drawTo(x, 0, z)
        NodePath(ls.create()).reparentTo(frame)
        OnscreenText(text=title, parent=frame, pos=(-width + 0.07, height - 0.11), align=TextNode.ALeft, scale=0.07,
                     font=self.font_title, fg=(*INK_DAY, 0.95))
        return frame

    journal_page = 'journal'

    def set_journal_page(self, page: str):
        self.journal_page = page
        self._rebuild_panel()

    def _journal_card(self):
        p = self._card('journal', width=0.72, height=0.62)
        for label, x in (('journal', 0.14), ('places', 0.36), ('notes', 0.56)):   # Pass 51 / 61: three pages
            b = self._button(p, label, x, 0.50, self.set_journal_page, self.journal_page != label, [label])
            b.setScale(0.85)
        return p

    def _text(self, parent, text, x, y, scale=0.036, font=None, alpha=0.95, colour=INK_DAY, align=TextNode.ALeft,
              wrap=None):
        return OnscreenText(text=text, parent=parent, pos=(x, y), align=align, scale=scale, font=font or self.font_light,
                            fg=(*colour, alpha), wordwrap=wrap, mayChange=True)

    def _button(self, parent, text, x, y, command, enabled=True, extra=None):
        fg = (*INK_DAY, 0.95) if enabled else (*INK_DAY, 0.3)
        b = DirectButton(parent=parent, text=text, text_font=self.font_ui, text_scale=0.042, text_align=TextNode.ACenter,
                         text_fg=fg, text2_fg=(*RUST, 1.0) if enabled else fg, relief=None, pos=(x, 0, y),
                         command=command if enabled else None, extraArgs=extra or [], pressEffect=1)
        b.setPythonTag('label', text)            # the words, for checks and tools
        return b

    def _rebuild_panel(self):
        name = self.panel_name
        if name is None:
            return
        if self.panel is not None:
            self.panel.destroy()
        self._panel_sig = self._panel_signature()
        b = self.bindings
        if name == 'craft':
            p = self._card('make')
            from journey import RECIPES
            y = 0.23
            for rid, title, cost, effect in RECIPES:
                made = rid in self.upgrades
                parts = []
                for item, n in cost.items():
                    have = self.pooled_count(item)
                    parts.append(f'{min(have, n)}/{n} {desert.ITEM_LABEL.get(item, item)}')
                self._text(p, title, -0.58, y, 0.044, self.font_ui)
                self._text(p, effect, -0.58, y - 0.052, 0.032, alpha=0.8)
                self._text(p, '    '.join(parts), -0.58, y - 0.097, 0.030, alpha=0.65)
                if made:
                    self._text(p, 'made', 0.50, y - 0.03, 0.034, self.font_ui, alpha=0.5, align=TextNode.ACenter)
                else:
                    self._button(p, 'make', 0.50, y - 0.03, self._craft_clicked, self.can_craft(rid), [rid])
                y -= 0.17
            self._text(p, f'uses your bag and Nyx\'s when it is beside you     {controls.label(b, "craft")} / esc  close',
                       -0.58, -0.43, 0.028, alpha=0.6)
        elif name == 'journal' and self.journal_page == 'places' and hasattr(self, 'atlas_lines'):
            p = self._journal_card()
            rows, rumours = self.atlas_lines()
            y = 0.40
            for tier, count, words in rows:                   # Pass 51: every kind, '?' for the unknown
                self._text(p, f'{tier}   {count}', -0.64, y, 0.036, self.font_ui)
                y -= 0.050
                line = '  ·  '.join(words)
                self._text(p, line, -0.60, y, 0.031, alpha=0.8, wrap=40)
                y -= 0.047 * (1 + len(line) // 70) + 0.022
            y -= 0.02
            self._text(p, 'stories heard', -0.64, y, 0.036, self.font_ui)
            y -= 0.052
            for text in (rumours or ['(no one has told you of anything far away yet)']):
                self._text(p, text, -0.60, y, 0.031, self.font_lore, alpha=0.85, wrap=40)
                y -= 0.047 * (1 + len(text) // 64) + 0.02
        elif name == 'journal' and self.journal_page == 'notes' and hasattr(self, 'notes_lines'):
            p = self._journal_card()                          # Pass 61: the etchings you have read
            head, texts = self.notes_lines()
            self._text(p, head, -0.64, 0.40, 0.036, self.font_ui)
            y = 0.33
            if not texts:
                self._text(p, '(somewhere out in the sand, old stones are cut with glowing marks. '
                              'at night you can see them from far off.)', -0.64, y, 0.032, self.font_lore,
                           alpha=0.75, wrap=40)
            # as many as fit, the farthest-out (latest in the story) kept when they do not all fit
            room, keep = y + 0.56, []
            for text in reversed(texts):
                h = 0.044 * (1 + len(text) // 66) + 0.026
                if h > room:
                    break
                keep.insert(0, (text, h))
                room -= h
            for text, h in keep:
                self._text(p, text, -0.64, y, 0.032, self.font_lore, alpha=0.88, wrap=40)
                y -= h
        elif name == 'journal':
            p = self._journal_card()
            lines, lore = self.journal_lines()
            y = 0.40
            for line in (ln for ln in lines if ln):
                self._text(p, line, -0.64, y, 0.034)
                y -= 0.056
            y -= 0.03
            # Pass 49: only as many recent entries as fit on the page (newest kept)
            entries = list(lore or ['(the desert has not spoken to you yet)'])
            room, keep = y + 0.54, []
            for text in reversed(entries):
                h = 0.047 * (1 + len(text) // 62) + 0.028
                if h > room:
                    break
                keep.insert(0, (text, h))
                room -= h
            for text, h in keep:
                self._text(p, text, -0.64, y, 0.034, self.font_lore, alpha=0.85, wrap=37)
                y -= h
        elif name == 'help':
            p = self._card('controls', width=1.02, height=0.60)
            L = lambda a: controls.label(b, a)          # noqa: E731
            left = [('move', f'{L("move_forward")} {L("move_left")} {L("move_back")} {L("move_right")}'),
                    ('jog / sprint', f'{L("jog")}  /  {L("jog")} + {L("sprint_with_jog")}'),
                    ('look', 'hold right mouse  ·  arrows'), ('jump', L('jump')), ('crouch', L('crouch')),
                    ('use  (tap / hold)', L('use')), ('eat  (pods · gourds · scraps)', L('eat')),
                    ('sleep  (shell · by Nyx)', L('sleep')),
                    ('give / take', f'{L("give_to_giant")} / {L("take_from_giant")}'),
                    ('be Nyx / be Orbit', L('switch_character'))]
            right = [('come', L('come')), ('stay', L('stay')), ('lift me / set me down', L('lift')),
                     ('go there', f'{L("go_there")}  ·  left click riding'), ('shade me', L('shade')),
                     ('whistle', L('whistle')), ('gesture wheel', 'hold middle mouse'),
                     ('Nyx: punch  (hold: hammer)', f'left click · {L("punch")}'),     # Pass 58
                     ('Nyx: kneel', L('kneel')),
                     ("take Nyx's glow (night)", f'hold {L("use")} beside it'),       # Pass 59
                     ('poison a branch', L('poison')),
                     ('make / journal', f'{L("craft")} / {L("journal")}'), ('music · save · menu', f'{L("music")} · {L("quick_save")} · esc')]
            for col, x in ((left, -0.92), (right, 0.08)):
                y = 0.36
                for what, key in col:
                    self._text(p, what, x, y, 0.032, alpha=0.7)
                    self._text(p, key, x + 0.52, y, 0.032, self.font_ui)
                    y -= 0.066
            self._text(p, 'change any key in  Esc  >  settings  >  keys', -0.92, -0.52, 0.028, alpha=0.55)
        elif name == 'ending':                      # Pass 61: Nyx and Orbit leave REDACTED with Gleebs
            p = self._card(self.ending_title() if hasattr(self, 'ending_title') else 'the end', width=0.80, height=0.52)
            story = self.ending_story() if hasattr(self, 'ending_story') else ()
            y = 0.30
            for line in story[:2]:
                self._text(p, line, -0.70, y, 0.038, self.font_lore, alpha=0.9, wrap=36)
                y -= 0.047 * (1 + len(line) // 58) + 0.035
            y -= 0.01
            for line in self.ending_lines():
                self._text(p, line, -0.70, y, 0.032)
                y -= 0.056
            for line in story[2:]:
                self._text(p, line, -0.70, y - 0.02, 0.036, self.font_lore, alpha=0.85)
            self._button(p, 'new journey', -0.22, -0.42, self._ending_new)
            self._button(p, 'quit', 0.22, -0.42, self.userExit)
        else:   # menu
            p = self._card('paused', width=0.42, height=0.46)
            y = 0.24
            items = [('resume', self.close_panel, []), ('save', self._menu_save, []),
                     ('settings', self.toggle_panel, ['settings']),
                     ('controls', self.toggle_panel, ['help']),
                     ('new journey' if not self._menu_confirm_new else 'really start over?', self._menu_new, []),
                     ('save and quit', self.userExit, [])]
            for label, cmd, extra in items:
                self._button(p, label, 0.0, y, cmd, True, extra)
                y -= 0.10
        self.panel = p

    def _craft_clicked(self, rid):
        self.craft(rid)
        self._rebuild_panel()

    def _menu_save(self):
        if self.save_game('quick save'):
            self.say('saved', 1.2)
        else:
            self.say('nothing to save yet', 1.2)

    def _ending_new(self):
        """Pass 61: the journey is over - a new one at once (no 'really?' step)."""
        self.new_journey_file()
        self.persist = False
        if hasattr(self, 'restart_new_journey'):
            self.restart_new_journey()
            return
        self.say('a new journey begins next time you launch', 3.0)

    def _menu_new(self):
        if not self._menu_confirm_new:
            self._menu_confirm_new = True
            self._rebuild_panel()
            return
        self.new_journey_file()
        self.persist = False                 # do not save this journey again on quit
        if hasattr(self, 'restart_new_journey'):
            self.restart_new_journey()       # Pass 50: begin it now
            return
        self.say('a new journey begins next time you launch', 3.0)
        self.close_panel()
