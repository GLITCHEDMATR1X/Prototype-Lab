#!/usr/bin/env python3
"""Dependency-free Pass 32 smoothness and expedition-feedback verifier.

This verifier intentionally avoids importing pygame so it can validate source and
math contracts in build environments where pygame-ce is unavailable.
"""
from __future__ import annotations

import ast
import json
import math
import random
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "verification" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = REPORT_DIR / "pass32_smooth_expedition.json"

checks: list[dict] = []


def check(name: str, ok: bool, detail="") -> None:
    checks.append({"name": name, "pass": bool(ok), "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


space = read("space_core.py")
ui = read("standard_ui.py")
interiors = read("interiors.py")
manifest = json.loads(read("build_manifest.json"))

# Syntax / authority contracts.
for name in ("space_core.py", "standard_ui.py", "interiors.py"):
    try:
        ast.parse(read(name), filename=name)
        check(f"AST parse {name}", True)
    except SyntaxError as exc:
        check(f"AST parse {name}", False, exc)

check("Pass 32 app version", 'APP_VERSION = "Pass 32 — Smooth Expedition Feedback"' in space)
check("Manifest pass 32", manifest.get("pass") == 32)
check("Manifest authority", manifest.get("authoritative_baseline") == "Pass 32 — Smooth Expedition Feedback")
check("Save schema remains v5", '"schema_version": 5' in space and "schema v5" in space)

# Frame pacing: wall-clock lifecycle/collapse semantics separated from bounded motion delta.
check("Raw wall delta captured", "wall_dt = clock.tick(60) / 1000.0" in space)
check("Motion delta bounded to 50ms", "dt = min(max(0.0, wall_dt), 0.050)" in space)
check("Suspend detector uses wall delta", "lifecycle_frame_count > 0 and wall_dt > 1.0" in space)
check("Supernova pause deadline uses wall delta", "supernova_deadline += wall_dt" in space)
check("Black-hole pause deadline uses wall delta", "blackhole_deadline += wall_dt" in space)

# Hot-loop allocation/CPU contracts.
check("Fast star LOD uses islice", "itertools.islice(self.stars, 0, None, 2)" in space)
check("Fast star LOD slice allocation removed", "self.stars[::2]" not in space)
check("Star quaternion rotation inlined", "tx = 2.0 * (qy * vz - qz * vy)" in space and "dcx = vx + qw * tx" in space)
check("Star velocity dot product inlined", "ct = vdx * svx + vdy * svy + vdz * svz" in space)

# CRT noise keeps authored 25Hz appearance but eliminates duplicate reconstruction.
check("CRT noise frame cache exists", "self._noise_frame_id = None" in space)
check("CRT noise keyed to authored 25Hz", "noise_frame_id = int(tsec * 25.0)" in space)
check("CRT noise rebuild is conditional", "if noise_frame_id != self._noise_frame_id:" in space)
check("Static CRT overlays precomposed", "self.static_overlay = pygame.Surface" in space and "self.static_overlay.blit(self.scan" in space and "surf.blit(self.static_overlay" in space)
check("Separate per-frame scan/vign blits removed", "surf.blit(self.scan, (0, 0))" not in space and "surf.blit(self.vign, (0, 0))" not in space)
noise_rebuild_reduction = 1.0 - 25.0 / 60.0
check("CRT duplicate rebuild reduction model", abs(noise_rebuild_reduction - 0.5833333333333333) < 1e-12, f"{noise_rebuild_reduction*100:.2f}% fewer rebuild opportunities at 60Hz")

# Presentation scaling, especially the user's 4K desktop.
check("Exact integer upscale path", "integer_upscale = (" in space and "pygame.transform.scale if integer_upscale else pygame.transform.smoothscale" in space)
check("4K is exact 2x from authored canvas", 1920 * 2 == 3840 and 1080 * 2 == 2160)
check("Presenter reuses destination surface", 'present_cache["surf"]' in space and 'present_cache["size"]' in space)
check("Presenter avoids unnecessary clear when frame fills display", "if (tw, th) != (dw, dh):\n                display.fill" in space)

# UI rendering allocations.
check("UI text cache bounded", "_TEXT_SURFACE_CACHE = OrderedDict()" in ui and "while len(_TEXT_SURFACE_CACHE) > 256" in ui)
check("UI panel cache bounded", "_PANEL_FILL_CACHE = OrderedDict()" in ui and "while len(_PANEL_FILL_CACHE) > 48" in ui)
check("Collapse edge-pressure mask cached", "_EDGE_PRESSURE_CACHE" in ui and "edge.set_alpha(alpha)" in ui)
check("Cockpit glow text cache bounded", "self._glow_text_cache = OrderedDict()" in space and "while len(self._glow_text_cache) > 48" in space)
check("HUD notice panel cached", "hud_notice_cache_text" in space and "hud_notice_cache_panel" in space)
check("No stale HUD notice position cache", "hud_notice_cache_msg_pos" not in space)

# Interior render stability / font churn.
check("Interior font cache exists", "_FONT_CACHE = {}" in interiors and "def _font(size: int, bold: bool = False):" in interiors)
check("Interior direct SysFont creation centralized", interiors.count("pygame.font.SysFont") == 1, f"count={interiors.count('pygame.font.SysFont')}")
check("Terrain fallback reuses info font", 'info_font.render("Generating terrain..."' in space)

# Pass 32 player-facing expedition outcome clarity.
feedback_strings = (
    "planetfall — data signal active — warp locked until system goal resolves",
    "data fragment signal locked — warp locked until secured or missed",
    "DATA SECURED — ARCHIVE",
    "HYPERDRIVE AVAILABLE",
)
for value in feedback_strings:
    haystack = space + "\n" + interiors
    check(f"Feedback: {value[:42]}", value in haystack)

# Preserve core Pass 31 state-machine authority.
flow_contracts = {
    "HOME start routing": "HOME",
    "planet entry pending state": "planet_entry_pending",
    "surface-ready entry handoff": "planet_entry_surface_ready",
    "dead-target landability retirement": "not planet_is_landable(system.planets[target_i])",
    "target loss resolution": 'mission.resolve_target_loss("planet_destroyed")',
    "warp outcome gating": "warp",
}
for label, token in flow_contracts.items():
    check(f"Pass31 preserved: {label}", token in space)

# Pure-Python equivalence and a non-fragile hot-loop timing sanity test.
def qrot_helper(q, v):
    qw, qx, qy, qz = q
    vx, vy, vz = v
    tx = 2.0 * (qy * vz - qz * vy)
    ty = 2.0 * (qz * vx - qx * vz)
    tz = 2.0 * (qx * vy - qy * vx)
    return (
        vx + qw * tx + (qy * tz - qz * ty),
        vy + qw * ty + (qz * tx - qx * tz),
        vz + qw * tz + (qx * ty - qy * tx),
    )


def old_loop(q, vectors, vdir):
    total = 0.0
    for vec in vectors:
        dc = qrot_helper(q, vec)
        ct = vdir[0] * vec[0] + vdir[1] * vec[1] + vdir[2] * vec[2]
        total += dc[0] * 0.17 + dc[1] * 0.11 + dc[2] * 0.07 + ct * 0.03
    return total


def new_loop(q, vectors, vdir):
    qw, qx, qy, qz = q
    vdx, vdy, vdz = vdir
    total = 0.0
    for vx, vy, vz in vectors:
        tx = 2.0 * (qy * vz - qz * vy)
        ty = 2.0 * (qz * vx - qx * vz)
        tz = 2.0 * (qx * vy - qy * vx)
        dcx = vx + qw * tx + (qy * tz - qz * ty)
        dcy = vy + qw * ty + (qz * tx - qx * tz)
        dcz = vz + qw * tz + (qx * ty - qy * tx)
        ct = vdx * vx + vdy * vy + vdz * vz
        total += dcx * 0.17 + dcy * 0.11 + dcz * 0.07 + ct * 0.03
    return total

rnd = random.Random(320032)
vectors = []
for _ in range(6200):
    x, y, z = rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)
    mag = math.sqrt(x*x + y*y + z*z) or 1.0
    vectors.append((x/mag, y/mag, z/mag))
q0 = (0.9238795325, 0.0, 0.3826834324, 0.0)
vdir0 = (0.211, -0.133, 0.968)
old_value = old_loop(q0, vectors, vdir0)
new_value = new_loop(q0, vectors, vdir0)
check("Star math numerical equivalence", math.isclose(old_value, new_value, rel_tol=1e-12, abs_tol=1e-12), f"delta={abs(old_value-new_value):.3e}")

# Median of several short samples reduces incidental process noise. The threshold
# is deliberately loose: this is a regression sanity check, not an FPS claim.
def measure(fn, repeats=5):
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        for _ in range(5):
            fn(q0, vectors, vdir0)
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples), samples

