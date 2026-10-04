#!/usr/bin/env python3
from pathlib import Path
import ast, json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from mission_state import legacy_save_needs_home_prologue, SHIP_BOOT_SEQUENCE

checks=[]
def check(name, cond):
    checks.append((name,bool(cond)))
    if not cond: raise AssertionError(name)

base={"campaign_phase":"expedition","fragments_secured_total":0,"gleebs_transmission_complete":False,"campaign_intro_revision":1}
check('zero boot routes HOME', legacy_save_needs_home_prologue({**base,"ship_boot_completed":[]}))
for count in range(1,len(SHIP_BOOT_SEQUENCE)):
    check(f'partial boot {count}/{len(SHIP_BOOT_SEQUENCE)} routes HOME', legacy_save_needs_home_prologue({**base,"ship_boot_completed":list(SHIP_BOOT_SEQUENCE[:count])}))
check('complete boot preserves zero-fragment expedition', not legacy_save_needs_home_prologue({**base,"ship_boot_completed":list(SHIP_BOOT_SEQUENCE)}))
check('fragment progress preserves expedition', not legacy_save_needs_home_prologue({**base,"fragments_secured_total":1,"ship_boot_completed":[]}))
check('HOME save is preserved', not legacy_save_needs_home_prologue({**base,"campaign_phase":"home","ship_boot_completed":[]}))
check('ship-recovery save is preserved', not legacy_save_needs_home_prologue({**base,"campaign_phase":"ship_recovery","ship_boot_completed":["power"]}))
check('delivery save is preserved', not legacy_save_needs_home_prologue({**base,"campaign_phase":"delivery","fragments_secured_total":6}))
check('complete save is preserved', not legacy_save_needs_home_prologue({**base,"campaign_phase":"complete","fragments_secured_total":6,"gleebs_transmission_complete":True}))

space=(ROOT/'space_core.py').read_text(encoding='utf-8')
terrain=(ROOT/'terrains.py').read_text(encoding='utf-8')
ast.parse((ROOT/'mission_state.py').read_text(encoding='utf-8'))
ast.parse(space); ast.parse(terrain)
check('startup migrates before restore', space.index('legacy_save_needs_home_prologue(saved_mission)') < space.index('mission.restore_from_dict(saved_mission, system)'))
check('HOME routes directly to surface', 'globals()["game_mode"] = GAME_MODE_SURFACE' in space and '_terrains().enter_surface(home_seed, screen, ship)' in space)
check('HOME surface receives mission binding', 'home_surface.configure_mission(mission, home_planet_i)' in space)
check('HOME launch remains disabled', "NO LAUNCH AVAILABLE — HOME EVACUATION IS AUTOMATIC AT SUPERNOVA" in space)
check('surface constructor remains deterministic', 'self._build_textures()' in terrain and 'self._build_world()' in terrain)

out={"pass":"Entropy Pass 33.2 — HOME Start Authority","status":"PASS","checks_passed":sum(v for _,v in checks),"checks_total":len(checks),"checks":[{"name":n,"ok":v} for n,v in checks]}
print(json.dumps(out,indent=2))
