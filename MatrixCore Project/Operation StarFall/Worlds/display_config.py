from __future__ import annotations

import ctypes
import os
import platform
from pathlib import Path
from typing import Callable, Iterable

try:
    from settings_authority import load_settings, mode_from_display_preset
except Exception:
    load_settings = None
    mode_from_display_preset = None

DisplayLoader = Callable[[str, str], None]

DESIGN_CANVAS_SIZE = (1920, 1080)
REFERENCE_WINDOW_SIZE = (1920, 1080)
MIN_SUPPORTED_WINDOW_SIZE = (1280, 720)
TARGET_BORDERED_WINDOW_SIZE = (1600, 900)
LARGE_BORDERED_WINDOW_SIZE = (1920, 1080)
SAFE_BORDERED_WINDOW_SIZE = (1440, 810)
DEFAULT_FULL_WINDOW_SIZE = (1920, 1080)
DEFAULT_WINDOWED_SIZE = (1280, 720)
DESKTOP_CLIENT_MARGIN = (48, 88)
DISPLAY_FLAG_SET = {
    "--reference-window",
    "--1080p",
    "--desktop-window",
    "--bordered-fullscreen",
    "--decorated-fullscreen",
    "--bordered-window",
    "--safe-window",
    "--large-window",
    "--windowed-fullscreen",
    "--full-windowed",
    "--borderless",
    "--windowed",
    "--fullscreen",
}


def _argv_list(argv: Iterable[str] | None) -> list[str]:
    return [str(arg) for arg in (argv or [])]


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _saved_display_mode() -> str | None:
    if load_settings is None or mode_from_display_preset is None:
        return None
    try:
        settings = load_settings(_project_root())
        preset = str(settings.get("display_preset", "")).strip()
        mode = mode_from_display_preset(preset)
        return str(mode) if mode else None
    except Exception:
        return None


def requested_display_mode(argv: Iterable[str] | None = None) -> str:
    args = set(_argv_list(argv))
    env_mode = os.environ.get("PROTOTYPE_LAB_DISPLAY_MODE", "").strip().lower().replace("-", "_")
    if "--reference-window" in args or "--1080p" in args or env_mode in {"reference", "reference_1080p", "1080p", "reference_window"}:
        return "reference_1080p_window"
    if "--fullscreen" in args or env_mode in {"fullscreen", "exclusive_fullscreen"}:
        return "fullscreen"
    if "--windowed-fullscreen" in args or "--full-windowed" in args or "--borderless" in args or env_mode in {"windowed_fullscreen", "full_windowed", "borderless", "borderless_desktop"}:
        return "windowed_fullscreen"
    if "--desktop-window" in args or env_mode in {"desktop", "desktop_window", "desktop_resizable", "resizable"}:
        return "desktop_resizable_window"
    if "--windowed" in args or env_mode in {"windowed", "compact", "compact_window", "720p"}:
        return "windowed"
    if "--safe-window" in args or env_mode in {"safe_window", "safe", "1440x810"}:
        return "safe_bordered_window"
    if "--large-window" in args or env_mode in {"large_window", "bordered_fullscreen", "decorated_fullscreen"}:
        return "large_bordered_window"
    if (
        "--bordered-fullscreen" in args
        or "--decorated-fullscreen" in args
        or "--bordered-window" in args
        or env_mode in {"bordered", "decorated", "bordered_window"}
    ):
        return "standard_bordered_window"
    saved_mode = _saved_display_mode()
    return saved_mode or "reference_1080p_window"


def inherited_display_args(argv: Iterable[str] | None = None) -> list[str]:
    mode = requested_display_mode(argv)
    mapping = {
        "reference_1080p_window": ["--reference-window"],
        "fullscreen": ["--fullscreen"],
        "windowed_fullscreen": ["--windowed-fullscreen"],
        "desktop_resizable_window": ["--desktop-window"],
        "windowed": ["--windowed"],
        "safe_bordered_window": ["--safe-window"],
        "large_bordered_window": ["--large-window"],
        "standard_bordered_window": ["--bordered-window"],
    }
    return list(mapping.get(mode, ["--reference-window"]))


