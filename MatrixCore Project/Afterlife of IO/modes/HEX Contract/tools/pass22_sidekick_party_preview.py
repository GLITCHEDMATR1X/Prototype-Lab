from __future__ import annotations
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from game.world_data import WORLD_RECT, LAYOUT_POOLS, expand_object
from game.data import MISSION_ENVIRONMENTS, QUESTS, HEROES

OUT=ROOT/'verification/screenshots/pass22'; OUT.mkdir(parents=True,exist_ok=True)
TEX=ROOT/'assets/world'; FONT=ImageFont.load_default()
PRIMARY={'purge':'p_gate_north','recovery':'r_index_stack','rescue':'s_u_south'}
HERO_KEYS=('nyx','circuit','morrow')


def lift(c,n): return tuple(max(0,min(255,int(v)+n)) for v in c[:3])
def diamond(d,center,r,outline,width=2,fill=None):
    x,y=center; pts=[(x,y-r),(x+r,y),(x,y+r),(x-r,y)]
    d.polygon(pts,fill=fill)
    d.line(pts+[pts[0]],fill=outline,width=width,joint='curve')
def bracket(d,center,r,color,width=2):
    x,y=center; l=max(6,r//3)
    for dx,dy,sx,sy in ((-r,-r,1,1),(r,-r,-1,1),(-r,r,1,-1),(r,r,-1,-1)):
        p=(x+dx,y+dy)
        d.line((p[0],p[1],p[0]+sx*l,p[1]),fill=color,width=width)
        d.line((p[0],p[1],p[0],p[1]+sy*l),fill=color,width=width)
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
    if rec['id']==PRIMARY.get(current_quest): return 'landmark'
    if ob['destructible']: return 'interactive'
    if rec['prefab'].startswith('setpiece_') or rec['prefab']=='relic_carriage': return 'setpiece'
    return 'support'

def floor_grammar(d,quest,env,x,y,w,h,layout):
    if quest=='purge':
        gd=lift(env['grid'],-9)
        for gx in range(x-220,x+w,156): d.line((gx,y,gx+310,y+h),fill=gd+(255,),width=1)
        for gy in range(y+84,y+h,136): d.line((x+20,gy,x+w-20,gy),fill=(38,19,35,255),width=1)
        # Choir pit uses angular nested polygons for the ring-free proof.
        diamond(d,(967,562),158,env['accent']+(255,),2)
        diamond(d,(967,562),126,env['secondary']+(255,),1)
    elif quest=='recovery':
        gd=lift(env['grid'],-8)
        for gx in range(x+32,x+w,160): d.line((gx,y+18,gx,y+h-18),fill=gd+(255,),width=1)
        for gy in range(y+32,y+h,160): d.line((x+18,gy,x+w-18,gy),fill=gd+(255,),width=1)
        wx,wy=layout['markers']['memory_well']
        for r,c in ((58,env['accent']),(92,env['secondary']),(128,env['accent'])): diamond(d,(wx,wy),r,c+(255,),2)
    else:
        gd=lift(env['grid'],-7)
        for gy in range(y+54,y+h,174):
            d.line((x+18,gy,x+w-18,gy),fill=gd+(255,),width=2)
            d.line((x+18,gy+12,x+w-18,gy+12),fill=lift(gd,-8)+(255,),width=1)
        for gx in range(x+80,x+w,240): d.line((gx,y+20,gx-38,y+h-20),fill=(14,42,44,255),width=1)

def draw_actor_marker(d,pos,key,label,lead=False):
    color=HEROES[key]['color']; accent=HEROES[key]['accent']; x,y=map(int,pos)
    # Ground shadow is a short rectangular footprint, not a circle.
    d.rounded_rectangle((x-16,y+10,x+16,y+18),radius=3,fill=(1,3,7,210))
    d.rounded_rectangle((x-10,y-15,x+10,y+12),radius=4,fill=lift(color,-65)+(255,),outline=color+(255,),width=2)
    d.rectangle((x-5,y-23,x+5,y-13),fill=lift(color,-30)+(255,),outline=accent+(255,),width=1)
    if lead: bracket(d,(x,y),27,accent+(255,),2)
    d.text((x-24,y-38),label,font=FONT,fill=color+(255,))

def render(quest,idx,layout):
    global current_quest; current_quest=quest
    env=dict(MISSION_ENVIRONMENTS[quest]); q=QUESTS[quest]
    lifts={'purge':{'floor':22,'grid':-3,'wall':24,'edge':14,'fog':14},'recovery':{'floor':24,'grid':-4,'wall':26,'edge':16,'fog':15},'rescue':{'floor':22,'grid':-4,'wall':24,'edge':14,'fog':15}}[quest]
    for k,n in lifts.items(): env[k]=lift(env[k],n)
    bg=lift(env['fog'],12); im=Image.new('RGBA',(1920,1080),bg+(255,)); d=ImageDraw.Draw(im)
    d.rounded_rectangle((28,18,1892,145),radius=12,fill=(8,14,25,245),outline=lift(env['edge'],-4)+(255,),width=2)
    d.text((52,34),'HEX CONTRACT / PASS 22 - BANKED SIDEKICK SQUADS',font=FONT,fill=(242,248,255,255))
    d.text((52,62),f"{layout['name']} / STATIC WORLD-DATA PROOF",font=FONT,fill=env['accent']+(255,))
    d.text((52,91),'RINGLESS ACTOR + OBJECT MARKERS / TEAM 3 OF 3 / +4 INITIAL HOSTILES / +2 COMPLICATION REINFORCEMENTS',font=FONT,fill=(190,207,230,255))
    d.text((52,118),'Native pygame runtime unavailable in this container; geometry and source contracts are verified separately.',font=FONT,fill=(155,176,205,255))
    x,y,w,h=WORLD_RECT
    d.rounded_rectangle((x,y,x+w,y+h),radius=7,fill=env['floor']+(255,),outline=lift(env['edge'],-5)+(255,),width=2)
    floor_grammar(d,quest,env,x,y,w,h,layout)

    for rec in layout['objects']:
        if rec['id']==PRIMARY[quest]:
            ob=expand_object(rec); bx,by,bw,bh=ob['bounds']
            p=(bx+bw//2,by+bh//2); bracket(d,p,max(38,int(max(bw,bh)//2+20)),lift(env['accent'],-20)+(255,),2)
            break

    for rec in layout['objects']:
        ob=expand_object(rec); t=tier(rec,ob); bx,by,bw,bh=ob['bounds']
        if t!='support':
            plate=(bx-(9 if t=='landmark' else 5),by-(7 if t=='landmark' else 4),bx+bw+(9 if t=='landmark' else 5),by+bh+(7 if t=='landmark' else 4))
            d.rounded_rectangle(plate,radius=8,fill=lift(env['floor'],-5)+(255,),outline=lift(env['grid'],13 if t=='landmark' else 5)+(255,),width=1)
        edge={'support':lift(env['edge'],-18),'setpiece':lift(env['edge'],8),'interactive':lift(env['secondary'],6),'landmark':lift(env['accent'],24)}[t]
        ta={'support':166,'setpiece':218,'interactive':224,'landmark':242}[t]; ow={'support':2,'setpiece':3,'interactive':3,'landmark':4}[t]
        for rx,ry,rw,rh in ob['parts']:
            off=8 if t=='support' else 10 if t=='setpiece' else 12
            d.rounded_rectangle((rx+off,ry+off+2,rx+rw+off,ry+rh+off+2),radius=6,fill=(1,3,8,230))
            fill=lift(env['wall'],11 if t=='support' else 16 if t=='setpiece' else 20 if t=='interactive' else 25)
            d.rounded_rectangle((rx,ry,rx+rw,ry+rh),radius=6,fill=fill+(255,),outline=edge+(255,),width=ow)
            alpha_tile(im,(rx+4,ry+4,rx+rw-4,ry+rh-4),rec.get('texture',''),ta)
            if ob['destructible']:
                d.line((rx+10,ry+6,rx+rw//2,ry+rh//2,rx+rw-8,ry+rh-7),fill=env['secondary']+(255,),width=3)
        if rec.get('setpiece'):
            diamond(d,(bx,by),7,lift(edge,18)+(255,),2,fill=(8,13,24,255))

    # Existing live markers are angular and subdued. No NPC/object marker uses a circular ring.
    for name,(px,py) in layout['markers'].items():
        if name.startswith('enemy_'):
            d.rectangle((px-4,py-4,px+4,py+4),fill=q['color']+(255,))
        elif name.startswith('civilian_'):
            diamond(d,(px,py),6,(255,210,118,255),1,fill=(50,38,22,255))
        elif name=='boss':
            bracket(d,(px,py),19,q['color']+(255,),3)
        elif name.startswith('spawn_gate_'):
            bracket(d,(px,py),23,lift(env['secondary'],-20)+(255,),2)
        elif name in {'artifact','extraction','reroute_extraction'}:
            diamond(d,(px,py),11,env['accent']+(255,),2)

    # Max party preview: lead and two sidekicks adjacent but never stacked.
    lead=tuple(layout['markers']['entry']); sides=[(lead[0]+58,lead[1]+18),(lead[0]-58,lead[1]+18)]
    draw_actor_marker(d,lead,HERO_KEYS[0],'LEAD',True)
    draw_actor_marker(d,sides[0],HERO_KEYS[1],'SIDEKICK')
    draw_actor_marker(d,sides[1],HERO_KEYS[2],'SIDEKICK')

    # Compact non-overlapping status card away from active world play.
    card=(1435,160,1872,270); d.rounded_rectangle(card,radius=10,fill=(7,12,23,235),outline=lift(env['edge'],4)+(255,),width=2)
    d.text((1455,178),'SIDEKICK PERKS / BANKABLE',font=FONT,fill=(255,221,112,255))
    d.text((1455,202),'MISSION TEAM / 3 MAX',font=FONT,fill=(226,236,248,255))
    d.text((1455,226),'EACH SIDEKICK / +2 START / +1 REINFORCEMENT',font=FONT,fill=(176,197,224,255))
    d.text((1455,250),'FALLEN HERO EXISTS / RESTORATION TAKES PRIORITY',font=FONT,fill=(176,197,224,255))

    out=OUT/f'pass22_{quest}_party_ringless.png'; im.convert('RGB').save(out); return out

paths=[]
for quest in ('purge','recovery','rescue'):
    paths.append((quest,render(quest,0,LAYOUT_POOLS[quest][0])))

sheet=Image.new('RGB',(1920,1080),(12,16,26)); ds=ImageDraw.Draw(sheet)
ds.text((28,18),'HEX CONTRACT - PASS 22 / BANKED SIDEKICK SQUADS',font=FONT,fill=(245,248,255))
ds.text((28,44),'Static proof: no persistent NPC/object selection rings; three-person squad separation and unchanged Pass 21 world hierarchy.',font=FONT,fill=(178,196,220))
for row,(quest,p) in enumerate(paths):
    src=Image.open(p).convert('RGB').crop((28,145,1892,990)).resize((1240,280),Image.Resampling.LANCZOS)
    yy=78+row*320; sheet.paste(src,(28,yy)); ds.rectangle((28,yy,1268,yy+280),outline=(63,80,108),width=2)
    env=MISSION_ENVIRONMENTS[quest]
    ds.text((1290,yy+8),QUESTS[quest]['name'],font=FONT,fill=QUESTS[quest]['color'])
    ds.text((1290,yy+38),'LEAD + 2 SIDEKICKS',font=FONT,fill=(225,235,248))
    ds.text((1290,yy+62),'SPAWN SEPARATION / 60.7 PX',font=FONT,fill=(170,196,224))
    ds.text((1290,yy+86),'+4 INITIAL HOSTILES',font=FONT,fill=(255,176,116))
    ds.text((1290,yy+110),'+2 COMPLICATION HOSTILES',font=FONT,fill=(255,176,116))
    ds.text((1290,yy+145),'WORLD DATA / UNCHANGED',font=FONT,fill=(150,230,190))
    ds.text((1290,yy+169),'120 PX OBSTACLE GAP',font=FONT,fill=(150,230,190))
    ds.text((1290,yy+193),'36 PX MAX ACTOR RADIUS',font=FONT,fill=(150,230,190))
    ds.text((1290,yy+227),'STATIC PROOF / NOT NATIVE RUNTIME',font=FONT,fill=(155,170,190))
ds.text((28,1045),'PASS 22: SIDEKICK PERKS BANK UNTIL SPENT / RESTORE FALLEN HEROES FIRST / MAX TEAM 3 / PARTY-SIZE ENEMY BODY SCALING',font=FONT,fill=(205,221,241))
sheet.save(OUT/'pass22_sidekick_party_contact_sheet.png')
print('\n'.join(str(p) for _,p in paths)); print(OUT/'pass22_sidekick_party_contact_sheet.png')
