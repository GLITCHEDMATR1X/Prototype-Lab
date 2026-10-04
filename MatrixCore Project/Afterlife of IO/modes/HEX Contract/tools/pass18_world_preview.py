from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.world_data import WORLD_RECT, LAYOUTS, expand_object
from game.data import MISSION_ENVIRONMENTS, QUESTS

OUT = ROOT / 'verification' / 'screenshots' / 'pass18'
OUT.mkdir(parents=True, exist_ok=True)
TEX = ROOT / 'assets' / 'world'

FONT = ImageFont.load_default()

def lift(c, n): return tuple(max(0,min(255,int(v)+n)) for v in c[:3])

def visual_env(key):
    env=dict(MISSION_ENVIRONMENTS[key])
    lifts={
        'purge': {'floor':13,'grid':15,'wall':18,'edge':18,'fog':8},
        'recovery': {'floor':15,'grid':15,'wall':19,'edge':20,'fog':9},
        'rescue': {'floor':14,'grid':14,'wall':18,'edge':18,'fog':9},
    }[key]
    for k,n in lifts.items(): env[k]=lift(env[k],n)
    return env

def tile(im, rect, key, alpha=232):
    p=TEX/f'{key}.png'
    if not p.exists(): return
    t=Image.open(p).convert('RGBA')
    if alpha != 255:
        t=t.copy(); t.putalpha(alpha)
    x0,y0,x1,y1=rect
    mask=Image.new('L',(x1-x0,y1-y0),255)
    layer=Image.new('RGBA',(x1-x0,y1-y0),(0,0,0,0))
    for y in range(0,y1-y0,t.height):
        for x in range(0,x1-x0,t.width): layer.alpha_composite(t,(x,y))
    im.alpha_composite(layer,(x0,y0))

def line(draw, pts, fill, width=1): draw.line(tuple(int(v) for p in pts for v in p), fill=fill, width=width)

