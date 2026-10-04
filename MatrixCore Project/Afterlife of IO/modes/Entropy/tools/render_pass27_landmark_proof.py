"""Static presentation proof for Pass 27 landmark identities.

This is intentionally not presented as a pygame/Panda3D runtime capture.  It is
only a composition check for silhouette variety, naming and hierarchy.
"""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'verification' / 'screenshots' / 'pass27_surface_landmarks.png'
OUT.parent.mkdir(parents=True, exist_ok=True)

W,H=1920,1080
img=Image.new('RGB',(W,H),(8,12,18))
d=ImageDraw.Draw(img)
try:
    title_font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',28)
    name_font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',19)
    sub_font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',12)
except Exception:
    title_font=name_font=sub_font=ImageFont.load_default()

profiles=[
 ('DESERT','SUN RING','ERODED SOLAR ARRAY',(104,66,45),(255,188,102),'sun_ring'),
 ('ICE','CRYO NEEDLES','FROZEN TRANSMISSION SPIRES',(55,72,104),(174,232,255),'cryo_needles'),
 ('JUNGLE','ROOT CATHEDRAL','OVERGROWN ARCHIVE FRAME',(38,78,54),(116,230,145),'root_cathedral'),
 ('VOLCANIC','CALDERA CROWN','THERMAL EXTRACTION RING',(86,42,39),(255,112,72),'caldera_crown'),
 ('CRYSTAL','PRISM CHOIR','FRACTURED SIGNAL LATTICE',(52,55,110),(188,152,255),'prism_choir'),
 ('OCEANIC','FLOOD PYLONS','DROWNED RELAY FIELD',(37,77,104),(102,225,235),'flood_pylons'),
 ('FUNGAL','SPORE CROWN','BIOLOGICAL UPLINK GROWTH',(74,42,84),(224,126,215),'spore_crown'),
 ('RUST','FOUNDRY RIBS','COLLAPSED INDUSTRIAL SPAN',(92,56,40),(224,137,87),'foundry_ribs'),
 ('SALT','MIRROR OBELISK','SALT-GLASS SURVEY MARKER',(110,105,126),(241,235,255),'mirror_obelisk'),
 ('ABYSS','VOID LANTERN','DORMANT DEEP-SIGNAL BEACON',(22,32,63),(79,220,232),'void_lantern'),
 ('STORM','STORM MAST','ATMOSPHERIC DISCHARGE TOWER',(48,60,85),(122,184,255),'storm_mast'),
 ('ROSEGLASS','ROSEGLASS FAN','SHATTERED SPECTRAL ARRAY',(88,42,77),(255,121,213),'roseglass_fan'),
]

