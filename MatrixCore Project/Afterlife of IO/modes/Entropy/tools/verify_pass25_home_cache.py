#!/usr/bin/env python3
"""Headless logic verification for HOME emergency-cache storage semantics."""
from __future__ import annotations
import json, sys, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.modules.setdefault('pygame', types.ModuleType('pygame'))
from mission_state import MissionState
from terrains import SurfaceView

checks=[]
def req(c,label):
 checks.append({'check':label,'ok':bool(c)})
 if not c: raise AssertionError(label)

class Planet:
 style='desert'
class System:
 seed=777
 planets=[Planet()]
class Ship:
 def __init__(self):
  self.player_pack={}; self.cargo={}; self.upgrade_levels={}; self.hull_hp=100; self.hull_hp_max=100
  self.fuel=60; self.fuel_max=100; self.fuel_quality=.5; self.shield_recharge_rate=.7; self.state_dirty=False; self.saved=0
 def save_state(self): self.saved += 1

mission=MissionState(); mission.begin_system(System(),1); mission.land_on(0)
ship=Ship()
view=SurfaceView.__new__(SurfaceView)
view.mode='surface'; view.resource_cache_pos=(10.0,10.0); view.resource_cache_claimed=False; view.resource_cache_role='home'
view.mission_state=mission; view.mission_planet_index=0; view.ship=ship; view.cam_x=10.0; view.cam_y=10.0
view.notification=''; view.notification_until=0; view.mission_target_structure=None; view.fragment_pos=None
view.ship_pos=(0.0,0.0)
req(view.try_collect_resource(),'HOME emergency cache collects')
req(ship.player_pack.get('fuel_cells')==4,'HOME cache puts four Fuel Cells in field pack')
req(ship.player_pack.get('salvage')==6,'HOME cache puts six Salvage in field pack')
req(ship.cargo.get('fuel_cells',0)==0 and ship.cargo.get('salvage',0)==0,'HOME cache does not teleport resources into ship cargo')
req(mission.resource_claimed(0),'HOME cache claim persists in mission state')
req(mission.phase=='home_wait_collapse','HOME objective advances to wait-for-collapse state')
req(view.resource_cache_pos is None and view.resource_cache_claimed,'HOME cache cannot be collected twice in the live surface view')

out={'pass':'Entropy Pass 25 — HOME Cache Logic','status':'PASS','checks_passed':sum(x['ok'] for x in checks),'checks_total':len(checks),'checks':checks}
print(json.dumps(out,indent=2))
