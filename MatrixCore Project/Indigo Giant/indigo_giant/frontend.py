"""Pass 50 — first launch: the title screen, settings and key rebinding.

TITLE     continue (or begin), new journey, settings, quit - over the living desert, the
          camera drifting slowly around Indigo. Nothing moves in the world until you choose.
SETTINGS  (from the title or Esc)
          display   resolution (native / 3840x2160 / 2560x1440 / 1920x1080 / 1600x900 / 1280x720),
                    fullscreen, vsync, anti-aliasing  - size and fullscreen change at once;
                    vsync and anti-aliasing on the next launch
          sound     master, music, effects, ambience
          play      mouse sensitivity, invert mouse Y, first-dawn hints
          keys      every action: click it, press the new key (Esc cancels). A key already in
                    use swaps with it. Saved beside the journey (controls.json in the save folder).
Settings are saved in settings.json in the save folder.
"""
from __future__ import annotations

import subprocess
import sys

from panda3d.core import ClockObject, WindowProperties

from . import controls
from . import settings as settings_mod
from . import paths                 # Pass 62: where the game files are

KEY_ACTIONS = (   # (action, words) - the order the keys page lists them
    ('move_forward', 'walk forward'), ('move_back', 'walk back'), ('move_left', 'walk left'),
    ('move_right', 'walk right'), ('jog', 'jog'), ('sprint_with_jog', 'sprint (with jog)'), ('crouch', 'crouch'),
    ('jump', 'jump'), ('use', 'use / hold to dig, study...'), ('eat', 'eat / drink'), ('sleep', 'sleep'),
    ('poison', 'poison a branch'), ('give_to_giant', 'give to Nyx'), ('take_from_giant', 'take from Nyx'),
    ('come', 'come'), ('stay', 'stay'), ('lift', 'lift me / set me down'), ('go_there', 'go there'),
    ('shade', 'shade me'), ('whistle', 'whistle'), ('switch_character', 'be Nyx / be Orbit'),
    ('punch', 'Nyx: punch (hold: hammer blow)'), ('kneel', 'Nyx: kneel'), ('camera_reset', 'reset camera'),
    ('camera_left', 'look left'), ('camera_right', 'look right'), ('camera_up', 'look up'),
    ('camera_down', 'look down'), ('craft', 'make'), ('journal', 'journal'), ('controls_help', 'controls'),
    ('retry', 'wake after falling'), ('music', 'music on / off'), ('quick_save', 'quick save'), ('fps', 'frame rate'),
)
NO_BIND = {'escape', 'mouse1', 'mouse2', 'mouse3', 'wheel_up', 'wheel_down', 'mouse1-up', 'mouse3-up'}
MODIFIER_NAMES = {'lshift': 'shift', 'rshift': 'shift', 'lcontrol': 'control', 'rcontrol': 'control',
                  'lalt': 'alt', 'ralt': 'alt'}
VOLUME_STEP = 0.1
SENS_STEPS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)
TITLE_ORBIT_DEG_PER_S = 3.0