# Header
header=(24,18,1896,72)
d.rounded_rectangle(header,12,fill=(4,8,13),outline=(91,230,224),width=2)
text='ENTROPY PASS 27 — SURFACE LANDMARK IDENTITY'
b=d.textbbox((0,0),text,font=title_font); d.text(((W-(b[2]-b[0]))//2,31),text,font=title_font,fill=(236,246,249))
d.text((28,84),'STATIC PRESENTATION PROOF — NOT A NATIVE RUNTIME CAPTURE',font=sub_font,fill=(255,180,94))

cols,rows=4,3
pad=18
top=112
cell_w=(W-pad*(cols+1))//cols
cell_h=(H-top-pad*(rows+1))//rows

def line(points,fill,width=3): d.line(points,fill=fill,width=width,joint='curve')

def shape(kind,cx,cy,r,accent):
    dark=(8,12,18); pale=tuple(min(255,int(c*.65+80)) for c in accent); metal=(112,122,132)
    d.ellipse((cx-r,cy+int(r*.3),cx+r,cy+int(r*.75)),fill=(8,10,12))
    if kind=='sun_ring':
        d.arc((cx-r,cy-r,cx+r,cy+r),195,350,fill=accent,width=7); d.arc((cx-r,cy-r,cx+r,cy+r),15,145,fill=pale,width=5)
        d.ellipse((cx-r//4,cy-r//4,cx+r//4,cy+r//4),fill=dark,outline=accent,width=3); d.rectangle((cx-7,cy-int(r*.62),cx+7,cy+int(r*.48)),fill=pale)
    elif kind=='cryo_needles':
        for i,o in enumerate((-0.42,0,.42)):
            x=cx+int(o*r); hh=int(r*(1.15 if i==1 else .82)); ww=int(r*.22)
            pts=[(x,cy-hh),(x+ww,cy+int(r*.42)),(x,cy+int(r*.24)),(x-ww,cy+int(r*.42))]
            d.polygon(pts,fill=(12,22,35),outline=pale if i==1 else accent)
    elif kind=='root_cathedral':
        d.ellipse((cx-int(r*.62),cy-int(r*.62),cx+int(r*.62),cy+int(r*.62)),fill=(12,27,17),outline=accent,width=5)
        for i in range(7):
            a=i*math.tau/7+.2; ex=cx+int(math.cos(a)*r*.95); ey=cy+int(math.sin(a)*r*.72); line([(cx,cy),(ex,ey)],pale,5)
    elif kind=='caldera_crown':
        d.ellipse((cx-int(r*.78),cy-int(r*.78),cx+int(r*.78),cy+int(r*.78)),fill=(27,10,10),outline=accent,width=7); d.ellipse((cx-int(r*.34),cy-int(r*.34),cx+int(r*.34),cy+int(r*.34)),fill=(6,5,7))
        for i in range(9):
            a=i*math.tau/9; tip=(cx+int(math.cos(a)*r),cy+int(math.sin(a)*r)); base=(cx+int(math.cos(a)*r*.75),cy+int(math.sin(a)*r*.75)); line([base,tip],metal,6)
    elif kind=='prism_choir':
        for i,o in enumerate((-.5,-.17,.2,.54)):
            x=cx+int(o*r); hh=int(r*(1-abs(o)*.4)); ww=int(r*.2); pts=[(x,cy-hh),(x+ww,cy),(x,cy+hh//2),(x-ww,cy)]; d.polygon(pts,fill=(14,17,30),outline=accent if i%2 else pale)
    elif kind=='flood_pylons':
        d.ellipse((cx-int(r*.65),cy-int(r*.48),cx+int(r*.65),cy+int(r*.48)),outline=accent,width=5)
        for i in range(5):
            a=i*math.tau/5+.3; x=cx+int(math.cos(a)*r*.58); y=cy+int(math.sin(a)*r*.4); d.ellipse((x-10,y-10,x+10,y+10),fill=dark,outline=pale,width=3); line([(x,y-10),(x,y-38)],accent,4)
    elif kind=='spore_crown':
        for i in range(6):
            a=i*math.tau/6+.2; x=cx+int(math.cos(a)*r*.55); y=cy+int(math.sin(a)*r*.42); rr=16+(i%2)*5; line([(x,y+rr),(x,y+rr+22)],pale,5); d.ellipse((x-rr,y-rr,x+rr,y+rr),fill=accent,outline=pale,width=2)
    elif kind=='foundry_ribs':
        for i in range(4):
            rr=int(r*(.38+i*.15)); d.arc((cx-rr,cy-int(rr*.6),cx+rr,cy+int(rr*.6)),200,345,fill=metal,width=5)
        line([(cx-r,cy+20),(cx+r,cy-12)],accent,7)
    elif kind=='mirror_obelisk':
        ww=int(r*.3); hh=int(r*1.05); pts=[(cx,cy-hh),(cx+ww,cy),(cx,cy+hh//2),(cx-ww,cy)]; d.polygon(pts,fill=(19,22,29),outline=pale); line([(cx,cy-hh+8),(cx,cy+hh//2-8)],accent,3)
    elif kind=='void_lantern':
        d.ellipse((cx-int(r*.72),cy-int(r*.72),cx+int(r*.72),cy+int(r*.72)),fill=(2,4,8),outline=accent,width=6); d.ellipse((cx-int(r*.42),cy-int(r*.42),cx+int(r*.42),cy+int(r*.42)),outline=pale,width=3); d.ellipse((cx-16,cy-16,cx+16,cy+16),fill=(1,2,5))
    elif kind=='storm_mast':
        line([(cx,cy+int(r*.55)),(cx,cy-int(r*1.05))],metal,8); line([(cx-2,cy+int(r*.5)),(cx-2,cy-int(r*1.0))],pale,2)
        for side in (-1,1):
            x=cx+side*int(r*.55); y=cy-int(r*.35); line([(cx,y),(x,y-15)],accent,5); line([(x,y-15),(x+side*12,y-36),(x+side*2,y-55),(x+side*16,y-78)],pale,3)
    elif kind=='roseglass_fan':
        for i in range(7):
            a=-2.0+i*.31; p1=(cx+int(math.cos(a-.08)*r*.95),cy+int(math.sin(a-.08)*r*.95)); p2=(cx+int(math.cos(a+.08)*r*.95),cy+int(math.sin(a+.08)*r*.95)); d.polygon([(cx,cy),p1,p2],fill=(31,11,31),outline=accent if i%2 else pale)

for idx,(terrain,name,sub,bg,accent,kind) in enumerate(profiles):
    row,col=divmod(idx,cols)
    x=pad+col*(cell_w+pad); y=top+pad+row*(cell_h+pad)
    d.rounded_rectangle((x,y,x+cell_w,y+cell_h),12,fill=bg,outline=tuple(min(255,c+55) for c in bg),width=2)
    # terrain strata
    for k in range(5):
        yy=y+88+k*34
        d.line((x+12,yy,x+cell_w-12,yy-18),fill=tuple(max(0,c-12-k*2) for c in bg),width=8)
    cx=x+cell_w//2; cy=y+cell_h//2+20; shape(kind,cx,cy,64,accent)
    d.rounded_rectangle((x+12,y+12,x+cell_w-12,y+72),8,fill=(4,8,13),outline=accent,width=1)
    d.text((x+24,y+21),terrain,font=sub_font,fill=accent)
    d.text((x+24,y+37),name,font=name_font,fill=(238,246,249))
    d.text((x+24,y+61),sub,font=sub_font,fill=(170,188,198))

img.save(OUT)
print(OUT)
