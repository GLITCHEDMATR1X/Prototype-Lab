"""Clean HoloCore entry point.

Standalone HoloCore runs still execute ``main.py`` directly.  When HoloVerse
discovers this project under ``Prototype Lab/MatrixCore Project/HoloCore``, it
loads ``holoverse_native_adapter.py`` in-process.  That adapter owns HoloCore's
scene, input, and teardown inside HoloVerse's existing Panda3D window; HoloVerse
does not ship a private HoloCore scene anymore.

This wrapper remains standalone/fallback protection only.  It refuses stale
child-window HoloVerse launches so an obsolete route cannot create a second
overlapping HoloCore process.  TAB remains HoloVerse-owned while embedded.
"""
from __future__ import annotations

import json
import os
import runpy
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "main.py"


def _launched_from_holoverse_child_gateway() -> bool:
    transition_mode = str(os.environ.get("HOLOVERSE_TRANSITION_MODE_ID", "")).strip().lower()
    transition_label = str(os.environ.get("HOLOVERSE_TRANSITION_MODE_LABEL", "")).replace(" ", "").strip().lower()
    gateway_source = str(os.environ.get("HOLOVERSE_GATEWAY_SOURCE", "")).strip().lower()
    transition_active = str(os.environ.get("HOLOVERSE_TRANSITION_ACTIVE", "")).strip().lower() in {"1", "true", "yes", "on"}
    return bool(transition_active and (transition_mode == "holocore" or transition_label == "holocore" or gateway_source == "holocore"))


def _write_child_block_report() -> None:
    payload = {
        "kind": "holocore_child_window_launch_blocked",
        "reason": "HoloCore is an external native HoloVerse dimension; use its folder-local holoverse_native_adapter.py instead of a child process.",
        "timestamp": time.time(),
        "argv": list(sys.argv),
        "transition_mode": os.environ.get("HOLOVERSE_TRANSITION_MODE_ID", ""),
        "transition_label": os.environ.get("HOLOVERSE_TRANSITION_MODE_LABEL", ""),
    }
    try:
        logs = ROOT / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "holocore_child_window_blocked.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass
    print(payload["reason"])


if __name__ == "__main__":
    if _launched_from_holoverse_child_gateway():
        _write_child_block_report()
        raise SystemExit(0)
    runpy.run_path(str(MAIN), run_name="__main__")
