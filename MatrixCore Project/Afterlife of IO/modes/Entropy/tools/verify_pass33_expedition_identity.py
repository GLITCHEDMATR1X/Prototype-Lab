#!/usr/bin/env python3
"""Dependency-free Pass 33 expedition-identity and Pass 32 preservation verifier."""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "verification" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = REPORT_DIR / "pass33_expedition_identity.json"

checks: list[dict] = []

def check(name: str, ok: bool, detail="") -> None:
    checks.append({"name": name, "pass": bool(ok), "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))

def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")

space = read("space_core.py")
mission_src = read("mission_state.py")
terrain_src = read("terrains.py")
interior_src = read("interiors.py")
identity_src = read("expedition_identity.py")
manifest = json.loads(read("build_manifest.json"))

for name in ("space_core.py", "mission_state.py", "terrains.py", "interiors.py", "expedition_identity.py"):
    try:
        ast.parse(read(name), filename=name)
        check(f"AST parse {name}", True)
    except SyntaxError as exc:
        check(f"AST parse {name}", False, exc)

check("Pass 33 app version", 'APP_VERSION = "Pass 33 — Expedition Identity"' in space)
check("Manifest pass 33", manifest.get("pass") == 33)
check("Manifest authority", manifest.get("authoritative_baseline") == "Pass 33 — Expedition Identity")
check("Identity module active", "expedition_identity.py" in manifest.get("active_modules", []))
check("Save schema remains v5", '"schema_version": 5' in space)
check("No new save fields claimed", manifest.get("pass33_expedition_identity", {}).get("new_save_fields") == 0)

# Import the dependency-free identity and mission model.
import sys
sys.path.insert(0, str(ROOT))
from expedition_identity import (
    ARCHIVE_SITE_SEQUENCE, WORLD_ARCHIVE_PROFILES, archive_site_label,
    archive_slot, preferred_site_order, style_variety_score, world_profile,
)
from mission_state import (
    CAMPAIGN_EXPEDITION, GOAL_CARRYING, HAZARD_FAMILY_BY_STYLE,
    MissionState, PlanetMissionSignal,
)

check("Twelve world archive profiles", len(WORLD_ARCHIVE_PROFILES) == 12)
check("World profile styles complete", set(WORLD_ARCHIVE_PROFILES) == set(HAZARD_FAMILY_BY_STYLE))
check("World record names unique", len({p.record_name for p in WORLD_ARCHIVE_PROFILES.values()}) == 12)
check("World display names unique", len({p.world_name for p in WORLD_ARCHIVE_PROFILES.values()}) == 12)
check("Six archive site slots", len(ARCHIVE_SITE_SEQUENCE) == 6)
check("Archive site kinds unique", len({k for k, _ in ARCHIVE_SITE_SEQUENCE}) == 6)
check("Archive site labels unique", len({label for _, label in ARCHIVE_SITE_SEQUENCE}) == 6)
check("Archive slot starts at 1", archive_slot(0, 6) == 1)
check("Archive slot final pending is 6", archive_slot(5, 6) == 6)
check("Secured current slot stays current", archive_slot(3, 6, current_already_secured=True) == 3)
check("Preferred site order rotates", preferred_site_order(1)[0] == "ziggurat" and preferred_site_order(6)[0] == "labyrinth")
check("Site labels track slot", archive_site_label(4) == "SIGNAL ARCHIVE")

# Consecutive system variety: exact repeats rejected, same-hazard alternates are
# acceptable fallback, new hazard families are preferred.
check("Exact world repeat scores zero", style_variety_score("desert", "desert", HAZARD_FAMILY_BY_STYLE) == 0)
check("Same-hazard alternate scores one", style_variety_score("desert", "rust", HAZARD_FAMILY_BY_STYLE) == 1)
check("New hazard family scores two", style_variety_score("desert", "ice", HAZARD_FAMILY_BY_STYLE) == 2)
check("Unknown previous accepts candidate", style_variety_score("unknown", "fungal", HAZARD_FAMILY_BY_STYLE) == 2)

# Archive-site selection remains inside the original caller-supplied reachable pool.
@dataclass
class FakeStructure:
    x: float
    y: float
    seed: int
    kind: str
    title: str

structures = [
    FakeStructure(60.0, 0.0, 1001, "ziggurat", "Solar Ziggurat"),
    FakeStructure(62.0, 0.0, 1002, "observatory", "Orbital Observatory"),
    FakeStructure(64.0, 0.0, 1003, "bastion", "Astral Bastion"),
    FakeStructure(66.0, 0.0, 1004, "spire", "Archive Spire"),
    FakeStructure(68.0, 0.0, 1005, "sepulcher", "Buried Sepulcher"),
    FakeStructure(70.0, 0.0, 1006, "labyrinth", "Relic Labyrinth"),
]
slot_results = []
for secured in range(6):
    m = MissionState(campaign_phase=CAMPAIGN_EXPEDITION, fragments_secured_total=secured)
    m.system_seed = 330000 + secured
    m.target_planet_index = 0
    m.current_planet_index = 0
    chosen_seed = m.bind_surface_target(993300 + secured, structures, (0.0, 0.0))
    chosen = next(st for st in structures if st.seed == chosen_seed)
    slot_results.append(chosen.kind)
check("Six slots prefer six existing ruin families", slot_results == [k for k, _ in ARCHIVE_SITE_SEQUENCE], slot_results)
check("Target title exposes archive site identity", "CONTINUITY ARCHIVE" in m.target_structure_title, m.target_structure_title)

# Dead-world carrying continuity: target retirement must not erase record identity.
m = MissionState(campaign_phase=CAMPAIGN_EXPEDITION, fragments_secured_total=2)
m.target_planet_index = 0
m.target_style = "ice"
m.target_hazard_family = "COLD"
m.signals = {0: PlanetMissionSignal(0, "fragment", "ice", "COLD")}
m.carrying_fragment = True
outcome = m.resolve_target_loss("planet_destroyed")
check("Carried target loss remains CARRYING", outcome == GOAL_CARRYING)
check("Dead target index retired", m.target_planet_index == -1)
check("Dead target direct style retired", m.target_style == "unknown")
check("Carried archive style retained from signal", m.current_archive_style == "ice")
check("Carried archive record retained", m.current_archive_record == "CRYO RECORD")

# Player-facing consistency.
check("Warp arrival uses archive profile", "profile = world_profile(mission.target_style)" in space and "mission.current_archive_slot" in space)
check("Warp arrival includes hazard family", "mission.target_hazard_family" in space)
check("Surface HUD shows archive record", "ARCHIVE {int(getattr(mission, \"current_archive_slot\", 1))}" in terrain_src and "profile.record_name" in terrain_src)
check("Ship deposit uses retained archive record", "current_archive_record" in interior_src and "HYPERDRIVE AVAILABLE" in interior_src)
check("Objective title uses archive identity", "self.current_archive_record" in mission_src and "self.current_archive_slot" in mission_src)

# Pass 32 smoothness contracts remain authoritative.
smoothness_contracts = {
    "bounded motion delta": "dt = min(max(0.0, wall_dt), 0.050)",
    "wall-time suspend detection": "lifecycle_frame_count > 0 and wall_dt > 1.0",
    "integer 4K scaling": "pygame.transform.scale if integer_upscale else pygame.transform.smoothscale",
    "star LOD islice": "itertools.islice(self.stars, 0, None, 2)",
    "inlined quaternion rotation": "tx = 2.0 * (qy * vz - qz * vy)",
    "25Hz CRT authored noise": "noise_frame_id = int(tsec * 25.0)",
    "static CRT overlay": "self.static_overlay = pygame.Surface",
    "HUD notice cache": "hud_notice_cache_panel",
}
for label, token in smoothness_contracts.items():
    check(f"Pass32 preserved: {label}", token in space)

# Pass 31 state-machine contracts remain present.
flow_contracts = {
    "HOME routing": "legacy_save_needs_home_prologue",
    "committed planet entry": "planet_entry_surface_ready",
    "dead target recycle": 'mission.resolve_target_loss("planet_destroyed")',
    "collapse target recycle": 'mission.resolve_target_loss("system_collapse")',
    "warp gate": "warp_unlocked",
}
for label, token in flow_contracts.items():
    check(f"Pass31 preserved: {label}", token in space)
check(
    "Normal warp variety survives unloaded planet list",
    'previous_style = str(getattr(mission, "current_archive_style", "unknown") or "unknown")' in space,
)

result = {
    "pass": 33,
    "name": "Expedition Identity",
    "checks_passed": sum(1 for c in checks if c["pass"]),
    "checks_total": len(checks),
    "final_result": "PASS" if all(c["pass"] for c in checks) else "FAIL",
    "metrics": {
        "world_archive_profiles": len(WORLD_ARCHIVE_PROFILES),
        "archive_site_slots": len(ARCHIVE_SITE_SEQUENCE),
        "slot_preference_result": slot_results,
        "save_schema": 5,
        "new_save_fields": 0,
    },
    "notes": [
        "Pass 33 changes procedural selection/readability, not hazard values or collapse balance.",
        "Native pygame-ce rendering is verified separately when the runtime dependency is available.",
    ],
    "checks": checks,
}
REPORT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(f"\nFINAL_RESULT={result['final_result']} ({result['checks_passed']}/{result['checks_total']})")
print(f"REPORT={REPORT_PATH}")
raise SystemExit(0 if result["final_result"] == "PASS" else 1)
