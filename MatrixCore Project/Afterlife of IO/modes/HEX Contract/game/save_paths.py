from __future__ import annotations

import os
from pathlib import Path
import sys

SAVE_ROOT_ENV = "HEX_CONTRACT_SAVE_ROOT"
DEFAULT_PROFILE_NAME = "save_profile.json"


def resolve_save_root(project_root: Path, explicit_root: str | None = None) -> Path:
    """Resolve the writable save root without forcing a platform backend.

    Order of authority:
    1. explicit --save-root value
    2. HEX_CONTRACT_SAVE_ROOT environment variable
    3. packaged/frozen Windows fallback under LOCALAPPDATA
    4. current legacy project-root behavior for source/Prototype Lab runs

    A Microsoft GDK package can provide its XGameSaveFiles synchronized folder
    through --save-root, the environment variable, or Pass 26 native bridge.
    """
    if explicit_root:
        return Path(explicit_root).expanduser()
    env_root = os.environ.get(SAVE_ROOT_ENV)
    if env_root:
        return Path(env_root).expanduser()
    if os.name == "nt" and getattr(sys, "frozen", False):
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "GLITCHED MATRIX" / "HEX CONTRACT"
    return Path(project_root)


def resolve_profile_path(project_root: Path, explicit_profile: str | None = None, explicit_root: str | None = None) -> Path:
    if explicit_profile:
        return Path(explicit_profile).expanduser()
    return resolve_save_root(project_root, explicit_root) / DEFAULT_PROFILE_NAME
