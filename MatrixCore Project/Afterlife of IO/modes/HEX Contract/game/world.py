from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pygame

from .world_data import PREFABS, TEXTURE_FAMILIES, expand_object, select_layout


@dataclass
class WorldObstacle:
    object_id: str
    prefab: str
    category: str
    texture_key: str
    rects: list[pygame.Rect]
    bounds: pygame.Rect
    blocks_movement: bool = True
    blocks_vision: bool = True
    blocks_projectiles: bool = True
    destructible: bool = False
    max_hp: float = 0.0
    hp: float = 0.0
    destroyed: bool = False
    hit_flash: float = 0.0

    @property
    def integrity(self) -> float:
        if not self.destructible or self.max_hp <= 0:
            return 1.0
        return max(0.0, min(1.0, self.hp / self.max_hp))

    @property
    def damage_state(self) -> str:
        if self.destroyed:
            return "RUBBLE"
        if not self.destructible:
            return "SOLID"
        if self.integrity <= 0.34:
            return "BREACHED"
        if self.integrity <= 0.68:
            return "CRACKED"
        return "INTACT"

    def active_rects(self, purpose: str) -> Iterable[pygame.Rect]:
        if self.destroyed:
            return ()
        allowed = {
            "movement": self.blocks_movement,
            "vision": self.blocks_vision,
            "projectiles": self.blocks_projectiles,
        }.get(purpose, True)
        return self.rects if allowed else ()

    def contains(self, point, purpose: str = "projectiles") -> bool:
        return any(rect.collidepoint(point) for rect in self.active_rects(purpose))

    def damage(self, amount: float) -> bool:
        """Damage destructible cover. Returns True only on the destruction frame."""
        if not self.destructible or self.destroyed or amount <= 0:
            return False
        self.hp = max(0.0, self.hp - amount)
        self.hit_flash = 0.18
        if self.hp <= 0:
            self.destroyed = True
            return True
        return False

    def update(self, dt: float) -> None:
        self.hit_flash = max(0.0, self.hit_flash - dt)


def build_world(quest_key: str, layout_seed: int = 0) -> tuple[list[WorldObstacle], dict[str, pygame.Vector2], str]:
    layout = select_layout(quest_key, layout_seed)
    texture_family = TEXTURE_FAMILIES[quest_key]
    objects: list[WorldObstacle] = []
    for record in layout["objects"]:
        data = expand_object(record)
        category = data["category"]
        texture_key = record.get("texture", texture_family.get(category, texture_family["wall"]))
        max_hp = float(data["max_hp"])
        objects.append(WorldObstacle(
            object_id=str(record["id"]),
            prefab=str(record["prefab"]),
            category=category,
            texture_key=texture_key,
            rects=[pygame.Rect(*r) for r in data["parts"]],
            bounds=pygame.Rect(*data["bounds"]),
            blocks_movement=bool(data["movement"]),
            blocks_vision=bool(data["vision"]),
            blocks_projectiles=bool(data["projectiles"]),
            destructible=bool(data["destructible"]),
            max_hp=max_hp,
            hp=max_hp,
        ))
    markers = {name: pygame.Vector2(*pos) for name, pos in layout["markers"].items()}
    # Reinforcement spawners are authored floor devices. They are visible world
    # objects with reserved emergence space, but intentionally do not block
    # movement, vision, or projectiles.
    spawn_prefab = PREFABS["spawn_gate"]
    for name, pos in markers.items():
        if not name.startswith("spawn_gate_"):
            continue
        size = spawn_prefab["size"]
        bounds = pygame.Rect(int(pos.x - size[0] / 2), int(pos.y - size[1] / 2), *size)
        objects.append(WorldObstacle(
            object_id=name, prefab="spawn_gate", category="spawner",
            texture_key=texture_family["spawner"], rects=[], bounds=bounds,
            blocks_movement=False, blocks_vision=False, blocks_projectiles=False,
        ))
    return objects, markers, str(layout["name"])


class WorldTextureLibrary:
    """Small authored material tiles used to make obstacles read as physical objects."""
    def __init__(self):
        self._cache: dict[str, pygame.Surface | None] = {}
        self.root = Path(__file__).resolve().parents[1] / "assets" / "world"

    def get(self, key: str) -> pygame.Surface | None:
        if key in self._cache:
            return self._cache[key]
        path = self.root / f"{key}.png"
        if not path.exists():
            self._cache[key] = None
            return None
        try:
            image = pygame.image.load(str(path)).convert_alpha()
        except (pygame.error, OSError):
            image = None
        self._cache[key] = image
        return image