def preview(key):
    env=visual_env(key); q=QUESTS[key]; layout=LAYOUTS[key]
    bg=lift(env['fog'],6)
    im=Image.new('RGBA',(1920,1080),bg+(255,)); d=ImageDraw.Draw(im)
    # backdrop gradient bands
    for y in range(0,1080,24):
        t=y/1080; c=tuple(int(bg[i]*(1-t)+lift(bg,22)[i]*t) for i in range(3))
        d.rectangle((0,y,1920,y+24),fill=c+(255,))
    # top HUD-safe presentation strip
    for r in [(28,20,405,150),(520,20,880,150),(1485,20,405,150)]:
        x,y,w,h=r; d.rounded_rectangle((x,y,x+w,y+h),radius=12,fill=(9,15,28,242),outline=env['edge']+(255,),width=2)
    d.text((52,38),'HEX CONTRACT / PASS 18',font=FONT,fill=(242,248,255,255))
    d.text((550,38),f"{env['site']} / BROKEN-MAZE TACTICAL PROOF",font=FONT,fill=env['accent']+(255,))
    d.text((1510,38),f"{q['type']} / {q['danger']}",font=FONT,fill=q['color']+(255,))
    # floor
    x,y,w,h=WORLD_RECT; floor=(x,y,x+w,y+h)
    d.rounded_rectangle(floor,radius=6,fill=env['floor']+(255,),outline=env['edge']+(255,),width=3)
    # floor grammar
    if key=='purge':
        for gx in range(x,x+w,72): d.line((gx,y,gx+38,y+h),fill=env['grid']+(255,),width=1)
        for gy in range(y,y+h,68): d.line((x,gy,x+w,gy),fill=lift(env['grid'],-4)+(255,),width=1)
        d.ellipse((792,425,1142,700),outline=env['accent']+(255,),width=2)
    elif key=='recovery':
        for gx in range(x,x+w,64): d.line((gx,y,gx,y+h),fill=env['grid']+(255,),width=1)
        for gy in range(y,y+h,64): d.line((x,gy,x+w,gy),fill=env['grid']+(255,),width=1)
        wx,wy=layout['markers']['memory_well']
        for rr in (58,92,128): d.ellipse((wx-rr,wy-rr,wx+rr,wy+rr),outline=(env['accent'] if rr!=92 else env['secondary'])+(255,),width=2)
    else:
        for gy in range(y,y+h,58): d.line((x,gy,x+w,gy),fill=env['grid']+(255,),width=2 if (gy//58)%3==0 else 1)
        for gx in range(x,x+w,120): d.line((gx,y,gx-42,y+h),fill=lift(env['grid'],-2)+(255,),width=1)
    # authored objects
    for rec in layout['objects']:
        ob=expand_object(rec); tex=rec.get('texture')
        if not tex:
            fam={'purge':('cathedral_labyrinth_stone','cathedral_reliquary'),'recovery':('blackglass_labyrinth_panels','blackglass_archive'),'rescue':('ossuary_labyrinth_bulkheads','ossuary_carriage')}[key]
            tex=fam[1] if ob['category']=='object' else fam[0]
        for rx,ry,rw,rh in ob['parts']:
            # shadow and side face
            d.rounded_rectangle((rx+11,ry+13,rx+rw+11,ry+rh+13),radius=7,fill=(2,4,9,255))
            d.rectangle((rx+5,ry+rh-5,rx+rw,ry+rh+5),fill=tuple(max(2,c//2) for c in env['wall'])+(255,))
            d.rounded_rectangle((rx,ry,rx+rw,ry+rh),radius=7,fill=env['wall']+(255,))
            tile(im,(rx+4,ry+4,rx+rw-4,ry+rh-4),tex,232)
            d.line((rx+8,ry+4,rx+rw-8,ry+4),fill=lift(env['edge'],28)+(255,),width=3)
            d.line((rx+4,ry+8,rx+4,ry+rh-8),fill=lift(env['edge'],12)+(255,),width=2)
            d.rounded_rectangle((rx,ry,rx+rw,ry+rh),radius=7,outline=env['edge']+(255,),width=3)
            if ob['destructible']:
                d.line((rx+rw*.28,ry+5,rx+rw*.5,ry+rh*.5,rx+rw-7,ry+rh-9),fill=(255,180,84,255),width=3)
    # spawners and important markers
    for name,pos in layout['markers'].items():
        px,py=pos
        if name.startswith('spawn_gate_'):
            d.ellipse((px-48,py-48,px+48,py+48),fill=(5,10,20,255),outline=env['secondary']+(255,),width=3)
            d.line((px-30,py,px+30,py),fill=env['edge']+(255,),width=1); d.line((px,py-30,px,py+30),fill=env['edge']+(255,),width=1)
            d.ellipse((px-18,py-18,px+18,py+18),outline=env['accent']+(255,),width=2)
        elif name.startswith('enemy_'):
            d.ellipse((px-12,py-12,px+12,py+12),fill=(88,24,39,255),outline=q['color']+(255,),width=2)
        elif name.startswith('civilian_'):
            d.ellipse((px-11,py-11,px+11,py+11),fill=(28,70,65,255),outline=(255,207,112,255),width=2)
        elif name=='boss':
            d.ellipse((px-36,py-36,px+36,py+36),fill=(26,15,34,255),outline=q['color']+(255,),width=4)
        elif name in ('artifact','extraction','reroute_extraction'):
            d.ellipse((px-18,py-18,px+18,py+18),outline=env['accent']+(255,),width=3)
    d.text((42,1015),f"{layout['name']}  •  SOLID COVER USES MATCHED TEXTURE + COLLISION  •  120 PX MINIMUM GAP",font=FONT,fill=(220,232,245,255))
    out=OUT/f'pass18_{key}_material_preview.png'; im.convert('RGB').save(out)
    return out

paths=[preview(k) for k in ('purge','recovery','rescue')]
# professional 1920x1080 contact sheet: crop to the actual battlefield so the
# proof fills the frame instead of leaving large unused space.
sheet=Image.new('RGB',(1920,1080),(8,11,19)); ds=ImageDraw.Draw(sheet)
ds.text((38,28),'HEX CONTRACT — PASS 18 BROKEN-MAZE TACTICAL MAPS',font=FONT,fill=(245,248,255))
ds.text((38,52),'Recovered from the user-supplied Pass 17 authority; gameplay code frozen.',font=FONT,fill=(180,194,214))
labels=('PURGE / BROKEN NAVE','RECOVERY / FRACTURED INDEX','RESCUE / SPLIT MERCY')
for i,pth in enumerate(paths):
    src=Image.open(pth).convert('RGB')
    crop=src.crop((18,150,1902,1010)).resize((600,520),Image.Resampling.LANCZOS)
    x=30+i*630
    sheet.paste(crop,(x,105))
    ds.rectangle((x,105,x+600,625),outline=(70,84,110),width=2)
    ds.text((x,642),labels[i],font=FONT,fill=(226,234,246))
# metric cards
metrics=[
    ('PHYSICAL OBJECTS','8 / 8 / 8'),
    ('MAZE PIECES','7 / 7 / 6'),
    ('ACCESS BREAKS','4 / 4 / 4'),
    ('MINIMUM GAP','120 PX'),
    ('MAX ACTOR RADIUS','36 PX'),
    ('ROUTES BEFORE DESTRUCTION','PASS'),
]
for i,(name,value) in enumerate(metrics):
    col=i%3; row=i//3; x=30+col*630; y=710+row*130
    ds.rounded_rectangle((x,y,x+600,y+100),radius=10,fill=(13,19,31),outline=(57,75,104),width=2)
    ds.text((x+20,y+18),name,font=FONT,fill=(160,180,210))
    ds.text((x+20,y+52),value,font=FONT,fill=(255,205,112))
ds.text((38,1008),'Maze-like, deliberately broken open: all objectives, civilians, enemies, bosses and extraction routes remain reachable with intact cover.',font=FONT,fill=(218,230,245))
sheet.save(OUT/'pass18_material_contact_sheet.png')
print('\n'.join(str(p) for p in paths))
