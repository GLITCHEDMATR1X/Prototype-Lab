from __future__ import annotations

import math

import pygame

from game.building_stage import BuildingStageState, StageCamera
from game.hacking import HackOutcome, METHODS

VIRTUAL_SIZE = (1920, 1080)
C = {
    "bg": (4, 7, 10),
    "panel": (7, 12, 16),
    "line": (55, 76, 82),
    "cyan": (46, 218, 246),
    "white": (215, 248, 252),
    "amber": (238, 165, 61),
    "red": (232, 58, 55),
    "violet": (173, 45, 235),
    "green": (57, 221, 100),
    "muted": (112, 128, 134),
    "steel": (48, 58, 63),
    "floor": (18, 23, 27),
    "dark": (8, 12, 15),
}


class StageRenderer:
    def __init__(self, text_scale: float = 1.0) -> None:
        self.set_text_scale(text_scale)

    def set_text_scale(self, text_scale: float) -> None:
        scale = max(0.90, min(1.15, float(text_scale)))
        self.text_scale = scale
        self.small = pygame.font.SysFont("dejavusansmono", round(20 * scale))
        self.medium = pygame.font.SysFont("dejavusansmono", round(28 * scale), bold=True)
        self.large = pygame.font.SysFont("dejavusansmono", round(48 * scale), bold=True)

    def render(
        self,
        target: pygame.Surface,
        state: BuildingStageState,
        elapsed: float,
        settings=None,
        onboarding_step: int = 0,
    ) -> None:
        settings = settings or {}
        target.fill(C["bg"])
        self._header(target, state)
        feed = pygame.Rect(70, 120, 1380, 790)
        pygame.draw.rect(target, C["panel"], feed)
        border = C["white"] if settings.get("high_contrast") else C["line"]
        pygame.draw.rect(target, border, feed, 3 if settings.get("high_contrast") else 2)
        self._room(target, feed, state, elapsed)
        self._feed_vignette(target, feed, bool(settings.get("reduced_motion", False)))
        self._sidebar(target, state)
        self._footer(target, state)
        self._status_strip(target, state, bool(settings.get("high_contrast", False)))
        self._onboarding_card(target, state, onboarding_step)
        self._outcome_overlay(target, state)
        if state.gleebs_ejected:
            self._ejection_overlay(
                target,
                state,
                elapsed,
                bool(settings.get("reduced_glitch", False)),
                bool(settings.get("reduced_flashing", False)),
            )
        self._scanlines(target, feed, bool(settings.get("reduced_glitch", False)))

    def _header(self, target: pygame.Surface, state: BuildingStageState) -> None:
        self._text(target, state.title, (70, 34), self.medium, C["white"])
        if state.building_id == "maintenance_depot":
            subtitle = "DRONE SERVICE NETWORK"
        elif state.building_id == "transit_substation":
            subtitle = "MUNICIPAL TRANSIT ROUTING"
        elif state.building_id == "corporate_mall":
            subtitle = "COMMERCIAL IDENTITY NETWORK"
        elif state.building_id == "media_broadcast":
            subtitle = "PUBLIC SIGNAL AUTHORITY"
        elif state.building_id == "financial_exchange":
            subtitle = "TRANSACTION CLEARING AUTHORITY"
        elif state.building_id == "private_clinic":
            subtitle = "PATIENT SAFETY / BIOLOGICAL RECORDS"
        elif state.building_id == "automated_factory":
            subtitle = "AUTONOMOUS FABRICATION / WORKER SAFETY"
        elif state.building_id == "power_distribution_plant":
            subtitle = "CITY LOAD ROUTING / CRITICAL FEEDERS"
        elif state.building_id == "drone_assembly_facility":
            subtitle = "FLIGHT HOST FABRICATION / ACTIVE IDENTITIES"
        elif state.building_id == "waste_processing_complex":
            subtitle = "MATERIAL RECOVERY / HAZARD CONTAINMENT"
        else:
            subtitle = "MUNICIPAL OPTICAL ROUTING"
        self._text(target, f"CAM {self._cam_no(state):02d} / {subtitle}", (70, 78), self.small, C["cyan"])
        pygame.draw.rect(target, (20, 27, 31), (1510, 42, 330, 28))
        pygame.draw.rect(target, C["red"], (1510, 42, int(330 * state.trace / 100), 28))
        self._text(target, f"TRACE {int(state.trace):03d}%", (1580, 44), self.small, C["white"])

    def _room(self, target: pygame.Surface, rect: pygame.Rect, state: BuildingStageState, elapsed: float) -> None:
        inner = rect.inflate(-34, -34)
        pygame.draw.rect(target, C["floor"], inner)
        for x in range(inner.left, inner.right, 72):
            pygame.draw.line(target, (25, 34, 38), (x, inner.top), (x, inner.bottom), 1)
        for y in range(inner.top, inner.bottom, 72):
            pygame.draw.line(target, (25, 34, 38), (inner.left, y), (inner.right, y), 1)
        if state.building_id == "maintenance_depot":
            self._depot_room(target, inner, state, elapsed)
        elif state.building_id == "transit_substation":
            self._transit_room(target, inner, state, elapsed)
        elif state.building_id == "corporate_mall":
            self._mall_room(target, inner, state, elapsed)
        elif state.building_id == "media_broadcast":
            self._media_room(target, inner, state, elapsed)
        elif state.building_id == "financial_exchange":
            self._financial_room(target, inner, state, elapsed)
        elif state.building_id == "private_clinic":
            self._clinic_room(target, inner, state, elapsed)
        elif state.building_id == "automated_factory":
            self._factory_room(target, inner, state, elapsed)
        elif state.building_id == "power_distribution_plant":
            self._power_room(target, inner, state, elapsed)
        elif state.building_id == "drone_assembly_facility":
            self._drone_assembly_room(target, inner, state, elapsed)
        elif state.building_id == "waste_processing_complex":
            self._waste_processing_room(target, inner, state, elapsed)
        elif state.camera is StageCamera.EXTERIOR:
            self._annex_exterior(target, inner, state, elapsed)
        elif state.camera is StageCamera.OPERATIONS:
            self._annex_operations(target, inner, state)
        else:
            self._annex_core(target, inner, state, elapsed)

    def _annex_exterior(self, target, rect, state, elapsed) -> None:
        pygame.draw.rect(target, (27, 34, 38), (rect.left + 90, rect.top + 100, 520, 430))
        pygame.draw.rect(target, (78, 86, 90), (rect.left + 90, rect.top + 100, 520, 430), 3)
        door = pygame.Rect(rect.left + 470, rect.top + 250, 95, 210)
        pygame.draw.rect(target, C["dark"], door)
        pygame.draw.rect(target, C["cyan"] if state.door_open else C["amber"], door, 3)
        self._text(target, "OPEN" if state.door_open else "LOCKED", (door.x + 8, door.y + 75), self.small, C["cyan"] if state.door_open else C["amber"])
        camera = (rect.left + 820, rect.top + 210)
        pygame.draw.circle(target, C["steel"], camera, 28)
        pygame.draw.circle(target, C["cyan"], camera, 28, 3)
        sweep = pygame.Vector2(250, 0).rotate(25 + math.sin(elapsed) * 18)
        pygame.draw.line(target, C["cyan"], camera, (camera[0] + sweep.x, camera[1] + sweep.y), 2)
        self._room_caption(target, rect, "EXTERIOR SERVICE ACCESS")

    def _annex_operations(self, target, rect, state) -> None:
        for index in range(4):
            desk = pygame.Rect(rect.left + 120 + index * 255, rect.top + 260, 190, 120)
            pygame.draw.rect(target, (28, 36, 40), desk)
            pygame.draw.rect(target, C["line"], desk, 2)
            screen = desk.inflate(-24, -28)
            pygame.draw.rect(target, (6, 15, 18), screen)
            pygame.draw.line(target, C["cyan"], screen.topleft, screen.bottomright, 2)
        bus = pygame.Rect(rect.left + 220, rect.top + 90, 790, 80)
        pygame.draw.rect(target, C["dark"], bus)
        pygame.draw.rect(target, C["cyan"] if state.lights_rerouted else C["amber"], bus, 3)
        for index in range(9):
            color = C["cyan"] if state.lights_rerouted and index % 2 == 0 else C["amber"]
            pygame.draw.circle(target, color, (bus.left + 45 + index * 82, bus.centery), 8)
        self._text(target, "OPERATIONS LIGHT BUS", (bus.left, bus.top - 38), self.small, C["white"])
        self._room_caption(target, rect, "OPERATIONS FEED")

    def _annex_core(self, target, rect, state, elapsed) -> None:
        center = (rect.centerx, rect.centery - 20)
        for radius in (180, 130, 80):
            pygame.draw.circle(target, (16, 28, 32), center, radius)
            pygame.draw.circle(target, C["cyan"] if state.core_exposed else C["amber"], center, radius, 3)
        for angle in range(0, 360, 45):
            vector = pygame.Vector2(180, 0).rotate(angle + elapsed * 12)
            pygame.draw.circle(target, C["cyan"], (int(center[0] + vector.x), int(center[1] + vector.y)), 10)
        pygame.draw.rect(target, (25, 90, 102), (center[0] - 18, rect.top + 80, 36, rect.height - 160))
        self._room_caption(target, rect, "ANNEX NETWORK CORE")

    def _depot_room(self, target, rect, state, elapsed) -> None:
        if state.camera is StageCamera.YARD:
            pygame.draw.rect(target, (24, 30, 33), (rect.left + 80, rect.top + 90, 1080, 470))
            pygame.draw.rect(target, C["line"], (rect.left + 80, rect.top + 90, 1080, 470), 3)
            for index in range(5):
                bay = pygame.Rect(rect.left + 130 + index * 190, rect.top + 250, 145, 190)
                pygame.draw.rect(target, C["dark"], bay)
                pygame.draw.rect(target, C["cyan"] if state.door_open else C["amber"], bay, 3)
            caption = "DELIVERY YARD / SERVICE GATE"
        elif state.camera is StageCamera.REPAIR:
            for index in range(4):
                rack = pygame.Rect(rect.left + 120 + index * 255, rect.top + 180, 190, 330)
                pygame.draw.rect(target, (25, 33, 37), rack)
                pygame.draw.rect(target, C["line"], rack, 2)
                pygame.draw.circle(target, C["cyan"] if index == 2 and state.drone_unlocked else C["amber"], rack.center, 42, 4)
                self._text(target, f"D-{index + 2:02d}", (rack.x + 68, rack.bottom - 54), self.small, C["white"])
            caption = "REPAIR FLOOR / POSSESSION RACK"
        elif state.camera is StageCamera.DRONE:
            pygame.draw.rect(target, (14, 20, 23), rect.inflate(-70, -70))
            pygame.draw.rect(target, C["line"], rect.inflate(-70, -70), 2)
            pygame.draw.rect(target, (2, 5, 7), (rect.centerx - 45, rect.top + 70, 90, rect.height - 140))
            for y in range(rect.top + 100, rect.bottom - 100, 52):
                pygame.draw.line(target, C["red"], (rect.centerx - 36, y), (rect.centerx + 36, y), 2)
            origin = pygame.Vector2(rect.left + 70, rect.top + 70)
            drone = origin + state.drone_pos
            pygame.draw.circle(target, C["cyan"], (int(drone.x), int(drone.y)), 24)
            pygame.draw.circle(target, C["white"], (int(drone.x), int(drone.y)), 24, 3)
            port = (origin.x + 1000, origin.y + 380)
            pygame.draw.circle(target, C["green"] if state.drone_docked else C["cyan"], (int(port[0]), int(port[1])), 42, 4)
            self._text(target, "PHYSICAL SERVICE PORT", (int(port[0] - 120), int(port[1] - 70)), self.small, C["white"])
            caption = "WASD / ARROWS DRIVE UNIT D-04 ACROSS AIR GAP"
        else:
            center = rect.center
            for radius in (210, 150, 90):
                pygame.draw.circle(target, (13, 25, 28), center, radius)
                pygame.draw.circle(target, C["green"] if state.bridge_connected else C["amber"], center, radius, 4)
            for angle in range(0, 360, 60):
                vector = pygame.Vector2(210, 0).rotate(angle + elapsed * 18)
                pygame.draw.circle(target, C["cyan"], (int(center[0] + vector.x), int(center[1] + vector.y)), 12)
            caption = "DEPOT EMERGENCY REPAIR CORE"
        self._room_caption(target, rect, caption)

    def _transit_room(self, target, rect, state, elapsed) -> None:
        if state.camera is StageCamera.PLATFORM:
            self._transit_platform(target, rect, state, elapsed)
        elif state.camera is StageCamera.SERVICE_CONTROL:
            self._transit_service(target, rect, state, elapsed)
        elif state.camera is StageCamera.ROUTING_CORE:
            self._transit_core(target, rect, state, elapsed)
        else:
            self._transit_uplink(target, rect, state, elapsed)

    def _transit_platform(self, target, rect, state, elapsed) -> None:
        for lane in range(3):
            y = rect.top + 150 + lane * 160
            pygame.draw.rect(target, (8, 12, 14), (rect.left + 80, y, 1110, 82))
            for offset in (22, 58):
                pygame.draw.line(target, C["steel"], (rect.left + 90, y + offset), (rect.right - 100, y + offset), 4)
            car_x = rect.left + 160 + ((elapsed * (35 + lane * 8)) % 620)
            car = pygame.Rect(int(car_x), y + 10, 360, 62)
            pygame.draw.rect(target, (56, 65, 68), car, border_radius=8)
            pygame.draw.rect(target, C["green"] if state.platform_secured else C["amber"], car, 3, border_radius=8)
            for index in range(8):
                window = pygame.Rect(car.x + 22 + index * 40, car.y + 13, 26, 20)
                pygame.draw.rect(target, (16, 27, 31), window)
                pygame.draw.circle(target, C["white"], window.center, 3)
            self._text(target, f"CAR {state.occupied_lines[lane]:02d} OCCUPIED", (rect.left + 85, y - 30), self.small, C["green"] if state.platform_secured else C["amber"])
        self._room_caption(target, rect, "PLATFORM SURVEILLANCE / OCCUPIED ROUTES")

    def _transit_service(self, target, rect, state, elapsed) -> None:
        map_rect = pygame.Rect(rect.left + 120, rect.top + 100, 960, 420)
        pygame.draw.rect(target, (9, 17, 20), map_rect)
        pygame.draw.rect(target, C["line"], map_rect, 2)
        points = [(map_rect.left + 70, map_rect.centery), (map_rect.left + 280, map_rect.top + 90), (map_rect.left + 480, map_rect.bottom - 100), (map_rect.left + 700, map_rect.top + 120), (map_rect.right - 70, map_rect.centery)]
        for a, b in zip(points, points[1:]):
            pygame.draw.line(target, C["cyan"] if state.service_window_open else C["amber"], a, b, 7)
        for index, point in enumerate(points):
            pygame.draw.circle(target, C["green"] if state.service_window_open else C["amber"], point, 18, 4)
            self._text(target, f"R{index + 1}", (point[0] - 13, point[1] - 11), self.small, C["white"])
        tech = pygame.Rect(map_rect.right - 170, map_rect.bottom - 80, 120, 52)
        pygame.draw.rect(target, (34, 42, 44), tech)
        pygame.draw.rect(target, C["cyan"], tech, 2)
        self._text(target, "SERVICE", (tech.x + 15, tech.y + 14), self.small, C["cyan"])
        self._room_caption(target, rect, "SERVICE CONTROL / ROUTING WINDOW")

    def _transit_core(self, target, rect, state, elapsed) -> None:
        center = pygame.Vector2(rect.centerx, rect.centery - 10)
        for radius in (250, 185, 120):
            pygame.draw.circle(target, (12, 22, 25), center, radius)
            pygame.draw.circle(target, C["green"] if state.routing_safe else C["amber"], center, radius, 4)
        for index, line_id in enumerate(state.occupied_lines):
            angle = -35 + index * 35 + math.sin(elapsed * 0.8 + index) * 5
            end = center + pygame.Vector2(350, 0).rotate(angle)
            pygame.draw.line(target, C["green"] if state.routing_safe else C["amber"], center, end, 9)
            pygame.draw.circle(target, C["white"], end, 15)
            self._text(target, f"OCCUPIED {line_id:02d}", (int(end.x - 70), int(end.y - 45)), self.small, C["white"])
        battery = pygame.Rect(rect.left + 100, rect.top + 110, 150, 250)
        pygame.draw.rect(target, (22, 29, 31), battery)
        pygame.draw.rect(target, C["green"], battery, 3)
        self._text(target, "BACKUP", (battery.x + 25, battery.y + 40), self.small, C["white"])
        self._text(target, "ONLINE", (battery.x + 28, battery.y + 78), self.small, C["green"])
        self._room_caption(target, rect, "ROUTING CORE / CIVILIAN LINE STABILIZATION")

    def _transit_uplink(self, target, rect, state, elapsed) -> None:
        pygame.draw.rect(target, (5, 9, 13), (rect.left + 60, rect.top + 60, rect.width - 120, rect.height - 120))
        horizon = rect.top + 330
        for index in range(14):
            width = 58 + (index % 4) * 22
            height = 120 + (index % 5) * 35
            x = rect.left + 75 + index * 82
            pygame.draw.rect(target, (20, 27, 31), (x, horizon - height, width, height))
            pygame.draw.rect(target, C["cyan"] if state.uplink_exposed else C["muted"], (x, horizon - height, width, height), 1)
        base = (rect.centerx, rect.bottom - 140)
        pygame.draw.line(target, C["steel"], (base[0] - 130, base[1]), (base[0], rect.top + 150), 12)
        pygame.draw.line(target, C["steel"], (base[0] + 130, base[1]), (base[0], rect.top + 150), 12)
        pygame.draw.circle(target, C["cyan"], (base[0], rect.top + 150), 42, 5)
        beam_height = int(180 + 30 * math.sin(elapsed * 2.0))
        beam = pygame.Surface((110, beam_height), pygame.SRCALPHA)
        beam.fill((46, 218, 246, 38))
        target.blit(beam, (base[0] - 55, rect.top + 150 - beam_height))
        self._room_caption(target, rect, "ROOFTOP UPLINK / DISTRICT AUTHORITY RELAY")

    def _mall_room(self, target, rect, state, elapsed) -> None:
        if state.camera is StageCamera.MALL_ATRIUM:
            # Open retail atrium with live crowd lanes and repeating access gates.
            pygame.draw.rect(target, (21, 27, 31), rect.inflate(-80, -70), border_radius=8)
            pygame.draw.rect(target, C["line"], rect.inflate(-80, -70), 2, border_radius=8)
            skylight = pygame.Rect(rect.centerx - 230, rect.top + 80, 460, 130)
            pygame.draw.rect(target, (8, 22, 27), skylight, border_radius=10)
            pygame.draw.rect(target, C["cyan"], skylight, 3, border_radius=10)
            for i in range(6):
                x = rect.left + 145 + i * 170
                gate = pygame.Rect(x, rect.bottom - 235, 90, 150)
                pygame.draw.rect(target, C["dark"], gate)
                pygame.draw.rect(target, C["cyan"] if state.atrium_access else C["amber"], gate, 3)
            for i in range(18):
                x = rect.left + 120 + (i * 73) % (rect.width - 220)
                y = rect.top + 270 + ((i * 47 + int(elapsed * 20)) % 240)
                pygame.draw.circle(target, (176, 164, 146), (x, y), 6)
                pygame.draw.line(target, (48, 54, 58), (x, y + 6), (x, y + 24), 5)
            caption = "PUBLIC ATRIUM / SHOPPER ACCESS GATES"
        elif state.camera is StageCamera.AD_GRID:
            for row in range(3):
                for col in range(5):
                    panel = pygame.Rect(rect.left + 90 + col * 210, rect.top + 90 + row * 170, 165, 115)
                    pygame.draw.rect(target, (8, 18, 22), panel)
                    accent = C["cyan"] if state.ads_rerouted else (C["amber"] if (row + col) % 2 else C["violet"])
                    pygame.draw.rect(target, accent, panel, 3)
                    pygame.draw.line(target, accent, panel.topleft, panel.bottomright, 2)
            bus = pygame.Rect(rect.left + 230, rect.bottom - 130, rect.width - 460, 44)
            pygame.draw.rect(target, C["dark"], bus)
            pygame.draw.rect(target, C["cyan"] if state.ads_rerouted else C["amber"], bus, 3)
            caption = "ADVERTISING GRID / SERVICE CHANNEL"
        elif state.camera is StageCamera.IDENTITY_GALLERY:
            for index in range(8):
                kiosk = pygame.Rect(rect.left + 90 + index * 145, rect.top + 170, 105, 300)
                pygame.draw.rect(target, (17, 24, 28), kiosk, border_radius=5)
                pygame.draw.rect(target, C["cyan"] if index == 6 and state.identity_copied else C["violet"], kiosk, 3, border_radius=5)
                pygame.draw.circle(target, C["white"], (kiosk.centerx, kiosk.top + 65), 18, 2)
                pygame.draw.line(target, C["muted"], (kiosk.centerx, kiosk.top + 90), (kiosk.centerx, kiosk.bottom - 40), 4)
            caption = "IDENTITY GALLERY / LOYALTY MIRROR"
        else:
            center = rect.center
            for radius in (225, 165, 105):
                pygame.draw.circle(target, (12, 24, 29), center, radius)
                pygame.draw.circle(target, C["cyan"] if state.mall_core_exposed else C["amber"], center, radius, 4)
            for angle in range(0, 360, 30):
                v = pygame.Vector2(225, 0).rotate(angle + elapsed * 16)
                color = C["cyan"] if angle % 60 == 0 else C["violet"]
                pygame.draw.circle(target, color, (int(center[0] + v.x), int(center[1] + v.y)), 9)
            pygame.draw.rect(target, (21, 74, 82), (center[0] - 22, rect.top + 90, 44, rect.height - 180))
            caption = "RETAIL CORE / ISOLATED SAFE-REBOOT BUS"
        self._room_caption(target, rect, caption)


    def _media_room(self, target, rect, state, elapsed) -> None:
        if state.camera is StageCamera.BROADCAST_INGEST:
            # Newsroom ingest wall: multiple live sources entering a protected editorial buffer.
            wall = pygame.Rect(rect.left + 75, rect.top + 70, rect.width - 150, 250)
            pygame.draw.rect(target, (8, 16, 21), wall)
            pygame.draw.rect(target, C["line"], wall, 2)
            for row in range(2):
                for col in range(6):
                    screen = pygame.Rect(wall.left + 24 + col * 170, wall.top + 22 + row * 105, 140, 78)
                    accent = C["cyan"] if state.feed_looped else (C["violet"] if (row + col) % 2 else C["amber"])
                    pygame.draw.rect(target, (5, 20, 27), screen)
                    pygame.draw.rect(target, accent, screen, 2)
                    sweep = int((elapsed * 55 + col * 13 + row * 23) % max(1, screen.width - 18))
                    pygame.draw.line(target, accent, (screen.left + 8, screen.centery), (screen.left + 8 + sweep, screen.centery), 2)
            buffer = pygame.Rect(rect.centerx - 300, rect.bottom - 245, 600, 92)
            pygame.draw.rect(target, C["dark"], buffer)
            pygame.draw.rect(target, C["green"] if state.feed_looped else C["amber"], buffer, 3)
            self._text(target, "EDITORIAL BUFFER / CURRENT FEED HELD", (buffer.x + 55, buffer.y + 30), self.small, C["white"])
            caption = "PROGRAM INGEST / LIVE FEED MANIPULATION"
        elif state.camera is StageCamera.ALERT_ROUTER:
            router = pygame.Rect(rect.left + 110, rect.top + 85, rect.width - 220, rect.height - 190)
            pygame.draw.rect(target, (7, 15, 20), router)
            pygame.draw.rect(target, C["line"], router, 2)
            center = pygame.Vector2(router.center)
            channels = [
                ("CIVIL EMERGENCY", C["red"], -155),
                ("MAINTENANCE", C["cyan"], -50),
                ("PUBLIC NEWS", C["amber"], 55),
                ("TRANSIT NOTICE", C["green"], 160),
            ]
            for label, color, yoff in channels:
                start = (router.left + 80, int(center.y + yoff))
                end = (router.right - 85, int(center.y + yoff))
                pygame.draw.line(target, color if state.alert_routed and label == "MAINTENANCE" else C["steel"], start, end, 8)
                pygame.draw.circle(target, color, start, 16, 3)
                pygame.draw.circle(target, color, end, 16, 3)
                self._text(target, label, (router.left + 105, int(center.y + yoff - 34)), self.small, color)
            false_box = pygame.Rect(router.centerx - 175, router.centery - 52, 350, 104)
            pygame.draw.rect(target, (20, 24, 28), false_box)
            pygame.draw.rect(target, C["green"] if state.alert_routed else C["amber"], false_box, 3)
            self._text(target, "SIGNED CLEAR-SEQUENCE", (false_box.x + 50, false_box.y + 24), self.small, C["white"])
            self._text(target, "ROUTED" if state.alert_routed else "AWAITING", (false_box.x + 125, false_box.y + 60), self.small, C["green"] if state.alert_routed else C["amber"])
            caption = "EMERGENCY ALERT ROUTER / FALSE-ALERT CONTROL"
        elif state.camera is StageCamera.LIVE_STUDIO:
            studio = pygame.Rect(rect.left + 95, rect.top + 70, rect.width - 190, rect.height - 170)
            pygame.draw.rect(target, (17, 21, 25), studio, border_radius=8)
            pygame.draw.rect(target, C["line"], studio, 2, border_radius=8)
            desk = pygame.Rect(studio.centerx - 230, studio.centery + 70, 460, 90)
            pygame.draw.rect(target, (52, 40, 32), desk, border_radius=8)
            pygame.draw.rect(target, C["amber"], desk, 2, border_radius=8)
            presenter = (studio.centerx, studio.centery + 5)
            pygame.draw.circle(target, (176, 158, 138), presenter, 24)
            pygame.draw.line(target, C["cyan"] if state.studio_identity else C["steel"], (presenter[0], presenter[1] + 24), (presenter[0], presenter[1] + 95), 16)
            for side in (-1, 1):
                camera = (studio.centerx + side * 350, studio.centery - 80)
                pygame.draw.circle(target, C["dark"], camera, 38)
                pygame.draw.circle(target, C["cyan"], camera, 38, 3)
                pygame.draw.line(target, C["cyan"], camera, presenter, 2)
            ticker = pygame.Rect(studio.left + 55, studio.top + 30, studio.width - 110, 58)
            pygame.draw.rect(target, (7, 20, 26), ticker)
            pygame.draw.rect(target, C["cyan"] if state.studio_identity else C["violet"], ticker, 2)
            self._text(target, "LIVE PRESENTER IDENTITY MIRRORED" if state.studio_identity else "LIVE PRESENTER TOKEN ACTIVE", (ticker.x + 42, ticker.y + 16), self.small, C["white"])
            caption = "LIVE STUDIO / PUBLIC IDENTITY HANDSHAKE"
        else:
            center = rect.center
            for radius in (235, 175, 110):
                pygame.draw.circle(target, (9, 20, 26), center, radius)
                pygame.draw.circle(target, C["cyan"] if state.broadcast_core_exposed else C["amber"], center, radius, 4)
            for angle in range(0, 360, 30):
                v = pygame.Vector2(235, 0).rotate(angle + elapsed * 20)
                color = C["cyan"] if angle % 60 == 0 else C["violet"]
                pygame.draw.line(target, color, center, (center[0] + v.x, center[1] + v.y), 2)
                pygame.draw.circle(target, color, (int(center[0] + v.x), int(center[1] + v.y)), 9)
            mast = pygame.Rect(center[0] - 25, rect.top + 90, 50, rect.height - 180)
            pygame.draw.rect(target, (18, 65, 76), mast)
            pygame.draw.rect(target, C["cyan"], mast, 2)
            caption = "PUBLIC SIGNAL CORE / SAFE TRANSMITTER REBOOT"
        self._room_caption(target, rect, caption)


    def _financial_room(self, target, rect, state, elapsed) -> None:
        if state.camera is StageCamera.SETTLEMENT_FLOOR:
            # Transaction lanes remain readable as actual moving batches, not generic data decoration.
            floor = pygame.Rect(rect.left + 85, rect.top + 75, rect.width - 170, rect.height - 175)
            pygame.draw.rect(target, (8, 16, 20), floor)
            pygame.draw.rect(target, C["line"], floor, 2)
            for lane in range(5):
                y = floor.top + 72 + lane * 92
                color = C["cyan"] if state.settlement_traced and lane == 2 else (C["amber"] if lane % 2 else C["green"])
                pygame.draw.line(target, C["steel"], (floor.left + 55, y), (floor.right - 55, y), 10)
                for packet in range(7):
                    x = floor.left + 70 + ((packet * 145 + int(elapsed * (38 + lane * 3))) % max(160, floor.width - 160))
                    pygame.draw.rect(target, color, (x, y - 14, 34, 28), border_radius=4)
                self._text(target, f"SETTLEMENT LANE {lane + 1:02d}", (floor.left + 55, y - 43), self.small, C["white"])
            batch = pygame.Rect(floor.centerx - 195, floor.bottom - 95, 390, 58)
            pygame.draw.rect(target, C["dark"], batch)
            pygame.draw.rect(target, C["green"] if state.settlement_traced else C["amber"], batch, 3)
            self._text(target, "BATCH 441 SIGNATURE TRACED" if state.settlement_traced else "BATCH 441 SIGNATURE REPEATING", (batch.x + 28, batch.y + 16), self.small, C["white"])
            caption = "SETTLEMENT FLOOR / TRANSACTION TRACE"
        elif state.camera is StageCamera.CREDENTIAL_CHAIN:
            center = pygame.Vector2(rect.centerx, rect.centery - 15)
            nodes = []
            for index in range(7):
                angle = -150 + index * 50
                distance = 245 if index % 2 == 0 else 175
                v = pygame.Vector2(distance, 0).rotate(angle)
                node = pygame.Vector2(center.x + v.x, center.y + v.y)
                nodes.append(node)
                color = C["cyan"] if state.credential_chain_rebuilt else (C["amber"] if index == 4 else C["violet"])
                pygame.draw.circle(target, color, (int(node.x), int(node.y)), 32, 4)
                self._text(target, f"B-{10 + index:02d}", (int(node.x - 24), int(node.y - 10)), self.small, C["white"])
            for index in range(len(nodes) - 1):
                pygame.draw.line(target, C["cyan"] if state.credential_chain_rebuilt else C["steel"], nodes[index], nodes[index + 1], 5)
            pygame.draw.line(target, C["cyan"] if state.credential_chain_rebuilt else C["amber"], nodes[-1], center, 5)
            pygame.draw.circle(target, C["green"] if state.credential_chain_rebuilt else C["amber"], center, 62, 4)
            self._text(target, "LIVE BROKER AUTHORITY", (center.x - 142, center.y - 12), self.small, C["white"])
            caption = "BROKER CREDENTIAL CHAIN / AUTHORITY RECONSTRUCTION"
        elif state.camera is StageCamera.AUDIT_VAULT:
            vault = pygame.Rect(rect.centerx - 430, rect.centery - 250, 860, 500)
            pygame.draw.rect(target, (11, 17, 20), vault, border_radius=10)
            pygame.draw.rect(target, C["line"], vault, 3, border_radius=10)
            for row in range(4):
                for col in range(6):
                    ledger = pygame.Rect(vault.left + 48 + col * 128, vault.top + 55 + row * 96, 94, 62)
                    accent = C["cyan"] if state.audit_vault_open else (C["green"] if (row + col) % 3 else C["amber"])
                    pygame.draw.rect(target, (5, 20, 23), ledger)
                    pygame.draw.rect(target, accent, ledger, 2)
                    pygame.draw.line(target, accent, (ledger.left + 12, ledger.centery), (ledger.right - 12, ledger.centery), 2)
            seal = pygame.Rect(vault.centerx - 180, vault.bottom - 100, 360, 62)
            pygame.draw.rect(target, C["dark"], seal)
            pygame.draw.rect(target, C["green"] if state.audit_vault_open else C["amber"], seal, 3)
            self._text(target, "READ-ONLY MIRROR OPEN" if state.audit_vault_open else "PENSION LEDGER MIRROR SEALED", (seal.x + 32, seal.y + 18), self.small, C["white"])
            caption = "AUDIT VAULT / CIVILIAN LEDGER MIRROR"
        else:
            center = rect.center
            for radius in (240, 178, 112):
                pygame.draw.circle(target, (8, 20, 23), center, radius)
                pygame.draw.circle(target, C["cyan"] if state.clearing_core_exposed else C["amber"], center, radius, 4)
            for angle in range(0, 360, 24):
                v = pygame.Vector2(240, 0).rotate(angle + elapsed * 17)
                color = C["cyan"] if angle % 48 == 0 else C["green"]
                pygame.draw.line(target, color, center, (center[0] + v.x, center[1] + v.y), 2)
                pygame.draw.rect(target, color, (int(center[0] + v.x - 7), int(center[1] + v.y - 7), 14, 14))
            core = pygame.Rect(center[0] - 30, rect.top + 88, 60, rect.height - 176)
            pygame.draw.rect(target, (18, 70, 72), core)
            pygame.draw.rect(target, C["cyan"], core, 2)
            caption = "CLEARING CORE / ISOLATED SAFE REBOOT"
        self._room_caption(target, rect, caption)

    def _clinic_room(self, target, rect, state, elapsed) -> None:
        if state.camera is StageCamera.TRIAGE_INTAKE:
            ward = pygame.Rect(rect.left + 90, rect.top + 75, rect.width - 180, rect.height - 180)
            pygame.draw.rect(target, (9, 18, 20), ward, border_radius=10)
            pygame.draw.rect(target, C["line"], ward, 2, border_radius=10)
            for row in range(2):
                for col in range(5):
                    bed = pygame.Rect(ward.left + 45 + col * 205, ward.top + 65 + row * 210, 150, 78)
                    pygame.draw.rect(target, (18, 29, 30), bed, border_radius=7)
                    pygame.draw.rect(target, C["green"], bed, 2, border_radius=7)
                    pulse = bed.left + 18 + int((elapsed * 45 + col * 17 + row * 9) % 90)
                    pygame.draw.line(target, C["cyan"], (bed.left + 18, bed.centery), (pulse, bed.centery), 2)
            gate = pygame.Rect(ward.centerx - 230, ward.bottom - 110, 460, 62)
            pygame.draw.rect(target, C["dark"], gate)
            pygame.draw.rect(target, C["green"] if state.triage_routed else C["amber"], gate, 3)
            self._text(target, "SANITIZED INTAKE TOKEN ROUTED" if state.triage_routed else "ACTIVE TRIAGE QUEUE", (gate.x + 42, gate.y + 18), self.small, C["white"])
            caption = "TRIAGE INTAKE / ACTIVE PATIENT SAFETY"
        elif state.camera is StageCamera.MEDICAL_IDENTITY:
            center = pygame.Vector2(rect.centerx, rect.centery - 10)
            profile = pygame.Rect(center.x - 180, center.y - 210, 360, 420)
            pygame.draw.rect(target, (10, 22, 24), profile, border_radius=12)
            pygame.draw.rect(target, C["cyan"] if state.medical_identity_rebuilt else C["amber"], profile, 3, border_radius=12)
            pygame.draw.circle(target, (74, 91, 92), (int(center.x), int(center.y - 90)), 58, 3)
            pygame.draw.line(target, C["cyan"], (center.x, center.y - 32), (center.x, center.y + 110), 12)
            for index, label in enumerate(("PRISONER A-17", "BIO-ID LINK", "PHYSICIAN TOKEN", "NEURAL SCAN")):
                node = pygame.Rect(rect.left + 110 + (index % 2) * 850, rect.top + 120 + (index // 2) * 300, 250, 76)
                pygame.draw.rect(target, (8, 19, 22), node)
                pygame.draw.rect(target, C["green"] if state.medical_identity_rebuilt else C["violet"], node, 2)
                self._text(target, label, (node.x + 26, node.y + 24), self.small, C["white"])
                pygame.draw.line(target, C["cyan"] if state.medical_identity_rebuilt else C["steel"], node.center, profile.center, 3)
            caption = "MEDICAL IDENTITY / PRISON BIO-ID RECONSTRUCTION"
        elif state.camera is StageCamera.LIFE_SUPPORT:
            bus = pygame.Rect(rect.left + 100, rect.top + 75, rect.width - 200, rect.height - 180)
            pygame.draw.rect(target, (7, 17, 20), bus, border_radius=10)
            pygame.draw.rect(target, C["line"], bus, 2, border_radius=10)
            systems = (("VENTILATION", C["cyan"]), ("INFUSION", C["green"]), ("OXYGEN", C["white"]), ("MONITORING", C["violet"]))
            for index, (label, color) in enumerate(systems):
                y = bus.top + 80 + index * 115
                pygame.draw.line(target, color if state.life_support_safe else C["steel"], (bus.left + 90, y), (bus.right - 90, y), 10)
                pygame.draw.circle(target, color, (bus.left + 90, y), 18, 3)
                pygame.draw.circle(target, color, (bus.right - 90, y), 18, 3)
                self._text(target, label, (bus.left + 130, y - 38), self.small, C["white"])
            badge = pygame.Rect(bus.centerx - 210, bus.bottom - 92, 420, 58)
            pygame.draw.rect(target, C["dark"], badge)
            pygame.draw.rect(target, C["green"] if state.life_support_safe else C["amber"], badge, 3)
            self._text(target, "READ-ONLY DIAGNOSTICS ACTIVE" if state.life_support_safe else "OCCUPIED CARE BUS", (badge.x + 42, badge.y + 16), self.small, C["white"])
            caption = "LIFE-SUPPORT BUS / NON-DESTRUCTIVE DIAGNOSTICS"
        else:
            center = rect.center
            for radius in (235, 175, 112):
                pygame.draw.circle(target, (7, 21, 22), center, radius)
                pygame.draw.circle(target, C["cyan"] if state.biological_archive_exposed else C["green"], center, radius, 4)
            helix = []
            for i in range(32):
                y = rect.top + 105 + i * (rect.height - 210) / 31
                x = center[0] + math.sin(i * 0.72 + elapsed * 0.8) * 115
                helix.append((int(x), int(y)))
            pygame.draw.lines(target, C["cyan"], False, helix, 4)
            mirror = [(2 * center[0] - x, y) for x, y in helix]
            pygame.draw.lines(target, C["violet"], False, mirror, 4)
            for a, b in zip(helix[::3], mirror[::3]):
                pygame.draw.line(target, C["green"], a, b, 2)
            self._text(target, "PRISON BIOLOGICAL FILE A-17", (center[0] - 230, rect.bottom - 135), self.medium, C["white"])
            caption = "BIOLOGICAL ARCHIVE / ISOLATED SAFE REBOOT"
        self._room_caption(target, rect, caption)

    def _factory_room(self, target, rect, state, elapsed) -> None:
        if state.camera is StageCamera.MATERIAL_INTAKE:
            belt = pygame.Rect(rect.left + 90, rect.centery - 90, rect.width - 180, 180)
            pygame.draw.rect(target, (12, 20, 22), belt, border_radius=8)
            pygame.draw.rect(target, C["line"], belt, 2, border_radius=8)
            for index in range(9):
                x = belt.left + 45 + index * 125
                pygame.draw.circle(target, C["steel"], (x, belt.bottom - 28), 18, 3)
                crate = pygame.Rect(x - 38, belt.top + 38 + (index % 2) * 18, 76, 62)
                pygame.draw.rect(target, (43, 38, 31), crate)
                pygame.draw.rect(target, C["amber"], crate, 2)
            scanner = pygame.Rect(belt.left + 45, belt.top - 95, 310, 68)
            pygame.draw.rect(target, C["dark"], scanner)
            pygame.draw.rect(target, C["green"] if state.intake_manifest_replayed else C["amber"], scanner, 3)
            self._text(target, "SIGNED MANIFEST F-91" if state.intake_manifest_replayed else "MATERIAL INTAKE AUTHORITY", (scanner.x + 28, scanner.y + 20), self.small, C["white"])
            caption = "MATERIAL INTAKE / SIGNED LOGISTICS SEQUENCE"
        elif state.camera is StageCamera.ASSEMBLY_LINE:
            cell = pygame.Rect(rect.left + 90, rect.top + 70, rect.width - 180, rect.height - 175)
            pygame.draw.rect(target, (10, 18, 20), cell, border_radius=8)
            pygame.draw.rect(target, C["line"], cell, 2, border_radius=8)
            for index in range(5):
                base_x = cell.left + 130 + index * 225
                pygame.draw.circle(target, C["steel"], (base_x, cell.bottom - 90), 34, 3)
                arm_end = pygame.Vector2(0, -115).rotate(math.sin(elapsed * 1.4 + index) * 34)
                color = C["green"] if state.assembly_service_hold else C["amber"]
                pygame.draw.line(target, color, (base_x, cell.bottom - 90), (base_x + arm_end.x, cell.bottom - 90 + arm_end.y), 14)
                pygame.draw.circle(target, color, (int(base_x + arm_end.x), int(cell.bottom - 90 + arm_end.y)), 16, 3)
            curtain = pygame.Rect(cell.left + 30, cell.top + 24, cell.width - 60, 36)
            pygame.draw.rect(target, (38, 25, 10), curtain)
            pygame.draw.rect(target, C["green"] if state.assembly_service_hold else C["red"], curtain, 3)
            self._text(target, "CERTIFIED SERVICE HOLD" if state.assembly_service_hold else "ROBOT CELL ACTIVE / TECHNICIANS PRESENT", (curtain.x + 60, curtain.y + 7), self.small, C["white"])
            caption = "ASSEMBLY LINE / OCCUPIED ROBOT CELL 04"
        elif state.camera is StageCamera.SAFETY_CONTROLLER:
            core = pygame.Rect(rect.centerx - 260, rect.centery - 210, 520, 420)
            pygame.draw.rect(target, (8, 20, 22), core, border_radius=12)
            pygame.draw.rect(target, C["green"] if state.safety_interlock_claimed else C["amber"], core, 4, border_radius=12)
            for index, label in enumerate(("EMERGENCY STOP", "CURTAIN GRID", "HUMAN ZONE", "ROBOT HOLD")):
                node = pygame.Rect(rect.left + 80 + (index % 2) * 940, rect.top + 130 + (index // 2) * 310, 280, 82)
                pygame.draw.rect(target, (10, 18, 20), node)
                pygame.draw.rect(target, C["green"] if state.safety_interlock_claimed else C["violet"], node, 3)
                self._text(target, label, (node.x + 30, node.y + 26), self.small, C["white"])
                pygame.draw.line(target, C["cyan"], node.center, core.center, 3)
            self._text(target, "LIVE SUPERVISOR TOKEN S-04" if state.safety_interlock_claimed else "SAFETY AUTHORITY HANDSHAKE REQUIRED", (core.x + 42, core.centery - 12), self.small, C["white"])
            caption = "WORKER SAFETY CONTROLLER / LIVE INTERLOCK"
        else:
            center = rect.center
            for radius in (245, 180, 118):
                pygame.draw.circle(target, (8, 19, 21), center, radius)
                pygame.draw.circle(target, C["cyan"] if state.factory_core_exposed else C["amber"], center, radius, 4)
            for angle in range(0, 360, 30):
                v = pygame.Vector2(245, 0).rotate(angle + elapsed * 11)
                pygame.draw.line(target, C["cyan"], center, (center[0] + v.x, center[1] + v.y), 2)
            column = pygame.Rect(center[0] - 38, rect.top + 90, 76, rect.height - 180)
            pygame.draw.rect(target, (20, 64, 68), column)
            pygame.draw.rect(target, C["white"], column, 2)
            self._text(target, "ISOLATED PRODUCTION CORE", (center[0] - 220, rect.bottom - 130), self.medium, C["white"])
            caption = "FACTORY CORE / ISOLATED SAFE REBOOT"
        self._room_caption(target, rect, caption)

    def _power_room(self, target, rect, state, elapsed) -> None:
        if state.camera is StageCamera.LOAD_DISPATCH:
            board = pygame.Rect(rect.left + 80, rect.top + 70, rect.width - 160, rect.height - 190)
            pygame.draw.rect(target, (8, 16, 20), board, border_radius=10)
            pygame.draw.rect(target, C["line"], board, 3, border_radius=10)
            labels = ("CLINIC", "TRANSIT", "RESIDENTIAL", "INDUSTRIAL", "ARCHIVE")
            for index, label in enumerate(labels):
                y = board.top + 68 + index * 86
                critical = index < 3
                color = C["green"] if critical else C["amber"]
                pygame.draw.rect(target, (12, 24, 27), (board.left + 42, y, board.width - 84, 52))
                width = int((board.width - 84) * (0.55 + 0.08 * math.sin(elapsed + index)))
                pygame.draw.rect(target, color, (board.left + 42, y, width, 52), 2)
                self._text(target, f"{label} FEED", (board.left + 62, y + 13), self.small, C["white"])
                self._text(target, "CRITICAL" if critical else "SHED READY", (board.right - 220, y + 13), self.small, color)
            caption = "LOAD DISPATCH / SIGNED SHED SEQUENCE L-22"
        elif state.camera is StageCamera.SWITCHYARD:
            yard = pygame.Rect(rect.left + 70, rect.top + 70, rect.width - 140, rect.height - 180)
            pygame.draw.rect(target, (11, 17, 19), yard)
            pygame.draw.rect(target, C["line"], yard, 2)
            for index in range(6):
                x = yard.left + 100 + index * 190
                pygame.draw.line(target, C["amber"], (x, yard.top + 70), (x, yard.bottom - 90), 5)
                pygame.draw.circle(target, C["cyan"] if state.switchyard_isolated and index == 5 else C["amber"], (x, yard.centery), 35, 4)
                pygame.draw.line(target, C["white"], (x - 45, yard.centery - 65), (x + 45, yard.centery + 65), 3)
            tag = pygame.Rect(yard.centerx - 250, yard.top + 22, 500, 52)
            pygame.draw.rect(target, C["dark"], tag)
            pygame.draw.rect(target, C["green"] if state.switchyard_isolated else C["red"], tag, 3)
            label = "BREAKER BANK 06 SERVICE BYPASS" if state.switchyard_isolated else "ENERGIZED SWITCHYARD / RESIDENTIAL TIE LIVE"
            self._text(target, label, (tag.x + 26, tag.y + 13), self.small, C["white"])
            caption = "SWITCHYARD / ENERGIZED BREAKER ISOLATION"
        elif state.camera is StageCamera.CRITICAL_FEEDERS:
            center = rect.center
            core = pygame.Rect(center[0] - 170, center[1] - 105, 340, 210)
            pygame.draw.rect(target, (7, 20, 24), core, border_radius=14)
            pygame.draw.rect(target, C["green"] if state.critical_feeders_protected else C["violet"], core, 4, border_radius=14)
            feeders = (
                (rect.left + 180, rect.top + 190, "CLINIC"),
                (rect.right - 180, rect.top + 190, "TRANSIT"),
                (rect.left + 180, rect.bottom - 210, "HOMES"),
                (rect.right - 180, rect.bottom - 210, "RESERVE"),
            )
            for x, y, label in feeders:
                color = C["green"] if state.critical_feeders_protected else C["red"]
                pygame.draw.circle(target, (10, 18, 20), (x, y), 66)
                pygame.draw.circle(target, color, (x, y), 66, 4)
                pygame.draw.line(target, C["cyan"], (x, y), core.center, 4)
                self._text(target, label, (x - 48, y - 12), self.small, C["white"])
            label = "LIVE GRID SUPERVISOR G-12" if state.critical_feeders_protected else "CRITICAL FEEDER AUTHORITY REQUIRED"
            self._text(target, label, (core.x + 28, core.centery - 12), self.small, C["white"])
            caption = "CRITICAL FEEDERS / OCCUPIED CITY SERVICES"
        else:
            center = rect.center
            for radius in (260, 195, 130, 65):
                pygame.draw.circle(target, (7, 18, 22), center, radius)
                pygame.draw.circle(target, C["cyan"] if state.distribution_core_exposed else C["amber"], center, radius, 4)
            for angle in range(0, 360, 30):
                v = pygame.Vector2(260, 0).rotate(angle + elapsed * 10)
                pygame.draw.line(target, C["cyan"], center, (center[0] + v.x, center[1] + v.y), 2)
            bolt = [
                (center[0]-35, center[1]-130), (center[0]+35, center[1]-35),
                (center[0]-8, center[1]-35), (center[0]+42, center[1]+130),
                (center[0]-48, center[1]+22), (center[0]-4, center[1]+22),
            ]
            pygame.draw.polygon(target, C["white"], bolt)
            caption = "DISTRIBUTION CORE / ISOLATED COLD RESTART"
        self._room_caption(target, rect, caption)

    def _drone_assembly_room(self, target, rect, state, elapsed) -> None:
        if state.camera is StageCamera.PARTS_REGISTRY:
            manifest = pygame.Rect(rect.left + 85, rect.top + 55, rect.width - 170, 92)
            pygame.draw.rect(target, (7, 18, 22), manifest, border_radius=8)
            pygame.draw.rect(target, C["green"] if state.parts_receipt_replayed else C["amber"], manifest, 3, border_radius=8)
            self._text(target, "SIGNED RETURN RECEIPT D-77" if state.parts_receipt_replayed else "DOCKED HOST INVENTORY / RECEIPT REQUIRED", (manifest.x + 36, manifest.y + 28), self.medium, C["white"])
            for index in range(8):
                row, col = divmod(index, 4)
                pod = pygame.Rect(rect.left + 105 + col * 295, rect.top + 205 + row * 235, 225, 178)
                pygame.draw.rect(target, (10, 18, 21), pod, border_radius=12)
                pygame.draw.rect(target, C["cyan"] if state.parts_receipt_replayed else C["line"], pod, 3, border_radius=12)
                center = pod.center
                pygame.draw.circle(target, C["steel"], center, 38)
                pygame.draw.circle(target, C["cyan"], center, 38, 3)
                pygame.draw.line(target, C["cyan"], (center[0]-62, center[1]), (center[0]+62, center[1]), 5)
                pygame.draw.circle(target, C["white"], center, 8)
                self._text(target, f"HOST D-{70+index:02d} / DOCKED", (pod.x + 22, pod.bottom - 36), self.small, C["muted"])
            caption = "PARTS REGISTRY / DOCKED FLIGHT HOSTS"
        elif state.camera is StageCamera.CALIBRATION_GANTRY:
            cage = pygame.Rect(rect.left + 75, rect.top + 65, rect.width - 150, rect.height - 175)
            pygame.draw.rect(target, (8, 15, 18), cage, border_radius=10)
            pygame.draw.rect(target, C["green"] if state.calibration_hold_engaged else C["red"], cage, 4, border_radius=10)
            rail_y = cage.top + 120
            pygame.draw.line(target, C["amber"], (cage.left+55, rail_y), (cage.right-55, rail_y), 8)
            for index in range(5):
                base_x = cage.left + 135 + index * 235
                travel = 0 if state.calibration_hold_engaged else math.sin(elapsed * 1.2 + index) * 48
                center = (int(base_x + travel), cage.centery + 30 + (index % 2) * 34)
                pygame.draw.line(target, C["amber"], (base_x, rail_y), center, 4)
                pygame.draw.circle(target, (12, 24, 28), center, 48)
                pygame.draw.circle(target, C["green"] if state.calibration_hold_engaged else C["cyan"], center, 48, 4)
                pygame.draw.line(target, C["cyan"], (center[0]-74, center[1]), (center[0]+74, center[1]), 5)
            for index in range(3):
                x = cage.left + 210 + index * 390
                y = cage.bottom - 70
                pygame.draw.circle(target, C["white"], (x, y-22), 11, 2)
                pygame.draw.line(target, C["white"], (x, y-10), (x, y+26), 3)
                pygame.draw.line(target, C["white"], (x, y+4), (x-18, y+22), 3)
                pygame.draw.line(target, C["white"], (x, y+4), (x+18, y+22), 3)
            status = "CERTIFIED SERVICE HOLD / TECHNICIANS SAFE" if state.calibration_hold_engaged else "GANTRY 03 ACTIVE / THREE TECHNICIANS PRESENT"
            self._text(target, status, (cage.left + 180, cage.top + 38), self.medium, C["green"] if state.calibration_hold_engaged else C["red"])
            caption = "CALIBRATION GANTRY / OCCUPIED FLIGHT TEST CAGE"
        elif state.camera is StageCamera.IDENTITY_IMPRINT:
            core = pygame.Rect(rect.centerx - 250, rect.centery - 150, 500, 300)
            pygame.draw.rect(target, (6, 18, 22), core, border_radius=18)
            pygame.draw.rect(target, C["green"] if state.rescue_identities_protected else C["violet"], core, 5, border_radius=18)
            identities = (("RESCUE-01", -440, -180), ("MED-04", 440, -180), ("FIRE-12", -480, 40), ("SEARCH-08", 480, 40), ("TRANSIT-03", -360, 250), ("RELIEF-09", 360, 250))
            for label, dx, dy in identities:
                center = (rect.centerx + dx, rect.centery + dy)
                color = C["green"] if state.rescue_identities_protected else C["cyan"]
                pygame.draw.circle(target, (8, 18, 21), center, 58)
                pygame.draw.circle(target, color, center, 58, 4)
                pygame.draw.line(target, C["cyan"], center, core.center, 3)
                self._text(target, label, (center[0]-58, center[1]-12), self.small, C["white"])
            label = "QA SUPERVISOR Q-09 / IDENTITIES PRESERVED" if state.rescue_identities_protected else "ACTIVE NAVIGATION MINDS / LIVE AUTHORITY REQUIRED"
            self._text(target, label, (core.x + 30, core.centery - 12), self.small, C["white"])
            caption = "IDENTITY IMPRINT / ACTIVE RESCUE NAVIGATION MINDS"
        else:
            center = rect.center
            for radius in (280, 205, 135, 70):
                pygame.draw.circle(target, (6, 18, 22), center, radius)
                pygame.draw.circle(target, C["cyan"] if state.flight_core_exposed else C["amber"], center, radius, 4)
            for index in range(10):
                angle = elapsed * 18 + index * 36
                v = pygame.Vector2(245, 0).rotate(angle)
                p = (int(center[0]+v.x), int(center[1]+v.y))
                pygame.draw.circle(target, C["green"], p, 10)
            pygame.draw.circle(target, (12, 28, 34), center, 48)
            pygame.draw.circle(target, C["white"], center, 48, 4)
            pygame.draw.line(target, C["white"], (center[0]-100, center[1]), (center[0]+100, center[1]), 7)
            pygame.draw.line(target, C["cyan"], (center[0], center[1]-70), (center[0], center[1]+70), 5)
            self._text(target, "ISOLATED FLIGHT CONTROL CORE", (center[0]-220, rect.bottom-130), self.medium, C["white"])
            caption = "FLIGHT CONTROL CORE / IDENTITY-SAFE COLD BOOT"
        self._room_caption(target, rect, caption)


    def _waste_processing_room(self, target, rect, state, elapsed) -> None:
        if state.camera is StageCamera.RECEIVING_SCALE:
            deck = pygame.Rect(rect.left + 85, rect.top + 105, rect.width - 170, rect.height - 250)
            pygame.draw.rect(target, (18, 22, 20), deck, border_radius=10)
            pygame.draw.rect(target, C["line"], deck, 3, border_radius=10)
            for index in range(5):
                bin_rect = pygame.Rect(deck.left + 65 + index * 230, deck.top + 155 + (index % 2) * 35, 155, 115)
                pygame.draw.rect(target, (34, 40, 35), bin_rect, border_radius=8)
                pygame.draw.rect(target, C["amber"], bin_rect, 3, border_radius=8)
                self._text(target, ("METAL","POLYMER","GLASS","ORGANIC","SEALED")[index], (bin_rect.x + 22, bin_rect.y + 44), self.small, C["white"])
            scale = pygame.Rect(deck.left + 85, deck.top + 35, deck.width - 170, 62)
            pygame.draw.rect(target, C["dark"], scale)
            pygame.draw.rect(target, C["green"] if state.waste_manifest_replayed else C["amber"], scale, 3)
            self._text(target, "SIGNED TRANSFER W-44 ACCEPTED" if state.waste_manifest_replayed else "SEALED LOAD / AUTHORITY REQUIRED", (scale.x + 185, scale.y + 17), self.small, C["white"])
            caption = "RECEIVING SCALE / SEALED MATERIAL INTAKE"
        elif state.camera is StageCamera.SORTING_CONVEYOR:
            line = pygame.Rect(rect.left + 70, rect.top + 80, rect.width - 140, rect.height - 195)
            pygame.draw.rect(target, (9, 16, 17), line, border_radius=10)
            pygame.draw.rect(target, C["green"] if state.conveyor_lockout_engaged else C["red"], line, 4, border_radius=10)
            belt_y = line.centery + 40
            pygame.draw.line(target, C["steel"], (line.left + 60, belt_y), (line.right - 60, belt_y), 34)
            for index in range(10):
                x = line.left + 95 + index * 118
                pygame.draw.circle(target, C["amber"], (x, belt_y), 18, 3)
                item = pygame.Rect(x-24, belt_y-90-(index%3)*18, 48, 48)
                pygame.draw.rect(target, (38, 42, 36), item)
                pygame.draw.rect(target, C["cyan"], item, 2)
            for index in range(4):
                x = line.left + 210 + index * 285
                y = line.bottom - 68
                pygame.draw.circle(target, C["white"], (x, y-22), 11, 2)
                pygame.draw.line(target, C["white"], (x, y-10), (x, y+28), 3)
                pygame.draw.line(target, C["white"], (x, y+3), (x-18, y+24), 3)
                pygame.draw.line(target, C["white"], (x, y+3), (x+18, y+24), 3)
            status = "LOCKOUT/TAGOUT ACTIVE / TECHNICIANS SAFE" if state.conveyor_lockout_engaged else "CONVEYOR 02 JAM CLEAR / FOUR TECHNICIANS PRESENT"
            self._text(target, status, (line.left + 170, line.top + 30), self.medium, C["green"] if state.conveyor_lockout_engaged else C["red"])
            caption = "SORTING CONVEYOR / OCCUPIED JAM-CLEAR ZONE"
        elif state.camera is StageCamera.LEACHATE_CONTROL:
            center = rect.center
            tanks = []
            for index, (label, dx, dy) in enumerate((("RAW",-430,-170),("FILTER",430,-170),("BIO",-430,180),("CLEAN",430,180))):
                c=(center[0]+dx,center[1]+dy)
                tanks.append(c)
                color=C["green"] if state.leachate_contained else (C["amber"] if index<3 else C["cyan"])
                pygame.draw.circle(target,(9,24,21),c,82)
                pygame.draw.circle(target,color,c,82,4)
                self._text(target,label,(c[0]-38,c[1]-12),self.medium,C["white"])
            pump=pygame.Rect(center[0]-210,center[1]-115,420,230)
            pygame.draw.rect(target,(6,20,20),pump,border_radius=18)
            pygame.draw.rect(target,C["green"] if state.leachate_contained else C["violet"],pump,5,border_radius=18)
            for c in tanks:
                pygame.draw.line(target,C["cyan"],c,pump.center,4)
            self._text(target,"SEALED HOLDING LOOP PROTECTED" if state.leachate_contained else "ACTIVE TREATMENT PUMPS / LIVE AUTHORITY REQUIRED",(pump.x+34,pump.centery-12),self.small,C["white"])
            caption = "LEACHATE CONTROL / SEALED LIQUID TREATMENT"
        else:
            center=rect.center
            for radius in (285,215,145,78):
                pygame.draw.circle(target,(7,20,18),center,radius)
                pygame.draw.circle(target,C["green"] if state.recovery_core_exposed else C["amber"],center,radius,4)
            for index in range(12):
                angle=elapsed*14+index*30
                v=pygame.Vector2(250,0).rotate(angle)
                p=(int(center[0]+v.x),int(center[1]+v.y))
                pygame.draw.rect(target,C["cyan"],(p[0]-9,p[1]-9,18,18),2)
            pygame.draw.circle(target,(20,35,30),center,54)
            pygame.draw.circle(target,C["white"],center,54,4)
            self._text(target,"ISOLATED MATERIAL RECOVERY CORE",(center[0]-245,rect.bottom-130),self.medium,C["white"])
            caption = "RECOVERY CORE / CONTAINMENT-SAFE COLD RESTART"
        self._room_caption(target, rect, caption)

    def _room_caption(self, target, rect, caption: str) -> None:
        self._text(target, caption, (rect.left + 90, rect.bottom - 82), self.medium, C["white"])
        self._text(target, "SELECT METHOD 4–8 • E EXECUTE", (rect.left + 90, rect.bottom - 42), self.small, C["cyan"])

    def _sidebar(self, target: pygame.Surface, state: BuildingStageState) -> None:
        rect = pygame.Rect(1490, 120, 360, 790)
        pygame.draw.rect(target, C["panel"], rect)
        pygame.draw.rect(target, C["line"], rect, 2)
        self._text(target, "CAMERA CHAIN", (rect.x + 24, rect.y + 22), self.medium, C["white"])
        if state.building_id == "maintenance_depot":
            labels = [("1", "YARD", True), ("2", "REPAIR FLOOR", state.door_open), ("3", "DRONE LINK", state.drone_unlocked), ("TAB", "DEPOT CORE", state.bridge_connected)]
        elif state.building_id == "transit_substation":
            labels = [("1", "PLATFORM", True), ("2", "SERVICE CONTROL", state.platform_secured), ("3", "ROUTING CORE", state.service_window_open), ("TAB", "ROOFTOP UPLINK", state.uplink_exposed)]
        elif state.building_id == "corporate_mall":
            labels = [("1", "PUBLIC ATRIUM", True), ("2", "AD GRID", state.atrium_access), ("3", "IDENTITY GALLERY", state.ads_rerouted), ("TAB", "RETAIL CORE", state.mall_core_exposed)]
        elif state.building_id == "media_broadcast":
            labels = [("1", "PROGRAM INGEST", True), ("2", "ALERT ROUTER", state.feed_looped), ("3", "LIVE STUDIO", state.alert_routed), ("TAB", "SIGNAL CORE", state.broadcast_core_exposed)]
        elif state.building_id == "financial_exchange":
            labels = [("1", "SETTLEMENT FLOOR", True), ("2", "CREDENTIAL CHAIN", state.settlement_traced), ("3", "AUDIT VAULT", state.credential_chain_rebuilt), ("TAB", "CLEARING CORE", state.clearing_core_exposed)]
        elif state.building_id == "private_clinic":
            labels = [("1", "TRIAGE INTAKE", True), ("2", "MEDICAL IDENTITY", state.triage_routed), ("3", "LIFE SUPPORT", state.medical_identity_rebuilt), ("TAB", "BIO ARCHIVE", state.biological_archive_exposed)]
        elif state.building_id == "automated_factory":
            labels = [("1", "MATERIAL INTAKE", True), ("2", "ASSEMBLY LINE", state.intake_manifest_replayed), ("3", "SAFETY CONTROL", state.assembly_service_hold), ("TAB", "FACTORY CORE", state.factory_core_exposed)]
        elif state.building_id == "power_distribution_plant":
            labels = [("1", "LOAD DISPATCH", True), ("2", "SWITCHYARD", state.dispatch_pattern_replayed), ("3", "CRITICAL FEEDERS", state.switchyard_isolated), ("TAB", "DISTRIBUTION CORE", state.distribution_core_exposed)]
        elif state.building_id == "drone_assembly_facility":
            labels = [("1", "PARTS REGISTRY", True), ("2", "CALIBRATION", state.parts_receipt_replayed), ("3", "IDENTITY IMPRINT", state.calibration_hold_engaged), ("TAB", "FLIGHT CORE", state.flight_core_exposed)]
        elif state.building_id == "waste_processing_complex":
            labels = [("1", "RECEIVING SCALE", True), ("2", "SORTING LINE", state.waste_manifest_replayed), ("3", "LEACHATE CONTROL", state.conveyor_lockout_engaged), ("TAB", "RECOVERY CORE", state.recovery_core_exposed)]
        else:
            labels = [("1", "EXTERIOR", True), ("2", "OPERATIONS", state.door_open), ("3", "CORE", state.core_exposed)]
        for index, (key, label, available) in enumerate(labels):
            y = rect.y + 70 + index * 48
            color = C["cyan"] if available else C["muted"]
            pygame.draw.rect(target, (10, 19, 23), (rect.x + 22, y, 316, 38))
            pygame.draw.rect(target, color, (rect.x + 22, y, 316, 38), 2)
            self._text(target, f"{key} {label}", (rect.x + 36, y + 8), self.small, color)
        evidence_y = rect.y + (278 if len(labels) == 4 else 228)
        self._text(target, "OBSERVED EVIDENCE", (rect.x + 24, evidence_y), self.small, C["amber"])
        clue_y = evidence_y + 34
        for clue in state.clues:
            lines = self._wrap(clue, 29)
            pygame.draw.circle(target, C["cyan"], (rect.x + 32, clue_y + 12), 5)
            for line_index, line in enumerate(lines):
                self._text(target, line, (rect.x + 46, clue_y + line_index * 24), self.small, C["white"])
            clue_y += len(lines) * 24 + 16
        method_y = max(evidence_y + 154, clue_y + 4)
        self._text(target, "INTRUSION METHOD", (rect.x + 24, method_y), self.small, C["amber"])
        for index, method in enumerate(METHODS):
            y = method_y + 34 + index * 40
            selected = method.method_id == state.selected_method_id
            color = C["cyan"] if selected else C["muted"]
            pygame.draw.rect(target, (8, 17, 21), (rect.x + 22, y, 316, 34))
            pygame.draw.rect(target, color, (rect.x + 22, y, 316, 34), 2 if selected else 1)
            self._text(target, f"{method.key} {method.label}", (rect.x + 34, y + 6), self.small, color)
        self._text(target, "RESULT", (rect.x + 24, rect.bottom - 98), self.small, C["amber"])
        result_color = {
            HackOutcome.CLEAN: C["green"],
            HackOutcome.NOISY: C["amber"],
            HackOutcome.REJECTED: C["muted"],
            HackOutcome.GLEEBS_VIOLATION: C["violet"],
        }.get(state.last_outcome, C["white"])
        result = state.last_outcome.value.replace("_", " ").upper() if state.last_outcome else "AWAITING EXECUTION"
        self._text(target, result, (rect.x + 24, rect.bottom - 66), self.small, result_color)

    def _footer(self, target: pygame.Surface, state: BuildingStageState) -> None:
        pygame.draw.line(target, C["line"], (0, 970), (1920, 970), 1)
        controls = "1–3 CAMERA • TAB CAMERA 04 • 4–8 METHOD • E EXECUTE • F1 HELP • F2 SETTINGS • ESC PAUSE" if len(state.camera_chain) == 4 else "1/2/3 CAMERA • 4–8 SELECT METHOD • E EXECUTE • F1 HELP • F2 SETTINGS • ESC PAUSE"
        if state.building_id == "maintenance_depot":
            controls = "1–3 CAMERA • TAB DEPOT CORE • WASD DRONE • 4–8 METHOD • E EXECUTE • F2 SETTINGS"
        self._text(target, controls, (70, 1000), self.small, C["muted"])
        if state.captured:
            shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA)
            shade.fill((0, 18, 22, 180))
            target.blit(shade, (0, 0))
            if state.building_id == "maintenance_depot":
                headline, reward = "MAINTENANCE YARD CAPTURED", "TRANSIT DEPOT UNLOCKED"
            elif state.building_id == "transit_substation":
                headline, reward = "TRANSIT DEPOT CAPTURED", "MUNICIPAL FRINGE CONTROLLED"
            elif state.building_id == "corporate_mall":
                headline, reward = "CORPORATE MALL CAPTURED", "MEDIA BROADCAST BREACH AVAILABLE"
            elif state.building_id == "media_broadcast":
                headline, reward = "MEDIA BROADCAST CAPTURED", "FINANCIAL EXCHANGE UNLOCKED"
            elif state.building_id == "financial_exchange":
                headline, reward = "FINANCIAL EXCHANGE CAPTURED", "PRIVATE CLINIC UNLOCKED"
            elif state.building_id == "private_clinic":
                headline, reward = "PRIVATE CLINIC CAPTURED", "COMMERCIAL SPINE CONTROLLED"
            elif state.building_id == "automated_factory":
                headline, reward = "AUTOMATED FACTORY CAPTURED", "POWER DISTRIBUTION PLANT UNLOCKED"
            elif state.building_id == "power_distribution_plant":
                headline, reward = "POWER DISTRIBUTION PLANT CAPTURED", "DRONE ASSEMBLY FACILITY UNLOCKED"
            elif state.building_id == "drone_assembly_facility":
                headline, reward = "DRONE ASSEMBLY FACILITY CAPTURED", "WASTE PROCESSING COMPLEX UNLOCKED"
            elif state.building_id == "waste_processing_complex":
                headline, reward = "WASTE PROCESSING COMPLEX CAPTURED", "INDUSTRIAL GRID CONTROL READY"
            else:
                headline, reward = "ANNEX CAPTURED", "MAINTENANCE YARD UNLOCKED"
            self._text(target, headline, (500, 420), self.large, C["cyan"])
            self._text(target, reward, (590, 500), self.medium, C["white"])
            self._text(target, "PRESS ENTER TO RETURN TO CITY", (605, 565), self.small, C["amber"])
        elif state.failed:
            shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA)
            shade.fill((28, 0, 0, 185))
            target.blit(shade, (0, 0))
            self._text(target, "SIGNAL LOST", (730, 420), self.large, C["red"])
            self._text(target, "PRESS ENTER TO RETURN TO CITY", (605, 520), self.small, C["white"])

    def _status_strip(self, target: pygame.Surface, state: BuildingStageState, high_contrast: bool = False) -> None:
        if state.captured or state.failed or state.gleebs_ejected:
            return
        panel = pygame.Rect(70, 922, 1780, 42)
        pygame.draw.rect(target, (4, 11, 15), panel)
        color = {
            HackOutcome.CLEAN: C["green"],
            HackOutcome.NOISY: C["amber"],
            HackOutcome.REJECTED: C["muted"],
            HackOutcome.GLEEBS_VIOLATION: C["violet"],
        }.get(state.last_outcome, C["cyan"])
        pygame.draw.rect(target, C["white"] if high_contrast else color, panel, 3 if high_contrast else 2)
        self._text(target, state.message, (panel.x + 18, panel.y + 9), self.small, C["white"])

    def _onboarding_card(self, target: pygame.Surface, state: BuildingStageState, step: int) -> None:
        if state.building_id != "surveillance_annex" or step not in (2, 3, 4):
            return
        panel = pygame.Rect(430, 126, 820, 94)
        pygame.draw.rect(target, (3, 10, 15), panel)
        pygame.draw.rect(target, C["cyan"], panel, 3)
        if step == 2:
            title = "SIGNAL GUIDE 2/4 • READ THE SYSTEM"
            line = "SERVICE WINDOW ACTIVE + REMOTE ADMIN DISABLED → PRESS 5 MAINTENANCE BYPASS"
        elif step == 3:
            title = "SIGNAL GUIDE 3/4 • EXECUTE"
            line = "MAINTENANCE BYPASS ARMED → PRESS E TO OPEN THE SERVICE DOOR"
        else:
            title = "SIGNAL GUIDE 4/4 • FOLLOW THE CAMERA CHAIN"
            line = "CLEAN ACCESS UNLOCKED OPERATIONS → PRESS 2 • THEN FOLLOW EVIDENCE"
        self._text(target, title, (panel.x + 20, panel.y + 15), self.small, C["amber"])
        self._text(target, line, (panel.x + 20, panel.y + 49), self.small, C["white"])
        self._text(target, "G SKIP", (panel.right - 110, panel.y + 15), self.small, C["muted"])

    def _outcome_overlay(self, target, state) -> None:
        if state.last_outcome is not HackOutcome.GLEEBS_VIOLATION or state.failed or state.gleebs_ejected:
            return
        panel = pygame.Rect(390, 760, 980, 120)
        shade = pygame.Surface(panel.size, pygame.SRCALPHA)
        shade.fill((28, 4, 34, 222))
        target.blit(shade, panel.topleft)
        pygame.draw.rect(target, C["violet"], panel, 3)
        pygame.draw.line(target, C["green"], panel.topleft, panel.bottomright, 2)
        self._text(target, "GLEEBS INTEGRITY WARNING", (panel.x + 28, panel.y + 18), self.medium, C["green"])
        for index, line in enumerate(self._wrap(state.detection_cause, 58)):
            self._text(target, line, (panel.x + 28, panel.y + 62 + index * 26), self.small, C["white"])

    def _ejection_overlay(
        self,
        target,
        state,
        elapsed,
        reduced_glitch: bool = False,
        reduced_flashing: bool = False,
    ) -> None:
        shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA)
        shade.fill((25, 0, 32, 210))
        target.blit(shade, (0, 0))
        spacing = 92 if reduced_flashing else (76 if reduced_glitch else 38)
        amplitude = 0 if reduced_flashing else (22 if reduced_glitch else 70)
        rate = 0 if reduced_flashing else (7 if reduced_glitch else 18)
        for y in range(70, 930, spacing):
            shift = int(math.sin(elapsed * rate + y) * amplitude)
            pygame.draw.line(target, C["violet"], (max(0, shift), y), (min(1920, 1920 + shift), y), 2)
            if y % 76 == 0:
                pygame.draw.line(target, C["green"], (0, y + 8), (1920, y + 8), 1)
        cx, cy = 960, 390
        pygame.draw.polygon(target, (3, 5, 7), [(cx - 150, cy + 90), (cx - 105, cy - 85), (cx - 48, cy - 125), (cx, cy - 62), (cx + 52, cy - 128), (cx + 112, cy - 80), (cx + 155, cy + 92)])
        pygame.draw.polygon(target, C["white"], [(cx - 78, cy - 8), (cx - 20, cy + 10), (cx - 62, cy + 40)])
        pygame.draw.polygon(target, C["white"], [(cx + 78, cy - 8), (cx + 20, cy + 10), (cx + 62, cy + 40)])
        self._text(target, "GLEEBS HAS THE FEED", (560, 590), self.large, C["green"])
        line = state.gleebs_message or (
            "THERE ARE PEOPLE ON THOSE LINES, ANDREW." if state.building_id == "transit_substation"
            else "A CROWD IS NOT A PASSWORD, ANDREW." if state.building_id == "corporate_mall"
            else "A WARNING IS NOT YOUR VOICE, ANDREW." if state.building_id == "media_broadcast"
            else "PEOPLE ARE NOT NUMBERS YOU CAN ZERO, ANDREW." if state.building_id == "financial_exchange"
            else "THOSE HEARTBEATS ARE NOT YOUR CHECKSUM, ANDREW." if state.building_id == "private_clinic"
            else "THOSE ARMS ARE STILL MOVING, ANDREW." if state.building_id == "automated_factory"
            else "YOU DO NOT GET TO TURN THEM OFF TO FIND YOURSELF." if state.building_id == "power_distribution_plant"
            else "THEY ARE NOT EMPTY JUST BECAUSE THEY ARE MADE OF METAL." if state.building_id == "drone_assembly_facility"
            else "THE POISON DOES NOT VANISH WHEN YOU TURN OFF THE PUMPS." if state.building_id == "waste_processing_complex"
            else "YOU DO NOT GET THIS BUILDING YET."
        )
        self._text(target, line, (525, 675), self.medium, C["white"])
        self._text(target, state.detection_cause, (390, 735), self.small, C["violet"])
        self._text(target, "FORCING SIGNAL BACK TO SATELLITE...", (650, 805), self.small, C["cyan"])

    def _feed_vignette(self, target, rect, reduced_motion: bool) -> None:
        vignette = pygame.Surface(rect.size, pygame.SRCALPHA)
        edge = 18 if reduced_motion else 34
        for index in range(edge):
            alpha = int(3 + index * (2.2 if reduced_motion else 2.9))
            pygame.draw.rect(vignette, (0, 0, 0, min(95, alpha)), vignette.get_rect().inflate(-index * 2, -index * 2), 1)
        target.blit(vignette, rect.topleft)

    def _scanlines(self, target, rect, reduced_glitch: bool = False) -> None:
        spacing = 10 if reduced_glitch else 6
        alpha = 20 if reduced_glitch else 34
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        for y in range(0, rect.height, spacing):
            pygame.draw.line(layer, (0, 0, 0, alpha), (0, y), (rect.width, y), 1)
        target.blit(layer, rect.topleft)

    def _cam_no(self, state) -> int:
        return {camera: index + 1 for index, camera in enumerate(state.camera_chain)}[state.camera]

    def _text(self, target, text, position, font, color) -> None:
        target.blit(font.render(text, True, color), position)

    def _wrap(self, text: str, width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 > width:
                lines.append(current)
                current = word
            else:
                current = (current + " " + word).strip()
        if current:
            lines.append(current)
        return lines
