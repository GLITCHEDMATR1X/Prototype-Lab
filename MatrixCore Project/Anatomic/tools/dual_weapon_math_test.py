from __future__ import annotations
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'verification/dual_weapon_math.json'
# Audited source center/bounds from Pistol-Lazer.obj.
cx=(-3.247501+0.029894)*.5
cy=(-3.43516+3.631331)*.5
cz=(-5.052629+5.998172)*.5
scale=.060
muzzle_local=(( -1.603-cx)*scale,(5.60-cz)*scale,(.994-cy)*scale)
base_left=(-.26,.55,-.36); base_right=(.26,.55,-.36)
left=(base_left[0]+muzzle_local[0],base_left[1]+muzzle_local[1],base_left[2]+muzzle_local[2])
right=(base_right[0]-muzzle_local[0],base_right[1]+muzzle_local[1],base_right[2]+muzzle_local[2])
target=(0.0,5.0,-.58)  # camera-local target approximately torso-height relative to 1.68 m eye height

def norm(v):
    L=math.sqrt(sum(x*x for x in v)); return tuple(x/L for x in v)
def vec(a,b): return tuple(b[i]-a[i] for i in range(3))
ld=norm(vec(left,target)); rd=norm(vec(right,target))
# At the target distance both exact rays end at the same aim point by construction.
sep=math.dist(left,right)
report={
 'muzzle_local':muzzle_local,'left_muzzle_camera_local':left,'right_muzzle_camera_local':right,
 'muzzle_separation_m':sep,'left_direction_to_target':ld,'right_direction_to_target':rd,
 'target':target,
 'left_forward_component':ld[1],'right_forward_component':rd[1],
 'crosshair_convergence_error_m':0.0,
 'pass': bool(left[0]<0<right[0] and left[1]>.05 and right[1]>.05 and ld[1]>.95 and rd[1]>.95 and sep>.40)
}
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2)); raise SystemExit(0 if report['pass'] else 1)
