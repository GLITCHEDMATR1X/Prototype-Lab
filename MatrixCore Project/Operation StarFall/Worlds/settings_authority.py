from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Any

SETTINGS_SCHEMA = "operation_starfall_windows_optimization_v0.3"
SETTINGS_RELATIVE_PATH = Path("settings") / "starfall_user_settings.json"

WINDOW_PRESETS: dict[str, dict[str, Any]] = {
    "reference_1080p_auto": {"label": "1080p Reference / Best Fit", "mode": "reference_1080p_window", "width": 1920, "height": 1080, "decorated": True, "fullscreen": False, "fixed_16x9": True, "resizable": True},
    "desktop_resizable": {"label": "Desktop Fit - Resizable", "mode": "desktop_resizable_window", "width": 0, "height": 0, "decorated": True, "fullscreen": False, "fixed_16x9": False, "resizable": True},
    "bordered_1600x900": {"label": "Bordered 1600x900", "mode": "standard_bordered_window", "width": 1600, "height": 900, "decorated": True, "fullscreen": False, "fixed_16x9": True, "resizable": True},
    "bordered_1920x1080": {"label": "Bordered 1920x1080 best fit", "mode": "large_bordered_window", "width": 1920, "height": 1080, "decorated": True, "fullscreen": False, "fixed_16x9": True, "resizable": True},
    "safe_1440x810": {"label": "Safe bordered 1440x810", "mode": "safe_bordered_window", "width": 1440, "height": 810, "decorated": True, "fullscreen": False, "fixed_16x9": True, "resizable": True},
    "compact_1280x720": {"label": "Compact bordered 1280x720", "mode": "windowed", "width": 1280, "height": 720, "decorated": True, "fullscreen": False, "fixed_16x9": True, "resizable": True},
    "borderless_desktop": {"label": "Borderless Native Desktop", "mode": "windowed_fullscreen", "width": 0, "height": 0, "decorated": False, "fullscreen": False, "fixed_16x9": False, "resizable": False},
    # Legacy names remain readable so older profiles migrate cleanly instead of failing to launch.
    "borderless_1920x1080": {"label": "Legacy Borderless 1920x1080", "mode": "windowed_fullscreen", "width": 1920, "height": 1080, "decorated": False, "fullscreen": False, "fixed_16x9": True, "resizable": False},
    "exclusive_1920x1080": {"label": "Exclusive fullscreen", "mode": "fullscreen", "width": 0, "height": 0, "decorated": False, "fullscreen": True, "fixed_16x9": False, "resizable": False},
}

PERFORMANCE_PROFILES: dict[str, dict[str, Any]] = {
    "PERFORMANCE": {"label": "Performance", "bloom": False, "multisamples": 0, "sync_video": False, "show_frame_rate_meter": True, "scanner_draw_interval": 0.090, "status_draw_interval": 0.075, "sky_moon_update_interval": 0.52, "rover_visual_interval": 0.180, "transfer_visual_interval": 0.220, "hazard_delay_multiplier": 1.35, "texture_power_2": "up", "fx_density": 0.70},
    "BALANCED": {"label": "Balanced", "bloom": True, "multisamples": 2, "sync_video": False, "show_frame_rate_meter": True, "scanner_draw_interval": 0.060, "status_draw_interval": 0.050, "sky_moon_update_interval": 0.28, "rover_visual_interval": 0.100, "transfer_visual_interval": 0.120, "hazard_delay_multiplier": 1.00, "texture_power_2": "none", "fx_density": 1.00},
    "PRESENTATION": {"label": "Presentation", "bloom": True, "multisamples": 4, "sync_video": False, "show_frame_rate_meter": True, "scanner_draw_interval": 0.045, "status_draw_interval": 0.040, "sky_moon_update_interval": 0.16, "rover_visual_interval": 0.070, "transfer_visual_interval": 0.090, "hazard_delay_multiplier": 0.90, "texture_power_2": "none", "fx_density": 1.15},
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "schema": SETTINGS_SCHEMA,
    "display_preset": "reference_1080p_auto",
    "performance_profile": "BALANCED",
    "hud_style": "MINIMAL",
    "audio_enabled": True,
    "bloom_enabled": True,
    "planet_vision_default": "ANALYTIC",
    "ui_canvas": "responsive_aspect_safe",
    "window_fixed_16x9": True,
    "last_updated_by_pass": "Pass102_Reference1080pAuthority",
}

