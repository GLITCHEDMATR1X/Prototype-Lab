from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OBJ=ROOT/'assets/source/Pistol-Lazer.obj'
OUT=ROOT/'verification/pistol_lazer_audit.json'
verts=[]; groups=[]; group=''; faces=0; tri_count=0; group_indices={}
for raw in OBJ.read_text(errors='ignore').splitlines():
    s=raw.strip()
    if s.startswith('v '):
        _,x,y,z,*_=s.split(); verts.append((float(x),float(y),float(z)))
    elif s.startswith('g '):
        group=s[2:]; groups.append(group)
    elif s.startswith('f '):
        ids=[]
        for token in s.split()[1:]:
            idx=int(token.split('/')[0]); ids.append(idx-1 if idx>0 else len(verts)+idx)
        faces+=1; tri_count += max(0,len(ids)-2)
        group_indices.setdefault(group,set()).update(ids)
mins=[min(v[i] for v in verts) for i in range(3)]
maxs=[max(v[i] for v in verts) for i in range(3)]

def group_info(term):
    hits=[(g,inds) for g,inds in group_indices.items() if term.lower() in g.lower()]
    result=[]
    for g,inds in hits:
        pts=[verts[i] for i in inds]
        c=[sum(p[k] for p in pts)/len(pts) for k in range(3)]
        result.append({'group':g,'vertices':len(inds),'center':c})
    return result

report={
    'source':str(OBJ.relative_to(ROOT)),
    'vertices':len(verts),
    'source_faces':faces,
    'triangles_after_fan_triangulation':tri_count,
    'unique_groups':len(set(groups)),
    'bounds':{'min':mins,'max':maxs,'size':[maxs[i]-mins[i] for i in range(3)]},
    'muzzle_groups':group_info('Muzzle'),
    'grip_groups':group_info('Grip'),
    'receiver_groups':group_info('Receiver'),
    'scope_groups':group_info('Crosshair'),
}
report['pass']=bool(len(verts)==15442 and faces==15003 and len(set(groups))>=28 and report['muzzle_groups'] and report['grip_groups'] and report['receiver_groups'])
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2)); raise SystemExit(0 if report['pass'] else 1)
