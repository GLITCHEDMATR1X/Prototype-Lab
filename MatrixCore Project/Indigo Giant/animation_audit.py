from pathlib import Path
import csv, math, sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gltf_idle import GLBIdleSkin

ROOT=Path(__file__).resolve().parent
GLB=ROOT/'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
OUT=ROOT/'animation_audit.csv'
base=GLBIdleSkin(GLB,'Idle_Loop')
rows=[]
for anim in base.json['animations']:
    name=anim.get('name','')
    skin=GLBIdleSkin(GLB,name)
    finite=True
    for t in [0.0, skin.duration*0.5, max(0.0,skin.duration-1e-4)]:
        for pos,nrm in skin.pose(t):
            finite = finite and np.isfinite(pos).all() and np.isfinite(nrm).all()
    # Root local translation range, useful for checking whether the standard non-RM file drifts the world root.
    root_index=next(i for i,n in enumerate(skin.json['nodes']) if n.get('name')=='root')
    samples=[]
    for t in np.linspace(0, skin.duration, 9, endpoint=False):
        g=skin._global_matrices(float(t))
        p=g[root_index][:3,3]
        samples.append(p)
    arr=np.asarray(samples)
    root_range=np.ptp(arr,axis=0)
    rows.append({
        'animation':name,
        'duration_s':round(float(skin.duration),4),
        'channels':len(skin.channels),
        'pose_valid':bool(finite),
        'root_range_x':round(float(root_range[0]),6),
        'root_range_y':round(float(root_range[1]),6),
        'root_range_z':round(float(root_range[2]),6),
    })
with OUT.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
print('ANIMATIONS',len(rows))
print('VALID',sum(r['pose_valid'] for r in rows))
print('CSV',OUT)
