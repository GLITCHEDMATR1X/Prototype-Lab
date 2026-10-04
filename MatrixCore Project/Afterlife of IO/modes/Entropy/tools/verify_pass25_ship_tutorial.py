#!/usr/bin/env python3
"""Headless logic test for the Pass 25 ship onboarding stations."""
from __future__ import annotations
import json, sys, types
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
# interiors.py has no pygame work at module import; a stub lets us exercise
# non-rendering station logic in environments where pygame-ce is unavailable.
sys.modules.setdefault('pygame', types.ModuleType('pygame'))
from mission_state import MissionState, CAMPAIGN_EXPEDITION, CAMPAIGN_DELIVERY, CAMPAIGN_COMPLETE
from interiors import InteriorView

checks=[]
def req(c,label,detail=''):
    checks.append({'check':label,'ok':bool(c),'detail':detail})
    if not c: raise AssertionError(label+(': '+detail if detail else ''))

class Ship:
    def __init__(self):
        self.cargo={}
        self.player_pack={'fuel_cells':4,'salvage':6}
        self.upgrade_levels={}
        self.hull_hp=100; self.hull_hp_max=100
        self.fuel=60; self.fuel_max=100; self.fuel_quality=.5
        self.shield_recharge_rate=.7
        self.state_dirty=False
        self.saved=0
    def save_state(self): self.saved += 1

mission=MissionState(); mission.begin_ship_recovery()
ship=Ship()
view=InteriorView.__new__(InteriorView)
view.ship=ship; view.mission_state=mission
view.notification=''; view.notification_until=0
view.request_takeoff=False; view.request_campaign_complete=False
view.cargo_console_pos=(820.0,440.0); view.fuel_console_pos=(180.0,440.0)
view.power_console_pos=(180.0,700.0); view.navigation_console_pos=(820.0,700.0)
view.cockpit_console_pos=(500.0,120.0); view.repair_console_pos=(500.0,760.0); view.fabricator_pos=(500.0,310.0)
view.player=SimpleNamespace(x=0.0,y=0.0)

def at(pos): view.player.x,view.player.y=pos

# Wrong station remains gated.
at(view.fuel_console_pos)
req(view.try_process_fuel(), 'out-of-order station handled without fall-through')
req(mission.ship_boot_next_step=='power', 'out-of-order fuel cannot advance boot')

at(view.power_console_pos); req(view.try_restore_power(), 'power relay interaction succeeds')
req(mission.ship_boot_next_step=='storage','power advances to storage')

at(view.cargo_console_pos); req(view.try_store_inventory(), 'storage interaction succeeds')
req(ship.player_pack=={},'field pack empties into ship storage')
req(ship.cargo.get('fuel_cells')==4 and ship.cargo.get('salvage')==6,'field pack resources reach cargo')
req(mission.ship_boot_next_step=='fuel','storage advances to fuel')

at(view.fuel_console_pos); before=ship.fuel; req(view.try_process_fuel(),'fuel processing succeeds')
req(ship.fuel>before,'stored fuel cells increase ship fuel')
req(mission.ship_boot_next_step=='navigation','fuel advances to navigation')

at(view.navigation_console_pos); req(view.try_initialize_navigation(),'navigation interaction succeeds')
req(mission.ship_boot_next_step=='cockpit','navigation advances to cockpit')

at(view.cockpit_console_pos); req(view.try_cockpit(),'cockpit launches expedition')
req(view.request_takeoff,'cockpit requests takeoff')
req(mission.campaign_phase==CAMPAIGN_EXPEDITION,'cockpit commits expedition phase')

# Endgame cockpit behavior.
mission.campaign_phase=CAMPAIGN_DELIVERY; mission.fragments_secured_total=6
view.request_takeoff=False; view.request_campaign_complete=False
req(view.try_cockpit(),'delivery cockpit accepts Gleebs link')
req(view.request_campaign_complete,'delivery cockpit requests completion screen')
req(mission.campaign_phase==CAMPAIGN_COMPLETE and mission.gleebs_transmission_complete,'Gleebs transfer completes mission state')

out={'pass':'Entropy Pass 25 — Ship Tutorial Logic','status':'PASS','checks_passed':sum(x['ok'] for x in checks),'checks_total':len(checks),'checks':checks}
print(json.dumps(out,indent=2))