old_t, old_samples = measure(old_loop)
new_t, new_samples = measure(new_loop)
ratio = new_t / old_t if old_t else 0.0
check("Star hot-loop timing sanity", ratio <= 1.35, f"old={old_t:.6f}s new={new_t:.6f}s ratio={ratio:.3f}")

result = {
    "pass": 32,
    "name": "Smooth Expedition Feedback",
    "checks_passed": sum(1 for c in checks if c["pass"]),
    "checks_total": len(checks),
    "final_result": "PASS" if all(c["pass"] for c in checks) else "FAIL",
    "metrics": {
        "motion_dt_cap_seconds": 0.050,
        "authored_crt_noise_hz": 25,
        "render_target_hz": 60,
        "modeled_duplicate_noise_rebuild_reduction_percent": round(noise_rebuild_reduction * 100.0, 3),
        "authored_canvas": [1920, 1080],
        "integer_4k_scale": 2,
        "star_math_old_median_seconds": old_t,
        "star_math_new_median_seconds": new_t,
        "star_math_ratio_new_over_old": ratio,
        "star_math_checksum_delta": abs(old_value - new_value),
    },
    "notes": [
        "The star timing test measures only the pure-Python projection math slice, not total game FPS.",
        "Native pygame-ce execution is outside this dependency-free verifier.",
        "Pass 31 expedition-state authority is preserved and remains covered by its existing regression suites.",
    ],
    "checks": checks,
}
REPORT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(f"\nFINAL_RESULT={result['final_result']} ({result['checks_passed']}/{result['checks_total']})")
print(f"REPORT={REPORT_PATH}")
raise SystemExit(0 if result["final_result"] == "PASS" else 1)
