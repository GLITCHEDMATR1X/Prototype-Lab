from pathlib import Path
import json, collections
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'assets/cache/internal_skeleton.json').read_text())
parents=data['rig_parent']; bindings=data['body_bindings']
counts=collections.Counter(bindings)

def descendants(root):
    out=set(); frontier=[root]
    while frontier:
        cur=frontier.pop()
        for child,parent in parents.items():
            if parent==cur and child not in out:
                out.add(child); frontier.append(child)
    return out

left=descendants('left_shoulder'); right=descendants('right_shoulder')
left_arm={'left_elbow','left_wrist','left_hand'}|{f'left_{f}_{p}' for f in ('thumb','index','middle','ring','pinky') for p in ('root','mid','tip')}
right_arm={'right_elbow','right_wrist','right_hand'}|{f'right_{f}_{p}' for f in ('thumb','index','middle','ring','pinky') for p in ('root','mid','tip')}
body_forbidden={'pelvis','spine_low','spine_mid','spine_high','neck','head_base','left_hip','right_hip','left_knee','right_knee','left_ankle','right_ankle','left_foot','right_foot'}
checks={
    'left_shoulder_parent_spine_high':parents.get('left_shoulder')=='spine_high',
    'right_shoulder_parent_spine_high':parents.get('right_shoulder')=='spine_high',
    'left_elbow_parent_shoulder':parents.get('left_elbow')=='left_shoulder',
    'right_elbow_parent_shoulder':parents.get('right_elbow')=='right_shoulder',
    'left_descendants_complete':left_arm<=left,
    'right_descendants_complete':right_arm<=right,
    'left_no_torso_descendants':not (left & body_forbidden),
    'right_no_torso_descendants':not (right & body_forbidden),
    'arm_subtrees_disjoint':not (left & right),
    'left_upper_ascii_bound':counts['left_shoulder']>=20,
    'right_upper_ascii_bound':counts['right_shoulder']>=20,
    'left_forearm_ascii_bound':counts['left_elbow']>=20,
    'right_forearm_ascii_bound':counts['right_elbow']>=20,
    'all_body_glyphs_bound':len(bindings)==2200 and sum(counts.values())==2200,
}
result={
    'result':'PASS' if all(checks.values()) else 'FAIL',
    'checks':checks,
    'left_descendant_count':len(left),
    'right_descendant_count':len(right),
    'binding_counts':{k:counts[k] for k in ('left_shoulder','left_elbow','left_wrist','left_hand','right_shoulder','right_elbow','right_wrist','right_hand')},
}
(ROOT/'verification/shoulder_articulation_math.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['result']=='PASS' else 1)
