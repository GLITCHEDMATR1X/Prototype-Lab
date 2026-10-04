from __future__ import annotations

import hashlib
import json
import math
import random
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
BOOK_ROOT = ROOT / "assets" / "books"
OUT = ROOT / "assets" / "orbs"
CATALOG = BOOK_ROOT / "catalog.json"

THEMES = {
    "afterlife": ((28, 45, 78), (102, 176, 220), (130, 82, 180)),
    "entropy": ((4, 8, 20), (48, 105, 188), (230, 95, 66)),
    "matrix": ((3, 22, 28), (55, 214, 215), (151, 77, 205)),
    "utopia": ((14, 11, 30), (58, 215, 230), (232, 91, 174)),
    "apocalypse": ((32, 7, 7), (229, 76, 45), (255, 176, 79)),
    "doomsday": ((31, 6, 4), (222, 64, 39), (255, 191, 81)),
    "crimson": ((35, 5, 10), (194, 44, 67), (242, 145, 71)),
    "sable": ((12, 15, 22), (163, 136, 211), (209, 171, 84)),
    "empty field": ((10, 11, 13), (120, 124, 128), (202, 205, 210)),
    "ghost": ((13, 18, 27), (119, 194, 205), (177, 134, 206)),
    "time": ((11, 13, 31), (81, 150, 228), (231, 201, 95)),
    "andrew": ((10, 19, 24), (49, 219, 204), (236, 85, 125)),
}


def _theme(book: dict):
    text = f"{book.get('id','')} {book.get('title','')}".lower().replace("_", " ")
    for key, colors in THEMES.items():
        if key in text:
            return colors
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    base = tuple(8 + digest[i] % 30 for i in range(3))
    c1 = tuple(80 + digest[i + 3] % 155 for i in range(3))
    c2 = tuple(80 + digest[i + 6] % 155 for i in range(3))
    return base, c1, c2


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _clamp(v):
    return max(0, min(255, int(v)))


