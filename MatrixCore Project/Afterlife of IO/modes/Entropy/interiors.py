from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import pygame

from gamepad_input import get_active_gamepad

from ship_progression import (
    MAX_UPGRADE_LEVEL, UPGRADE_LABELS, UPGRADE_ORDER,
    add_resource, ensure_progression, next_upgrade_cost, process_fuel_cells, purchase_upgrade,
    repair_hull, resource_amount, upgrade_effect,
)


_FONT_CACHE = {}


def _font(size: int, bold: bool = False):
    key = (int(size), bool(bold))
    cached = _FONT_CACHE.get(key)
    if cached is None:
        cached = pygame.font.SysFont('consolas', int(size), bold=bool(bold))
        _FONT_CACHE[key] = cached
    return cached


def _base_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _safe_load_image(path: str) -> Optional[pygame.Surface]:
    try:
        return pygame.image.load(path).convert_alpha()
    except Exception:
        return None


def _is_image(path: str) -> bool:
    p = path.lower()
    return p.endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp"))


def _find_interior_image() -> Optional[str]:
    base = _base_dir()
    candidates: List[str] = []
    preferred_dirs = [
        os.path.join(base, "assets", "ui", "interior"),
        os.path.join(base, "assets", "ui", "ship_interior"),
        os.path.join(base, "assets", "interior"),
    ]
    for d in preferred_dirs:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            p = os.path.join(d, fn)
            if os.path.isfile(p) and _is_image(p):
                candidates.append(p)
    if candidates:
        return candidates[0]

    assets_root = os.path.join(base, "assets")
    if os.path.isdir(assets_root):
        for root, _dirs, files in os.walk(assets_root):
            for fn in files:
                if "interior" in fn.lower():
                    p = os.path.join(root, fn)
                    if os.path.isfile(p) and _is_image(p):
                        candidates.append(p)
    return sorted(candidates)[0] if candidates else None


ASSETS_DIR = os.path.join(_base_dir(), "assets")
PLAYER_DIR = os.path.join(ASSETS_DIR, "player")
PLAYER_DIRS = {
    "down": os.path.join(PLAYER_DIR, "down"),
    "up": os.path.join(PLAYER_DIR, "up"),
    "left": os.path.join(PLAYER_DIR, "left"),
    "right": os.path.join(PLAYER_DIR, "right"),
}


class PlayerAnim:
    def __init__(self) -> None:
        self.frames: Dict[str, List[pygame.Surface]] = {}
        self.dir = "down"
        self.frame_i = 0
        self.t = 0.0
        self.period = 0.18
        self.ready = False

    def load(self, target_px: int = 48) -> None:
        self.frames = {}
        ok = True

        def _scale(s: pygame.Surface) -> pygame.Surface:
            w, h = s.get_size()
            mx = max(w, h)
            if mx <= 0:
                return s.convert_alpha()
            if mx != target_px:
                sc = target_px / float(mx)
                s = pygame.transform.smoothscale(s, (max(1, int(w * sc)), max(1, int(h * sc))))
            return s.convert_alpha()

        def _load_numbered(folder: str) -> List[pygame.Surface]:
            loaded: List[pygame.Surface] = []
            for idx in range(1, 9):
                p = os.path.join(folder, f"{idx}.png")
                s = _safe_load_image(p)
                if s is None:
                    if loaded:
                        break
                    continue
                loaded.append(_scale(s))
            return loaded

        def _load_steps(folder: str) -> List[pygame.Surface]:
            p1 = os.path.join(folder, "step1.png")
            p2 = os.path.join(folder, "step2.png")
            s1 = _safe_load_image(p1)
            s2 = _safe_load_image(p2)
            if s1 is None or s2 is None:
                return []
            return [_scale(s1), _scale(s2)]

        raw: Dict[str, List[pygame.Surface]] = {}
        for dname in ("down", "up", "left", "right"):
            folder = PLAYER_DIRS[dname]
            frames = _load_numbered(folder)
            if not frames:
                frames = _load_steps(folder)
            raw[dname] = frames
            if not frames:
                ok = False

        if (not raw.get("right")) and raw.get("left"):
            raw["right"] = [pygame.transform.flip(f, True, False) for f in raw["left"]]
        if (not raw.get("left")) and raw.get("right"):
            raw["left"] = [pygame.transform.flip(f, True, False) for f in raw["right"]]

        fallback = raw.get("down") or raw.get("up") or raw.get("left") or raw.get("right") or []
        for dname in ("down", "up", "left", "right"):
            if not raw.get(dname):
                raw[dname] = fallback
                ok = False

        self.frames = {d: raw.get(d, []) for d in ("down", "up", "left", "right")}
        self.ready = ok

    def set_dir(self, d: str) -> None:
        if d in ("up", "down", "left", "right"):
            self.dir = d

    def update(self, dt: float, moving: bool) -> None:
        fr = self.frames.get(self.dir) or []
        if not fr:
            return
        if moving:
            self.t += dt
            if self.t >= self.period:
                self.t -= self.period
                self.frame_i = (self.frame_i + 1) % len(fr)
        else:
            self.t = 0.0
            self.frame_i = 0

    def get(self) -> Optional[pygame.Surface]:
        fr = self.frames.get(self.dir) or []
        if not fr:
            return None
        return fr[self.frame_i % len(fr)]


