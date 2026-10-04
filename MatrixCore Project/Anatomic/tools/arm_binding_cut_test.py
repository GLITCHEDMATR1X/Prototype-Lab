from pathlib import Path
import json, math
ROOT=Path(__file__).resolve().parents[1]
surface=json.loads((ROOT/'assets/cache/generic_male_ascii.json').read_text())['points']
data=json.loads((ROOT/'assets/cache/internal_skeleton.json').read_text())
binds=data['body_bindings']; joints=data['joints']

def length(a,b): return math.dist(joints[a],joints[b])
checks={}
checks['cache_v6']=data.get('version')==6
checks['left_elbow_lowered']=abs(joints['left_elbow'][2]-1.225)<1e-9
checks['right_elbow_lowered']=abs(joints['right_elbow'][2]-1.225)<1e-9
checks['elbow_drop_45mm']=abs((1.270-joints['left_elbow'][2])-0.045)<1e-9 and abs((1.270-joints['right_elbow'][2])-0.045)<1e-9
# Lowered elbow should make upper/lower arm proportions much closer than the old high pivot.
ratios={}
for side in ('left','right'):
    upper=length(f'{side}_shoulder',f'{side}_elbow'); lower=length(f'{side}_elbow',f'{side}_wrist')
    ratios[side]=upper/lower
    checks[f'{side}_balanced_limb_lengths']=0.90 <= upper/lower <= 1.15
# Geometry-derived hand zones, independent of the binding map. These are the actual
# far-lateral hanging-hand samples in the 1,300-glyph body cache.
zone_counts={}; orphan_counts={}; low_counts={}; low_wrong={}; hip_false_arm={}
for side in ('left','right'):
    same=lambda x: x<0 if side=='left' else x>=0
    zone=[i for i,p in enumerate(surface) if same(p['p'][0]) and abs(p['p'][0])>=0.30 and 0.70<=p['p'][2]<=1.02]
    allowed={f'{side}_elbow',f'{side}_wrist',f'{side}_hand'}
    orphan=[i for i in zone if binds[i] not in allowed]
    low=[i for i in zone if surface[i]['p'][2]<0.79]
    wrong=[i for i in low if binds[i]!=f'{side}_hand']
    # Near-hip shell should no longer be stolen by the hand branch, which was the
    # inverse artifact produced by the old broad abs(x)>=.155 rectangle.
    hip=[i for i,p in enumerate(surface) if same(p['p'][0]) and 0.145<=abs(p['p'][0])<=0.185 and 0.78<=p['p'][2]<=0.91]
    false_arm=[i for i in hip if binds[i] in {f'{side}_shoulder',f'{side}_elbow',f'{side}_wrist',f'{side}_hand'}]
    zone_counts[side]=len(zone); orphan_counts[side]=len(orphan); low_counts[side]=len(low); low_wrong[side]=len(wrong); hip_false_arm[side]=len(false_arm)
    checks[f'{side}_hand_zone_present']=len(zone)>=35
    checks[f'{side}_hand_zone_no_orphans']=not orphan
    checks[f'{side}_low_hand_samples_present']=len(low)>=5
    checks[f'{side}_low_hand_all_follow_hand']=not wrong
    checks[f'{side}_hip_not_stolen_by_arm']=not false_arm
result={'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'elbow_z':{'left':joints['left_elbow'][2],'right':joints['right_elbow'][2]},'arm_length_ratios':ratios,'hand_zone_counts':zone_counts,'hand_orphans':orphan_counts,'low_hand_counts':low_counts,'low_hand_wrong_bindings':low_wrong,'hip_false_arm_bindings':hip_false_arm}
(ROOT/'verification/arm_binding_cut.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