def build_story_texture(book: dict, path: Path, size=(512, 256)):
    w, h = size
    base, c1, c2 = _theme(book)
    seed = int.from_bytes(hashlib.sha256(str(book.get("id", "")).encode()).digest()[:8], "big")
    rng = random.Random(seed)
    img = Image.new("RGB", (w, h), base)
    pix = img.load()
    # Equirectangular base with vertical atmospheric banding.
    for y in range(h):
        v = y / max(1, h - 1)
        lat = math.sin(v * math.pi)
        for x in range(w):
            u = x / max(1, w - 1)
            wave = 0.5 + 0.5 * math.sin(u * math.tau * (2 + seed % 5) + v * 4.2)
            t = 0.16 + 0.48 * lat * (0.55 + 0.45 * wave)
            col = _lerp(base, c1, t)
            grain = rng.randint(-7, 7)
            pix[x, y] = tuple(_clamp(ch + grain) for ch in col)

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    # Story-specific longitudinal seams and memory arcs.
    for i in range(8 + seed % 8):
        x = rng.randrange(w)
        width = rng.choice([1, 1, 2, 3])
        gd.line([(x, 0), ((x + rng.randint(-45,45)) % w, h)], fill=(*c2, rng.randint(40, 105)), width=width)
    for i in range(7 + (seed >> 4) % 10):
        cx = rng.randrange(w)
        cy = rng.randrange(h)
        rw = rng.randrange(28, 130)
        rh = rng.randrange(10, 70)
        gd.ellipse((cx-rw, cy-rh, cx+rw, cy+rh), outline=(*c1, rng.randint(24, 85)), width=rng.choice([1,2,3]))
    # Bright memory nodes.
    for i in range(34 + seed % 45):
        x, y = rng.randrange(w), rng.randrange(h)
        r = rng.choice([1,1,1,2,2,3])
        col = c1 if i % 3 else c2
        gd.ellipse((x-r, y-r, x+r, y+r), fill=(*col, rng.randint(90, 190)))

    key = f"{book.get('id','')} {book.get('title','')}".lower()
    # Distinctive story motifs.
    if "matrix" in key or "utopia" in key or "andrew" in key:
        for x in range(0, w, 32):
            gd.line((x, 0, x, h), fill=(*c1, 42), width=1)
        for y in range(0, h, 24):
            gd.line((0, y, w, y), fill=(*c2, 36), width=1)
    if "entropy" in key or "last light" in key or "exodus" in key:
        for _ in range(110):
            x, y = rng.randrange(w), rng.randrange(h)
            a = rng.randint(80, 220)
            gd.point((x,y), fill=(220,230,255,a))
        gd.arc((w//2-105,h//2-105,w//2+105,h//2+105), 208, 336, fill=(*c2,150), width=4)
    if "afterlife" in key or "ghost" in key or "sable" in key:
        for k in range(5):
            off = k * 8
            gd.arc((w//2-92-off,h//2-68-off,w//2+92+off,h//2+68+off), 15, 165, fill=(*c1,70-k*8), width=2)
    if "empty" in key:
        gd.rectangle((0, h//2-2, w, h//2+2), fill=(220,220,224,80))
        for x in range(0,w,64):
            gd.rectangle((x, h//2-10, x+2, h//2+10), fill=(210,210,214,50))
    if "apocalypse" in key or "doomsday" in key or "crimson" in key:
        for _ in range(15):
            x = rng.randrange(w)
            pts = [(x,0)]
            for yy in range(20,h+20,20):
                x = (x + rng.randint(-20,20)) % w
                pts.append((x,min(h,yy)))
            gd.line(pts, fill=(*c2,120), width=2)

    glow = glow.filter(ImageFilter.GaussianBlur(radius=1.25))
    img = Image.alpha_composite(img.convert("RGBA"), glow)
    # Equatorial faint halo to make sphere silhouette feel luminous.
    halo = Image.new("RGBA", (w,h), (0,0,0,0))
    hd = ImageDraw.Draw(halo,"RGBA")
    hd.rectangle((0,h//2-8,w,h//2+8), fill=(*c1,28))
    halo = halo.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img, halo)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, quality=92)


def build_mind_eye(path: Path, size=(512,256)):
    w,h=size
    img=Image.new("RGB",size,(4,7,12))
    draw=ImageDraw.Draw(img,"RGBA")
    cx,cy=w//2,h//2
    for r in range(150,4,-4):
        t=1-r/150
        col=(int(55+180*t), int(45+145*t), int(25+85*t), 20+int(110*t))
        draw.ellipse((cx-r,cy-r//2,cx+r,cy+r//2),outline=col,width=3)
    draw.ellipse((cx-58,cy-58,cx+58,cy+58),fill=(225,170,78,210),outline=(255,231,170,255),width=4)
    draw.ellipse((cx-24,cy-24,cx+24,cy+24),fill=(25,8,5,255),outline=(255,101,55,230),width=4)
    draw.ellipse((cx-8,cy-8,cx+8,cy+8),fill=(255,220,150,255))
    for i in range(36):
        a=math.tau*i/36
        x=cx+math.cos(a)*110; y=cy+math.sin(a)*46
        draw.ellipse((x-2,y-2,x+2,y+2),fill=(180,220,235,110))
    img.save(path)


def main():
    catalog=json.loads(CATALOG.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    count=0
    for book in catalog:
        if not isinstance(book,dict) or not book.get("id"):
            continue
        safe=re.sub(r"[^A-Za-z0-9_.-]+","_",str(book["id"]))
        build_story_texture(book, OUT / f"{safe}.jpg")
        count+=1
    build_mind_eye(OUT / "_archivist_mind_eye.png")
    print(f"built {count} story orb textures in {OUT}")

if __name__ == "__main__":
    main()
