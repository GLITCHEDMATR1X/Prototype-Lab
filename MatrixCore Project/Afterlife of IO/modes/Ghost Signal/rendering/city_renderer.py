from __future__ import annotations

import math
import random

import pygame

from game.city_map import (
    BuildingStatus, CityMapModel, ROAD_X, ROAD_Y, VIEW_RECT, parcel_rect,
    building_district, district_buildings, COMMERCIAL_BUILDINGS, MUNICIPAL_BUILDINGS, INDUSTRIAL_BUILDINGS,
)
from ui.settings import (
    SETTING_ROWS,
    SETTINGS_CLOSE_RECT,
    SETTINGS_PANEL_RECT,
    SETTINGS_RESET_RECT,
    setting_value_text,
    settings_row_rect,
)
from game.version import PASS_ID, BUILD_LABEL, VERSION
from game.progression import MEMORY_FRAGMENTS

VIRTUAL_SIZE = (1920, 1080)
WORLD_SIZE = (2560, 1440)

PALETTE = {
    "black": pygame.Color(3, 6, 9),
    "panel": pygame.Color(6, 11, 15),
    "road": pygame.Color(17, 22, 25),
    "roof": pygame.Color(24, 31, 35),
    "roof2": pygame.Color(33, 40, 44),
    "steel": pygame.Color(65, 76, 81),
    "cyan": pygame.Color(46, 218, 246),
    "cyan_white": pygame.Color(208, 250, 255),
    "amber": pygame.Color(238, 165, 61),
    "red": pygame.Color(232, 58, 55),
    "violet": pygame.Color(173, 45, 235),
    "green": pygame.Color(57, 221, 100),
    "muted": pygame.Color(111, 126, 132),
}


