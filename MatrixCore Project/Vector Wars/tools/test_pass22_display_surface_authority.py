#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "main.py").read_text(encoding="utf-8")

checks = {
    "pass22 identity": "0.9.0-pass22-display-surface-authority" in source,
    "present path reacquires current display": "current_display = pygame.display.get_surface()" in source[source.index("# Present to the display module's current Surface"):],
    "present path checks actual display size": "actual_w, actual_h = display.get_size()" in source,
    "viewport recomputed after external resize": "view_scale, view_size, view_off = _compute_viewport(win_w, win_h)" in source[source.index("# Present to the display module's current Surface"):],
    "pygame2 window size event supported": "WINDOWSIZECHANGED" in source and "WINDOWRESIZED" in source,
    "maximized event supported": "WINDOWMAXIMIZED" in source,
    "redundant maximize avoided when maximized flag available": "and not maximized_flag" in source,
    "startup frame uses current display surface": "boot_display = pygame.display.get_surface() or display" in source,
    "legacy video resize still supported": "pygame.VIDEORESIZE" in source,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("PASS" if ok else "FAIL"), name)
if failed:
    raise SystemExit("Pass22 display-surface contract failed: " + ", ".join(failed))
print("PASS22_DISPLAY_SURFACE_AUTHORITY: PASS")
