from __future__ import annotations

from enum import Enum, auto


class GameState(Enum):
    BOOT = auto()
    TITLE = auto()
    CITY_MAP = auto()
    BUILDING_LOADING = auto()
    BUILDING_STAGE = auto()
    GLEEBS_EJECTION = auto()
    BUILDING_CAPTURED = auto()
    DISTRICT_COMPLETE = auto()
    PAUSED = auto()
    SETTINGS = auto()
    QUIT = auto()
