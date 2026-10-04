"""Pass 63 - The Indigo Giant as a HoloVerse dimension (same window, no second ShowBase).

In the lore, HoloVerse is the present and the dimensions are archives of the past that Gleebs
brought with him. The Indigo Giant is the archive of Nyx and Orbit on the dying world REDACTED.

Standalone (main.py, the Lab, GX Launcher) nothing here is used. When HoloVerse mounts the
game through holoverse_native_adapter.py, the game is built with host=<HoloVerse app>:

  - It borrows the host's window, camera, lens, task manager, loader and 2-D layers. Only the
    names ShowBase itself defines are borrowed (read from ShowBase's source), so a lazily
    set game attribute can never pick up an unrelated HoloVerse attribute of the same name.
  - Its world lives under its own node on host.render. Lights, the sketch shader, fog and
    shadows are set on that node, so nothing leaks onto HoloVerse's scene.
  - The window belongs to HoloVerse: resolution, fullscreen, vsync and anti-aliasing are not
    touched, and no PRC data is loaded.
  - TAB belongs to HoloVerse (it always returns home). "be Nyx / be Orbit" moves to V while
    hosted, only for that session; your saved keys are unchanged.
  - Quit becomes "return to HoloVerse". A new journey restarts inside the same window.
  - shutdown_for_holoverse() saves the journey and removes every task, key binding, sound,
    node and piece of UI the game made, and restores the few host settings it changed.
  - get_holoverse_result() tells HoloVerse how the archive stands (days, etchings read,
    whether Crimson has fallen, whether Nyx and Orbit have left with Gleebs).
"""
from __future__ import annotations

import inspect
import re

from direct.showbase.ShowBase import ShowBase
from panda3d.core import LColor

HOSTED_SWITCH_KEY = 'v'            # TAB is HoloVerse's while hosted
DIMENSION_ID = 'indigo_giant'
DIMENSION_TITLE = 'The Indigo Giant'


def _showbase_attribute_names() -> frozenset:
    """Every attribute ShowBase assigns on itself: the only names a hosted game borrows."""
    try:
        src = inspect.getsource(ShowBase)
    except (OSError, TypeError):                    # no source available (frozen build)
        src = ''
    names = set(re.findall(r'self\.(\w+)\s*=', src))
    # ShowBase's own private names (self.__x) are stored mangled as _ShowBase__x
    names |= {f'_ShowBase{n}' for n in list(names) if n.startswith('__') and not n.endswith('__')}
    names |= {'render', 'render2d', 'aspect2d', 'pixel2d', 'a2dTopLeft', 'a2dTopCenter', 'a2dTopRight',
              'a2dLeftCenter', 'a2dRightCenter', 'a2dBottomLeft', 'a2dBottomCenter', 'a2dBottomRight',
              'camera', 'cam', 'camLens', 'camNode', 'camList', 'win', 'winList', 'graphicsEngine', 'pipe',
              'taskMgr', 'loader', 'eventMgr', 'messenger', 'mouseWatcherNode', 'mouseWatcher',
              'buttonThrowers', 'sfxManagerList', 'musicManager', 'sfxActive', 'musicActive',
              'frameRateMeter', 'bufferViewer', 'dataRoot', 'dataRootNode', 'appRunner', 'clusterSyncFlag'}
    return frozenset(names)


SHOWBASE_NAMES = _showbase_attribute_names()
UI_LAYERS = ('aspect2d', 'render2d', 'pixel2d', 'a2dTopLeft', 'a2dTopCenter', 'a2dTopRight', 'a2dLeftCenter',
             'a2dRightCenter', 'a2dBottomLeft', 'a2dBottomCenter', 'a2dBottomRight')


