#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hud_layout
from ground_operation import GroundOperation
from air_operation import AirOperation
from ocean_operation import OceanOperation

main = (ROOT / "main.py").read_text(encoding="utf-8")

checks = {}
checks["safe zones do not overlap"] = hud_layout.zones_do_not_overlap()
checks["18px minimum gameplay font"] = 'pygame.font.SysFont("consolas", 18)' in main
checks["mission has contrast backing"] = '(0, 0, 0, 176)' in main
checks["weapon notice owns separate zone"] = 'hud_layout.WEAPON_NOTICE_Y' in main
checks["diagnostics moved below notices"] = 'hud_layout.DIAGNOSTIC_Y' in main
checks["duplicate center dev label removed"] = 'DEV MODE // TAB FRONT SWITCH ENABLED' not in main
checks["dev state remains visible in footer"] = 'F4 DEV OFF' in main and 'TAB FRONT' in main
checks["field guide matches campaign"] = 'Secure Ground, establish Air control, then gain Sea control.' in main

# Copy/readability contracts. Short uppercase labels are allowed; full lines are mixed case.
g = GroundOperation(); a = AirOperation(); o = OceanOperation()
label, detail = hud_layout.mission_lines(
    campaign_complete=False, ocean_mode=False, ground_assault=True,
    redeploy_required=False, ground_operation=g, air_operation=a, ocean_operation=o)
checks["ground mission copy"] = label == "GROUND // STREET ASSAULT" and detail == "Break hostile street units  0/8"
checks["ground detail mixed case"] = detail != detail.upper()

a.fighter_kills = a.FIGHTER_GOAL
label, detail = hud_layout.mission_lines(
    campaign_complete=False, ocean_mode=False, ground_assault=False,
    redeploy_required=False, ground_operation=g, air_operation=a, ocean_operation=o)
checks["air mission copy"] = label == "AIR // UFO INTERCEPT" and detail == "Intercept UFO contacts  0/2"
checks["air detail mixed case"] = detail != detail.upper()

o.warship_kills = o.WARSHIP_GOAL
label, detail = hud_layout.mission_lines(
    campaign_complete=False, ocean_mode=True, ground_assault=False,
    redeploy_required=False, ground_operation=g, air_operation=a, ocean_operation=o)
checks["ocean mission copy"] = label == "OCEAN // MARITIME AIR DEFENSE" and detail == "Defeat hostile helicopters  0/2"
checks["ocean detail mixed case"] = detail != detail.upper()

label, detail = hud_layout.mission_lines(
    campaign_complete=True, ocean_mode=True, ground_assault=False,
    redeploy_required=False, ground_operation=g, air_operation=a, ocean_operation=o)
checks["campaign complete copy"] = label == "CAMPAIGN COMPLETE" and "Enter to replay" in detail

for name, ok in checks.items():
    print(("PASS" if ok else "FAIL"), name)
if not all(checks.values()):
    raise SystemExit(1)
print("pass14_hud_hierarchy: PASS")