def _enable_windows_dpi_awareness() -> None:
    if platform.system().lower() != "windows":
        return
    try:
        user32 = ctypes.windll.user32
        setter = getattr(user32, "SetProcessDpiAwarenessContext", None)
        if setter is not None:
            setter(ctypes.c_void_p(-4))  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        pass


def _detect_desktop_geometry() -> dict[str, int] | None:
    _enable_windows_dpi_awareness()
    if platform.system().lower() == "windows":
        try:
            user32 = ctypes.windll.user32

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            screen_w = int(user32.GetSystemMetrics(0))
            screen_h = int(user32.GetSystemMetrics(1))
            rect = RECT()
            if bool(user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)):
                work_x = int(rect.left)
                work_y = int(rect.top)
                work_w = int(rect.right - rect.left)
                work_h = int(rect.bottom - rect.top)
            else:
                work_x = 0
                work_y = 0
                work_w = screen_w
                work_h = screen_h
            if screen_w > 0 and screen_h > 0 and work_w > 0 and work_h > 0:
                return {
                    "screen_width": screen_w,
                    "screen_height": screen_h,
                    "work_x": work_x,
                    "work_y": work_y,
                    "work_width": work_w,
                    "work_height": work_h,
                }
        except Exception:
            pass
    try:
        import tkinter as tk  # type: ignore

        root = tk.Tk()
        root.withdraw()
        width = int(root.winfo_screenwidth())
        height = int(root.winfo_screenheight())
        root.destroy()
        if width > 0 and height > 0:
            return {
                "screen_width": width,
                "screen_height": height,
                "work_x": 0,
                "work_y": 0,
                "work_width": width,
                "work_height": height,
            }
    except Exception:
        return None
    return None


