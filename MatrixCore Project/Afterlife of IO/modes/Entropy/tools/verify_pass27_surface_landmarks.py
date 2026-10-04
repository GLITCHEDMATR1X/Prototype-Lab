"""Headless verifier for Entropy Pass 27 — Surface Landmark Identity."""
from __future__ import annotations

import ast
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from surface_landmarks import LANDMARK_PROFILES, LANDMARK_TERRAINS, generate_landmarks

checks = []

def req(condition, label, detail=None):
    ok = bool(condition)
    checks.append({"ok": ok, "label": label, "detail": detail})
    if not ok:
        raise AssertionError(label if detail is None else f"{label}: {detail}")

# Twelve established world families each receive one authored visual identity.
expected = {"desert", "ice", "jungle", "volcanic", "crystal", "oceanic", "fungal", "rust", "salt", "abyss", "storm", "roseglass"}
req(set(LANDMARK_TERRAINS) == expected, "all 12 terrain families have a landmark profile", sorted(LANDMARK_TERRAINS))
req(len({p.kind for p in LANDMARK_PROFILES.values()}) == 12, "all 12 terrain families use distinct landmark silhouettes")
req(len({p.title for p in LANDMARK_PROFILES.values()}) == 12, "all 12 terrain families use distinct landmark names")

# Determinism, spacing and clear-route constraints across a broad seed matrix.
ship = (198.0, 200.0)
structure_sets = []
for offset in range(8):
    structure_sets.append(tuple((72.0 + ((i * 37 + offset * 11) % 238), 68.0 + ((i * 43 + offset * 17) % 244)) for i in range(9)))

layout_count = 0
for terrain_index, terrain in enumerate(sorted(expected)):
    for seed in range(1, 121):
        structures = structure_sets[(seed + terrain_index) % len(structure_sets)]
        first = generate_landmarks(seed * 1009 + terrain_index, terrain, ship, structures, count=3)
        second = generate_landmarks(seed * 1009 + terrain_index, terrain, ship, structures, count=3)
        req(first == second, f"{terrain} landmark generation is deterministic", seed)
        req(len(first) >= 2, f"{terrain} always produces at least two readable anchors", seed)
        req(first[0].primary, f"{terrain} first anchor is primary", seed)
        req(first[0].scale > min(x.scale for x in first[1:]), f"{terrain} primary anchor is visually dominant", seed)
        for lm in first:
            req(30.0 <= lm.x <= 354.0 and 30.0 <= lm.y <= 354.0, f"{terrain} landmarks stay inside world margin", (seed, lm.x, lm.y))
            req(math.hypot(lm.x - ship[0], lm.y - ship[1]) >= 38.0, f"{terrain} landmarks preserve the ship landing zone", seed)
            req(all(math.hypot(lm.x - sx, lm.y - sy) >= 22.0 for sx, sy in structures), f"{terrain} landmarks preserve authored ruin access", seed)
        for i, a in enumerate(first):
            for b in first[i + 1:]:
                req(math.hypot(a.x - b.x, a.y - b.y) >= 36.0, f"{terrain} landmarks do not visually stack", seed)
        layout_count += 1

# Runtime integration is intentionally visual-only.
terrain_path = ROOT / "terrains.py"
terrain_src = terrain_path.read_text(encoding="utf-8")
landmark_src = (ROOT / "surface_landmarks.py").read_text(encoding="utf-8")
ast.parse(terrain_src, filename=str(terrain_path))
ast.parse(landmark_src, filename=str(ROOT / "surface_landmarks.py"))
req("generate_landmarks(self.seed" in terrain_src, "surface generation installs deterministic landmark anchors")
req("self._draw_surface_landmark" in terrain_src, "top-down renderer draws landmark silhouettes")
req("visual-only" in terrain_src.lower() and "collision" in terrain_src.lower(), "runtime documents non-colliding landmark contract")
req("self.landmarks" not in terrain_src[terrain_src.find("def update_surface"):terrain_src.find("def draw_surface")], "landmarks do not alter surface movement/update physics")
req("landmarks" not in (ROOT / "surface_resources.py").read_text(encoding="utf-8").lower(), "landmarks do not become harvestable resources")
req("landmarks" not in (ROOT / "mission_state.py").read_text(encoding="utf-8").lower(), "landmarks do not become mission-state dependencies")

# Ensure each authored drawing branch is present.
for profile in LANDMARK_PROFILES.values():
    req(f"kind == '{profile.kind}'" in terrain_src, f"renderer includes {profile.kind} silhouette")

# Existing authoritative world list still covers the same twelve families.
module = ast.parse(terrain_src)
biome_terrains = []
for node in module.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "BIOMES" for t in node.targets):
        value = ast.literal_eval(node.value)
        biome_terrains = [str(item.get("terrain")) for item in value]
        break
req(set(biome_terrains) == expected, "Pass 27 preserves all 12 established biome families", biome_terrains)

out = {
    "pass": "Entropy Pass 27 — Surface Landmark Identity",
    "status": "PASS",
    "checks_passed": sum(1 for c in checks if c["ok"]),
    "checks_total": len(checks),
    "layouts_stress_tested": layout_count,
    "landmark_profiles": {terrain: {"kind": p.kind, "title": p.title, "subtitle": p.subtitle} for terrain, p in LANDMARK_PROFILES.items()},
    "contract": "three deterministic visual-only anchors per surface; clear of ship/ruins; no collision, resource, or mission-state authority",
    "checks": checks,
}
report = ROOT / "verification" / "reports" / "pass27_surface_landmarks.json"
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps({k: out[k] for k in ("pass", "status", "checks_passed", "checks_total", "layouts_stress_tested")}, indent=2))
