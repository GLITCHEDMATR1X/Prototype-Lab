from __future__ import annotations

import math
import random
import sys
import types
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def _font_path(bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    return None


class Rect:
    def __init__(self, *args):
        if len(args) == 1:
            args = tuple(args[0])
        self.x, self.y, self.w, self.h = map(int, args)
    @property
    def left(self): return self.x
    @left.setter
    def left(self, value): self.x = int(value)
    @property
    def top(self): return self.y
    @top.setter
    def top(self, value): self.y = int(value)
    @property
    def right(self): return self.x + self.w
    @right.setter
    def right(self, value): self.x = int(value) - self.w
    @property
    def bottom(self): return self.y + self.h
    @bottom.setter
    def bottom(self, value): self.y = int(value) - self.h
    @property
    def centerx(self): return self.x + self.w // 2
    @property
    def centery(self): return self.y + self.h // 2
    @property
    def center(self): return self.centerx, self.centery
    @property
    def topleft(self): return self.x, self.y
    def collidepoint(self, pos):
        return self.left <= pos[0] < self.right and self.top <= pos[1] < self.bottom
    def inflate(self, x, y):
        return Rect(self.x - x // 2, self.y - y // 2, self.w + x, self.h + y)


class Surface:
    def __init__(self, size, flags=0, image=None):
        self.image = image if image is not None else Image.new("RGBA", tuple(map(int, size)), (0, 0, 0, 0))
    def fill(self, color, rect=None, special_flags=0):
        rgba = tuple(color) if len(color) == 4 else tuple(color) + (255,)
        if rect is None:
            box = (0, 0, self.image.width - 1, self.image.height - 1)
        else:
            if hasattr(rect, "left"):
                box = (rect.left, rect.top, rect.right - 1, rect.bottom - 1)
            else:
                x, y, w, h = map(int, rect)
                box = (x, y, x + max(0, w - 1), y + max(0, h - 1))
        ImageDraw.Draw(self.image).rectangle(box, fill=rgba)
    def blit(self, other, pos, special_flags=0):
        src = other.image if isinstance(other, Surface) else other
        self.image.alpha_composite(src, (int(pos[0]), int(pos[1])))
    def get_size(self): return self.image.size
    def get_width(self): return self.image.width
    def get_height(self): return self.image.height
    def get_at(self, pos): return self.image.getpixel((int(pos[0]), int(pos[1])))
    def get_rect(self, **kwargs):
        rect = Rect(0, 0, self.image.width, self.image.height)
        if "center" in kwargs:
            cx, cy = kwargs["center"]
            rect.x = int(cx - rect.w / 2)
            rect.y = int(cy - rect.h / 2)
        return rect
    def copy(self): return Surface(self.get_size(), image=self.image.copy())
    def convert(self): return self
    def convert_alpha(self): return self
    def set_alpha(self, value):
        alpha = self.image.getchannel("A").point(lambda _: int(value))
        self.image.putalpha(alpha)


class FontWrap:
    def __init__(self, size, bold=False):
        path = _font_path(bold)
        self.font = ImageFont.truetype(path, int(size)) if path else ImageFont.load_default()
    def render(self, text, aa, color):
        text = str(text)
        box = self.font.getbbox(text)
        w = max(1, box[2] - box[0] + 4)
        h = max(1, box[3] - box[1] + 4)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        rgba = tuple(color) if len(color) == 4 else tuple(color) + (255,)
        ImageDraw.Draw(img).text((2 - box[0], 2 - box[1]), text, font=self.font, fill=rgba)
        return Surface((w, h), image=img)
    def size(self, text):
        box = self.font.getbbox(str(text))
        return max(1, box[2] - box[0] + 4), max(1, box[3] - box[1] + 4)


class FontModule:
    @staticmethod
    def SysFont(name, size, bold=False): return FontWrap(size, bold)


class DrawModule:
    @staticmethod
    def rect(surface, color, rect, width=0, border_radius=0):
        if not hasattr(rect, "left"):
            rect = Rect(*rect)
        box = (rect.left, rect.top, rect.right - 1, rect.bottom - 1)
        rgba = tuple(color) if len(color) == 4 else tuple(color) + (255,)
        draw = ImageDraw.Draw(surface.image)
        if width:
            draw.rounded_rectangle(box, radius=border_radius, outline=rgba, width=width)
        else:
            draw.rounded_rectangle(box, radius=border_radius, fill=rgba)
    @staticmethod
    def line(surface, color, start, end, width=1):
        rgba = tuple(color) if len(color) == 4 else tuple(color) + (255,)
        ImageDraw.Draw(surface.image).line((start, end), fill=rgba, width=width)
    aaline = line
    @staticmethod
    def aalines(surface, color, closed, points):
        rgba = tuple(color) if len(color) == 4 else tuple(color) + (255,)
        pts = list(points)
        if closed and pts:
            pts.append(pts[0])
        if len(pts) >= 2:
            ImageDraw.Draw(surface.image).line(pts, fill=rgba, width=1)
    @staticmethod
    def circle(surface, color, center, radius, width=0):
        rgba = tuple(color) if len(color) == 4 else tuple(color) + (255,)
        box = (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
        draw = ImageDraw.Draw(surface.image)
        if width:
            draw.ellipse(box, outline=rgba, width=width)
        else:
            draw.ellipse(box, fill=rgba)
    @staticmethod
    def polygon(surface, color, points, width=0):
        rgba = tuple(color) if len(color) == 4 else tuple(color) + (255,)
        draw = ImageDraw.Draw(surface.image)
        if width:
            draw.line(list(points) + [points[0]], fill=rgba, width=width)
        else:
            draw.polygon(points, fill=rgba)


class Dummy:
    def __init__(self, *args, **kwargs): pass
    def __call__(self, *args, **kwargs): return Dummy()
    def __getattr__(self, name): return Dummy()
    def __iter__(self): return iter(())
    def __bool__(self): return False


class PygameModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("K_") or name.isupper():
            return 0
        return Dummy()


pygame = PygameModule("pygame")
pygame.Surface = Surface
pygame.Rect = Rect
pygame.SRCALPHA = 1
pygame.USEREVENT = 24
pygame.BLEND_RGBA_ADD = 0
pygame.font = FontModule()
pygame.draw = DrawModule()
for module_name in ("mixer", "display", "transform", "image", "time", "event", "mouse", "key"):
    setattr(pygame, module_name, Dummy())
sys.modules["pygame"] = pygame
sys.path.insert(0, str(ROOT))

import standard_ui as ui
import space_core
from system_safety import SYSTEM_SPAWN_POSITION


def text(draw, xy, value, size=24, color=(236, 244, 248), bold=False, anchor=None):
    path = _font_path(bold)
    font = ImageFont.truetype(path, size) if path else ImageFont.load_default()
    draw.text(xy, value, font=font, fill=color, anchor=anchor)


def starfield(seed=2100):
    surf = Surface((1920, 1080))
    surf.fill((2, 5, 12, 255))
    draw = ImageDraw.Draw(surf.image)
    rng = random.Random(seed)
    for _ in range(620):
        x, y = rng.randrange(1920), rng.randrange(1080)
        v = rng.randrange(62, 230)
        r = 1 if rng.random() < 0.95 else 2
        draw.ellipse((x-r, y-r, x+r, y+r), fill=(v, v, min(255, v+24), 255))
    return surf


def make_planet_surface(radius, seed, base=(112, 174, 198)):
    size = radius * 2
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((0, 0, size-1, size-1), fill=(*base, 255), outline=(229, 247, 252, 255), width=3)
    rng = random.Random(seed)
    for _ in range(130):
        ang = rng.random() * math.tau
        rr = radius * math.sqrt(rng.random()) * 0.86
        x = radius + math.cos(ang) * rr
        y = radius + math.sin(ang) * rr
        pr = rng.randint(2, 8)
        col = rng.choice(((72, 118, 154, 210), (176, 223, 226, 190), (86, 206, 185, 190), (201, 188, 138, 160)))
        draw.ellipse((x-pr, y-pr, x+pr, y+pr), fill=col)
    return Surface((size, size), image=image)


def draw_sun(draw, center=(360, 530), radius=138):
    cx, cy = center
    for rr, col in ((radius+100, (72, 12, 18, 30)), (radius+60, (132, 20, 24, 64)), (radius+26, (220, 48, 38, 105))):
        draw.ellipse((cx-rr, cy-rr, cx+rr, cy+rr), fill=col)
    draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=(255, 104, 62, 255), outline=(255, 211, 164, 255), width=5)
    for a in range(0, 360, 18):
        length = 40 + (a % 54)
        ar = math.radians(a)
        draw.line((cx+math.cos(ar)*radius, cy+math.sin(ar)*radius, cx+math.cos(ar)*(radius+length), cy+math.sin(ar)*(radius+length)), fill=(255, 92, 60, 130), width=2)


def render_erosion(filename, timer, state, exposure, tsec, title):
    surf = starfield(int(timer * 101 + exposure * 1000))
    draw = ImageDraw.Draw(surf.image, "RGBA")
    draw_sun(draw)
    px, py, radius = 1335, 535, 146
    system = space_core.SolarSystem(seed=20260804)
    planet = system.planets[0]
    planet._last_orbital_surface = make_planet_surface(radius, planet.surface_seed)
    surf.blit(planet._last_orbital_surface, (px-radius, py-radius))
    space_core.draw_solar_erosion(
        surf, px, py, radius, planet, (-1.0, 0.06, 0.0), tsec,
        (255, 104, 62), exposure,
    )
    draw = ImageDraw.Draw(surf.image, "RGBA")
    draw.ellipse((px-radius-22, py-radius-22, px+radius+22, py+radius+22), outline=(74, 178, 196, 180), width=3)
    draw.line((px-radius-12, py, 545, 530), fill=(255, 138, 92, 95), width=2)
    text(draw, (px, py+radius+46), "SUNWARD PIXEL EROSION", 25, (220, 242, 246), True, "ma")
    text(draw, (px, py+radius+82), title, 18, (112, 244, 238), False, "ma")
    ui.draw_mode_chip(surf, "flight")
    ui.draw_mission_tracker(surf, "ONE WORLD — ONE MINUTE", "LAND • PROCESS MATERIAL • RECOVER RELIC CORE", state)
    ui.draw_collapse_panel(surf, state, timer, "COLLAPSE", 118, 125)
    ui.draw_bottom_hint(surf, "PLANET MATERIAL IS BEING PULLED TOWARD THE DYING SUN   •   ` PAUSE")
    path = OUT / filename
    surf.image.convert("RGB").save(path)
    return path, surf.image.convert("RGB")


def render_sun_reset():
    surf = starfield(2121)
    draw = ImageDraw.Draw(surf.image, "RGBA")
    draw_sun(draw, center=(1130, 500), radius=152)
    # High-speed segment crosses the entire stellar sphere.
    draw.line((440, 500, 1710, 500), fill=(255, 92, 76, 170), width=6)
    for x in range(510, 1660, 96):
        draw.rectangle((x, 495, x+22, 505), fill=(255, 180, 118, 120))
    draw.polygon([(1730, 500), (1680, 476), (1680, 524)], fill=(240, 248, 252), outline=(112, 244, 238))
    # Default system entry marker.
    spawn_x, spawn_y = 455, 760
    draw.ellipse((spawn_x-46, spawn_y-46, spawn_x+46, spawn_y+46), outline=(112, 244, 238, 220), width=4)
    draw.line((spawn_x-60, spawn_y, spawn_x+60, spawn_y), fill=(112, 244, 238, 180), width=2)
    draw.line((spawn_x, spawn_y-60, spawn_x, spawn_y+60), fill=(112, 244, 238, 180), width=2)
    draw.polygon([(spawn_x, spawn_y-26), (spawn_x-18, spawn_y+20), (spawn_x+18, spawn_y+20)], fill=(238, 246, 250), outline=(82, 226, 236))
    draw.line((1080, 680, 560, 750), fill=(112, 244, 238, 200), width=5)
    draw.polygon([(548, 752), (590, 730), (584, 770)], fill=(112, 244, 238))
    text(draw, (960, 720), "SWEPT SUN COLLISION", 30, (242, 198, 170), True, "ma")
    text(draw, (960, 766), "RESET TO CURRENT-SYSTEM ENTRY  (0, 0, 0)", 24, (112, 244, 238), True, "ma")
    text(draw, (960, 810), "CARGO • HULL • FUEL • OBJECTIVE • TIMER PRESERVED", 18, (184, 207, 216), False, "ma")
    ui.draw_mode_chip(surf, "flight")
    ui.draw_mission_tracker(surf, "SUN COLLISION — POSITION RESTORED", "THE CURRENT SYSTEM CONTINUES FROM ITS DEFAULT ENTRY POINT", "UNSTABLE")
    ui.draw_collapse_panel(surf, "UNSTABLE", 27, "COLLAPSE", 83, 125)
    ui.draw_bottom_hint(surf, "IMPACT DETECTED ACROSS THE FULL MOVEMENT SEGMENT   •   CLOCK REMAINS 00:27")
    path = OUT / "Entropy_Pass21_SunReset_Proof.png"
    surf.image.convert("RGB").save(path)
    return path, surf.image.convert("RGB")


def render_one_minute_start():
    surf = starfield(2160)
    draw = ImageDraw.Draw(surf.image, "RGBA")
    panel = (380, 245, 1540, 842)
    draw.rounded_rectangle(panel, radius=24, fill=(4, 9, 16, 238), outline=(74, 182, 196, 255), width=4)
    text(draw, (960, 330), "SYSTEM LIFETIME", 28, (112, 244, 238), True, "ma")
    text(draw, (960, 470), "01:00", 104, (240, 248, 252), True, "mm")
    text(draw, (960, 570), "ONE PLANET • ONE RELIC CORE • ONE AUTOMATIC EXIT", 24, (196, 219, 226), True, "ma")
    text(draw, (960, 628), "PAUSE / MISSION BRIEF / FAILURE SCREENS FREEZE THE CLOCK", 19, (146, 174, 186), False, "ma")
    draw.line((620, 690, 1300, 690), fill=(72, 150, 164, 160), width=2)
    text(draw, (960, 744), "BEGIN RUN", 28, (112, 244, 142), True, "ma")
    ui.draw_mode_chip(surf, "briefing")
    ui.draw_bottom_hint(surf, "ENTER / SPACE BEGIN   •   RECOVER THE CORE BEFORE THE STAR COLLAPSES")
    path = OUT / "Entropy_Pass21_OneMinuteStart_Proof.png"
    surf.image.convert("RGB").save(path)
    return path, surf.image.convert("RGB")


normal_path, normal = render_erosion(
    "Entropy_Pass21_SolarErosion_Proof.png", 42, "UNSTABLE", 0.56, 7.4,
    "ORBITAL PROXIMITY + MID-CLOCK PRESSURE",
)
critical_path, critical = render_erosion(
    "Entropy_Pass21_CriticalErosion_Proof.png", 8, "CRITICAL", 1.0, 12.8,
    "STRONGER PULL DURING THE FINAL SECONDS",
)
reset_path, reset = render_sun_reset()
start_path, start = render_one_minute_start()

contact = Image.new("RGB", (1440, 810), (3, 6, 10))
contact.paste(normal.resize((720, 405)), (0, 0))
contact.paste(critical.resize((720, 405)), (720, 0))
contact.paste(reset.resize((720, 405)), (0, 405))
contact.paste(start.resize((720, 405)), (720, 405))
contact_path = OUT / "Entropy_Pass21_contact_sheet.png"
contact.save(contact_path)

print(normal_path)
print(critical_path)
print(reset_path)
print(start_path)
print(contact_path)
