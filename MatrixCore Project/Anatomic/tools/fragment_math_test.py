import json, math, random
from pathlib import Path
R=Path(__file__).resolve().parents[1]
data=json.loads((R/'assets/cache/generic_male_ascii.json').read_text())
impact=(0.10,0.0,1.18); radius=.23
cand=[]
for i,it in enumerate(data['points']):
    p=it['p']; dist=math.sqrt(sum((p[k]-impact[k])**2 for k in range(3)))
    if dist<=radius: cand.append((dist,i,p))
cand=sorted(cand)[:100]
rng=random.Random(7001); fragments=[]
for _,i,p in cand:
    ox,oy,oz=(p[0]-impact[0],p[1]-impact[1],p[2]-impact[2]); m=math.sqrt(ox*ox+oy*oy+oz*oz) or 1
    ox,oy,oz=ox/m,oy/m,oz/m
    vel=[ox*rng.uniform(1.4,4)+rng.uniform(-.6,.6), oy*rng.uniform(1.4,4)+rng.uniform(-.6,.6), oz*rng.uniform(1.4,4)+rng.uniform(.8,2.4)]
    fragments.append([list(p),vel])
for step in range(180):
    dt=1/60
    for f in fragments:
        p,v=f; v[2]-=6.2*dt
        for k in range(3): p[k]+=v[k]*dt
        if p[2]<.03: p[2]=.03; v[2]=abs(v[2])*.36; v[0]*=.78; v[1]*=.78
        if p[0]<-3.65 or p[0]>3.65: p[0]=max(-3.65,min(3.65,p[0])); v[0]*=-.42
        if p[1]>3.15: p[1]=3.15; v[1]*=-.42
spread=max(math.sqrt((f[0][0]-impact[0])**2+(f[0][1]-impact[1])**2) for f in fragments) if fragments else 0
report={'schema':'ascii_matter.fragment_math.v1','impact_candidates':len(cand),'simulated_fragments':len(fragments),'steps':180,'dt':1/60,'max_horizontal_spread_m':round(spread,4),'all_above_floor':all(f[0][2]>=.03 for f in fragments),'pass':bool(fragments) and all(f[0][2]>=.03 for f in fragments) and spread>.5}
out=R/'verification/fragment_math.json'; out.write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
