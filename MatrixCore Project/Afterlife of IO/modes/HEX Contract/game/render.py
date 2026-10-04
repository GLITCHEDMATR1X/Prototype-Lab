from __future__ import annotations

import math
import pygame

from .data import HEROES, QUESTS, HERO_ORDERS, CONTRACT_COMPLICATIONS, EQUIPMENT_KITS, QUEST_INTEL, ENEMY_ARCHETYPES, ENEMY_VARIANTS, MISSION_ENVIRONMENTS, CIVILIAN_ROLES, SIGNATURE_BOSSES, HERO_LINKS, STORY_CHAIN, SOVEREIGN_AFTERMATHS, BOND_EVENTS, quest_fit, equipment_fit, recovery_quote, recovery_state
from .sim import Mission, WORLD
from .actors import ActorArtist
from .world import WorldTextureLibrary, WorldObstacle
from .platform_input import INPUT_XBOX, prompt_for

Vec2 = pygame.Vector2

VIRTUAL_SIZE = (1920, 1080)
# Afterlife of IO hosts HEX Contract in-process; there, quitting returns to
# the Afterlife title, so the host relabels the title-screen exit.
QUIT_LABEL = "QUIT"


class Fonts:
    def __init__(self, scale: float = 1.0):
        preferred = pygame.font.match_font("dejavusans")
        bold = pygame.font.match_font("dejavusans", bold=True)
        size = lambda value: max(12, int(round(value * scale)))
        self.xs = pygame.font.Font(preferred, size(18))
        self.sm = pygame.font.Font(preferred, size(23))
        self.md = pygame.font.Font(preferred, size(30))
        self.lg = pygame.font.Font(bold, size(42))
        self.xl = pygame.font.Font(bold, size(64))
        self.hero = pygame.font.Font(bold, size(35))


