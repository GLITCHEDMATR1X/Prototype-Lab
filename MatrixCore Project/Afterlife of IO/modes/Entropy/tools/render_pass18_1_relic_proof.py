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



import interiors
from mission_state import MissionState, PlanetMissionSignal
from ship_progression import ensure_progression


def background():
    surf = Surface((1920, 1080))
    surf.fill((2, 5, 10, 255))
    draw = ImageDraw.Draw(surf.image)
    for i in range(220):
        x = (i * 137 + 71) % 1920
        y = (i * 83 + 29) % 1080
        b = 80 + (i * 17) % 150
        draw.point((x, y), fill=(b, b, min(255, b + 30), 255))
    # Top-down relic landmark vignette behind the UI.
    draw.ellipse((760, 310, 1160, 710), fill=(14, 21, 29, 255), outline=(94, 226, 224, 255), width=4)
    draw.polygon([(960, 370), (1050, 520), (960, 655), (870, 520)], fill=(54, 31, 64, 255), outline=(255, 215, 102, 255))
    draw.ellipse((900, 460, 1020, 580), outline=(255, 205, 78, 255), width=5)
    return surf


mission = MissionState(
    run_started=True, system_index=4, system_seed=18181, system_planet_count=5,
    target_planet_index=1, target_style='roseglass', target_hazard_family='ANOMALOUS',
    current_planet_index=1, target_structure_seed=444, target_structure_title='Relic Labyrinth',
    surface_target_distance=12.0,
)
mission.signals = {
    0: PlanetMissionSignal(0, 'fuel', 'ice', 'COLD'),
    1: PlanetMissionSignal(1, 'fragment', 'roseglass', 'ANOMALOUS'),
    2: PlanetMissionSignal(2, 'salvage', 'rust', 'HEAT'),
    3: PlanetMissionSignal(3, 'survey', 'jungle', 'BIOLOGICAL'),
    4: PlanetMissionSignal(4, 'survey', 'storm', 'COLD'),
}

brief = background()
ui.draw_mode_chip(brief, 'surface')
ui.draw_collapse_panel(brief, 'UNSTABLE', 81.0, 'COLLAPSE', 118, 125)
ui.draw_mission_tracker(brief, mission.objective_title('surface'), mission.objective_detail('surface'), 'UNSTABLE')
ui.draw_mission_brief(brief, mission, 'surface', mission.surface_target_distance)
brief_path = OUT / 'Entropy_Pass18_1_RelicMission_Proof.png'
brief.image.convert('RGB').save(brief_path)

class DummyShip:
    def __init__(self):
        self.cargo = {'relic_cores': 2, 'salvage': 6, 'fuel_cells': 3}
        self.upgrade_levels = {'warp': 1, 'scanner': 0, 'hull': 1, 'surface': 0}
        self.hull_hp_max = 125
        self.hull_hp = 108
        self.fuel = 72
        self.state_dirty = False

fabricator = background()
ship = DummyShip(); ensure_progression(ship)
view = interiors.InteriorView.__new__(interiors.InteriorView)
view.screen = fabricator
view.ship = ship
view.upgrade_menu_open = True
view.upgrade_selection = 1
view._draw_upgrade_menu()
fab_path = OUT / 'Entropy_Pass18_1_RelicFabricator_Proof.png'
fabricator.image.convert('RGB').save(fab_path)

contact = Image.new('RGB', (960, 540), (0, 0, 0))
contact.paste(brief.image.convert('RGB').resize((480, 270)), (0, 0))
contact.paste(fabricator.image.convert('RGB').resize((480, 270)), (480, 0))
d = ImageDraw.Draw(contact)
font = ImageFont.truetype(_font_path(True), 21) if _font_path(True) else ImageFont.load_default()
d.text((24, 302), 'PASS 18.1 — SURFACE RELIC', font=font, fill=(225, 240, 245))
d.text((504, 302), 'PASS 18.1 — CORE FABRICATION', font=font, fill=(225, 240, 245))
d.text((24, 350), 'No first-person transition', font=font, fill=(112, 244, 238))
d.text((504, 350), '1 core or salvage fallback', font=font, fill=(112, 244, 238))
contact_path = OUT / 'Entropy_Pass18_1_contact_sheet.png'
contact.save(contact_path)

print(brief_path)
print(fab_path)
print(contact_path)
