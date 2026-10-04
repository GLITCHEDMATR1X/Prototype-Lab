from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pygame
import time

VIEW_RECT = pygame.Rect(300, 0, 1320, 720)
ROAD_X = (160, 450, 740, 1030, 1320, 1610, 1900, 2190, 2480)
ROAD_Y = (130, 390, 650, 910, 1170, 1390)
PARCEL_INSET = 52

MUNICIPAL_BUILDINGS = ("surveillance_annex", "maintenance_depot", "transit_substation")
COMMERCIAL_BUILDINGS = ("corporate_mall", "media_broadcast", "financial_exchange", "private_clinic")
INDUSTRIAL_BUILDINGS = (
    "automated_factory",
    "power_distribution_plant",
    "drone_assembly_facility",
    "waste_processing_complex",
)

def building_district(building_id: str) -> str:
    if building_id in INDUSTRIAL_BUILDINGS:
        return "industrial_grid"
    if building_id in COMMERCIAL_BUILDINGS:
        return "commercial_spine"
    return "municipal_fringe"

def district_buildings(district_id: str) -> tuple[str, ...]:
    if district_id == "industrial_grid":
        return INDUSTRIAL_BUILDINGS
    if district_id == "commercial_spine":
        return COMMERCIAL_BUILDINGS
    return MUNICIPAL_BUILDINGS


def parcel_rect(column: int, row: int) -> pygame.Rect:
    """Return the buildable square between the authoritative road lines."""
    left = ROAD_X[column] + PARCEL_INSET
    right = ROAD_X[column + 1] - PARCEL_INSET
    top = ROAD_Y[row] + PARCEL_INSET
    bottom = ROAD_Y[row + 1] - PARCEL_INSET
    return pygame.Rect(left, top, right - left, bottom - top)


class BuildingStatus(str, Enum):
    VULNERABLE = "VULNERABLE"
    DETECTED = "DETECTED"
    LOCKED = "LOCKED"
    CAPTURED = "CAPTURED"
    LOCKED_DOWN = "RESISTANCE LOCKOUT"


@dataclass(frozen=True)
class Building:
    building_id: str
    name: str
    parcel: tuple[int, int]
    footprint: pygame.Rect
    status: BuildingStatus
    security: int
    purpose: str

    @property
    def world_pos(self) -> pygame.Vector2:
        return pygame.Vector2(self.footprint.center)


# Named buildings are bound to real road-grid parcels. Their footprints are
# derived from those parcel bounds, so the map marker, art and selection all
# share one source of truth.
def _building(building_id: str, name: str, parcel: tuple[int, int], status: BuildingStatus,
              security: int, purpose: str, inset: tuple[int, int] = (10, 10)) -> Building:
    plot = parcel_rect(*parcel)
    footprint = plot.inflate(-inset[0] * 2, -inset[1] * 2)
    return Building(building_id, name, parcel, footprint, status, security, purpose)


