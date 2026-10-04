from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pygame


TEXT_SCALES = (0.90, 1.00, 1.15)
VOLUME_STEP = 0.05
SETTINGS_PANEL_RECT = pygame.Rect(450, 72, 1020, 936)
SETTINGS_ROW_ORIGIN = (520, 218)
SETTINGS_ROW_SIZE = (880, 46)
SETTINGS_ROW_STEP = 54
SETTINGS_RESET_RECT = pygame.Rect(548, 932, 250, 42)
SETTINGS_CLOSE_RECT = pygame.Rect(1122, 932, 250, 42)

DEFAULT_SETTINGS: dict[str, Any] = {
    "master_volume": 0.80,
    "ambience_volume": 0.62,
    "music_volume": 0.42,
    "sfx_volume": 0.86,
    "reduced_motion": False,
    "reduced_glitch": False,
    "reduced_flashing": False,
    "high_contrast": False,
    "state_symbols": True,
    "audio_captions": True,
    "edge_pan": True,
    "text_scale": 1.00,
    "muted": False,
}


@dataclass(frozen=True)
class SettingRow:
    key: str
    label: str
    kind: str
    description: str


SETTING_ROWS: tuple[SettingRow, ...] = (
    SettingRow("master_volume", "MASTER VOLUME", "volume", "Overall game output."),
    SettingRow("ambience_volume", "AMBIENCE VOLUME", "volume", "City rain, room hum, and machinery."),
    SettingRow("music_volume", "SIGNAL SCORE VOLUME", "volume", "Background score layer."),
    SettingRow("sfx_volume", "SFX VOLUME", "volume", "Hacks, menus, alarms, and capture cues."),
    SettingRow("reduced_motion", "REDUCED CAMERA MOTION", "toggle", "Slower traffic, rain, and interface motion."),
    SettingRow("reduced_glitch", "REDUCED GLITCH INTENSITY", "toggle", "Fewer scanlines and interference fragments."),
    SettingRow("reduced_flashing", "REDUCED FLASHING", "toggle", "Static warnings and non-pulsing selection frames."),
    SettingRow("high_contrast", "HIGH-CONTRAST TARGETS", "toggle", "Brighter target and camera-feed borders."),
    SettingRow("state_symbols", "BUILDING STATE SYMBOLS", "toggle", "Adds shape-coded status markers independent of color."),
    SettingRow("audio_captions", "AUDIO EVENT CAPTIONS", "toggle", "Displays important sound events as short captions."),
    SettingRow("edge_pan", "MOUSE EDGE PAN", "toggle", "Pan the satellite view at screen edges."),
    SettingRow("text_scale", "INTERFACE TEXT SIZE", "scale", "Compact, standard, or large interface text."),
)


def settings_row_rect(index: int) -> pygame.Rect:
    return pygame.Rect(
        SETTINGS_ROW_ORIGIN[0],
        SETTINGS_ROW_ORIGIN[1] + index * SETTINGS_ROW_STEP,
        SETTINGS_ROW_SIZE[0],
        SETTINGS_ROW_SIZE[1],
    )


def settings_hit_test(position: tuple[int, int] | pygame.Vector2) -> int | None:
    point = (int(position[0]), int(position[1]))
    for index in range(len(SETTING_ROWS)):
        if settings_row_rect(index).collidepoint(point):
            return index
    return None


def normalize_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    settings = dict(DEFAULT_SETTINGS)
    settings.update(source)
    for key in ("master_volume", "ambience_volume", "music_volume", "sfx_volume"):
        try:
            settings[key] = max(0.0, min(1.0, float(settings[key])))
        except (TypeError, ValueError):
            settings[key] = DEFAULT_SETTINGS[key]
    for key in (
        "reduced_motion",
        "reduced_glitch",
        "reduced_flashing",
        "high_contrast",
        "state_symbols",
        "audio_captions",
        "edge_pan",
        "muted",
    ):
        settings[key] = bool(settings.get(key, DEFAULT_SETTINGS[key]))
    try:
        requested = float(settings.get("text_scale", 1.0))
    except (TypeError, ValueError):
        requested = 1.0
    settings["text_scale"] = min(TEXT_SCALES, key=lambda value: abs(value - requested))
    return settings


def setting_value_text(settings: dict[str, Any], row: SettingRow) -> str:
    value = settings[row.key]
    if row.kind == "volume":
        return f"{round(float(value) * 100):3d}%"
    if row.kind == "toggle":
        return "ON" if bool(value) else "OFF"
    if row.kind == "scale":
        return {0.90: "COMPACT", 1.00: "STANDARD", 1.15: "LARGE"}.get(float(value), "STANDARD")
    return str(value)


def adjust_setting(settings: dict[str, Any], row_index: int, direction: int) -> bool:
    row = SETTING_ROWS[row_index % len(SETTING_ROWS)]
    old = settings[row.key]
    if row.kind == "volume":
        settings[row.key] = round(max(0.0, min(1.0, float(old) + direction * VOLUME_STEP)), 2)
    elif row.kind == "toggle":
        settings[row.key] = not bool(old)
    elif row.kind == "scale":
        index = min(range(len(TEXT_SCALES)), key=lambda idx: abs(TEXT_SCALES[idx] - float(old)))
        settings[row.key] = TEXT_SCALES[max(0, min(len(TEXT_SCALES) - 1, index + direction))]
    return settings[row.key] != old


def reset_settings(settings: dict[str, Any]) -> None:
    settings.clear()
    settings.update(DEFAULT_SETTINGS)