@dataclass
class Player:
    x: float = 160.0
    y: float = 90.0
    speed: float = 240.0
    r: int = 10

    def update(self, dt: float, keys) -> tuple[float, float]:
        dx = 0.0
        dy = 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1.0
        gamepad = get_active_gamepad()
        if gamepad is not None and bool(getattr(gamepad, "connected", False)):
            gx, gy = gamepad.move_vector()
            dx += float(gx)
            dy += float(gy)
        mag = (dx * dx + dy * dy) ** 0.5
        if mag > 1.0:
            dx /= mag
            dy /= mag
        self.x += dx * self.speed * dt
        self.y += dy * self.speed * dt
        return dx, dy


class InteriorView:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.anim = PlayerAnim()
        self.anim.load(target_px=64)
        self.player_dir = "down"
        self.bg_path: Optional[str] = None
        self.bg_img: Optional[pygame.Surface] = None
        self.bg_scaled: Optional[pygame.Surface] = None
        self.bg_size = (0, 0)
        self.player = Player()
        self.active = False
        self.bounds = pygame.Rect(0, 0, screen.get_width(), screen.get_height())
        self.request_takeoff = False
        self.hud_visible = True
        self.ship = None
        self.mission_state = None
        self.notification = ''
        self.notification_until = 0.0
        self.cargo_console_pos = (0.0, 0.0)
        self.fuel_console_pos = (0.0, 0.0)
        self.repair_console_pos = (0.0, 0.0)
        self.fabricator_pos = (0.0, 0.0)
        self.power_console_pos = (0.0, 0.0)
        self.navigation_console_pos = (0.0, 0.0)
        self.cockpit_console_pos = (0.0, 0.0)
        self.request_campaign_complete = False
        self.upgrade_menu_open = False
        self.upgrade_selection = 0

    def activate(self, ship=None) -> None:
        self.active = True
        self.request_takeoff = False
        self.request_campaign_complete = False
        if ship is not None:
            self.ship = ship
            self.mission_state = getattr(ship, 'mission_state', None)
        self.bounds = pygame.Rect(0, 0, self.screen.get_width(), self.screen.get_height())
        new_path = _find_interior_image()
        if new_path != self.bg_path or self.bg_img is None:
            self.bg_path = new_path
            self.bg_img = None
            self.bg_scaled = None
            self.bg_size = (0, 0)
            if self.bg_path:
                try:
                    self.bg_img = pygame.image.load(self.bg_path).convert()
                except Exception:
                    self.bg_img = None
        elif self.bg_size != self.screen.get_size():
            self.bg_scaled = None
            self.bg_size = (0, 0)
        self.player.x = self.screen.get_width() * 0.5
        self.player.y = self.screen.get_height() * 0.55
        self.cargo_console_pos = (self.screen.get_width() * 0.82, self.screen.get_height() * 0.44)
        self.fuel_console_pos = (self.screen.get_width() * 0.18, self.screen.get_height() * 0.44)
        self.power_console_pos = (self.screen.get_width() * 0.18, self.screen.get_height() * 0.70)
        self.navigation_console_pos = (self.screen.get_width() * 0.82, self.screen.get_height() * 0.70)
        self.cockpit_console_pos = (self.screen.get_width() * 0.50, self.screen.get_height() * 0.12)
        self.fabricator_pos = (self.screen.get_width() * 0.50, self.screen.get_height() * 0.31)
        self.repair_console_pos = (self.screen.get_width() * 0.50, self.screen.get_height() * 0.76)
        self.upgrade_menu_open = False
        if self.ship is not None:
            ensure_progression(self.ship)

    def deactivate(self) -> None:
        self.active = False
        self.request_takeoff = False
        self.request_campaign_complete = False
        self.upgrade_menu_open = False

    def set_notification(self, text: str, duration: float = 2.4) -> None:
        self.notification = str(text)
        self.notification_until = time.time() + max(0.1, float(duration))

    def cargo_distance(self) -> float:
        return math.hypot(self.player.x - self.cargo_console_pos[0], self.player.y - self.cargo_console_pos[1])

    def station_distance(self, pos) -> float:
        return math.hypot(self.player.x - pos[0], self.player.y - pos[1])

    def nearest_station(self):
        stations = (
            ("storage", self.cargo_console_pos),
            ("fuel", self.fuel_console_pos),
            ("power", self.power_console_pos),
            ("navigation", self.navigation_console_pos),
            ("cockpit", self.cockpit_console_pos),
            ("repair", self.repair_console_pos),
            ("fabricator", self.fabricator_pos),
        )
        return min(((self.station_distance(pos), name, pos) for name, pos in stations), default=(1e9, None, None))

    def _tutorial_expected(self):
        mission = self.mission_state
        if mission is None or not bool(getattr(mission, 'is_ship_recovery_phase', False)):
            return None
        return getattr(mission, 'ship_boot_next_step', None)

    def _complete_boot_step(self, step: str, message: str) -> bool:
        mission = self.mission_state
        if mission is None or not mission.complete_ship_boot_step(step):
            expected = self._tutorial_expected()
            if expected:
                self.set_notification(f'BOOT SEQUENCE — USE {str(expected).upper()} NEXT', 2.2)
            return False
        self.set_notification(message, 2.4)
        try:
            self.ship.save_state()
        except Exception:
            pass
        return True

    def try_restore_power(self) -> bool:
        if self.ship is None or self.station_distance(self.power_console_pos) > 92.0:
            return False
        if self._tutorial_expected() is None:
            self.set_notification('AUXILIARY POWER ONLINE', 1.6)
            return True
        return self._complete_boot_step('power', 'AUXILIARY POWER RESTORED — CARGO STORAGE ONLINE')

    def try_store_inventory(self) -> bool:
        if self.ship is None or self.cargo_distance() > 92.0:
            return False
        if self._tutorial_expected() not in (None, 'storage'):
            self.set_notification(f'BOOT SEQUENCE — USE {str(self._tutorial_expected()).upper()} NEXT', 2.2)
            return True
        pack = getattr(self.ship, 'player_pack', None)
        if not isinstance(pack, dict):
            pack = {}
            self.ship.player_pack = pack
        moved = []
        for resource, amount in list(pack.items()):
            amount = max(0, int(amount))
            if amount <= 0:
                continue
            add_resource(self.ship, str(resource), amount)
            moved.append(f'{amount} {str(resource).replace("_", " ").upper()}')
        self.ship.player_pack = {}
        if self._tutorial_expected() == 'storage':
            message = 'FIELD PACK STOWED — ' + (' + '.join(moved) if moved else 'PACK EMPTY')
            return self._complete_boot_step('storage', message)
        self.set_notification('CARGO STORED — ' + (' + '.join(moved) if moved else 'NO FIELD ITEMS'), 2.2)
        try:
            self.ship.save_state()
        except Exception:
            pass
        return True

    def try_initialize_navigation(self) -> bool:
        if self.ship is None or self.station_distance(self.navigation_console_pos) > 92.0:
            return False
        if self._tutorial_expected() is None:
            mission = self.mission_state
            if bool(getattr(mission, 'is_delivery_phase', False)):
                self.set_notification('NAVIGATION LOCKED TO GLEEBS DATA LINK', 2.2)
            else:
                self.set_notification('NAVIGATION ARRAY ONLINE', 1.6)
            return True
        return self._complete_boot_step('navigation', 'NAVIGATION ARRAY ONLINE — PROCEED TO COCKPIT')

    def try_cockpit(self) -> bool:
        if self.ship is None or self.station_distance(self.cockpit_console_pos) > 104.0:
            return False
        mission = self.mission_state
        if mission is None:
            return False
        expected = self._tutorial_expected()
        if expected is not None:
            if expected != 'cockpit':
                self.set_notification(f'COCKPIT LOCKED — RESTORE {str(expected).upper()} FIRST', 2.4)
                return True
            if self._complete_boot_step('cockpit', 'MISSION ONLINE — FIND 6 DATA FRAGMENTS BEFORE THE SYSTEMS COLLAPSE'):
                self.request_takeoff = True
            return True
        if bool(getattr(mission, 'is_delivery_phase', False)):
            if mission.transmit_to_gleebs():
                self.set_notification('DATA TRANSFER COMPLETE — RECIPIENT: GLEEBS', 3.0)
                self.request_campaign_complete = True
                try:
                    self.ship.save_state()
                except Exception:
                    pass
            return True
        if bool(getattr(mission, 'campaign_complete', False)):
            self.set_notification('GLEEBS TRANSFER COMPLETE', 1.8)
            self.request_campaign_complete = True
            return True
        self.set_notification('COCKPIT READY — RETURNING TO FLIGHT', 1.8)
        self.request_takeoff = True
        return True

    def try_process_fuel(self) -> bool:
        if self.ship is None or self.station_distance(self.fuel_console_pos) > 92.0:
            return False
        expected = self._tutorial_expected()
        if expected not in (None, 'fuel'):
            self.set_notification(f'BOOT SEQUENCE — USE {str(expected).upper()} NEXT', 2.2)
            return True
        ok, message = process_fuel_cells(self.ship)
        if ok and expected == 'fuel':
            self._complete_boot_step('fuel', f'{message} — NAVIGATION POWER AVAILABLE')
        else:
            self.set_notification(message, 2.6)
            if ok:
                try:
                    self.ship.save_state()
                except Exception:
                    pass
        return True

    def try_repair_hull(self) -> bool:
        if self.ship is None or self.station_distance(self.repair_console_pos) > 92.0:
            return False
        ok, message = repair_hull(self.ship)
        self.set_notification(message, 2.6)
        if ok:
            try:
                self.ship.save_state()
            except Exception:
                pass
        return True

    def try_open_fabricator(self) -> bool:
        if self.ship is None or self.station_distance(self.fabricator_pos) > 92.0:
            return False
        ensure_progression(self.ship)
        self.upgrade_menu_open = True
        self.set_notification('FABRICATION CONSOLE ONLINE', 1.4)
        return True

    def interact_nearest_station(self) -> bool:
        distance, name, _pos = self.nearest_station()
        if distance > 92.0 or name is None:
            return False
        if name == "storage":
            if bool(getattr(self.mission_state, 'carrying_fragment', False)):
                self.try_deposit_fragment()
                return True
            return self.try_store_inventory()
        if name == "fuel":
            return self.try_process_fuel()
        if name == "power":
            return self.try_restore_power()
        if name == "navigation":
            return self.try_initialize_navigation()
        if name == "cockpit":
            return self.try_cockpit()
        if name == "repair":
            return self.try_repair_hull()
        if name == "fabricator":
            return self.try_open_fabricator()
        return False

    def try_deposit_fragment(self) -> bool:
        mission = self.mission_state
        if mission is None or self.cargo_distance() > 92.0:
            return False
        if mission.deposit_fragment():
            secured = int(getattr(mission, "fragments_secured_total", 0))
            required = int(getattr(mission, "data_fragments_required", 6))
            record_name = str(getattr(mission, "current_archive_record", "DATA RECORD"))
            if bool(getattr(mission, "warp_unlocked", False)) and secured < required:
                self.set_notification(f'{record_name} SECURED — ARCHIVE {secured}/{required} — HYPERDRIVE AVAILABLE', 3.6)
            elif secured >= required:
                self.set_notification(f'{record_name} SECURED — ARCHIVE {secured}/{required} — COCKPIT', 3.6)
            else:
                self.set_notification(f'{record_name} SECURED — ARCHIVE {secured}/{required}', 3.2)
            try:
                self.ship.save_state()
            except Exception:
                pass
            return True
        if mission.fragment_deposited:
            self.set_notification(f'DATA ARCHIVE  {int(getattr(mission, "fragments_secured_total", 0))}/{int(getattr(mission, "data_fragments_required", 6))}', 1.8)
        elif not mission.carrying_fragment:
            self.set_notification(f'DATA ARCHIVE  {int(getattr(mission, "fragments_secured_total", 0))}/{int(getattr(mission, "data_fragments_required", 6))}', 1.8)
        return False

    def handle_event(self, event) -> bool:
        if not self.active or event.type != pygame.KEYDOWN:
            return False

        if self.upgrade_menu_open:
            if event.key in (pygame.K_ESCAPE, pygame.K_TAB):
                self.upgrade_menu_open = False
                return True
            if event.key in (pygame.K_w, pygame.K_UP, pygame.K_a, pygame.K_LEFT):
                self.upgrade_selection = (self.upgrade_selection - 1) % len(UPGRADE_ORDER)
                return True
            if event.key in (pygame.K_s, pygame.K_DOWN, pygame.K_d, pygame.K_RIGHT):
                self.upgrade_selection = (self.upgrade_selection + 1) % len(UPGRADE_ORDER)
                return True
            if event.key in (pygame.K_e, pygame.K_RETURN, pygame.K_SPACE):
                track = UPGRADE_ORDER[self.upgrade_selection]
                ok, message = purchase_upgrade(self.ship, track)
                self.set_notification(message, 2.8)
                if ok:
                    try:
                        self.ship.save_state()
                    except Exception:
                        pass
                return True
            return False

        if event.key == pygame.K_e:
            return self.interact_nearest_station()
        return False

    def _ensure_scaled_bg(self) -> None:
        if not self.bg_img:
            return
        size = (self.screen.get_width(), self.screen.get_height())
        if self.bg_scaled is None or self.bg_size != size:
            src_w, src_h = self.bg_img.get_size()
            dst_w, dst_h = size
            scale = max(dst_w / max(1.0, float(src_w)), dst_h / max(1.0, float(src_h)))
            scaled_size = (max(1, int(round(src_w * scale))), max(1, int(round(src_h * scale))))
            expanded = pygame.transform.smoothscale(self.bg_img, scaled_size)
            crop_x = max(0, (expanded.get_width() - dst_w) // 2)
            crop_y = max(0, (expanded.get_height() - dst_h) // 2)
            self.bg_scaled = expanded.subsurface(pygame.Rect(crop_x, crop_y, dst_w, dst_h)).copy()
            self.bg_size = size

    def update(self, dt: float) -> None:
        if not self.active:
            return
        if self.upgrade_menu_open:
            self.anim.update(dt, False)
            return
        keys = pygame.key.get_pressed()
        dx, dy = self.player.update(dt, keys)
        moving = (dx != 0.0 or dy != 0.0)
        if moving:
            if dx > 0:
                self.player_dir = "right"
            elif dx < 0:
                self.player_dir = "left"
            elif dy > 0:
                self.player_dir = "down"
            elif dy < 0:
                self.player_dir = "up"
            self.anim.set_dir(self.player_dir)
        self.anim.update(dt, moving)
        r = self.player.r
        self.player.x = max(r, min(self.bounds.w - r, self.player.x))
        self.player.y = max(r, min(self.bounds.h - r, self.player.y))

    def _draw_station(self, pos, label: str, color, symbol: str, prompt: str) -> None:
        cx, cy = int(pos[0]), int(pos[1])
        rect = pygame.Rect(cx - 72, cy - 38, 144, 76)
        pygame.draw.rect(self.screen, (7, 14, 22), rect, border_radius=10)
        pygame.draw.rect(self.screen, color, rect, 3, border_radius=10)
        pygame.draw.rect(self.screen, (18, 40, 50), rect.inflate(-20, -20), border_radius=6)
        sym = _font(28, True).render(symbol, True, color)
        self.screen.blit(sym, (cx - sym.get_width() // 2, cy - sym.get_height() // 2))
        text = _font(18, True).render(label, True, color)
        label_rect = pygame.Rect(cx - (text.get_width() + 18) // 2, cy + 43, text.get_width() + 18, text.get_height() + 8)
        label_bg = pygame.Surface(label_rect.size, pygame.SRCALPHA)
        label_bg.fill((3, 8, 13, 220))
        self.screen.blit(label_bg, label_rect.topleft)
        pygame.draw.rect(self.screen, color, label_rect, 1, border_radius=5)
        self.screen.blit(text, (label_rect.centerx - text.get_width() // 2, label_rect.centery - text.get_height() // 2))
        if self.station_distance(pos) <= 92.0 and not self.upgrade_menu_open:
            use = _font(18, True).render(prompt, True, (240, 246, 248))
            self.screen.blit(use, (cx - use.get_width() // 2, cy + 72))
            pygame.draw.line(self.screen, color, (int(self.player.x), int(self.player.y)), (cx, cy), 2)

    def _draw_resource_panel(self) -> None:
        if self.ship is None or not self.hud_visible:
            return
        ensure_progression(self.ship)
        w = 430
        h = 138
        x = self.screen.get_width() - w - 48
        y = 92
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((5, 9, 15, 206))
        self.screen.blit(panel, (x, y))
        pygame.draw.rect(self.screen, (55, 92, 112), pygame.Rect(x, y, w, h), 1, border_radius=8)
        title = _font(18, True).render('SHIP STORES', True, (112, 244, 238))
        self.screen.blit(title, (x + 18, y + 13))
        mission = self.mission_state
        rows = (
            f'DATA  {int(getattr(mission, "fragments_secured_total", 0)):02d}/{int(getattr(mission, "data_fragments_required", 6)):02d}    SALVAGE  {resource_amount(self.ship, "salvage"):02d}    FUEL CELLS  {resource_amount(self.ship, "fuel_cells"):02d}',
            f'FUEL  {int(self.ship.fuel):03d}/{int(self.ship.fuel_max):03d}    HULL  {int(self.ship.hull_hp):03d}/{int(self.ship.hull_hp_max):03d}',
            'UPGRADES  ' + '  '.join(f'{key[0].upper()}{int(self.ship.upgrade_levels[key])}' for key in UPGRADE_ORDER),
        )
        for i, row in enumerate(rows):
            img = _font(17).render(row, True, (194, 214, 224))
            self.screen.blit(img, (x + 18, y + 45 + i * 26))

    def _draw_upgrade_menu(self) -> None:
        if not self.upgrade_menu_open or self.ship is None:
            return
        ensure_progression(self.ship)
        sw, sh = self.screen.get_size()
        dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        self.screen.blit(dim, (0, 0))
        rect = pygame.Rect(sw // 2 - 480, sh // 2 - 330, 960, 660)
        pygame.draw.rect(self.screen, (4, 8, 14), rect, border_radius=14)
        pygame.draw.rect(self.screen, (96, 214, 232), rect, 2, border_radius=14)
        title = _font(36, True).render('SHIP FABRICATOR', True, (236, 244, 248))
        self.screen.blit(title, (rect.left + 38, rect.top + 30))
        legacy_cores = resource_amount(self.ship, "relic_cores")
        stores_text = f'SALVAGE  {resource_amount(self.ship, "salvage")}'
        if legacy_cores > 0:
            stores_text += f'  •  LEGACY CORES  {legacy_cores}'
        stores = _font(20, True).render(
            stores_text, True, (112, 244, 238)
        )
        self.screen.blit(stores, (rect.left + 40, rect.top + 82))
        y = rect.top + 132
        for idx, track in enumerate(UPGRADE_ORDER):
            lvl = int(self.ship.upgrade_levels[track])
            selected = idx == self.upgrade_selection
            row = pygame.Rect(rect.left + 36, y, rect.w - 72, 98)
            pygame.draw.rect(self.screen, (18, 30, 42) if selected else (10, 17, 26), row, border_radius=8)
            pygame.draw.rect(self.screen, (112, 244, 238) if selected else (55, 92, 112), row, 2 if selected else 1, border_radius=8)
            label = _font(22, True).render(UPGRADE_LABELS[track], True, (238, 244, 248))
            self.screen.blit(label, (row.left + 22, row.top + 16))
            effect = _font(17).render(upgrade_effect(track, lvl), True, (166, 190, 202))
            self.screen.blit(effect, (row.left + 22, row.top + 53))
            level_img = _font(20, True).render(f'LEVEL {lvl}/{MAX_UPGRADE_LEVEL}', True, (112, 244, 238))
            self.screen.blit(level_img, (row.right - level_img.get_width() - 210, row.top + 18))
            cost = next_upgrade_cost(self.ship, track)
            cost_text = 'MAXIMUM' if cost is None else (f'NEXT  1 LEGACY CORE OR {cost} SALVAGE' if legacy_cores > 0 else f'NEXT  {cost} SALVAGE')
            cost_img = _font(17, True).render(cost_text, True, (255, 202, 108) if cost is not None else (146, 164, 176))
            self.screen.blit(cost_img, (row.right - cost_img.get_width() - 24, row.top + 56))
            y += 108
        footer = _font(18, True).render('W/S OR ARROWS SELECT  •  E/ENTER INSTALL  •  ESC CLOSE', True, (166, 184, 198))
        self.screen.blit(footer, (rect.centerx - footer.get_width() // 2, rect.bottom - 44))

    def draw(self) -> None:
        if not self.active:
            return
        if self.bg_img:
            self._ensure_scaled_bg()
            if self.bg_scaled:
                self.screen.blit(self.bg_scaled, (0, 0))
        else:
            self.screen.fill((14, 18, 26))
            w, h = self.screen.get_width(), self.screen.get_height()
            for x in range(0, w, 48):
                pygame.draw.line(self.screen, (24, 30, 42), (x, 0), (x, h), 1)
            for y in range(0, h, 48):
                pygame.draw.line(self.screen, (24, 30, 42), (0, y), (w, y), 1)
            pygame.draw.rect(self.screen, (26, 34, 48), pygame.Rect(0, h - 120, w, 120))

        # Pass 17 ship hub stations. They remain in-world and only open a
        # modal panel when the player deliberately uses the Fabricator.
        self._draw_station(self.cockpit_console_pos, 'COCKPIT', (255, 216, 104), 'C', 'E  COCKPIT / MISSION')
        self._draw_station(self.power_console_pos, 'POWER RELAY', (126, 246, 190), 'P', 'E  RESTORE AUX POWER')
        self._draw_station(self.fuel_console_pos, 'FUEL PORT', (112, 224, 255), '+', 'E  PROCESS FUEL CELLS')
        self._draw_station(self.navigation_console_pos, 'NAVIGATION', (126, 190, 255), 'N', 'E  INITIALIZE NAV ARRAY')
        self._draw_station(self.repair_console_pos, 'REPAIR BAY', (255, 164, 104), 'R', 'E  REPAIR 25 HULL / 2 SALVAGE')
        self._draw_station(self.fabricator_pos, 'FABRICATOR', (192, 134, 255), 'F', 'E  OPEN UPGRADES')

        # Functional cargo console: an in-world interaction, not a permanent modal HUD.
        cx, cy = int(self.cargo_console_pos[0]), int(self.cargo_console_pos[1])
        carrying = bool(getattr(self.mission_state, 'carrying_fragment', False))
        deposited = bool(getattr(self.mission_state, 'fragment_deposited', False))
        pulse = 0.5 + 0.5 * math.sin(time.time() * 3.4)
        console_rect = pygame.Rect(cx - 78, cy - 42, 156, 84)
        pygame.draw.rect(self.screen, (7, 14, 22), console_rect, border_radius=10)
        pygame.draw.rect(self.screen, (255, 212, 104) if carrying else (76, 216, 220), console_rect, 3, border_radius=10)
        pygame.draw.rect(self.screen, (22, 54, 64), console_rect.inflate(-22, -22), border_radius=6)
        core_col = (255, 230, 138) if carrying else ((98, 248, 226) if deposited else (92, 162, 176))
        pygame.draw.polygon(self.screen, core_col, [(cx, cy - 24), (cx + 16, cy), (cx, cy + 24), (cx - 16, cy)])
        if carrying:
            pygame.draw.circle(self.screen, (255, 214, 104), (cx, cy), int(48 + pulse * 10), 2)
        label = _font(19, True).render('CARGO / DATA ARCHIVE', True, core_col)
        label_rect = pygame.Rect(cx - (label.get_width() + 20) // 2, cy + 49, label.get_width() + 20, label.get_height() + 8)
        label_bg = pygame.Surface(label_rect.size, pygame.SRCALPHA)
        label_bg.fill((3, 8, 13, 224))
        self.screen.blit(label_bg, label_rect.topleft)
        pygame.draw.rect(self.screen, core_col, label_rect, 1, border_radius=5)
        self.screen.blit(label, (label_rect.centerx - label.get_width() // 2, label_rect.centery - label.get_height() // 2))
        near = self.cargo_distance() <= 92.0
        if near and not self.upgrade_menu_open:
            prompt_text = 'E  CONVERT LEGACY FRAGMENT' if carrying else 'E  STORE FIELD PACK / CHECK DATA'
            prompt = _font(20, True).render(prompt_text, True, (255, 232, 150) if carrying else (186, 226, 230))
            self.screen.blit(prompt, (cx - prompt.get_width() // 2, cy + 82))
            pygame.draw.line(self.screen, (255, 218, 116) if carrying else (92, 190, 198), (int(self.player.x), int(self.player.y)), (cx, cy), 2)

        spr = self.anim.get()
        if spr is not None:
            self.screen.blit(spr, (int(self.player.x - spr.get_width() * 0.5), int(self.player.y - spr.get_height() * 0.5)))
        else:
            pygame.draw.circle(self.screen, (210, 210, 220), (int(self.player.x), int(self.player.y)), self.player.r)
            pygame.draw.circle(self.screen, (40, 220, 120), (int(self.player.x), int(self.player.y)), max(2, self.player.r // 3))

        if self.notification and time.time() <= self.notification_until:
            note = _font(22, True).render(self.notification, True, (236, 248, 246))
            box = pygame.Surface((note.get_width() + 52, 52), pygame.SRCALPHA)
            box.fill((5, 9, 15, 220))
            x = self.screen.get_width() // 2 - box.get_width() // 2
            y = 132
            self.screen.blit(box, (x, y))
            pygame.draw.rect(self.screen, (78, 214, 214), pygame.Rect(x, y, box.get_width(), box.get_height()), 1, border_radius=8)
            self.screen.blit(note, (self.screen.get_width() // 2 - note.get_width() // 2, y + 14))

        mission = self.mission_state
        expected = getattr(mission, 'ship_boot_next_step', None) if bool(getattr(mission, 'is_ship_recovery_phase', False)) else None
        if expected:
            step_names = {'power':'POWER RELAY','storage':'CARGO STORAGE','fuel':'FUEL PORT','navigation':'NAVIGATION','cockpit':'COCKPIT'}
            objective = f'RESTORE SHIP  •  NEXT: {step_names.get(str(expected), str(expected).upper())}'
            img = _font(22, True).render(objective, True, (255, 226, 132))
            box = pygame.Surface((img.get_width() + 52, 50), pygame.SRCALPHA)
            box.fill((5, 9, 15, 226))
            bx = self.screen.get_width() // 2 - box.get_width() // 2
            by = self.screen.get_height() - 86
            self.screen.blit(box, (bx, by))
            pygame.draw.rect(self.screen, (255, 210, 104), pygame.Rect(bx, by, box.get_width(), box.get_height()), 1, border_radius=8)
            self.screen.blit(img, (bx + 26, by + 13))

        self._draw_resource_panel()
        self._draw_upgrade_menu()


_VIEW: Optional[InteriorView] = None


def enter_interior(screen: pygame.Surface, ship=None, return_mode=None) -> None:
    global _VIEW
    if _VIEW is None or _VIEW.screen is not screen:
        _VIEW = InteriorView(screen)
    _VIEW.activate(ship)


def get_interior(screen: pygame.Surface, ship=None) -> InteriorView:
    global _VIEW
    if _VIEW is None or _VIEW.screen is not screen:
        _VIEW = InteriorView(screen)
    if not _VIEW.active:
        _VIEW.activate(ship)
    elif ship is not None:
        _VIEW.ship = ship
        _VIEW.mission_state = getattr(ship, 'mission_state', None)
    return _VIEW


def leave_interior() -> None:
    global _VIEW
    if _VIEW is not None:
        _VIEW.deactivate()
