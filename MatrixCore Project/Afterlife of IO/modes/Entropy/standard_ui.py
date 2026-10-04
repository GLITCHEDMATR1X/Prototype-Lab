from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple
from collections import OrderedDict
import math

import pygame

from hazard_rules import HAZARD_SHORT_RULE

DESIGN_W = 1920
DESIGN_H = 1080
SAFE_X = 48
SAFE_Y = 36
PANEL_BG = (5, 8, 14, 224)
PANEL_BG_SOFT = (8, 12, 20, 190)
BORDER = (96, 214, 232)
BORDER_DIM = (55, 92, 112)
TEXT = (236, 244, 248)
TEXT_DIM = (166, 184, 198)
ACCENT = (112, 244, 238)
DANGER = (255, 116, 110)

_FONT_CACHE = {}
_TEXT_SURFACE_CACHE = OrderedDict()
_PANEL_FILL_CACHE = OrderedDict()
_EDGE_PRESSURE_CACHE = {}


# Afterlife of IO hosts Entropy in-process; its exit returns to the Afterlife
# title instead of the desktop, so the host swaps these labels at launch.
EXIT_LABEL = "EXIT GAME"
FINISH_EXIT_LABEL = "RETURN TO TITLE / EXIT"


def _cached_text(value: str, size=24, color=TEXT, bold=False):
    key = (str(value), int(size), tuple(color), bool(bold))
    rendered = _TEXT_SURFACE_CACHE.get(key)
    if rendered is None:
        rendered = font(size, bold).render(str(value), True, color)
        _TEXT_SURFACE_CACHE[key] = rendered
        _TEXT_SURFACE_CACHE.move_to_end(key)
        while len(_TEXT_SURFACE_CACHE) > 256:
            _TEXT_SURFACE_CACHE.popitem(last=False)
    else:
        _TEXT_SURFACE_CACHE.move_to_end(key)
    return rendered


def _cached_panel_fill(size, bg):
    key = (int(size[0]), int(size[1]), tuple(bg))
    surface = _PANEL_FILL_CACHE.get(key)
    if surface is None:
        surface = pygame.Surface((key[0], key[1]), pygame.SRCALPHA)
        surface.fill(bg)
        _PANEL_FILL_CACHE[key] = surface
        _PANEL_FILL_CACHE.move_to_end(key)
        while len(_PANEL_FILL_CACHE) > 48:
            _PANEL_FILL_CACHE.popitem(last=False)
    else:
        _PANEL_FILL_CACHE.move_to_end(key)
    return surface


def font(size: int, bold: bool = False):
    key = (int(size), bool(bold))
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = pygame.font.SysFont("consolas", int(size), bold=bold)
    return _FONT_CACHE[key]


def fit_window_16_9(desktop_w: int, desktop_h: int, target_w: int = 1920, target_h: int = 1080) -> Tuple[int, int]:
    """Return an exact Full-HD window when the desktop supports it.

    Smaller displays retain a 16:9 fallback. Native 1080p mode itself is
    borderless, so a 1920x1080 desktop does not lose pixels to title-bar chrome.
    """
    if int(desktop_w) >= int(target_w) and int(desktop_h) >= int(target_h):
        return int(target_w), int(target_h)
    max_w = max(960, int(desktop_w * 0.96))
    max_h = max(540, int(desktop_h * 0.92))
    scale = min(1.0, max_w / float(target_w), max_h / float(target_h))
    w = max(960, int(target_w * scale))
    h = max(540, int(target_h * scale))
    h = min(max_h, int(w * 9 / 16))
    w = int(h * 16 / 9)
    return max(960, w), max(540, h)


def window_to_virtual(pos, display_size, virtual_size=(DESIGN_W, DESIGN_H)):
    px, py = float(pos[0]), float(pos[1])
    dw, dh = float(display_size[0]), float(display_size[1])
    vw, vh = float(virtual_size[0]), float(virtual_size[1])
    if dw <= 0 or dh <= 0:
        return (-1, -1)
    scale = min(dw / vw, dh / vh)
    if scale <= 0:
        return (-1, -1)
    tw, th = vw * scale, vh * scale
    ox, oy = (dw - tw) * 0.5, (dh - th) * 0.5
    vx, vy = (px - ox) / scale, (py - oy) / scale
    if vx < 0 or vy < 0 or vx >= vw or vy >= vh:
        return (-1, -1)
    return (int(vx), int(vy))


