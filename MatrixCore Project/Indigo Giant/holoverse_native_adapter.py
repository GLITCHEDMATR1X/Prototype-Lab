"""The Indigo Giant as a HoloVerse dimension (Pass 63).

HoloVerse (Gleebs -> Dimension Archive) loads this file into its own running Panda3D app and
calls create_mode(host, ...). The real game (indigo_giant/app.py) is then built against the
host's ShowBase: same window, no second ShowBase, subprocess or event loop. The host owns
TAB (it always returns home) and restores itself after exit().

Standalone play does not use this file: main.py, RUN_INDIGO_GIANT.bat, the Prototype Lab
cabinet and GX Launcher all start the game on its own.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


class HoloVerseNativeMode:
    """HoloVerse's lifecycle bridge: enter() builds the game, exit() takes it down."""

    HOST_CONTRACT = 'holoverse_dimension_v1'
    COMPATIBILITY = 'native'

    def __init__(self, host: Any, mode: dict | None = None, entry_path: Path | None = None,
                 label: str = 'THE INDIGO GIANT') -> None:
        self.host = host
        self.mode = mode or {}
        self.entry_path = Path(entry_path).resolve() if entry_path else ROOT / 'main.py'
        self.label = label
        self.game = None
        self._destroyed = False

    # ------------------------------------------------------------ the game
    def _game_class(self):
        # The game folder is on sys.path only while the package is imported: the package imports
        # itself relatively, and HoloVerse must never pick up a module of ours by name (an old
        # top-level audio.py or settings.py, say) during the visit.
        added = str(ROOT) not in sys.path
        if added:
            sys.path.insert(0, str(ROOT))
        try:
            from indigo_giant import app, paths
        finally:
            if added:
                try:
                    sys.path.remove(str(ROOT))
                except ValueError:
                    pass
        return app.StreamingTerrainWithGiant, paths

    def _build(self, new_game: bool = False):
        cls, paths = self._game_class()
        return cls(giant_glb=paths.GIANT_GLB, new_game=new_game, host=self.host,
                   host_hooks={'restart': self._restart_new_journey})

    def enter(self):
        if self.game is None:
            self.game = self._build()
            print('indigo_giant_native_enter source=indigo_giant/app.py shared_showbase=1 tab_owner=holoverse '
                  'responder=holoverse_responder_v1')
        return self.game

    def _restart_new_journey(self):
        """'new journey' inside HoloVerse: the old journey is already backed up by the game."""
        old = self.game
        self.game = None
        if old is not None:
            old.shutdown_for_holoverse()
        self.game = self._build(new_game=True)
        print('indigo_giant_native_new_journey')

    def update(self, dt: float):
        return None                     # the game drives itself with its own tasks

    # ------------------------------------------------------------ what HoloVerse keeps
    def get_holoverse_result(self) -> dict:
        return self.game.get_holoverse_result() if self.game is not None else {}

    # ------------------------------------------------------------ leaving
    def exit(self):
        self.destroy()

    def destroy(self):
        if self._destroyed:
            return
        self._destroyed = True
        game, self.game = self.game, None
        if game is not None:
            try:
                game.shutdown_for_holoverse()
            except Exception as exc:
                print(f'indigo_giant_native_exit_cleanup_error {type(exc).__name__}:{exc}')
        print('indigo_giant_native_exit clean=1')


def create_mode(host, mode: dict | None = None, entry_path: Path | None = None,
                label: str = 'THE INDIGO GIANT') -> HoloVerseNativeMode:
    return HoloVerseNativeMode(host, mode=mode, entry_path=entry_path, label=label)


# the factory names other HoloVerse builds look for
create_native_mode = create_mode
create_native_adapter = create_mode
create_adapter = create_mode
