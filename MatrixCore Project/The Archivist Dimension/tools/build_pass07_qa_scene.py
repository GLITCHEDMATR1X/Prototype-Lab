from __future__ import annotations
import math, pathlib, json
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'verification'/'archivist_pass07_planetary_systems.egg'
OUT2=ROOT/'verification'/'archivist_pass07_orbital_hierarchy.egg'
TEXROOT=ROOT/'assets/cyber_orbs'; CYBER=ROOT/'assets/cyber'
planet_ids=[
 ('continuation_matrixcore',(0,16,4),3.20),
 ('continuation_afterlife_of_io',(-20,-5,8),3.00),
 ('continuation_entropy',(19,-10,11),3.10),
 ('continuation_the_restoration_of_utopia',(-5,27,-5),3.05),
 ('apocalypse_apocalypse_run',(24,10,-9),2.85),
 ('archive_what_the_archive_became',(-25,13,0),2.90),
]
moon_ids=[
 'continuation_io_88_and_the_prototype_realities','archive_human_reviewer','archive_first_copy',
 'continuation_sables_mission','archive_the_body_they_kept','archive_true_version',
 'continuation_beyond_the_last_light','continuation_the_last_signal','archive_the_uncalibrated_sky',
 'continuation_the_victory_and_reunion','archive_public_access','archive_expected_passenger',
 'apocalypse_crimson_valley','apocalypse_doomsday_countdown','apocalypse_earth_exodus',
 'archive_sleeping_archive','archive_dream_catcher','archive_ghost_field',
]

def build(out, close=False):
    lines=['<CoordinateSystem> { Z-up }']; vp=[]; polys=[]; tex=[]; n=0
    def V(x,y,z,u=0,v=0):
        nonlocal n
        vp.append(f'<Vertex> {n} {{ {x:.5f} {y:.5f} {z:.5f} <UV> {{ {u:.5f} {v:.5f} }} }}'); n+=1; return n-1
    def P(vs,t=None,rgba=None):
        s='<Polygon> {'
        if t:s+=f' <TRef> {{ {t} }}'
        if rgba:s+=f' <RGBA> {{ {rgba[0]} {rgba[1]} {rgba[2]} {rgba[3]} }}'
        s+=' <VertexRef> { '+' '.join(map(str,vs))+' <Ref> { vp } } }'; polys.append(s)
    def sphere(cx,cy,cz,r,tn,seg=24,rings=13,rgba=(1,1,1,1)):
        rows=[]
        for rr in range(rings+1):
            v=rr/rings; ph=math.pi*v; sp,cp=math.sin(ph),math.cos(ph); row=[]
            for ss in range(seg+1):
                u=ss/seg; th=math.tau*u
                row.append(V(cx+r*sp*math.cos(th),cy+r*sp*math.sin(th),cz+r*cp,u,1-v))
            rows.append(row)
        for rr in range(rings):
            for ss in range(seg):
                a,b=rows[rr][ss],rows[rr][ss+1]; c,d=rows[rr+1][ss],rows[rr+1][ss+1]
                if rr:P([a,c,b],tn,rgba)
                if rr!=rings-1:P([b,c,d],tn,rgba)
    def box(cx,cy,cz,sx,sy,sz,col):
        x0,x1=cx-sx/2,cx+sx/2; y0,y1=cy-sy/2,cy+sy/2; z0,z1=cz-sz/2,cz+sz/2
        raw=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
        q=[V(*p) for p in raw]
        for f in [(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7)]:P([q[i] for i in f],rgba=col)
    def orbit(cx,cy,cz,r,tilt,col):
        pts=[]; t=math.radians(tilt); ct,st=math.cos(t),math.sin(t)
        for i in range(64):
            a=math.tau*i/64; x=math.cos(a)*r; yy=math.sin(a)*r; y=yy*ct; z=yy*st
            pts.append((cx+x,cy+y,cz+z))
        for i in range(64):
            a=pts[i]; b=pts[(i+1)%64]
            mx,my,mz=(a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2
            box(mx,my,mz,0.035+abs(a[0]-b[0]),0.035+abs(a[1]-b[1]),0.035+abs(a[2]-b[2]),col)
    allids=[x[0] for x in planet_ids]+moon_ids
    texref={}
    for i,bid in enumerate(allids):
        path=TEXROOT/(bid+'.jpg')
        name=f't{i}'
        texref[bid]=name
        tex.append(f'<Texture> {name} {{ "{path.as_posix()}" <Scalar> minfilter {{ linear_mipmap_linear }} <Scalar> magfilter {{ linear }} }}')
    tex.append(f'<Texture> eye {{ "{(CYBER/"archivist_mind_eye_cyber.jpg").as_posix()}" }}')
    tex.append(f'<Texture> shell {{ "{(CYBER/"archive_shell_cyber.jpg").as_posix()}" }}')

    # broken 4D exterior pieces
    for x,y,z in [(-31,15,18),(31,17,15),(-27,-19,-15),(30,-17,-13),(2,39,20),(0,-35,18)]:
        box(x,y,z,7,0.25,10,(.18,.27,.34,.55))
    # mind eye
    sphere(0,2,4.5,1.5,'eye',28,16)

    moon_cursor=0
    for pi,(bid,(cx,cy,cz),pr) in enumerate(planet_ids):
        sphere(cx,cy,cz,pr,texref[bid],28,16)
        accent=[(.15,.65,.82,.45),(.55,.30,.80,.45),(.22,.45,.84,.45),(.26,.76,.76,.45),(.88,.30,.14,.45),(.78,.56,.24,.45)][pi]
        # 3 orbit tracks and 3 moons per system, plus one machine satellite on alternating systems
        for j,rr in enumerate((5.4,7.9,10.2)):
            orbit(cx,cy,cz,rr,(-28+pi*11+j*17)%62-31,accent)
            a=0.8+j*1.7+pi*.4
            tilt=math.radians((-28+pi*11+j*17)%62-31)
            x=math.cos(a)*rr; yy=math.sin(a)*rr; y=yy*math.cos(tilt); z=yy*math.sin(tilt)
            mbid=moon_ids[moon_cursor % len(moon_ids)]; moon_cursor+=1
            sphere(cx+x,cy+y,cz+z,0.82+0.12*(j%2),texref[mbid],18,10)
        if pi%2==0:
            a=2.1; rr=6.7
            sx,sy,sz=cx+math.cos(a)*rr,cy+math.sin(a)*rr,cz+1.3
            # simulation satellite/gate
            sphere(sx,sy,sz,0.82,texref[bid],20,11)
            orbit(cx,cy,cz,rr,42,accent)
            for k in range(12):
                aa=math.tau*k/12
                box(sx+math.cos(aa)*1.25,sy+math.sin(aa)*1.25,sz,0.10,0.28,0.10,(accent[0],accent[1],accent[2],.75))
    lines+=tex; lines.append('<VertexPool> vp {'); lines += ['  '+x for x in vp]; lines.append('}'); lines.append('<Group> scene {'); lines += ['  '+x for x in polys]; lines.append('}')
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text('\n'.join(lines),encoding='utf-8')
    print(out,'verts',len(vp),'polys',len(polys),'textures',len(tex))

build(OUT,False)
build(OUT2,True)