def _panel(screen, rect, bg=PANEL_BG, border=BORDER_DIM, radius=10):
    surface = _cached_panel_fill((rect.w, rect.h), bg)
    screen.blit(surface, rect.topleft)
    pygame.draw.rect(screen, border, rect, 2, border_radius=radius)


def _text(screen, value: str, pos, size=24, color=TEXT, bold=False):
    rendered = _cached_text(str(value), size, color, bold)
    screen.blit(rendered, pos)
    return rendered


def draw_bottom_hint(screen, text: str, right_text: str = "F1 CONTROLS  •  ` PAUSE"):
    w, h = screen.get_size()
    left = _cached_text(text, 20, TEXT_DIM, False)
    right = _cached_text(right_text, 20, TEXT_DIM, False)
    panel_h = 42
    rect = pygame.Rect(SAFE_X, h - SAFE_Y - panel_h, w - SAFE_X * 2, panel_h)
    surface = _cached_panel_fill((rect.w, rect.h), PANEL_BG_SOFT)
    screen.blit(surface, rect.topleft)
    pygame.draw.line(screen, BORDER_DIM, (rect.left, rect.top), (rect.right, rect.top), 1)
    screen.blit(left, (rect.left + 14, rect.top + 10))
    screen.blit(right, (rect.right - right.get_width() - 14, rect.top + 10))


def draw_mode_chip(screen, mode_name: str):
    label = _cached_text(mode_name.upper(), 20, ACCENT, True)
    rect = pygame.Rect(screen.get_width() - SAFE_X - label.get_width() - 30, SAFE_Y, label.get_width() + 30, 38)
    _panel(screen, rect, bg=PANEL_BG_SOFT, border=BORDER_DIM, radius=8)
    screen.blit(label, (rect.left + 15, rect.top + 8))


def draw_collapse_pressure(screen, state: str, intensity: float, tsec: float):
    """Subtle edge pressure that never covers the central play field."""
    state = str(state).upper()
    if state not in ("UNSTABLE", "CRITICAL", "SUPERNOVA", "BLACK HOLE"):
        return
    intensity = max(0.0, min(1.0, float(intensity)))
    pulse = 0.55 + 0.45 * math.sin(float(tsec) * (2.0 if state == "UNSTABLE" else 4.2))
    alpha = int((12 + 38 * intensity) * pulse)
    if state in ("SUPERNOVA", "BLACK HOLE"):
        alpha = max(alpha, 34)
    w, h = screen.get_size()
    band = 18 if state == "UNSTABLE" else 28
    key = (int(w), int(h), int(band))
    edge = _EDGE_PRESSURE_CACHE.get(key)
    if edge is None:
        edge = pygame.Surface((w, h), pygame.SRCALPHA)
        edge.fill((0, 0, 0, 0))
        col = (255, 72, 58, 255)
        pygame.draw.rect(edge, col, (0, 0, w, band))
        pygame.draw.rect(edge, col, (0, h - band, w, band))
        pygame.draw.rect(edge, col, (0, 0, band, h))
        pygame.draw.rect(edge, col, (w - band, 0, band, h))
        _EDGE_PRESSURE_CACHE[key] = edge
    edge.set_alpha(alpha)
    screen.blit(edge, (0, 0))


def draw_collapse_panel(screen, state: str, remaining: float, timer_name: str, hull_hp: int, hull_max: int):
    """Compact top-center collapse + hull instrument shared by every mode."""
    w, _h = screen.get_size()
    rect = pygame.Rect(w // 2 + 20, SAFE_Y, 430, 76)
    state = str(state).upper()
    urgent = state in ("CRITICAL", "SUPERNOVA", "BLACK HOLE")
    _panel(screen, rect, bg=PANEL_BG_SOFT, border=DANGER if urgent else BORDER_DIM, radius=8)
    seconds = max(0, int(float(remaining)))
    timer = f"{seconds // 60:02d}:{seconds % 60:02d}"
    _text(screen, str(timer_name).upper(), (rect.left + 16, rect.top + 10), 15, DANGER if urgent else ACCENT, True)
    _text(screen, timer, (rect.left + 162, rect.top + 6), 28, TEXT, True)
    _text(screen, state, (rect.right - font(17, True).size(state)[0] - 16, rect.top + 13), 17, DANGER if urgent else TEXT_DIM, True)
    bar = pygame.Rect(rect.left + 16, rect.bottom - 22, rect.w - 32, 8)
    pygame.draw.rect(screen, (22, 31, 41), bar)
    ratio = max(0.0, min(1.0, float(hull_hp) / max(1.0, float(hull_max))))
    fill = pygame.Rect(bar.left, bar.top, int(bar.w * ratio), bar.h)
    hull_col = ACCENT if ratio > 0.50 else ((245, 184, 92) if ratio > 0.25 else DANGER)
    pygame.draw.rect(screen, hull_col, fill)
    _text(screen, f"HULL {max(0, int(hull_hp)):03d}/{max(1, int(hull_max)):03d}", (bar.left, bar.top - 19), 14, TEXT_DIM, True)


def draw_collapse_banner(screen, message: str):
    if not message:
        return
    w, h = screen.get_size()
    text = font(22, True).render(str(message).upper(), True, TEXT)
    rect = pygame.Rect(w // 2 - min(650, text.get_width() // 2 + 46), int(h * 0.15), min(1300, text.get_width() + 92), 62)
    _panel(screen, rect, bg=(35, 8, 10, 232), border=DANGER, radius=8)
    screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))


