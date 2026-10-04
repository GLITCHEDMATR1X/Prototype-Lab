#!/usr/bin/env python3
"""Dependency-free verification for Pass 33.1 HOME-start save migration."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mission_state import (
    MissionState,
    CAMPAIGN_HOME,
    CAMPAIGN_EXPEDITION,
    CAMPAIGN_SHIP_RECOVERY,
    CAMPAIGN_DELIVERY,
    CAMPAIGN_COMPLETE,
    legacy_save_needs_home_prologue,
)

checks = []
def check(name, cond, detail=""):
    ok = bool(cond)
    checks.append(ok)
    print(("PASS" if ok else "FAIL") + f": {name}" + (f" — {detail}" if detail else ""))

# Fresh in-memory campaign contract.
m = MissionState()
check("Fresh MissionState begins in HOME phase", m.campaign_phase == CAMPAIGN_HOME, m.campaign_phase)

# The real bug: a newer build could stamp revision 1 on an old impossible
# zero-progress expedition save. Revision must not block repair.
for revision in (0, 1, 2, 99):
    bad = {
        "campaign_intro_revision": revision,
        "campaign_phase": CAMPAIGN_EXPEDITION,
        "fragments_secured_total": 0,
        "ship_boot_completed": [],
        "gleebs_transmission_complete": False,
    }
    check(f"Impossible zero-progress expedition revision {revision} routes to HOME", legacy_save_needs_home_prologue(bad))

# Genuine campaign progress must never be reset.
check("Ship boot progress is preserved", not legacy_save_needs_home_prologue({
    "campaign_intro_revision": 1,
    "campaign_phase": CAMPAIGN_EXPEDITION,
    "fragments_secured_total": 0,
    "ship_boot_completed": ["power"],
}))
check("Fragment progress is preserved", not legacy_save_needs_home_prologue({
    "campaign_intro_revision": 1,
    "campaign_phase": CAMPAIGN_EXPEDITION,
    "fragments_secured_total": 1,
    "ship_boot_completed": [],
}))
check("Ship recovery phase is preserved", not legacy_save_needs_home_prologue({
    "campaign_phase": CAMPAIGN_SHIP_RECOVERY,
    "fragments_secured_total": 0,
    "ship_boot_completed": [],
}))
check("HOME phase is preserved", not legacy_save_needs_home_prologue({
    "campaign_phase": CAMPAIGN_HOME,
    "fragments_secured_total": 0,
    "ship_boot_completed": [],
}))
check("Delivery phase is preserved", not legacy_save_needs_home_prologue({
    "campaign_phase": CAMPAIGN_DELIVERY,
    "fragments_secured_total": 6,
    "ship_boot_completed": [],
}))
check("Complete phase is preserved", not legacy_save_needs_home_prologue({
    "campaign_phase": CAMPAIGN_COMPLETE,
    "fragments_secured_total": 6,
    "ship_boot_completed": [],
    "gleebs_transmission_complete": True,
}))

src = (ROOT / "space_core.py").read_text(encoding="utf-8")
paths = (ROOT / "runtime_paths.py").read_text(encoding="utf-8")
check("Runtime migration clears loaded bad mission before routing", "ship._loaded_mission_data = None" in src and "routed to HOME prologue" in src)
check("Normal HOME route enters SURFACE mode", 'globals()["game_mode"] = GAME_MODE_SURFACE' in src and "new expedition begins on HOME surface" in src)
check("Windows save root is outside shipping folder", "LOCALAPPDATA" in paths and 'APP_AUTHOR / APP_NAME' in paths)

passed = sum(checks)
print(f"FINAL_RESULT={'PASS' if passed == len(checks) else 'FAIL'} ({passed}/{len(checks)})")
raise SystemExit(0 if passed == len(checks) else 1)
