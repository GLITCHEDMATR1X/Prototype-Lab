from __future__ import annotations

import json
import os
from pathlib import Path

APP_DIR_NAME = "Andrews Nightmare"
ORG_DIR_NAME = "GLITCHED MATRIX"
DEFAULTS = {
    "mouse_sensitivity": 0.115,
    "fov": 86.0,
    "borderless": True,
}


def user_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        path = base / ORG_DIR_NAME / APP_DIR_NAME
    elif sys_platform() == "darwin":
        path = Path.home() / "Library" / "Application Support" / ORG_DIR_NAME / APP_DIR_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        path = base / "glitched-matrix" / "andrews-nightmare"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sys_platform() -> str:
    import sys
    return sys.platform


def load_settings() -> dict:
    data = DEFAULTS.copy()
    path = user_data_dir() / "settings.json"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            for key in DEFAULTS:
                if key in loaded:
                    data[key] = loaded[key]
    except (OSError, json.JSONDecodeError):
        pass
    data["mouse_sensitivity"] = max(0.03, min(0.30, float(data["mouse_sensitivity"])))
    data["fov"] = max(70.0, min(105.0, float(data["fov"])))
    data["borderless"] = bool(data["borderless"])
    return data


def save_settings(settings: dict) -> None:
    path = user_data_dir() / "settings.json"
    tmp = path.with_suffix(".tmp")
    payload = {k: settings[k] for k in DEFAULTS}
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)
