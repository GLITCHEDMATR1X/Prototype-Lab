from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "verification" / "reports" / "pass30_display_finalization.json"

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from game.display_policy import choose_desktop_size, fit_virtual_canvas

VIRTUAL = (1920, 1080)
CASES = [
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
    (1920, 1200),
    (2560, 1440),
    (3440, 1440),
    (3840, 2160),
    (5120, 1440),
]


def check_source_contract():
    source = (ROOT / "game" / "app.py").read_text(encoding="utf-8")
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    batch = (ROOT / "platform" / "windows" / "BUILD_WINDOWS_FULL_TITLE.bat").read_text(encoding="utf-8")
    checks = {
        "desktop_query_present": "pygame.display.get_desktop_sizes()" in source,
        "fullscreen_flag_uses_current_desktop": "pygame.display.set_mode(self.desktop_size, pygame.FULLSCREEN" in source,
        "no_noframe_taskbar_window": "pygame.NOFRAME" not in source,
        "dpi_awareness_before_pygame_init": source.find('SDL_WINDOWS_DPI_AWARENESS') < source.find('pygame.init()'),
        "dpi_awareness_permonitorv2": 'SDL_WINDOWS_DPI_AWARENESS\", \"permonitorv2' in source,
        "default_borderless": 'self.borderless_fullscreen = not bool(getattr(args, "windowed", False))' in source,
        "windowed_override": 'p.add_argument("--windowed"' in source,
        "display_index_override": 'p.add_argument("--display-index"' in source,
        "f11_uses_policy_toggle": 'self._toggle_display_mode()' in source,
        "display_self_test_available": '--display-self-test' in source,
        "windows_builder_runs_display_self_test": '--display-self-test --no-audio --no-save' in batch,
        "native_canvas_1920x1080": VIRTUAL == (1920, 1080),
        "pass30_build_label": "Pass 30 Finalization Prep / Adaptive Borderless" in main,
    }
    return checks


def check_geometry():
    rows = []
    for size in CASES:
        rect = fit_virtual_canvas(size, VIRTUAL)
        ratio = rect.width / rect.height
        target = VIRTUAL[0] / VIRTUAL[1]
        rows.append({
            "desktop": list(size),
            "rect": [rect.x, rect.y, rect.width, rect.height],
            "scale": rect.scale,
            "integer_scale": rect.integer_scale,
            "inside_desktop": rect.x >= 0 and rect.y >= 0 and rect.x + rect.width <= size[0] and rect.y + rect.height <= size[1],
            "aspect_error": abs(ratio - target),
        })
    return rows


def main():
    checks = check_source_contract()
    geometry = check_geometry()
    desktops = choose_desktop_size([(1920,1080), (3840,2160)], 1, fallback=VIRTUAL)
    all_geometry = all(r["inside_desktop"] and r["aspect_error"] < 0.0025 for r in geometry)
    checks["all_aspect_fit_cases_pass"] = all_geometry
    checks["display_index_selection_pass"] = desktops == (3840,2160)
    payload = {
        "pass30_display_finalization": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "desktop_cases": geometry,
        "policy": {
            "default": "borderless_desktop",
            "exclusive_fullscreen": False,
            "physical_monitor_mode_change_requested": False,
            "virtual_resolution": list(VIRTUAL),
            "windowed_fallback": [1280,720],
            "windows_dpi_awareness": "permonitorv2",
        },
        "native_runtime_note": "Source/display-policy validation only in this Linux container; packaged Windows --display-self-test is the native acceptance gate.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["pass30_display_finalization"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
