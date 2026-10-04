from __future__ import annotations

import os
import sys
from pathlib import Path

APP_FOLDER_NAME = "GhostSignalUtopia"
LEGACY_FOLDER_NAME = ".ghost_signal_utopia"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def user_data_dir() -> Path:
    override = os.environ.get("GHOST_SIGNAL_DATA_DIR")
    if override:
        return Path(override).expanduser()

    legacy = Path.home() / LEGACY_FOLDER_NAME
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            native = Path(local_app_data) / APP_FOLDER_NAME
            # Preserve an existing source-build profile until the native location
            # has been used once; new Windows installs use LOCALAPPDATA.
            if native.exists() or not legacy.exists():
                return native
    return legacy


def crash_log_path() -> Path:
    override = os.environ.get("GHOST_SIGNAL_CRASH_LOG")
    return Path(override).expanduser() if override else user_data_dir() / "crash.log"


def source_result_dir() -> Path:
    return project_root() / "verification" / "reports"
