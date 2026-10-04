"""Where the game's files are (Pass 62).

The game code lives in indigo_giant/; everything it loads lives beside it in the game folder.
This is the only module that works out where that is, so moving the folder (or renaming it
inside a bigger project) changes nothing else.
"""
from __future__ import annotations

from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent                      # the game folder: main.py, assets/, audio/, shaders/, ui/
MAIN = ROOT / 'main.py'                    # the launcher (the Prototype Lab and RUN_INDIGO_GIANT.bat start it)
ASSETS = ROOT / 'assets'
AUDIO = ROOT / 'audio'
SHADERS = ROOT / 'shaders'
FONTS = ROOT / 'ui' / 'fonts'
GHOST_SAVES = ROOT / 'ghost_saves'
GIANT_GLB = ASSETS / 'Universal Animation Library[Standard]' / 'Unreal-Godot' / 'UAL1_Standard.glb'
GLEEBS_BAM = ASSETS / 'gleebs' / 'Gleebs_Game.bam'
