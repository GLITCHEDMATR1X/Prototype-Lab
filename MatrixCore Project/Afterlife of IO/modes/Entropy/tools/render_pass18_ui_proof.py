from __future__ import annotations

import math
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
    def left(self, v): self.x = int(v)
    @property
    def top(self): return self.y
    @top.setter
    def top(self, v): self.y = int(v)
    @property
    def right(self): return self.x + self.w
    @right.setter
    def right(self, v): self.x = int(v) - self.w
    @property
    def bottom(self): return self.y + self.h
    @bottom.setter
    def bottom(self, v): self.y = int(v) - self.h
    @property
    def centerx(self): return self.x + self.w // 2
    @property
    def centery(self): return self.y + self.h // 2
    @property
    def center(self): return (self.centerx, self.centery)
    @property
    def topleft(self): return (self.x, self.y)
    def collidepoint(self, pos):
        return self.left <= pos[0] < self.right and self.top <= pos[1] < self.bottom


class Surface:
    def __init__(self, size, flags=0, image=None):
        self.image = image if image is not None else Image.new("RGBA", tuple(map(int, size)), (0, 0, 0, 0))
    def fill(self, color):
        rgba = tuple(color) if len(color) == 4 else tuple(color) + (255,)
        ImageDraw.Draw(self.image).rectangle((0, 0, self.image.width, self.image.height), fill=rgba)
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
        ImageDraw.Draw(img).text((2 - box[0], 2 - box[1]), text, font=self.font, fill=tuple(color) + ((255,) if len(color) == 3 else ()))
        return Surface((w, h), image=img)
    def size(self, text):
        box = self.font.getbbox(str(text))
        return (max(1, box[2] - box[0] + 4), max(1, box[3] - box[1] + 4))


class FontModule:
    @staticmethod
    def SysFont(name, size, bold=False): return FontWrap(size, bold)


class DrawModule:
    @staticmethod
    def rect(surface, color, rect, width=0, border_radius=0):
        draw = ImageDraw.Draw(surface.image)
        if not hasattr(rect, "left"):
            rect = Rect(*rect)
        box = (rect.left, rect.top, rect.right - 1, rect.bottom - 1)
        rgba = tuple(color) if len(color) == 4 else tuple(color) + (255,)
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
        box = (center[0]-radius, center[1]-radius, center[0]+radius, center[1]+radius)
        draw = ImageDraw.Draw(surface.image)
        if width: draw.ellipse(box, outline=rgba, width=width)
        else: draw.ellipse(box, fill=rgba)


pygame = types.ModuleType("pygame")
pygame.Surface = Surface
pygame.Rect = Rect
pygame.SRCALPHA = 1
pygame.font = FontModule()
pygame.draw = DrawModule()
sys.modules["pygame"] = pygame
sys.path.insert(0, str(ROOT))

import standard_ui as ui


def background():
    surf = Surface((1920, 1080))
    surf.fill((2, 4, 8, 255))
    draw = ImageDraw.Draw(surf.image)
    for i in range(190):
        x = (i * 137 + 71) % 1920
        y = (i * 83 + 29) % 1080
        b = 90 + (i * 17) % 150
        draw.point((x, y), fill=(b, b, min(255, b + 24), 255))
    draw.ellipse((735, 260, 1185, 710), fill=(35, 8, 8, 255), outline=(184, 58, 43, 255), width=5)
    draw.ellipse((820, 345, 1100, 625), fill=(8, 4, 6, 255), outline=(255, 119, 72, 255), width=3)
    return surf


critical = background()
ui.draw_collapse_pressure(critical, "CRITICAL", 0.72, 2.3)
ui.draw_mode_chip(critical, "space")
ui.draw_collapse_panel(critical, "CRITICAL", 24.0, "COLLAPSE", 76, 125)
ui.draw_mission_tracker(critical, "RETURN TO THE SHIP", "FRAGMENT IN HAND  •  DEPOSIT BEFORE WARP", "CRITICAL")
ui.draw_collapse_banner(critical, "COLLAPSE CRITICAL — RETURN TO ORBIT AND PREPARE TO WARP")
ui.draw_bottom_hint(critical, "V VIEW  •  TAB INTERIOR  •  C DAMPERS", "F WARP  1J / 18 FUEL  •  ` PAUSE")
critical_path = OUT / "Entropy_Pass18_CollapseCritical_Proof.png"
critical.image.convert("RGB").save(critical_path)

failure = background()
ui.draw_failure_screen(failure, "EVENT HORIZON CONSUMED THE SHIP", 4, 3, 125)
failure_path = OUT / "Entropy_Pass18_FailureRecovery_Proof.png"
failure.image.convert("RGB").save(failure_path)

contact = Image.new("RGB", (960, 540), (0, 0, 0))
a = critical.image.convert("RGB").resize((480, 270))
b = failure.image.convert("RGB").resize((480, 270))
contact.paste(a, (0, 0))
contact.paste(b, (480, 0))
d = ImageDraw.Draw(contact)
font = ImageFont.truetype(_font_path(True), 22) if _font_path(True) else ImageFont.load_default()
d.text((24, 300), "PASS 18 — COLLAPSE PRESSURE", font=font, fill=(225, 240, 245))
d.text((504, 300), "PASS 18 — FAILURE / RETRY", font=font, fill=(225, 240, 245))
d.text((24, 350), "Shared timer + hull instrument", font=font, fill=(112, 244, 238))
d.text((504, 350), "Current-system checkpoint recovery", font=font, fill=(112, 244, 238))
contact_path = OUT / "Entropy_Pass18_contact_sheet.png"
contact.save(contact_path)

print(critical_path)
print(failure_path)
print(contact_path)
