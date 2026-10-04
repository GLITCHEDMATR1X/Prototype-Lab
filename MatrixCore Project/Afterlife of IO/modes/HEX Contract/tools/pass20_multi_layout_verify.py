from __future__ import annotations
import hashlib, json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from game.world_data import LAYOUTS, LAYOUT_POOLS, WORLD_RECT, MAX_ACTOR_RADIUS, MIN_CLEAR_GAP, EDGE_CLEARANCE, expand_object, select_layout
from tools.pass14_world_verify import rect_distance, point_rect_distance, reachable

PASS19_FROZEN = {
    'game/data.py':'eb2262c00d24519e075e91e4a55bf2f4aa44e02b0e09475658f10c5b5db2b159',
    'game/actors.py':'8be771ef389f8e0f739eebc5de59148c4671ca551f39d36ea44fe5fec7172a8e',
    'game/actor_visuals.py':'bffe05ba33677bfc59b322495ef233f739c5707d5bde1c46c5e6473de8a3a881',
    'game/audio.py':'4b0be21e1c38c883a4cdd9b0e26cb250f5de4744132e2f4fe23e46af9f8e2221',
    'game/render.py':'f2f05bfa62fe37155bbaac8584edb3b809eea34eb42cf4954934ad7585c245c5',
}
EXPECTED_MAZE={'purge':7,'recovery':7,'rescue':6}
EXPECTED_SETPIECES={
 'purge':{'Flying Buttresses','Altar Gate','Choir Screens','Broken Cloister','Votive Rail'},
 'recovery':{'Mirror Archive','Index Engine','Stack Bridge','Shard Barricade'},
 'rescue':{'Service Hook','Signal Barricade','Shrine Lane','Split Bulkhead'},
}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def validate_layout(quest, idx, layout):
    expanded=[expand_object(o) for o in layout['objects']]
    physical=[o for o in expanded if o['movement']]
    parts=[r for o in physical for r in o['parts']]
    issues=[]; wx,wy,ww,wh=WORLD_RECT; right=wx+ww; bottom=wy+wh
    for o in physical:
        for x,y,w,h in o['parts']:
            if not (x>=wx+EDGE_CLEARANCE and y>=wy+EDGE_CLEARANCE and x+w<=right-EDGE_CLEARANCE and y+h<=bottom-EDGE_CLEARANCE):
                issues.append(f"{o['id']} edge clearance")
    gaps=[]
    for i,a in enumerate(physical):
        for b in physical[i+1:]:
            d=rect_distance(a['bounds'],b['bounds']); gaps.append(d)
            if d<MIN_CLEAR_GAP: issues.append(f"{a['id']}/{b['id']} gap {d:.1f}")
    marker_clear={}
    for name,pos in layout['markers'].items():
        req=120 if name.startswith(('boss','spawn_gate')) else 96 if name.startswith(('enemy_','comp_','civilian_')) else 88
        nearest=min((point_rect_distance(pos,p) for p in parts),default=9999.0); marker_clear[name]=round(nearest,2)
        if nearest<req: issues.append(f"marker {name} clearance {nearest:.1f}")
    live={n:p for n,p in layout['markers'].items() if n.startswith(('enemy_','comp_','boss','civilian_')) or n=='artifact'}
    live_min=9999.0; items=list(live.items())
    for i,(_,a) in enumerate(items):
        for _,b in items[i+1:]: live_min=min(live_min,math.dist(a,b))
    goals={n:p for n,p in layout['markers'].items() if n.startswith(('enemy_','comp_','boss','civilian_')) or n in {'extraction','artifact','reroute_extraction'}}
    reached=reachable(layout['markers']['entry'],goals,parts)
    missing=sorted(set(goals)-reached)
    if missing: issues.append('unreachable: '+','.join(missing))
    setpieces={o.get('setpiece') for o in layout['objects'] if o.get('setpiece')}
    if setpieces!=EXPECTED_SETPIECES[quest]: issues.append('setpiece identity mismatch')
    maze=sum(1 for o in physical if o.get('maze_piece'))
    if len(physical)!=8: issues.append('physical count')
    if maze!=EXPECTED_MAZE[quest]: issues.append('maze piece count')
    if layout['markers']!=LAYOUTS[quest]['markers']: issues.append('marker authority changed')
    if layout.get('access_breaks')!=LAYOUTS[quest].get('access_breaks'): issues.append('access break authority changed')
    return {
      'pass':not issues,'quest':quest,'variant_index':idx,'layout':layout['name'],
      'physical_objects':len(physical),'maze_pieces':maze,'setpieces':sorted(setpieces),
      'minimum_obstacle_gap':round(min(gaps) if gaps else 9999,2),'minimum_live_marker_gap':round(live_min,2),
      'all_required_routes_reachable':not missing,'markers_identical_to_pass19':layout['markers']==LAYOUTS[quest]['markers'],
      'access_breaks_identical_to_pass19':layout.get('access_breaks')==LAYOUTS[quest].get('access_breaks'),
      'marker_clearance':marker_clear,'issues':issues,
    }

def main():
    frozen={rel:sha(ROOT/rel)==dig for rel,dig in PASS19_FROZEN.items()}
    rows=[]; ok=all(frozen.values())
    for quest,pool in LAYOUT_POOLS.items():
        if len(pool)!=3: ok=False
        if pool[0] is not LAYOUTS[quest]: ok=False
        for idx,layout in enumerate(pool):
            row=validate_layout(quest,idx,layout); rows.append(row); ok=ok and row['pass']
    selection={q:[select_layout(q,s)['name'] for s in (1701,1702,1703)] for q in LAYOUT_POOLS}
    static_app=(ROOT/'game/app.py').read_text(encoding='utf-8')
    static_sim=(ROOT/'game/sim.py').read_text(encoding='utf-8')
    rotation_contract=('aftermath_counts' in static_app and 'mission_seed = int(self.args.seed) + layout_cycle' in static_app and 'build_world(quest_key, seed)' in static_sim)
    ok=ok and rotation_contract and MAX_ACTOR_RADIUS==36 and MIN_CLEAR_GAP==120
    payload={
      'pass20_multiple_approved_layouts':'PASS' if ok else 'FAIL',
      'layout_variants_per_contract':3,'approved_layout_total':sum(len(v) for v in LAYOUT_POOLS.values()),
      'frozen_gameplay_balance_modules':frozen,'runtime_layout_rotation_contract':rotation_contract,
      'seed_selection_examples':selection,'layouts':rows,
      'contract':{'minimum_obstacle_gap_px':120,'maximum_required_actor_radius_px':36,'markers_preserved':True,'destruction_required_for_progression':False,'setpiece_identity_preserved':True,'failed_retry_keeps_layout_until_aftermath_count_changes':True},
    }
    out=ROOT/'verification/reports/pass20_multi_layouts.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print(json.dumps(payload,indent=2)); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