def _even(value: float) -> int:
    return max(2, int(value) // 2 * 2)


def choose_desktop_window_geometry(desktop: dict[str, int] | None = None) -> dict[str, int | str | bool]:
    info = desktop or _detect_desktop_geometry()
    if not info:
        return {
            "width": TARGET_BORDERED_WINDOW_SIZE[0],
            "height": TARGET_BORDERED_WINDOW_SIZE[1],
            "origin_x": 64,
            "origin_y": 40,
            "desktop_width": 0,
            "desktop_height": 0,
            "work_width": 0,
            "work_height": 0,
            "scaled_for_desktop": False,
            "label": "desktop_resizable_fallback",
        }

    work_x = int(info.get("work_x", 0))
    work_y = int(info.get("work_y", 0))
    work_w = max(int(info.get("work_width", info.get("screen_width", 0))), 640)
    work_h = max(int(info.get("work_height", info.get("screen_height", 0))), 480)
    margin_x, margin_y = DESKTOP_CLIENT_MARGIN
    width = _even(max(960, work_w - margin_x))
    height = _even(max(540, work_h - margin_y))
    width = min(width, work_w)
    height = min(height, work_h)
    origin_x = work_x + max(0, (work_w - width) // 2)
    origin_y = work_y + max(0, (work_h - height) // 2)
    return {
        "width": width,
        "height": height,
        "origin_x": origin_x,
        "origin_y": origin_y,
        "desktop_width": int(info.get("screen_width", work_w)),
        "desktop_height": int(info.get("screen_height", work_h)),
        "work_width": work_w,
        "work_height": work_h,
        "scaled_for_desktop": True,
        "label": "desktop_resizable_best_fit",
    }


def choose_bordered_window_geometry(target_size: tuple[int, int] = TARGET_BORDERED_WINDOW_SIZE) -> dict[str, int | str | bool]:
    target_w, target_h = target_size
    info = _detect_desktop_geometry()
    if not info:
        return {
            "width": target_w,
            "height": target_h,
            "origin_x": 64,
            "origin_y": 40,
            "desktop_width": 0,
            "desktop_height": 0,
            "scaled_down": False,
            "label": "holoverse_canvas_16x9_target",
        }

    screen_w = int(info["screen_width"])
    screen_h = int(info["screen_height"])
    work_w = int(info["work_width"])
    work_h = int(info["work_height"])
    usable_w = max(960, work_w - 48)
    usable_h = max(540, work_h - 88)
    scale = min(1.0, usable_w / target_w, usable_h / target_h)
    width = _even(target_w * scale)
    height = _even(target_h * scale)
    origin_x = int(info["work_x"]) + max(0, int((work_w - width) / 2))
    origin_y = int(info["work_y"]) + max(0, int((work_h - height) / 2))
    return {
        "width": width,
        "height": height,
        "origin_x": origin_x,
        "origin_y": origin_y,
        "desktop_width": screen_w,
        "desktop_height": screen_h,
        "scaled_down": (width, height) != (target_w, target_h),
        "label": "holoverse_canvas_16x9_best_fit",
    }



def choose_reference_window_geometry(desktop: dict[str, int] | None = None) -> dict[str, int | str | bool]:
    """Resolve the normal StarFall window around the 1920x1080 reference canvas.

    Prefer an exact decorated 1920x1080 client when the OS work area can hold it.
    On a 1920x1080-class desktop where decorations/taskbar would force the client
    smaller, use an exact borderless 1920x1080 surface.  Smaller desktops fall
    back to the largest 16:9 decorated client that fits.
    """
    info = desktop or _detect_desktop_geometry()
    target_w, target_h = REFERENCE_WINDOW_SIZE
    if not info:
        return {
            "width": target_w,
            "height": target_h,
            "origin_x": 64,
            "origin_y": 40,
            "desktop_width": 0,
            "desktop_height": 0,
            "work_width": 0,
            "work_height": 0,
            "undecorated": False,
            "fixed_size": False,
            "scaled_down": False,
            "below_minimum": False,
            "label": "reference_1080p_no_desktop_probe",
        }

    screen_w = int(info.get("screen_width", 0))
    screen_h = int(info.get("screen_height", 0))
    work_x = int(info.get("work_x", 0))
    work_y = int(info.get("work_y", 0))
    work_w = max(int(info.get("work_width", screen_w)), 1)
    work_h = max(int(info.get("work_height", screen_h)), 1)

    decorated = choose_bordered_window_geometry(REFERENCE_WINDOW_SIZE) if desktop is None else None
    if desktop is not None:
        usable_w = max(960, work_w - 48)
        usable_h = max(540, work_h - 88)
        scale = min(1.0, usable_w / target_w, usable_h / target_h)
        dw = _even(target_w * scale)
        dh = _even(target_h * scale)
        decorated = {
            "width": dw, "height": dh,
            "origin_x": work_x + max(0, (work_w - dw) // 2),
            "origin_y": work_y + max(0, (work_h - dh) // 2),
        }

    assert decorated is not None
    if int(decorated["width"]) == target_w and int(decorated["height"]) == target_h:
        return {
            "width": target_w, "height": target_h,
            "origin_x": int(decorated["origin_x"]), "origin_y": int(decorated["origin_y"]),
            "desktop_width": screen_w, "desktop_height": screen_h,
            "work_width": work_w, "work_height": work_h,
            "undecorated": False, "fixed_size": False,
            "scaled_down": False, "below_minimum": False,
            "label": "reference_1080p_decorated",
        }

    if screen_w >= target_w and screen_h >= target_h:
        origin_x = max(0, (screen_w - target_w) // 2)
        origin_y = max(0, (screen_h - target_h) // 2)
        return {
            "width": target_w, "height": target_h,
            "origin_x": origin_x, "origin_y": origin_y,
            "desktop_width": screen_w, "desktop_height": screen_h,
            "work_width": work_w, "work_height": work_h,
            "undecorated": True, "fixed_size": True,
            "scaled_down": False, "below_minimum": False,
            "label": "reference_1080p_borderless_fit",
        }

    min_w, min_h = MIN_SUPPORTED_WINDOW_SIZE
    if screen_w >= min_w and screen_h >= min_h:
        scale = min(screen_w / target_w, screen_h / target_h)
        width = _even(target_w * scale)
        height = _even(target_h * scale)
        origin_x = max(0, (screen_w - width) // 2)
        origin_y = max(0, (screen_h - height) // 2)
        return {
            "width": width, "height": height,
            "origin_x": origin_x, "origin_y": origin_y,
            "desktop_width": screen_w, "desktop_height": screen_h,
            "work_width": work_w, "work_height": work_h,
            "undecorated": True, "fixed_size": True,
            "scaled_down": True, "below_minimum": width < min_w or height < min_h,
            "label": "reference_scaled_borderless_fit",
        }

    width = int(decorated["width"])
    height = int(decorated["height"])
    return {
        "width": width, "height": height,
        "origin_x": int(decorated["origin_x"]), "origin_y": int(decorated["origin_y"]),
        "desktop_width": screen_w, "desktop_height": screen_h,
        "work_width": work_w, "work_height": work_h,
        "undecorated": False, "fixed_size": False,
        "scaled_down": True,
        "below_minimum": width < MIN_SUPPORTED_WINDOW_SIZE[0] or height < MIN_SUPPORTED_WINDOW_SIZE[1],
        "label": "reference_1080p_scaled_fallback",
    }

def native_desktop_size() -> tuple[int, int]:
    info = _detect_desktop_geometry()
    if info:
        return int(info["screen_width"]), int(info["screen_height"])
    return DEFAULT_FULL_WINDOW_SIZE


def apply_panda_window_config(
    load_prc: DisplayLoader,
    title: str,
    argv: Iterable[str] | None = None,
    *,
    full_window_size: tuple[int, int] = DEFAULT_FULL_WINDOW_SIZE,
    windowed_size: tuple[int, int] = DEFAULT_WINDOWED_SIZE,
) -> str:
    """Apply one responsive display authority before ShowBase is created."""
    mode = requested_display_mode(argv)
    load_prc("", f"window-title {title}")
    load_prc("", "dpi-aware #t")
    load_prc("", "dpi-window-resize #t")

    if mode == "reference_1080p_window":
        geom = choose_reference_window_geometry()
        load_prc("", f"win-size {int(geom['width'])} {int(geom['height'])}")
        load_prc("", "fullscreen #f")
        load_prc("", f"undecorated {'#t' if bool(geom['undecorated']) else '#f'}")
        load_prc("", f"win-fixed-size {'#t' if bool(geom['fixed_size']) else '#f'}")
        load_prc("", f"win-origin {int(geom['origin_x'])} {int(geom['origin_y'])}")
    elif mode == "fullscreen":
        width, height = native_desktop_size()
        if (width, height) == DEFAULT_FULL_WINDOW_SIZE:
            width, height = full_window_size
        load_prc("", f"win-size {width} {height}")
        load_prc("", "fullscreen #t")
        load_prc("", "undecorated #f")
    elif mode == "windowed_fullscreen":
        width, height = native_desktop_size()
        load_prc("", f"win-size {width} {height}")
        load_prc("", "fullscreen #f")
        load_prc("", "undecorated #t")
        load_prc("", "win-fixed-size #t")
        load_prc("", "win-origin 0 0")
    elif mode == "desktop_resizable_window":
        geom = choose_desktop_window_geometry()
        load_prc("", f"win-size {int(geom['width'])} {int(geom['height'])}")
        load_prc("", "fullscreen #f")
        load_prc("", "undecorated #f")
        load_prc("", "win-fixed-size #f")
        load_prc("", f"win-origin {int(geom['origin_x'])} {int(geom['origin_y'])}")
    elif mode == "windowed":
        width, height = windowed_size
        load_prc("", f"win-size {width} {height}")
        load_prc("", "fullscreen #f")
        load_prc("", "undecorated #f")
        load_prc("", "win-fixed-size #f")
        load_prc("", "win-origin 80 56")
    elif mode == "safe_bordered_window":
        width, height = SAFE_BORDERED_WINDOW_SIZE
        load_prc("", f"win-size {width} {height}")
        load_prc("", "fullscreen #f")
        load_prc("", "undecorated #f")
        load_prc("", "win-fixed-size #f")
        load_prc("", "win-origin 80 56")
    else:
        target = LARGE_BORDERED_WINDOW_SIZE if mode == "large_bordered_window" else TARGET_BORDERED_WINDOW_SIZE
        geom = choose_bordered_window_geometry(target)
        load_prc("", f"win-size {int(geom['width'])} {int(geom['height'])}")
        load_prc("", "fullscreen #f")
        load_prc("", "undecorated #f")
        load_prc("", "win-fixed-size #f")
        load_prc("", f"win-origin {int(geom['origin_x'])} {int(geom['origin_y'])}")
    return mode


def display_contract_self_test(project_root: str | os.PathLike[str]) -> dict[str, object]:
    root = Path(project_root).resolve()
    simulated_1080 = {
        "screen_width": 1920, "screen_height": 1080,
        "work_x": 0, "work_y": 0, "work_width": 1920, "work_height": 1040,
    }
    simulated_1440 = {
        "screen_width": 2560, "screen_height": 1440,
        "work_x": 0, "work_y": 0, "work_width": 2560, "work_height": 1392,
    }
    simulated_720 = {
        "screen_width": 1280, "screen_height": 720,
        "work_x": 0, "work_y": 0, "work_width": 1280, "work_height": 680,
    }
    ref_1080 = choose_reference_window_geometry(simulated_1080)
    ref_1440 = choose_reference_window_geometry(simulated_1440)
    ref_720 = choose_reference_window_geometry(simulated_720)
    checks = {
        "reference_canvas_1920x1080": DESIGN_CANVAS_SIZE == (1920, 1080),
        "1080p_desktop_gets_exact_1080p": (int(ref_1080["width"]), int(ref_1080["height"])) == (1920, 1080),
        "1080p_taskbar_uses_borderless_not_downscale": bool(ref_1080["undecorated"]) and not bool(ref_1080["scaled_down"]),
        "larger_desktop_uses_decorated_exact_1080p": (int(ref_1440["width"]), int(ref_1440["height"])) == (1920, 1080) and not bool(ref_1440["undecorated"]),
        "minimum_desktop_preserves_1280x720": (int(ref_720["width"]), int(ref_720["height"])) == (1280, 720) and not bool(ref_720["below_minimum"]),
        "normal_default_not_exclusive_fullscreen": True,
        "borderless_fullscreen_still_explicit": "--windowed-fullscreen" in DISPLAY_FLAG_SET,
        "exclusive_fullscreen_still_explicit": "--fullscreen" in DISPLAY_FLAG_SET,
    }
    return {
        "contract": "operation_starfall_reference_1080p_window_v3",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "default_mode": "reference_1080p_window",
        "design_canvas_size": "1920x1080",
        "minimum_supported_size": "1280x720",
        "simulated_1080p": ref_1080,
        "simulated_1440p": ref_1440,
        "simulated_720p": ref_720,
        "rule": "Normal startup targets the 1920x1080 reference surface; it uses decorated 1080p when the work area can fit it, borderless 1080p on a 1080p-class desktop when decorations would force a downscale, and only scales below 1080p when the desktop itself is smaller.",
        "starfall_main_exists": (root.parent / "main.py").exists(),
        "shared_flags": ["--reference-window", "--1080p", "--desktop-window", "--bordered-window", "--large-window", "--safe-window", "--windowed", "--windowed-fullscreen", "--fullscreen"],
        "saved_settings_supported": _saved_display_mode() is not None or load_settings is not None,
    }
