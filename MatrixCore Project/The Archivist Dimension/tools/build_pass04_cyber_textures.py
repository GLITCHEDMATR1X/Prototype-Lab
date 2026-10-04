from __future__ import annotations

import hashlib
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'assets' / 'orbs'
OUT = ROOT / 'assets' / 'cyber_orbs'
CYBER = ROOT / 'assets' / 'cyber'
OUT.mkdir(parents=True, exist_ok=True)
CYBER.mkdir(parents=True, exist_ok=True)


def seed_for(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode('utf-8')).digest()[:8], 'big')


def circuit_overlay(size: tuple[int,int], seed: int, accent=(90, 220, 240), alpha=180) -> Image.Image:
    w, h = size
    layer = Image.new('RGBA', size, (0,0,0,0))
    d = ImageDraw.Draw(layer)
    # fine indexing grid
    for x in range(0, w, 32):
        d.line((x, 0, x, h), fill=(accent[0],accent[1],accent[2],28), width=1)
    for y in range(0, h, 24):
        d.line((0, y, w, y), fill=(accent[0],accent[1],accent[2],22), width=1)
    # deterministic stepped circuit traces that wrap cleanly left/right
    for i in range(18):
        y = 10 + ((seed >> (i % 40)) + i * 37) % max(12, h-20)
        x = -16
        pts=[(x,y)]
        for j in range(8):
            x += 24 + ((seed >> ((i+j)%48)) & 31)
            y += (((seed >> ((i*3+j)%52)) & 3)-1) * 12
            y = max(8,min(h-8,y))
            pts.extend([(x,y),(x+10,y)])
            x += 10
        col=(accent[0],accent[1],accent[2], 65 + (i%3)*28)
        d.line(pts, fill=col, width=2 if i%4==0 else 1)
        for px,py in pts[2::5]:
            d.ellipse((px-2,py-2,px+2,py+2), fill=(accent[0],accent[1],accent[2],alpha))
    # orbital scan bands / machine indexing marks
    for y in (int(h*.18), int(h*.50), int(h*.82)):
        d.rectangle((0,y,w,y+2), fill=(accent[0],accent[1],accent[2],70))
        for x in range((seed % 17), w, 48):
            d.rectangle((x,y-3,x+9,y+5), fill=(accent[0],accent[1],accent[2],95))
    return layer


def cyberize(img: Image.Image, key: str) -> Image.Image:
    im=img.convert('RGB').resize((512,256), Image.Resampling.LANCZOS)
    # pull the imagery into darker metallic contrast, preserving world identity
    im=ImageEnhance.Contrast(im).enhance(1.12)
    im=ImageEnhance.Color(im).enhance(0.82)
    base=im.convert('RGBA')
    seed=seed_for(key)
    palette=[(66,214,232),(124,96,232),(232,168,65),(76,224,150)]
    accent=palette[seed % len(palette)]
    overlay=circuit_overlay(base.size,seed,accent,190)
    # slight smoked-glass veil helps the circuit layer read as embedded, not pasted on.
    smoke=Image.new('RGBA',base.size,(4,8,14,42))
    out=Image.alpha_composite(base,smoke)
    out=Image.alpha_composite(out,overlay)
    # narrow emission bloom baked into the authored texture only.
    glow=overlay.filter(ImageFilter.GaussianBlur(4))
    glow.putalpha(glow.getchannel('A').point(lambda a: min(90,a)))
    out=Image.alpha_composite(out,glow)
    return out.convert('RGB')

count=0
for src in sorted(SRC.glob('*.jpg')):
    with Image.open(src) as im:
        cyberize(im,src.stem).save(OUT/src.name,quality=92,optimize=True)
    count += 1

# Mind eye receives stronger concentric machine rings.
eye_src=SRC/'_archivist_mind_eye.png'
if eye_src.is_file():
    with Image.open(eye_src) as im:
        base=cyberize(im,'archivist_mind_eye').convert('RGBA')
    d=ImageDraw.Draw(base)
    cx,cy=256,128
    for r,a in ((92,110),(70,135),(48,160),(27,185)):
        d.ellipse((cx-r,cy-r*.52,cx+r,cy+r*.52),outline=(220,177,78,a),width=2)
    for a in range(0,360,30):
        x=cx+math.cos(math.radians(a))*110; y=cy+math.sin(math.radians(a))*56
        d.line((cx,cy,x,y), fill=(89,212,231,65), width=1)
    base.convert('RGB').save(CYBER/'archivist_mind_eye_cyber.jpg',quality=94,optimize=True)

# Repeating shell panel material.
w=h=512
shell=Image.new('RGB',(w,h),(8,12,19)); d=ImageDraw.Draw(shell)
# subtle brushed panel bands
for y in range(h):
    v=8+int(6*(0.5+0.5*math.sin(y*0.055)))
    d.line((0,y,w,y),fill=(v,v+4,v+9))
# hard panel frames
for x in range(0,w,128): d.line((x,0,x,h),fill=(34,49,62),width=3)
for y in range(0,h,128): d.line((0,y,w,y),fill=(34,49,62),width=3)
# circuit trunks and nodes
for i in range(28):
    seed=seed_for('shell'+str(i))
    y=16+(seed%(h-32)); x=0
    col=(45,126+(i%3)*25,154+(i%4)*18)
    pts=[(x,y)]
    for j in range(7):
        x += 42 + ((seed >> (j*4)) & 31)
        y += (((seed >> (j*5)) & 3)-1)*18; y=max(12,min(h-12,y))
        pts.append((x,y))
    d.line(pts,fill=col,width=2)
    for x0,y0 in pts[1::2]: d.ellipse((x0-3,y0-3,x0+3,y0+3),fill=(93,219,236))
# sparse gold archive bus lines
for y in (64,256,448):
    d.line((0,y,w,y),fill=(124,85,31),width=2)
    for x in range(24,w,96): d.rectangle((x-4,y-4,x+4,y+4),fill=(198,143,55))
shell.save(CYBER/'archive_shell_cyber.jpg',quality=94,optimize=True)

# Holographic interface grid.
grid=Image.new('RGBA',(512,512),(5,13,20,230)); d=ImageDraw.Draw(grid)
for x in range(0,512,32): d.line((x,0,x,512),fill=(53,166,193,45),width=1)
for y in range(0,512,32): d.line((0,y,512,y),fill=(53,166,193,45),width=1)
for i in range(24):
    x=(i*83)%512; y=(i*131)%512
    d.rectangle((x,y,min(511,x+40+(i%4)*16),min(511,y+3)),fill=(79,213,231,120))
    d.rectangle((x,y,min(511,x+3),min(511,y+28+(i%3)*12)),fill=(79,213,231,90))
grid.save(CYBER/'interface_grid.png')

print(f'cyber story textures: {count}')
print(CYBER/'archive_shell_cyber.jpg')
print(CYBER/'archivist_mind_eye_cyber.jpg')