def draw_failure_screen(screen, reason: str, system_index: int, fragments: int, hull_max: int, controller: bool = False) -> Dict[str, pygame.Rect]:
    """Terminal failure state with explicit recovery and exit choices."""
    w, h = screen.get_size()
    dim = pygame.Surface((w, h), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 220))
    screen.blit(dim, (0, 0))
    panel = pygame.Rect(w // 2 - 500, h // 2 - 300, 1000, 600)
    _panel(screen, panel, bg=(6, 5, 9, 250), border=DANGER, radius=16)
    _text(screen, "EXPEDITION LOST", (panel.left + 56, panel.top + 46), 52, DANGER, True)
    _text(screen, str(reason).upper(), (panel.left + 60, panel.top + 126), 25, TEXT, True)
    _text(screen, f"SYSTEM REACHED  {max(1, int(system_index)):02d}", (panel.left + 60, panel.top + 194), 20, TEXT_DIM, True)
    _text(screen, f"DATA FRAGMENTS RECOVERED  {max(0, int(fragments))}/6", (panel.left + 60, panel.top + 230), 20, TEXT_DIM, True)
    _text(screen, f"CHECKPOINT HULL CAPACITY  {max(1, int(hull_max))}", (panel.left + 60, panel.top + 266), 20, TEXT_DIM, True)
    _text(screen, "RETRY restores the current system-entry checkpoint.", (panel.left + 60, panel.top + 322), 18, ACCENT)
    _text(screen, "Current-system pickups, spending, and data progress are discarded.", (panel.left + 60, panel.top + 352), 17, TEXT_DIM)
    _text(screen, "Earlier-system advancement remains.", (panel.left + 60, panel.top + 380), 17, TEXT_DIM)
    retry = pygame.Rect(panel.left + 60, panel.bottom - 130, 410, 68)
    quit_rect = pygame.Rect(panel.right - 470, panel.bottom - 130, 410, 68)
    _panel(screen, retry, bg=(10, 28, 32, 242), border=BORDER, radius=9)
    _panel(screen, quit_rect, bg=(34, 16, 20, 242), border=(128, 62, 68), radius=9)
    _text(screen, "RETRY SYSTEM", (retry.left + 28, retry.top + 19), 23, TEXT, True)
    retry_key = "A" if controller else "R / ENTER"
    _text(screen, retry_key, (retry.right - font(16, True).size(retry_key)[0] - 24, retry.top + 23), 16, TEXT_DIM, True)
    _text(screen, EXIT_LABEL, (quit_rect.left + 28, quit_rect.top + 19), 23, DANGER, True)
    quit_key = "B" if controller else "Q"
    _text(screen, quit_key, (quit_rect.right - font(16, True).size(quit_key)[0] - 24, quit_rect.top + 23), 16, TEXT_DIM, True)
    return {"retry": retry, "quit": quit_rect}


def draw_controls_overlay(screen, context: str = "space", controller: bool = False):
    w, h = screen.get_size()
    context = str(context).lower()
    keyboard_controls: Dict[str, Sequence[Tuple[str, str]]] = {
        "space": (
            ("MOUSE", "yaw / pitch"), ("Q / E", "roll"), ("W / S", "forward / reverse"),
            ("A / D", "strafe"), ("SPACE / CTRL", "vertical thrust"), ("SHIFT", "boost"),
            ("X", "brake"), ("C", "inertial dampers"), ("F", "warp"),
            ("M", "mission brief"), ("V", "cockpit / third-person"), ("TAB", "ship interior"),
            ("`", "pause / resume"), ("F11", "fullscreen toggle"),
        ),
        "surface": (
            ("WASD", "screen-relative walk / turn"),
            ("E", "recover / process ruins and objects"), ("TAB", "ship interior near beacon"),
            ("SPACE", "return to orbit"), ("M", "mission brief"),
            ("`", "pause / resume"), ("F11", "fullscreen toggle"),
        ),
        "ruin": (
            ("WASD", "move"), ("MOUSE", "look"),
            ("E", "legacy exit only"), ("X", "leave ruin"),
            ("M", "mission brief"), ("`", "pause / resume"), ("F11", "fullscreen toggle"),
        ),
        "interior": (
            ("WASD / ARROWS", "move / select upgrade"), ("E / ENTER", "use station / install"),
            ("TAB", "return to previous view"),
            ("SPACE", "take off / return to space"), ("M", "mission brief"),
            ("`", "pause / resume"), ("F11", "fullscreen toggle"),
        ),
    }
    controller_controls: Dict[str, Sequence[Tuple[str, str]]] = {
        "space": (
            ("RIGHT STICK", "yaw / pitch"), ("LB / RB", "roll"), ("LEFT STICK", "forward / reverse + strafe"),
            ("LT / RT", "vertical thrust"), ("A", "boost"), ("B", "brake"),
            ("DPAD RIGHT", "warp"), ("DPAD LEFT", "inertial dampers"),
            ("Y", "cockpit / third-person"), ("X", "ship interior"),
            ("VIEW", "mission brief"), ("MENU", "pause / resume"),
        ),
        "surface": (
            ("LEFT STICK / DPAD", "walk / turn"), ("A", "recover / process"),
            ("X", "ship interior near beacon"), ("B", "return to orbit"),
            ("Y / VIEW", "mission brief"), ("MENU", "pause / resume"),
        ),
        "ruin": (
            ("LEFT STICK / DPAD", "move"), ("RIGHT STICK", "look"),
            ("A", "interact"), ("B", "leave ruin"),
            ("Y / VIEW", "mission brief"), ("MENU", "pause / resume"),
        ),
        "interior": (
            ("LEFT STICK / DPAD", "move / select upgrade"), ("A", "use station / install"),
            ("B", "return / close fabricator"), ("X", "take off / return to space"),
            ("Y / VIEW", "mission brief"), ("MENU", "pause / resume"),
        ),
    }
    controls = controller_controls if controller else keyboard_controls
    items = controls.get(context, controls["space"])
    rect = pygame.Rect(w - SAFE_X - 590, SAFE_Y + 132, 590, min(650, 112 + len(items) * 34))
    _panel(screen, rect, bg=PANEL_BG, border=BORDER, radius=12)
    _text(screen, "CONTROLS", (rect.left + 26, rect.top + 22), 30, ACCENT, True)
    mode = "CONTROLLER" if controller else context.upper()
    _text(screen, mode, (rect.right - 26 - font(18, True).size(mode)[0], rect.top + 28), 18, TEXT_DIM, True)
    y = rect.top + 74
    for key, action in items:
        key_img = font(20, True).render(key, True, TEXT)
        action_img = font(20).render(action, True, TEXT_DIM)
        screen.blit(key_img, (rect.left + 28, y))
        screen.blit(action_img, (rect.left + 220, y))
        y += 34
    close_hint = "VIEW closes this panel" if controller else "F1 closes this panel"
    _text(screen, close_hint, (rect.left + 28, rect.bottom - 38), 18, TEXT_DIM)

def draw_pause_menu(screen, context: str, hud_visible: bool, controls_visible: bool,
                    selected_index: int = 0, controller: bool = False, status_text: str = "") -> Dict[str, pygame.Rect]:
    w, h = screen.get_size()
    dim = pygame.Surface((w, h), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 150))
    screen.blit(dim, (0, 0))

    menu = pygame.Rect(w // 2 - 320, h // 2 - 350, 640, 700)
    _panel(screen, menu, bg=(4, 7, 12, 242), border=BORDER, radius=14)
    _text(screen, "ENTROPY", (menu.left + 40, menu.top + 34), 46, TEXT, True)
    _text(screen, "PAUSED", (menu.left + 42, menu.top + 92), 22, ACCENT, True)
    _text(screen, f"CURRENT VIEW  /  {context.upper()}", (menu.left + 42, menu.top + 130), 18, TEXT_DIM)
    if status_text:
        _text(screen, str(status_text).upper(), (menu.left + 42, menu.top + 158), 15, DANGER, True)

    if controller:
        labels = [
            ("resume", "RESUME", "A / B"),
            ("settings", "SETTINGS", "A"),
            ("controls", "CONTROLS", "VIEW"),
            ("hud", f"HUD  {'ON' if hud_visible else 'OFF'}", "A"),
            ("quit", EXIT_LABEL, "A"),
        ]
    else:
        labels = [
            ("resume", "RESUME", "` / ENTER"),
            ("settings", "SETTINGS", "S"),
            ("controls", "CONTROLS", "F1"),
            ("hud", f"HUD  {'ON' if hud_visible else 'OFF'}", "H"),
            ("quit", EXIT_LABEL, "Q"),
        ]
    buttons: Dict[str, pygame.Rect] = {}
    y = menu.top + 190
    for index, (name, label, key) in enumerate(labels):
        rect = pygame.Rect(menu.left + 42, y, menu.w - 84, 72)
        selected = int(selected_index) == index
        bg = (20, 36, 50, 242) if selected else ((13, 20, 31, 232) if name != "quit" else (34, 16, 20, 232))
        border = BORDER if selected else (BORDER_DIM if name != "quit" else (128, 62, 68))
        _panel(screen, rect, bg=bg, border=border, radius=8)
        _text(screen, label, (rect.left + 24, rect.top + 19), 24, DANGER if name == "quit" else TEXT, True)
        key_img = font(17, True).render(key, True, ACCENT if selected else TEXT_DIM)
        screen.blit(key_img, (rect.right - key_img.get_width() - 22, rect.top + 25))
        buttons[name] = rect
        y += 86

    if controller:
        _text(screen, "DPAD / LEFT STICK SELECT   •   A CONFIRM   •   B RESUME", (menu.left + 42, menu.bottom - 42), 15, TEXT_DIM)
    if controls_visible:
        draw_controls_overlay(screen, context, controller=controller)
    return buttons

def draw_settings_menu(screen, settings: dict, active_window_mode: str, selected_row: int = 0, controller: bool = False) -> Dict[str, pygame.Rect]:
    """Draw the pause-safe display/audio settings panel and return click targets."""
    w, h = screen.get_size()
    dim = pygame.Surface((w, h), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 168))
    screen.blit(dim, (0, 0))

    panel = pygame.Rect(w // 2 - 500, h // 2 - 410, 1000, 820)
    _panel(screen, panel, bg=(4, 7, 12, 248), border=BORDER, radius=14)
    _text(screen, "SETTINGS", (panel.left + 46, panel.top + 32), 42, TEXT, True)
    _text(screen, "DISPLAY + AUDIO", (panel.left + 48, panel.top + 88), 20, ACCENT, True)
    settings_hint = ("DPAD / LEFT STICK SELECT   •   LEFT / RIGHT ADJUST   •   B BACK   •   MENU RESUME"
                     if controller else "UP / DOWN SELECT   •   LEFT / RIGHT ADJUST   •   ESC BACK   •   ` RESUME")
    _text(screen, settings_hint, (panel.left + 48, panel.top + 122), 16, TEXT_DIM)

    mode_labels = {
        "bordered": "BORDERED WINDOW",
        "native_1080p": "BORDERLESS 1920 × 1080",
        "fullscreen": "FULLSCREEN DESKTOP (SAFE)",
    }
    rows = [
        ("display", "DISPLAY MODE", mode_labels.get(active_window_mode, active_window_mode.upper())),
        ("size", "BORDERED SIZE", f"{int(settings.get('bordered_width', 1600))} × {int(settings.get('bordered_height', 900))}"),
        ("master", "MASTER VOLUME", f"{round(float(settings.get('master_volume', 1.0)) * 100):.0f}%"),
        ("music", "MUSIC", f"{round(float(settings.get('music_volume', 0.85)) * 100):.0f}%"),
        ("sfx", "SHIP + EFFECTS", f"{round(float(settings.get('sfx_volume', 0.95)) * 100):.0f}%"),
        ("ambience", "WORLD AMBIENCE", f"{round(float(settings.get('ambience_volume', 0.80)) * 100):.0f}%"),
        ("mute", "MUTE ALL AUDIO", "ON" if settings.get("audio_muted", False) else "OFF"),
    ]

    buttons: Dict[str, pygame.Rect] = {}
    y = panel.top + 170
    for index, (name, label, value) in enumerate(rows):
        row = pygame.Rect(panel.left + 48, y, panel.w - 96, 70)
        selected = index == int(selected_row)
        bg = (17, 29, 42, 242) if selected else (11, 18, 28, 226)
        border = BORDER if selected else BORDER_DIM
        _panel(screen, row, bg=bg, border=border, radius=8)
        _text(screen, label, (row.left + 22, row.top + 22), 20, TEXT if selected else TEXT_DIM, True)
        value_img = font(20, True).render(value, True, ACCENT if selected else TEXT)
        screen.blit(value_img, (row.right - value_img.get_width() - 72, row.top + 22))
        if name != "mute":
            left_rect = pygame.Rect(row.right - 54, row.top + 10, 38, 50)
            right_rect = pygame.Rect(row.right - 12, row.top + 10, 38, 50)
            # Keep arrows visually inside the panel while retaining generous hit boxes.
            left_rect.right = row.right - 18
            right_rect.left = row.right + 2
            # Separate compact arrows live at the value edges.
            left_rect = pygame.Rect(row.right - value_img.get_width() - 124, row.top + 12, 42, 46)
            right_rect = pygame.Rect(row.right - 58, row.top + 12, 42, 46)
            _panel(screen, left_rect, bg=(9, 15, 24, 238), border=BORDER_DIM, radius=6)
            _panel(screen, right_rect, bg=(9, 15, 24, 238), border=BORDER_DIM, radius=6)
            _text(screen, "‹", (left_rect.left + 13, left_rect.top + 7), 26, TEXT, True)
            _text(screen, "›", (right_rect.left + 13, right_rect.top + 7), 26, TEXT, True)
            buttons[f"{name}_prev"] = left_rect
            buttons[f"{name}_next"] = right_rect
        else:
            buttons["mute"] = row
        buttons[f"row_{index}"] = row
        y += 78

    back = pygame.Rect(panel.left + 48, panel.bottom - 70, 190, 44)
    _panel(screen, back, bg=(12, 20, 31, 238), border=BORDER_DIM, radius=7)
    _text(screen, "BACK", (back.left + 60, back.top + 10), 20, TEXT, True)
    buttons["back"] = back
    return buttons


def draw_mission_tracker(screen, title: str, detail: str, collapse_state: str = "STABLE", show_hint: bool = True):
    """Compact objective strip that stays inside the Full-HD safe frame."""
    w, _h = screen.get_size()
    rect = pygame.Rect(SAFE_X, SAFE_Y, min(920, w - SAFE_X * 2 - 260), 76)
    state = str(collapse_state).upper()
    alert = state in ("CRITICAL", "SUPERNOVA", "BLACK HOLE")
    border = DANGER if alert else BORDER_DIM
    _panel(screen, rect, bg=PANEL_BG_SOFT, border=border, radius=8)
    _text(screen, "MISSION", (rect.left + 16, rect.top + 11), 16, DANGER if alert else ACCENT, True)
    _text(screen, str(title).upper(), (rect.left + 112, rect.top + 8), 22, TEXT, True)
    detail_img = _cached_text(str(detail).upper(), 17, TEXT_DIM, False)
    max_detail_w = rect.w - 34
    if detail_img.get_width() > max_detail_w:
        # Keep objective guidance inside the safe frame without shrinking the HUD.
        text = str(detail).upper()
        while len(text) > 8 and font(17).size(text + "…")[0] > max_detail_w:
            text = text[:-1]
        detail_img = _cached_text(text.rstrip() + "…", 17, TEXT_DIM, False)
    screen.blit(detail_img, (rect.left + 16, rect.top + 43))
    if show_hint:
        hint = _cached_text("M BRIEF", 15, TEXT_DIM, True)
        screen.blit(hint, (rect.right - hint.get_width() - 14, rect.top + 12))


def draw_mission_brief(screen, mission, context: str = "space", target_distance=None, controller: bool = False):
    """Toggleable mission/signals panel; intentionally modal only when requested."""
    w, h = screen.get_size()
    dim = pygame.Surface((w, h), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 112))
    screen.blit(dim, (0, 0))

    rect = pygame.Rect(w // 2 - 480, h // 2 - 330, 960, 660)
    _panel(screen, rect, bg=(4, 7, 12, 244), border=BORDER, radius=14)
    _text(screen, "MISSION BRIEF", (rect.left + 42, rect.top + 34), 38, TEXT, True)
    _text(screen, f"SYSTEM {mission.system_index:02d}  /  {mission.collapse_state}", (rect.left + 44, rect.top + 86), 20, ACCENT, True)

    _text(screen, mission.objective_title(context), (rect.left + 44, rect.top + 138), 28, TEXT, True)
    _text(screen, mission.objective_detail(context, target_distance), (rect.left + 44, rect.top + 180), 19, TEXT_DIM)
    target = getattr(mission, "target_signal", None)
    goal_outcome = str(getattr(mission, "system_goal_outcome", "active"))
    if target is None and goal_outcome == "missed":
        _text(screen, "TARGET LOST  /  HYPERDRIVE AVAILABLE", (rect.left + 44, rect.top + 214), 17, ACCENT, True)
    elif target is None and goal_outcome == "carrying":
        _text(screen, "TARGET LOST  /  DATA IN FIELD CUSTODY", (rect.left + 44, rect.top + 214), 17, ACCENT, True)
    else:
        family = str(getattr(target, "hazard_family", "UNKNOWN") if target is not None else "UNKNOWN").upper()
        hazard_rule = HAZARD_SHORT_RULE.get(family, HAZARD_SHORT_RULE["UNKNOWN"])
        _text(screen, f"HAZARD {family}  /  {hazard_rule}", (rect.left + 44, rect.top + 214), 17, TEXT_DIM, True)

    _text(screen, "SYSTEM WORLD", (rect.left + 44, rect.top + 258), 20, ACCENT, True)
    y = rect.top + 298
    for row in mission.signal_summary():
        role_col = ACCENT if "MATRIX" in row else TEXT_DIM
        _text(screen, row, (rect.left + 52, y), 19, role_col, "MATRIX" in row)
        y += 34

    close_key = "Y / VIEW CLOSE" if controller else "M CLOSE"
    if bool(getattr(mission, "is_home_phase", False)):
        footer = f"{close_key}  •  RECOVER THE EMERGENCY CACHE  •  SUPERNOVA EVACUATES HOME"
    elif bool(getattr(mission, "is_ship_recovery_phase", False)):
        footer = f"{close_key}  •  RESTORE SHIP SYSTEMS IN ORDER  •  COCKPIT STARTS THE EXPEDITION"
    elif bool(getattr(mission, "is_delivery_phase", False)):
        footer = f"{close_key}  •  RETURN TO THE COCKPIT  •  DELIVER THE ARCHIVE TO GLEEBS"
    elif str(getattr(mission, "system_goal_outcome", "active")) == "missed":
        footer = f"{close_key}  •  TARGET WORLD LOST  •  HYPERDRIVE AVAILABLE / DATA RETURNS NEXT SYSTEM"
    elif str(getattr(mission, "system_goal_outcome", "active")) == "carrying":
        footer = f"{close_key}  •  TARGET WORLD LOST  •  SECURE CARRIED DATA IN SHIP STORAGE"
    elif getattr(mission, "fragment_deposited", False):
        footer = f"{close_key}  •  DATA SECURED  •  RETURN TO SHIP / REFUEL / DEPART WHEN READY"
    else:
        footer = f"{close_key}  •  LAND ON THE MARKED WORLD  •  RECOVER THE DATA FRAGMENT"
    footer_img = font(18, True).render(footer, True, TEXT_DIM)
    screen.blit(footer_img, (rect.centerx - footer_img.get_width() // 2, rect.bottom - 54))



def draw_campaign_complete_screen(screen, system_index: int, fragments: int, required: int = 6, controller: bool = False) -> Dict[str, pygame.Rect]:
    """Final non-overlapping campaign handoff to Gleebs / MatrixCore."""
    w, h = screen.get_size()
    dim = pygame.Surface((w, h), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 228))
    screen.blit(dim, (0, 0))
    panel = pygame.Rect(w // 2 - 560, h // 2 - 330, 1120, 660)
    _panel(screen, panel, bg=(4, 7, 12, 252), border=BORDER, radius=16)
    _text(screen, "DATA TRANSFER COMPLETE", (panel.left + 58, panel.top + 48), 48, ACCENT, True)
    _text(screen, "RECIPIENT  /  GLEEBS", (panel.left + 62, panel.top + 118), 26, TEXT, True)
    _text(screen, "MATRIXCORE LINK ACCEPTED", (panel.left + 62, panel.top + 160), 20, TEXT_DIM, True)
    archive = pygame.Rect(panel.left + 58, panel.top + 224, panel.w - 116, 164)
    _panel(screen, archive, bg=(9, 17, 26, 238), border=BORDER_DIM, radius=10)
    _text(screen, "EXPEDITION ARCHIVE", (archive.left + 28, archive.top + 22), 19, ACCENT, True)
    _text(screen, f"DATA FRAGMENTS  {max(0, int(fragments))}/{max(1, int(required))}", (archive.left + 28, archive.top + 58), 30, TEXT, True)
    _text(screen, f"SYSTEMS REACHED  {max(1, int(system_index)):02d}", (archive.left + 28, archive.top + 104), 21, TEXT_DIM, True)
    _text(screen, "The abandoned-world archive now survives outside the collapsing systems.", (panel.left + 62, panel.top + 430), 19, TEXT_DIM)
    _text(screen, "ENTROPY expedition complete.", (panel.left + 62, panel.top + 466), 21, TEXT, True)
    quit_rect = pygame.Rect(panel.centerx - 210, panel.bottom - 112, 420, 64)
    _panel(screen, quit_rect, bg=(10, 28, 32, 242), border=BORDER, radius=9)
    _text(screen, FINISH_EXIT_LABEL, (quit_rect.left + 54, quit_rect.top + 18), 22, TEXT, True)
    exit_key = "A / B" if controller else "ENTER / ESC"
    key_img = font(15, True).render(exit_key, True, TEXT_DIM)
    screen.blit(key_img, (quit_rect.right - key_img.get_width() - 22, quit_rect.top + 24))
    return {"quit": quit_rect}

def draw_run_start_screen(screen, mission, controller: bool = False):
    """One-page run start that teaches the locked loop without menu sprawl."""
    w, h = screen.get_size()
    dim = pygame.Surface((w, h), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 205))
    screen.blit(dim, (0, 0))

    panel = pygame.Rect(w // 2 - 610, h // 2 - 410, 1220, 820)
    _panel(screen, panel, bg=(3, 6, 11, 250), border=BORDER, radius=16)

    _text(screen, "ENTROPY", (panel.left + 58, panel.top + 48), 62, TEXT, True)
    _text(screen, "HOME — LAST MINUTE", (panel.left + 62, panel.top + 124), 24, ACCENT, True)
    _text(screen, f"SYSTEM {mission.system_index:02d}  •  {mission.system_planet_count} WORLD  •  STAR COLLAPSE ACTIVE", (panel.left + 62, panel.top + 176), 20, TEXT_DIM)

    target = mission.target_signal
    target_label = target.planet_label if target else "NO TARGET"
    hazard = target.hazard_family if target else "UNKNOWN"
    objective_rect = pygame.Rect(panel.left + 58, panel.top + 224, panel.w - 116, 128)
    _panel(screen, objective_rect, bg=(10, 17, 26, 238), border=BORDER_DIM, radius=10)
    _text(screen, "PRIMARY OBJECTIVE", (objective_rect.left + 26, objective_rect.top + 20), 18, ACCENT, True)
    _text(screen, "RECOVER EMERGENCY SUPPLIES", (objective_rect.left + 26, objective_rect.top + 52), 30, TEXT, True)
    _text(screen, f"TARGET  {target_label}  •  {hazard} HAZARD", (objective_rect.left + 26, objective_rect.top + 92), 19, TEXT_DIM, True)

    steps = (
        ("01", "MOVE", "You begin on HOME. The collapse timer is already running."),
        ("02", "SCAVENGE", "Recover the emergency cache before the star erupts."),
        ("03", "SURVIVE", "The first supernova triggers the emergency transfer."),
        ("04", "RESTORE", "Wake aboard the ship and reactivate its systems."),
        ("05", "EXPEDITION", "Recover six Data Fragments and deliver them to Gleebs."),
    )
    y = panel.top + 392
    for number, title, body in steps:
        _text(screen, number, (panel.left + 70, y), 18, ACCENT, True)
        _text(screen, title, (panel.left + 126, y - 2), 22, TEXT, True)
        _text(screen, body, (panel.left + 300, y), 18, TEXT_DIM)
        y += 58

    start_label = "A  —  BEGIN ON HOME" if controller else "ENTER / SPACE  —  BEGIN ON HOME"
    start = font(25, True).render(start_label, True, ACCENT)
    screen.blit(start, (panel.centerx - start.get_width() // 2, panel.bottom - 84))
    quit_hint = font(16).render("B exits before launch" if controller else "ESC exits before launch", True, TEXT_DIM)
    screen.blit(quit_hint, (panel.centerx - quit_hint.get_width() // 2, panel.bottom - 44))
