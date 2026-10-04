"""Headless regression verifier for Entropy Pass 26 — Hazard Personality."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hazard_rules import FAMILIES, evaluate_hazard
from mission_state import HAZARD_FAMILY_BY_STYLE

checks = []

def req(condition, label, detail=None):
    ok = bool(condition)
    checks.append({"ok": ok, "label": label, "detail": detail})
    if not ok:
        raise AssertionError(label if detail is None else f"{label}: {detail}")

# All twelve established worlds remain covered exactly once.
req(len(HAZARD_FAMILY_BY_STYLE) == 12, "all 12 terrain styles have a hazard family")
for family in FAMILIES:
    styles = [s for s, fam in HAZARD_FAMILY_BY_STYLE.items() if fam == family]
    req(len(styles) == 3, f"{family} owns exactly three terrain styles", styles)

# HEAT: distance pressure, safe ship proximity, rig mitigation.
heat_near = evaluate_hazard("HEAT", distance_from_ship=8, elapsed_seconds=5, surface_rig_level=0)
heat_far = evaluate_hazard("HEAT", distance_from_ship=120, elapsed_seconds=5, surface_rig_level=0)
heat_rig = evaluate_hazard("HEAT", distance_from_ship=120, elapsed_seconds=5, surface_rig_level=3)
req(heat_near.severity < 0.05, "HEAT is effectively safe beside the landed ship")
req(heat_far.severity > heat_near.severity and heat_far.move_multiplier < 1.0, "HEAT rises with distance and slows traversal")
req(heat_rig.severity < heat_far.severity and heat_rig.move_multiplier > heat_far.move_multiplier, "Surface Rig mitigates HEAT")

# COLD: distance-based mobility drag, stronger than heat but still bounded/non-lethal.
cold_near = evaluate_hazard("COLD", distance_from_ship=8, elapsed_seconds=5, surface_rig_level=0)
cold_far = evaluate_hazard("COLD", distance_from_ship=140, elapsed_seconds=5, surface_rig_level=0)
cold_rig = evaluate_hazard("COLD", distance_from_ship=140, elapsed_seconds=5, surface_rig_level=3)
req(cold_near.move_multiplier > 0.98, "COLD preserves mobility near ship")
req(0.70 <= cold_far.move_multiplier < 0.80, "COLD creates a clear but bounded far-field mobility drag", cold_far.move_multiplier)
req(cold_rig.move_multiplier > cold_far.move_multiplier, "Surface Rig mitigates COLD")

# BIOLOGICAL: deterministic periodic bloom; find at least one active and one quiet second.
bio_frames = [evaluate_hazard("BIOLOGICAL", distance_from_ship=60, elapsed_seconds=t, seed=445, surface_rig_level=0) for t in [x * 0.5 for x in range(29)]]
active = [f for f in bio_frames if f.pulse_active]
quiet = [f for f in bio_frames if not f.pulse_active]
req(active and quiet, "BIOLOGICAL cycles between bloom and dormant states")
req(min(f.move_multiplier for f in active) < 0.90, "active spore bloom slows travel")
req(all(abs(f.move_multiplier - 1.0) < 1e-6 for f in quiet), "dormant biological phase does not slow travel")

# ANOMALOUS: close-range lock, long-range drift, never changes physical player speed.
ano_close = evaluate_hazard("ANOMALOUS", distance_from_ship=50, target_distance=10, elapsed_seconds=4.3, seed=777, surface_rig_level=0)
ano_far_samples = [evaluate_hazard("ANOMALOUS", distance_from_ship=50, target_distance=120, elapsed_seconds=t, seed=777, surface_rig_level=0) for t in (1.1, 2.7, 4.3, 5.9, 7.2)]
req(ano_close.severity == 0.0 and abs(ano_close.signal_angle_offset) < 1e-9, "ANOMALOUS signal resolves at close range")
req(max(abs(f.signal_angle_offset) for f in ano_far_samples) > 0.12, "ANOMALOUS creates meaningful long-range direction drift")
req(max(abs(f.signal_distance_multiplier - 1.0) for f in ano_far_samples) > 0.08, "ANOMALOUS creates meaningful long-range range drift")
req(all(abs(f.move_multiplier - 1.0) < 1e-6 for f in ano_far_samples), "ANOMALOUS does not stack a movement penalty")

# Global safety/balance bounds.
for family in FAMILIES:
    for lvl in range(4):
        for distance in (0, 20, 60, 120, 180):
            for t in (0.0, 5.0, 9.0, 13.0):
                f = evaluate_hazard(family, distance_from_ship=distance, target_distance=distance, elapsed_seconds=t, seed=91, surface_rig_level=lvl, storm_intensity=1.0)
                req(0.0 <= f.severity <= 1.0, f"{family} severity stays normalized")
                req(0.65 <= f.move_multiplier <= 1.0, f"{family} movement multiplier stays bounded")
                req(0.72 <= f.signal_distance_multiplier <= 1.28, f"{family} signal range multiplier stays bounded")

# Integration/source contracts: hazard is evaluated in update, affects walk speed,
# affects only objective presentation on anomalous worlds, and appears in HUD/UI.
terrain_src = (ROOT / "terrains.py").read_text(encoding="utf-8")
ui_src = (ROOT / "standard_ui.py").read_text(encoding="utf-8")
progress_src = (ROOT / "ship_progression.py").read_text(encoding="utf-8")
for path in (ROOT / "hazard_rules.py", ROOT / "terrains.py", ROOT / "standard_ui.py", ROOT / "ship_progression.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
req("self._evaluate_surface_hazard()" in terrain_src, "surface update evaluates hazard every frame")
req('surface_speed_multiplier(self.ship) * float(getattr(self.hazard_frame, "move_multiplier", 1.0))' in terrain_src, "hazard movement multiplier is applied to existing Surface Rig movement")
req('signal_angle_offset' in terrain_src and 'signal_distance_multiplier' in terrain_src, "anomalous signal drift is wired into objective presentation")
req("HAZARD {family}" in terrain_src and "HAZARD_SHORT_RULE" in ui_src, "hazard behavior is explained in surface HUD and mission brief")
req("HAZARD SHIELD" in progress_src, "Surface Rig upgrade copy exposes its new hazard protection")
req("player_hp" not in (ROOT / "hazard_rules.py").read_text(encoding="utf-8"), "surface hazards remain non-lethal and do not create a second health game")

out = {
    "pass": "Entropy Pass 26 — Hazard Personality",
    "status": "PASS",
    "checks_passed": sum(1 for c in checks if c["ok"]),
    "checks_total": len(checks),
    "families": list(FAMILIES),
    "rules": {
        "HEAT": "thermal load rises away from ship; high load slows traversal",
        "COLD": "distance-driven cryo drag reduces mobility",
        "BIOLOGICAL": "deterministic periodic spore blooms temporarily slow travel",
        "ANOMALOUS": "distant archive guidance drifts; close range resolves cleanly",
    },
    "surface_rig": "existing Surface Rig levels mitigate all hazard severity by 12/24/38 percent after level 0",
    "checks": checks,
}
report = ROOT / "verification" / "reports" / "pass26_hazard_personality.json"
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps({k: out[k] for k in ("pass", "status", "checks_passed", "checks_total")}, indent=2))