class FrontendMixin:
    _capturing_key = None
    _title_hidden = None

    def _init_frontend(self):
        self.apply_sound_settings()
        self._keys_page = 0
        if self.show_title:
            self.open_title()

    # ------------------------------------------------------------ title
    def open_title(self):
        self._title_hidden = [np_ for np_ in self.aspect2d.getChildren() if not np_.isHidden()]
        for np_ in self._title_hidden:
            np_.hide()
        self.toggle_panel('title')
        self.taskMgr.add(self._title_task, 'title_orbit', sort=48)

    def _title_task(self, task):
        if self.panel_name not in ('title',) and not (self._panel_stack and self._panel_stack[0] == 'title'):
            return task.done
        dt = min(ClockObject.getGlobalClock().getDt(), 0.05)
        self.heading += TITLE_ORBIT_DEG_PER_S * dt
        self.cam_target = self._controlled_focus()
        self._place_camera(immediate=False, dt=dt)
        return task.cont

    def leave_title(self):
        self._panel_stack.clear()
        self.close_panel()
        for np_ in self._title_hidden or []:
            np_.show()
        self._title_hidden = None
        self._snap_camera_to_controlled(immediate=True)

    def restart_new_journey(self):
        """Back up the old journey and start a fresh one (a new launch with --new)."""
        self.persist = False
        exe = sys.executable
        args = [exe, '--new'] if getattr(sys, 'frozen', False) else [exe, str(paths.MAIN), '--new']
        try:
            subprocess.Popen(args, cwd=str(paths.ROOT))
        except OSError as exc:
            print(f'[frontend] could not relaunch: {exc}')
            self.say('a new journey begins next time you launch', 3.0)
            return
        self.finalizeExit()

    def _title_new(self):
        if not self._menu_confirm_new:
            self._menu_confirm_new = True
            self._rebuild_panel()
            return
        if hasattr(self, 'new_journey_file'):
            self.new_journey_file()
        self.restart_new_journey()

    # ------------------------------------------------------------ settings
    def save_settings(self):
        if self.persist:
            settings_mod.save(self.save_dir, self.settings)

    def apply_sound_settings(self):
        audio = getattr(self, 'audio', None)
        if audio is not None:
            for k in ('master', 'music', 'sfx', 'ambience'):
                audio.settings[k] = self.settings[k]

    def apply_display_settings(self):
        if self.offscreen or self.win is None:
            return
        w, h = settings_mod.window_size(self.settings)
        wp = WindowProperties()
        wp.setSize(w, h)
        wp.setFullscreen(bool(self.settings['fullscreen']))
        self.win.requestProperties(wp)

    def change_setting(self, key, direction):
        s = self.settings
        if key == 'resolution':
            opts = settings_mod.RESOLUTIONS
            s[key] = opts[(opts.index(s[key]) + direction) % len(opts)]
            self.apply_display_settings()
        elif key in ('fullscreen', 'vsync', 'invert_y', 'hints'):
            s[key] = not s[key]
            if key == 'fullscreen':
                self.apply_display_settings()
        elif key == 'msaa':
            opts = settings_mod.MSAA_STEPS
            s[key] = opts[(opts.index(s[key]) + direction) % len(opts)]
        elif key in ('master', 'music', 'sfx', 'ambience'):
            s[key] = round(min(1.0, max(0.0, s[key] + VOLUME_STEP * direction)), 2)
            self.apply_sound_settings()
        elif key == 'mouse_sensitivity':
            i = min(range(len(SENS_STEPS)), key=lambda k: abs(SENS_STEPS[k] - s[key]))
            s[key] = SENS_STEPS[max(0, min(len(SENS_STEPS) - 1, i + direction))]
        self.save_settings()
        self._rebuild_panel()

    def setting_words(self, key) -> str:
        v = self.settings[key]
        if key == 'resolution':
            if v == 'native':
                w, h = settings_mod.window_size(dict(self.settings, fullscreen=True))
                return f'native  ({w} x {h})'
            return v.replace('x', ' x ')
        if isinstance(v, bool):
            return 'on' if v else 'off'
        if key == 'msaa':
            return 'off' if v == 0 else f'{v}x'
        if key == 'mouse_sensitivity':
            return f'{v:g}x'
        return f'{int(round(v * 100))}%'

    # ------------------------------------------------------------ keys
    def bindings_to_save(self) -> dict:
        """Pass 63: while hosted, TAB was lent to HoloVerse for the session; what is saved is
        what the keys are outside HoloVerse."""
        out = dict(self.bindings)
        for action, (original, lent_as) in getattr(self, '_hosted_lent_keys', {}).items():
            if out.get(action) == lent_as:
                out[action] = original
        return out

    def start_key_capture(self, action):
        self._capturing_key = action
        if self.buttonThrowers:
            self._capture_prev_event = self.buttonThrowers[0].node().getButtonDownEvent()
            self.buttonThrowers[0].node().setButtonDownEvent('indigo-capture-key')
        self.accept('indigo-capture-key', self._captured_key)
        self._rebuild_panel()

    def _stop_capture(self):
        self._capturing_key = None
        self._capture_end_frame = ClockObject.getGlobalClock().getFrameCount()
        if self.buttonThrowers:
            self.buttonThrowers[0].node().setButtonDownEvent(getattr(self, '_capture_prev_event', ''))
        self.ignore('indigo-capture-key')

    def _captured_key(self, key):
        action = self._capturing_key
        if action is None:
            return
        if key == 'escape':
            self._stop_capture()
            self._rebuild_panel()
            return
        if key in NO_BIND or key.startswith('mouse') or key.startswith('wheel'):
            return                                   # keep waiting for a keyboard key
        if key == 'tab' and self.hosted:
            self.say('TAB belongs to HoloVerse (it takes you home)', 2.0)
            return
        key = MODIFIER_NAMES.get(key, key)           # left/right Shift, Ctrl, Alt -> the names the game binds
        self._stop_capture()
        self.assign_key(action, key)

    def assign_key(self, action, key):
        """Bind `action` to `key`; an action already on that key takes the old one (a swap)."""
        old = self.bindings[action]
        other = next((a for a, k in self.bindings.items() if k == key and a != action), None)
        if other == 'menu':
            self.say('Esc stays the menu key', 2.0)
            self._rebuild_panel()
            return
        if other is not None:
            self.rebind(other, '__swap__')
        self.rebind(action, key)
        if other is not None:
            self.rebind(other, old)
        if self.persist:
            controls.save(self.bindings_to_save(), self.save_dir)
        self._rebuild_panel()

    def reset_keys(self):
        for action, key in controls.DEFAULT_BINDINGS.items():
            if self.bindings.get(action) != key:
                self.rebind(action, '__reset_' + action)
        for action, key in controls.DEFAULT_BINDINGS.items():
            if self.bindings.get(action) != key:
                self.rebind(action, key)
        if self.hosted:
            for action, (_original, lent_as) in self._hosted_key_rules().items():
                self.rebind(action, lent_as)
        if self.persist:
            controls.save(self.bindings_to_save(), self.save_dir)
        self._rebuild_panel()

    # ------------------------------------------------------------ panels
    def _panel_signature(self):
        if self.panel_name in ('title', 'settings', 'keys'):
            return (self.panel_name, self._menu_confirm_new, self._capturing_key)
        return super()._panel_signature()

    def _rebuild_panel(self):
        name = self.panel_name
        if name not in ('title', 'settings', 'keys'):
            super()._rebuild_panel()
            return
        if self.panel is not None:
            self.panel.destroy()
        self._panel_sig = self._panel_signature()
        if name == 'title':
            p = self._build_title()
        elif name == 'settings':
            p = self._build_settings()
        else:
            p = self._build_keys()
        self.panel = p

    def _build_title(self):
        """A soft paper column on the left, so the words never sit on the player or the giants."""
        from direct.gui.DirectGui import DirectFrame
        from .hud import PAPER
        ar = self.getAspectRatio() if self.win is not None else 16 / 9
        left = -ar
        p = DirectFrame(frameColor=(0, 0, 0, 0), frameSize=(-ar, ar, -1, 1))
        DirectFrame(parent=p, frameColor=(*PAPER, 0.72), frameSize=(left, left + 1.05, -1, 1))
        x = left + 0.52
        self._text(p, 'the indigo giant', x, 0.46, 0.12, self.font_title, 0.95, align=self._align_center())
        self._text(p, 'a journey across the pale desert', x, 0.36, 0.042, self.font_lore, 0.8,
                   align=self._align_center())
        has_save = bool(getattr(self, 'loaded_from_save', False))
        items = [(f'continue  ·  day {self.day}' if has_save else 'begin', self.leave_title, [])]
        if has_save:
            items.append(('new journey' if not self._menu_confirm_new else 'really start over?', self._title_new, []))
        items += [('settings', self.toggle_panel, ['settings']), (self.quit_words(), self.userExit, [])]
        y = 0.06
        for label, cmd, extra in items:
            self._button(p, label, x, y, cmd, True, extra).setScale(1.45)
            y -= 0.14
        return p

    def _align_center(self):
        from panda3d.core import TextNode
        return TextNode.ACenter

    def _build_settings(self):
        p = self._card('settings', width=0.80, height=0.66)
        rows = [('display', None), ('resolution', 'resolution'), ('fullscreen', 'fullscreen'),
                ('vsync  (next launch)', 'vsync'), ('anti-aliasing  (next launch)', 'msaa'),
                ('sound', None), ('master', 'master'), ('music', 'music'), ('effects', 'sfx'), ('ambience', 'ambience'),
                ('play', None), ('mouse sensitivity', 'mouse_sensitivity'), ('invert mouse y', 'invert_y'),
                ('first-dawn hints', 'hints')]
        y = 0.46
        for label, key in rows:
            if key is None:
                self._text(p, label, -0.72, y, 0.036, self.font_title, 0.9)
                y -= 0.068
                continue
            self._text(p, label, -0.66, y, 0.033, alpha=0.75)
            if self.hosted and key in ('resolution', 'fullscreen', 'vsync', 'msaa'):
                # Pass 63: inside HoloVerse the window is HoloVerse's
                self._text(p, 'set by HoloVerse', 0.38, y, 0.030, self.font_ui, alpha=0.5, align=self._align_center())
                y -= 0.06
                continue
            self._button(p, '<', 0.12, y + 0.005, self.change_setting, True, [key, -1])
            self._text(p, self.setting_words(key), 0.38, y, 0.034, self.font_ui, align=self._align_center())
            self._button(p, '>', 0.64, y + 0.005, self.change_setting, True, [key, 1])
            y -= 0.06
        self._button(p, 'keys ...', -0.40, -0.58, self.toggle_panel, True, ['keys'])
        self._button(p, 'back', 0.40, -0.58, self.close_panel)
        return p

    def _build_keys(self):
        p = self._card('keys', width=1.10, height=0.68)
        half = (len(KEY_ACTIONS) + 1) // 2
        for col, (x, chunk) in enumerate(((-1.00, KEY_ACTIONS[:half]), (0.08, KEY_ACTIONS[half:]))):
            y = 0.50
            for action, words in chunk:
                capturing = self._capturing_key == action
                self._text(p, words, x, y, 0.030, alpha=0.75)
                key = 'press a key ...' if capturing else controls.label(self.bindings, action)
                self._button(p, key, x + 0.74, y + 0.004, self.start_key_capture, not self._capturing_key or capturing,
                             [action]).setScale(0.8)
                y -= 0.056
        hint = ('press the new key  ·  Esc cancels' if self._capturing_key else
                'click a key to change it  ·  a key already in use swaps places')
        self._text(p, hint, -1.00, -0.58, 0.028, alpha=0.6)
        self._button(p, 'defaults', 0.30, -0.58, self.reset_keys, not self._capturing_key)
        self._button(p, 'back', 0.80, -0.58, self.close_panel, not self._capturing_key)
        return p
