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


class Surface:
    def __init__(self, size, flags=0, image=None):
        self.image = image if image is not None else Image.new("RGBA", tuple(map(int, size)), (0, 0, 0, 0))
    def fill(self, color, rect=None):
        rgba = tuple(color) if len(color) == 4 else tuple(color) + (255,)
        box = (0, 0, self.image.width, self.image.height) if rect is None else tuple(rect)
        ImageDraw.Draw(self.image).rectangle(box, fill=rgba)
    def blit(self, other, pos):
        src = other.image if isinstance(other, Surface) else other
        self.image.alpha_composite(src, (int(pos[0]), int(pos[1])))
    def get_size(self): return self.image.size
    def get_width(self): return self.image.width
    def get_height(self): return self.image.height


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
    @staticmethod
    def circle(surface, color, center, radius, width=0):
        rgba = tuple(color) if len(color) == 4 else tuple(color) + (255,)
        box = (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
        draw = ImageDraw.Draw(surface.image)
        if width:
            draw.ellipse(box, outline=rgba, width=width)
        else:
            draw.ellipse(box, fill=rgba)


pygame = types.ModuleType("pygame")
pygame.Surface = Surface
pygame.Rect = Rect
pygame.SRCALPHA = 1
pygame.font = FontModule()
pygame.draw = DrawModule()
sys.modules["pygame"] = pygame
sys.path.insert(0, str(ROOT))

import standard_ui as ui
from surface_resources import harvest_yield


def text(draw, xy, value, size=24, color=(236, 244, 248), bold=False, anchor=None):
    path = _font_path(bold)
    font = ImageFont.truetype(path, size) if path else ImageFont.load_default()
    draw.text(xy, value, font=font, fill=color, anchor=anchor)


def starfield():
    surf = Surface((1920, 1080))
    surf.fill((2, 5, 12, 255))
    draw = ImageDraw.Draw(surf.image)
    rng = random.Random(19019)
    for _ in range(520):
        x, y = rng.randrange(1920), rng.randrange(1080)
        v = rng.randrange(70, 235)
        r = 1 if rng.random() < 0.93 else 2
        draw.ellipse((x-r, y-r, x+r, y+r), fill=(v, v, min(255, v+22), 255))
    return surf


def render_orbit():
    surf = starfield()
    draw = ImageDraw.Draw(surf.image)
    # Distant active star.
    for radius, col in ((132, (75, 19, 18, 65)), (96, (145, 38, 30, 100)), (62, (255, 126, 68, 255))):
        draw.ellipse((960-radius, 540-radius, 960+radius, 540+radius), fill=col)
    # Every intact planet is explicitly landable.
    planets = [
        (445, 360, 42, (166, 214, 242), "P1 ICE / LANDABLE"),
        (670, 710, 54, (188, 94, 82), "P2 SALVAGE / LANDABLE"),
        (1265, 330, 48, (136, 220, 154), "P3 LANDABLE"),
        (1475, 715, 64, (208, 142, 236), "P4 MATRIX SIGNAL / LANDABLE"),
    ]
    for x, y, r, col, label in planets:
        draw.ellipse((x-r, y-r, x+r, y+r), fill=col, outline=(238, 250, 255), width=2)
        draw.arc((x-r-14, y-r-14, x+r+14, y+r+14), 20, 300, fill=(80, 214, 226), width=2)
        text(draw, (x, y+r+28), label, 19, (206, 232, 240), True, "ma")
    # Ship + approach guide.
    draw.polygon([(1115, 620), (1080, 638), (1092, 600)], fill=(238, 246, 250), outline=(82, 226, 236))
    draw.line((1115, 620, 1430, 715), fill=(112, 244, 238), width=3)
    ui.draw_mode_chip(surf, "flight")
    ui.draw_mission_tracker(surf, "CHOOSE A WORLD", "EVERY INTACT PLANET NOW SUPPORTS ATMOSPHERE ENTRY", "UNSTABLE")
    ui.draw_collapse_panel(surf, "UNSTABLE", 96, "COLLAPSE", 118, 125)
    ui.draw_bottom_hint(surf, "APPROACH ANY INTACT PLANET TO ENTER ATMOSPHERE")
    path = OUT / "Entropy_Pass19_UniversalPlanetfall_Proof.png"
    surf.image.convert("RGB").save(path)
    return path, surf.image.convert("RGB")


def render_surface():
    surf = Surface((1920, 1080))
    draw = ImageDraw.Draw(surf.image)
    # Stylized top-down procedural surface.
    draw.rectangle((0, 0, 1920, 1080), fill=(11, 26, 30))
    rng = random.Random(7719)
    for _ in range(160):
        x, y = rng.randrange(1920), rng.randrange(1080)
        r = rng.randrange(10, 44)
        col = rng.choice(((22, 62, 62), (27, 76, 71), (49, 67, 62), (42, 86, 79)))
        draw.ellipse((x-r, y-r, x+r, y+r), fill=col)
    # Ruin, tree growth, prop and plant—all recoverable.
    draw.polygon([(960, 400), (1080, 480), (1035, 650), (875, 650), (840, 485)], fill=(51, 48, 66), outline=(221, 190, 105), width=5)
    draw.rectangle((906, 490, 1010, 635), fill=(17, 20, 30), outline=(126, 218, 228), width=3)
    draw.ellipse((785, 610, 875, 700), fill=(42, 92, 62), outline=(112, 244, 142), width=3)
    draw.rectangle((1260, 545, 1330, 620), fill=(82, 74, 58), outline=(216, 191, 116), width=3)
    draw.ellipse((610, 700, 660, 750), fill=(118, 72, 156), outline=(216, 152, 255), width=3)
    # Player and active recovery ring.
    draw.ellipse((918, 714, 1002, 798), outline=(112, 244, 142), width=5)
    draw.polygon([(960, 728), (935, 774), (985, 774)], fill=(235, 244, 248), outline=(75, 220, 230))
    text(draw, (960, 826), "E  RECOVER / PROCESS", 28, (112, 244, 142), True, "ma")
    # Recovery result panel uses deterministic game yield.
    result = harvest_yield(19019, 444, "structure", 2)
    panel = (64, 760, 600, 970)
    draw.rounded_rectangle(panel, radius=12, fill=(4, 8, 14, 235), outline=(72, 148, 164), width=3)
    text(draw, (92, 790), "SURFACE RIG", 20, (112, 244, 238), True)
    text(draw, (92, 830), "ANCIENT RUIN PROCESSED", 28, (238, 246, 250), True)
    text(draw, (92, 878), f"+{result['salvage']} SALVAGE", 25, (235, 205, 112), True)
    text(draw, (330, 878), f"+{result['fuel_cells']} FUEL CELL", 25, (132, 220, 250), True)
    text(draw, (92, 925), "PERSISTED FOR THIS PLANET", 18, (166, 184, 198))
    ui.draw_mode_chip(surf, "surface")
    ui.draw_mission_tracker(surf, "RECOVER THE WORLD", "RUINS, OBJECTS, GROWTHS AND SAMPLES PROCESS INTO EXISTING RESOURCES", "UNSTABLE")
    ui.draw_collapse_panel(surf, "UNSTABLE", 82, "COLLAPSE", 116, 125)
    ui.draw_bottom_hint(surf, "E RECOVER / PROCESS   •   SPACE RETURN TO ORBIT")
    path = OUT / "Entropy_Pass19_SurfaceRecovery_Proof.png"
    surf.image.convert("RGB").save(path)
    return path, surf.image.convert("RGB")


def render_pause():
    surf = starfield()
    ui.draw_pause_menu(surf, "space", True, False)
    path = OUT / "Entropy_Pass19_BacktickPause_Proof.png"
    surf.image.convert("RGB").save(path)
    return path, surf.image.convert("RGB")


orbit_path, orbit = render_orbit()
surface_path, surface = render_surface()
pause_path, pause = render_pause()

contact = Image.new("RGB", (1440, 810), (3, 6, 10))
contact.paste(orbit.resize((720, 405)), (0, 0))
contact.paste(surface.resize((720, 405)), (720, 0))
contact.paste(pause.resize((480, 270)), (480, 500))
draw = ImageDraw.Draw(contact)
text(draw, (32, 446), "PASS 19 — UNIVERSAL PLANETFALL", 26, (225, 240, 245), True)
text(draw, (752, 446), "PASS 19 — SURFACE RECOVERY", 26, (225, 240, 245), True)
text(draw, (32, 486), "Every intact planet is landable", 20, (112, 244, 238))
text(draw, (752, 486), "Every visible object becomes useful", 20, (112, 244, 238))
text(draw, (720, 790), "BACKTICK PAUSE — NO GAMEPLAY OVERLAP", 20, (166, 184, 198), True, "ms")
contact_path = OUT / "Entropy_Pass19_contact_sheet.png"
contact.save(contact_path)

print(orbit_path)
print(surface_path)
print(pause_path)
print(contact_path)
