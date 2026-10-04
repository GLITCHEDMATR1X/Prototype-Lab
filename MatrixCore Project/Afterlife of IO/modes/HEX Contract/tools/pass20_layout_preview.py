from __future__ import annotations
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from game.world_data import WORLD_RECT, LAYOUT_POOLS, expand_object
from game.data import MISSION_ENVIRONMENTS, QUESTS
OUT=ROOT/'verification/screenshots/pass20'; OUT.mkdir(parents=True,exist_ok=True)
TEX=ROOT/'assets/world'; FONT=ImageFont.load_default()

def lift(c,n): return tuple(max(0,min(255,int(v)+n)) for v in c[:3])
def tile(im,rect,key):
    p=TEX/f'{key}.png'
    if not p.exists(): return
    t=Image.open(p).convert('RGBA'); x0,y0,x1,y1=map(int,rect)
    layer=Image.new('RGBA',(max(1,x1-x0),max(1,y1-y0)),(0,0,0,0))
    for y in range(0,layer.height,t.height):
        for x in range(0,layer.width,t.width): layer.alpha_composite(t,(x,y))
    im.alpha_composite(layer,(x0,y0))

def render(quest,idx,layout):
    env=dict(MISSION_ENVIRONMENTS[quest]); q=QUESTS[quest]
    for k,n in {'floor':14,'grid':16,'wall':20,'edge':22,'fog':10}.items(): env[k]=lift(env[k],n)
    bg=lift(env['fog'],9); im=Image.new('RGBA',(1920,1080),bg+(255,)); d=ImageDraw.Draw(im)
    d.rounded_rectangle((28,18,1892,145),radius=12,fill=(9,15,28,244),outline=env['edge']+(255,),width=2)
    d.text((52,34),'HEX CONTRACT / PASS 20 - MULTIPLE APPROVED BROKEN-MAZE LAYOUTS',font=FONT,fill=(242,248,255,255))
    d.text((52,62),f"{layout['name']} / VARIANT {idx+1} OF 3",font=FONT,fill=env['accent']+(255,))
    d.text((52,91),'120 PX MIN GAP / 36 PX MAX ACTOR / SETPIECE KIT PRESERVED / COVER-INTACT ROUTES VALID',font=FONT,fill=(190,207,230,255))
    d.text((52,118),'Layout changes are authored and deterministic; no free random blocker placement.',font=FONT,fill=(155,176,205,255))
    x,y,w,h=WORLD_RECT; d.rounded_rectangle((x,y,x+w,y+h),radius=7,fill=env['floor']+(255,),outline=env['edge']+(255,),width=3)
    for gx in range(x,x+w,72): d.line((gx,y,gx,y+h),fill=env['grid']+(255,),width=1)
    for gy in range(y,y+h,68): d.line((x,gy,x+w,gy),fill=lift(env['grid'],-3)+(255,),width=1)
    for rec in layout['objects']:
        ob=expand_object(rec)
        for rx,ry,rw,rh in ob['parts']:
            d.rectangle((rx+8,ry+10,rx+rw+8,ry+rh+10),fill=(2,4,9,220))
            d.rounded_rectangle((rx,ry,rx+rw,ry+rh),radius=6,fill=env['wall']+(255,),outline=env['edge']+(255,),width=3)
            tile(im,(rx+4,ry+4,rx+rw-4,ry+rh-4),rec.get('texture',''))
            if ob['destructible']:
                d.line((rx+10,ry+6,rx+rw//2,ry+rh//2,rx+rw-8,ry+rh-7),fill=(255,183,90,255),width=3)
        if rec.get('setpiece'):
            bx,by,bw,bh=ob['bounds']; d.ellipse((bx-11,by-11,bx+11,by+11),fill=(8,13,24,255),outline=(255,210,118,255),width=2)
    for name,(px,py) in layout['markers'].items():
        if name.startswith('enemy_'): d.ellipse((px-11,py-11,px+11,py+11),fill=(90,25,42,255),outline=q['color']+(255,),width=2)
        elif name.startswith('civilian_'): d.ellipse((px-10,py-10,px+10,py+10),fill=(28,76,66,255),outline=(255,210,118,255),width=2)
        elif name=='boss': d.ellipse((px-32,py-32,px+32,py+32),fill=(24,13,32,255),outline=q['color']+(255,),width=4)
        elif name.startswith('spawn_gate_'): d.ellipse((px-42,py-42,px+42,py+42),outline=env['secondary']+(255,),width=3)
        elif name in {'artifact','extraction','reroute_extraction'}: d.ellipse((px-17,py-17,px+17,py+17),outline=env['accent']+(255,),width=3)
    out=OUT/f'pass20_{quest}_variant{idx+1}.png'; im.convert('RGB').save(out); return out

paths=[]
for quest in ('purge','recovery','rescue'):
    for idx,layout in enumerate(LAYOUT_POOLS[quest]): paths.append((quest,idx,render(quest,idx,layout)))
sheet=Image.new('RGB',(1920,1080),(8,11,19)); ds=ImageDraw.Draw(sheet)
ds.text((28,20),'HEX CONTRACT - PASS 20 / 9 APPROVED BROKEN-MAZE LAYOUTS',font=FONT,fill=(245,248,255))
ds.text((28,46),'Three deterministic layouts per contract. Same markers, setpiece identities, actor metric, and route-access contract.',font=FONT,fill=(178,196,220))
for n,(quest,idx,p) in enumerate(paths):
    row=n//3; col=n%3; x=28+col*630; y=82+row*318
    src=Image.open(p).convert('RGB').crop((28,145,1892,990)).resize((600,270),Image.Resampling.LANCZOS)
    sheet.paste(src,(x,y)); ds.rectangle((x,y,x+600,y+270),outline=(70,88,116),width=2)
    ds.text((x+8,y+278),f"{LAYOUT_POOLS[quest][idx]['name']}  [{idx+1}/3]",font=FONT,fill=(225,235,248))
ds.text((28,1042),'PASS 20 CONTRACT: 120 PX MINIMUM GAP / 36 PX MAX ACTOR / ROUTES VALID BEFORE DESTRUCTION / AI + COMBAT BALANCE DATA FROZEN',font=FONT,fill=(205,221,241))
sheet.save(OUT/'pass20_approved_layouts_contact_sheet.png')
print('\n'.join(str(p) for _,_,p in paths)); print(OUT/'pass20_approved_layouts_contact_sheet.png')
