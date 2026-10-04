from __future__ import annotations
import hashlib, json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from game.world_data import LAYOUTS, LAYOUT_POOLS, WORLD_RECT, MAX_ACTOR_RADIUS, MIN_CLEAR_GAP, EDGE_CLEARANCE, expand_object
from tools.pass14_world_verify import rect_distance, point_rect_distance, reachable

EXPECTED_MAZE={'purge':7,'recovery':7,'rescue':6}
EXPECTED_SETPIECES={
 'purge':{'Flying Buttresses','Altar Gate','Choir Screens','Broken Cloister','Votive Rail'},
 'recovery':{'Mirror Archive','Index Engine','Stack Bridge','Shard Barricade'},
 'rescue':{'Service Hook','Signal Barricade','Shrine Lane','Split Bulkhead'},
}
FROZEN_FILES=['main.py','game/data.py','game/actors.py','game/actor_visuals.py','game/audio.py','game/world_data.py','game/world.py','game/sim.py','game/app.py']
BASE=Path('/mnt/data/hex_pass21_base/HEX Contract')

def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def validate_layout(quest,idx,layout):
    expanded=[expand_object(o) for o in layout['objects']]
    physical=[o for o in expanded if o['movement']]
    parts=[r for o in physical for r in o['parts']]
    issues=[]; wx,wy,ww,wh=WORLD_RECT; right=wx+ww; bottom=wy+wh
    gaps=[]
    for o in physical:
        for x,y,w,h in o['parts']:
            if not (x>=wx+EDGE_CLEARANCE and y>=wy+EDGE_CLEARANCE and x+w<=right-EDGE_CLEARANCE and y+h<=bottom-EDGE_CLEARANCE): issues.append(f"{o['id']} edge")
    for i,a in enumerate(physical):
        for b in physical[i+1:]:
            d=rect_distance(a['bounds'],b['bounds']); gaps.append(d)
            if d<MIN_CLEAR_GAP: issues.append(f"gap {a['id']}/{b['id']}={d:.1f}")
    for name,pos in layout['markers'].items():
        req=120 if name.startswith(('boss','spawn_gate')) else 96 if name.startswith(('enemy_','comp_','civilian_')) else 88
        nearest=min((point_rect_distance(pos,p) for p in parts),default=9999)
        if nearest<req: issues.append(f"marker {name} clearance {nearest:.1f}")
    goals={n:p for n,p in layout['markers'].items() if n.startswith(('enemy_','comp_','boss','civilian_')) or n in {'extraction','artifact','reroute_extraction'}}
    reached=reachable(layout['markers']['entry'],goals,parts)
    missing=sorted(set(goals)-reached)
    if missing: issues.append('unreachable '+','.join(missing))
    sp={o.get('setpiece') for o in layout['objects'] if o.get('setpiece')}
    if sp!=EXPECTED_SETPIECES[quest]: issues.append('setpieces')
    maze=sum(1 for o in physical if o.get('maze_piece'))
    if len(physical)!=8 or maze!=EXPECTED_MAZE[quest]: issues.append('counts')
    if layout['markers']!=LAYOUTS[quest]['markers']: issues.append('markers changed')
    return {'quest':quest,'variant':idx+1,'name':layout['name'],'pass':not issues,'physical':len(physical),'maze':maze,'min_gap':round(min(gaps),2),'routes':not missing,'issues':issues}

def main():
    frozen={rel:(sha(ROOT/rel)==sha(BASE/rel)) for rel in FROZEN_FILES}
    rows=[]; ok=all(frozen.values())
    for quest,pool in LAYOUT_POOLS.items():
        for idx,layout in enumerate(pool):
            r=validate_layout(quest,idx,layout); rows.append(r); ok=ok and r['pass']
    render=(ROOT/'game/render.py').read_text(encoding='utf-8')
    visual_contract={
      'grid_quieted':'Sparse nave inlays' in render and 'Archive lanes use large index cells' in render and 'broad transit plates' in render,
      'tiered_obstacles':'_obstacle_visual_tier' in render,
      'landmark_halo':'Dominant landmarks receive a traversable floor halo' in render,
      'support_edges_recede':'"support": self._lift_color(env["edge"], -18)' in render,
      'collision_not_modified':all(frozen.values()),
    }
    ok=ok and all(visual_contract.values()) and MAX_ACTOR_RADIUS==36 and MIN_CLEAR_GAP==120
    payload={'pass21_world_visual_hierarchy':'PASS' if ok else 'FAIL','frozen_gameplay_and_world_authority':frozen,'visual_contract':visual_contract,'layouts':rows,'contract':{'layouts':9,'minimum_gap':120,'max_actor_radius':36,'world_data_unchanged':True,'gameplay_balance_unchanged':True}}
    out=ROOT/'verification/reports/pass21_visual_hierarchy.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print(json.dumps(payload,indent=2)); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
