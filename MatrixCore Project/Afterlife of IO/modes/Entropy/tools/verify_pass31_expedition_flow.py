"""Pass 31 expedition flow-integrity verifier.

Dependency-free checks for HOME routing, committed planetfall transition,
objective lifecycle, dead-world retargeting, and hyperdrive gating.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SRC = (ROOT / 'space_core.py').read_text(encoding='utf-8')
MISSION_SRC = (ROOT / 'mission_state.py').read_text(encoding='utf-8')

from mission_state import (
    MissionState,
    SHIP_BOOT_SEQUENCE,
    GOAL_ACTIVE,
    GOAL_SECURED,
    GOAL_MISSED,
    GOAL_CARRYING,
    legacy_save_needs_home_prologue,
)

checks = []
def check(name, condition, detail=''):
    ok = bool(condition)
    checks.append({'name': name, 'pass': ok, 'detail': str(detail)})
    print(('PASS' if ok else 'FAIL') + ': ' + name + (f' — {detail}' if detail else ''))
    return ok

class Planet:
    def __init__(self, style='desert'):
        self.style = style
        self.destroyed = False

class System:
    def __init__(self, seed=100, planets=1):
        self.seed = seed
        self.planets = [Planet() for _ in range(planets)]

# Parse gates.
for fn in ('space_core.py', 'mission_state.py', 'standard_ui.py'):
    try:
        ast.parse((ROOT / fn).read_text(encoding='utf-8'))
        check(f'AST parses: {fn}', True)
    except Exception as exc:
        check(f'AST parses: {fn}', False, exc)

# Fresh campaign starts on HOME and cannot warp.
m = MissionState(); s1 = System(101)
m.begin_system(s1, 1)
check('Fresh campaign phase is HOME', m.is_home_phase, m.campaign_phase)
check('HOME has a target world', m.target_planet_index == 0, m.target_planet_index)
check('Hyperdrive locked on HOME', not m.warp_unlocked, m.warp_lock_reason)

# Ship boot -> expedition -> new active system goal.
m.begin_ship_recovery()
check('Ship recovery locks hyperdrive', not m.warp_unlocked, m.warp_lock_reason)
for step in SHIP_BOOT_SEQUENCE:
    check(f'Ship boot accepts {step}', m.complete_ship_boot_step(step))
s2 = System(202)
m.begin_system(s2, 2)
check('Expedition system goal starts active', m.system_goal_outcome == GOAL_ACTIVE, m.system_goal_outcome)
check('Active system goal locks hyperdrive', not m.warp_unlocked, m.warp_lock_reason)
check('Active system has Data Fragment waypoint', m.target_planet_index == 0, m.target_planet_index)

# Missing a fragment: no count increase, waypoint removed, warp enabled, next system retargets.
before = m.data_fragments_secured
outcome = m.resolve_target_loss('system_collapse')
check('Collapse resolves unrecovered goal as missed', outcome == GOAL_MISSED, outcome)
check('Missed target waypoint removed immediately', m.target_planet_index == -1, m.target_planet_index)
check('Missed fragment does not increase archive count', m.data_fragments_secured == before, m.data_fragments_secured)
check('Missed goal unlocks hyperdrive', m.warp_unlocked, m.warp_lock_reason)
check('Missed objective copy explains recycle', 'RETURNS TO THE NEXT SYSTEM' in m.objective_detail('space').upper(), m.objective_detail('space'))

s3 = System(303)
m.begin_system(s3, 3)
check('Next system restores required Data Fragment target', m.target_planet_index == 0, m.target_planet_index)
check('Next-system target is active again', m.system_goal_outcome == GOAL_ACTIVE, m.system_goal_outcome)
check('Next-system recycle keeps secured count unchanged', m.data_fragments_secured == before, m.data_fragments_secured)
check('Next-system hyperdrive relocks until resolution', not m.warp_unlocked, m.warp_lock_reason)

# Carrying a fragment survives target loss but does not unlock departure until stored.
m.land_on(0)
m.target_structure_seed = 777
m.inside_target_ruin = True
check('Legacy/ruin fragment can be picked up', m.recover_fragment(777))
check('Carried goal state recorded', m.system_goal_outcome == GOAL_CARRYING, m.system_goal_outcome)
check('Carrying alone does not unlock hyperdrive', not m.warp_unlocked, m.warp_lock_reason)
outcome = m.resolve_target_loss('planet_destroyed')
check('Destroyed world preserves carried fragment state', outcome == GOAL_CARRYING, outcome)
check('Destroyed carried-data waypoint removed', m.target_planet_index == -1, m.target_planet_index)
check('Carried data still locks hyperdrive', not m.warp_unlocked, m.warp_lock_reason)
check('Carried fragment can be secured after world loss', m.deposit_fragment())
check('Secured fragment unlocks hyperdrive', m.system_goal_outcome == GOAL_SECURED and m.warp_unlocked, m.system_goal_outcome)
check('Secured fragment increments archive once', m.data_fragments_secured == before + 1, m.data_fragments_secured)

# Persistence of new goal-state fields.
payload = m.to_dict()
check('Save payload carries campaign intro revision', int(payload.get('campaign_intro_revision', 0)) >= 1)
check('Save payload carries goal outcome', payload.get('system_goal_outcome') == GOAL_SECURED, payload.get('system_goal_outcome'))
check('Save payload carries missed-goal count', int(payload.get('missed_goals_total', 0)) >= 1, payload.get('missed_goals_total'))

# Retired waypoints survive save/reload instead of reappearing on a dead world.
mr = MissionState(); mr.campaign_phase = 'expedition'; sr = System(505); mr.begin_system(sr, 5)
mr.resolve_target_loss('system_collapse')
mr_payload = mr.to_dict()
mr2 = MissionState(); mr2.campaign_phase = 'expedition'; mr2.begin_system(sr, 5)
check('Missed-goal save restores cleanly', mr2.restore_from_dict(mr_payload, sr))
check('Reloaded missed target remains retired', mr2.target_planet_index == -1, mr2.target_planet_index)
check('Reloaded missed goal remains warp-ready', mr2.system_goal_outcome == GOAL_MISSED and mr2.warp_unlocked, mr2.system_goal_outcome)

# No-world safety cannot dead-end the run.
m2 = MissionState(); m2.campaign_phase = 'expedition'; m2.begin_system(System(404, planets=0), 4)
check('No-world expedition resolves as missed', m2.system_goal_outcome == GOAL_MISSED, m2.system_goal_outcome)
check('No-world expedition allows departure', m2.warp_unlocked, m2.warp_lock_reason)

# Legacy save migration contract.
check('Legacy zero-progress expedition requires HOME prologue', legacy_save_needs_home_prologue({
    'campaign_phase': 'expedition', 'fragments_secured_total': 0, 'ship_boot_completed': []
}))
check('Real campaign boot progress is not reset to HOME', not legacy_save_needs_home_prologue({
    'campaign_phase': 'expedition', 'fragments_secured_total': 0, 'ship_boot_completed': list(SHIP_BOOT_SEQUENCE)
}))
check('Recovered fragment progress is not reset to HOME', not legacy_save_needs_home_prologue({
    'campaign_phase': 'expedition', 'fragments_secured_total': 2, 'ship_boot_completed': []
}))

# Source contract: HOME migration and launch routing.
check('Legacy zero-progress saves are routed to HOME', 'legacy_skipped_home' in SRC and 'routed to HOME prologue' in SRC)
check('Normal HOME launch enters surface mode', 'globals()["game_mode"] = GAME_MODE_SURFACE' in SRC and 'new expedition begins on HOME surface' in SRC)

# Source contract: loading is excluded from suspend detector.
check('Planet entry excluded from resume-gap pause', 'planet_entry_pending or planet_entry_surface_ready' in SRC)
check('Transition grace excludes initial surface load stalls', 'transition_gap_grace_frames > 0' in SRC)

# Source contract: surface fully prepares behind transition; handoff occurs next frame.
check('Two-stage planetfall ready flag exists', 'planet_entry_surface_ready = True' in SRC)
check('Prepared surface logs behind transition', 'surface ready behind transition' in SRC)
check('Planetfall handoff happens at fresh-frame commit', 'Commit a fully prepared planet only at the start of a fresh frame' in SRC)
entry_prepare = SRC.split('Once the visible entry animation has run', 1)[-1].split('missiles.update(dt)', 1)[0]
check('Entry preparation does not expose SURFACE game mode early', 'globals()["game_mode"] = GAME_MODE_SURFACE' not in entry_prepare)

# Source contract: one gating point is shared by keyboard and controller via K_f.
check('Keyboard warp checks mission.warp_unlocked', 'if not bool(getattr(mission, "warp_unlocked", False))' in SRC)
check('Controller warp routes through shared F-key path', 'if gamepad.pressed("dpad_right")' in SRC and 'post_key(pygame.K_f)' in SRC)
check('Warp HUD exposes locked state', 'WARP LOCKED — RESOLVE SYSTEM GOAL' in SRC)

# Source contract: dead targets are retired both on collapse and destruction.
check('System collapse retires target waypoint', 'mission.resolve_target_loss("system_collapse")' in SRC)
check('Destroyed/devoured target retires waypoint', 'mission.resolve_target_loss("planet_destroyed")' in SRC)
check('Old auto-warp contract remains disabled', 'def system_goal_complete' in MISSION_SRC and 'return False' in MISSION_SRC.split('def system_goal_complete',1)[1].split('@property',1)[0])

status = 'PASS' if all(c['pass'] for c in checks) else 'FAIL'
out = {
    'pass': 31,
    'title': 'Expedition Flow Integrity',
    'status': status,
    'checks_passed': sum(1 for c in checks if c['pass']),
    'checks_total': len(checks),
    'checks': checks,
}
(ROOT / 'Entropy_Pass31_flow_validation.json').write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
print(f'FINAL_RESULT={status} ({out["checks_passed"]}/{out["checks_total"]})')
raise SystemExit(0 if status == 'PASS' else 1)
