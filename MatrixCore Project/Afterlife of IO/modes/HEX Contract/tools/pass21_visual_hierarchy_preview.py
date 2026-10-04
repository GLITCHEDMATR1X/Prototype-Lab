from __future__ import annotations
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from game.world_data import WORLD_RECT, LAYOUT_POOLS, expand_object
from game.data import MISSION_ENVIRONMENTS, QUESTS
OUT=ROOT/'verification/screenshots/pass21'; OUT.mkdir(parents=True,exist_ok=True)
TEX=ROOT/'assets/world'; FONT=ImageFont.load_default()
PRIMARY={'purge':'p_gate_north','recovery':'r_index_stack','rescue':'s_u_south'}

def lift(c,n): return tuple(max(0,min(255,int(v)+n)) for v in c[:3])
def alpha_tile(im,rect,key,alpha=200):
    p=TEX/f'{key}.png'
    if not p.exists(): return
    t=Image.open(p).convert('RGBA')
    if alpha != 255:
        a=t.getchannel('A').point(lambda v:int(v*alpha/255)); t.putalpha(a)
    x0,y0,x1,y1=map(int,rect)
    if x1<=x0 or y1<=y0:return
    layer=Image.new('RGBA',(x1-x0,y1-y0),(0,0,0,0))
    for y in range(0,layer.height,t.height):
        for x in range(0,layer.width,t.width): layer.alpha_composite(t,(x,y))
    im.alpha_composite(layer,(x0,y0))

def tier(rec,ob):
    if rec['id'] in PRIMARY.values(): return 'landmark'
    if ob['destructible']: return 'interactive'
    if rec['prefab'].startswith('setpiece_') or rec['prefab']=='relic_carriage': return 'setpiece'
    return 'support'

def floor_grammar(d,quest,env,x,y,w,h,layout):
    if quest=='purge':
        gd=lift(env['grid'],-9)
        for gx in range(x-220,x+w,156): d.line((gx,y,gx+310,y+h),fill=gd+(255,),width=1)
        for gy in range(y+84,y+h,136): d.line((x+20,gy,x+w-20,gy),fill=(38,19,35,255),width=1)
        pit=(792,425,1142,700); d.ellipse(pit,outline=env['accent']+(255,),width=2); d.ellipse((819,452,1115,673),outline=env['secondary']+(255,),width=1)
    elif quest=='recovery':
        gd=lift(env['grid'],-8)
        for gx in range(x+32,x+w,160): d.line((gx,y+18,gx,y+h-18),fill=gd+(255,),width=1)
        for gy in range(y+32,y+h,160): d.line((x+18,gy,x+w-18,gy),fill=gd+(255,),width=1)
        wx,wy=layout['markers']['memory_well']
        for r,c in ((58,env['accent']),(92,env['secondary']),(128,env['accent'])): d.ellipse((wx-r,wy-r,wx+r,wy+r),outline=c+(255,),width=2)
    else:
        gd=lift(env['grid'],-7)
        for gy in range(y+54,y+h,174):
            d.line((x+18,gy,x+w-18,gy),fill=gd+(255,),width=2)
            d.line((x+18,gy+12,x+w-18,gy+12),fill=lift(gd,-8)+(255,),width=1)
        for gx in range(x+80,x+w,240): d.line((gx,y+20,gx-38,y+h-20),fill=(14,42,44,255),width=1)