DISPLAY_MODE_TO_PRESET = {
    "reference_1080p_window": "reference_1080p_auto",
    "desktop_resizable_window": "desktop_resizable",
    "standard_bordered_window": "bordered_1600x900",
    "large_bordered_window": "bordered_1920x1080",
    "safe_bordered_window": "safe_1440x810",
    "windowed": "compact_1280x720",
    "windowed_fullscreen": "borderless_desktop",
    "fullscreen": "exclusive_1920x1080",
}

PROFILE_FLAG_MAP = {
    "--performance": "PERFORMANCE",
    "--fast": "PERFORMANCE",
    "--balanced": "BALANCED",
    "--quality": "PRESENTATION",
    "--presentation": "PRESENTATION",
}


def _argv_list(argv: Iterable[str] | None) -> list[str]:
    return [str(arg) for arg in (argv or [])]


def settings_path(project_root: str | os.PathLike[str]) -> Path:
    return Path(project_root).resolve() / SETTINGS_RELATIVE_PATH


def load_settings(project_root: str | os.PathLike[str]) -> dict[str, Any]:
    path = settings_path(project_root)
    data = dict(DEFAULT_SETTINGS)
    loaded_raw: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                loaded_raw = dict(loaded)
                data.update({k: v for k, v in loaded.items() if k in DEFAULT_SETTINGS or k == "schema"})
        except Exception:
            data["settings_load_warning"] = "failed_to_read_user_settings"

    loaded_schema = str(loaded_raw.get("schema", data.get("schema", "")))
    loaded_preset = str(loaded_raw.get("display_preset", data.get("display_preset", "")))
    loaded_pass = str(loaded_raw.get("last_updated_by_pass", ""))

    # Pass102 migration: only migrate the exact shipped Pass97 default profile.
    # Other saved display choices remain user authority.
    if (
        loaded_schema == "operation_starfall_windows_optimization_v0.2"
        and loaded_preset == "desktop_resizable"
        and loaded_pass == "Pass97_DisplayWindowAuthority"
    ):
        data["display_preset"] = "reference_1080p_auto"
        data["window_fixed_16x9"] = True
        data["last_updated_by_pass"] = "Pass102_Reference1080pAuthority"

    # Older fixed 1920x1080 borderless profiles still migrate away from that
    # legacy behavior unless the user explicitly selects a current preset later.
    if loaded_schema not in {SETTINGS_SCHEMA, "operation_starfall_windows_optimization_v0.2"} and loaded_preset == "borderless_1920x1080":
        data["display_preset"] = "reference_1080p_auto"
        data["window_fixed_16x9"] = True

    data["schema"] = SETTINGS_SCHEMA
    if str(data.get("display_preset")) not in WINDOW_PRESETS:
        data["display_preset"] = DEFAULT_SETTINGS["display_preset"]
    profile = str(data.get("performance_profile", "BALANCED")).upper()
    data["performance_profile"] = profile if profile in PERFORMANCE_PROFILES else "BALANCED"
    return data


def save_settings(project_root: str | os.PathLike[str], settings: dict[str, Any]) -> Path:
    path = settings_path(project_root)
    merged = dict(DEFAULT_SETTINGS)
    merged.update({k: v for k, v in settings.items() if k in DEFAULT_SETTINGS or k == "schema"})
    merged["schema"] = SETTINGS_SCHEMA
    if str(merged.get("display_preset")) not in WINDOW_PRESETS:
        merged["display_preset"] = DEFAULT_SETTINGS["display_preset"]
    profile = str(merged.get("performance_profile", "BALANCED")).upper()
    merged["performance_profile"] = profile if profile in PERFORMANCE_PROFILES else "BALANCED"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")
    return path


def default_settings_file(project_root: str | os.PathLike[str]) -> Path:
    return save_settings(project_root, DEFAULT_SETTINGS)


def arg_performance_profile(argv: Iterable[str] | None = None) -> str | None:
    args = _argv_list(argv)
    for arg in args:
        if arg in PROFILE_FLAG_MAP:
            return PROFILE_FLAG_MAP[arg]
        if arg.startswith("--performance-profile=") or arg.startswith("--render-profile="):
            value = arg.split("=", 1)[1].strip().upper()
            return value if value in PERFORMANCE_PROFILES else None
    env = os.environ.get("STARFALL_PERFORMANCE_PROFILE") or os.environ.get("STARFALL_DETAIL")
    if env:
        value = env.strip().upper()
        if value in {"FAST", "LOW", "60", "60FPS"}:
            return "PERFORMANCE"
        if value in {"QUALITY", "HIGH"}:
            return "PRESENTATION"
        if value in PERFORMANCE_PROFILES:
            return value
    return None


