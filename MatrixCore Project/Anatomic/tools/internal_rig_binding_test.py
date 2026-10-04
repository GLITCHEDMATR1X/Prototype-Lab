from pathlib import Path
import json, collections
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'assets/cache/internal_skeleton.json').read_text())
parents=data.get('rig_parent',{})
joints=data.get('joints',{})
binds=data.get('body_bindings',[])
org=data.get('organ_bindings',{})
checks={}
checks['version6']=data.get('version')==6
checks['joint_parent_complete']=set(parents)==set(joints)
checks['body_binding_count']=len(binds)==2200
checks['body_bindings_valid']=all(x in joints for x in binds)
checks['body_uses_arms']=all(collections.Counter(binds).get(x,0)>0 for x in ('left_shoulder','left_elbow','left_wrist','left_hand','right_shoulder','right_elbow','right_wrist','right_hand'))
checks['body_uses_legs']=all(collections.Counter(binds).get(x,0)>0 for x in ('left_hip','left_knee','left_ankle','left_foot','right_hip','right_knee','right_ankle','right_foot'))
checks['organ_bindings_valid']=all(v in joints for v in org.values()) and len(org)==8
checks['brain_to_head']=org.get('brain')=='head_base'
checks['thorax_to_spine']=all(org.get(x)=='spine_high' for x in ('left_lung','right_lung','heart'))
# Parent chains terminate and contain no cycle.
acyclic=True
for name in joints:
    seen=set(); cur=name
    while cur is not None:
        if cur in seen: acyclic=False; break
        seen.add(cur); cur=parents.get(cur)
checks['acyclic']=acyclic
checks['pelvis_root']=parents.get('pelvis') is None
checks['hands_feet_present']=all(x in joints for x in ('left_hand','right_hand','left_foot','right_foot'))
checks['finger_joint_count']=sum(1 for x in joints if any(f in x for f in ('thumb','index','middle','ring','pinky')))==30
checks['finger_parenting']=all(parents.get(f'{side}_{finger}_root')==f'{side}_hand' and parents.get(f'{side}_{finger}_mid')==f'{side}_{finger}_root' and parents.get(f'{side}_{finger}_tip')==f'{side}_{finger}_mid' for side in ('left','right') for finger in ('thumb','index','middle','ring','pinky'))
checks['lower_elbows']=abs(joints['left_elbow'][2]-1.225)<1e-9 and abs(joints['right_elbow'][2]-1.225)<1e-9
counts=collections.Counter(binds)
result={'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'joint_count':len(joints),'body_binding_count':len(binds),'binding_counts':dict(sorted(counts.items())),'organ_bindings':org}
(ROOT/'verification/internal_rig_bindings.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