class Renderer:
    def __init__(self, canvas: pygame.Surface):
        self.canvas = canvas
        self.fonts = Fonts()
        self.glow = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA)
        self.fx = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA)
        self.time = 0.0
        self.actors = ActorArtist()
        self.world_textures = WorldTextureLibrary()
        self._atmosphere_halo_cache: dict[tuple[int, int, int], pygame.Surface] = {}
        self.high_contrast = False
        self.reduced_motion = False
        self.text_scale = "standard"

    def apply_settings(self, settings: dict):
        self.high_contrast = bool(settings.get("high_contrast", False))
        self.reduced_motion = bool(settings.get("reduced_motion", False))
        requested = "large" if settings.get("text_scale") == "large" else "standard"
        if requested != self.text_scale:
            self.text_scale = requested
            self.fonts = Fonts(1.08 if requested == "large" else 1.0)

    @staticmethod
    def _lift_color(color, amount: int):
        return tuple(max(0, min(255, int(c) + amount)) for c in color[:3])

    def _visual_env(self, mission: Mission) -> dict:
        """Presentation-only lift for world readability; gameplay data stays untouched."""
        env = dict(mission.environment)
        # GPTOOL review of the previous geometry proof found the battlefield too
        # dark/flat for dependable cover review.  Lift only rendered world values.
        # Pass 21 keeps the floor readable while deliberately quieting the
        # universal grid.  Important structures now earn the strongest edges
        # locally instead of every block competing at the same brightness.
        lifts = {
            "purge": {"floor": 22, "grid": -3, "wall": 24, "edge": 14, "fog": 14},
            "recovery": {"floor": 24, "grid": -4, "wall": 26, "edge": 16, "fog": 15},
            "rescue": {"floor": 22, "grid": -4, "wall": 24, "edge": 14, "fog": 15},
        }[mission.quest_key]
        for key, amount in lifts.items():
            env[key] = self._lift_color(env[key], amount)
        return env

    def text(self, surf, text, pos, font, color=(230, 238, 255), anchor="topleft"):
        img = font.render(str(text), True, color)
        rect = img.get_rect()
        setattr(rect, anchor, (int(pos[0]), int(pos[1])))
        surf.blit(img, rect)
        return rect

    def wrap_text(self, surf, text, rect, font, color=(230, 238, 255), line_gap=5, max_lines=3):
        words = str(text).split()
        lines, current = [], ""
        for word in words:
            test = word if not current else current + " " + word
            if font.size(test)[0] <= rect.width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        for i, line in enumerate(lines[:max_lines]):
            self.text(surf, line, (rect.left, rect.top + i * (font.get_linesize() + line_gap)), font, color)
        return len(lines)

    def panel(self, rect: pygame.Rect, fill=(8, 14, 28, 225), edge=(66, 120, 170), radius=12):
        pygame.draw.rect(self.canvas, fill, rect, border_radius=radius)
        pygame.draw.rect(self.canvas, edge, rect, 2, border_radius=radius)
        pygame.draw.line(self.canvas, (*edge[:3],), (rect.left + 18, rect.top + 5), (rect.right - 18, rect.top + 5), 2)

    def bar(self, rect, ratio, color, back=(22, 30, 45), edge=(80, 100, 125)):
        ratio = max(0.0, min(1.0, ratio))
        pygame.draw.rect(self.canvas, back, rect, border_radius=5)
        if ratio > 0:
            fill = rect.copy(); fill.width = max(1, int(rect.width * ratio))
            pygame.draw.rect(self.canvas, color, fill, border_radius=5)
        pygame.draw.rect(self.canvas, edge, rect, 2, border_radius=5)

    def _background(self, accent=(50, 130, 180)):
        self.canvas.fill((1, 2, 7) if self.high_contrast else (4, 6, 15))
        for y in range(0, 1080, 24):
            shade = (12 if self.high_contrast else 7) + int((10 if self.high_contrast else 7) * y / 1080)
            pygame.draw.line(self.canvas, (shade, shade + 3, shade + 10), (0, y), (1920, y))
        for x in range(-300, 2200, 120):
            line = (22, 37, 58) if self.high_contrast else (9, 17, 29)
            pygame.draw.line(self.canvas, line, (x, 0), (x + 500, 1080), 1)
        halo = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA)
        pygame.draw.circle(halo, (*accent, 34 if self.high_contrast else 20), (1650, 90), 460)
        self.canvas.blit(halo, (0, 0))

    def draw_platform_prompt(self, input_mode: str, state: str, *, controller_connected: bool, notice: str = "", mission: Mission | None = None, paused: bool = False):
        mission_active = bool(mission and mission.status == "ACTIVE")
        mission_finished = bool(mission and mission.status != "ACTIVE")
        if input_mode != INPUT_XBOX and not notice:
            return
        if state == "MISSION" and mission_active and not paused and not notice:
            return
        prompt = prompt_for(state, mission_active=mission_active, mission_finished=mission_finished, paused=paused)
        if state == "MISSION" and notice:
            rect = pygame.Rect(610, 82, 700, 58)
            pygame.draw.rect(self.canvas, (7, 13, 25), rect, border_radius=10)
            pygame.draw.rect(self.canvas, (92, 226, 255), rect, 2, border_radius=10)
            self.text(self.canvas, notice, rect.center, self.fonts.xs, (232, 246, 255), "center")
            return
        bar = pygame.Rect(0, 1018, VIRTUAL_SIZE[0], 62)
        pygame.draw.rect(self.canvas, (4, 9, 18), bar)
        pygame.draw.line(self.canvas, (48, 92, 128), (0, bar.top), (VIRTUAL_SIZE[0], bar.top), 2)
        status = "Xbox Controller" if controller_connected else "KEYBOARD / MOUSE"
        self.text(self.canvas, status, (34, 1034), self.fonts.xs, (92, 226, 255))
        self.text(self.canvas, prompt.primary, (960, 1030), self.fonts.xs, (232, 244, 255), "midtop")
        if prompt.secondary:
            self.text(self.canvas, prompt.secondary, (1888, 1055), self.fonts.xs, (145, 174, 205), "bottomright")
        if notice:
            self.text(self.canvas, notice, (1888, 1030), self.fonts.xs, (255, 218, 112), "topright")

    def draw_title_screen(self, profile: dict, has_progress: bool, recovery_note: str = "", new_guild_confirm: bool = False, selected_index: int = 0):
        self._background((84, 61, 160))
        # Guild seal / three sovereign geometry.
        center = (960, 310)
        pygame.draw.circle(self.canvas, (10, 16, 30), center, 176)
        pygame.draw.circle(self.canvas, (92, 226, 255), center, 176, 3)
        pygame.draw.circle(self.canvas, (182, 96, 255), center, 132, 2)
        for angle, color in zip((-90, 30, 150), ((255, 82, 126), (184, 94, 255), (84, 245, 210))):
            a = math.radians(angle)
            tip = (center[0] + math.cos(a) * 142, center[1] + math.sin(a) * 142)
            left = (center[0] + math.cos(a + 2.42) * 66, center[1] + math.sin(a + 2.42) * 66)
            right = (center[0] + math.cos(a - 2.42) * 66, center[1] + math.sin(a - 2.42) * 66)
            pygame.draw.polygon(self.canvas, color, (tip, left, right), 3)
        pygame.draw.circle(self.canvas, (236, 248, 255), center, 20, 3)
        self.text(self.canvas, "HEX CONTRACT", (960, 92), self.fonts.xl, (234, 248, 255), "midtop")
        self.text(self.canvas, "FINALIZATION RC1 / AUTONOMOUS HERO GUILD", (960, 164), self.fonts.sm, (92, 226, 255), "midtop")
        self.text(self.canvas, "NO HERO IS DISPOSABLE. EVERY CONTRACT MAY PROVE OTHERWISE.", (960, 202), self.fonts.xs, (174, 194, 222), "midtop")
        self.text(self.canvas, "NIGHT OF THREE SOVEREIGNS", (960, 296), self.fonts.xs, (255, 218, 108), "center")

        guild = profile.get("guild", {})
        campaign = profile.get("campaign", {})
        active = sum(1 for record in profile.get("heroes", {}).values() if record.get("availability", "ACTIVE") == "ACTIVE")
        summary = pygame.Rect(120, 500, 470, 335)
        self.panel(summary, fill=(6, 11, 23, 244), edge=(72, 118, 162), radius=15)
        self.text(self.canvas, "GUILD RECORD", (150, 530), self.fonts.sm, (92, 226, 255))
        rows = [
            ("ROSTER", f"{active}/{len(HEROES)} ACTIVE"),
            ("TREASURY", f"{int(guild.get('credits', 0)):,} CR"),
            ("RENOWN", f"{int(guild.get('renown', 0)):02d}"),
            ("CONTRACTS", f"{int(guild.get('contracts', 0)):03d}"),
            ("GUILD CYCLE", f"{int(guild.get('cycles', 1)):02d}"),
            ("CHAIN CLEARS", f"{int(campaign.get('chain_completions', 0)):02d}"),
        ]
        for i, (label, value) in enumerate(rows):
            y = 584 + i * 38
            self.text(self.canvas, label, (150, y), self.fonts.xs, (136, 158, 188))
            self.text(self.canvas, value, (555, y), self.fonts.xs, (236, 243, 252), "topright")

        buttons = [
            (pygame.Rect(705, 520, 510, 72), "CONTINUE GUILD" if has_progress else "BEGIN GUILD", (92, 226, 255)),
            (pygame.Rect(705, 610, 510, 64), "SETTINGS", (184, 94, 255)),
            (pygame.Rect(705, 690, 510, 64), "FIELD GUIDE", (84, 245, 210)),
            (pygame.Rect(705, 770, 510, 64), QUIT_LABEL, (255, 105, 126)),
        ]
        for i, (rect, label, color) in enumerate(buttons):
            active = i == selected_index
            pygame.draw.rect(self.canvas, (10, 20, 36) if active else (8, 15, 29), rect, border_radius=12)
            pygame.draw.rect(self.canvas, (238, 248, 255) if active else color, rect, 4 if active else 2, border_radius=12)
            self.text(self.canvas, ("› " if active else "") + label, rect.center, self.fonts.sm, (238, 248, 255) if active else color, "center")

        chapter_key = STORY_CHAIN["order"][int(campaign.get("chain_step", 0)) % len(STORY_CHAIN["order"])]
        chapter = STORY_CHAIN["chapters"][chapter_key]
        right = pygame.Rect(1330, 500, 470, 335)
        self.panel(right, fill=(6, 11, 23, 244), edge=QUESTS[chapter_key]["color"], radius=15)
        self.text(self.canvas, "CURRENT OPERATION", (1360, 530), self.fonts.sm, QUESTS[chapter_key]["color"])
        self.text(self.canvas, chapter["name"], (1360, 580), self.fonts.md, (239, 246, 255))
        self.wrap_text(self.canvas, chapter["brief"], pygame.Rect(1360, 628, 400, 92), self.fonts.xs, (189, 207, 230), max_lines=4)
        self.text(self.canvas, "N  NEW GUILD (PRESS TWICE)", (1360, 772), self.fonts.xs, (140, 160, 188))
        self.text(self.canvas, "F11  BORDERLESS / WINDOWED", (1360, 800), self.fonts.xs, (140, 160, 188))
        if new_guild_confirm:
            warning = pygame.Rect(555, 870, 810, 64)
            pygame.draw.rect(self.canvas, (28, 8, 16), warning, border_radius=10)
            pygame.draw.rect(self.canvas, (255, 88, 116), warning, 2, border_radius=10)
            self.text(self.canvas, "PRESS N AGAIN TO ERASE CURRENT ROSTER PROGRESS", warning.center, self.fonts.sm, (255, 158, 174), "center")
        elif recovery_note:
            note = pygame.Rect(555, 870, 810, 64)
            pygame.draw.rect(self.canvas, (8, 21, 24), note, border_radius=10)
            pygame.draw.rect(self.canvas, (84, 245, 210), note, 2, border_radius=10)
            self.text(self.canvas, recovery_note, note.center, self.fonts.xs, (160, 255, 228), "center")
        self.text(self.canvas, f"ENTER CONTINUE   •   S SETTINGS   •   H GUIDE   •   N NEW GUILD   •   ESC {QUIT_LABEL}", (960, 1034), self.fonts.xs, (126, 148, 180), "midbottom")

    def draw_settings(self, settings: dict, selected_index: int = 0):
        self._background((72, 105, 160))
        self.draw_title_bar("FINALIZATION / SETTINGS")
        self.text(self.canvas, "Changes save immediately and apply to every guild screen.", (960, 150), self.fonts.sm, (205, 220, 239), "midtop")
        labels = [
            ("MASTER VOLUME", "master_volume", "Overall game output"),
            ("SFX VOLUME", "sfx_volume", "Combat, interface, objectives, cover, and sovereign cues"),
            ("AMBIENCE VOLUME", "ambience_volume", "Contract-specific environmental beds and guild room"),
            ("MUSIC VOLUME", "music_volume", "Independent looping-score level; 100% is full music output"),
            ("REDUCED MOTION", "reduced_motion", "Freezes nonessential atmospheric drift"),
            ("HIGH CONTRAST", "high_contrast", "Strengthens lines, panels, and background separation"),
            ("CONTEXTUAL TIPS", "tutorial_tips", "Shows short first-contract guidance in context"),
            ("TEXT SIZE", "text_scale", "Applies a modest increase to important interface text"),
        ]
        for i, (label, key, desc) in enumerate(labels):
            rect = pygame.Rect(490, 246 + i * 75, 940, 56)
            active = i == selected_index
            edge = (92, 226, 255) if active else (56, 82, 112)
            pygame.draw.rect(self.canvas, (9, 15, 29), rect, border_radius=10)
            pygame.draw.rect(self.canvas, edge, rect, 3 if active else 1, border_radius=10)
            self.text(self.canvas, label, (rect.left + 22, rect.top + 11), self.fonts.sm, (236, 244, 255) if active else (190, 205, 225))
            self.text(self.canvas, desc, (rect.left + 300, rect.top + 15), self.fonts.xs, (135, 158, 187))
            value = settings.get(key)
            if key.endswith("volume"):
                display = f"{int(round(float(value) * 100)):03d}%"
                minus = pygame.Rect(1530, rect.top + 10, 52, 36)
                plus = pygame.Rect(1748, rect.top + 10, 52, 36)
                pygame.draw.rect(self.canvas, (12, 22, 38), minus, border_radius=7)
                pygame.draw.rect(self.canvas, (12, 22, 38), plus, border_radius=7)
                pygame.draw.rect(self.canvas, edge, minus, 2, border_radius=7)
                pygame.draw.rect(self.canvas, edge, plus, 2, border_radius=7)
                self.text(self.canvas, "−", minus.center, self.fonts.sm, edge, "center")
                self.text(self.canvas, "+", plus.center, self.fonts.sm, edge, "center")
                self.text(self.canvas, display, (1664, rect.centery), self.fonts.sm, edge if active else (180, 198, 220), "center")
            elif key == "text_scale":
                display = str(value).upper()
                self.text(self.canvas, display, (rect.right - 22, rect.centery), self.fonts.sm, edge if active else (180, 198, 220), "midright")
            else:
                display = "ON" if value else "OFF"
                self.text(self.canvas, display, (rect.right - 22, rect.centery), self.fonts.sm, edge if active else (180, 198, 220), "midright")
        back = pygame.Rect(760, 910, 400, 62)
        pygame.draw.rect(self.canvas, (8, 15, 29), back, border_radius=10)
        pygame.draw.rect(self.canvas, (84, 245, 210), back, 2, border_radius=10)
        self.text(self.canvas, "RETURN", back.center, self.fonts.sm, (84, 245, 210), "center")
        self.text(self.canvas, "↑/↓ SELECT   •   ←/→ OR −/+ CHANGE   •   ENTER TOGGLE   •   ESC RETURN", (960, 1035), self.fonts.xs, (132, 154, 183), "midbottom")

    def draw_title_bar(self, subtitle: str):
        pygame.draw.rect(self.canvas, (5, 9, 20), (0, 0, 1920, 118))
        pygame.draw.line(self.canvas, (70, 210, 245), (0, 117), (1920, 117), 2)
        self.text(self.canvas, "HEX CONTRACT", (52, 28), self.fonts.xl, (224, 244, 255))
        self.text(self.canvas, "AUTONOMOUS HERO GUILD", (54, 108), self.fonts.xs, (72, 220, 255), "bottomleft")
        self.text(self.canvas, subtitle, (1860, 70), self.fonts.md, (170, 180, 210), "midright")

    def draw_contract_board(self, selected: str | None = None, profile: dict | None = None):
        profile = profile or {"guild": {}}
        self._background((65, 90, 160))
        self.draw_title_bar("CONTRACT BOARD / SELECT A QUEST")
        guild = profile.get("guild", {})
        campaign = profile.get("campaign", {})
        chain_step = int(campaign.get("chain_step", 0)) % len(STORY_CHAIN["order"])
        chain_target = STORY_CHAIN["order"][chain_step]
        chain_chapter = STORY_CHAIN["chapters"][chain_target]
        self.text(self.canvas, f"TREASURY {int(guild.get('credits', 0)):,} CR   •   RENOWN {int(guild.get('renown', 0)):02d}", (1860, 108), self.fonts.xs, (255, 218, 108), "bottomright")
        active_count = sum(1 for r in profile.get("heroes", {}).values() if r.get("availability", "ACTIVE") == "ACTIVE")
        self.text(self.canvas, f"ROSTER {active_count}/{len(HEROES)}   •   CYCLE {int(guild.get('cycles', 1)):02d}", (60, 155), self.fonts.xs, (110, 238, 205))
        self.text(self.canvas, "Choose the danger. The hero chooses how to survive it.", (960, 155), self.fonts.md, (190, 205, 230), "midtop")
        onboarding = profile.get("onboarding", {})
        if profile.get("settings", {}).get("tutorial_tips", True) and not onboarding.get("completed", False):
            self.text(self.canvas, "FIRST CONTRACT / STEP 1 OF 3 / SELECT THE HIGHLIGHTED ASH TESTAMENT", (960, 193), self.fonts.xs, (255, 218, 108), "midtop")
        else:
            self.text(self.canvas, "THE GUILD SELLS SURVIVAL WHERE NORMAL MERCENARIES STOP ANSWERING", (960, 193), self.fonts.xs, (105, 226, 244), "midtop")
        keys = list(QUESTS)
        for i, key in enumerate(keys):
            q = QUESTS[key]
            rect = pygame.Rect(85 + i * 610, 230, 535, 675)
            active = selected == key
            edge = q["color"] if active else (58, 84, 118)
            fill = (13, 19, 35) if not active else (18, 25, 44)
            pygame.draw.rect(self.canvas, fill, rect, border_radius=16)
            pygame.draw.rect(self.canvas, edge, rect, 4 if active else 2, border_radius=16)
            pygame.draw.rect(self.canvas, q["color"], (rect.left, rect.top, rect.width, 10), border_radius=8)
            self.text(self.canvas, q["type"], (rect.left + 30, rect.top + 34), self.fonts.sm, q["color"])
            self.text(self.canvas, q["name"], (rect.left + 30, rect.top + 82), self.fonts.hero, (238, 244, 255))
            self.text(self.canvas, f"DANGER / {q['danger']}", (rect.left + 30, rect.top + 136), self.fonts.sm, (255, 170, 118))
            env = MISSION_ENVIRONMENTS[key]
            center = Vec2(rect.centerx, rect.top + 252)
            pygame.draw.rect(self.canvas, env["floor"], pygame.Rect(rect.left+50, rect.top+178, rect.width-100, 146), border_radius=12)
            pygame.draw.rect(self.canvas, env["edge"], pygame.Rect(rect.left+50, rect.top+178, rect.width-100, 146), 2, border_radius=12)
            if key == "purge":
                pygame.draw.polygon(self.canvas, env["wall"], [(center.x-105,center.y+55),(center.x-70,center.y-35),(center.x-28,center.y+55)])
                pygame.draw.polygon(self.canvas, env["wall"], [(center.x+28,center.y+55),(center.x+70,center.y-35),(center.x+105,center.y+55)])
                pygame.draw.circle(self.canvas, env["secondary"], center, 28, 3)
            elif key == "recovery":
                for dx in (-90,-45,0,45,90):
                    pygame.draw.polygon(self.canvas, env["accent"], [(center.x+dx,center.y-45),(center.x+dx+18,center.y),(center.x+dx,center.y+45),(center.x+dx-18,center.y)], 2)
            else:
                pygame.draw.line(self.canvas, env["accent"], (center.x-120,center.y+35),(center.x+120,center.y+35), 4)
                for dx in (-80,0,80):
                    pygame.draw.rect(self.canvas, env["wall"], pygame.Rect(int(center.x+dx-28),int(center.y-38),56,72), border_radius=7)
                    pygame.draw.circle(self.canvas, env["secondary"], (int(center.x+dx),int(center.y-8)), 8, 2)
            self.text(self.canvas, env["site"], (center.x, rect.top+309), self.fonts.xs, env["accent"], "midbottom")
            self.wrap_text(self.canvas, q["brief"], pygame.Rect(rect.left + 30, rect.top + 350, rect.width - 60, 72), self.fonts.xs, (190, 205, 225), max_lines=3)
            self.text(self.canvas, "KNOWN THREATS", (rect.left + 30, rect.top + 430), self.fonts.sm, q["color"])
            for j, item in enumerate(q["threats"]):
                self.text(self.canvas, "◆ " + item, (rect.left + 42, rect.top + 470 + j * 34), self.fonts.xs, (208, 218, 236))
            self.text(self.canvas, q["reward"], (rect.left + 30, rect.bottom - 112), self.fonts.xs, (255, 220, 105))
            if key == chain_target:
                badge = pygame.Rect(rect.left + 30, rect.bottom - 82, rect.width - 60, 34)
                pygame.draw.rect(self.canvas, (7, 13, 24), badge, border_radius=7)
                pygame.draw.rect(self.canvas, q["color"], badge, 2, border_radius=7)
                self.text(self.canvas, f"CHAIN TARGET / {chain_chapter['name']}", badge.center, self.fonts.xs, q["color"], "center")
            else:
                self.text(self.canvas, "SIDE CONTRACT / AFTERMATH STILL PERSISTS", (rect.centerx, rect.bottom - 66), self.fonts.xs, (116, 138, 164), "center")
            self.text(self.canvas, "SELECT", (rect.centerx, rect.bottom - 25), self.fonts.sm, q["color"], "midbottom")
        strip = pygame.Rect(85, 920, 1750, 78)
        self.panel(strip, fill=(7, 12, 24, 246), edge=QUESTS[chain_target]["color"], radius=12)
        self.text(self.canvas, STORY_CHAIN["name"], (112, 936), self.fonts.xs, QUESTS[chain_target]["color"])
        self.text(self.canvas, f"CURRENT / {chain_chapter['name']}", (112, 963), self.fonts.sm, (238, 244, 255))
        self.wrap_text(self.canvas, chain_chapter["brief"], pygame.Rect(540, 938, 850, 48), self.fonts.xs, (185, 204, 226), max_lines=2)
        self.text(self.canvas, f"COMPLETED CYCLES {int(campaign.get('chain_completions', 0)):02d}", (1805, 938), self.fonts.xs, (255, 218, 108), "topright")
        self.text(self.canvas, str(campaign.get("last_chain_event", "CHAIN READY")), (1805, 970), self.fonts.xs, (140, 164, 192), "topright")
        self.text(self.canvas, "LMB SELECT   •   S SETTINGS   •   H GUIDE   •   ESC TITLE", (960, 1042), self.fonts.sm, (122, 142, 170), "midbottom")

    def draw_hero_select(self, quest_key: str, selected: str | None = None, profile: dict | None = None, selected_order: str = "balanced"):
        q = QUESTS[quest_key]
        profile = profile or {"heroes": {}}
        self._background(q["color"])
        self.draw_title_bar(f"{q['name']} / SELECT HERO")
        guild = profile.get("guild", {})
        self.text(self.canvas, f"TREASURY {int(guild.get('credits', 0)):,} CR   •   RENOWN {int(guild.get('renown', 0)):02d}", (1860, 108), self.fonts.xs, (255, 218, 108), "bottomright")
        self.text(self.canvas, "Compatibility predicts pressure—not certainty. Persistent injuries change real behavior.", (960, 150), self.fonts.sm, (205, 218, 238), "midtop")
        if profile.get("settings", {}).get("tutorial_tips", True) and not profile.get("onboarding", {}).get("completed", False):
            self.text(self.canvas, "FIRST CONTRACT / STEP 2 OF 3 / CHOOSE A HERO, THEN PREPARE", (960, 184), self.fonts.xs, (255, 218, 108), "midtop")
        card_w, card_h, gap, start_x = 420, 640, 30, 75
        for i, key in enumerate(HEROES):
            h = HEROES[key]
            fit = quest_fit(key, quest_key)
            record = profile.get("heroes", {}).get(key, {})
            strain = int(record.get("strain", 0))
            availability = record.get("availability", "ACTIVE")
            condition = recovery_state(key, strain)
            rect = pygame.Rect(start_x + i * (card_w + gap), 215, card_w, card_h)
            active = selected == key
            edge = h["color"] if active and availability == "ACTIVE" else ((255, 72, 96) if availability == "ELIMINATED" else (55, 78, 108))
            pygame.draw.rect(self.canvas, (12, 18, 33) if availability == "ACTIVE" else (20, 10, 16), rect, border_radius=18)
            pygame.draw.rect(self.canvas, edge, rect, 4 if active else 2, border_radius=18)
            portrait_rect = pygame.Rect(rect.centerx - 70, rect.top + 12, 140, 140)
            pygame.draw.rect(self.canvas, (5, 9, 18), portrait_rect, border_radius=12)
            portrait = self.actors.portrait(key, 132)
            self.canvas.blit(portrait, portrait.get_rect(center=portrait_rect.center))
            pygame.draw.rect(self.canvas, h["color"] if availability == "ACTIVE" else (255, 72, 96), portrait_rect, 2, border_radius=12)
            restorations = int(record.get("restorations", 0))
            if restorations > 0:
                # Persistent revival scar makes restored actors visually distinct.
                pygame.draw.line(self.canvas, (232, 250, 255), (portrait_rect.left + 35, portrait_rect.top + 25), (portrait_rect.right - 30, portrait_rect.bottom - 28), 3)
                pygame.draw.circle(self.canvas, h["accent"], (portrait_rect.right - 18, portrait_rect.top + 18), 10, 2)
            if availability == "ELIMINATED":
                veil = pygame.Surface(portrait_rect.size, pygame.SRCALPHA); veil.fill((15, 0, 8, 155)); self.canvas.blit(veil, portrait_rect)
                pygame.draw.line(self.canvas, (255, 72, 96), portrait_rect.topleft, portrait_rect.bottomright, 7)
                self.text(self.canvas, "ELIMINATED", portrait_rect.center, self.fonts.xs, (255, 120, 138), "center")
            self.text(self.canvas, h["height"], (portrait_rect.right - 7, portrait_rect.bottom - 6), self.fonts.xs, h["accent"], "bottomright")
            self.text(self.canvas, h["name"], (rect.centerx, rect.top + 160), self.fonts.hero, (240, 247, 255), "midtop")
            self.text(self.canvas, h["title"], (rect.centerx, rect.top + 194), self.fonts.xs, h["color"], "midtop")
            self.text(self.canvas, h.get("guild_epithet", h["title"]), (rect.centerx, rect.top + 218), self.fonts.xs, h["accent"], "midtop")
            badge = pygame.Rect(rect.left + 24, rect.top + 240, rect.width - 48, 46)
            pygame.draw.rect(self.canvas, (7, 12, 24), badge, border_radius=8)
            pygame.draw.rect(self.canvas, fit["color"], badge, 2, border_radius=8)
            self.text(self.canvas, fit["rating"], (badge.left + 12, badge.centery), self.fonts.xs, fit["color"], "midleft")
            self.text(self.canvas, f"{fit['percent']}%", (badge.right - 12, badge.centery), self.fonts.sm, fit["color"], "midright")
            trait_line = " / ".join(h["personality"])
            if self.fonts.xs.size(trait_line)[0] <= rect.width - 34:
                self.text(self.canvas, trait_line, (rect.centerx, rect.top + 296), self.fonts.xs, h["accent"], "midtop")
            else:
                self.text(self.canvas, " / ".join(h["personality"][:2]), (rect.centerx, rect.top + 292), self.fonts.xs, h["accent"], "midtop")
                self.text(self.canvas, h["personality"][2], (rect.centerx, rect.top + 316), self.fonts.xs, h["accent"], "midtop")
            self.text(self.canvas, "STRENGTH", (rect.left + 24, rect.top + 346), self.fonts.xs, h["color"])
            self.wrap_text(self.canvas, h["strength"], pygame.Rect(rect.left + 24, rect.top + 376, rect.width - 48, 50), self.fonts.xs, (205, 215, 232), max_lines=2)
            self.text(self.canvas, "WEAKNESS", (rect.left + 24, rect.top + 433), self.fonts.xs, (255, 108, 128))
            self.wrap_text(self.canvas, h["weakness"], pygame.Rect(rect.left + 24, rect.top + 463, rect.width - 48, 52), self.fonts.xs, (205, 215, 232), max_lines=2)
            self.text(self.canvas, "DOCTRINE", (rect.left + 24, rect.top + 523), self.fonts.xs, h["accent"])
            self.wrap_text(self.canvas, h["doctrine"], pygame.Rect(rect.left + 24, rect.top + 553, rect.width - 48, 48), self.fonts.xs, (175, 190, 214), max_lines=2)
            condition_color = (255, 92, 112) if availability == "ELIMINATED" else ((92, 255, 184) if condition["severity"] == 0 else ((255, 218, 104) if condition["severity"] == 1 else (255, 104, 116)))
            self.text(self.canvas, h["ability"], (rect.centerx, rect.top + 592), self.fonts.xs, (120, 126, 140) if availability == "ELIMINATED" else (240, 246, 255), "midtop")
            status_label = f"ELIMINATED / DEATHS {int(record.get('deaths', 0))}" if availability == "ELIMINATED" else f"{condition['name']} / {strain:02d}"
            self.text(self.canvas, status_label, (rect.centerx, rect.top + 620), self.fonts.xs, condition_color, "midtop")

        for i, (key, order) in enumerate(HERO_ORDERS.items()):
            rect = pygame.Rect(95 + i * 345, 862, 310, 58)
            active = selected_order == key
            pygame.draw.rect(self.canvas, (10, 17, 31), rect, border_radius=10)
            pygame.draw.rect(self.canvas, order["color"] if active else (54, 77, 104), rect, 3 if active else 1, border_radius=10)
            self.text(self.canvas, order["short"], rect.center, self.fonts.xs, order["color"] if active else (155, 174, 198), "center")
        order = HERO_ORDERS[selected_order]
        order_panel = pygame.Rect(320, 928, 1280, 42)
        self.panel(order_panel, fill=(7, 13, 25, 238), edge=order["color"], radius=8)
        self.text(self.canvas, f"GUILD ORDER / {order['name']}", (340, order_panel.centery), self.fonts.xs, order["color"], "midleft")
        self.text(self.canvas, order["brief"], (1575, order_panel.centery), self.fonts.xs, (198, 214, 234), "midright")
        if selected:
            fit = quest_fit(selected, quest_key)
            record = profile.get("heroes", {}).get(selected, {})
            selected_available = record.get("availability", "ACTIVE") == "ACTIVE"
            quote = recovery_quote(selected, record.get("strain", 0))
            recover_button = pygame.Rect(245, 978, 430, 54)
            affordable = int(guild.get("credits", 0)) >= int(quote["cost"])
            recover_color = (98, 255, 190) if quote["ready"] and affordable else (92, 108, 130)
            pygame.draw.rect(self.canvas, (10, 22, 31), recover_button, border_radius=12)
            pygame.draw.rect(self.canvas, recover_color, recover_button, 3 if quote["ready"] and affordable else 1, border_radius=12)
            label = f"R RECOVER -{quote['reduction']} STRAIN / {quote['cost']:,} CR" if quote["ready"] else "HERO FULLY RECOVERED"
            self.text(self.canvas, label, recover_button.center, self.fonts.xs, recover_color, "center")
            button = pygame.Rect(735, 978, 450, 54)
            pygame.draw.rect(self.canvas, (12, 28, 40), button, border_radius=12)
            pygame.draw.rect(self.canvas, HEROES[selected]["color"], button, 3, border_radius=12)
            prepare_color = HEROES[selected]["color"] if selected_available else (100, 105, 120)
            if not selected_available:
                pygame.draw.rect(self.canvas, (28, 14, 20), button, border_radius=12)
                pygame.draw.rect(self.canvas, (255, 72, 96), button, 2, border_radius=12)
            self.text(self.canvas, f"PREPARE / {fit['rating']} {fit['percent']}%" if selected_available else "HERO ELIMINATED", button.center, self.fonts.sm, prepare_color if selected_available else (255, 100, 120), "center")
        else:
            self.text(self.canvas, "SELECT A HERO TO REVIEW THE CONTRACT MATCH", (960, 1018), self.fonts.sm, (150, 170, 198), "midtop")
        self.text(self.canvas, "LMB HERO / ORDER  •  R RECOVER  •  O CYCLE ORDER  •  ENTER PREPARE  •  RMB BACK", (960, 1074), self.fonts.sm, (130, 150, 178), "midbottom")


    def draw_restore_select(self, profile: dict, selected_hero: str | None = None):
        self._background((112, 70, 160))
        self.draw_title_bar("VICTORY RESTORATION / SELECT ONE FALLEN HERO")
        guild = profile.get("guild", {})
        tokens = int(guild.get("restoration_tokens", 0))
        self.text(self.canvas, f"RESTORATION CHARGES {tokens}", (1860, 108), self.fonts.xs, (255, 220, 112), "bottomright")
        self.text(self.canvas, "A surviving hero returned victorious. Choose who the guild reconstructs.", (960, 155), self.fonts.md, (215, 226, 244), "midtop")
        card_w, card_h, gap, start_x = 420, 620, 30, 75
        for i, key in enumerate(HEROES):
            h = HEROES[key]; record = profile.get("heroes", {}).get(key, {})
            fallen = record.get("availability", "ACTIVE") == "ELIMINATED"
            rect = pygame.Rect(start_x + i * (card_w + gap), 230, card_w, card_h)
            fill = (22, 9, 18) if fallen else (10, 18, 24)
            selected = fallen and key == selected_hero
            edge = (238, 248, 255) if selected else (255, 82, 112) if fallen else (58, 92, 94)
            pygame.draw.rect(self.canvas, fill, rect, border_radius=18); pygame.draw.rect(self.canvas, edge, rect, 5 if selected else 3 if fallen else 1, border_radius=18)
            portrait = self.actors.portrait(key, 205)
            self.canvas.blit(portrait, portrait.get_rect(center=(rect.centerx, rect.top + 135)))
            if fallen:
                pygame.draw.line(self.canvas, (255, 90, 115), (rect.centerx-75, rect.top+58), (rect.centerx+72, rect.top+210), 5)
            self.text(self.canvas, h["name"], (rect.centerx, rect.top + 255), self.fonts.hero, (245, 248, 255), "midtop")
            self.text(self.canvas, h["title"], (rect.centerx, rect.top + 300), self.fonts.xs, h["color"] if fallen else (110, 132, 142), "midtop")
            self.text(self.canvas, "ELIMINATED IN FIELD" if fallen else "ACTIVE / NOT ELIGIBLE", (rect.centerx, rect.top + 345), self.fonts.sm, edge, "midtop")
            self.wrap_text(self.canvas, h["visual_signature"], pygame.Rect(rect.left+34, rect.top+395, rect.width-68, 70), self.fonts.xs, (190, 204, 224), max_lines=3)
            deaths = int(record.get("deaths", 0)); restores = int(record.get("restorations", 0))
            self.text(self.canvas, f"DEATHS {deaths}   •   PRIOR RESTORES {restores}", (rect.centerx, rect.top+495), self.fonts.xs, (180, 190, 210), "midtop")
            if fallen:
                self.text(self.canvas, "LMB RESTORE", (rect.centerx, rect.bottom-38), self.fonts.sm, (255, 218, 112), "midbottom")
            else:
                self.text(self.canvas, "STANDING", (rect.centerx, rect.bottom-38), self.fonts.sm, (96, 255, 190), "midbottom")
        self.panel(pygame.Rect(410, 900, 1100, 95), fill=(8, 13, 25, 244), edge=(255, 218, 112), radius=14)
        self.text(self.canvas, "RESTORED HERO RETURNS WITH 28–55 STRAIN AND A PERMANENT REVIVAL SCAR", (960, 930), self.fonts.sm, (255, 225, 145), "midtop")
        self.text(self.canvas, "The choice is saved immediately. It cannot be spent twice.", (960, 968), self.fonts.xs, (174, 192, 218), "midtop")

    def draw_last_light(self, profile: dict):
        self._background((180, 38, 72))
        self.draw_title_bar("TOTAL ROSTER LOSS / LAST LIGHT PROTOCOL")
        shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA); shade.fill((18, 0, 8, 90)); self.canvas.blit(shade, (0, 0))
        self.text(self.canvas, "THE LAST HERO HAS FALLEN", (960, 185), self.fonts.xl, (255, 96, 122), "midtop")
        self.text(self.canvas, "No active contract operative remains.", (960, 265), self.fonts.md, (232, 220, 230), "midtop")
        y = 355
        for i, key in enumerate(HEROES):
            h = HEROES[key]; x = 420 + i * 360
            portrait = self.actors.portrait(key, 170)
            self.canvas.blit(portrait, portrait.get_rect(center=(x, y)))
            pygame.draw.circle(self.canvas, (255, 72, 100), (x, y), 92, 3)
            pygame.draw.line(self.canvas, (255, 72, 100), (x-68, y-68), (x+68, y+68), 6)
            self.text(self.canvas, h["name"], (x, y+110), self.fonts.sm, (255, 168, 180), "midtop")
        r = pygame.Rect(410, 590, 1100, 285); self.panel(r, fill=(11, 8, 20, 250), edge=(255, 84, 112), radius=18)
        self.text(self.canvas, "LAST LIGHT SAFETY RESET", (960, 625), self.fonts.lg, (255, 120, 142), "midtop")
        self.wrap_text(self.canvas, "The guild archives the failed cycle, reconstitutes all four heroes, clears restoration charges, and starts a new roster cycle. Treasury, renown, contracts, deaths, and historical records remain intact.", pygame.Rect(500, 700, 920, 95), self.fonts.sm, (216, 226, 242), max_lines=4)
        self.text(self.canvas, f"CURRENT CYCLE {int(profile.get('guild', {}).get('cycles', 1)):02d}   •   PRIOR WIPES {int(profile.get('guild', {}).get('roster_wipes', 0)):02d}", (960, 812), self.fonts.xs, (255, 210, 120), "midtop")
        self.text(self.canvas, "ENTER ACKNOWLEDGE AND BEGIN NEW CYCLE", (960, 945), self.fonts.md, (255, 235, 190), "midtop")


    def draw_bond_event(self, profile: dict, selected_index: int = 0):
        pending = profile.get("campaign", {}).get("pending_bond_event") or {"pair": "nyx|circuit", "level": 3}
        pair = pending.get("pair", "nyx|circuit")
        level = int(pending.get("level", 3))
        event = BOND_EVENTS.get(pair, BOND_EVENTS["nyx|circuit"])
        a, b = pair.split("|")
        bond = profile.get("bonds", {}).get(pair, {})
        self._background(event["color"])
        self.draw_title_bar("GUILD RELATIONSHIP EVENT")
        self.text(self.canvas, event["name"], (960, 155), self.fonts.xl, (242, 248, 255), "midtop")
        self.text(self.canvas, f"BOND MILESTONE {level}/9   •   LINK MASTERY {int(bond.get('mastery', 0))}", (960, 225), self.fonts.sm, event["color"], "midtop")
        left = pygame.Rect(190, 300, 620, 390); right = pygame.Rect(1110, 300, 620, 390)
        for rect, key in ((left, a), (right, b)):
            hero = HEROES[key]
            self.panel(rect, fill=(7, 13, 26, 246), edge=hero["color"], radius=18)
            portrait = self.actors.portrait(key, 220)
            self.canvas.blit(portrait, portrait.get_rect(center=(rect.centerx, rect.top+145)))
            self.text(self.canvas, hero["name"], (rect.centerx, rect.top+270), self.fonts.hero, (242, 248, 255), "midtop")
            self.text(self.canvas, hero["guild_epithet"], (rect.centerx, rect.top+315), self.fonts.xs, hero["accent"], "midtop")
            self.text(self.canvas, f"STRAIN {int(profile['heroes'][key].get('strain', 0)):02d}", (rect.centerx, rect.top+350), self.fonts.xs, hero["color"], "midtop")
        prompt = pygame.Rect(355, 680, 1210, 84)
        self.panel(prompt, fill=(8, 14, 28, 250), edge=event["color"], radius=13)
        self.wrap_text(self.canvas, event["prompt"], pygame.Rect(390, 700, 1140, 52), self.fonts.sm, (220, 232, 246), max_lines=2)
        choices = ((pygame.Rect(330,790,580,130), "ANCHOR THE BOND", event["anchor"], event["color"]), (pygame.Rect(1010,790,580,130), "KEEP THE BOUNDARY", event["boundary"], (145, 178, 214)))
        for i, (rect, title, desc, edge) in enumerate(choices):
            active = i == selected_index
            focus_edge = (238, 248, 255) if active else edge
            self.panel(rect, fill=(10, 18, 34, 248) if active else (7, 13, 26, 248), edge=focus_edge, radius=14)
            if active:
                pygame.draw.rect(self.canvas, focus_edge, rect, 4, border_radius=14)
            self.text(self.canvas, ("› " if active else "") + title, (rect.centerx, rect.top+20), self.fonts.sm, focus_edge, "midtop")
            self.wrap_text(self.canvas, desc, pygame.Rect(rect.left+24, rect.top+58, rect.width-48, 56), self.fonts.xs, (204, 219, 238), max_lines=3)
        self.text(self.canvas, "ANCHOR: +1 LINK MASTERY, +2 STRAIN EACH   •   BOUNDARY: -4 STRAIN EACH", (960, 960), self.fonts.xs, (170, 190, 215), "midtop")
        self.text(self.canvas, "LMB CHOOSE   •   1/A ANCHOR   •   2/D BOUNDARY", (960, 1035), self.fonts.sm, (120, 146, 176), "midbottom")

    def draw_loadout_prep(self, quest_key: str, hero_key: str, order_key: str, equipment_key: str, sidekick_keys=(), profile: dict | None = None):
        q = QUESTS[quest_key]
        h = HEROES[hero_key]
        order = HERO_ORDERS[order_key]
        intel = QUEST_INTEL[quest_key]
        profile = profile or {"heroes": {}}
        if isinstance(sidekick_keys, str):
            sidekick_keys = [] if sidekick_keys in {"none", "auto", ""} else [sidekick_keys]
        sidekick_keys = list(sidekick_keys)[:2]
        strain = int(profile.get("heroes", {}).get(hero_key, {}).get("strain", 0))
        self._background(q["color"])
        self.draw_title_bar(f"{q['name']} / EQUIPMENT PREPARATION")
        if profile.get("settings", {}).get("tutorial_tips", True) and not profile.get("onboarding", {}).get("completed", False):
            self.text(self.canvas, "FIRST CONTRACT / STEP 3 OF 3 / SELECT A KIT AND OPTIONAL SIDEKICKS", (960, 145), self.fonts.xs, (255, 218, 108), "midtop")
        else:
            self.text(self.canvas, "Prepare for the contract you understand—not the one you hope is waiting.", (960, 145), self.fonts.sm, (202, 217, 238), "midtop")

        hero_panel = pygame.Rect(100, 190, 500, 285)
        self.panel(hero_panel, fill=(8, 14, 28, 242), edge=h["color"], radius=14)
        portrait = self.actors.portrait(hero_key, 180, equipment_key)
        self.canvas.blit(portrait, portrait.get_rect(center=(205, 325)))
        self.text(self.canvas, h["name"], (315, 220), self.fonts.hero, (242, 248, 255))
        self.text(self.canvas, h["title"], (315, 264), self.fonts.xs, h["color"])
        self.text(self.canvas, f"ORDER / {order['name']}", (315, 305), self.fonts.xs, order["color"])
        self.wrap_text(self.canvas, order["brief"], pygame.Rect(315, 338, 250, 55), self.fonts.xs, (188, 205, 228), max_lines=2)
        condition = recovery_state(hero_key, strain)
        condition_color = (96, 255, 184) if condition["severity"] == 0 else ((255, 214, 100) if condition["severity"] == 1 else (255, 104, 122))
        self.text(self.canvas, f"FIELD CONDITION / {condition['name']} / STRAIN {strain:02d}", (120, 422), self.fonts.xs, condition_color)

        intel_panel = pygame.Rect(640, 190, 1180, 285)
        self.panel(intel_panel, fill=(8, 14, 28, 242), edge=q["color"], radius=14)
        self.text(self.canvas, "QUEST INTELLIGENCE", (675, 216), self.fonts.hero, (242, 248, 255))
        campaign = profile.get("campaign", {})
        counts = campaign.get("aftermath_counts", {})
        aftermath_key = "none"
        if quest_key == "recovery" and int(counts.get("purge", 0)) > 0:
            aftermath_key = "choir_silence"
        elif quest_key == "rescue" and int(counts.get("recovery", 0)) > 0:
            aftermath_key = "open_index"
        elif quest_key == "purge" and int(campaign.get("chain_completions", 0)) > 0 and int(counts.get("rescue", 0)) > 0:
            aftermath_key = "mercy_route"
        aftermath = SOVEREIGN_AFTERMATHS[aftermath_key]
        self.text(self.canvas, f"AFTERMATH / {aftermath['name']}", (1780, 220), self.fonts.xs, aftermath["color"], "topright")
        self.text(self.canvas, "CONFIRMED", (675, 270), self.fonts.xs, (92, 238, 255))
        for i, item in enumerate(intel["confirmed"]):
            self.text(self.canvas, "◆ " + item, (690, 304 + i * 31), self.fonts.xs, (205, 220, 238))
        self.text(self.canvas, "PROBABLE", (1180, 270), self.fonts.xs, (255, 207, 96))
        for i, item in enumerate(intel["probable"]):
            self.wrap_text(self.canvas, "◇ " + item, pygame.Rect(1195, 304 + i * 48, 570, 44), self.fonts.xs, (220, 222, 232), max_lines=2)
        self.text(self.canvas, "UNRESOLVED VARIABLE", (1180, 382), self.fonts.xs, (220, 102, 255))
        self.wrap_text(self.canvas, intel["unknown"], pygame.Rect(1195, 414, 570, 44), self.fonts.xs, (205, 210, 230), max_lines=2)

        for i, (key, kit) in enumerate(EQUIPMENT_KITS.items()):
            rect = pygame.Rect(100 + i * 455, 520, 410, 300)
            active = key == equipment_key
            fit = equipment_fit(key, hero_key, quest_key)
            pygame.draw.rect(self.canvas, (10, 17, 31), rect, border_radius=14)
            pygame.draw.rect(self.canvas, kit["color"] if active else (54, 77, 104), rect, 4 if active else 2, border_radius=14)
            pygame.draw.rect(self.canvas, kit["color"], (rect.left, rect.top, rect.width, 8), border_radius=7)
            self.text(self.canvas, kit["type"], (rect.left + 22, rect.top + 26), self.fonts.xs, kit["color"])
            self.text(self.canvas, kit["name"], (rect.left + 22, rect.top + 60), self.fonts.sm, (242, 248, 255))
            badge = pygame.Rect(rect.left + 22, rect.top + 103, rect.width - 44, 40)
            pygame.draw.rect(self.canvas, (6, 11, 22), badge, border_radius=8)
            pygame.draw.rect(self.canvas, fit["color"], badge, 2, border_radius=8)
            self.text(self.canvas, fit["rating"], (badge.left + 12, badge.centery), self.fonts.xs, fit["color"], "midleft")
            self.text(self.canvas, f"{fit['percent']}%", (badge.right - 12, badge.centery), self.fonts.xs, fit["color"], "midright")
            self.wrap_text(self.canvas, kit["brief"], pygame.Rect(rect.left + 22, rect.top + 158, rect.width - 44, 60), self.fonts.xs, (190, 207, 229), max_lines=3)
            for j, effect in enumerate(kit["effects"][:3]):
                self.text(self.canvas, "• " + effect, (rect.left + 25, rect.top + 225 + j * 25), self.fonts.xs, (213, 224, 238))
            if active:
                self.text(self.canvas, "EQUIPPED", (rect.right - 20, rect.top + 25), self.fonts.xs, kit["color"], "topright")

        selected = EQUIPMENT_KITS[equipment_key]
        # Banked Sidekick Perks physically add active heroes to the mission.
        guild = profile.get("guild", {})
        perks = max(0, int(guild.get("sidekick_perks", 0)))
        fallen = [k for k, rec in profile.get("heroes", {}).items() if rec.get("availability", "ACTIVE") == "ELIMINATED"]
        limit = 0 if fallen else min(2, perks)
        for i, (key, link) in enumerate(HERO_LINKS.items()):
            rect = pygame.Rect(250 + i * 355, 832, 320, 72)
            active = key in sidekick_keys
            roster_active = key != hero_key and profile.get("heroes", {}).get(key, {}).get("availability", "ACTIVE") == "ACTIVE"
            available = roster_active and limit > 0
            edge = link["color"] if active else ((62, 82, 108) if available else (50, 42, 56))
            pygame.draw.rect(self.canvas, (8, 14, 27), rect, border_radius=10)
            pygame.draw.rect(self.canvas, edge, rect, 3 if active else 1, border_radius=10)
            self.text(self.canvas, HEROES[key]["name"], (rect.left+14, rect.top+12), self.fonts.xs, edge)
            if key == hero_key:
                status = "LEAD HERO"
            elif fallen:
                status = "RESTORE FALLEN FIRST"
            elif not perks:
                status = "NO SIDEKICK PERKS"
            elif active:
                status = "JOINING MISSION"
            else:
                status = "AVAILABLE"
            self.text(self.canvas, status, (rect.left+14, rect.top+39), self.fonts.xs, (230, 238, 248) if active else (145, 163, 187))
            if roster_active:
                pair = "|".join(sorted((hero_key, key), key=list(HEROES).index))
                mastery = int(profile.get("bonds", {}).get(pair, {}).get("mastery", 0))
                self.text(self.canvas, f"M{mastery}", (rect.right-12, rect.bottom-12), self.fonts.xs, link["color"] if active else (120, 142, 168), "bottomright")
        self.text(self.canvas, f"SIDEKICK PERKS / {perks} BANKED   •   TEAM {1+len(sidekick_keys)}/3", (960, 918), self.fonts.xs, (255, 220, 112) if perks else (150,165,188), "midbottom")
        self.text(self.canvas, f"KIT RISK / {selected['risk']}", (960, 935), self.fonts.xs, (182, 198, 220), "midbottom")
        button = pygame.Rect(735, 940, 450, 66)
        pygame.draw.rect(self.canvas, (11, 29, 40), button, border_radius=12)
        pygame.draw.rect(self.canvas, selected["color"], button, 3, border_radius=12)
        self.text(self.canvas, f"DEPLOY WITH {selected['name']}", button.center, self.fonts.sm, selected["color"], "center")
        self.text(self.canvas, "LMB SELECT KIT / SIDEKICK  •  E CYCLE KIT  •  B CYCLE TEAM  •  ENTER DEPLOY  •  RMB BACK", (960, 1070), self.fonts.xs, (130, 151, 180), "midbottom")

    def _tile_world_texture(self, rect: pygame.Rect, texture_key: str, alpha: int = 205) -> None:
        texture = self.world_textures.get(texture_key)
        if texture is None:
            return
        tile = texture.copy()
        tile.set_alpha(alpha)
        old_clip = self.canvas.get_clip()
        self.canvas.set_clip(rect)
        for y in range(rect.top, rect.bottom, tile.get_height()):
            for x in range(rect.left, rect.right, tile.get_width()):
                self.canvas.blit(tile, (x, y))
        self.canvas.set_clip(old_clip)

    @staticmethod
    def _obstacle_visual_tier(obj: WorldObstacle) -> str:
        # One dominant authored landmark per contract gets the strongest visual
        # weight.  This is presentation-only; collision remains the exact Pass 20
        # rect set.
        if obj.object_id in {"p_gate_north", "r_index_stack", "s_u_south"}:
            return "landmark"
        if obj.destructible:
            return "interactive"
        if obj.prefab.startswith("setpiece_") or obj.prefab == "relic_carriage":
            return "setpiece"
        return "support"

    def _draw_obstacle_foundation(self, obj: WorldObstacle, env: dict, tier: str) -> None:
        if obj.category == "spawner":
            return
        # A thin floor plate groups multipart pieces without pretending the gaps
        # are solid. The plate is intentionally lower-value than wall faces.
        plate = obj.bounds.inflate(18 if tier == "landmark" else 10, 14 if tier == "landmark" else 8)
        base = tuple(max(3, c - 5) for c in env["floor"])
        line = self._lift_color(env["grid"], 13 if tier == "landmark" else 5)
        pygame.draw.rect(self.canvas, base, plate, border_radius=8)
        pygame.draw.rect(self.canvas, line, plate, 1, border_radius=8)
        if tier in {"landmark", "setpiece"}:
            # Corner brackets read as floor inlays, never blockers.
            length = 15 if tier == "landmark" else 10
            for x, y, sx, sy in ((plate.left, plate.top, 1, 1), (plate.right, plate.top, -1, 1),
                                 (plate.left, plate.bottom, 1, -1), (plate.right, plate.bottom, -1, -1)):
                pygame.draw.line(self.canvas, line, (x, y), (x + sx*length, y), 2 if tier == "landmark" else 1)
                pygame.draw.line(self.canvas, line, (x, y), (x, y + sy*length), 2 if tier == "landmark" else 1)

    def _draw_world_obstacle(self, obj: WorldObstacle, env: dict) -> None:
        """Draw one world obstacle without changing its collision footprint."""
        if obj.category == "spawner":
            c = obj.bounds.center
            pulse = 34 + int(5 * (0.5 + 0.5 * math.sin(self.time * 5.2 + c[0] * .01)))
            plate = pygame.Rect(0, 0, 86, 70); plate.center = c
            pygame.draw.rect(self.canvas, (4, 8, 16), plate, border_radius=6)
            pygame.draw.rect(self.canvas, self._lift_color(env["grid"], 12), plate, 2, border_radius=6)
            pygame.draw.line(self.canvas, env["edge"], (c[0]-30, c[1]), (c[0]+30, c[1]), 1)
            pygame.draw.line(self.canvas, env["edge"], (c[0], c[1]-24), (c[0], c[1]+24), 1)
            texture = self.world_textures.get(obj.texture_key)
            if texture is not None:
                stamp = pygame.transform.smoothscale(texture, (68, 54))
                stamp.set_alpha(190)
                self.canvas.blit(stamp, stamp.get_rect(center=c))
            pygame.draw.lines(self.canvas, env["secondary"], True, [(c[0],c[1]-pulse),(c[0]+pulse,c[1]),(c[0],c[1]+pulse),(c[0]-pulse,c[1])], 2)
            return

        if obj.destroyed:
            # Rubble remains visible but deliberately stops blocking navigation,
            # vision and fire so the breach creates a real tactical lane.
            rubble = obj.bounds.inflate(-max(8, obj.bounds.width // 3), -max(8, obj.bounds.height // 3))
            pygame.draw.rect(self.canvas, tuple(max(4, c // 2) for c in env["wall"]), rubble, border_radius=5)
            self._tile_world_texture(rubble, obj.texture_key, 80)
            for k in range(6):
                x = rubble.left + 8 + (k * 23) % max(12, rubble.width - 16)
                y = rubble.top + 7 + (k * 17) % max(12, rubble.height - 14)
                shard = env["secondary"] if k % 2 else env["edge"]
                pygame.draw.line(self.canvas, shard, (x-8,y+5), (x+9,y-4), 2)
                if k % 2 == 0:
                    pygame.draw.circle(self.canvas, shard, (x, y), 3, 1)
            return

        tier = self._obstacle_visual_tier(obj)
        self._draw_obstacle_foundation(obj, env, tier)
        tier_edge = {
            "support": self._lift_color(env["edge"], -18),
            "setpiece": self._lift_color(env["edge"], 8),
            "interactive": self._lift_color(env["secondary"], 6),
            "landmark": self._lift_color(env["accent"], 24),
        }[tier]
        texture_alpha = {"support": 166, "setpiece": 218, "interactive": 224, "landmark": 242}[tier]
        outline_width = {"support": 2, "setpiece": 3, "interactive": 3, "landmark": 4}[tier]

        for rect in obj.rects:
            # Pseudo-depth remains bounded to the real collision footprint.
            shadow_offset = 8 if tier == "support" else (10 if tier == "setpiece" else 12)
            shadow = rect.move(shadow_offset, shadow_offset + 2)
            pygame.draw.rect(self.canvas, (1, 3, 8), shadow, border_radius=6)
            side_h = 7 if tier == "support" else 10
            side = pygame.Rect(rect.left + 5, rect.bottom - 4, max(1, rect.width - 5), side_h)
            pygame.draw.rect(self.canvas, tuple(max(2, c // 2) for c in env["wall"]), side, border_radius=3)
            lift = 11 if tier == "support" else (16 if tier == "setpiece" else 20)
            if tier == "landmark":
                lift = 25
            fill = tuple(min(255, c + lift + (18 if obj.hit_flash > 0 else 0)) for c in env["wall"])
            pygame.draw.rect(self.canvas, fill, rect, border_radius=6)
            self._tile_world_texture(rect.inflate(-4, -4), obj.texture_key, texture_alpha)

            # Long cover receives sparse structural ribs; square pieces get a
            # central inset.  This breaks up repeated rectangles without adding
            # fake geometry or changing collision.
            if rect.width >= rect.height * 2.2:
                rib = self._lift_color(tier_edge, -18 if tier == "support" else -8)
                for rx in range(rect.left + 30, rect.right - 18, 54):
                    pygame.draw.line(self.canvas, rib, (rx, rect.top+8), (rx, rect.bottom-8), 1)
            elif rect.height >= rect.width * 1.7:
                rib = self._lift_color(tier_edge, -18 if tier == "support" else -8)
                for ry in range(rect.top + 28, rect.bottom - 14, 48):
                    pygame.draw.line(self.canvas, rib, (rect.left+8, ry), (rect.right-8, ry), 1)

            top_w = 2 if tier == "support" else 3
            pygame.draw.line(self.canvas, self._lift_color(tier_edge, 22), (rect.left+8, rect.top+4), (rect.right-8, rect.top+4), top_w)
            pygame.draw.line(self.canvas, self._lift_color(tier_edge, 5), (rect.left+4, rect.top+8), (rect.left+4, rect.bottom-8), 1 if tier == "support" else 2)
            pygame.draw.line(self.canvas, self._lift_color(tier_edge, -38), (rect.left+8, rect.bottom-4), (rect.right-8, rect.bottom-4), 2)
            pygame.draw.rect(self.canvas, tier_edge, rect, outline_width, border_radius=6)
            inner = rect.inflate(-18, -18)
            if inner.width > 12 and inner.height > 12 and tier != "support":
                inner_color = env["secondary"] if tier == "interactive" else (env["accent"] if tier == "landmark" else tier_edge)
                pygame.draw.rect(self.canvas, inner_color, inner, 1, border_radius=3)

            if tier == "landmark":
                c = rect.center
                pulse = 0.5 + 0.5 * math.sin(self.time * 2.4 + c[0] * .01)
                glow = self._lift_color(env["accent"], int(18 * pulse))
                pygame.draw.line(self.canvas, glow, (rect.left+16, rect.centery), (rect.right-16, rect.centery), 2)

            if obj.destructible:
                state = obj.damage_state
                ratio = obj.integrity
                crack = env["secondary"] if state == "INTACT" else ((255, 180, 84) if state == "CRACKED" else (255, 92, 108))
                if state != "INTACT":
                    pygame.draw.line(self.canvas, crack, (rect.left + rect.width*.28, rect.top+5), (rect.centerx, rect.centery), 3)
                    pygame.draw.line(self.canvas, crack, (rect.centerx, rect.centery), (rect.right-7, rect.bottom-9), 2)
                    if state == "BREACHED":
                        pygame.draw.line(self.canvas, crack, (rect.centerx, rect.centery), (rect.left+12, rect.bottom-7), 2)
                bar = pygame.Rect(rect.left+8, rect.bottom-8, max(10, rect.width-16), 4)
                pygame.draw.rect(self.canvas, (16, 18, 24), bar)
                live = bar.copy(); live.width = max(1, int(bar.width * ratio))
                pygame.draw.rect(self.canvas, crack, live)

    def _draw_contract_site(self, mission: Mission):
        env = self._visual_env(mission)
        q = QUESTS[mission.quest_key]
        floor = WORLD
        pygame.draw.rect(self.canvas, env["floor"], floor, border_radius=6)
        # Each contract owns a distinct floor grammar.
        if mission.quest_key == "purge":
            # Sparse nave inlays replace the old full-field graph paper.
            grid_dim = self._lift_color(env["grid"], -9)
            for x in range(floor.left - 220, floor.right, 156):
                pygame.draw.line(self.canvas, grid_dim, (x, floor.top), (x+310, floor.bottom), 1)
            for y in range(floor.top + 84, floor.bottom, 136):
                pygame.draw.line(self.canvas, (38, 19, 35), (floor.left+20, y), (floor.right-20, y), 1)
            for x in range(floor.left+90, floor.right, 312):
                for y in range(floor.top+68, floor.bottom, 272):
                    pygame.draw.circle(self.canvas, self._lift_color(env["grid"], 2), (x,y), 2, 1)
            # Choir seal is painted into the floor; unlike the physical prefab
            # cover below, it deliberately reads as a traversable surface mark.
            pit = pygame.Rect(792, 425, 350, 275)
            pygame.draw.ellipse(self.canvas, env["accent"], pit, 2)
            pygame.draw.ellipse(self.canvas, env["secondary"], pit.inflate(-54, -54), 1)
            pygame.draw.line(self.canvas, env["grid"], pit.midleft, pit.midright, 1)
            pygame.draw.line(self.canvas, env["grid"], pit.midtop, pit.midbottom, 1)
            for x in (305, 1590):
                for y in (280, 470, 660):
                    window = pygame.Rect(x-36, y-66, 72, 132)
                    pygame.draw.rect(self.canvas, (35, 11, 31), window, border_radius=26)
                    pygame.draw.rect(self.canvas, env["secondary"], window, 2, border_radius=26)
                    pygame.draw.line(self.canvas, env["accent"], window.midtop, window.midbottom, 2)
            for x,y in ((610,265),(1270,820),(1510,315)):
                # Embedded voltage seals are floor details, not fake solid braziers.
                pygame.draw.circle(self.canvas, env["secondary"], (x,y), 18, 1)
                pygame.draw.circle(self.canvas, env["accent"], (x,y), 7, 1)
                pygame.draw.line(self.canvas, env["grid"], (x-12,y), (x+12,y), 1)
        elif mission.quest_key == "recovery":
            # Archive lanes use large index cells plus small corner ticks instead
            # of a bright square grid across every combat lane.
            grid_dim = self._lift_color(env["grid"], -8)
            for x in range(floor.left+32, floor.right, 160):
                pygame.draw.line(self.canvas, grid_dim, (x, floor.top+18), (x, floor.bottom-18), 1)
            for y in range(floor.top+32, floor.bottom, 160):
                pygame.draw.line(self.canvas, grid_dim, (floor.left+18, y), (floor.right-18, y), 1)
            for x in range(floor.left+80, floor.right, 160):
                for y in range(floor.top+80, floor.bottom, 160):
                    pygame.draw.line(self.canvas, self._lift_color(env["secondary"], -64), (x-6,y), (x+6,y), 1)
                    pygame.draw.line(self.canvas, self._lift_color(env["secondary"], -64), (x,y-6), (x,y+6), 1)
            # Archive stacks are now physical prefab objects. The memory well
            # remains a floor landmark and therefore never lies about collision.
            well = Vec2(mission.world_markers["memory_well"])
            for r in (58,92,128):
                pygame.draw.lines(self.canvas, env["accent"] if r != 92 else env["secondary"], True, [(well.x,well.y-r),(well.x+r,well.y),(well.x,well.y+r),(well.x-r,well.y)], 2)
            for k in range(6):
                ang=self.time*.55+k*math.tau/6
                shard=well+Vec2(math.cos(ang),math.sin(ang))*115
                pygame.draw.polygon(self.canvas, env["secondary"], [(shard.x,shard.y-10),(shard.x+6,shard.y),(shard.x,shard.y+10),(shard.x-6,shard.y)], 1)
        else:
            # The ossuary reads as broad transit plates and drainage seams rather
            # than a uniform grid.
            grid_dim = self._lift_color(env["grid"], -7)
            for y in range(floor.top+54, floor.bottom, 174):
                pygame.draw.line(self.canvas, grid_dim, (floor.left+18, y), (floor.right-18, y), 2)
                pygame.draw.line(self.canvas, self._lift_color(grid_dim, -8), (floor.left+18, y+12), (floor.right-18, y+12), 1)
            for x in range(floor.left+80, floor.right, 240):
                pygame.draw.line(self.canvas, (14, 42, 44), (x, floor.top+20), (x-38, floor.bottom-20), 1)
            # Relic carriages and shrines are now physical prefab objects.
            # Small embedded platform studs remain explicitly floor decoration.
            for x,y in ((260,540),(710,620),(1250,560),(1660,650)):
                pulse=7+int(2*(.5+.5*math.sin(self.time*5+x)))
                pygame.draw.circle(self.canvas, env["accent"], (x,y), pulse, 1)
                pygame.draw.circle(self.canvas, env["secondary"], (x,y), 3)

        # Persistent sovereign aftermaths leave physical evidence in the next linked site.
        if mission.aftermath_key == "choir_silence":
            for i, x in enumerate(range(360, 1680, 220)):
                y = 900 - (i % 2) * 42
                pygame.draw.arc(self.canvas, mission.aftermath["color"], pygame.Rect(x-34, y-18, 68, 36), math.pi, math.tau, 3)
                pygame.draw.line(self.canvas, mission.aftermath["color"], (x-12, y-8), (x+16, y+9), 2)
        elif mission.aftermath_key == "open_index":
            route_points = [(225,875),(620,265),(1015,865),(1570,570)]
            for a, b in zip(route_points, route_points[1:]):
                pygame.draw.line(self.canvas, mission.aftermath["color"], a, b, 3)
                for t in (0.25, 0.5, 0.75):
                    px = int(a[0] + (b[0]-a[0])*t); py = int(a[1] + (b[1]-a[1])*t)
                    pygame.draw.circle(self.canvas, mission.aftermath["color"], (px, py), 5, 1)
        elif mission.aftermath_key == "mercy_route":
            rail = [(180,850),(480,760),(760,690),(1100,560),(1420,430),(1740,300)]
            pygame.draw.lines(self.canvas, mission.aftermath["color"], False, rail, 5)
            for point in rail:
                pygame.draw.circle(self.canvas, mission.aftermath["color"], point, 9, 2)

        # Dominant landmarks receive a traversable floor halo so each contract
        # has an immediate visual anchor without adding blockers.
        landmark_id = {"purge": "p_gate_north", "recovery": "r_index_stack", "rescue": "s_u_south"}[mission.quest_key]
        for obj in mission.world_obstacles:
            if obj.object_id == landmark_id:
                halo = obj.bounds.inflate(54, 46)
                pygame.draw.rect(self.canvas, self._lift_color(env["grid"], 7), halo, 2, border_radius=14)
                pygame.draw.rect(self.canvas, self._lift_color(env["accent"], -28), halo.inflate(-12,-12), 1, border_radius=11)
                break

        pygame.draw.rect(self.canvas, self._lift_color(env["edge"], -5), floor, 2, border_radius=6)
        # Every solid-looking object now owns its actual movement / LOS / projectile
        # footprint.  Floor-only patterns stay non-colliding by construction.
        for obj in mission.world_obstacles:
            self._draw_world_obstacle(obj, env)

        pulse = 0.5 + 0.5 * math.sin(self.time * 4)
        ec = env["secondary"] if mission.quest_key != "rescue" else env["accent"]
        gate = mission.extraction_point
        for dx, dy, sx, sy in ((-38,-38,1,1),(38,-38,-1,1),(-38,38,1,-1),(38,38,-1,-1)):
            x=int(gate.x+dx); y=int(gate.y+dy)
            pygame.draw.line(self.canvas, ec, (x,y), (x+sx*16,y), 3)
            pygame.draw.line(self.canvas, ec, (x,y), (x,y+sy*16), 3)
        self.text(self.canvas, "GUILD GATE", (mission.extraction_point.x, mission.extraction_point.y + 53), self.fonts.xs, ec, "midtop")

        if mission.quest_key == "recovery" and not mission.artifact_collected:
            ac = env["accent"]
            artifact = mission.artifact_point
            pygame.draw.polygon(self.canvas, ac, [(artifact.x,artifact.y-38),(artifact.x+38,artifact.y),(artifact.x,artifact.y+38),(artifact.x-38,artifact.y)], 3)
            pygame.draw.polygon(self.canvas, (245, 238, 255), [(artifact.x,artifact.y-28),(artifact.x+21,artifact.y),(artifact.x,artifact.y+28),(artifact.x-21,artifact.y)], 2)
            self.text(self.canvas, "MEMORY RELIQUARY", (artifact.x, artifact.y + 48), self.fonts.xs, ac, "midtop")

        if mission.complication_triggered:
            cc = mission.complication["color"]
            pulse_r = 24 + int(8 * (0.5 + 0.5 * math.sin(self.time * 6)))
            if mission.quest_key == "purge":
                for pos in [mission.world_markers["comp_0"], mission.world_markers["comp_1"]]:
                    pygame.draw.lines(self.canvas, cc, True, [(pos[0],pos[1]-pulse_r),(pos[0]+pulse_r,pos[1]),(pos[0],pos[1]+pulse_r),(pos[0]-pulse_r,pos[1])], 2)
                    pygame.draw.line(self.canvas, cc, (pos[0]-18, pos[1]), (pos[0]+18, pos[1]), 2)
            elif mission.quest_key == "recovery":
                pygame.draw.line(self.canvas, cc, mission.world_markers["extraction"], mission.extraction_point, 3)
                self.text(self.canvas, "GATE REROUTED", (mission.extraction_point.x, mission.extraction_point.y - 58), self.fonts.xs, cc, "midbottom")
            else:
                for civ in mission.civilians:
                    if not civ.rescued:
                        pygame.draw.lines(self.canvas, cc, True, [(civ.pos.x,civ.pos.y-(pulse_r+12)),(civ.pos.x+(pulse_r+12),civ.pos.y),(civ.pos.x,civ.pos.y+(pulse_r+12)),(civ.pos.x-(pulse_r+12),civ.pos.y)], 2)

    def _draw_contract_atmosphere(self, mission: Mission) -> None:
        """Low-cost, deterministic contract atmosphere. Presentation only."""
        env = self._visual_env(mission)
        old_clip = self.canvas.get_clip()
        self.canvas.set_clip(WORLD)
        quest = mission.quest_key
        # Large, dim light pools break up the flat floor without becoming UI or
        # collision cues. Their motion freezes automatically in reduced motion.
        for i in range(5):
            x = WORLD.left + 160 + ((i * 397 + int(42 * math.sin(self.time * .31 + i))) % max(1, WORLD.width - 320))
            y = WORLD.top + 130 + ((i * 233 + int(34 * math.cos(self.time * .27 + i * 1.7))) % max(1, WORLD.height - 260))
            tint = tuple(env["accent"] if i % 2 == 0 else env["secondary"])
            halo = self._atmosphere_halo_cache.get(tint)
            if halo is None:
                halo = pygame.Surface((170, 110), pygame.SRCALPHA)
                pygame.draw.ellipse(halo, (*tint, 12), halo.get_rect())
                self._atmosphere_halo_cache[tint] = halo
            self.canvas.blit(halo, halo.get_rect(center=(x, y)))

        count = 28
        for i in range(count):
            seed_x = (i * 173 + 47) % WORLD.width
            seed_y = (i * 97 + 31) % WORLD.height
            if quest == "purge":
                drift = (self.time * (18 + i % 5) + i * 23) % WORLD.height
                x = WORLD.left + (seed_x + int(math.sin(self.time * .9 + i) * 16)) % WORLD.width
                y = WORLD.bottom - int((seed_y + drift) % WORLD.height)
                c = env["secondary"] if i % 3 else env["accent"]
                pygame.draw.circle(self.canvas, c, (x, y), 1 + (i % 2))
                if i % 4 == 0:
                    pygame.draw.line(self.canvas, c, (x, y + 6), (x, y - 5), 1)
            elif quest == "recovery":
                x = WORLD.left + (seed_x + int(math.sin(self.time * .35 + i * .7) * 20)) % WORLD.width
                y = WORLD.top + (seed_y + int(math.cos(self.time * .28 + i) * 13)) % WORLD.height
                c = env["accent"] if i % 2 else env["secondary"]
                r = 2 + (i % 3)
                pygame.draw.polygon(self.canvas, c, [(x, y-r), (x+r, y), (x, y+r), (x-r, y)], 1)
            else:
                x = WORLD.left + (seed_x + int(self.time * (8 + i % 3))) % WORLD.width
                y = WORLD.top + (seed_y + int(math.sin(self.time * .4 + i) * 12)) % WORLD.height
                c = env["secondary"] if i % 3 else env["accent"]
                pygame.draw.line(self.canvas, c, (x-6, y+2), (x+6, y-2), 1)

        # Pass 22 removes persistent sovereign aura rings; boss presence comes from silhouette and HUD.
        self.canvas.set_clip(old_clip)

    def _draw_enemy(self, e):
        if e.dead:
            return
        if hasattr(self, "current_mission") and getattr(e, "is_boss", False):
            variant = self.current_mission.boss_profile
        else:
            variant = ENEMY_VARIANTS[self.current_mission.quest_key][e.kind] if hasattr(self, "current_mission") else ENEMY_ARCHETYPES[e.kind]
        self.actors.draw_enemy_world(self.canvas, e, self.time, variant)
        color = variant.get("color", e.color)
        if getattr(e, "hit_flash", 0.0) > 0:
            r = 30
            for dx,dy,sx,sy in ((-r,-r,1,1),(r,-r,-1,1),(-r,r,1,-1),(r,r,-1,-1)):
                x=int(e.pos.x+dx); y=int(e.pos.y+dy)
                pygame.draw.line(self.canvas, (248,250,255), (x,y), (x+sx*9,y), 2)
                pygame.draw.line(self.canvas, color, (x,y), (x,y+sy*9), 2)
        ratio = max(0.0, e.hp / max(1.0, e.max_hp))
        if ratio < 0.999 or getattr(e, "is_boss", False):
            bar = pygame.Rect(int(e.pos.x-22), int(e.pos.y-40), 44, 4)
            pygame.draw.rect(self.canvas, (18,20,27), bar)
            pygame.draw.rect(self.canvas, color, (bar.x, bar.y, int(bar.width*ratio), bar.height))
        if getattr(e, "is_boss", False):
            self.text(self.canvas, variant["name"], (e.pos.x, e.pos.y - 68), self.fonts.xs, variant["accent"], "midbottom")
            self.text(self.canvas, f"PHASE {e.boss_phase}", (e.pos.x, e.pos.y - 50), self.fonts.xs, variant["color"], "midbottom")
        elif e.overridden > 0:
            self.text(self.canvas, "OVERRIDE", (e.pos.x, e.pos.y - 50), self.fonts.xs, (104, 255, 180), "midbottom")

    def _draw_hero(self, mission: Mission):
        h = mission.hero
        spec = HEROES[h.key]
        self.actors.draw_hero_world(self.canvas, mission, self.time)
        if getattr(h, "hit_flash", 0.0) > 0:
            r = 31
            for dx,dy,sx,sy in ((-r,-r,1,1),(r,-r,-1,1),(-r,r,1,-1),(r,r,-1,-1)):
                x=int(h.pos.x+dx); y=int(h.pos.y+dy)
                pygame.draw.line(self.canvas, spec["accent"], (x,y), (x+sx*10,y), 2)
                pygame.draw.line(self.canvas, (246,250,255), (x,y), (x,y+sy*10), 1)
        self.text(self.canvas, spec["name"], (h.pos.x, h.pos.y - 57), self.fonts.xs, spec["color"], "midbottom")
        condition = mission.inspected_actor()["condition"] if mission.inspection.get("type") == "hero" else None
        if h.hp / max(1.0, h.max_hp) < .6:
            self.text(self.canvas, condition or "WOUNDED", (h.pos.x, h.pos.y - 37), self.fonts.xs, (255, 110, 132), "midbottom")

    def _draw_sidekicks(self, mission: Mission):
        for member in getattr(mission, "sidekicks", []):
            self.actors.draw_hero_world(self.canvas, mission, self.time, hero=member)
            spec = HEROES[member.key]
            label = "DOWN" if member.hp <= 0 else spec["name"]
            color = (255,100,120) if member.hp <= 0 else spec["color"]
            self.text(self.canvas, label, (member.pos.x, member.pos.y - 53), self.fonts.xs, color, "midbottom")
            if member.hp > 0 and member.hp < member.max_hp:
                ratio = member.hp / max(1.0, member.max_hp)
                bar = pygame.Rect(int(member.pos.x-20), int(member.pos.y-38), 40, 4)
                pygame.draw.rect(self.canvas, (18,20,27), bar)
                pygame.draw.rect(self.canvas, color, (bar.x,bar.y,int(bar.width*ratio),bar.height))

    def _draw_civilians(self, mission: Mission):
        for civ in mission.civilians:
            if civ.extracted:
                continue
            self.actors.draw_civilian_world(self.canvas, civ, self.time)
            spec = CIVILIAN_ROLES[civ.role_index % len(CIVILIAN_ROLES)]
            color = (96, 255, 212) if civ.rescued else (218, 230, 240)
            if not civ.rescued:
                self.text(self.canvas, spec["role"], (civ.pos.x, civ.pos.y - 32), self.fonts.xs, color, "midbottom")

    def _draw_projectiles(self, mission):
        for p in mission.projectiles:
            direction = p.vel.normalize() if p.vel.length_squared() else Vec2(1, 0)
            tail = p.pos - direction * 26
            mid = p.pos - direction * 12
            pygame.draw.line(self.canvas, (8, 12, 22), tail, p.pos, 7)
            pygame.draw.line(self.canvas, p.color, tail, p.pos, 4)
            pygame.draw.line(self.canvas, (235, 244, 255), mid, p.pos, 2)
            pygame.draw.circle(self.canvas, p.color, p.pos, int(p.radius) + 3, 1)
            pygame.draw.circle(self.canvas, (248, 251, 255), p.pos, int(p.radius))

    def _draw_mission_hud(self, mission: Mission, show_analysis: bool):
        h = mission.hero; spec = HEROES[h.key]; q = QUESTS[mission.quest_key]
        r = pygame.Rect(28, 20, 405, 150); self.panel(r, edge=spec["color"])
        self.text(self.canvas, spec["name"], (52, 38), self.fonts.hero, (240, 247, 255))
        self.text(self.canvas, spec["title"], (52, 78), self.fonts.xs, spec["color"])
        self.bar(pygame.Rect(52, 108, 350, 15), h.hp/h.max_hp, (84, 235, 150) if h.hp/h.max_hp>.45 else (255, 95, 95))
        self.text(self.canvas, f"VIT {int(h.hp)}/{int(h.max_hp)}", (402, 105), self.fonts.xs, (220, 230, 242), "bottomright")
        resolve_color = (90, 210, 255) if h.resolve > 40 else (255, 150, 90)
        self.bar(pygame.Rect(52, 137, 350, 11), h.resolve/h.max_resolve, resolve_color)
        self.text(self.canvas, f"RESOLVE {int(h.resolve)}", (402, 135), self.fonts.xs, (180, 200, 224), "bottomright")

        r = pygame.Rect(520, 20, 880, 150); self.panel(r, edge=q["color"])
        env = mission.environment
        self.text(self.canvas, f"{env['site']} / {env['site_code']}", (960, 32), self.fonts.xs, env["accent"], "midtop")
        self.text(self.canvas, mission.objective_text(), (960, 66), self.fonts.md, (242, 247, 255), "midtop")
        order_color = mission.order["color"] if mission.order_status == "COMPLYING" else HEROES[h.key]["accent"]
        self.text(self.canvas, f"ORDER / {mission.order['name']} / {mission.order_status}", (550, 110), self.fonts.xs, order_color, "topleft")
        comp_color = mission.complication["color"] if mission.complication_triggered else (110, 126, 150)
        self.text(self.canvas, f"COMPLICATION / {mission.complication['name']}", (550, 137), self.fonts.xs, comp_color, "topleft")
        if mission.aftermath_key != "none":
            self.text(self.canvas, f"AFTERMATH / {mission.aftermath['name']}", (1370, 137), self.fonts.xs, mission.aftermath["color"], "topright")

        r = pygame.Rect(1485, 20, 405, 150); self.panel(r, edge=mission.fit["color"])
        threats = sum(1 for e in mission.enemies if not e.dead and e.overridden <= 0)
        self.text(self.canvas, "THREAT / QUEST FIT", (1510, 38), self.fonts.xs, mission.fit["color"])
        self.text(self.canvas, f"{threats:02d} HOSTILES", (1510, 70), self.fonts.md, (240, 247, 255))
        self.text(self.canvas, f"{mission.fit['rating']}  {mission.fit['percent']}%", (1510, 105), self.fonts.xs, mission.fit["color"])
        self.text(self.canvas, f"KIT / {mission.equipment['name']}", (1510, 126), self.fonts.xs, mission.equipment["color"])
        squad = getattr(mission, "sidekicks", [])
        squad_names = "+".join(HEROES[m.key]["name"] for m in squad) if squad else "SOLO"
        squad_color = HEROES[squad[0].key]["color"] if squad else (110,126,150)
        self.text(self.canvas, f"SQUAD {mission.party_size}/3 / {squad_names}", (1510, 148), self.fonts.xs, squad_color)
        self.text(self.canvas, f"{mission.time:05.1f}s", (1860, 148), self.fonts.xs, (155, 172, 198), "bottomright")

        boss = next((e for e in mission.enemies if getattr(e, "is_boss", False) and not e.dead), None)
        if boss:
            r = pygame.Rect(590, 176, 740, 58)
            pygame.draw.rect(self.canvas, (5, 8, 17), r, border_radius=10)
            pygame.draw.rect(self.canvas, mission.boss_profile["color"], r, 2, border_radius=10)
            self.text(self.canvas, mission.boss_profile["name"], (610, 188), self.fonts.xs, mission.boss_profile["accent"])
            self.bar(pygame.Rect(610, 213, 700, 10), boss.hp/max(1.0,boss.max_hp), mission.boss_profile["color"], back=(28, 14, 25), edge=mission.boss_profile["accent"])
            self.text(self.canvas, mission.boss_phase_note, (1310, 188), self.fonts.xs, mission.boss_profile["accent"], "topright")

        if show_analysis:
            r = pygame.Rect(28, 788, 830, 242); self.panel(r, edge=spec["accent"])
            self.text(self.canvas, "AUTONOMOUS PERSONALITY TRACE", (52, 808), self.fonts.sm, spec["accent"])
            self.text(self.canvas, h.intent, (52, 846), self.fonts.lg, (242, 247, 255))
            self.text(self.canvas, "WHY", (52, 901), self.fonts.xs, spec["color"])
            self.wrap_text(self.canvas, h.reason, pygame.Rect(115, 901, 705, 52), self.fonts.sm, (200, 214, 233), max_lines=2)
            top_scores = "  •  ".join(f"{name} {score:.2f}" for name, score in h.decision_scores[:2])
            self.text(self.canvas, top_scores, (52, 958), self.fonts.xs, (160, 184, 210))
            self.text(self.canvas, f"ORDER {mission.order_status}: {mission.order_reason}", (52, 986), self.fonts.xs, mission.order["color"] if mission.order_status == "COMPLYING" else spec["accent"])
            self.text(self.canvas, f"TARGET {h.target_label}   KILLS {h.kills}   STRESS {int(h.stress)}   ABILITY {max(0,h.ability_timer):.1f}s", (52, 1012), self.fonts.xs, (150, 170, 199))

            r = pygame.Rect(1280, 804, 610, 226); self.panel(r, edge=(68, 105, 138))
            self.text(self.canvas, "MISSION / PERSONALITY FEED", (1304, 826), self.fonts.sm, (144, 191, 229))
            for i, (_, text, color) in enumerate(mission.events[:5]):
                self.text(self.canvas, text, (1306, 868 + i*30), self.fonts.xs, color)

        self.text(self.canvas, "TAB ANALYSIS   •   I ACTOR DOSSIER   •   LMB INSPECT   •   SPACE PAUSE   •   H HELP", (960, 1074), self.fonts.xs, (105, 124, 152), "midbottom")

    def _draw_actor_dossier(self, mission: Mission):
        actor = mission.inspected_actor()
        color = actor["color"]
        rect = pygame.Rect(880, 642, 1010, 398)
        self.panel(rect, fill=(6, 11, 23, 246), edge=color, radius=14)
        self.text(self.canvas, "ACTOR DOSSIER", (905, 662), self.fonts.xs, color)
        self.text(self.canvas, "LMB ACTOR SELECT   •   I CLOSE", (1865, 662), self.fonts.xs, (125, 148, 176), "topright")
        self.text(self.canvas, actor["name"], (905, 690), self.fonts.hero, (242, 248, 255))
        self.text(self.canvas, actor["role"], (905, 731), self.fonts.xs, color)
        condition_line = f"CONDITION / {actor['condition']}    POSE / {actor['pose']}"
        self.text(self.canvas, condition_line, (905, 758), self.fonts.xs, (190, 208, 228))
        field_condition = actor.get("field_condition", "COMBAT READY")
        self.text(self.canvas, f"FIELD / {field_condition}", (905, 784), self.fonts.xs, color if field_condition != "COMBAT READY" else (145, 167, 194))
        hp_ratio = actor["hp"] / max(1.0, actor["max_hp"])
        self.bar(pygame.Rect(905, 812, 665, 12), hp_ratio, color)

        label_x, value_x, value_w = 905, 1036, 522
        rows = [
            ("ORIGIN", actor["origin"], 842, (205, 217, 235)),
            ("BODY", actor["body"], 904, (180, 198, 220)),
            ("BEHAVIOR", actor["behavior"], 966, (180, 198, 220)),
        ]
        for label, value, y, value_color in rows:
            self.text(self.canvas, label, (label_x, y), self.fonts.xs, color)
            self.wrap_text(self.canvas, value, pygame.Rect(value_x, y, value_w, 54), self.fonts.xs, value_color, line_gap=2, max_lines=2)

        if actor["type"] == "hero":
            portrait = self.actors.portrait(mission.hero_key, 132, mission.equipment_key)
            portrait_box = pygame.Rect(1614, 660, 132, 132)
            self.canvas.blit(portrait, portrait.get_rect(center=portrait_box.center))
            pygame.draw.rect(self.canvas, color, portrait_box, 1, border_radius=9)
        side = pygame.Rect(1590, 812, 275, 202)
        pygame.draw.rect(self.canvas, (9, 16, 29), side, border_radius=8)
        pygame.draw.rect(self.canvas, color, side, 1, border_radius=8)
        self.text(self.canvas, "EQUIPMENT / FUNCTION", (1604, 827), self.fonts.xs, color)
        self.wrap_text(self.canvas, actor["weapon"], pygame.Rect(1604, 856, 245, 62), self.fonts.xs, (215, 226, 240), max_lines=3)
        self.text(self.canvas, "KNOWN WEAKNESS", (1604, 924), self.fonts.xs, (255, 118, 142))
        self.wrap_text(self.canvas, actor["weakness"], pygame.Rect(1604, 952, 245, 50), self.fonts.xs, (205, 217, 235), max_lines=2)

    def draw_mission(self, mission: Mission, show_analysis: bool = False, show_dossier: bool = False, paused: bool = False, tutorial_tip: bool = False, pause_index: int = 0, abort_confirm: bool = False):
        self.time = 0.0 if self.reduced_motion else mission.time
        self.current_mission = mission
        self._background(self._visual_env(mission)["fog"])
        self._draw_contract_site(mission)
        self._draw_contract_atmosphere(mission)
        self._draw_civilians(mission)
        for e in mission.enemies:
            self._draw_enemy(e)
        self._draw_projectiles(mission)
        self._draw_hero(mission)
        self._draw_sidekicks(mission)
        self._draw_mission_hud(mission, show_analysis)
        if tutorial_tip and mission.time < 8.0 and mission.status == "ACTIVE" and not show_analysis and not show_dossier:
            tip = pygame.Rect(610, 244, 700, 62)
            pygame.draw.rect(self.canvas, (5, 10, 20), tip, border_radius=10)
            pygame.draw.rect(self.canvas, (255, 218, 108), tip, 2, border_radius=10)
            self.text(self.canvas, "OBSERVE THE HERO / TAB EXPLAINS DECISIONS / SPACE PAUSES", tip.center, self.fonts.xs, (255, 230, 150), "center")
        if mission.complication_triggered and mission.complication_timer > 0 and mission.status == "ACTIVE" and mission.boss_intro_timer <= 0:
            rect = pygame.Rect(610, 242 if mission.boss_spawned and not mission.boss_defeated else 176, 700, 52)
            pygame.draw.rect(self.canvas, (6, 10, 20), rect, border_radius=10)
            pygame.draw.rect(self.canvas, mission.complication["color"], rect, 3, border_radius=10)
            self.text(self.canvas, f"COMPLICATION / {mission.complication['name']}", rect.center, self.fonts.sm, mission.complication["color"], "center")
        if mission.boss_intro_timer > 0 and mission.status == "ACTIVE":
            b = mission.boss_profile
            rect = pygame.Rect(610, 300, 700, 96)
            shade = pygame.Surface(rect.size, pygame.SRCALPHA); shade.fill((4, 6, 14, 228)); self.canvas.blit(shade, rect)
            pygame.draw.rect(self.canvas, b["color"], rect, 3, border_radius=14)
            self.text(self.canvas, "SIGNATURE SOVEREIGN", (960, 311), self.fonts.xs, b["accent"], "midtop")
            self.text(self.canvas, b["name"], (960, 335), self.fonts.lg, (246, 249, 255), "midtop")
            self.text(self.canvas, b["title"], (960, 374), self.fonts.xs, b["color"], "midtop")
        if show_dossier and not show_analysis:
            self._draw_actor_dossier(mission)
        if paused:
            self._draw_mission_pause(pause_index, abort_confirm)
        elif mission.status != "ACTIVE":
            color = (90, 255, 180) if mission.status == "SUCCESS" else (255, 80, 105)
            self._result_overlay(mission, color)

    def _draw_mission_pause(self, selected_index: int = 0, abort_confirm: bool = False):
        shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA); shade.fill((0, 0, 0, 188)); self.canvas.blit(shade, (0, 0))
        panel = pygame.Rect(570, 300, 780, 510)
        self.panel(panel, fill=(7, 12, 25, 252), edge=(92, 226, 255), radius=18)
        self.text(self.canvas, "CONTRACT PAUSED", (960, 340), self.fonts.xl, (232, 247, 255), "midtop")
        self.text(self.canvas, "The mission remains frozen until you resume or deliberately abort.", (960, 412), self.fonts.xs, (165, 188, 214), "midtop")
        labels = ("RESUME CONTRACT", "SETTINGS", "ABORT CONTRACT")
        colors = ((84, 245, 210), (184, 94, 255), (255, 105, 126))
        for i, (label, color) in enumerate(zip(labels, colors)):
            rect = pygame.Rect(700, 452 + i * 86, 520, 64)
            active = i == selected_index % 3
            pygame.draw.rect(self.canvas, (13, 23, 40) if active else (8, 15, 29), rect, border_radius=10)
            pygame.draw.rect(self.canvas, (238, 248, 255) if active else color, rect, 4 if active else 2, border_radius=10)
            shown = "CONFIRM ABORT" if i == 2 and abort_confirm else label
            self.text(self.canvas, ("› " if active else "") + shown, rect.center, self.fonts.sm, (238, 248, 255) if active else color, "center")
        if abort_confirm:
            self.text(self.canvas, "PRESS ENTER / A AGAIN TO ABORT. ESC / B CANCELS.", (960, 724), self.fonts.xs, (255, 174, 188), "midtop")
        else:
            self.text(self.canvas, "↑/↓ SELECT   •   ENTER/A CONFIRM   •   ESC/B RESUME", (960, 724), self.fonts.xs, (150, 174, 202), "midtop")

    def _result_overlay(self, mission: Mission, color):
        shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA); shade.fill((0, 0, 0, 182)); self.canvas.blit(shade, (0, 0))
        r = pygame.Rect(390, 188, 1140, 730); self.panel(r, fill=(7, 12, 25, 250), edge=color, radius=18)
        self.text(self.canvas, "CONTRACT " + mission.status, (960, 234), self.fonts.xl, color, "midtop")
        self.text(self.canvas, mission.environment["site"], (960, 305), self.fonts.xs, mission.environment["accent"], "midtop")
        self.wrap_text(self.canvas, mission.result_reason, pygame.Rect(520, 350, 880, 64), self.fonts.md, (220, 231, 246), max_lines=2)
        self.text(self.canvas, f"QUEST FIT  {mission.fit['rating']} / {mission.fit['percent']}%", (960, 431), self.fonts.sm, mission.fit["color"], "midtop")
        self.text(self.canvas, f"ORDER {mission.order['name']} / {mission.order_status}", (960, 475), self.fonts.xs, mission.order["color"], "midtop")
        self.text(self.canvas, f"COMPLICATION {mission.complication['name']} / {mission.complication_note}", (960, 505), self.fonts.xs, mission.complication["color"], "midtop")
        link_name = mission.support["name"] if mission.support else "NO LINK"
        self.text(self.canvas, f"KIT {mission.equipment['name']}  •  HEX LINK {link_name}", (960, 535), self.fonts.xs, mission.equipment["color"], "midtop")
        boss_color = mission.boss_profile["accent"] if mission.boss_defeated else mission.boss_profile["color"]
        boss_state = "DEFEATED" if mission.boss_defeated else "UNRESOLVED"
        self.text(self.canvas, f"SIGNATURE HOST / {mission.boss_profile['name']} / {boss_state}", (960, 565), self.fonts.xs, boss_color, "midtop")
        consequence_color = (100, 245, 190) if mission.strain_delta < 0 else ((255, 210, 100) if mission.strain_delta < 10 else (255, 105, 120))
        self.text(self.canvas, mission.result_consequence, (960, 610), self.fonts.lg, consequence_color, "midtop")
        eliminated = mission.hero.hp <= 0 and mission.status == "FAILED"
        field_label = "ELIMINATED" if eliminated else mission.hero.field_condition
        self.text(self.canvas, f"FIELD CONDITION / {field_label}", (960, 666), self.fonts.xs, (255, 100, 122) if eliminated else (184, 203, 226), "midtop")
        delta_label = "ROSTER STATUS / ELIMINATED" if eliminated else f"HERO STRAIN {mission.strain_delta:+d}"
        self.text(self.canvas, delta_label, (690, 704), self.fonts.sm, consequence_color, "midtop")
        self.text(self.canvas, f"GUILD PAYOUT  +{mission.reward_credits:,} CR   +{mission.reward_renown} RENOWN", (1230, 704), self.fonts.sm, (255, 218, 108), "midtop")
        reward_note = "  •  ".join(mission.reward_notes[:3])
        self.text(self.canvas, reward_note, (960, 744), self.fonts.xs, (185, 203, 225), "midtop")
        roster_event = getattr(mission, "roster_event", "ROSTER UNCHANGED")
        roster_color = (255, 90, 116) if "ELIMINATED" in roster_event or "LAST HERO" in roster_event else ((255, 220, 110) if "RESTORE" in roster_event else (165, 185, 210))
        self.text(self.canvas, f"ROSTER / {roster_event}", (960, 780), self.fonts.sm, roster_color, "midtop")
        campaign_event = getattr(mission, "campaign_event", "CHAIN POSITION HELD")
        campaign_color = mission.aftermath["color"] if mission.aftermath_key != "none" else mission.environment["accent"]
        self.text(self.canvas, f"CAMPAIGN / {campaign_event}", (960, 820), self.fonts.xs, campaign_color, "midtop")
        next_label = "ENTER ACKNOWLEDGE LAST LIGHT" if "LAST HERO" in roster_event else ("ENTER CHOOSE A HERO TO RESTORE" if "RESTORE" in roster_event else "ENTER CONTINUE")
        self.text(self.canvas, next_label, (960, 878), self.fonts.sm, (180, 198, 225), "midbottom")

    def _overlay(self, title: str, subtitle: str, color=(110, 225, 255)):
        shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA); shade.fill((0, 0, 0, 155)); self.canvas.blit(shade, (0, 0))
        r = pygame.Rect(460, 360, 1000, 350); self.panel(r, fill=(7, 12, 25, 245), edge=color, radius=18)
        self.text(self.canvas, title, (960, 420), self.fonts.xl, color, "midtop")
        self.text(self.canvas, subtitle, (960, 495), self.fonts.md, (220, 231, 246), "midtop")
        self.text(self.canvas, "ENTER RETURN TO CONTRACT BOARD", (960, 640), self.fonts.sm, (145, 166, 195), "midtop")

    def draw_help(self, page: int = 0):
        shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA); shade.fill((0, 0, 0, 205)); self.canvas.blit(shade, (0, 0))
        r = pygame.Rect(320, 150, 1280, 780); self.panel(r, fill=(6, 11, 24, 250), edge=(92, 226, 255), radius=18)
        title = "FIELD GUIDE / CORE FLOW" if page % 2 == 0 else "FIELD GUIDE / GUILD SYSTEMS"
        self.text(self.canvas, title, (960, 195), self.fonts.lg, (232, 247, 255), "midtop")
        self.text(self.canvas, f"PAGE {page % 2 + 1}/2", (1540, 205), self.fonts.xs, (124, 151, 184), "topright")
        if page % 2 == 0:
            left = [
                ("LMB", "Select contracts, heroes, equipment, links, actors, and choices"),
                ("RMB", "Return to the previous screen or close a dossier"),
                ("ENTER", "Prepare, deploy, acknowledge results, or continue meta events"),
                ("O", "Cycle the non-binding guild order"),
                ("E", "Cycle equipment during preparation"),
                ("B", "Cycle an optional remote HEX Link"),
                ("R", "Buy medbay recovery for the selected active hero"),
                ("S", "Open settings from the contract board"),
            ]
            right = [
                ("TAB", "Show live decision reasoning and order compliance"),
                ("I", "Open or close the selected actor dossier"),
                ("SPACE", "Pause or resume an active contract"),
                ("H", "Open or close this guide"),
                ("F11", "Toggle borderless desktop / windowed; native 1920×1080 canvas is unchanged"),
                ("ESC", "Open mission pause/options, go back in menus, or quit from title"),
                ("AUTONOMY", "Heroes navigate, fight, use abilities, and pursue objectives"),
                ("FIRST RUN", "Contextual tips appear only until the first victory"),
            ]
        else:
            left = [
                ("FIT", "Compatibility predicts pressure; it never guarantees success"),
                ("ORDERS", "Orders bias utility; personality and danger may override them"),
                ("KIT", "Equipment changes real stats and appears on the deployed hero"),
                ("HEX LINK", "A second active hero provides remote mechanical support"),
                ("BONDS", "Shared missions build pair history and unlock guild events"),
                ("SOVEREIGN", "Every contract escalates into one signature boss"),
                ("CHAIN", "Complete the highlighted three-contract operation in order"),
                ("AFTERMATH", "Each sovereign leaves a mechanical mark on the next site"),
            ]
            right = [
                ("DEATH", "Zero vitality eliminates that hero from deployment"),
                ("VICTORY", "A win can restore one fallen hero of your choice"),
                ("LAST LIGHT", "A full roster wipe starts a new preserved guild cycle"),
                ("STRAIN", "Persistent injuries alter real hero behavior and capability"),
                ("MEDBAY", "Credits reduce strain but cannot restore eliminated heroes"),
                ("PROFILE", "Saves are atomic, backed up, and recover interrupted writes"),
                ("ACCESS", "High contrast, reduced motion, text size, and volume persist"),
                ("NO COLOR ONLY", "Status also uses names, icons, borders, and explicit labels"),
            ]
        for column, x in ((left, 380), (right, 995)):
            for i, (key, desc) in enumerate(column):
                y = 290 + i * 70
                self.text(self.canvas, key, (x, y), self.fonts.sm, (92, 226, 255) if x < 900 else (184, 94, 255))
                self.wrap_text(self.canvas, desc, pygame.Rect(x + 150, y + 2, 430, 56), self.fonts.xs, (207, 220, 238), max_lines=2)
        self.text(self.canvas, "←/→ CHANGE PAGE   •   H / ESC / ENTER CLOSE", (960, 885), self.fonts.sm, (132, 157, 189), "midtop")

