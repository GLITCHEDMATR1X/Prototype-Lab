"""HoloSpace ship interior settings (Pass 282.76).

The cockpit's colours and window design live in ``assets/config/holospace_cockpit.json`` so they
can be edited without touching code.  The file is written with the defaults the first time the
game runs without one, and every field falls back to its default if it is missing or invalid.

The theme the player last picked in flight (C cycles themes) is a per-player choice, so it is
saved in the player's save folder (``holospace_cockpit_choice.json`` beside dimension_archive.json),
never in the game folder.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "assets" / "config" / "holospace_cockpit.json"

DEFAULT_CONFIG = {
    "_readme": [
        "HoloSpace ship interior. Edit this file, then restart HoloVerse to see the changes.",
        "Colours are [red, green, blue] from 0.0 to 1.0.",
        "themes: the colour sets C cycles through in flight. hull = frame and struts, glass = tint of the",
        "  outer canopy glass, trim = glowing window edge, hud = holographic display colour, hud_warn = warnings.",
        "default_theme: the theme name used until the player picks one with C.",
        "window: the clear main window. sides 6-16 (8 = octagon), half_width/half_height in canopy units,",
        "  centre_z moves it up/down, frame_width/strut_width are the hull bar thicknesses.",
        "glass_alpha: how strongly the outer glass is tinted (0 = fully clear, 0.4 = heavy tint).",
        "struts: draw the hull struts from the window corners to the canopy edge (true/false).",
        "Delete this file to restore the defaults.",
    ],
    "default_theme": "CYAN",
    "glass_alpha": 0.10,
    "struts": True,
    "window": {
        "sides": 8,
        "half_width": 0.86,
        "half_height": 0.47,
        "centre_z": 0.06,
        "frame_width": 0.020,
        "strut_width": 0.022,
    },
    "themes": [
        {"name": "CYAN", "hull": [0.10, 0.13, 0.17], "glass": [0.30, 0.75, 0.95], "trim": [0.40, 0.95, 1.00],
         "hud": [0.40, 0.95, 1.00], "hud_warn": [1.00, 0.45, 0.32]},
        {"name": "VIOLET", "hull": [0.13, 0.09, 0.19], "glass": [0.62, 0.38, 0.95], "trim": [0.86, 0.48, 1.00],
         "hud": [0.80, 0.62, 1.00], "hud_warn": [1.00, 0.45, 0.40]},
        {"name": "AMBER", "hull": [0.17, 0.12, 0.08], "glass": [0.95, 0.62, 0.28], "trim": [1.00, 0.72, 0.28],
         "hud": [1.00, 0.78, 0.40], "hud_warn": [1.00, 0.36, 0.30]},
        {"name": "EMERALD", "hull": [0.07, 0.15, 0.12], "glass": [0.30, 0.90, 0.62], "trim": [0.40, 1.00, 0.70],
         "hud": [0.50, 1.00, 0.78], "hud_warn": [1.00, 0.48, 0.32]},
    ],
}


def _colour(value, fallback):
    try:
        vals = [max(0.0, min(1.0, float(v))) for v in list(value)[:3]]
        if len(vals) == 3:
            return tuple(vals)
    except Exception:
        pass
    return tuple(fallback)


def _number(value, fallback, lo, hi):
    try:
        return max(lo, min(hi, float(value)))
    except Exception:
        return fallback


def load_config() -> dict:
    """The cockpit config with every field validated (defaults fill anything missing)."""
    raw = {}
    if CONFIG_PATH.is_file():
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raw = {}
        except Exception as exc:
            print(f"holospace_cockpit_config_invalid path={CONFIG_PATH} err={exc}")
            raw = {}
    else:
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass                                   # read-only install: defaults still apply
    base = copy.deepcopy(DEFAULT_CONFIG)
    win_raw = raw.get("window") if isinstance(raw.get("window"), dict) else {}
    dw = base["window"]
    window = {
        "sides": int(_number(win_raw.get("sides"), dw["sides"], 6, 16)),
        "half_width": _number(win_raw.get("half_width"), dw["half_width"], 0.30, 1.05),
        "half_height": _number(win_raw.get("half_height"), dw["half_height"], 0.20, 0.60),
        "centre_z": _number(win_raw.get("centre_z"), dw["centre_z"], -0.20, 0.25),
        "frame_width": _number(win_raw.get("frame_width"), dw["frame_width"], 0.004, 0.08),
        "strut_width": _number(win_raw.get("strut_width"), dw["strut_width"], 0.004, 0.08),
    }
    themes = []
    for entry in raw.get("themes") if isinstance(raw.get("themes"), list) else []:
        if not isinstance(entry, dict):
            continue
        d = DEFAULT_CONFIG["themes"][0]
        themes.append({
            "name": str(entry.get("name") or f"THEME {len(themes) + 1}").upper()[:16],
            "hull": _colour(entry.get("hull"), d["hull"]),
            "glass": _colour(entry.get("glass"), d["glass"]),
            "trim": _colour(entry.get("trim"), d["trim"]),
            "hud": _colour(entry.get("hud"), entry.get("trim") or d["hud"]),
            "hud_warn": _colour(entry.get("hud_warn"), d["hud_warn"]),
        })
    if not themes:
        themes = [{k: (tuple(v) if isinstance(v, list) else v) for k, v in t.items()} for t in DEFAULT_CONFIG["themes"]]
    return {
        "default_theme": str(raw.get("default_theme") or base["default_theme"]).upper(),
        "glass_alpha": _number(raw.get("glass_alpha"), base["glass_alpha"], 0.0, 0.6),
        "struts": bool(raw.get("struts", base["struts"])),
        "window": window,
        "themes": themes,
    }


def _choice_path() -> Path | None:
    try:
        from holoverse_userdata import user_data_root
        return user_data_root() / "holospace_cockpit_choice.json"
    except Exception:
        return None


def load_theme_choice() -> str:
    path = _choice_path()
    try:
        if path is not None and path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return str(data.get("theme") or "").upper()
    except Exception:
        pass
    return ""


def save_theme_choice(name: str) -> None:
    path = _choice_path()
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"theme": str(name)}, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"holospace_cockpit_choice_save_failed err={exc}")