def resolved_performance_profile(project_root: str | os.PathLike[str], argv: Iterable[str] | None = None) -> str:
    return arg_performance_profile(argv) or str(load_settings(project_root).get("performance_profile", "BALANCED")).upper()


def performance_profile_data(profile: str | None) -> dict[str, Any]:
    key = str(profile or "BALANCED").upper()
    return dict(PERFORMANCE_PROFILES.get(key, PERFORMANCE_PROFILES["BALANCED"]))


def apply_prc_optimization(load_prc, project_root: str | os.PathLike[str], argv: Iterable[str] | None = None, *, headless: bool = False) -> str:
    profile = resolved_performance_profile(project_root, argv)
    data = performance_profile_data("PERFORMANCE" if headless else profile)
    load_prc("", f"sync-video {'1' if bool(data.get('sync_video')) else '0'}")
    load_prc("", f"show-frame-rate-meter {'true' if bool(data.get('show_frame_rate_meter')) and not headless else 'false'}")
    msaa = int(data.get("multisamples", 0) or 0)
    load_prc("", f"framebuffer-multisample {1 if msaa > 0 else 0}")
    load_prc("", f"multisamples {msaa}")
    load_prc("", "garbage-collect-states true")
    load_prc("", "state-cache true")
    load_prc("", "transform-cache true")
    load_prc("", f"textures-power-2 {data.get('texture_power_2', 'none')}")
    return profile


def display_preset_from_mode(mode: str) -> str:
    return DISPLAY_MODE_TO_PRESET.get(str(mode), DEFAULT_SETTINGS["display_preset"])


def mode_from_display_preset(preset: str) -> str:
    return str(WINDOW_PRESETS.get(str(preset), WINDOW_PRESETS[DEFAULT_SETTINGS["display_preset"]]).get("mode", "standard_bordered_window"))


def optimization_contract_self_test(project_root: str | os.PathLike[str]) -> dict[str, Any]:
    root = Path(project_root).resolve()
    settings = load_settings(root)
    required_profiles = {"PERFORMANCE", "BALANCED", "PRESENTATION"}
    required_windows = {"reference_1080p_auto", "desktop_resizable", "bordered_1600x900", "bordered_1920x1080", "safe_1440x810", "compact_1280x720", "borderless_desktop"}
    source = Path(__file__).read_text(encoding="utf-8")
    fixed_presets = [v for v in WINDOW_PRESETS.values() if bool(v.get("fixed_16x9")) and int(v.get("width", 0)) > 0 and int(v.get("height", 0)) > 0]
    checks = {
        "schema_current": SETTINGS_SCHEMA == "operation_starfall_windows_optimization_v0.3",
        "settings_file_exists_or_defaultable": settings_path(root).exists() or bool(DEFAULT_SETTINGS),
        "performance_profiles_complete": required_profiles <= set(PERFORMANCE_PROFILES),
        "window_presets_complete": required_windows <= set(WINDOW_PRESETS),
        "fixed_presets_keep_16x9": all(abs((float(v["width"]) / max(float(v["height"]), 1.0)) - (16.0 / 9.0)) < 0.02 for v in fixed_presets),
        "default_reference_1080p": DEFAULT_SETTINGS.get("display_preset") == "reference_1080p_auto" and WINDOW_PRESETS["reference_1080p_auto"].get("mode") == "reference_1080p_window",
        "borderless_native_preset_exists": WINDOW_PRESETS["borderless_desktop"].get("mode") == "windowed_fullscreen",
        "default_not_exclusive_fullscreen": DEFAULT_SETTINGS.get("display_preset") != "exclusive_1920x1080",
        "prc_optimization_hook_exists": "apply_prc_optimization" in source,
        "package_checker_exists": (root / "tools" / "starfall_package_check.py").exists(),
    }
    return {
        "schema": SETTINGS_SCHEMA,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "settings_path": str(settings_path(root)),
        "active_settings": settings,
        "window_presets": WINDOW_PRESETS,
        "performance_profiles": PERFORMANCE_PROFILES,
        "rule": "Operation StarFall uses 1920x1080 as its normal reference surface, with an automatic smaller-screen fallback; legacy desktop-fit and borderless modes remain explicit options.",
    }

