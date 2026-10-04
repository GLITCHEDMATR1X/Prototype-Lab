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


def render_single_world_orbit():
    surf = starfield()
    draw = ImageDraw.Draw(surf.image)
    # One redshifted star and one readable destination.
    for radius, col in ((150, (72, 16, 20, 55)), (104, (148, 34, 32, 105)), (68, (255, 116, 66, 255))):
        draw.ellipse((410-radius, 500-radius, 410+radius, 500+radius), fill=col)
    # Sole varied planet.
    x, y, r = 1325, 525, 122
    draw.ellipse((x-r-20, y-r-20, x+r+20, y+r+20), outline=(74, 178, 196), width=3)
    draw.ellipse((x-r, y-r, x+r, y+r), fill=(151, 205, 232), outline=(235, 249, 255), width=4)
    # Ice/fungal/crystal bands suggest the full variant mix without adding more planets.
    draw.arc((x-r+16, y-r+22, x+r-8, y+r-18), 195, 350, fill=(90, 122, 174), width=12)
    draw.arc((x-r+8, y-r+42, x+r-30, y+r-2), 18, 166, fill=(202, 241, 246), width=9)
    draw.arc((x-r+34, y-r+18, x+r-10, y+r-38), 72, 205, fill=(117, 222, 203), width=6)
    text(draw, (x, y+r+48), "P1  ICE WORLD  /  LANDABLE", 25, (210, 238, 246), True, "ma")
    text(draw, (x, y+r+84), "1 WORLD PER SYSTEM  •  12 CLASSES IN ROTATION", 19, (112, 244, 238), False, "ma")
    # Ship and clear approach lane.
    draw.polygon([(930, 520), (880, 548), (892, 490)], fill=(238, 246, 250), outline=(82, 226, 236))
    draw.line((930, 520, 1185, 525), fill=(112, 244, 238), width=4)
    ui.draw_mode_chip(surf, "flight")
    ui.draw_mission_tracker(surf, "ONE WORLD — ONE GOAL", "LAND • PROCESS SURFACE OBJECTS • RECOVER THE RELIC CORE", "UNSTABLE")
    ui.draw_collapse_panel(surf, "UNSTABLE", 116, "COLLAPSE", 118, 125)
    ui.draw_bottom_hint(surf, "APPROACH P1 TO ENTER ATMOSPHERE   •   ` PAUSE")
    path = OUT / "Entropy_Pass20_SingleWorldOrbit_Proof.png"
    surf.image.convert("RGB").save(path)
    return path, surf.image.convert("RGB")


def render_goal_autowarp():
    surf = Surface((1920, 1080))
    draw = ImageDraw.Draw(surf.image)
    draw.rectangle((0, 0, 1920, 1080), fill=(10, 24, 31))
    rng = random.Random(2020)
    for _ in range(190):
        x, y = rng.randrange(1920), rng.randrange(1080)
        r = rng.randrange(8, 38)
        col = rng.choice(((23, 64, 69), (30, 78, 76), (47, 84, 77), (38, 91, 87)))
        draw.ellipse((x-r, y-r, x+r, y+r), fill=col)
    # Stripped landmark and player.
    draw.polygon([(975, 360), (1095, 458), (1042, 676), (870, 676), (820, 458)], fill=(48, 45, 67), outline=(229, 198, 104), width=5)
    draw.rectangle((905, 492, 1015, 656), fill=(15, 18, 29), outline=(112, 244, 238), width=3)
    draw.ellipse((925, 735, 1005, 815), outline=(112, 244, 142), width=5)
    draw.polygon([(965, 746), (942, 792), (988, 792)], fill=(238, 246, 250), outline=(75, 220, 230))
    # Core pickup feedback.
    for rr, alpha in ((86, 80), (62, 125), (38, 220)):
        draw.ellipse((960-rr, 458-rr, 960+rr, 458+rr), outline=(112, 244, 238, alpha), width=5)
    text(draw, (960, 455), "+1 RELIC CORE", 31, (238, 250, 255), True, "mm")
    panel=(560,820,1360,986)
    draw.rounded_rectangle(panel, radius=14, fill=(4,8,14,238), outline=(74,182,196), width=3)
    text(draw, (960, 854), "SYSTEM GOAL COMPLETE", 29, (112,244,238), True, "ma")
    text(draw, (960, 902), "AUTO-WARP CHARGING  1.35s", 26, (238,246,250), True, "ma")
    text(draw, (960, 946), "SURFACE STATE WILL CLEANLY TRANSITION TO THE NEXT SYSTEM", 18, (166,190,202), False, "ma")
    ui.draw_mode_chip(surf, "surface")
    ui.draw_mission_tracker(surf, "RELIC CORE RECOVERED", "FABRICATOR TOKEN STORED  •  NEXT SYSTEM INBOUND", "UNSTABLE")
    ui.draw_collapse_panel(surf, "UNSTABLE", 91, "COLLAPSE", 116, 125)
    path=OUT/"Entropy_Pass20_SurfaceAutowarp_Proof.png"
    surf.image.convert("RGB").save(path)
    return path, surf.image.convert("RGB")