class HoloVerseHostedMixin:
    """First in the game's bases, so its overrides win while hosted (and step aside otherwise)."""

    _holoverse_host = None

    # ------------------------------------------------------------ borrowing the host
    def __getattr__(self, name):
        host = self.__dict__.get('_holoverse_host')
        if host is not None and name in SHOWBASE_NAMES:
            return getattr(host, name)
        raise AttributeError(name)

    @property
    def hosted(self) -> bool:
        return self.__dict__.get('_holoverse_host') is not None

    def _hosted_begin(self, host, hooks: dict | None):
        """Before anything is built: remember what the host looks like, make our own scene root."""
        self._holoverse_host = host
        self._holoverse_hooks = dict(hooks or {})
        self._holoverse_closed = False
        self._holoverse_ui_baseline = {}
        for layer in UI_LAYERS:
            np_ = getattr(host, layer, None)
            if np_ is not None and not np_.isEmpty():
                self._holoverse_ui_baseline[layer] = {c.getKey() for c in np_.getChildren()}
        self._holoverse_saved = {
            'mw_modifiers': host.mouseWatcherNode.getModifierButtons() if host.mouseWatcherNode is not None else None,
            'thrower_modifiers': [t.node().getModifierButtons() for t in (host.buttonThrowers or [])],
            'thrower_down_events': [t.node().getButtonDownEvent() for t in (host.buttonThrowers or [])],
            # a copy: getClearColor() hands back a view of the window's own colour
            'background': LColor(host.win.getClearColor()) if host.win is not None else None,
        }
        # our world: a child of the host's render, so lights / shader / fog stay ours
        self.render = host.render.attachNewNode('indigo_giant_world')

    # ------------------------------------------------------------ asking the host for things
    def return_to_holoverse(self):
        """Leave for HoloVerse (the same as pressing TAB). Deferred a frame, so it never runs
        inside one of the game's own tasks or key handlers that it is about to remove."""
        host = self._holoverse_host
        if host is None:
            return
        cb = self._holoverse_hooks.get('return_home') or getattr(host, 'handle_tab_action', None)
        if callable(cb):
            host.taskMgr.doMethodLater(0.0, lambda task: (cb(), task.done)[1], 'holoverse_indigo_return_request')

    # ------------------------------------------------------------ what changes while hosted
    def userExit(self):
        if not self.hosted:
            return super().userExit()
        if getattr(self, 'persist', False) and getattr(self, 'human', None) is not None:
            self.save_game('back to HoloVerse')
        self.return_to_holoverse()

    def finalizeExit(self):
        if not self.hosted:
            return super().finalizeExit()
        self.return_to_holoverse()

    def restart_new_journey(self):
        if not self.hosted:
            return super().restart_new_journey()
        restart = self._holoverse_hooks.get('restart')
        if callable(restart):
            self._holoverse_host.taskMgr.doMethodLater(0.0, lambda task: (restart(), task.done)[1],
                                                       'holoverse_indigo_restart_request')
        else:
            self.return_to_holoverse()

    def apply_display_settings(self):
        if not self.hosted:
            return super().apply_display_settings()            # HoloVerse owns the window

    def _toggle_frame_meter(self):
        if not self.hosted:
            return super()._toggle_frame_meter()

    def _hosted_key_rules(self) -> dict:
        """action -> (its key outside HoloVerse, the key it uses inside): anything on TAB moves."""
        rules = {}
        taken = set(self.bindings.values())
        for action, key in self.bindings.items():
            if key == 'tab':
                spare = HOSTED_SWITCH_KEY if action == 'switch_character' and HOSTED_SWITCH_KEY not in taken else ''
                rules[action] = ('tab', spare)
        return rules

    def quit_words(self, standalone: str = 'quit') -> str:
        return 'return to HoloVerse' if self.hosted else standalone

    # ------------------------------------------------------------ the result HoloVerse keeps
    def get_holoverse_result(self) -> dict:
        state = getattr(self, 'gleebs_state', None)
        read = len(self.etchings_read()) if hasattr(self, 'etchings_read') else 0
        total = len(getattr(self, 'etchings', ()) or ())
        left = state == 'gone'
        return {
            'mode_id': DIMENSION_ID,
            'title': DIMENSION_TITLE,
            'completed': bool(left),
            'signal': 'indigo_giant_archive_complete' if left else (
                'indigo_giant_gleebs_waiting' if state in ('arriving', 'waiting') else ''),
            'day': int(getattr(self, 'day', 1) or 1),
            'etchings_read': read,
            'etchings_total': total,
            'fragments_recovered': str(read),
            'fragments_required': str(total),
            'crimson_fallen': bool(getattr(self, 'red_dead', False)),
            'gleebs_state': state or '',
            'places_found': int(self.places.found_count()) if getattr(self, 'places', None) else 0,
            'gleebs_response': ('The REDACTED archive is sealed. Nyx and Orbit came home with me.' if left else
                                'Nyx and Orbit are still out on REDACTED.'),
        }

    # ------------------------------------------------------------ leaving: remove everything we made
    def shutdown_for_holoverse(self):
        if not self.hosted or getattr(self, '_holoverse_closed', True):
            return
        self._holoverse_closed = True
        host = self._holoverse_host
        # 1. the journey is kept
        try:
            if getattr(self, 'persist', False) and getattr(self, 'human', None) is not None \
                    and getattr(self, 'gleebs_state', None) != 'leaving':
                self.save_game('back to HoloVerse')
        except Exception as exc:
            print(f'indigo_giant_holoverse_save_failed {type(exc).__name__}:{exc}')
        # 2. our tasks (every task whose function is one of our methods, plus the known names)
        names = {'shared_actor_movement', 'indigo_defender', 'red_giant_hunter', 'companion_survival',
                 'camera_controls', 'terrain_stream_queue', 'visibility_profile', 'stylized_sun_shadows',
                 'giant_idle', 'title_orbit'}
        for task in list(host.taskMgr.getAllTasks()):
            fn = task.getFunction() if hasattr(task, 'getFunction') else None
            if getattr(fn, '__self__', None) is self or task.getName() in names:
                host.taskMgr.remove(task)
        # 3. our key and mouse bindings
        try:
            self.ignoreAll()
        except Exception:
            pass
        # 4. our sounds (the host's audio device stays up)
        audio = getattr(self, 'audio', None)
        if audio is not None:
            try:
                audio.shutdown(release_device=False)
            except Exception as exc:
                print(f'indigo_giant_holoverse_audio_cleanup_error {type(exc).__name__}:{exc}')
            self.audio = None
        # 5. panels, the Gleebs hologram actor, the sky, the sun's shadow buffer, our world
        try:
            if getattr(self, 'panel', None) is not None:
                self._destroy_panel()
        except Exception:
            pass
        actor = getattr(self, 'gleebs_actor', None)
        if actor is not None:
            try:
                actor.cleanup()
            except Exception:
                pass
            self.gleebs_actor = None
        sky = getattr(self, 'sky', None)
        np_ = getattr(sky, 'np', None)
        if np_ is not None and not np_.isEmpty():
            np_.removeNode()
        sun = getattr(self, 'sun', None)
        if sun is not None:
            try:
                sun.setShadowCaster(False)
            except Exception:
                pass
        world = self.__dict__.get('render')
        if world is not None and not world.isEmpty():
            world.removeNode()
        # 6. every piece of UI we added to the host's 2-D layers
        for layer, before in self._holoverse_ui_baseline.items():
            np_ = getattr(host, layer, None)
            if np_ is None or np_.isEmpty():
                continue
            for child in list(np_.getChildren()):
                if child.getKey() not in before:
                    child.removeNode()
        # 7. the host input and background settings we changed
        saved = self._holoverse_saved
        try:
            if saved['mw_modifiers'] is not None and host.mouseWatcherNode is not None:
                host.mouseWatcherNode.setModifierButtons(saved['mw_modifiers'])
            for t, mods, down in zip(host.buttonThrowers or [], saved['thrower_modifiers'], saved['thrower_down_events']):
                t.node().setModifierButtons(mods)
                t.node().setButtonDownEvent(down)
            if saved['background'] is not None and host.win is not None:
                host.win.setClearColor(saved['background'])
        except Exception as exc:
            print(f'indigo_giant_holoverse_restore_error {type(exc).__name__}:{exc}')
        print('indigo_giant_holoverse_exit clean=1')
