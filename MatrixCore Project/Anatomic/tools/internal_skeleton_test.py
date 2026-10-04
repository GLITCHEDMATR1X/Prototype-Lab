from pathlib import Path
import json, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
proc=subprocess.run([sys.executable,str(ROOT/'tools/build_internal_skeleton.py')],capture_output=True,text=True,timeout=60)
if proc.returncode:
    print(proc.stdout); print(proc.stderr,file=sys.stderr); raise SystemExit(proc.returncode)
data=json.loads((ROOT/'assets/cache/internal_skeleton.json').read_text())
m=data['metrics']
curves={c['name']:c for c in data['curves']}
bones={b['name']:b for b in data['bones']}
skull=data.get('skull',{})
checks={
    'version': data.get('version',0)>=6,
    'joint_count': m.get('joint_count')==52,
    'primary_bones': m.get('primary_bone_count')==51,
    'curves': m.get('curve_count')==25,
    'render_segments': m.get('render_segment_count')==152,
    'formed_skull_mesh': m.get('formed_skull_mesh_count')==1 and bool(skull),
    'shell_clearance': m.get('minimum_segment_shell_clearance_m',0)>m.get('required_shell_clearance_m',999),
    'organ_clearance': m.get('minimum_segment_organ_clearance_m',0)>m.get('required_organ_clearance_m',999),
    'joint_shell_clearance': m.get('minimum_joint_shell_clearance_m',0)>m.get('required_shell_clearance_m',999),
    'joint_organ_clearance': m.get('minimum_joint_organ_clearance_m',0)>m.get('required_organ_clearance_m',999),
    'skull_shell_clearance': m.get('formed_skull_outer_shell_clearance_m',0)>m.get('required_shell_clearance_m',999),
    'skull_organ_clearance': m.get('formed_skull_organ_clearance_m',0)>m.get('required_organ_clearance_m',999),
    'no_violations': not m.get('violations'),
    'rib_levels': sum(1 for c in data['curves'] if 'rib_' in c['name'])==8,
    'sternum': 'sternum' in curves,
    'formed_face': all(n in curves for n in ('skull_brow','left_orbit','right_orbit','left_cheek','right_cheek','nasal_bridge','maxilla','mandible')),
    'thicker_humerus': bones['left_humerus']['radius']>=0.0070 and bones['right_humerus']['radius']>=0.0070,
    'thicker_femur': bones['left_femur']['radius']>=0.0090 and bones['right_femur']['radius']>=0.0090,
    'thicker_ribs': curves['left_rib_1']['radius']>=0.0040 and curves['right_rib_1']['radius']>=0.0040,
    'solid_cranium_thickness': skull.get('thickness',0)>=0.0030,
    'future_articulation_role': 'articulation' in data.get('role',''),
    'finger_chains': all(f'{side}_{finger}_{part}' in data['joints'] for side in ('left','right') for finger in ('thumb','index','middle','ring','pinky') for part in ('root','mid','tip')),
    'finger_bones': sum(1 for n in bones if any(f in n for f in ('thumb','index','middle','ring','pinky'))) == 30,
    'lower_elbows': abs(data['joints']['left_elbow'][2]-1.225)<1e-9 and abs(data['joints']['right_elbow'][2]-1.225)<1e-9,
}
passed=sum(checks.values())
print(f'INTERNAL_SKELETON={passed}/{len(checks)}')
for k,v in checks.items(): print(('PASS ' if v else 'FAIL ')+k)
print(f"MIN_SEGMENT_SHELL={m['minimum_segment_shell_clearance_m']:.6f}")
print(f"MIN_SEGMENT_ORGAN={m['minimum_segment_organ_clearance_m']:.6f}")
print(f"SKULL_SHELL={m['formed_skull_outer_shell_clearance_m']:.6f}")
print(f"SKULL_ORGAN={m['formed_skull_organ_clearance_m']:.6f}")
raise SystemExit(0 if passed==len(checks) else 1)
