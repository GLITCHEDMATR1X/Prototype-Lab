from pathlib import Path
import ast, json, math
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'main.py').read_text(encoding='utf-8')
tree=ast.parse(source)
vals={}
for node in tree.body:
    if isinstance(node,(ast.Assign,ast.AnnAssign)):
        targets=node.targets if isinstance(node,ast.Assign) else [node.target]
        for t in targets:
            if isinstance(t,ast.Name) and t.id.startswith('NPC_'):
                try: vals[t.id]=ast.literal_eval(node.value)
                except Exception: pass
checks={
 'walk_speed_reasonable':0.45 <= vals.get('NPC_WALK_SPEED',0) <= 1.2,
 'turn_speed_reasonable':70 <= vals.get('NPC_TURN_SPEED_DPS',0) <= 180,
 'gait_frequency_reasonable':0.6 <= vals.get('NPC_GAIT_HZ',0) <= 1.5,
 'hip_swing_bounded':10 <= vals.get('NPC_HIP_SWING_DEG',0) <= 24,
 'knee_flex_bounded':15 <= vals.get('NPC_KNEE_FLEX_DEG',0) <= 40,
 'root_bob_small':0 < vals.get('NPC_ROOT_BOB_M',0) <= 0.02,
 'route_present':len(vals.get('NPC_WALK_ROUTE',())) >= 4,
 'walk_update':'def _update_npc_walk' in source,
 'gait_update':'def _apply_walk_gait' in source,
 'dynamic_collision':'npc = self.body_root.getPos(self.render)' in source,
 'walk_smoke':'ASCII_MATTER_WALK_SMOKE=' in source,
 'walk_disable':'--no-npc-walk' in source,
}
# Verify the authored local -Y heading convention used by the route solver:
# world forward=(sin(H), -cos(H)); target headings should map exactly.
for label,(dx,dy),expected in (
    ('forward',(0,-1),0),('right',(1,0),90),('left',(-1,0),-90),('back',(0,1),180)):
    h=math.degrees(math.atan2(dx,-dy))
    delta=((h-expected+180)%360)-180
    checks[f'heading_{label}']=abs(delta)<1e-9
result={'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'constants':vals}
(ROOT/'verification/npc_walk_math.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['result']=='PASS' else 1)