class CityRenderer:
    # Afterlife of IO relabels this when it hosts Ghost Signal in-process.
    disconnect_label = "DISCONNECT"

    def __init__(self, text_scale: float = 1.0) -> None:
        self.world = pygame.Surface(WORLD_SIZE).convert()
        self.set_text_scale(text_scale)
        self._build_static_world()

    def set_text_scale(self, text_scale: float) -> None:
        scale = max(0.90, min(1.15, float(text_scale)))
        self.text_scale = scale
        self.font_tiny = pygame.font.SysFont("dejavusansmono", round(16 * scale))
        self.font_small = pygame.font.SysFont("dejavusansmono", round(20 * scale))
        self.font_medium = pygame.font.SysFont("dejavusansmono", round(27 * scale), bold=True)
        self.font_large = pygame.font.SysFont("dejavusansmono", round(68 * scale), bold=True)

    def _build_static_world(self) -> None:
        self.world.fill((6, 9, 11))
        rng = random.Random(20084)
        # Dense orthogonal street plan.
        road_x = ROAD_X
        road_y = ROAD_Y
        for x in road_x:
            pygame.draw.rect(self.world, (15, 19, 21), (x - 42, 0, 84, WORLD_SIZE[1]))
            pygame.draw.line(self.world, (88, 73, 48), (x - 31, 0), (x - 31, WORLD_SIZE[1]), 1)
            pygame.draw.line(self.world, (88, 73, 48), (x + 31, 0), (x + 31, WORLD_SIZE[1]), 1)
            for y in range(20, WORLD_SIZE[1], 46):
                pygame.draw.line(self.world, (118, 112, 90), (x - 3, y), (x + 3, y + 20), 1)
        for y in road_y:
            pygame.draw.rect(self.world, (15, 19, 21), (0, y - 42, WORLD_SIZE[0], 84))
            pygame.draw.line(self.world, (88, 73, 48), (0, y - 31), (WORLD_SIZE[0], y - 31), 1)
            pygame.draw.line(self.world, (88, 73, 48), (0, y + 31), (WORLD_SIZE[0], y + 31), 1)
            for x in range(20, WORLD_SIZE[0], 52):
                pygame.draw.line(self.world, (118, 112, 90), (x, y - 3), (x + 22, y + 3), 1)

        # Buildable squares are the authority for every roof. Named facilities
        # claim an entire parcel; ordinary parcels use dense mixed rooftops.
        building_by_parcel = {building.parcel: building for building in CityMapModel().buildings}
        block_id = 0
        for xi in range(len(road_x) - 1):
            for yi in range(len(road_y) - 1):
                plot = parcel_rect(xi, yi)
                if plot.width < 80 or plot.height < 80:
                    continue
                building = building_by_parcel.get((xi, yi))
                if building is not None:
                    self._draw_facility_parcel(rng, plot, building)
                else:
                    if yi <= 1 and xi >= 4:
                        accent = ("amber", "violet", "cyan", "amber")[(xi + yi) % 4]
                        self._draw_commercial_block(rng, plot, accent, block_id)
                    else:
                        accent = ("cyan", "amber", "muted", "violet")[(xi + yi) % 4]
                        self._draw_city_block(rng, plot, accent, block_id)
                block_id += 1

        # Rail line crossing the lower middle.
        rail_y = 1010
        pygame.draw.rect(self.world, (10, 13, 15), (0, rail_y - 25, WORLD_SIZE[0], 50))
        for off in (-10, 10):
            pygame.draw.line(self.world, (112, 123, 125), (0, rail_y + off), (WORLD_SIZE[0], rail_y + off), 3)
        for x in range(0, WORLD_SIZE[0], 24):
            pygame.draw.line(self.world, (55, 60, 62), (x, rail_y - 17), (x, rail_y + 17), 2)


    def _draw_city_block(self, rng: random.Random, rect: pygame.Rect, accent_key: str, block_id: int) -> None:
        pygame.draw.rect(self.world, (10, 14, 16), rect)
        accent = PALETTE[accent_key]
        margin = 8
        cols = 2 if rect.width < 220 else 3
        rows = 2 if rect.height < 210 else 3
        cell_w = (rect.width - margin * (cols + 1)) // cols
        cell_h = (rect.height - margin * (rows + 1)) // rows
        for row in range(rows):
            for col in range(cols):
                if rng.random() < 0.12:
                    continue
                x = rect.x + margin + col * (cell_w + margin)
                y = rect.y + margin + row * (cell_h + margin)
                roof = pygame.Rect(x, y, cell_w, cell_h)
                shade = rng.randint(20, 34)
                pygame.draw.rect(self.world, (shade, shade + 5, shade + 7), roof, border_radius=2)
                pygame.draw.rect(self.world, (64, 70, 72), roof, 1, border_radius=2)
                inset = roof.inflate(-12, -12)
                pygame.draw.rect(self.world, (13, 18, 20), inset, 1)
                # HVAC, ducts, vents, water tanks and rooftop cabling.
                for _ in range(rng.randint(2, 5)):
                    w = rng.randint(10, max(11, min(34, roof.width // 3)))
                    h = rng.randint(8, max(9, min(28, roof.height // 3)))
                    rx = rng.randint(roof.left + 7, max(roof.left + 7, roof.right - w - 7))
                    ry = rng.randint(roof.top + 7, max(roof.top + 7, roof.bottom - h - 7))
                    pygame.draw.rect(self.world, (51, 60, 63), (rx, ry, w, h))
                    pygame.draw.rect(self.world, (102, 112, 114), (rx, ry, w, h), 1)
                if rng.random() < 0.7:
                    cx, cy = roof.center
                    r = rng.randint(8, 15)
                    pygame.draw.circle(self.world, (18, 23, 25), (cx, cy), r)
                    pygame.draw.circle(self.world, (91, 103, 106), (cx, cy), r, 2)
                    for a in range(0, 360, 90):
                        v = pygame.Vector2(r - 2, 0).rotate(a)
                        pygame.draw.line(self.world, (70, 82, 84), (cx, cy), (cx + v.x, cy + v.y), 2)
                # Sparse lit windows/roof indicators.
                if (block_id + row + col) % 3 == 0:
                    for k in range(3):
                        px = roof.left + 10 + k * 13
                        pygame.draw.rect(self.world, (*accent[:3],), (px, roof.bottom - 7, 6, 2))

    def _draw_commercial_block(self, rng: random.Random, rect: pygame.Rect, accent_key: str, block_id: int) -> None:
        """Dense storefront roofs and light wells for the Commercial Spine."""
        pygame.draw.rect(self.world, (12, 14, 18), rect)
        accent = PALETTE[accent_key]
        margin = 7
        rows = 2
        cols = 4
        cell_w = (rect.width - margin * (cols + 1)) // cols
        cell_h = (rect.height - margin * (rows + 1)) // rows
        for row in range(rows):
            for col in range(cols):
                roof = pygame.Rect(
                    rect.x + margin + col * (cell_w + margin),
                    rect.y + margin + row * (cell_h + margin),
                    cell_w, cell_h,
                )
                shade = 23 + ((row * cols + col + block_id) % 9)
                pygame.draw.rect(self.world, (shade, shade + 5, shade + 9), roof, border_radius=2)
                pygame.draw.rect(self.world, (72, 73, 82), roof, 1, border_radius=2)
                lightwell = roof.inflate(-14, -14)
                pygame.draw.rect(self.world, (8, 18, 24), lightwell)
                pygame.draw.rect(self.world, accent, lightwell, 1)
                for n in range(3):
                    px = roof.left + 8 + n * max(8, (roof.width - 16) // 3)
                    pygame.draw.rect(self.world, accent, (px, roof.bottom - 6, 5, 2))

    def _draw_facility_parcel(self, rng: random.Random, plot: pygame.Rect, building) -> None:
        """Draw one named facility fitted to the square that owns it."""
        key = (
            "amber" if building.building_id in ("corporate_mall", "financial_exchange")
            else "violet" if building.building_id == "media_broadcast"
            else "green" if building.building_id == "private_clinic"
            else "red" if building.building_id in INDUSTRIAL_BUILDINGS
            else "cyan" if building.building_id == "maintenance_depot"
            else "amber" if building.status == BuildingStatus.VULNERABLE
            else "muted"
        )
        accent = PALETTE[key]
        pygame.draw.rect(self.world, (9, 13, 15), plot)
        pygame.draw.rect(self.world, (46, 53, 56), plot, 1)

        footprint = building.footprint
        # A narrow setback makes the square visibly legible as a parcel.
        pygame.draw.rect(self.world, (18, 23, 25), footprint, border_radius=3)
        if building.status == BuildingStatus.VULNERABLE:
            veil = pygame.Surface(footprint.size, pygame.SRCALPHA)
            veil.fill((*accent[:3], 18))
            self.world.blit(veil, footprint.topleft)
        pygame.draw.rect(self.world, (82, 90, 92), footprint, 1, border_radius=3)
        inner = footprint.inflate(-18, -18)
        pygame.draw.rect(self.world, (27, 34, 37), inner)
        pygame.draw.rect(self.world, accent, inner, 1)

        if building.building_id == "surveillance_annex":
            # Municipal monitoring roof: four optical arrays around a data spine.
            spine = pygame.Rect(inner.centerx - 16, inner.top + 12, 32, inner.height - 24)
            pygame.draw.rect(self.world, (11, 23, 27), spine)
            pygame.draw.rect(self.world, accent, spine, 1)
            for px, py in ((inner.left+34, inner.top+32), (inner.right-34, inner.top+32),
                           (inner.left+34, inner.bottom-32), (inner.right-34, inner.bottom-32)):
                pygame.draw.circle(self.world, (13, 19, 21), (px, py), 15)
                pygame.draw.circle(self.world, accent, (px, py), 15, 2)
                pygame.draw.circle(self.world, (90, 105, 108), (px, py), 5, 1)
        elif building.building_id == "maintenance_depot":
            # Service bays align to the road-facing lower edge.
            bay_w = max(20, (inner.width - 24) // 3)
            for i in range(3):
                bay = pygame.Rect(inner.left + 6 + i * bay_w, inner.bottom - 38, bay_w - 6, 30)
                pygame.draw.rect(self.world, (12, 20, 22), bay)
                pygame.draw.rect(self.world, accent, bay, 1)
            for i in range(2):
                tank = (inner.left + 35 + i * (inner.width - 70), inner.top + 34)
                pygame.draw.circle(self.world, (47, 57, 60), tank, 19)
                pygame.draw.circle(self.world, (105, 118, 120), tank, 19, 2)
        elif building.building_id == "transit_substation":
            # Transit control roof: parallel routing banks echo the nearby rail.
            for i in range(4):
                y = inner.top + 14 + i * max(18, (inner.height - 28) // 4)
                pygame.draw.rect(self.world, (13, 20, 22), (inner.left + 12, y, inner.width - 24, 11))
                pygame.draw.line(self.world, accent, (inner.left + 12, y), (inner.right - 12, y), 1)
            pygame.draw.circle(self.world, (14, 21, 23), inner.center, 20)
            pygame.draw.circle(self.world, accent, inner.center, 20, 2)
        elif building.building_id == "corporate_mall":
            # Central skylight with a complete storefront service ring.
            skylight = inner.inflate(-46, -34)
            pygame.draw.rect(self.world, (8, 20, 27), skylight, border_radius=8)
            pygame.draw.rect(self.world, accent, skylight, 3, border_radius=8)
            pygame.draw.line(self.world, accent, skylight.midtop, skylight.midbottom, 1)
            pygame.draw.line(self.world, accent, skylight.midleft, skylight.midright, 1)
            for point in (inner.topleft, inner.topright, inner.bottomleft, inner.bottomright):
                cx = point[0] + (20 if point[0] == inner.left else -20)
                cy = point[1] + (20 if point[1] == inner.top else -20)
                pygame.draw.circle(self.world, (40, 47, 52), (cx, cy), 10)
                pygame.draw.circle(self.world, accent, (cx, cy), 10, 1)
        elif building.building_id == "media_broadcast":
            pygame.draw.circle(self.world, (10, 18, 24), inner.center, min(inner.width, inner.height) // 3)
            pygame.draw.circle(self.world, accent, inner.center, min(inner.width, inner.height) // 3, 3)
            for angle in range(0, 360, 45):
                v = pygame.Vector2(min(inner.width, inner.height) // 3, 0).rotate(angle)
                pygame.draw.line(self.world, accent, inner.center, (inner.centerx + v.x, inner.centery + v.y), 1)
        elif building.building_id == "financial_exchange":
            for col in range(3):
                vault = pygame.Rect(inner.left + 12 + col * (inner.width // 3), inner.top + 18, inner.width // 3 - 18, inner.height - 36)
                pygame.draw.rect(self.world, (12, 18, 23), vault)
                pygame.draw.rect(self.world, accent, vault, 2)
                pygame.draw.circle(self.world, (67, 73, 78), vault.center, 12)
        elif building.building_id == "private_clinic":
            # Private clinic: clean service pods around a protected central lab.
            pygame.draw.rect(self.world, (13, 24, 24), inner.inflate(-34, -24), border_radius=10)
            pygame.draw.rect(self.world, accent, inner.inflate(-34, -24), 2, border_radius=10)
            pygame.draw.line(self.world, accent, (inner.centerx, inner.centery - 24), (inner.centerx, inner.centery + 24), 5)
            pygame.draw.line(self.world, accent, (inner.centerx - 24, inner.centery), (inner.centerx + 24, inner.centery), 5)
        elif building.building_id == "automated_factory":
            # Sawtooth production halls and a central robot-cell bus.
            for index in range(4):
                hall = pygame.Rect(inner.left + 8 + index * (inner.width // 4), inner.top + 28, inner.width // 4 - 12, inner.height - 56)
                pygame.draw.rect(self.world, (26, 31, 32), hall)
                pygame.draw.rect(self.world, accent, hall, 2)
                pygame.draw.polygon(self.world, accent, [(hall.left, hall.top), (hall.centerx, hall.top - 14), (hall.right, hall.top)], 2)
            pygame.draw.line(self.world, accent, (inner.left + 12, inner.centery), (inner.right - 12, inner.centery), 4)
        elif building.building_id == "power_distribution_plant":
            for x in (inner.left + 38, inner.centerx, inner.right - 38):
                pygame.draw.circle(self.world, (20, 27, 29), (x, inner.centery), 26)
                pygame.draw.circle(self.world, accent, (x, inner.centery), 26, 3)
                pygame.draw.line(self.world, accent, (x, inner.top + 18), (x, inner.bottom - 18), 2)
        elif building.building_id == "drone_assembly_facility":
            for row in range(2):
                for col in range(3):
                    pod = pygame.Rect(inner.left + 16 + col * (inner.width // 3), inner.top + 16 + row * (inner.height // 2), inner.width // 3 - 28, inner.height // 2 - 28)
                    pygame.draw.rect(self.world, (12, 19, 22), pod, border_radius=8)
                    pygame.draw.rect(self.world, accent, pod, 2, border_radius=8)
                    pygame.draw.circle(self.world, accent, pod.center, 9, 2)
        elif building.building_id == "waste_processing_complex":
            for index in range(3):
                tank = (inner.left + 44 + index * max(42, (inner.width - 88) // 2), inner.centery - 18)
                pygame.draw.circle(self.world, (23, 34, 29), tank, 30)
                pygame.draw.circle(self.world, accent, tank, 3)
            pygame.draw.line(self.world, accent, (inner.left + 18, inner.bottom - 34), (inner.right - 18, inner.bottom - 34), 5)
            for x in range(inner.left + 22, inner.right - 16, 32):
                pygame.draw.rect(self.world, (36, 44, 37), (x, inner.top + 22, 20, 26))
                pygame.draw.rect(self.world, accent, (x, inner.top + 22, 20, 26), 1)
        else:
            for index in range(3):
                tank = (inner.left + 42 + index * max(45, (inner.width - 84) // 2), inner.centery)
                pygame.draw.circle(self.world, (28, 33, 30), tank, 28)
                pygame.draw.circle(self.world, accent, tank, 3)
            pygame.draw.line(self.world, accent, (inner.left + 18, inner.bottom - 28), (inner.right - 18, inner.bottom - 28), 4)

        # Perimeter service lights reinforce footprint scale without spilling into roads.
        for x in range(footprint.left + 10, footprint.right - 8, 22):
            pygame.draw.rect(self.world, accent, (x, footprint.top + 4, 5, 2))
            pygame.draw.rect(self.world, accent, (x, footprint.bottom - 6, 5, 2))

    def render_city(self, target: pygame.Surface, model: CityMapModel, elapsed: float, profile=None, settings=None) -> None:
        settings = settings or {}
        target.fill(PALETTE["black"])
        source = model.source_rect().clip(self.world.get_rect())
        view = self.world.subsurface(source)
        if view.get_size() != VIEW_RECT.size:
            view = pygame.transform.smoothscale(view, VIEW_RECT.size)
        target.blit(view, VIEW_RECT.topleft)
        self._draw_live_city(target, model, elapsed, settings, profile)
        self._draw_weather(target, elapsed, bool(settings.get("reduced_motion", False)))
        self._draw_left_sidebar(target, model, profile)
        self._draw_right_sidebar(target, profile, settings)
        remaining_lockout = max((model.lockout_remaining(b.building_id) for b in model.buildings if b.status == BuildingStatus.LOCKED_DOWN), default=0)
        self._draw_bottom_panels(
            target, elapsed, bool(settings.get("reduced_glitch", False)),
            remaining_lockout, model.selected()
        )
        self._draw_frame(target)

    def _draw_live_city(self, target: pygame.Surface, model: CityMapModel, elapsed: float, settings, profile=None) -> None:
        layer = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA)
        # Moving vehicle lights remain clipped to map viewport.
        traffic_count = 18 if settings.get("reduced_motion") else 36
        motion_scale = 0.42 if settings.get("reduced_motion") else 1.0
        for i in range(traffic_count):
            phase = (elapsed * motion_scale * (0.028 + (i % 5) * 0.006) + i * 0.071) % 1.0
            if i % 2:
                wp = pygame.Vector2(160 + phase * 2320, [390, 650, 910, 1170][i % 4])
            else:
                wp = pygame.Vector2([450, 1030, 1610, 2190][i % 4], 130 + phase * 1260)
            p = model.world_to_screen(wp)
            if VIEW_RECT.collidepoint(p):
                color = PALETTE["amber"] if i % 3 == 0 else PALETTE["cyan_white"]
                pygame.draw.circle(layer, (*color[:3], 160), p, 3)
                pygame.draw.circle(layer, (*color[:3], 28), p, 9)
        # Captured infrastructure becomes Andrew's visible city-scale nervous system.
        # Routes stay grouped by district so the final city remains readable rather
        # than drawing one giant zig-zag through every captured building.
        captured = [b for b in model.buildings if b.status == BuildingStatus.CAPTURED]
        captured_ids = {b.building_id for b in captured}
        district_centers: list[pygame.Vector2] = []
        for district_index, district_id in enumerate(("municipal_fringe", "commercial_spine", "industrial_grid")):
            ids = set(district_buildings(district_id))
            district_captured = [b for b in model.buildings if b.building_id in ids and b.status == BuildingStatus.CAPTURED]
            route_points = [model.world_to_screen(b.world_pos) for b in district_captured]
            for route_index, (start, end) in enumerate(zip(route_points, route_points[1:])):
                pygame.draw.line(layer, (*PALETTE["cyan"][:3], 42), start, end, 11)
                pygame.draw.line(layer, (*PALETTE["cyan_white"][:3], 195), start, end, 3)
                pulse = start.lerp(end, (elapsed * 0.35 + route_index * 0.19) % 1.0)
                pygame.draw.circle(layer, (*PALETTE["cyan_white"][:3], 220), pulse, 6)
            if ids.issubset(captured_ids) and route_points:
                center = sum(route_points[1:], route_points[0].copy()) / len(route_points)
                district_centers.append(center)
        for route_index, (start, end) in enumerate(zip(district_centers, district_centers[1:])):
            pygame.draw.line(layer, (*PALETTE["cyan"][:3], 28), start, end, 7)
            pygame.draw.line(layer, (*PALETTE["cyan_white"][:3], 110), start, end, 1)
            pulse = start.lerp(end, (elapsed * 0.23 + route_index * 0.37) % 1.0)
            pygame.draw.circle(layer, (*PALETTE["cyan_white"][:3], 190), pulse, 5)
        for district_id in ("municipal_fringe", "commercial_spine", "industrial_grid"):
            ids = set(district_buildings(district_id))
            if ids and ids.issubset({b.building_id for b in captured}):
                district_rects = [model.world_rect_to_screen(b.footprint) for b in model.buildings if b.building_id in ids]
                if district_rects:
                    bounds = district_rects[0].copy()
                    for rect in district_rects[1:]:
                        bounds.union_ip(rect)
                    pygame.draw.rect(layer, (*PALETTE["cyan"][:3], 28), bounds.inflate(28, 28), 8)

        # Train.
        train_speed = 34 if settings.get("reduced_motion") else 80
        train_x = 160 + ((elapsed * train_speed) % 2150)
        tp = model.world_to_screen(pygame.Vector2(train_x, 1010))
        for car in range(5):
            r = pygame.Rect(int(tp.x - car * 38), int(tp.y - 6), 32, 12)
            if r.colliderect(VIEW_RECT):
                pygame.draw.rect(layer, (80, 98, 104, 230), r, border_radius=3)
                pygame.draw.rect(layer, PALETTE["cyan"], r, 1, border_radius=3)

        for b in model.buildings:
            p = model.world_to_screen(b.world_pos)
            if not VIEW_RECT.collidepoint(p):
                continue
            color = (
                PALETTE["amber"] if b.status == BuildingStatus.VULNERABLE
                else PALETTE["violet"] if b.status == BuildingStatus.LOCKED_DOWN
                else PALETTE["cyan"] if b.status == BuildingStatus.CAPTURED
                else PALETTE["green"] if b.status == BuildingStatus.DETECTED
                else PALETTE["muted"]
            )
            footprint = model.world_rect_to_screen(b.footprint)
            if b.status == BuildingStatus.CAPTURED:
                pygame.draw.rect(layer, (*PALETTE["cyan"][:3], 34), footprint)
                pygame.draw.rect(layer, PALETTE["cyan"], footprint, 2)
            if b.building_id == model.selected_building_id:
                pulse = 2 if settings.get("reduced_motion") or settings.get("reduced_flashing") else 2 + int((math.sin(elapsed * 3.0) + 1.0) * 1.5)
                pygame.draw.rect(layer, (*color[:3], 24), footprint.inflate(pulse * 2, pulse * 2), 5)
                border_color = PALETTE["cyan_white"] if settings.get("high_contrast") else color
                pygame.draw.rect(layer, border_color, footprint.inflate(8, 8), 3 if settings.get("high_contrast") else 2)
            selected = b.building_id == model.selected_building_id
            short_names = {
                "surveillance_annex": "ANNEX",
                "maintenance_depot": "MAINTENANCE",
                "transit_substation": "TRANSIT",
                "corporate_mall": "CORPORATE MALL",
                "media_broadcast": "MEDIA",
                "financial_exchange": "FINANCIAL",
                "private_clinic": "CLINIC",
                "automated_factory": "FACTORY",
                "power_distribution_plant": "POWER",
                "drone_assembly_facility": "DRONE ASSEMBLY",
                "waste_processing_complex": "WASTE",
            }
            display_name = b.name if selected else short_names.get(b.building_id, b.name)
            label = self.font_tiny.render(display_name, True, color)
            status = self.font_tiny.render(b.status.value, True, color)
            if selected:
                box_w = max(label.get_width(), status.get_width()) + 22
                box_y = footprint.bottom + 8
                if box_y + 52 > VIEW_RECT.bottom:
                    box_y = footprint.top - 60
                box_x = max(VIEW_RECT.left + 6, min(VIEW_RECT.right - box_w - 6, footprint.centerx - box_w // 2))
                box = pygame.Rect(int(box_x), int(box_y), box_w, 52)
            else:
                box = pygame.Rect(footprint.x + 6, footprint.y + 6, max(70, footprint.width - 12), 48)
            pygame.draw.rect(layer, (3, 7, 10, 224), box)
            pygame.draw.rect(layer, (*color[:3], 110), box, 1)
            layer.blit(label, (box.centerx - label.get_width() // 2, box.y + 5))
            if settings.get("state_symbols", True):
                self._draw_building_state_icon(
                    layer,
                    (box.x + 15, box.y + 35),
                    b.status,
                    color,
                    bool(settings.get("high_contrast", False)),
                )
                layer.blit(status, (box.centerx - status.get_width() // 2 + 8, box.y + 26))
            else:
                layer.blit(status, (box.centerx - status.get_width() // 2, box.y + 26))
            if b.status == BuildingStatus.LOCKED_DOWN:
                remaining=model.lockout_remaining(b.building_id)
                timer=self.font_small.render(f'{remaining:02d}s',True,PALETTE['green'])
                layer.blit(timer,(footprint.centerx-timer.get_width()//2,footprint.centery-timer.get_height()//2))
        # A completed Industrial Grid becomes one synchronized district system.
        if profile is not None and "industrial_grid" in profile.districts_completed:
            industrial = [b for b in model.buildings if b.building_id in INDUSTRIAL_BUILDINGS]
            points = [model.world_to_screen(b.world_pos) for b in industrial]
            if len(points) == 4:
                loop_points = points + [points[0]]
                for index, (start, end) in enumerate(zip(loop_points, loop_points[1:])):
                    pygame.draw.line(layer, (*PALETTE["cyan"][:3], 70), start, end, 18)
                    pygame.draw.line(layer, (*PALETTE["cyan_white"][:3], 230), start, end, 4)
                    pulse_t = (elapsed * 0.5 + index * 0.23) % 1.0
                    pulse = start.lerp(end, pulse_t)
                    pygame.draw.circle(layer, (*PALETTE["cyan_white"][:3], 240), pulse, 9)
                    pygame.draw.circle(layer, (*PALETTE["cyan"][:3], 45), pulse, 20)

            # The next campaign boundary is visible but remains encrypted and non-playable.
            anchor = model.world_to_screen(pygame.Vector2(2415, 690))
            if VIEW_RECT.collidepoint(anchor):
                skyline = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA)
                tower_specs = ((-92, 118, 38), (-44, 172, 48), (16, 226, 58), (84, 148, 42))
                for offset, height, width in tower_specs:
                    rect = pygame.Rect(int(anchor.x + offset), int(anchor.y - height), width, height)
                    pygame.draw.polygon(
                        skyline,
                        (*PALETTE["violet"][:3], 52),
                        [(rect.left, rect.bottom), (rect.left + 8, rect.top + 22), (rect.centerx, rect.top), (rect.right - 8, rect.top + 22), (rect.right, rect.bottom)],
                    )
                    pygame.draw.lines(
                        skyline, (*PALETTE["violet"][:3], 165), False,
                        [(rect.left, rect.bottom), (rect.left + 8, rect.top + 22), (rect.centerx, rect.top), (rect.right - 8, rect.top + 22), (rect.right, rect.bottom)], 2
                    )
                label = self.font_tiny.render("HIGH TOWERS • ENCRYPTED AUTHORITY", True, PALETTE["violet"])
                box = label.get_rect(center=(int(anchor.x), int(anchor.y + 28))).inflate(18, 10)
                box.clamp_ip(VIEW_RECT.inflate(-20, -20))
                pygame.draw.rect(skyline, (4, 6, 12, 220), box)
                pygame.draw.rect(skyline, (*PALETTE["violet"][:3], 150), box, 1)
                skyline.blit(label, label.get_rect(center=box.center))
                layer.blit(skyline, (0, 0))

        # surveillance scanlines, only over map.
        for y in range(VIEW_RECT.top, VIEW_RECT.bottom, 6):
            pygame.draw.line(layer, (80, 180, 195, 7), (VIEW_RECT.left, y), (VIEW_RECT.right, y))
        target.blit(layer, (0, 0))

    def _draw_weather(self, target: pygame.Surface, elapsed: float, reduced_motion: bool) -> None:
        rain = pygame.Surface(VIEW_RECT.size, pygame.SRCALPHA)
        count = 36 if reduced_motion else 92
        speed = 110 if reduced_motion else 260
        for index in range(count):
            x = (index * 137 + int(elapsed * speed * (1 + index % 4) * 0.28)) % VIEW_RECT.width
            y = (index * 83 + int(elapsed * speed)) % VIEW_RECT.height
            length = 5 if reduced_motion else 10 + index % 8
            alpha = 28 if reduced_motion else 38 + index % 28
            pygame.draw.line(rain, (115, 190, 205, alpha), (x, y), (x - 4, y + length), 1)
        target.blit(rain, VIEW_RECT.topleft)

    def _corner_brackets(self, surf: pygame.Surface, p: pygame.Vector2, radius: int, color: pygame.Color) -> None:
        for sx, sy in ((-1,-1),(1,-1),(1,1),(-1,1)):
            x, y = int(p.x + sx*radius), int(p.y + sy*radius)
            pygame.draw.line(surf, color, (x, y), (x - sx*18, y), 2)
            pygame.draw.line(surf, color, (x, y), (x, y - sy*18), 2)

    def _draw_left_sidebar(self, target: pygame.Surface, model: CityMapModel, profile=None) -> None:
        r = pygame.Rect(0, 0, 300, 720)
        pygame.draw.rect(target, PALETTE["panel"], r)
        pygame.draw.line(target, (47, 57, 61), (299, 0), (299, 720))
        self._text(target, "UTOPIA MUNICIPAL NET", (22, 20), self.font_medium, PALETTE["cyan_white"])
        self._text(target, "SURVEILLANCE SATELLITE FEED", (22, 58), self.font_small, PALETTE["muted"])
        self._text(target, "● LIVE", (22, 88), self.font_small, PALETTE["green"])
        selected = model.selected()
        district_id = building_district(selected.building_id)
        district_ids = set(district_buildings(district_id))
        captured_count = sum(b.status == BuildingStatus.CAPTURED and b.building_id in district_ids for b in model.buildings)
        control = round(100 * captured_count / max(1, len(district_ids)))
        lockout_active = any(b.status == BuildingStatus.LOCKED_DOWN for b in model.buildings)
        memories = len(profile.memory_fragments) if profile is not None else captured_count
        district_name = (
            "INDUSTRIAL GRID" if district_id == "industrial_grid"
            else "COMMERCIAL SPINE" if district_id == "commercial_spine"
            else "MUNICIPAL FRINGE"
        )
        entries = [
            ("DISTRICT", district_name),
            ("CONTROL", f"{control:02d}%  ANDREW"),
            ("MEMORY", f"{memories}/{len(MEMORY_FRAGMENTS)}  RESTORED"),
            ("ALERT LEVEL", "RESISTANCE" if lockout_active else "NORMAL"),
        ]
        y = 138
        for title, value in entries:
            self._text(target, title, (22, y), self.font_tiny, PALETTE["muted"])
            self._text(target, value, (22, y+24), self.font_small, PALETTE["cyan_white"])
            y += 76
        if profile is not None:
            operation = self._current_operation(profile)
            self._text(target, "CURRENT OPERATION", (22, 438), self.font_tiny, PALETTE["amber"])
            for line_index, line in enumerate(self._wrap_text(operation, 23)[:2]):
                self._text(target, line, (22, 462 + line_index * 22), self.font_tiny, PALETTE["cyan_white"])
        self._text(target, "M  MEMORY ARCHIVE", (22, 512), self.font_tiny, PALETTE["muted"])
        # Mini map.
        mini = pygame.Rect(20, 542, 250, 148)
        pygame.draw.rect(target, (2, 8, 12), mini)
        pygame.draw.rect(target, (40, 100, 124), mini, 1)
        for i in range(8):
            x = mini.x + 12 + i*31
            pygame.draw.line(target, (18, 48, 61), (x, mini.y+8), (x, mini.bottom-8))
        for i in range(5):
            y2 = mini.y + 12 + i*31
            pygame.draw.line(target, (18, 48, 61), (mini.x+8, y2), (mini.right-8, y2))
        cx = mini.centerx + int((model.camera.x-1280)/12)
        cy = mini.centery + int((model.camera.y-720)/12)
        pygame.draw.rect(target, PALETTE["amber"], (cx-8, cy-6, 16, 12), 1)

    def _current_operation(self, profile) -> str:
        campaign = (
            ("surveillance_annex", "BREACH SURVEILLANCE ANNEX"),
            ("maintenance_depot", "CLAIM MAINTENANCE DRONE ACCESS"),
            ("transit_substation", "CAPTURE MUNICIPAL TRANSIT"),
            ("corporate_mall", "ENTER THE COMMERCIAL SPINE"),
            ("media_broadcast", "CAPTURE PUBLIC SIGNAL AUTHORITY"),
            ("financial_exchange", "TRACE FINANCIAL CLEARING"),
            ("private_clinic", "RECOVER ANDREW'S BIOLOGICAL RECORD"),
            ("automated_factory", "ENTER THE INDUSTRIAL GRID"),
            ("power_distribution_plant", "STABILIZE CRITICAL POWER FEEDS"),
            ("drone_assembly_facility", "PRESERVE ACTIVE MACHINE MINDS"),
            ("waste_processing_complex", "SECURE HAZARD CONTAINMENT"),
        )
        for building_id, objective in campaign:
            if building_id not in profile.captured_buildings:
                return objective
        return "CHAPTER ONE COMPLETE • REVIEW HIGH TOWERS SIGNAL"

    def _draw_right_sidebar(self, target: pygame.Surface, profile=None, settings=None) -> None:
        settings = settings or {}
        r = pygame.Rect(1620, 0, 300, 720)
        pygame.draw.rect(target, PALETTE["panel"], r)
        pygame.draw.line(target, (47, 57, 61), (1620, 0), (1620, 720))
        self._text(target, "22:47:33", (1652, 22), self.font_small, PALETTE["cyan_white"])
        self._text(target, "7 MAY 2084", (1652, 50), self.font_tiny, PALETTE["muted"])
        self._text(target, "SIGNAL QUALITY", (1652, 104), self.font_tiny, PALETTE["muted"])
        self._text(target, "87%", (1652, 132), self.font_small, PALETTE["cyan_white"])
        for i in range(7):
            pygame.draw.rect(target, PALETTE["green"] if i < 6 else (28,65,38), (1710+i*14, 139, 9, 15))

        if settings.get("state_symbols", True):
            self._text(target, "BUILDING STATE KEY", (1646, 174), self.font_tiny, PALETTE["muted"])
            legend = (
                (BuildingStatus.CAPTURED, "CAPTURED", PALETTE["cyan"]),
                (BuildingStatus.VULNERABLE, "BREACH", PALETTE["amber"]),
                (BuildingStatus.DETECTED, "DETECTED", PALETTE["green"]),
                (BuildingStatus.LOCKED_DOWN, "LOCKOUT", PALETTE["violet"]),
            )
            for index, (status, label, color) in enumerate(legend):
                col, row = index % 2, index // 2
                x, y = 1648 + col * 136, 204 + row * 30
                self._draw_building_state_icon(target, (x + 9, y + 9), status, color, bool(settings.get("high_contrast", False)))
                self._text(target, label, (x + 24, y), self.font_tiny, PALETTE["cyan_white"])

        # zoom rail
        pygame.draw.rect(target, (18, 24, 27), (1850, 282, 44, 176))
        pygame.draw.rect(target, (66, 78, 82), (1850, 282, 44, 176), 1)
        self._text(target, "+", (1863, 288), self.font_medium, PALETTE["cyan_white"])
        self._text(target, "−", (1863, 414), self.font_medium, PALETTE["cyan_white"])
        pygame.draw.line(target, PALETTE["muted"], (1872, 330), (1872, 398), 1)
        pygame.draw.circle(target, PALETTE["cyan"], (1872, 365), 4)
        if profile is not None:
            stats = profile.statistics
            self._text(target, "SIGNATURE MEMORY", (1646, 510), self.font_tiny, PALETTE["muted"])
            self._text(target, f"CLEAN {int(stats.get('clean_hacks', 0)):02d}", (1646, 542), self.font_small, PALETTE["cyan"])
            self._text(target, f"ALARMS {int(stats.get('gleebs_alarms', 0)):02d}", (1646, 574), self.font_small, PALETTE["violet"])
        self._text(target, "E / ENTER BREACH", (1646, 620), self.font_tiny, PALETTE["cyan"])
        self._text(target, "LMB SELECT", (1646, 646), self.font_tiny, PALETTE["muted"])
        self._text(target, "WHEEL ZOOM", (1646, 672), self.font_tiny, PALETTE["muted"])
        self._text(target, "WASD PAN", (1646, 698), self.font_tiny, PALETTE["muted"])

    def _draw_building_state_icon(
        self,
        target: pygame.Surface,
        center: tuple[int, int],
        status: BuildingStatus,
        color: pygame.Color,
        high_contrast: bool = False,
    ) -> None:
        x, y = int(center[0]), int(center[1])
        width = 3 if high_contrast else 2
        if status == BuildingStatus.CAPTURED:
            pygame.draw.circle(target, color, (x, y), 8, width)
            pygame.draw.line(target, color, (x - 4, y), (x - 1, y + 4), width)
            pygame.draw.line(target, color, (x - 1, y + 4), (x + 5, y - 4), width)
        elif status == BuildingStatus.VULNERABLE:
            pygame.draw.polygon(target, color, [(x, y - 9), (x + 9, y + 7), (x - 9, y + 7)], width)
            pygame.draw.line(target, color, (x, y - 3), (x, y + 2), width)
            pygame.draw.circle(target, color, (x, y + 5), 1 + high_contrast)
        elif status == BuildingStatus.DETECTED:
            pygame.draw.polygon(target, color, [(x, y - 9), (x + 9, y), (x, y + 9), (x - 9, y)], width)
            pygame.draw.circle(target, color, (x, y), 2 + high_contrast)
        elif status == BuildingStatus.LOCKED_DOWN:
            pygame.draw.rect(target, color, (x - 8, y - 6, 16, 14), width)
            pygame.draw.arc(target, color, (x - 6, y - 12, 12, 12), math.pi, math.tau, width)
            pygame.draw.line(target, color, (x - 4, y - 2), (x + 4, y + 5), width)
            pygame.draw.line(target, color, (x + 4, y - 2), (x - 4, y + 5), width)
        else:
            pygame.draw.circle(target, color, (x, y), 4, width)

    def _draw_bottom_panels(self, target: pygame.Surface, elapsed: float, reduced_glitch: bool = False, lockout_seconds: int = 0, selected=None) -> None:
        # Three panels: physical interior, network overlay, Gleebs interference.
        panels = [pygame.Rect(0, 720, 800, 320), pygame.Rect(800, 720, 740, 320), pygame.Rect(1540, 720, 380, 320)]
        for r in panels:
            pygame.draw.rect(target, (4, 8, 11), r)
            pygame.draw.rect(target, (54, 67, 72), r, 1)
        self._draw_interior(target, panels[0], network=False, selected=selected)
        self._draw_interior(target, panels[1], network=True, selected=selected)
        self._draw_gleebs(target, panels[2], elapsed, reduced_glitch, lockout_seconds)
        pygame.draw.rect(target, (2, 4, 6), (0, 1040, 1920, 40))
        self._text(target, "GHOST SIGNAL: UTOPIA", (20, 1043), self.font_medium, PALETTE["cyan_white"])
        self._text(target, f"V{VERSION}  CHAPTER ONE", (330, 1054), self.font_tiny, PALETTE["muted"])
        self._text(target, "F1 HELP   F2 SETTINGS   SHIFT+M MUTE", (760, 1054), self.font_tiny, PALETTE["muted"])
        self._text(target, '"THE CITY REMEMBERS. SO DO I." — GLEEBS', (1330, 1054), self.font_tiny, PALETTE["green"])

    def _draw_interior(self, target: pygame.Surface, rect: pygame.Rect, network: bool, selected=None) -> None:
        title = "NETWORK VIEW" if network else "CAM 07 — INTERIOR"
        self._text(target, title, (rect.x+18, rect.y+14), self.font_small, PALETTE["cyan_white"])
        building_name = selected.name if selected is not None else "SURVEILLANCE ANNEX"
        self._text(target, building_name, (rect.x+18, rect.y+42), self.font_tiny, PALETTE["muted"])
        scene = rect.inflate(-28, -86)
        scene.top += 58
        pygame.draw.rect(target, (11, 15, 17), scene)
        if selected is not None and selected.building_id == "waste_processing_complex":
            pygame.draw.rect(target, (8, 18, 16), scene)
            tanks=[]
            for index,label in enumerate(("RAW","FILTER","BIO","CLEAN")):
                x=scene.x+85+(index%2)*(scene.width-170)
                y=scene.y+78+(index//2)*(scene.height-156)
                tanks.append((x,y))
                pygame.draw.circle(target,(14,31,25),(x,y),26)
                pygame.draw.circle(target,PALETTE["green"],(x,y),26,3)
                self._text(target,label,(x-26,y+34),self.font_tiny,PALETTE["muted"])
            core=(scene.centerx,scene.centery)
            pygame.draw.circle(target,(12,28,24),core,46)
            pygame.draw.circle(target,PALETTE["cyan"],core,46,3)
            if network:
                for point in tanks:
                    pygame.draw.line(target,PALETTE["cyan"],point,core,2)
                self._text(target,"RECEIVE",(rect.x+18,rect.bottom-72),self.font_tiny,PALETTE["cyan"])
                self._text(target,"SORT",(rect.x+120,rect.bottom-72),self.font_tiny,PALETTE["cyan"])
                self._text(target,"LEACHATE",(rect.x+215,rect.bottom-72),self.font_tiny,PALETTE["cyan"])
                self._text(target,"RECOVERY",(rect.x+350,rect.bottom-72),self.font_tiny,PALETTE["cyan"])
            else:
                self._text(target,"SEALED RECOVERY / LIQUID TREATMENT",(rect.x+18,rect.bottom-72),self.font_tiny,PALETTE["green"])
            return
        if selected is not None and selected.building_id == "drone_assembly_facility":
            pygame.draw.rect(target, (8, 17, 22), scene)
            pods = []
            for row in range(2):
                for col in range(4):
                    pod = pygame.Rect(scene.x + 30 + col * 155, scene.y + 62 + row * 105, 118, 72)
                    pygame.draw.rect(target, (12, 24, 28), pod, border_radius=8)
                    pygame.draw.rect(target, PALETTE["cyan"], pod, 2, border_radius=8)
                    pygame.draw.circle(target, PALETTE["cyan_white"], pod.center, 12, 2)
                    pygame.draw.line(target, PALETTE["cyan"], (pod.centerx - 26, pod.centery), (pod.centerx + 26, pod.centery), 3)
                    pods.append(pod.center)
            core = (scene.right - 68, scene.centery)
            pygame.draw.circle(target, (13, 28, 34), core, 38)
            pygame.draw.circle(target, PALETTE["green"], core, 38, 3)
            if network:
                for point in pods:
                    pygame.draw.line(target, PALETTE["cyan"], point, core, 2)
                self._text(target, "PARTS", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "CALIBRATE", (rect.x+105, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "IDENTITIES", (rect.x+225, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "FLIGHT CORE", (rect.x+365, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
            else:
                self._text(target, "DOCKED FLIGHT HOSTS / ACTIVE RESCUE MINDS", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["green"])
            return
        if selected is not None and selected.building_id == "power_distribution_plant":
            pygame.draw.rect(target, (8, 17, 20), scene)
            center = scene.center
            feeders = []
            for index, label in enumerate(("CLINIC", "TRANSIT", "HOMES", "INDUSTRIAL")):
                x = scene.x + 95 + (index % 2) * (scene.width - 190)
                y = scene.y + 85 + (index // 2) * (scene.height - 170)
                feeders.append((x, y))
                pygame.draw.circle(target, PALETTE["green"] if index < 3 else PALETTE["amber"], (x, y), 22, 3)
                self._text(target, label, (x - 38, y + 30), self.font_tiny, PALETTE["muted"])
            pygame.draw.circle(target, (14, 26, 30), center, 52)
            pygame.draw.circle(target, PALETTE["cyan"], center, 52, 3)
            if network:
                for point in feeders:
                    pygame.draw.line(target, PALETTE["cyan"], point, center, 2)
                self._text(target, "LOAD", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "SWITCH", (rect.x+105, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "FEEDERS", (rect.x+215, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "CORE", (rect.x+340, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
            else:
                self._text(target, "CRITICAL GRID FEED PREVIEW", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["green"])
            return
        if selected is not None and selected.building_id == "automated_factory":
            pygame.draw.rect(target, (21, 24, 23), (scene.x+12, scene.y+50, scene.width-24, scene.height-62))
            nodes = []
            for index in range(5):
                x = scene.x + 55 + index * 135
                pygame.draw.circle(target, PALETTE["steel"], (x, scene.bottom - 58), 20, 3)
                arm = pygame.Rect(x - 22, scene.y + 88 + (index % 2) * 28, 44, 110)
                pygame.draw.rect(target, (38, 45, 45), arm)
                pygame.draw.rect(target, PALETTE["amber"], arm, 2)
                nodes.append(arm.center)
            safety = pygame.Rect(scene.centerx - 115, scene.y + 32, 230, 46)
            pygame.draw.rect(target, (8, 19, 21), safety)
            pygame.draw.rect(target, PALETTE["green"], safety, 2)
            if network:
                core = (scene.right - 70, scene.centery)
                for point in nodes:
                    pygame.draw.line(target, PALETTE["cyan"], point, core, 2)
                pygame.draw.circle(target, PALETTE["red"], core, 17, 3)
                self._text(target, "INTAKE", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "ASSEMBLY", (rect.x+110, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "SAFETY", (rect.x+225, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "CORE", (rect.x+325, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
            else:
                self._text(target, "AUTONOMOUS PRODUCTION PREVIEW", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["green"])
            return
        if selected is not None and selected.building_id == "private_clinic":
            pygame.draw.rect(target, (16, 29, 29), (scene.x+12, scene.y+50, scene.width-24, scene.height-62), border_radius=8)
            for row in range(2):
                for col in range(4):
                    bed = pygame.Rect(scene.x+35+col*145, scene.y+85+row*105, 112, 54)
                    pygame.draw.rect(target, (18, 34, 34), bed, border_radius=6)
                    pygame.draw.rect(target, PALETTE["green"], bed, 2, border_radius=6)
            core = pygame.Rect(scene.centerx-95, scene.bottom-125, 190, 72)
            pygame.draw.rect(target, (7, 21, 24), core, border_radius=8)
            pygame.draw.rect(target, PALETTE["cyan"], core, 2, border_radius=8)
            if network:
                for row in range(2):
                    for col in range(4):
                        point=(scene.x+91+col*145, scene.y+112+row*105)
                        pygame.draw.line(target, PALETTE["cyan"], point, core.center, 2)
                self._text(target, "TRIAGE", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "BIO-ID", (rect.x+115, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "LIFE SUPPORT", (rect.x+215, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "ARCHIVE", (rect.x+365, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
            else:
                self._text(target, "PATIENT SYSTEMS STABLE", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["green"])
                self._text(target, "RESTRICTED BIOLOGICAL PREVIEW", (rect.right-315, rect.bottom-72), self.font_tiny, PALETTE["cyan_white"])
            return
        if selected is not None and selected.building_id == "financial_exchange":
            pygame.draw.rect(target, (15, 22, 22), (scene.x+12, scene.y+50, scene.width-24, scene.height-62))
            nodes = []
            for lane in range(4):
                y = scene.y + 88 + lane * 46
                pygame.draw.line(target, PALETTE["muted"], (scene.x+34, y), (scene.right-34, y), 5)
                for packet in range(5):
                    x = scene.x + 50 + packet * 118 + (lane % 2) * 24
                    pygame.draw.rect(target, PALETTE["green"] if lane % 2 else PALETTE["cyan"], (x, y-7, 22, 14), border_radius=3)
                    nodes.append((x+11, y))
            vault = pygame.Rect(scene.centerx-100, scene.bottom-62, 200, 42)
            pygame.draw.rect(target, (6, 18, 20), vault)
            pygame.draw.rect(target, PALETTE["amber"], vault, 2)
            if network:
                core = (scene.right-55, scene.centery+20)
                for point in nodes[::4]:
                    pygame.draw.line(target, PALETTE["cyan"], point, core, 2)
                pygame.draw.circle(target, PALETTE["green"], core, 16, 3)
                self._text(target, "SETTLEMENT", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "CREDENTIAL", (rect.x+145, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "AUDIT", (rect.x+285, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "CLEARING", (rect.x+380, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
            else:
                self._text(target, "LIVE TRANSACTION CLEARING PREVIEW", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["green"])
            return
        if selected is not None and selected.building_id == "media_broadcast":
            pygame.draw.rect(target, (18, 22, 28), (scene.x+12, scene.y+50, scene.width-24, scene.height-62))
            monitor_wall = pygame.Rect(scene.x+28, scene.y+72, scene.width-56, 92)
            pygame.draw.rect(target, (5, 18, 25), monitor_wall)
            nodes = []
            for index in range(6):
                panel = pygame.Rect(monitor_wall.x+12+index*100, monitor_wall.y+12, 82, 58)
                accent = PALETTE["violet"] if index % 2 else PALETTE["cyan"]
                pygame.draw.rect(target, (7, 23, 29), panel)
                pygame.draw.rect(target, accent, panel, 2)
                nodes.append(panel.center)
            studio = pygame.Rect(scene.centerx-155, scene.y+190, 310, 86)
            pygame.draw.rect(target, (48, 39, 34), studio, border_radius=6)
            pygame.draw.rect(target, PALETTE["amber"], studio, 2, border_radius=6)
            pygame.draw.circle(target, (174, 157, 136), (studio.centerx, studio.y-24), 10)
            pygame.draw.line(target, PALETTE["cyan"], (studio.centerx, studio.y-14), (studio.centerx, studio.y+30), 7)
            if network:
                core = (scene.right-80, scene.centery+50)
                for a, b in zip(nodes, nodes[1:]):
                    pygame.draw.line(target, PALETTE["cyan"], a, b, 3)
                pygame.draw.line(target, PALETTE["cyan"], nodes[-1], core, 3)
                pygame.draw.circle(target, PALETTE["violet"], core, 18, 3)
                self._text(target, "INGEST", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "ALERT", (rect.x+110, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "STUDIO", (rect.x+205, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "CORE", (rect.x+305, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
            else:
                ticker = pygame.Rect(scene.x+38, scene.bottom-52, scene.width-76, 28)
                pygame.draw.rect(target, (7, 18, 23), ticker)
                pygame.draw.rect(target, PALETTE["cyan"], ticker, 1)
                self._text(target, "LIVE PUBLIC SIGNAL PREVIEW", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["green"])
            return
        if selected is not None and selected.building_id == "corporate_mall":
            pygame.draw.rect(target, (26, 29, 31), (scene.x+12, scene.y+50, scene.width-24, scene.height-62))
            skylight = pygame.Rect(scene.centerx-95, scene.y+18, 190, 58)
            pygame.draw.rect(target, (8, 23, 29), skylight, border_radius=5)
            pygame.draw.rect(target, PALETTE["cyan"], skylight, 2, border_radius=5)
            nodes = []
            for index in range(5):
                store = pygame.Rect(scene.x+28+index*125, scene.y+110, 96, 72)
                pygame.draw.rect(target, (12, 18, 22), store)
                pygame.draw.rect(target, PALETTE["amber"] if index % 2 == 0 else PALETTE["violet"], store, 2)
                nodes.append(store.center)
            for index in range(7):
                px = scene.x + 65 + index * 86
                py = scene.bottom - 42 - (index % 2) * 18
                pygame.draw.circle(target, (176, 163, 144), (px, py), 5)
                pygame.draw.line(target, (44, 49, 52), (px, py+5), (px, py+18), 4)
            if network:
                for a, b in zip(nodes, nodes[1:]):
                    pygame.draw.line(target, PALETTE["cyan"], a, b, 3)
                for point in nodes:
                    pygame.draw.rect(target, (7, 27, 32), (point[0]-8, point[1]-8, 16, 16))
                    pygame.draw.rect(target, PALETTE["cyan"], (point[0]-8, point[1]-8, 16, 16), 2)
                self._text(target, "GATE", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "AD GRID", (rect.x+95, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
                self._text(target, "IDENTITY", (rect.x+205, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
            else:
                self._text(target, "CROWD FEED STABLE", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["green"])
                self._text(target, "LIVE COMMERCIAL PREVIEW", (rect.right-250, rect.bottom-72), self.font_tiny, PALETTE["cyan_white"])
            return
        # Room floor tiles and walls.
        pygame.draw.rect(target, (28, 31, 31), (scene.x+12, scene.y+50, scene.width-24, scene.height-62))
        for x in range(scene.x+18, scene.right-12, 42):
            pygame.draw.line(target, (51, 53, 52), (x, scene.y+50), (x, scene.bottom-12), 1)
        for y in range(scene.y+56, scene.bottom-12, 34):
            pygame.draw.line(target, (51, 53, 52), (scene.x+12, y), (scene.right-12, y), 1)
        # Monitor wall.
        for row in range(2):
            for col in range(4):
                rr = pygame.Rect(scene.x+30+col*52, scene.y+18+row*31, 44, 24)
                pygame.draw.rect(target, (10, 23, 27), rr)
                pygame.draw.rect(target, PALETTE["cyan"], rr, 1)
        # Desks, terminals, people.
        desks = [(scene.x+90, scene.y+120), (scene.x+310, scene.y+155), (scene.x+470, scene.y+100)]
        for dx, dy in desks:
            pygame.draw.rect(target, (52, 43, 34), (dx, dy, 110, 42))
            pygame.draw.rect(target, (103, 86, 68), (dx, dy, 110, 42), 1)
            pygame.draw.rect(target, (10, 30, 34), (dx+38, dy-18, 34, 22))
            pygame.draw.rect(target, PALETTE["cyan"], (dx+38, dy-18, 34, 22), 1)
        for px, py in [(scene.x+180, scene.y+164), (scene.x+390, scene.y+115), (scene.x+570, scene.y+170)]:
            pygame.draw.circle(target, (170, 154, 134), (px, py), 7)
            pygame.draw.line(target, (38, 43, 45), (px, py+7), (px, py+28), 6)
        if network:
            # Connected devices overlay only in network view.
            nodes = [(scene.x+70, scene.y+82), (scene.x+190, scene.y+140), (scene.x+350, scene.y+95), (scene.x+520, scene.y+150), (scene.x+650, scene.y+72)]
            for a, b in zip(nodes, nodes[1:]):
                pygame.draw.line(target, PALETTE["cyan"], a, b, 3)
            for p in nodes:
                pygame.draw.rect(target, (7, 27, 32), (p[0]-10, p[1]-10, 20, 20))
                pygame.draw.rect(target, PALETTE["cyan"], (p[0]-10, p[1]-10, 20, 20), 2)
            self._text(target, "CAMERA", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
            self._text(target, "TERMINAL", (rect.x+110, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
            self._text(target, "DOOR", (rect.x+220, rect.bottom-72), self.font_tiny, PALETTE["cyan"])
        else:
            self._text(target, "SIGNAL STABLE", (rect.x+18, rect.bottom-72), self.font_tiny, PALETTE["green"])
            self._text(target, "LIVE CAMERA PREVIEW", (rect.right-220, rect.bottom-72), self.font_tiny, PALETTE["cyan_white"])

    def _draw_gleebs(self, target: pygame.Surface, rect: pygame.Rect, elapsed: float, reduced_glitch: bool = False, lockout_seconds: int = 0) -> None:
        self._text(target, "GLEEBS INTERFERENCE", (rect.x+18, rect.y+14), self.font_small, PALETTE["violet"])
        rng = random.Random(int(elapsed * (3 if reduced_glitch else 8)))
        for _ in range(14 if reduced_glitch else 40):
            y = rng.randrange(rect.y+55, rect.bottom-28)
            x = rng.randrange(rect.x+10, rect.right-30)
            w = rng.randrange(8, 95)
            color = PALETTE["violet"] if rng.random() < 0.55 else PALETTE["green"]
            pygame.draw.rect(target, (*color[:3],), (x, y, w, 1))
        cx, cy = rect.centerx, rect.centery-18
        pygame.draw.polygon(target, (4, 6, 8), [(cx-85,cy+40),(cx-60,cy-45),(cx-26,cy-70),(cx,cy-35),(cx+30,cy-72),(cx+66,cy-42),(cx+88,cy+42)])
        pygame.draw.polygon(target, PALETTE["cyan_white"], [(cx-45,cy-5),(cx-10,cy+7),(cx-38,cy+24)])
        pygame.draw.polygon(target, PALETTE["cyan_white"], [(cx+45,cy-5),(cx+10,cy+7),(cx+38,cy+24)])
        if lockout_seconds > 0:
            self._text(target, "INTRUSION DETECTED", (rect.x+62, rect.bottom-95), self.font_small, PALETTE["violet"])
            self._text(target, "RESISTANCE LOCKOUT", (rect.x+58, rect.bottom-66), self.font_small, PALETTE["green"])
            self._text(target, f"00:{lockout_seconds:02d}", (rect.x+135, rect.bottom-36), self.font_medium, PALETTE["violet"])
        else:
            self._text(target, "RESISTANCE CHANNEL", (rect.x+68, rect.bottom-95), self.font_small, PALETTE["violet"])
            self._text(target, "SIGNATURE WATCH", (rect.x+82, rect.bottom-66), self.font_small, PALETTE["green"])
            self._text(target, "STANDBY", (rect.x+120, rect.bottom-36), self.font_medium, PALETTE["muted"])

    def _draw_frame(self, target: pygame.Surface) -> None:
        pygame.draw.rect(target, (65, 75, 78), target.get_rect(), 1)
        pygame.draw.line(target, (65, 75, 78), (0, 720), (1920, 720), 1)

    def render_title(self, target: pygame.Surface, elapsed: float, profile=None) -> None:
        # Title uses the same approved top-down city, darkened.
        target.fill(PALETTE["black"])
        view = pygame.transform.smoothscale(self.world.subsurface(pygame.Rect(620, 330, 1320, 720)), VIRTUAL_SIZE)
        target.blit(view, (0,0))
        shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA); shade.fill((0,0,0,145)); target.blit(shade,(0,0))
        self._text(target, "GHOST SIGNAL", (110, 380), self.font_large, PALETTE["cyan_white"])
        self._text(target, "UTOPIA", (115, 470), self.font_large, PALETTE["amber"])
        captured = len(getattr(profile, "captured_buildings", set())) if profile is not None else 0
        memories = len(getattr(profile, "memory_fragments", [])) if profile is not None else 0
        complete = profile is not None and "industrial_grid" in getattr(profile, "districts_completed", set())
        if complete:
            status = "CHAPTER ONE COMPLETE"
            prompt = "ENTER OR CLICK TO RETURN TO SATELLITE FREEROAM"
        elif captured:
            status = f"CONTINUE SIGNAL • {captured}/11 BUILDINGS • {memories}/{len(MEMORY_FRAGMENTS)} MEMORIES"
            prompt = "ENTER OR CLICK TO CONTINUE CAMPAIGN"
        else:
            status = "NEW SIGNAL • ANDREW AWAKENS INSIDE UTOPIA'S NETWORK"
            prompt = "ENTER OR CLICK TO BEGIN • F1 CONTROLS"
        self._text(target, status, (120, 570), self.font_medium, PALETTE["muted"])
        self._text(target, prompt, (120, 650), self.font_small, PALETTE["cyan"])
        self._text(target, f"VERSION {VERSION}  •  CHAPTER ONE RELEASE CANDIDATE", (120, 715), self.font_tiny, PALETTE["violet"])

    def render_onboarding_city(self, target: pygame.Surface, step: int, selected) -> None:
        if step <= 0 or step >= 5:
            return
        panel = pygame.Rect(550, 36, 820, 92)
        pygame.draw.rect(target, (3, 10, 15), panel)
        pygame.draw.rect(target, PALETTE["cyan"], panel, 3)
        self._text(target, "SIGNAL GUIDE 1/4", (580, 52), self.font_small, PALETTE["amber"])
        self._text(target, "SELECT SURVEILLANCE ANNEX • PRESS E / ENTER TO BREACH", (580, 84), self.font_small, PALETTE["cyan_white"])
        self._text(target, "G SKIP GUIDE", (1185, 54), self.font_tiny, PALETTE["muted"])

    def render_city_message(self,target:pygame.Surface,message:str)->None:
        panel=pygame.Rect(430,650,1060,52)
        pygame.draw.rect(target,(4,9,13),panel)
        pygame.draw.rect(target,PALETTE['violet'],panel,2)
        text=self.font_small.render(message,True,PALETTE['cyan_white'])
        target.blit(text,text.get_rect(center=panel.center))


    def render_district_complete(self, target: pygame.Surface, elapsed: float, profile=None, page: int = 0) -> None:
        shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA)
        shade.fill((0, 10, 16, 182))
        target.blit(shade, (0, 0))
        panel = pygame.Rect(390, 190, 1140, 610)
        pygame.draw.rect(target, (4, 12, 16), panel)

        industrial_complete = profile is not None and "industrial_grid" in profile.districts_completed
        industrial_ready = profile is not None and "industrial_grid_reclamation_ready" in profile.districts_completed
        commercial_complete = profile is not None and "commercial_spine" in profile.districts_completed
        border = PALETTE["violet"] if industrial_complete and page == 1 else PALETTE["cyan"]
        pygame.draw.rect(target, border, panel, 3)

        for index in range(8):
            y = panel.y + 56 + index * 64
            pulse = int(54 * ((elapsed * 0.24 + index * 0.11) % 1.0))
            pygame.draw.line(target, (14, 50, 58), (panel.x + 28, y), (panel.x + 88, y), 5)
            pygame.draw.line(target, border, (panel.x + 28, y), (panel.x + 28 + pulse, y), 2)
            pygame.draw.line(target, (14, 50, 58), (panel.right - 88, y), (panel.right - 28, y), 5)
            pygame.draw.line(target, border, (panel.right - 28 - pulse, y), (panel.right - 28, y), 2)

        if industrial_complete and page == 1:
            headline_text = "GLEEBS SIGNAL OVERRIDE"
            headline = self.font_large.render(headline_text, True, PALETTE["violet"])
            target.blit(headline, headline.get_rect(center=(panel.centerx, panel.y + 84)))
            self._text(target, "HIGH TOWERS / AUTHORITY BLACKSITE", (650, 330), self.font_medium, PALETTE["amber"])
            self._text(target, 'GLEEBS: "YOU FOUND THE PIECES. THAT DOES NOT MAKE YOU WHOLE."', (500, 408), self.font_small, PALETTE["green"])
            self._text(target, 'ANDREW: "THEN WHY DID YOU KEEP THEM?"', (630, 460), self.font_small, PALETTE["cyan_white"])
            self._text(target, "UNRESOLVED SIGNAL: ORIGINAL ANDREW MEMORY VAULT", (570, 535), self.font_small, PALETTE["violet"])
            self._text(target, "NEXT CAMPAIGN BOUNDARY DETECTED • ACCESS DENIED", (590, 580), self.font_small, PALETTE["amber"])
            self._text(target, "ENTER FOR SATELLITE FREEROAM • M FOR MEMORY", (610, 720), self.font_small, PALETTE["cyan_white"])
            return

        if industrial_complete:
            headline_text = "INDUSTRIAL GRID CONTROLLED"
            building_line = "FACTORY + POWER + DRONES + WASTE"
            route_line = "CHAPTER ONE COMPLETE • HIGH TOWERS DETECTED"
        elif industrial_ready:
            headline_text = "INDUSTRIAL GRID RECLAMATION READY"
            building_line = "FACTORY + POWER + DRONES + WASTE"
            route_line = "DISTRICT CONTROL SEQUENCE PENDING"
        elif commercial_complete:
            headline_text = "COMMERCIAL SPINE CONTROLLED"
            building_line = "MALL + MEDIA + FINANCIAL + CLINIC"
            route_line = "INDUSTRIAL GRID DETECTED"
        else:
            headline_text = "MUNICIPAL FRINGE CONTROLLED"
            building_line = "ANNEX + MAINTENANCE + TRANSIT"
            route_line = "CORPORATE MALL BREACH ROUTE ACQUIRED"

        headline = self.font_large.render(headline_text, True, PALETTE["cyan_white"])
        target.blit(headline, headline.get_rect(center=(panel.centerx, panel.y + 84)))
        building_surface = self.font_medium.render(building_line, True, PALETTE["cyan"])
        target.blit(building_surface, building_surface.get_rect(center=(panel.centerx, panel.y + 180)))

        buildings = len(profile.captured_buildings) if profile is not None else 3
        districts = sum(name in getattr(profile, "districts_completed", set()) for name in ("municipal_fringe", "commercial_spine", "industrial_grid")) if profile is not None else 1
        memories = len(profile.memory_fragments) if profile is not None else 3
        alarms = int(profile.statistics.get("gleebs_alarms", 0)) if profile is not None else 0
        stats = (
            ("CONTROLLED DISTRICTS", f"{districts}/3"),
            ("CAPTURED BUILDINGS", f"{buildings}/11"),
            ("MEMORIES RESTORED", f"{memories}/{len(MEMORY_FRAGMENTS)}"),
            ("GLEEBS ALARMS", str(alarms)),
        )
        for index, (title, value) in enumerate(stats):
            x = panel.x + 95 + (index % 2) * 530
            y = panel.y + 260 + (index // 2) * 105
            rect = pygame.Rect(x, y, 420, 78)
            pygame.draw.rect(target, (7, 18, 24), rect)
            pygame.draw.rect(target, PALETTE["cyan"] if index < 3 else PALETTE["violet"], rect, 2)
            self._text(target, title, (rect.x + 18, rect.y + 10), self.font_tiny, PALETTE["muted"])
            self._text(target, value, (rect.x + 18, rect.y + 34), self.font_medium, PALETTE["cyan_white"])

        self._text(target, route_line, (585, 650), self.font_small, PALETTE["amber"])
        prompt = "ENTER TO RECEIVE GLEEBS TRANSMISSION • M FOR MEMORY" if industrial_complete else "PRESS M FOR MEMORY • ENTER FOR SATELLITE FREEROAM"
        self._text(target, prompt, (555, 730), self.font_small, PALETTE["cyan_white"])

    def render_memory_archive(self, target: pygame.Surface, memories, profile) -> None:
        shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA)
        shade.fill((0, 4, 9, 218))
        target.blit(shade, (0, 0))
        panel = pygame.Rect(330, 145, 1260, 790)
        pygame.draw.rect(target, (4, 11, 16), panel)
        pygame.draw.rect(target, PALETTE["violet"], panel, 2)
        pygame.draw.line(target, PALETTE["green"], (panel.x, panel.y + 72), (panel.right, panel.y + 72), 2)
        total_memories = len(MEMORY_FRAGMENTS)
        self._text(target, "ANDREW / GLEEBS MEMORY ARCHIVE", (390, 178), self.font_medium, PALETTE["cyan_white"])
        self._text(target, f"RESTORED {len(memories)}/{total_memories}", (1300, 182), self.font_small, PALETTE["green"])

        # Two compact columns expose every live campaign memory without scrolling
        # or covering the normal gameplay view.
        slots: list[pygame.Rect] = []
        for index in range(total_memories):
            col = index % 2
            row = index // 2
            slots.append(pygame.Rect(390 + col * 585, 240 + row * 96, 555, 88))

        for index, slot in enumerate(slots):
            pygame.draw.rect(target, (7, 16, 21), slot)
            color = PALETTE["cyan"] if index < len(memories) else PALETTE["muted"]
            pygame.draw.rect(target, color, slot, 2 if index < len(memories) else 1)
            if index < len(memories):
                memory = memories[index]
                self._text(target, f"{index+1:02d}  {memory.title}", (slot.x + 14, slot.y + 7), self.font_tiny, color)
                self._text(target, memory.source, (slot.x + 14, slot.y + 30), self.font_tiny, PALETTE["amber"])
                for line_index, line in enumerate(self._wrap_text(memory.text, 58)[:2]):
                    self._text(target, line, (slot.x + 14, slot.y + 51 + line_index * 17), self.font_tiny, PALETTE["cyan_white"])
            else:
                self._text(target, f"{index+1:02d}  ENCRYPTED MEMORY", (slot.x + 14, slot.y + 12), self.font_tiny, PALETTE["muted"])
                self._text(target, "CAPTURE THE NEXT CONNECTED SYSTEM.", (slot.x + 14, slot.y + 48), self.font_tiny, PALETTE["muted"])

        stats = profile.statistics
        self._text(target, f"CLEAN {int(stats.get('clean_hacks',0))}  NOISY {int(stats.get('noisy_hacks',0))}  REJECTED {int(stats.get('rejected_hacks',0))}  GLEEBS {int(stats.get('gleebs_alarms',0))}", (430, 860), self.font_small, PALETTE["green"])
        self._text(target, "M / ESC  CLOSE ARCHIVE", (1195, 860), self.font_small, PALETTE["muted"])

    def _wrap_text(self, text: str, width: int) -> list[str]:
        words = text.split()
        lines = []
        current = ""
        for word in words:
            candidate = (current + " " + word).strip()
            if len(candidate) > width and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    def render_pause(self, target: pygame.Surface) -> None:
        shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA); shade.fill((0,0,0,182)); target.blit(shade,(0,0))
        panel = pygame.Rect(630, 350, 660, 350)
        self._panel(target, panel)
        pygame.draw.rect(target, PALETTE["cyan"], panel, 2)
        self._text(target, "CONNECTION PAUSED", (740, 395), self.font_medium, PALETTE["cyan_white"])
        pygame.draw.line(target, (48, 69, 75), (690, 455), (1230, 455), 1)
        self._text(target, "ESC", (735, 500), self.font_small, PALETTE["cyan"])
        self._text(target, "RESUME SIGNAL", (850, 500), self.font_small, PALETTE["cyan_white"])
        self._text(target, "F2", (735, 552), self.font_small, PALETTE["amber"])
        self._text(target, "SETTINGS / ACCESSIBILITY", (850, 552), self.font_small, PALETTE["cyan_white"])
        self._text(target, "Q", (735, 604), self.font_small, PALETTE["violet"])
        self._text(target, self.disconnect_label, (850, 604), self.font_small, PALETTE["muted"])
        self._text(target, "AUDIO AND SIMULATION ARE PAUSED", (760, 660), self.font_tiny, PALETTE["muted"])

    def render_help(self, target: pygame.Surface, stage_active: bool = False) -> None:
        shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA)
        shade.fill((0, 0, 0, 182))
        target.blit(shade, (0, 0))
        panel = pygame.Rect(470, 96, 980, 884)
        self._panel(target, panel)
        pygame.draw.rect(target, PALETTE["cyan"], panel, 2)
        self._text(target, "MUNICIPAL ACCESS GUIDE", (555, 136), self.font_medium, PALETTE["cyan_white"])
        self._text(target, "CURRENT CONTEXT: BUILDING STAGE" if stage_active else "CURRENT CONTEXT: SATELLITE CITY", (555, 178), self.font_tiny, PALETTE["amber"])
        if stage_active:
            lines = [
                "1–3              DIRECT CAMERA FEEDS",
                "TAB              CAMERA 04 / ISOLATED CORE",
                "4–8              SELECT INTRUSION METHOD",
                "E                EXECUTE METHOD",
                "WASD             MAINTENANCE DRONE / MOVEMENT",
                "R                DELIBERATE TRACE TEST",
            ]
        else:
            lines = [
                "WASD / ARROWS    PAN SATELLITE FEED",
                "MOUSE WHEEL      ZOOM",
                "LMB              SELECT BUILDING PARCEL",
                "E / ENTER        ENTER SELECTED BUILDING",
                "M                MEMORY ARCHIVE",
                "MOUSE EDGE       OPTIONAL CAMERA PAN",
            ]
        lines.extend([
            "G                SKIP CONTEXTUAL SIGNAL GUIDE",
            "F2               SETTINGS / ACCESSIBILITY",
            "SHIFT+M          MUTE ALL AUDIO",
            "AUDIO CAPTIONS   SETTINGS OPTION",
            "STATE SYMBOLS    COLOR-INDEPENDENT MAP KEY",
            "F11              FULLSCREEN",
            "F1 / H           CLOSE GUIDE",
            "ESC              PAUSE / CLOSE PANEL",
        ])
        for i, line in enumerate(lines):
            color = PALETTE["cyan"] if i >= len(lines) - 5 else PALETTE["muted"]
            self._text(target, line, (555, 226 + i * 48), self.font_small, color)
        self._text(target, "PANELS PAUSE AUDIO AND SIMULATION WHILE OPEN", (650, 925), self.font_tiny, PALETTE["green"])

    def render_settings(self, target: pygame.Surface, settings, selected_index: int, audio_available: bool) -> None:
        shade = pygame.Surface(VIRTUAL_SIZE, pygame.SRCALPHA)
        shade.fill((0, 0, 0, 198))
        target.blit(shade, (0, 0))
        panel = SETTINGS_PANEL_RECT
        self._panel(target, panel)
        pygame.draw.rect(target, PALETTE["cyan"], panel, 2)
        pygame.draw.line(target, PALETTE["violet"], (panel.x, panel.y + 112), (panel.right, panel.y + 112), 2)
        self._text(target, "SIGNAL ACCESSIBILITY / SYSTEM SETTINGS", (520, 108), self.font_medium, PALETTE["cyan_white"])
        status = "AUDIO DEVICE ONLINE" if audio_available else "AUDIO DISABLED / UNAVAILABLE"
        self._text(target, status, (522, 154), self.font_tiny, PALETTE["green"] if audio_available else PALETTE["amber"])
        self._text(target, "KEYBOARD, MOUSE, AND WINDOW SETTINGS PERSIST", (960, 154), self.font_tiny, PALETTE["muted"])

        for index, row in enumerate(SETTING_ROWS):
            row_rect = settings_row_rect(index)
            selected = index == selected_index
            pygame.draw.rect(target, (7, 17, 22), row_rect)
            border = PALETTE["cyan_white"] if selected else (55, 72, 78)
            pygame.draw.rect(target, border, row_rect, 2 if selected else 1)
            if selected:
                pygame.draw.rect(target, (*PALETTE["cyan"][:3],), (row_rect.x, row_rect.y, 5, row_rect.height))
            self._text(target, row.label, (row_rect.x + 18, row_rect.y + 5), self.font_tiny, PALETTE["cyan_white"] if selected else PALETTE["muted"])
            self._text(target, row.description, (row_rect.x + 18, row_rect.y + 25), self.font_tiny, PALETTE["muted"])
            value = setting_value_text(settings, row)
            value_color = PALETTE["green"] if settings.get(row.key) not in (False, 0, 0.0) else PALETTE["amber"]
            value_surf = self.font_small.render(value, True, value_color)
            target.blit(value_surf, (row_rect.right - value_surf.get_width() - 18, row_rect.y + 10))
            if row.kind == "volume":
                bar = pygame.Rect(row_rect.x + 555, row_rect.y + 18, 180, 12)
                pygame.draw.rect(target, (20, 31, 34), bar)
                fill = bar.copy()
                fill.width = round(bar.width * float(settings[row.key]))
                pygame.draw.rect(target, PALETTE["cyan"], fill)
                pygame.draw.rect(target, (72, 91, 96), bar, 1)
            elif row.kind == "toggle":
                pill = pygame.Rect(row_rect.right - 116, row_rect.y + 12, 72, 22)
                pygame.draw.rect(target, (16, 28, 31), pill, border_radius=11)
                pygame.draw.rect(target, value_color, pill, 2, border_radius=11)
                knob_x = pill.right - 13 if settings[row.key] else pill.left + 13
                pygame.draw.circle(target, value_color, (knob_x, pill.centery), 7)

        pygame.draw.rect(target, (7, 17, 22), SETTINGS_RESET_RECT)
        pygame.draw.rect(target, PALETTE["amber"], SETTINGS_RESET_RECT, 2)
        self._text(target, "R / CLICK  RESET DEFAULTS", (SETTINGS_RESET_RECT.x + 18, SETTINGS_RESET_RECT.y + 10), self.font_tiny, PALETTE["amber"])
        pygame.draw.rect(target, (7, 17, 22), SETTINGS_CLOSE_RECT)
        pygame.draw.rect(target, PALETTE["cyan"], SETTINGS_CLOSE_RECT, 2)
        self._text(target, "F2 / ESC / CLICK  CLOSE", (SETTINGS_CLOSE_RECT.x + 20, SETTINGS_CLOSE_RECT.y + 10), self.font_tiny, PALETTE["cyan"])
        self._text(target, "UP/DOWN OR WHEEL SELECT  •  LEFT/RIGHT ADJUST  •  LMB CHANGES VALUE", (610, 888), self.font_tiny, PALETTE["muted"])

    def render_audio_caption(
        self,
        target: pygame.Surface,
        caption: str,
        stage_active: bool = False,
        city_message_active: bool = False,
    ) -> None:
        if not caption:
            return
        y = 872 if stage_active else (606 if city_message_active else 666)
        text = self.font_small.render(f"[AUDIO]  {caption}", True, PALETTE["cyan_white"])
        panel = text.get_rect(center=(960, y)).inflate(42, 18)
        panel.clamp_ip(pygame.Rect(320, 0, 1280, 1040))
        shade = pygame.Surface(panel.size, pygame.SRCALPHA)
        shade.fill((3, 9, 13, 232))
        target.blit(shade, panel.topleft)
        pygame.draw.rect(target, PALETTE["green"], panel, 2)
        target.blit(text, text.get_rect(center=panel.center))

    def _panel(self, target: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(target, (4, 9, 13, 235), rect)
        pygame.draw.rect(target, (58, 84, 92), rect, 1)

    def _text(self, target: pygame.Surface, text: str, pos: tuple[int,int], font: pygame.font.Font, color: pygame.Color | tuple[int,int,int]) -> None:
        target.blit(font.render(text, True, color), pos)
