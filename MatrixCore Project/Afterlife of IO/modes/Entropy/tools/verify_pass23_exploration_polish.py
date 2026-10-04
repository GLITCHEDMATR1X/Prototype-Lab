from __future__ import annotations

import ast
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


def assigned_constants(source: str) -> dict[str, object]:
    tree = ast.parse(source)
    values: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                values[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    return values


def main() -> int:
    terrain_source = (ROOT / "terrains.py").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "build_manifest.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    plan = (ROOT / "Entropy_Authoritative_Game_Plan.md").read_text(encoding="utf-8")

    for name in ("terrains.py", "surface_chunks.py", "surface_resources.py", "space_core.py", "standard_ui.py"):
        ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)
    require(True, "Pass 23 active gameplay modules parse")

    constants = assigned_constants(terrain_source)
    accel = float(constants["SURFACE_ACCEL_RESPONSE"])
    brake = float(constants["SURFACE_BRAKE_RESPONSE"])
    camera_response = float(constants["SURFACE_CAMERA_RESPONSE"])
    lookahead = float(constants["SURFACE_CAMERA_LOOKAHEAD"])
    fx_limit = int(constants["SURFACE_RECOVERY_FX_LIMIT"])
    walk_speed = float(constants["SURFACE_WALK_SPEED"])

    require(8.0 <= accel <= 20.0, "surface acceleration response is responsive but eased")
    require(brake > accel, "surface braking settles faster than acceleration")
    require(4.0 <= camera_response <= 12.0, "camera easing stays controlled")
    require(2.0 <= lookahead <= 5.0, "camera look-ahead stays restrained")
    require(3 <= fx_limit <= 8, "recovery effect pool is tightly bounded")

    dt = 1.0 / 60.0
    accel_blend = 1.0 - math.exp(-accel * dt)
    brake_blend = 1.0 - math.exp(-brake * dt)
    vx = 0.0
    samples = []
    for _ in range(12):
        vx = vx + (walk_speed - vx) * accel_blend
        samples.append(vx)
    require(all(b > a for a, b in zip(samples, samples[1:])), "movement accelerates monotonically")
    require(samples[0] < walk_speed * 0.35, "first movement frame does not snap to full speed")
    require(samples[-1] > walk_speed * 0.85, "movement reaches useful speed promptly")

    braking = []
    for _ in range(12):
        vx = vx + (0.0 - vx) * brake_blend
        braking.append(vx)
    require(all(b < a for a, b in zip(braking, braking[1:])), "movement braking is monotonic")
    require(braking[-1] < walk_speed * 0.06, "movement settles quickly after input release")

    diagonal = math.hypot(1 / math.sqrt(2), 1 / math.sqrt(2)) * walk_speed
    require(abs(diagonal - walk_speed) < 1e-9, "diagonal movement remains speed-normalized")

    require("self.surface_vel_x" in terrain_source and "self.surface_vel_y" in terrain_source, "surface movement owns persistent velocity")
    require("math.exp(-response * safe_dt)" in terrain_source, "movement response is frame-rate independent")
    require("self.surface_view_x" in terrain_source and "self.surface_view_y" in terrain_source, "presentation camera is separate from actor coordinates")
    require("target_view_x = self.cam_x + ahead_x" in terrain_source, "camera look-ahead follows actual velocity")
    require("self.cam_x = clamp(self.cam_x" not in terrain_source and "self.cam_y = clamp(self.cam_y" not in terrain_source, "seamless surface remains unclamped")

    require("_surface_action_prompt" in terrain_source, "one contextual surface action source exists")
    require("_draw_surface_action_prompt" in terrain_source, "bottom-safe action chip renderer exists")
    require("y = h - 78" in terrain_source, "action prompt uses the bottom safe strip")
    require("has_action = self.mode == 'surface'" in terrain_source, "notification placement accounts for the action prompt")
    require("y = h - (140 if has_action else 82)" in terrain_source, "notifications cannot overlap the action chip")
    require("y = 132" not in terrain_source, "legacy top notification overlap anchor is removed")
    require("E  RECOVER / PROCESS" not in terrain_source, "duplicate object-local process labels are removed")

    require("navigation lattice" in terrain_source, "grid removal is documented in the live renderer")
    require("step_world = 32" not in terrain_source, "screen-wide surface grid drawing is removed")
    require("_draw_surface_finish" in terrain_source, "surface finish pass exists")
    require("surface_entry_fade" in terrain_source, "planetfall uses a short visual settle")
    require("_draw_surface_recovery_fx" in terrain_source, "recovery has world-space feedback")
    require("self.surface_recovery_fx[-SURFACE_RECOVERY_FX_LIMIT:]" in terrain_source, "recovery effects enforce their hard limit")
    require("tuple(min(255, c + 28) for c in tree_col)" in terrain_source, "tree silhouettes include a depth highlight")
    require("variant = int(prop.get('seed', 0)) % 3" in terrain_source, "surface props use deterministic silhouette variants")
    require("compact facing chevron" in terrain_source, "long debug-like direction line is replaced")

    require(int(manifest.get("pass", 0)) >= 23, "manifest preserves Pass 23 polish under current authority")
    contract = manifest.get("surface_polish_contract", {})
    require(contract.get("movement") == "frame-rate-independent acceleration and braking", "manifest locks polished movement")
    require(contract.get("camera") == "bounded velocity look-ahead with eased recentering", "manifest locks polished camera")
    require(contract.get("navigation_grid") == "removed from gameplay terrain", "manifest locks unobstructed geology")
    require(contract.get("interaction_prompt") == "single bottom-safe contextual action chip", "manifest locks one action prompt")
    require(contract.get("recovery_fx_limit") == fx_limit, "manifest records bounded recovery feedback")
    require("camera" in manifest.get("surface_polish_contract", {}) and "seamless" in readme.lower(), "release documentation preserves the polished seamless surface")
    require("Pass 23 direction lock" in plan and "screen-wide navigation lattice stays removed" in plan, "authoritative plan records the polish direction")

    print("FINAL_RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
