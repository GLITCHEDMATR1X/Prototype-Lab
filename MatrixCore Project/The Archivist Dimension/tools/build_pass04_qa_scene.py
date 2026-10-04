from __future__ import annotations
import math, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'verification'/'archivist_pass04_cybernetic_archive.egg'
TEXROOT=ROOT/'assets/cyber_orbs'; CYBER=ROOT/'assets/cyber'
ids=['continuation_afterlife_of_io','continuation_entropy','continuation_matrixcore','archive_true_version','continuation_the_restoration_of_utopia','archive_the_empty_field']
lines=['<CoordinateSystem> { Z-up }']; vp=[]; polys=[]; tex=[]; n=0

def V(x,y,z,u=0,vv=0):
 global n; vp.append(f'<Vertex> {n} {{ {x:.5f} {y:.5f} {z:.5f} <UV> {{ {u:.5f} {vv:.5f} }} }}'); n+=1; return n-1

def P(ids,t=None,rgba=None):
 s='<Polygon> {'
 if t:s+=f' <TRef> {{ {t} }}'
 if rgba:s+=f' <RGBA> {{ {rgba[0]} {rgba[1]} {rgba[2]} {rgba[3]} }}'
 s+=' <VertexRef> { '+' '.join(map(str,ids))+' <Ref> { vp } } }'; polys.append(s)

def sphere(cx,cy,cz,r,tn,seg=28,rings=16,rgba=(1,1,1,1)):
 rows=[]
 for rr in range(rings+1):
  vv=rr/rings; ph=math.pi*vv; sp,cp=math.sin(ph),math.cos(ph); row=[]
  for ss in range(seg+1):
   u=ss/seg; th=math.tau*u; row.append(V(cx+r*sp*math.cos(th),cy+r*sp*math.sin(th),cz+r*cp,u,1-vv))
  rows.append(row)
 for rr in range(rings):
  for ss in range(seg):
   a,b=rows[rr][ss],rows[rr][ss+1]; c,d=rows[rr+1][ss],rows[rr+1][ss+1]; P([a,c,d,b],tn,rgba)

def panel(cx,cy,cz,w,h,tn,rgba=(1,1,1,1)):
 a=V(cx-w/2,cy,cz-h/2,0,0); b=V(cx+w/2,cy,cz-h/2,1,0); c=V(cx+w/2,cy,cz+h/2,1,1); d=V(cx-w/2,cy,cz+h/2,0,1); P([a,b,c,d],tn,rgba)

def box(cx,cy,cz,sx,sy,sz,col):
 x0,x1=cx-sx/2,cx+sx/2; y0,y1=cy-sy/2,cy+sy/2; z0,z1=cz-sz/2,cz+sz/2
 q=[V(x0,y0,z0),V(x1,y0,z0),V(x1,y1,z0),V(x0,y1,z0),V(x0,y0,z1),V(x1,y0,z1),V(x1,y1,z1),V(x0,y1,z1)]
 for f in [(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7)]:P([q[i] for i in f],rgba=col)

def beam(a,b,t,col):
 ax,ay,az=a; bx,by,bz=b; box((ax+bx)/2,(ay+by)/2,(az+bz)/2,max(t,abs(bx-ax)+t),max(t,abs(by-ay)+t),max(t,abs(bz-az)+t),col)

for i,bid in enumerate(ids): tex.append(f'<Texture> t{i} {{ "{(TEXROOT/(bid+".jpg")).as_posix()}" <Scalar> minfilter {{ linear_mipmap_linear }} <Scalar> magfilter {{ linear }} }}')
tex.append(f'<Texture> eye {{ "{(CYBER/"archivist_mind_eye_cyber.jpg").as_posix()}" }}')
tex.append(f'<Texture> shell {{ "{(CYBER/"archive_shell_cyber.jpg").as_posix()}" <Scalar> wrapu {{ repeat }} <Scalar> wrapv {{ repeat }} }}')

# Cybernetic broken exterior fragments, angled to frame the orbs.
for x,z,w,h in [(-8,4.8,4.8,8.0),(8,4.8,4.8,8.0),(-4,8.5,5.2,3.0),(4,8.5,5.2,3.0)]:
 panel(x,5.7,z,w,h,'shell',(0.72,0.82,0.88,0.96))
# bright circuit rails
for x in (-6.2,6.2):
 beam((x,5.45,0.7),(x,5.45,9.3),.08,(.10,.62,.76,.78))
for z in (1.5,8.2):
 beam((-7.2,5.45,z),(7.2,5.45,z),.07,(.55,.34,.10,.68))

# Archivist Mind above center.
sphere(0,1.7,7.3,1.32,'eye',30,18)
for r,col in [(1.95,(.84,.58,.18,.88)),(2.55,(.17,.70,.82,.76)),(3.15,(.50,.31,.72,.62))]:
 for k in range(28):
  a=math.tau*k/28; box(math.cos(a)*r,1.7+math.sin(a)*r,7.3,.065,.26,.065,col)
for k in range(12):
 a=math.tau*k/12; beam((0,1.7,7.3),(math.cos(a)*2.9,1.7+math.sin(a)*2.9,7.3),.025,(.16,.70,.82,.42))

# Story orbs with readable cybernetic texture wrappers.
pos=[(-6,-2.0,2.2),(-3.6,-2.7,3.1),(-1.2,-2.2,2.4),(1.6,-2.3,3.2),(4.2,-2.4,2.3),(6.3,-1.6,3.0)]
for i,p in enumerate(pos): sphere(*p,1.18 if i in (2,5) else .95,f't{i}',26,15)
for j in [0,1,3,4,5]: beam(pos[2],pos[j],.035,(.12,.68,.80,.44))
# no floor: sparse data glints only
for i in range(36):
 a=math.tau*i/36; r=3.0+(i%7)*1.1; box(math.cos(a)*r,math.sin(a)*r-1,.12+(i%4)*.35,.04,.04,.04,(.16,.48,.60,1))

lines+=tex; lines.append('<VertexPool> vp {'); lines+=['  '+x for x in vp]; lines.append('}'); lines.append('<Group> scene {'); lines+=['  '+x for x in polys]; lines.append('}')
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text('\n'.join(lines),encoding='utf-8'); print(OUT); print('verts',len(vp),'polys',len(polys),'textures',len(tex))