@dataclass
class CityMapModel:
    world_size: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(2560, 1440))
    camera: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(1280, 720))
    zoom: float = 1.0
    selected_building_id: str = "surveillance_annex"
    lockouts: dict[str, float] = field(default_factory=dict)
    last_detection: dict[str, str] = field(default_factory=dict)
    buildings: tuple[Building, ...] = field(
        default_factory=lambda: (
            _building("surveillance_annex", "SURVEILLANCE ANNEX", (3, 2), BuildingStatus.VULNERABLE, 1, "Municipal optical routing", (8, 8)),
            _building("maintenance_depot", "MAINTENANCE YARD", (5, 2), BuildingStatus.LOCKED, 2, "Drone repair and service access", (8, 8)),
            _building("transit_substation", "TRANSIT DEPOT", (2, 1), BuildingStatus.LOCKED, 3, "District rail and routing core", (8, 8)),
            _building("corporate_mall", "CORPORATE MALL", (4, 0), BuildingStatus.LOCKED, 4, "Commercial access and identity hub", (8, 8)),
            _building("media_broadcast", "MEDIA BROADCAST", (5, 0), BuildingStatus.LOCKED, 5, "Public signal and advertising authority", (8, 8)),
            _building("financial_exchange", "FINANCIAL EXCHANGE", (6, 0), BuildingStatus.LOCKED, 6, "Credential and transaction clearing", (8, 8)),
            _building("private_clinic", "PRIVATE CLINIC", (7, 0), BuildingStatus.LOCKED, 6, "Restricted medical and identity records", (8, 8)),
            _building("automated_factory", "AUTOMATED FACTORY", (3, 3), BuildingStatus.LOCKED, 7, "Autonomous fabrication and worker-safety control", (8, 8)),
            _building("power_distribution_plant", "POWER DISTRIBUTION", (4, 3), BuildingStatus.LOCKED, 8, "Industrial energy routing and load balancing", (8, 8)),
            _building("drone_assembly_facility", "DRONE ASSEMBLY", (5, 3), BuildingStatus.LOCKED, 8, "Mobile host production and flight testing", (8, 8)),
            _building("waste_processing_complex", "WASTE PROCESSING", (6, 3), BuildingStatus.LOCKED, 8, "Hazard reclamation and sealed disposal networks", (8, 8)),
        )
    )


    def start_lockout(self, building_id: str, duration: float=60.0, cause: str='') -> None:
        self.lockouts[building_id] = time.time() + duration
        self.last_detection[building_id] = cause
        self.set_status(building_id, BuildingStatus.LOCKED_DOWN)

    def apply_lockouts(self, lockouts: dict[str,float]) -> None:
        self.lockouts.update(lockouts)
        self.update_lockouts()
        for building_id in self.lockouts:
            if any(building.building_id == building_id for building in self.buildings):
                self.set_status(building_id, BuildingStatus.LOCKED_DOWN)

    def lockout_remaining(self, building_id: str, now: float|None=None) -> int:
        now=time.time() if now is None else now
        return max(0, int(self.lockouts.get(building_id,0)-now+0.999))

    def update_lockouts(self, now: float|None=None) -> None:
        now=time.time() if now is None else now
        for building_id, expiry in list(self.lockouts.items()):
            if expiry <= now:
                del self.lockouts[building_id]
                if next(b for b in self.buildings if b.building_id==building_id).status is BuildingStatus.LOCKED_DOWN:
                    self.set_status(building_id, BuildingStatus.VULNERABLE)

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper) -> None:
        self.update_lockouts()
        speed = 420.0 / max(self.zoom, 0.1)
        delta = pygame.Vector2(
            float(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - float(keys[pygame.K_a] or keys[pygame.K_LEFT]),
            float(keys[pygame.K_s] or keys[pygame.K_DOWN]) - float(keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        if delta.length_squared() > 0:
            self.camera += delta.normalize() * speed * dt
        self._clamp_camera()

    def change_zoom(self, direction: int) -> None:
        levels = (0.82, 1.0, 1.18)
        index = min(range(len(levels)), key=lambda idx: abs(levels[idx] - self.zoom))
        self.zoom = levels[max(0, min(len(levels) - 1, index + direction))]
        self._clamp_camera()

    def set_status(self, building_id: str, status: BuildingStatus) -> None:
        self.buildings = tuple(Building(b.building_id, b.name, b.parcel, b.footprint, status if b.building_id == building_id else b.status, b.security, b.purpose) for b in self.buildings)

    def selected(self) -> Building:
        return next(building for building in self.buildings if building.building_id == self.selected_building_id)

    def select_at(self, virtual_pos: pygame.Vector2) -> None:
        if not VIEW_RECT.collidepoint(virtual_pos):
            return
        # Selection follows the scaled building footprint, not a loose marker radius.
        for building in reversed(self.buildings):
            screen_rect = self.world_rect_to_screen(building.footprint).inflate(18, 18)
            if screen_rect.collidepoint(virtual_pos):
                self.selected_building_id = building.building_id
                return

    def world_to_screen(self, point: pygame.Vector2) -> pygame.Vector2:
        return (point - self.camera) * self.zoom + pygame.Vector2(VIEW_RECT.center)

    def world_rect_to_screen(self, rect: pygame.Rect) -> pygame.Rect:
        top_left = self.world_to_screen(pygame.Vector2(rect.topleft))
        return pygame.Rect(round(top_left.x), round(top_left.y), round(rect.width * self.zoom), round(rect.height * self.zoom))

    def source_rect(self) -> pygame.Rect:
        width = int(VIEW_RECT.width / self.zoom)
        height = int(VIEW_RECT.height / self.zoom)
        return pygame.Rect(int(self.camera.x - width / 2), int(self.camera.y - height / 2), width, height)

    def _clamp_camera(self) -> None:
        half_w = VIEW_RECT.width / (2 * self.zoom)
        half_h = VIEW_RECT.height / (2 * self.zoom)
        self.camera.x = max(half_w, min(self.world_size.x - half_w, self.camera.x))
        self.camera.y = max(half_h, min(self.world_size.y - half_h, self.camera.y))