def render(quest,idx,layout):
    env=dict(MISSION_ENVIRONMENTS[quest]); q=QUESTS[quest]
    lifts={'purge':{'floor':22,'grid':-3,'wall':24,'edge':14,'fog':14},'recovery':{'floor':24,'grid':-4,'wall':26,'edge':16,'fog':15},'rescue':{'floor':22,'grid':-4,'wall':24,'edge':14,'fog':15}}[quest]
    for k,n in lifts.items(): env[k]=lift(env[k],n)
    bg=lift(env['fog'],12); im=Image.new('RGBA',(1920,1080),bg+(255,)); d=ImageDraw.Draw(im)
    d.rounded_rectangle((28,18,1892,145),radius=12,fill=(8,14,25,245),outline=lift(env['edge'],-4)+(255,),width=2)
    d.text((52,34),'HEX CONTRACT / PASS 21 - WORLD VISUAL HIERARCHY',font=FONT,fill=(242,248,255,255))
    d.text((52,62),f"{layout['name']} / VARIANT {idx+1} OF 3",font=FONT,fill=env['accent']+(255,))
    d.text((52,91),'QUIETER FLOOR / STRONGER SETPIECES / ONE DOMINANT LANDMARK / COLLISION + ROUTES UNCHANGED',font=FONT,fill=(190,207,230,255))
    d.text((52,118),'Visual grouping only: floor plates are traversable; every solid face still matches the Pass 20 collision footprint.',font=FONT,fill=(155,176,205,255))
    x,y,w,h=WORLD_RECT
    d.rounded_rectangle((x,y,x+w,y+h),radius=7,fill=env['floor']+(255,),outline=lift(env['edge'],-5)+(255,),width=2)
    floor_grammar(d,quest,env,x,y,w,h,layout)

    # Landmark floor halo, explicitly traversable.
    for rec in layout['objects']:
        if rec['id']==PRIMARY[quest]:
            ob=expand_object(rec); bx,by,bw,bh=ob['bounds']; halo=(bx-27,by-23,bx+bw+27,by+bh+23)
            d.rounded_rectangle(halo,radius=14,outline=lift(env['grid'],7)+(255,),width=2)
            d.rounded_rectangle((halo[0]+12,halo[1]+12,halo[2]-12,halo[3]-12),radius=11,outline=lift(env['accent'],-28)+(255,),width=1)
            break

    for rec in layout['objects']:
        ob=expand_object(rec); t=tier(rec,ob)
        bx,by,bw,bh=ob['bounds']
        if t!='support':
            plate=(bx-(9 if t=='landmark' else 5),by-(7 if t=='landmark' else 4),bx+bw+(9 if t=='landmark' else 5),by+bh+(7 if t=='landmark' else 4))
            d.rounded_rectangle(plate,radius=8,fill=lift(env['floor'],-5)+(255,),outline=lift(env['grid'],13 if t=='landmark' else 5)+(255,),width=1)
        edge={'support':lift(env['edge'],-18),'setpiece':lift(env['edge'],8),'interactive':lift(env['secondary'],6),'landmark':lift(env['accent'],24)}[t]
        ta={'support':166,'setpiece':218,'interactive':224,'landmark':242}[t]
        ow={'support':2,'setpiece':3,'interactive':3,'landmark':4}[t]
        for rx,ry,rw,rh in ob['parts']:
            off=8 if t=='support' else 10 if t=='setpiece' else 12
            d.rounded_rectangle((rx+off,ry+off+2,rx+rw+off,ry+rh+off+2),radius=6,fill=(1,3,8,230))
            fill=lift(env['wall'],11 if t=='support' else 16 if t=='setpiece' else 20 if t=='interactive' else 25)
            d.rounded_rectangle((rx,ry,rx+rw,ry+rh),radius=6,fill=fill+(255,),outline=edge+(255,),width=ow)
            alpha_tile(im,(rx+4,ry+4,rx+rw-4,ry+rh-4),rec.get('texture',''),ta)
            if rw>=rh*2.2:
                rib=lift(edge,-18 if t=='support' else -8)
                for px in range(rx+30,rx+rw-18,54): d.line((px,ry+8,px,ry+rh-8),fill=rib+(255,),width=1)
            elif rh>=rw*1.7:
                rib=lift(edge,-18 if t=='support' else -8)
                for py in range(ry+28,ry+rh-14,48): d.line((rx+8,py,rx+rw-8,py),fill=rib+(255,),width=1)
            d.line((rx+8,ry+4,rx+rw-8,ry+4),fill=lift(edge,22)+(255,),width=2 if t=='support' else 3)
            if ob['destructible']:
                d.line((rx+10,ry+6,rx+rw//2,ry+rh//2,rx+rw-8,ry+rh-7),fill=env['secondary']+(255,),width=3)
        if rec.get('setpiece'):
            # tiny floor badge for proof only
            d.ellipse((bx-9,by-9,bx+9,by+9),fill=(8,13,24,255),outline=lift(edge,18)+(255,),width=2)

    # Markers deliberately reduced in visual weight versus Pass 20.
    for name,(px,py) in layout['markers'].items():
        if name.startswith('enemy_'): d.ellipse((px-5,py-5,px+5,py+5),fill=q['color']+(255,))
        elif name.startswith('civilian_'): d.ellipse((px-5,py-5,px+5,py+5),fill=(255,210,118,255))
        elif name=='boss': d.ellipse((px-18,py-18,px+18,py+18),outline=q['color']+(255,),width=3)
        elif name.startswith('spawn_gate_'): d.ellipse((px-26,py-26,px+26,py+26),outline=lift(env['secondary'],-20)+(255,),width=2)
        elif name in {'artifact','extraction','reroute_extraction'}: d.ellipse((px-10,py-10,px+10,py+10),outline=env['accent']+(255,),width=2)

    out=OUT/f'pass21_{quest}_variant{idx+1}.png'; im.convert('RGB').save(out); return out

paths=[]
for quest in ('purge','recovery','rescue'):
    for idx,layout in enumerate(LAYOUT_POOLS[quest]): paths.append((quest,idx,render(quest,idx,layout)))

sheet=Image.new('RGB',(1920,1080),(12,16,26)); ds=ImageDraw.Draw(sheet)
ds.text((28,20),'HEX CONTRACT - PASS 21 / WORLD VISUAL HIERARCHY',font=FONT,fill=(245,248,255))
ds.text((28,46),'All nine Pass 20 layouts preserved. Generic grid/support architecture recedes; authored setpieces, destructibles, and one landmark per contract lead.',font=FONT,fill=(178,196,220))
for n,(quest,idx,p) in enumerate(paths):
    row=n//3; col=n%3; xx=28+col*630; yy=82+row*318
    src=Image.open(p).convert('RGB').crop((28,145,1892,990)).resize((600,270),Image.Resampling.LANCZOS)
    sheet.paste(src,(xx,yy)); ds.rectangle((xx,yy,xx+600,yy+270),outline=(63,80,108),width=2)
    ds.text((xx+8,yy+278),f"{LAYOUT_POOLS[quest][idx]['name']}  [{idx+1}/3]",font=FONT,fill=(225,235,248))
ds.text((28,1042),'PASS 21: PRESENTATION ONLY / PASS 20 WORLD DATA + MARKERS + 120 PX CLEARANCE + 36 PX ACTOR CONTRACT FROZEN',font=FONT,fill=(205,221,241))
sheet.save(OUT/'pass21_visual_hierarchy_contact_sheet.png')

# Before/after canonical comparison using existing Pass 20 proof if available.
oldroot=ROOT/'verification/screenshots/pass20'
compare=Image.new('RGB',(1920,1080),(12,16,26)); dc=ImageDraw.Draw(compare)
dc.text((28,18),'HEX CONTRACT - PASS 20 vs PASS 21 / CANONICAL WORLD READABILITY',font=FONT,fill=(245,248,255))
for row,quest in enumerate(('purge','recovery','rescue')):
    old=oldroot/f'pass20_{quest}_variant1.png'; new=OUT/f'pass21_{quest}_variant1.png'
    if old.exists():
        a=Image.open(old).convert('RGB').crop((28,145,1892,990)).resize((880,265),Image.Resampling.LANCZOS)
        compare.paste(a,(28,72+row*326))
    b=Image.open(new).convert('RGB').crop((28,145,1892,990)).resize((880,265),Image.Resampling.LANCZOS)
    compare.paste(b,(1012,72+row*326))
    dc.text((28,45+row*326),'PASS 20',font=FONT,fill=(170,184,207)); dc.text((1012,45+row*326),'PASS 21',font=FONT,fill=(220,235,248))
compare.save(OUT/'pass21_before_after.png')
print('\n'.join(str(p) for _,_,p in paths)); print(OUT/'pass21_visual_hierarchy_contact_sheet.png'); print(OUT/'pass21_before_after.png')