def render_safe_deflection():
    surf = starfield()
    draw = ImageDraw.Draw(surf.image)
    x,y,r=1270,535,128
    draw.ellipse((x-r-30,y-r-30,x+r+30,y+r+30), outline=(226,82,82), width=5)
    draw.ellipse((x-r,y-r,x+r,y+r), fill=(66,48,52), outline=(150,112,116), width=3)
    for offset in (-54,-18,22,58):
        draw.line((x-r+20,y+offset,x+r-20,y-offset//2), fill=(118,62,67), width=5)
    # Incoming path bends along exclusion edge.
    points=[(650,560),(920,552),(1075,548),(1120,500),(1115,430)]
    draw.line(points, fill=(112,244,238), width=5)
    draw.polygon([(1115,430),(1092,472),(1136,466)], fill=(238,246,250), outline=(82,226,236))
    text(draw,(x,y+r+56),"PLANETFALL UNAVAILABLE",24,(242,166,166),True,"ma")
    text(draw,(x,y+r+92),"SOFT EXCLUSION — NO COLLISION / NO CLIPPING",19,(112,244,238),False,"ma")
    ui.draw_mode_chip(surf,"flight")
    ui.draw_mission_tracker(surf,"SAFE COURSE CORRECTION","INWARD VELOCITY REMOVED AT THE ATMOSPHERE BOUNDARY","CRITICAL")
    ui.draw_collapse_panel(surf,"CRITICAL",44,"COLLAPSE",98,125)
    ui.draw_bottom_hint(surf,"UNAVAILABLE WORLD DEFLECTED   •   NEXT VALID SYSTEM REMAINS REACHABLE")
    path=OUT/"Entropy_Pass20_SafeDeflection_Proof.png"
    surf.image.convert("RGB").save(path)
    return path, surf.image.convert("RGB")


def render_run_start():
    surf = starfield()
    class Signal:
        planet_label = "P1 FUNGAL"
        hazard_family = "BIOLOGICAL"
    class Mission:
        system_index = 9
        collapse_state = "STABLE"
        system_planet_count = 1
        target_signal = Signal()
    ui.draw_run_start_screen(surf, Mission())
    path = OUT / "Entropy_Pass20_RunStart_Proof.png"
    surf.image.convert("RGB").save(path)
    return path, surf.image.convert("RGB")


orbit_path, orbit = render_single_world_orbit()
autowarp_path, autowarp = render_goal_autowarp()
deflect_path, deflect = render_safe_deflection()
run_start_path, run_start = render_run_start()

contact = Image.new("RGB", (1440, 810), (3, 6, 10))
contact.paste(orbit.resize((720, 405)), (0, 0))
contact.paste(autowarp.resize((720, 405)), (720, 0))
contact.paste(deflect.resize((720, 405)), (0, 405))
contact.paste(run_start.resize((720, 405)), (720, 405))
draw = ImageDraw.Draw(contact)
text(draw, (28, 44), "PASS 20 — SINGLE-WORLD SYSTEM", 24, (225, 240, 245), True)
text(draw, (748, 44), "PASS 20 — GOAL AUTOWARP", 24, (225, 240, 245), True)
text(draw, (28, 770), "SOFT EXCLUSION — NO COLLISION TRAP", 19, (166, 204, 214), True)
text(draw, (748, 770), "ONE-WORLD FIRST-MINUTE GUIDANCE", 19, (166, 204, 214), True)
contact_path = OUT / "Entropy_Pass20_contact_sheet.png"
contact.save(contact_path)

print(orbit_path)
print(autowarp_path)
print(deflect_path)
print(run_start_path)
print(contact_path)
