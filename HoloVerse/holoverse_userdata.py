"""Where HoloVerse keeps the player's own files.  Pass 282.68.

Everything a player creates while playing (settings, progression, region saves, the
dimension archive, logs and crash reports) lives outside the game folder, the same way
the other Glitched Matrix games already do it (Indigo Giant, Afterlife of IO, Mirror's Limbo):

    Windows   %LOCALAPPDATA%\\GLITCHED MATRIX\\HoloVerse\\
    macOS     ~/Library/Application Support/GLITCHED MATRIX/HoloVerse/
    Linux     $XDG_DATA_HOME/glitched-matrix/holoverse/  (default ~/.local/share/...)

Inside that folder:

    dimension_archive.json   linked realities and visits
    saves/                   settings, progression, region and world state
    logs/                    latest.log, crash.log, return signals, test reports

The game folder itself stays read-only, so a Steam build never ships anyone's progress.
HOLOVERSE_USER_DATA overrides the whole location (used by tests and portable runs).
Standard library only, so it can be imported before Panda3D.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

COMPANY_FOLDER = "GLITCHED MATRIX"
GAME_FOLDER = "HoloVerse"


def user_data_root() -> Path:
    override = str(os.environ.get("HOLOVERSE_USER_DATA") or "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = str(os.environ.get("LOCALAPPDATA") or "").strip()
        return (Path(base) if base else Path.home() / "AppData" / "Local") / COMPANY_FOLDER / GAME_FOLDER
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / COMPANY_FOLDER / GAME_FOLDER
    xdg = str(os.environ.get("XDG_DATA_HOME") or "").strip()
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / "glitched-matrix" / "holoverse"


def state_root() -> Path:
    """Settings, progression, region and world saves (was <game>/runtime_state)."""
    return user_data_root() / "saves"


def log_root() -> Path:
    """latest.log, crash.log, return-signal handoff files and test reports (was <game>/logs)."""
    return user_data_root() / "logs"


def is_inside(path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except Exception:
        return False
