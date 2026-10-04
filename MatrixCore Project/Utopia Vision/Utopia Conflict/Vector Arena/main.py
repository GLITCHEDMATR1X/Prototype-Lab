"""Standalone launcher for Vector Arena.

This package was split out of HoloVerse, so this file owns the normal window
configuration while ``standalone_native_adapter.py`` owns the Panda3D game
mode.  Smoke/self-test runs still use an offscreen/null-audio profile so the
build can be validated on machines without an audio device.

    python main.py
    python main.py --self-test --auto-exit --screenshot proof.png
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

GAME_CONTRACT_CLI_FLAGS = {"--game-contract-test", "--game-result-test", "--complete-game-test", "--profile-test"}
if any(_flag in sys.argv for _flag in GAME_CONTRACT_CLI_FLAGS):
    from standalone_game_contract import handle_game_contract_cli
    raise SystemExit(handle_game_contract_cli(root=Path(__file__).resolve().parent))

from panda3d.core import ClockObject, loadPrcFileData


SELF_TEST = "--self-test" in sys.argv or "--smoke-test" in sys.argv
AUTO_EXIT = "--auto-exit" in sys.argv or SELF_TEST


def _arg_value(flag: str, default: str = "") -> str:
    try:
        return sys.argv[sys.argv.index(flag) + 1]
    except Exception:
        return default


SCREENSHOT_PATH = _arg_value("--screenshot", "") or _arg_value("--test-shot", "")
APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "vector_arena_config.json"


def _load_config() -> dict:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _bool_config(data: dict, key: str, default: bool) -> bool:
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _int_config(data: dict, key: str, default: int, low: int, high: int) -> int:
    try:
        value = int(data.get(key, default))
    except Exception:
        value = default
    return max(low, min(high, value))


_config = _load_config()
_window_cfg = _config.get("window", {}) if isinstance(_config.get("window", {}), dict) else {}
_audio_cfg = _config.get("audio", {}) if isinstance(_config.get("audio", {}), dict) else {}
win_w = _int_config(_window_cfg, "width", 1920, 640, 7680)
win_h = _int_config(_window_cfg, "height", 1080, 360, 4320)
borderless = _bool_config(_window_cfg, "borderless", True)
show_fps = _bool_config(_window_cfg, "show_fps", False)
standalone_audio = _bool_config(_audio_cfg, "enabled", True) and "--no-audio" not in sys.argv

_prc = [
    "window-title Vector Arena",
    f"win-size {win_w} {win_h}",
    "sync-video true",
    f"show-frame-rate-meter {1 if show_fps else 0}",
]
if SELF_TEST:
    _prc += [
        "window-type offscreen",
        "load-display p3tinydisplay",
        "aux-display p3tinydisplay",
        "audio-library-name null",
    ]
else:
    _prc += ["window-type onscreen"]
    if borderless:
        _prc.append("undecorated true")
    if not standalone_audio:
        _prc.append("audio-library-name null")
loadPrcFileData("", "\n".join(_prc))

from direct.showbase.ShowBase import ShowBase
from standalone_native_adapter import create_mode


def write_crash_report(exc: BaseException, context: str = "standalone") -> Path | None:
    try:
        root = Path(__file__).resolve().parent / "crash_reports"
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = root / f"vector_arena_crash_{context}_{stamp}.txt"
        path.write_text(
            "Vector Arena standalone smoke crash\n"
            f"context={context}\nargv={' '.join(sys.argv)}\n\n"
            + "".join(traceback.format_exception(type(exc), exc, getattr(exc, "__traceback__", None))),
            encoding="utf-8",
        )
        print(f"crash_report={path}")
        return path
    except Exception as report_exc:
        print(f"crash_report_failed={report_exc.__class__.__name__}:{report_exc}")
        return None


class _VectorArenaDebugHost(ShowBase):
    def __init__(self):
        super().__init__()
        self.mode = create_mode(self, entry_path=str(APP_DIR / "main.py"), label="Vector Arena")
        self.mode.enter()
        self.frame_count = 0
        self.taskMgr.add(self._update, "vector-arena-debug-update")
        self.accept("escape", self._exit)
        self.accept("h", self.mode.toggle_dimension_ui)
        self.accept("mouse1", lambda: self.mode.on_host_action("mouse1"))
        self.accept("mouse3", lambda: self.mode.on_host_action("mouse3"))
        self.accept("mouse2", lambda: self.mode.on_host_action("mouse3"))

    def _update(self, task):
        dt = min(0.033, ClockObject.getGlobalClock().getDt())
        self.frame_count += 1
        self.mode.update(dt)
        if SCREENSHOT_PATH and self.frame_count == 4:
            try:
                shot_path = Path(SCREENSHOT_PATH)
                if shot_path.parent and str(shot_path.parent) not in {"", "."}:
                    shot_path.parent.mkdir(parents=True, exist_ok=True)
                self.graphicsEngine.renderFrame()
                ok = self.screenshot(str(shot_path), defaultFilename=False)
                print(f"screenshot={shot_path} saved={bool(ok and shot_path.exists())}")
            except Exception as exc:
                print(f"screenshot_failed={exc.__class__.__name__}:{exc}")
        if AUTO_EXIT and self.frame_count >= 6:
            try:
                result = self.mode.get_result()
                print(f"sfx_loaded={result.get('sfx_loaded', 0)}")
            except Exception:
                print("sfx_loaded=unknown")
            print("VECTOR_ARENA_SELF_TEST_OK")
            self._exit()
            return task.done
        return task.cont

    def _exit(self):
        try:
            self.mode.exit()
        except Exception:
            pass
        self.userExit()


if __name__ == "__main__":
    try:
        _VectorArenaDebugHost().run()
    except Exception as exc:
        write_crash_report(exc, context="self_test" if SELF_TEST else "standalone")
        raise
