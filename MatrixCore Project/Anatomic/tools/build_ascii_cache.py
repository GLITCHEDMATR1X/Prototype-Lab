from __future__ import annotations
import argparse, bisect, json, math, random
from pathlib import Path

GLYPHS = "@#%+=*:."

def parse_obj(path: Path):
    vertices=[]; triangles=[]
    for raw in path.read_text(errors='ignore').splitlines():
        if raw.startswith('v '):
            p=raw.split(); vertices.append(tuple(float(x) for x in p[1:4]))
        elif raw.startswith('f '):
            ids=[]
            for tok in raw.split()[1:]:
                head=tok.split('/')[0]
                if not head: continue
                idx=int(head); idx = idx-1 if idx>0 else len(vertices)+idx
                ids.append(idx)
            for i in range(1, len(ids)-1):
                triangles.append((ids[0], ids[i], ids[i+1]))
    return vertices, triangles

def cross(a,b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def sub(a,b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def norm(v):
    m=math.sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]) or 1
    return (v[0]/m,v[1]/m,v[2]/m)

def region_for(z, height):
    r=z/height
    if r>0.89: return 'head'
    if r>0.72: return 'chest'
    if r>0.54: return 'torso'
    if r>0.46: return 'pelvis'
    if r>0.24: return 'upper_leg'
    if r>0.06: return 'lower_leg'
    return 'foot'

def build(src: Path, out: Path, count: int, seed: int):
    vertices, triangles = parse_obj(src)
    mins=[min(v[i] for v in vertices) for i in range(3)]
    maxs=[max(v[i] for v in vertices) for i in range(3)]
    # Generic male is Z-up. Normalize to a 1.78 m figure standing on z=0.
    height=maxs[2]-mins[2]; scale=1.78/height
    center_x=(mins[0]+maxs[0])/2; center_y=(mins[1]+maxs[1])/2
    vv=[((v[0]-center_x)*scale,(v[1]-center_y)*scale,(v[2]-mins[2])*scale) for v in vertices]
    cumulative=[]; tri_data=[]; total=0.0
    for a,b,c in triangles:
        va,vb,vc=vv[a],vv[b],vv[c]
        nraw=cross(sub(vb,va),sub(vc,va)); area=0.5*math.sqrt(sum(x*x for x in nraw))
        if area < 1e-10: continue
        total += area; cumulative.append(total); tri_data.append((va,vb,vc,norm(nraw)))
    rng=random.Random(seed); samples=[]
    for i in range(count):
        pick=rng.random()*total; j=bisect.bisect_left(cumulative,pick)
        a,b,c,n=tri_data[min(j,len(tri_data)-1)]
        r1=math.sqrt(rng.random()); r2=rng.random()
        wa=1-r1; wb=r1*(1-r2); wc=r1*r2
        p=(a[0]*wa+b[0]*wb+c[0]*wc, a[1]*wa+b[1]*wb+c[1]*wc, a[2]*wa+b[2]*wb+c[2]*wc)
        # Bias character density visually by upward-facing / front-facing normals, deterministic.
        shade=max(0.0,min(1.0,0.42 + 0.30*n[2] - 0.20*n[1]))
        gi=min(len(GLYPHS)-1, int((1-shade)*(len(GLYPHS)-1)))
        if rng.random()<0.18: gi=max(0,min(len(GLYPHS)-1,gi+rng.choice((-1,1))))
        samples.append({'p':[round(x,6) for x in p], 'n':[round(x,6) for x in n], 'g':GLYPHS[gi], 'region':region_for(p[2],1.78)})
    payload={
        'schema':'ascii_matter.surface.v1','source':src.name,'source_vertices':len(vertices),'source_triangles':len(triangles),
        'sample_count':len(samples),'height_m':1.78,'seed':seed,'glyphs':GLYPHS,'points':samples
    }
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(payload,separators=(',',':')))
    print(f'Wrote {out} with {len(samples)} glyph samples from {len(vertices)} vertices / {len(triangles)} triangles')

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('src',type=Path); ap.add_argument('out',type=Path); ap.add_argument('--count',type=int,default=2200); ap.add_argument('--seed',type=int,default=424242)
    a=ap.parse_args(); build(a.src,a.out,a.count,a.seed)
