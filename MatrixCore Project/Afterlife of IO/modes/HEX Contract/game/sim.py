from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
import heapq
from typing import Iterable

import pygame

from .data import HEROES, QUESTS, HERO_ORDERS, CONTRACT_COMPLICATIONS, EQUIPMENT_KITS, ENEMY_ARCHETYPES, ENEMY_VARIANTS, MISSION_ENVIRONMENTS, CIVILIAN_ROLES, SIGNATURE_BOSSES, HERO_LINKS, SOVEREIGN_AFTERMATHS, quest_fit, equipment_fit, contract_reward, recovery_state
from .world import build_world, WorldObstacle
from .world_data import WORLD_RECT

Vec2 = pygame.Vector2

WORLD = pygame.Rect(*WORLD_RECT)
# Legacy exports remain for old tooling; live missions now receive their entry,
# extraction, artifact, boss, civilian, and reinforcement points from the authored
# Pass 14 world layout.
EXTRACTION = Vec2(120, 900)
ARTIFACT = Vec2(1580, 560)


@dataclass
class Enemy:
    pos: Vec2
    kind: str
    hp: float
    max_hp: float
    speed: float
    damage: float
    attack_range: float
    attack_delay: float
    radius: float
    attack_timer: float = 0.0
    pulse: float = 0.0
    overridden: float = 0.0
    dead: bool = False
    facing: Vec2 = field(default_factory=lambda: Vec2(0, 1))
    velocity: Vec2 = field(default_factory=Vec2)
    walk_phase: float = 0.0
    pose: str = "IDLE"
    pose_timer: float = 0.0
    hit_flash: float = 0.0
    anim_frame: int = 0
    anim_clock: float = 0.0
    echo_reanimated: bool = False
    is_boss: bool = False
    boss_id: str = ""
    boss_phase: int = 1
    boss_special_timer: float = 0.0

    @property
    def color(self) -> tuple[int, int, int]:
        if self.overridden > 0:
            return (104, 255, 180)
        return {
            "revenant": (255, 70, 116),
            "construct": (255, 184, 60),
            "cantor": (198, 78, 255),
        }[self.kind]


@dataclass
class Projectile:
    pos: Vec2
    vel: Vec2
    damage: float
    life: float
    friendly: bool
    color: tuple[int, int, int]
    radius: float = 5.0


@dataclass
class Civilian:
    pos: Vec2
    role_index: int = 0
    rescued: bool = False
    extracted: bool = False
    panic: float = 0.0
    facing: Vec2 = field(default_factory=lambda: Vec2(0, 1))
    velocity: Vec2 = field(default_factory=Vec2)
    walk_phase: float = 0.0
    pose: str = "WAITING"
    anim_frame: int = 0
    anim_clock: float = 0.0


@dataclass
class Hero:
    key: str
    pos: Vec2
    hp: float
    max_hp: float
    speed: float
    damage: float
    attack_range: float
    attack_delay: float
    discipline: float
    caution: float
    tech: float
    arcana: float
    aggression: float
    altruism: float
    resolve: float
    max_resolve: float
    curiosity: float
    protectiveness: float
    starting_strain: float
    attack_timer: float = 0.0
    ability_timer: float = 0.0
    shield_timer: float = 0.0
    flash: float = 0.0
    intent: str = "ASSESSING"
    reason: str = "Reading the contract environment"
    target_label: str = "NONE"
    kills: int = 0
    rescued: int = 0
    artifact: bool = False
    stress: float = 0.0
    last_intent: str = ""
    decision_scores: list[tuple[str, float]] = field(default_factory=list)
    facing: Vec2 = field(default_factory=lambda: Vec2(1, 0))
    velocity: Vec2 = field(default_factory=Vec2)
    walk_phase: float = 0.0
    pose: str = "ASSESS"
    pose_timer: float = 0.0
    hit_flash: float = 0.0
    anim_frame: int = 0
    anim_clock: float = 0.0
    corruption: float = 0.0
    field_condition: str = "COMBAT READY"


class Mission:
    def __init__(self, hero_key: str, quest_key: str, seed: int = 1701, starting_strain: float = 0.0, order_key: str = "balanced", equipment_key: str = "ampoule", support_key: str = "none", support_mastery: int = 0, aftermath_key: str = "none", chain_chapter: str = "", sidekick_keys: tuple[str, ...] | list[str] = (), sidekick_strains: dict[str, float] | None = None):
        if hero_key not in HEROES or quest_key not in QUESTS:
            raise ValueError("Unknown hero or quest")
        if order_key not in HERO_ORDERS:
            raise ValueError("Unknown hero order")
        if equipment_key not in EQUIPMENT_KITS:
            raise ValueError("Unknown equipment kit")
        self.random = random.Random(seed)
        self.hero_key = hero_key
        self.quest_key = quest_key
        self.order_key = order_key
        self.order = HERO_ORDERS[order_key]
        self.equipment_key = equipment_key
        self.equipment = EQUIPMENT_KITS[equipment_key]
        self.equipment_fit = equipment_fit(equipment_key, hero_key, quest_key)
        if support_key not in HERO_LINKS and support_key != "none":
            raise ValueError("Unknown HEX link support")
        if support_key == hero_key:
            support_key = "none"
        self.support_key = support_key
        self.support = HERO_LINKS.get(support_key)
        self.support_mastery = max(0, min(3, int(support_mastery)))
        # Pass 22 party deployment: one lead hero plus up to two banked sidekicks.
        # Duplicate/invalid selections are discarded deterministically.
        clean_sidekicks: list[str] = []
        for key in sidekick_keys:
            if key in HEROES and key != hero_key and key not in clean_sidekicks:
                clean_sidekicks.append(key)
            if len(clean_sidekicks) >= 2:
                break
        self.sidekick_keys = tuple(clean_sidekicks)
        self.sidekick_strains = {k: float((sidekick_strains or {}).get(k, 0.0)) for k in self.sidekick_keys}
        self.party_size = 1 + len(self.sidekick_keys)
        self.sidekicks: list[Hero] = []
        self.sidekick_downs = 0
        if aftermath_key not in SOVEREIGN_AFTERMATHS:
            aftermath_key = "none"
        self.aftermath_key = aftermath_key
        self.aftermath = SOVEREIGN_AFTERMATHS[aftermath_key]
        self.chain_chapter = chain_chapter
        self.aftermath_note = self.aftermath["effect"]
        self.support_note = "NO REMOTE LINK"
        self.consumable_used = False
        self.equipment_note = "READY"
        self.complication = CONTRACT_COMPLICATIONS[quest_key]
        self.environment = MISSION_ENVIRONMENTS[quest_key]
        self.complication_triggered = False
        self.complication_resolved = False
        self.complication_timer = 0.0
        self.complication_note = "DORMANT"
        self.order_status = "ACKNOWLEDGED"
        self.order_reason = "Awaiting first tactical decision"
        self.last_order_status = ""
        self.order_follow_seconds = 0.0
        self.order_override_seconds = 0.0
        self.world_obstacles, self.world_markers, self.world_layout_name = build_world(quest_key, seed)
        self.extraction_point = Vec2(self.world_markers["extraction"])
        self.artifact_point = Vec2(self.world_markers.get("artifact", ARTIFACT))
        spec = HEROES[hero_key]
        starting_strain = max(0.0, min(100.0, float(starting_strain)))
        base_max_hp = float(spec["max_hp"])
        conditioned_max_hp = base_max_hp * (1.0 - min(starting_strain, 60.0) / 250.0)
        starting_resolve = max(42.0, 100.0 - starting_strain * 0.55)
        self.hero = Hero(
            key=hero_key,
            pos=Vec2(self.world_markers["entry"]),
            hp=conditioned_max_hp,
            max_hp=conditioned_max_hp,
            speed=float(spec["speed"]),
            damage=float(spec["damage"]),
            attack_range=float(spec["range"]),
            attack_delay=float(spec["attack_cooldown"]),
            discipline=float(spec["discipline"]),
            caution=float(spec["caution"]),
            tech=float(spec["tech"]),
            arcana=float(spec["arcana"]),
            aggression=float(spec["aggression"]),
            altruism=float(spec["altruism"]),
            resolve=starting_resolve,
            max_resolve=100.0,
            curiosity=float(spec["curiosity"]),
            protectiveness=float(spec["protectiveness"]),
            starting_strain=starting_strain,
        )
        self.recovery_state = recovery_state(hero_key, starting_strain)
        self.hero.field_condition = self.recovery_state["name"]
        severity = int(self.recovery_state["severity"])
        if severity:
            if hero_key == "nyx":
                self.hero.aggression = min(1.15, self.hero.aggression + 0.05 * severity)
                self.hero.caution = max(0.15, self.hero.caution - 0.05 * severity)
            elif hero_key == "circuit":
                self.hero.speed *= 1.0 - 0.035 * severity
                self.hero.protectiveness = min(1.15, self.hero.protectiveness + 0.04 * severity)
            elif hero_key == "vesper":
                self.hero.attack_range *= 1.0 - 0.055 * severity
                self.hero.caution = min(1.10, self.hero.caution + 0.05 * severity)
            elif hero_key == "morrow":
                self.hero.corruption = min(70.0, starting_strain * 0.42)
                self.hero.resolve = max(30.0, self.hero.resolve - 4.0 * severity)
        # Equipment modifies real runtime state; no UI-only loadouts.
        if equipment_key == "aegis":
            self.hero.max_hp *= 1.22
            self.hero.hp = self.hero.max_hp
            self.hero.speed *= 0.93
            self.equipment_note = "WARD PLATES ACTIVE"
        elif equipment_key == "surveyor":
            self.hero.attack_range *= 1.18
            self.hero.resolve = min(self.hero.max_resolve, self.hero.resolve + 8.0)
            self.hero.tech = min(1.15, self.hero.tech + 0.08)
            self.equipment_note = "THREAT CHANNELS MAPPED"
        elif equipment_key == "beacon":
            self.hero.protectiveness = min(1.20, self.hero.protectiveness + 0.12)
            self.hero.altruism = min(1.15, self.hero.altruism + 0.08)
            self.equipment_note = "ESCORT RELAY ACTIVE"
        else:
            self.equipment_note = "AUTO-RECONSTRUCTION ARMED"
        if quest_key == "rescue" and hero_key == "nyx" and equipment_key != "beacon" and order_key != "protect":
            self.hero.speed *= 0.72
            self.equipment_note += " / ESCORT FRICTION"
        # A second active hero may maintain a remote HEX link.  This is a
        # real runtime modifier, not a decorative relationship label.
        mastery = self.support_mastery
        if self.support_key == "nyx":
            self.hero.damage *= 1.06 + 0.02 * mastery
            self.support_note = f"EXECUTION MARKS ACTIVE / MASTERY {mastery}"
        elif self.support_key == "circuit":
            self.hero.max_hp *= 1.08 + 0.02 * mastery
            self.hero.hp = self.hero.max_hp
            self.support_note = f"SANCTUARY CHECKSUM ACTIVE / MASTERY {mastery}"
        elif self.support_key == "vesper":
            self.hero.attack_range *= 1.10 + 0.02 * mastery
            self.hero.attack_delay *= max(0.88, 0.95 - 0.01 * mastery)
            self.support_note = f"OVERWATCH LANES MAPPED / MASTERY {mastery}"
        elif self.support_key == "morrow":
            bonus = 6.0 + 2.0 * mastery
            self.hero.max_resolve += bonus
            self.hero.resolve = min(self.hero.max_resolve, self.hero.resolve + bonus)
            self.support_note = f"ECHO VIGIL OPEN / MASTERY {mastery}"
        if self.aftermath_key == "choir_silence":
            self.hero.max_resolve += 4.0
            self.hero.resolve = min(self.hero.max_resolve, self.hero.resolve + 8.0)
        elif self.aftermath_key == "open_index":
            self.hero.curiosity = min(1.15, self.hero.curiosity + 0.05)
        elif self.aftermath_key == "mercy_route":
            self.hero.speed *= 1.07
            self.hero.resolve = min(self.hero.max_resolve, self.hero.resolve + 5.0)
        self.fit = quest_fit(hero_key, quest_key)
        self.behavior_counts = {
            "wounded_pursuit": 0,
            "civilian_intercepts": 0,
            "objective_bypass": 0,
            "tactical_withdrawals": 0,
            "order_followed": 0,
            "order_overridden": 0,
            "complication_responses": 0,
            "echo_reanimations": 0,
            "boss_encounters": 0,
            "boss_phase_changes": 0,
            "link_assists": 0,
            "echo_damage_absorbed": 0,
        }
        self.result_consequence = "PENDING"
        self.campaign_event = "CHAIN POSITION HELD"
        self.strain_delta = 0
        self.reward_credits = 0
        self.reward_renown = 0
        self.reward_notes: list[str] = []
        self.result_finalized = False
        self.time = 0.0
        self.status = "ACTIVE"
        self.result_reason = ""
        self.projectiles: list[Projectile] = []
        self.enemies: list[Enemy] = []
        self.civilians: list[Civilian] = []
        self.events: list[tuple[float, str, tuple[int, int, int]]] = []
        # Presentation-only event queue. App/audio consume these cues; they never
        # change simulation values, decisions, damage, timing, or pathfinding.
        self.presentation_events: list[str] = []
        self.inspection: dict = {"type": "hero", "index": 0}
        self.objective_progress = 0
        self.total_objectives = 1
        self.artifact_collected = False
        self.extraction_open = False
        self.boss_profile = SIGNATURE_BOSSES[quest_key]
        self.boss_spawned = False
        self.boss_defeated = False
        self.boss_intro_timer = 0.0
        self.boss_phase_note = "DORMANT"
        self.obstacles: list[pygame.Rect] = []
        self._sync_obstacle_rects()
        self._nav_cache: dict[int, tuple[float, Vec2, list[Vec2]]] = {}
        self._spawn_sidekicks()
        self._spawn_quest()
        self.log("CONTRACT DEPLOYED", (110, 240, 255))
        self.log(f"ORDER / {self.order['name']}", self.order["color"])
        self.log(f"KIT / {self.equipment['name']}", self.equipment["color"])
        if self.sidekicks:
            names = " + ".join(HEROES[h.key]["name"] for h in self.sidekicks)
            self.log(f"SIDEKICK TEAM / {names}", HEROES[self.sidekicks[0].key]["color"])
        elif self.support:
            self.log(f"HEX LINK / {self.support['name']} / MASTERY {self.support_mastery}", self.support["color"])
        if self.aftermath_key != "none":
            self.log(f"AFTERMATH / {self.aftermath['name']}", self.aftermath["color"])
        self.log(f"QUEST FIT {self.fit['rating']} / {self.fit['percent']}%", self.fit["color"])

    def validate_launch_state(self) -> dict:
        """Validate the freshly constructed mission before the UI commits to it."""
        required = {"entry", "extraction", "boss"}
        missing = sorted(required - set(self.world_markers))
        if missing:
            raise RuntimeError(f"Mission layout missing required markers: {missing}")
        party = [self.hero, *self.sidekicks]
        if len(party) != self.party_size or not 1 <= self.party_size <= 3:
            raise RuntimeError("Mission party-size contract failed")
        for index, member in enumerate(party):
            if not math.isfinite(member.pos.x) or not math.isfinite(member.pos.y):
                raise RuntimeError(f"Non-finite party spawn at slot {index}")
            if not WORLD.collidepoint(member.pos):
                raise RuntimeError(f"Party spawn outside world at slot {index}")
            if not self._walkable_grid_point(member.pos, 18.0):
                raise RuntimeError(f"Party spawn intersects solid geometry at slot {index}")
        for i, a in enumerate(party):
            for b in party[i+1:]:
                if a.pos.distance_to(b.pos) < 40.0:
                    raise RuntimeError("Party spawn separation contract failed")
        for enemy in self.enemies:
            if not math.isfinite(enemy.pos.x) or not math.isfinite(enemy.pos.y):
                raise RuntimeError("Non-finite enemy spawn")
        return {
            "quest": self.quest_key, "layout": self.world_layout_name,
            "party_size": self.party_size, "enemies": len(self.enemies),
            "sidekicks": list(self.sidekick_keys),
        }

    def _sync_obstacle_rects(self) -> None:
        self.obstacles = [
            rect
            for obj in self.world_obstacles
            for rect in obj.active_rects("movement")
        ]

    def _make_sidekick_hero(self, key: str, pos: Vec2, starting_strain: float) -> Hero:
        spec = HEROES[key]
        strain = max(0.0, min(100.0, float(starting_strain)))
        max_hp = float(spec["max_hp"]) * (1.0 - min(strain, 60.0) / 250.0)
        resolve = max(42.0, 100.0 - strain * 0.55)
        actor = Hero(
            key=key, pos=Vec2(pos), hp=max_hp, max_hp=max_hp,
            speed=float(spec["speed"]), damage=float(spec["damage"]),
            attack_range=float(spec["range"]), attack_delay=float(spec["attack_cooldown"]),
            discipline=float(spec["discipline"]), caution=float(spec["caution"]),
            tech=float(spec["tech"]), arcana=float(spec["arcana"]),
            aggression=float(spec["aggression"]), altruism=float(spec["altruism"]),
            resolve=resolve, max_resolve=100.0, curiosity=float(spec["curiosity"]),
            protectiveness=float(spec["protectiveness"]), starting_strain=strain,
        )
        actor.field_condition = recovery_state(key, strain)["name"]
        # Sidekicks retain their class identity but use slightly restrained output;
        # added enemy bodies provide the primary squad-size difficulty scaling.
        actor.damage *= 0.92
        return actor

    def _spawn_sidekicks(self) -> None:
        if not self.sidekick_keys:
            return
        entry = Vec2(self.world_markers["entry"])
        offsets = [Vec2(58, 18), Vec2(-58, 18), Vec2(0, 64), Vec2(76, -24), Vec2(-76, -24)]
        occupied = [Vec2(entry)]
        for key in self.sidekick_keys:
            chosen = None
            for offset in offsets:
                candidate = entry + offset
                if not self._walkable_grid_point(candidate, 22.0):
                    continue
                if any(candidate.distance_to(other) < 46.0 for other in occupied):
                    continue
                chosen = candidate
                break
            if chosen is None:
                # Conservative fallback: still never stack exactly on the lead hero.
                chosen = entry + Vec2(48 + 44 * len(self.sidekicks), 0)
            occupied.append(Vec2(chosen))
            self.sidekicks.append(self._make_sidekick_hero(key, chosen, self.sidekick_strains.get(key, 0.0)))

    def _living_party(self) -> list[Hero]:
        return [member for member in [self.hero, *self.sidekicks] if member.hp > 0]

    def _nearest_party_member(self, pos: Vec2) -> Hero:
        living = self._living_party()
        return min(living, key=lambda member: pos.distance_squared_to(member.pos)) if living else self.hero

    def _damage_party_member(self, member: Hero, damage: float) -> None:
        if member is self.hero:
            self._damage_hero(damage)
            return
        if member.hp <= 0:
            return
        member.hp = max(0.0, member.hp - damage)
        member.hit_flash = 0.26
        member.pose, member.pose_timer = "HIT", 0.28
        member.resolve = max(0.0, member.resolve - damage * 0.12)
        self.emit_presentation("impact_hero")
        if member.hp <= 0:
            member.intent = "DOWNED"
            member.reason = "Sidekick was overwhelmed and can no longer assist this contract"
            self.sidekick_downs += 1
            self.log(f"SIDEKICK DOWN / {HEROES[member.key]['name']}", HEROES[member.key]["color"])

    def _sidekick_slot(self, index: int) -> Vec2:
        h = self.hero
        forward = Vec2(h.facing) if h.facing.length_squared() else Vec2(1, 0)
        forward = forward.normalize()
        right = Vec2(-forward.y, forward.x)
        lateral = -58.0 if index == 0 else 58.0
        return h.pos - forward * 34.0 + right * lateral

    def _sidekick_attack(self, sidekick: Hero, enemy: Enemy, dt: float) -> None:
        sidekick.attack_timer = max(0.0, sidekick.attack_timer - dt)
        dist = sidekick.pos.distance_to(enemy.pos)
        if dist > sidekick.attack_range or sidekick.attack_timer > 0 or not self._line_clear(sidekick.pos, enemy.pos):
            return
        sidekick.attack_timer = sidekick.attack_delay
        dealt = sidekick.damage
        if sidekick.attack_range < 120:
            enemy.hp -= dealt
            enemy.hit_flash = 0.20
            sidekick.pose, sidekick.pose_timer = "SLASH", 0.26
            self.emit_presentation("hero_melee")
            self.emit_presentation("impact_enemy")
        else:
            direction = enemy.pos - sidekick.pos
            if direction.length_squared() > 0:
                self.projectiles.append(Projectile(Vec2(sidekick.pos), direction.normalize() * 560, dealt, 1.1, True, HEROES[sidekick.key]["color"], 5))
                sidekick.pose, sidekick.pose_timer = "FIRE", 0.22
                self.emit_presentation("hero_ranged")
        if enemy.hp <= 0 and not enemy.dead:
            enemy.dead = True
            sidekick.kills += 1
            # Existing purge/boss progression reads the lead kill counter; treat it
            # as team eliminations so sidekick kills cannot stall the objective.
            self.hero.kills += 1
            if enemy.is_boss:
                self.boss_defeated = True
                self.boss_phase_note = "SOVEREIGN DEFEATED"
                self.log(f"{self.boss_profile['name']} DEFEATED", self.boss_profile["accent"])
                self.emit_presentation("boss_down")
            if self.quest_key == "purge":
                self.objective_progress += 1
            self.log(f"{HEROES[sidekick.key]['name']} / {enemy.kind.upper()} DOWN", HEROES[sidekick.key]["color"])
            self.emit_presentation("enemy_down")

    def _update_sidekicks(self, dt: float) -> None:
        for index, sidekick in enumerate(self.sidekicks):
            if sidekick.hp <= 0:
                continue
            sidekick.ability_timer = max(0.0, sidekick.ability_timer - dt)
            sidekick.shield_timer = max(0.0, sidekick.shield_timer - dt)
            enemy = self._nearest_enemy(sidekick.pos)
            slot = self._sidekick_slot(index)
            if enemy is not None and (enemy.pos.distance_to(self.hero.pos) < 430 or enemy.pos.distance_to(sidekick.pos) < 300):
                sidekick.intent = "SUPPORTING ENGAGEMENT"
                sidekick.reason = "Sidekick is engaging pressure near the squad"
                sidekick.target_label = enemy.kind.upper()
                if sidekick.pos.distance_to(enemy.pos) > sidekick.attack_range * 0.82:
                    self._move_toward(sidekick.pos, enemy.pos, sidekick.speed * 0.92, dt, 18.0)
                self._sidekick_attack(sidekick, enemy, dt)
            else:
                sidekick.intent = "HOLDING FORMATION"
                sidekick.reason = "Maintaining a separated support lane beside the lead hero"
                sidekick.target_label = "LEAD"
                if sidekick.pos.distance_to(slot) > 24:
                    self._move_toward(sidekick.pos, slot, sidekick.speed * 0.95, dt, 18.0)

    def _spawn_scaled_enemy_near(self, anchor: Vec2, kind: str, ordinal: int) -> bool:
        offsets = [
            Vec2(72,0), Vec2(-72,0), Vec2(0,72), Vec2(0,-72),
            Vec2(58,58), Vec2(-58,58), Vec2(58,-58), Vec2(-58,-58),
            Vec2(96,36), Vec2(-96,36), Vec2(36,96), Vec2(36,-96),
        ]
        start = ordinal % len(offsets)
        for step in range(len(offsets)):
            candidate = anchor + offsets[(start + step) % len(offsets)]
            if not self._walkable_grid_point(candidate, 20.0):
                continue
            if any(not e.dead and candidate.distance_to(e.pos) < 44 for e in self.enemies):
                continue
            if any(candidate.distance_to(member.pos) < 95 for member in self._living_party()):
                continue
            self._spawn_enemy(candidate.x, candidate.y, kind)
            return True
        return False

    def _spawn_party_scaled_enemies(self, count: int, *, complication: bool = False) -> int:
        if count <= 0:
            return 0
        marker_names = sorted(name for name in self.world_markers if name.startswith("comp_" if complication else "enemy_"))
        if not marker_names:
            marker_names = sorted(name for name in self.world_markers if name.startswith("enemy_"))
        kinds = ("revenant", "construct", "cantor")
        added = 0
        for i in range(count):
            anchor = Vec2(self.world_markers[marker_names[i % len(marker_names)]])
            if self._spawn_scaled_enemy_near(anchor, kinds[(i + len(self.enemies)) % len(kinds)], i):
                added += 1
        return added

    def _active_world_rects(self, purpose: str) -> list[pygame.Rect]:
        return [
            rect
            for obj in self.world_obstacles
            for rect in obj.active_rects(purpose)
        ]

    def _world_object_at(self, point: Vec2, purpose: str = "projectiles") -> WorldObstacle | None:
        for obj in self.world_obstacles:
            if obj.contains(point, purpose):
                return obj
        return None

    def _damage_world_obstacle(self, obj: WorldObstacle, damage: float, source: str = "IMPACT") -> bool:
        if not obj.destructible or obj.destroyed:
            return False
        destroyed = obj.damage(damage)
        if destroyed:
            self._sync_obstacle_rects()
            self._nav_cache.clear()
            self.log(f"COVER BREACHED / {obj.object_id.upper()}", self.environment["accent"])
            self.emit_presentation("cover_break")
        elif obj.hit_flash > 0:
            self.log(f"COVER HIT / {obj.damage_state}", self.environment["secondary"])
            self.emit_presentation("cover_hit")
        return destroyed

    def _damage_cover_near(self, center: Vec2, radius: float, damage: float) -> int:
        count = 0
        for obj in self.world_obstacles:
            if obj.destructible and not obj.destroyed and obj.bounds.centerx is not None:
                nearest = Vec2(obj.bounds.center)
                if nearest.distance_to(center) <= radius:
                    if self._damage_world_obstacle(obj, damage, "AREA"): 
                        count += 1
        return count

    def _spawn_enemy(self, x: float, y: float, kind: str) -> None:
        stats = {
            "revenant": (64.0, 84.0, 11.0, 52.0, 0.75, 18.0),
            "construct": (82.0, 66.0, 10.0, 310.0, 1.05, 20.0),
            "cantor": (58.0, 54.0, 7.5, 260.0, 1.35, 19.0),
        }
        hp, speed, damage, rng, delay, radius = stats[kind]
        self.enemies.append(Enemy(Vec2(x, y), kind, hp, hp, speed, damage, rng, delay, radius))

    def _spawn_signature_boss(self) -> None:
        if self.boss_spawned:
            return
        b = self.boss_profile
        x, y = self.world_markers["boss"]
        enemy = Enemy(Vec2(x, y), b["kind"], float(b["hp"]), float(b["hp"]), float(b["speed"]),
                      float(b["damage"]), float(b["range"]), float(b["delay"]), float(b["radius"]),
                      is_boss=True, boss_id=b["id"], boss_special_timer=2.2)
        self.enemies.append(enemy)
        if self.quest_key == "purge":
            self.total_objectives += 1
        self.boss_spawned = True
        self.boss_intro_timer = 2.2
        self.boss_phase_note = "PHASE I / SOVEREIGN ARRIVAL"
        self.behavior_counts["boss_encounters"] += 1
        self.log(f"SIGNATURE HOST / {b['name']}", b["color"])
        self.log(b["intro"], b["accent"])
        self.emit_presentation("boss_intro")

    def _spawn_quest(self) -> None:
        if self.quest_key == "purge":
            kinds = ["revenant", "construct", "cantor", "revenant", "construct", "revenant", "cantor"]
            positions = [(*self.world_markers[f"enemy_{i}"], kind) for i, kind in enumerate(kinds)]
            self.total_objectives = len(positions)
        elif self.quest_key == "recovery":
            kinds = ["revenant", "construct", "cantor", "construct", "revenant"]
            positions = [(*self.world_markers[f"enemy_{i}"], kind) for i, kind in enumerate(kinds)]
            self.total_objectives = 2
        else:
            kinds = ["revenant", "construct", "cantor", "revenant", "construct"]
            positions = [(*self.world_markers[f"enemy_{i}"], kind) for i, kind in enumerate(kinds)]
            self.civilians = [Civilian(Vec2(self.world_markers[f"civilian_{i}"]), i) for i in range(3)]
            self.total_objectives = 3
        for x, y, kind in positions:
            self._spawn_enemy(x, y, kind)
        # Party scaling changes encounter density, not enemy HP. Each joined
        # sidekick adds two initial hostiles to preserve pressure as firepower rises.
        self.enemy_scale_initial = self._spawn_party_scaled_enemies(len(self.sidekicks) * 2)
        self.enemy_scale_complication = 0
        if self.quest_key == "purge":
            self.total_objectives += self.enemy_scale_initial

    def log(self, text: str, color: tuple[int, int, int] = (230, 240, 255)) -> None:
        self.events.insert(0, (self.time, text, color))
        del self.events[5:]

    def emit_presentation(self, cue: str) -> None:
        """Queue an audio/visual cue without affecting the simulation."""
        self.presentation_events.append(str(cue))
        if len(self.presentation_events) > 32:
            del self.presentation_events[:-32]

    def consume_presentation_events(self) -> list[str]:
        cues = list(self.presentation_events)
        self.presentation_events.clear()
        return cues

    def _circle_rect_overlap(self, pos: Vec2, radius: float, rect: pygame.Rect) -> bool:
        cx = max(rect.left, min(pos.x, rect.right))
        cy = max(rect.top, min(pos.y, rect.bottom))
        return (pos.x - cx) ** 2 + (pos.y - cy) ** 2 < radius ** 2

    def _move_entity(self, pos: Vec2, delta: Vec2, radius: float) -> Vec2:
        candidate = Vec2(pos.x + delta.x, pos.y)
        if WORLD.inflate(-radius * 2, -radius * 2).collidepoint(candidate) and not any(
            self._circle_rect_overlap(candidate, radius, r) for r in self.obstacles
        ):
            pos.x = candidate.x
        candidate = Vec2(pos.x, pos.y + delta.y)
        if WORLD.inflate(-radius * 2, -radius * 2).collidepoint(candidate) and not any(
            self._circle_rect_overlap(candidate, radius, r) for r in self.obstacles
        ):
            pos.y = candidate.y
        return pos

    def _segment_clear_for_radius(self, a: Vec2, b: Vec2, radius: float) -> bool:
        margin = int(radius * 2 + 8)
        return not any(rect.inflate(margin, margin).clipline(a, b) for rect in self._active_world_rects("movement"))

    def _walkable_grid_point(self, point: Vec2, radius: float) -> bool:
        inner = WORLD.inflate(-int(radius * 2), -int(radius * 2))
        return inner.collidepoint(point) and not any(self._circle_rect_overlap(point, radius + 4, r) for r in self.obstacles)

    def _astar_path(self, start: Vec2, goal: Vec2, radius: float) -> list[Vec2]:
        cell = 50
        cols = int(WORLD.width / cell) + 1
        rows = int(WORLD.height / cell) + 1

        def point(node: tuple[int, int]) -> Vec2:
            return Vec2(WORLD.left + node[0] * cell, WORLD.top + node[1] * cell)

        walkable = {}
        for x in range(cols):
            for y in range(rows):
                pt = point((x, y))
                walkable[(x, y)] = self._walkable_grid_point(pt, radius)

        valid = [node for node, ok in walkable.items() if ok]
        if not valid:
            return []
        start_node = min(valid, key=lambda n: point(n).distance_squared_to(start))
        goal_node = min(valid, key=lambda n: point(n).distance_squared_to(goal))
        queue: list[tuple[float, int, tuple[int, int]]] = []
        counter = 0
        heapq.heappush(queue, (0.0, counter, start_node))
        came: dict[tuple[int, int], tuple[int, int]] = {}
        cost = {start_node: 0.0}
        dirs = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]
        while queue:
            _, _, cur = heapq.heappop(queue)
            if cur == goal_node:
                break
            cp = point(cur)
            for dx, dy in dirs:
                nxt = (cur[0]+dx, cur[1]+dy)
                if not walkable.get(nxt, False):
                    continue
                np = point(nxt)
                if not self._segment_clear_for_radius(cp, np, radius):
                    continue
                step = 1.4142 if dx and dy else 1.0
                new_cost = cost[cur] + step
                if new_cost < cost.get(nxt, 1e9):
                    cost[nxt] = new_cost
                    came[nxt] = cur
                    counter += 1
                    heuristic = np.distance_to(point(goal_node)) / cell
                    heapq.heappush(queue, (new_cost + heuristic, counter, nxt))
        if goal_node not in came and goal_node != start_node:
            return []
        nodes = [goal_node]
        while nodes[-1] != start_node:
            nodes.append(came[nodes[-1]])
        nodes.reverse()
        route = [point(n) for n in nodes[1:]]
        route.append(Vec2(goal))
        return route

    def _move_toward(self, pos: Vec2, target: Vec2, speed: float, dt: float, radius: float) -> None:
        if self._segment_clear_for_radius(pos, target, radius):
            waypoint = Vec2(target)
            self._nav_cache.pop(id(pos), None)
        else:
            key = id(pos)
            cached = self._nav_cache.get(key)
            needs_path = (
                cached is None
                or self.time >= cached[0]
                or cached[1].distance_to(target) > 90
                or not cached[2]
            )
            if needs_path:
                path = self._astar_path(pos, target, radius)
                self._nav_cache[key] = (self.time + 0.45, Vec2(target), path)
            else:
                path = cached[2]
            while path and pos.distance_to(path[0]) < max(24.0, radius * 1.5):
                path.pop(0)
            waypoint = path[0] if path else Vec2(target)
        d = waypoint - pos
        if d.length_squared() > 1:
            self._move_entity(pos, d.normalize() * speed * dt, radius)

    def _line_clear(self, a: Vec2, b: Vec2) -> bool:
        line = (a, b)
        for rect in self._active_world_rects("vision"):
            if rect.clipline(line):
                return False
        return True

    def _nearest_enemy(self, pos: Vec2, include_overridden: bool = False) -> Enemy | None:
        living = [e for e in self.enemies if not e.dead and (include_overridden or e.overridden <= 0)]
        if not living:
            return None
        return min(living, key=lambda e: pos.distance_squared_to(e.pos))

    def _threats_near(self, pos: Vec2, distance: float) -> int:
        return sum(1 for e in self.enemies if not e.dead and e.overridden <= 0 and e.pos.distance_to(pos) < distance)

    def _order_aligned(self, intent: str) -> bool:
        if self.order_key == "balanced":
            return True
        return intent in self.order.get("aligned", set())

    def _order_bias(self, intent: str, hp_ratio: float, resolve_ratio: float) -> float:
        h = self.hero
        if self.order_key == "balanced":
            return 0.0
        discipline_scale = 0.18 + h.discipline * 0.34
        aligned = self._order_aligned(intent)
        bonus = discipline_scale if aligned else -0.08 * h.discipline
        if self.order_key == "objective" and intent in {"FINISHING WOUNDED TARGET", "HUNTING HOSTILE"}:
            bonus -= 0.16
        elif self.order_key == "protect" and intent == "INTERCEPTING THREAT":
            bonus += 0.22 * h.protectiveness
        elif self.order_key == "eliminate" and intent in {"HUNTING HOSTILE", "CLEARING ROUTE", "FINISHING WOUNDED TARGET"}:
            bonus += 0.18 * h.aggression
        elif self.order_key == "survive":
            if intent == "TACTICAL WITHDRAWAL":
                bonus += (1.0 - hp_ratio) * 0.55 + (1.0 - resolve_ratio) * 0.35
            elif intent in {"HUNTING HOSTILE", "FINISHING WOUNDED TARGET"}:
                bonus -= 0.18
        return bonus

    def _hero_goal(self) -> tuple[Vec2, str, str]:
        h = self.hero
        enemy = self._nearest_enemy(h.pos)
        hp_ratio = h.hp / max(1.0, h.max_hp)
        resolve_ratio = h.resolve / max(1.0, h.max_resolve)
        candidates: list[tuple[float, Vec2, str, str]] = []

        # Survival is a scored option, not a universal override. Cautious heroes
        # leave earlier; NYX is likely to continue until physically stopped.
        retreat_score = (1.0 - hp_ratio) * (0.75 + h.caution) + (1.0 - resolve_ratio) * 0.9
        retreat_score -= max(0.0, float(self.fit["score"]) - 0.60) * 0.62
        if hp_ratio < 0.18 or h.resolve < 16:
            retreat_score += 0.85
        candidates.append((retreat_score, Vec2(self.extraction_point), "TACTICAL WITHDRAWAL", "Vitality or resolve crossed personal safety doctrine"))

        if self.quest_key == "purge":
            if enemy:
                combat_score = 0.62 + h.aggression * 0.9 + h.resolve / 250.0
                candidates.append((combat_score, Vec2(enemy.pos), "HUNTING HOSTILE", "Purge priority weighted by aggression and resolve"))
            else:
                candidates.append((1.4, Vec2(self.extraction_point), "VERIFYING CLEARANCE", "No active hostile signal remains"))

        elif self.quest_key == "recovery":
            if not self.artifact_collected:
                objective_score = 0.82 + h.discipline * 0.45 + h.curiosity * 0.38 + h.tech * 0.22
                if h.key == "vesper":
                    objective_score += 0.28
                candidates.append((objective_score, Vec2(self.artifact_point), "SEEKING RELIQUARY", "Relic value outweighs optional combat"))
                if enemy:
                    distance = h.pos.distance_to(enemy.pos)
                    route_pressure = max(0.0, 1.0 - distance / 360.0)
                    combat_score = 0.32 + route_pressure * (0.85 + h.aggression * 0.45)
                    candidates.append((combat_score, Vec2(enemy.pos), "CLEARING ROUTE", "Nearby hostile obstructs the reliquary approach"))
            else:
                boss = next((e for e in self.enemies if e.is_boss and not e.dead), None)
                if boss is not None:
                    candidates.append((1.52 + h.discipline * 0.22, Vec2(boss.pos), "CONFRONTING SOVEREIGN", "The reliquary cannot extract while its appointed guardian remains active"))
                else:
                    candidates.append((1.35 + h.discipline * 0.25, Vec2(self.extraction_point), "RETURNING TO GATE", "Relic secured; extraction overrides curiosity"))

        else:
            remaining = [c for c in self.civilians if not c.rescued]
            if remaining:
                civilian = min(remaining, key=lambda c: h.pos.distance_squared_to(c.pos))
                rescue_score = 0.68 + h.altruism * 0.72 + h.discipline * 0.35 + min(0.32, self.time / 260.0) + h.rescued * 0.10
                candidates.append((rescue_score, Vec2(civilian.pos), "LOCATING PILGRIM", "Civilian priority weighted by altruism and discipline"))

                # Threats near any unrescued civilian create a protection decision.
                if enemy:
                    threatened = min(remaining, key=lambda c: enemy.pos.distance_squared_to(c.pos))
                    civilian_threat_distance = enemy.pos.distance_to(threatened.pos)
                    intercept_pressure = max(0.0, 1.0 - civilian_threat_distance / 360.0)
                    intercept_score = 0.38 + h.protectiveness * 0.95 + intercept_pressure * 0.75
                    candidates.append((intercept_score, Vec2(enemy.pos), "INTERCEPTING THREAT", "Hostile proximity threatens a pilgrim"))
            else:
                boss = next((e for e in self.enemies if e.is_boss and not e.dead), None)
                if boss is not None:
                    candidates.append((1.48 + h.protectiveness * 0.24, Vec2(boss.pos), "CONFRONTING SOVEREIGN", "The panic sovereign must fall before the survivors can cross the gate"))
                else:
                    candidates.append((1.25 + h.discipline * 0.25, Vec2(self.extraction_point), "ESCORTING SURVIVORS", "All linked civilians require extraction"))

        # NYX sees wounded enemies as opportunities even when they are not the
        # formal objective. This can be brilliant on purge and disastrous on rescue.
        wounded = [e for e in self.enemies if not e.dead and e.overridden <= 0 and e.hp < e.max_hp * 0.72]
        if h.key == "nyx" and wounded:
            target = min(wounded, key=lambda e: h.pos.distance_squared_to(e.pos))
            chase_score = 0.78 + h.aggression * 0.92 + (1.0 - target.hp / target.max_hp) * 0.65
            if self.quest_key == "rescue":
                chase_score -= h.altruism * 0.18
            candidates.append((chase_score, Vec2(target.pos), "FINISHING WOUNDED TARGET", "Impulsive hunter doctrine detected a vulnerable enemy"))

        # Vesper strongly values a controllable machine encounter, but only while
        # the area is not already saturated with melee pressure.
        if h.key == "vesper":
            hosts = [e for e in self.enemies if not e.dead and e.overridden <= 0 and e.kind in {"construct", "cantor"}]
            if hosts:
                host = min(hosts, key=lambda e: h.pos.distance_squared_to(e.pos))
                host_distance = h.pos.distance_to(host.pos)
                if host_distance < 560:
                    bypass_score = 0.58 + h.tech * 0.72 + h.curiosity * 0.18 - self._threats_near(h.pos, 170) * 0.18
                    candidates.append((bypass_score, Vec2(host.pos), "SETTING GHOST OVERRIDE", "Controllable host can replace a direct engagement"))

        # Morrow seeks usable corpses because temporary echoes can redirect pressure.
        if h.key == "morrow":
            corpses = [e for e in self.enemies if e.dead and not e.echo_reanimated]
            if corpses and h.corruption < 82:
                corpse = min(corpses, key=lambda e: h.pos.distance_squared_to(e.pos))
                echo_score = 0.60 + h.arcana * 0.52 + h.curiosity * 0.18 - h.corruption / 125.0
                if self.quest_key == "rescue":
                    echo_score -= 0.16 + h.rescued * 0.08
                candidates.append((echo_score, Vec2(corpse.pos), "RAISING ECHO", "A defeated host can absorb pressure for the contract"))

        # A guild order biases utility but never directly puppets the hero.
        adjusted: list[tuple[float, Vec2, str, str]] = []
        for score, target, intent, reason in candidates:
            bonus = self._order_bias(intent, hp_ratio, resolve_ratio)
            adjusted.append((score + bonus, target, intent, reason))
        adjusted.sort(key=lambda item: item[0], reverse=True)
        h.decision_scores = [(item[2], round(item[0], 2)) for item in adjusted[:4]]
        _, target, intent, reason = adjusted[0]
        aligned = self._order_aligned(intent)
        self.order_status = "COMPLYING" if aligned else "OVERRIDDEN"
        if aligned:
            self.order_reason = f"{intent.title()} supports {self.order['name'].title()}"
        else:
            self.order_reason = f"{HEROES[h.key]['personality'][0].title()} doctrine outweighed the guild order"
        return target, intent, reason

    def _hero_attack(self, enemy: Enemy, dt: float) -> None:
        h = self.hero
        h.attack_timer = max(0.0, h.attack_timer - dt)
        h.ability_timer = max(0.0, h.ability_timer - dt)
        h.shield_timer = max(0.0, h.shield_timer - dt)
        dist = h.pos.distance_to(enemy.pos)

        if h.key == "nyx" and h.ability_timer <= 0 and 120 < dist < 520 and enemy.hp < enemy.max_hp * 0.9:
            direction = h.pos - enemy.pos
            if direction.length_squared() < 1:
                direction = Vec2(1, 0)
            h.pos = enemy.pos + direction.normalize() * 55
            h.ability_timer = 7.0
            h.intent = "SHADOW SKIP"
            h.reason = "Wounded target exposed a finishing route"
            h.flash = 0.35
            h.pose, h.pose_timer = "PHASE", 0.48
            self.log("NYX-7: SHADOW SKIP", HEROES[h.key]["accent"])
            self.emit_presentation("hero_ability")
            dist = h.pos.distance_to(enemy.pos)

        if h.key == "circuit" and h.ability_timer <= 0 and (h.hp < h.max_hp * 0.62 or self._threats_near(h.pos, 240) >= 2):
            h.shield_timer = 4.5
            h.ability_timer = 10.0
            h.intent = "SANCTUARY PROTOCOL"
            h.pose, h.pose_timer = "WARD", 0.75
            h.reason = "Multiple threat vectors exceed safe doctrine"
            self.log("SANCTUARY FIELD ACTIVE", HEROES[h.key]["accent"])
            self.emit_presentation("hero_ability")

        if h.key == "vesper" and h.ability_timer <= 0:
            candidates = [e for e in self.enemies if not e.dead and e.overridden <= 0 and e.kind in {"construct", "cantor"} and not e.is_boss and h.pos.distance_to(e.pos) < 390]
            if candidates:
                target = min(candidates, key=lambda e: h.pos.distance_squared_to(e.pos))
                target.overridden = 5.4
                self.behavior_counts["objective_bypass"] += 1
                h.shield_timer = max(h.shield_timer, 1.4)
                h.ability_timer = 12.0
                h.intent = "GHOST OVERRIDE"
                h.pose, h.pose_timer = "OVERRIDE", 0.75
                h.reason = "Machine intelligence presents a controllable host"
                self.log(f"{target.kind.upper()} OVERRIDDEN", HEROES[h.key]["accent"])
                self.emit_presentation("hero_ability")

        if h.key == "morrow" and h.ability_timer <= 0 and h.corruption < 88:
            corpses = [e for e in self.enemies if e.dead and not e.is_boss and not e.echo_reanimated and h.pos.distance_to(e.pos) < 430]
            if corpses:
                echo = min(corpses, key=lambda e: h.pos.distance_squared_to(e.pos))
                echo.dead = False
                echo.echo_reanimated = True
                echo.hp = max(24.0, echo.max_hp * 0.46)
                echo.overridden = 9.0
                echo.hit_flash = 0.35
                h.ability_timer = 9.5
                h.corruption = min(100.0, h.corruption + 15.0)
                h.resolve = max(0.0, h.resolve - 4.0)
                h.intent = "ECHO REVENANT"
                h.reason = "Defeated host converted into temporary contract support"
                h.pose, h.pose_timer = "REANIMATE", 0.82
                self.behavior_counts["echo_reanimations"] += 1
                self.log(f"{echo.kind.upper()} RAISED AS ECHO", HEROES[h.key]["accent"])
                self.emit_presentation("hero_ability")

        if dist <= h.attack_range and h.attack_timer <= 0 and self._line_clear(h.pos, enemy.pos):
            h.attack_timer = h.attack_delay
            dealt = h.damage
            if h.key == "vesper" and enemy.is_boss and self.quest_key == "recovery":
                dealt *= 1.25
            if self.support_key == "nyx" and enemy.hp / max(1.0, enemy.max_hp) <= 0.30:
                dealt *= 1.18
                self.behavior_counts["link_assists"] += 1
            if h.attack_range < 120:
                enemy.hp -= dealt
                enemy.hit_flash = 0.20
                h.flash = 0.12
                h.pose, h.pose_timer = "SLASH", 0.26
                self.emit_presentation("hero_melee")
                self.emit_presentation("impact_enemy")
            else:
                d = enemy.pos - h.pos
                if d.length_squared() > 0:
                    self.projectiles.append(Projectile(Vec2(h.pos), d.normalize() * 580, dealt, 1.1, True, HEROES[h.key]["color"], 5))
                    h.pose, h.pose_timer = "FIRE", 0.22
                    self.emit_presentation("hero_ranged")
            if enemy.hp <= 0 and not enemy.dead:
                enemy.dead = True
                h.kills += 1
                if h.key == "nyx":
                    h.hp = min(h.max_hp, h.hp + 13.0)
                    h.resolve = min(h.max_resolve, h.resolve + 3.0)
                elif h.key == "circuit":
                    h.hp = min(h.max_hp, h.hp + 5.0)
                    h.resolve = min(h.max_resolve, h.resolve + 1.5)
                if enemy.is_boss:
                    self.boss_defeated = True
                    self.boss_phase_note = "SOVEREIGN DEFEATED"
                    self.log(f"{self.boss_profile['name']} DEFEATED", self.boss_profile["accent"])
                    self.emit_presentation("boss_down")
                if self.quest_key == "purge":
                    self.objective_progress += 1
                self.log(f"{enemy.kind.upper()} DISMANTLED", enemy.color)
                self.emit_presentation("enemy_down")

    def _update_hero(self, dt: float) -> None:
        h = self.hero
        h.flash = max(0.0, h.flash - dt)
        goal, intent, reason = self._hero_goal()
        h.intent, h.reason = intent, reason
        aligned = self._order_aligned(intent)
        if aligned:
            self.order_follow_seconds += dt
        else:
            self.order_override_seconds += dt
        if self.order_status != self.last_order_status:
            if self.order_status == "COMPLYING":
                self.behavior_counts["order_followed"] += 1
                self.log(f"ORDER FOLLOWED / {self.order['short']}", self.order["color"])
            else:
                self.behavior_counts["order_overridden"] += 1
                self.log("ORDER OVERRIDDEN BY PERSONALITY", HEROES[h.key]["accent"])
            self.last_order_status = self.order_status
        if intent != h.last_intent:
            if intent == "FINISHING WOUNDED TARGET":
                self.behavior_counts["wounded_pursuit"] += 1
                self.log("PERSONALITY: WOUNDED PURSUIT", HEROES[h.key]["accent"])
            elif intent == "INTERCEPTING THREAT":
                self.behavior_counts["civilian_intercepts"] += 1
                self.log("PERSONALITY: PROTECTIVE INTERCEPT", HEROES[h.key]["accent"])
            elif intent == "SETTING GHOST OVERRIDE":
                self.log("PERSONALITY: MACHINE BYPASS", HEROES[h.key]["accent"])
            elif intent == "TACTICAL WITHDRAWAL":
                self.behavior_counts["tactical_withdrawals"] += 1
                self.log("PERSONALITY: WITHDRAWAL THRESHOLD", HEROES[h.key]["accent"])
            h.last_intent = intent
        enemy = self._nearest_enemy(h.pos)
        if h.key == "vesper" and enemy and goal != enemy.pos and h.pos.distance_to(enemy.pos) < 135:
            away = h.pos - enemy.pos
            if away.length_squared() > 1:
                self._move_entity(h.pos, away.normalize() * h.speed * 1.18 * dt, 18)
            h.intent = "EVADING DIRECT PRESSURE"
            h.reason = "Self-preservation doctrine protects the objective route"
        elif enemy and (goal == enemy.pos or (h.pos.distance_to(enemy.pos) < h.attack_range * 1.05 and self._line_clear(h.pos, enemy.pos))):
            h.target_label = enemy.kind.upper()
            self._hero_attack(enemy, dt)
            dist = h.pos.distance_to(enemy.pos)
            preferred = max(48.0, h.attack_range * (0.78 if h.key == "vesper" else 0.58))
            if dist > preferred:
                self._move_toward(h.pos, enemy.pos, h.speed, dt, 18)
            elif h.key == "vesper" and dist < 150:
                away = h.pos - enemy.pos
                if away.length_squared() > 1:
                    self._move_entity(h.pos, away.normalize() * h.speed * dt, 18)
        else:
            h.target_label = "OBJECTIVE"
            self._move_toward(h.pos, goal, h.speed, dt, 18)

        if h.intent == "TACTICAL WITHDRAWAL" and h.pos.distance_to(self.extraction_point) < 58 and (h.hp / h.max_hp < 0.20 or h.resolve < 16):
            self.status = "FAILED"
            self.result_reason = "Hero withdrew after vitality or resolve collapsed"
            self.log("CONTRACT FAILED — HERO WITHDREW", (255, 126, 84))
            return

        # Objective contact.
        if self.quest_key == "recovery" and not self.artifact_collected and h.pos.distance_to(self.artifact_point) < 44:
            self.artifact_collected = True
            h.artifact = True
            self.objective_progress = 1
            h.resolve = min(h.max_resolve, h.resolve + 7.0 * h.curiosity)
            self.log("BLACKGLASS RELIQUARY SECURED", QUESTS[self.quest_key]["color"])
            self.emit_presentation("objective")
            self._trigger_complication()
        if self.quest_key == "rescue":
            for civ in self.civilians:
                if not civ.rescued and h.pos.distance_to(civ.pos) < 48:
                    civ.rescued = True
                    h.rescued += 1
                    self.objective_progress = h.rescued
                    h.resolve = min(h.max_resolve, h.resolve + 8.0 * h.altruism)
                    self.log("PILGRIM LINKED TO ESCORT", (88, 255, 216))
                    self.emit_presentation("civilian_link")
                    if h.rescued == 1:
                        self._trigger_complication()
            rescued = [c for c in self.civilians if c.rescued and not c.extracted]
            for i, civ in enumerate(rescued):
                target = h.pos + Vec2(-34 - (i % 2) * 22, 30 + i * 22)
                self._move_toward(civ.pos, target, 132, dt, 12)

    def _trigger_complication(self) -> None:
        if self.complication_triggered:
            return
        self.complication_triggered = True
        self.complication_timer = 8.0
        self.complication_note = "ACTIVE"
        self.behavior_counts["complication_responses"] += 1
        color = self.complication["color"]
        self.log(f"COMPLICATION / {self.complication['name']}", color)
        if self.quest_key == "purge":
            for i, kind in enumerate(("revenant", "construct")):
                x, y = self.world_markers[f"comp_{i}"]
                self._spawn_enemy(x, y, kind)
            self.total_objectives += 2
            self.complication_note = "REINFORCEMENTS ENTERED"
        elif self.quest_key == "recovery":
            self.extraction_point = Vec2(self.world_markers["reroute_extraction"])
            for i, kind in enumerate(("construct", "cantor")):
                x, y = self.world_markers[f"comp_{i}"]
                self._spawn_enemy(x, y, kind)
            self.complication_note = "EXTRACTION REROUTED"
        else:
            for i, kind in enumerate(("revenant", "construct")):
                x, y = self.world_markers[f"comp_{i}"]
                self._spawn_enemy(x, y, kind)
            for civ in self.civilians:
                if not civ.rescued:
                    civ.panic = 1.0
            self.complication_note = "PANIC AMBUSH"
        # One additional reinforcement per joined sidekick keeps complication
        # pressure proportional without multiplying boss stats.
        extra = self._spawn_party_scaled_enemies(len(self.sidekicks), complication=True)
        self.enemy_scale_complication += extra
        if self.quest_key == "purge":
            self.total_objectives += extra

    def _update_complication(self, dt: float) -> None:
        if self.quest_key == "purge" and not self.complication_triggered and self.hero.kills >= 3:
            self._trigger_complication()
        if not self.complication_triggered:
            return
        if not self.boss_spawned:
            if self.quest_key == "purge" and self.hero.kills >= 5:
                self._spawn_signature_boss()
            elif self.quest_key == "recovery" and self.artifact_collected:
                self._spawn_signature_boss()
            elif self.quest_key == "rescue" and self.hero.rescued >= 2:
                self._spawn_signature_boss()
        self.complication_timer = max(0.0, self.complication_timer - dt)
        self.boss_intro_timer = max(0.0, self.boss_intro_timer - dt)
        if not self.complication_resolved:
            if self.quest_key == "purge":
                self.complication_resolved = self.hero.kills >= self.total_objectives
            elif self.quest_key == "recovery":
                self.complication_resolved = self.artifact_collected and self.hero.pos.distance_to(self.extraction_point) < 150
            else:
                self.complication_resolved = self.hero.rescued >= 2
            if self.complication_resolved:
                self.complication_note = "CONTAINED"
                self.log("COMPLICATION CONTAINED", (108, 255, 190))

    def _damage_hero(self, damage: float) -> None:
        h = self.hero
        # Compatibility creates a modest preparation advantage without making
        # off-role deployments impossible.  This is deliberately capped so
        # equipment and doctrine choices still matter.
        fit_guard = min(0.14, max(0.0, float(self.fit["score"]) - 0.60) * 0.42)
        damage *= 1.0 - fit_guard
        # NYX can complete escort work only when deliberately prepared for it.
        # Without a protection order or Pilgrim Beacon, wounded-target pursuit
        # leaves the exposed blade taking concentrated rescue-lane fire.
        if self.quest_key == "rescue" and h.key == "nyx" and self.equipment_key != "beacon" and self.order_key != "protect":
            damage *= 1.90
        if h.key == "vesper" and h.intent in {"SEEKING RELIQUARY", "RETURNING TO GATE", "EVADING DIRECT PRESSURE"}:
            damage *= 0.62
        elif h.key == "vesper" and h.intent == "CONFRONTING SOVEREIGN" and self.quest_key == "recovery":
            damage *= 0.72
        if self.equipment_key == "aegis":
            damage *= 0.90
        if h.shield_timer > 0:
            damage *= 0.28
        h.hp -= damage
        if h.hp <= 0:
            h.hp = 0
        if self.equipment_key == "ampoule" and not self.consumable_used and h.hp > 0 and h.hp / max(1.0, h.max_hp) <= 0.34:
            recovered = h.max_hp * 0.34
            h.hp = min(h.max_hp, h.hp + recovered)
            h.stress = min(100.0, h.stress + 15.0)
            h.resolve = max(0.0, h.resolve - 6.0)
            self.consumable_used = True
            self.equipment_note = "AMPOULE SPENT / RECOVERY SHOCK"
            self.log("VOIDGLASS AMPOULE AUTO-TRIGGERED", self.equipment["color"])
        mismatch_pressure = max(0.0, 0.62 - float(self.fit["score"]))
        h.stress = min(100.0, h.stress + damage * (0.09 + mismatch_pressure * 0.16))
        h.resolve = max(0.0, h.resolve - damage * (0.18 + mismatch_pressure * 0.22))
        h.flash = 0.22
        h.hit_flash = 0.26
        h.pose, h.pose_timer = "HIT", 0.28
        self.emit_presentation("impact_hero")
        if h.hp <= 0 and self.status == "ACTIVE":
            h.hp = 0
            self.status = "FAILED"
            self.result_reason = "Hero fell before the contract was completed"
            self.log("CONTRACT FAILED — HERO DOWN", (255, 65, 92))

    def _nearest_active_echo(self, pos: Vec2, max_distance: float = 300.0) -> Enemy | None:
        echoes = [e for e in self.enemies if not e.dead and e.echo_reanimated and e.overridden > 0 and e.pos.distance_to(pos) <= max_distance]
        return min(echoes, key=lambda e: pos.distance_squared_to(e.pos), default=None)

    def _update_enemies(self, dt: float) -> None:
        h = self.hero
        for e in self.enemies:
            if e.dead:
                continue
            target_hero = self._nearest_party_member(e.pos)
            e.attack_timer = max(0.0, e.attack_timer - dt)
            e.pulse += dt
            if e.is_boss:
                hp_ratio = e.hp / max(1.0, e.max_hp)
                if hp_ratio <= 0.5 and e.boss_phase == 1:
                    e.boss_phase = 2
                    e.speed *= 1.12
                    e.attack_delay *= 0.78
                    e.damage *= 1.12
                    self.boss_phase_note = f"PHASE II / {self.boss_profile['phase_two']}"
                    self.behavior_counts["boss_phase_changes"] += 1
                    self.log(self.boss_phase_note, self.boss_profile["accent"])
                    self.emit_presentation("boss_phase")
                e.boss_special_timer = max(0.0, e.boss_special_timer - dt)
                if e.boss_special_timer <= 0 and e.pos.distance_to(target_hero.pos) < 430:
                    e.boss_special_timer = 3.8 if e.boss_phase == 1 else 2.7
                    if self.quest_key == "purge":
                        rupture_distance = e.pos.distance_to(target_hero.pos)
                        if rupture_distance < 320:
                            close = rupture_distance < 150
                            shock = (12.0 if self.support_key == "circuit" else 17.0) if close else (7.5 if self.support_key == "circuit" else 11.5)
                            self._damage_party_member(target_hero, shock)
                            self._damage_cover_near(e.pos, 285.0, 26.0 if e.boss_phase == 1 else 38.0)
                            self.log("ASH SAINT / CHOIR RUPTURE", self.boss_profile["accent"])
                            self.emit_presentation("boss_special")
                    elif self.quest_key == "recovery":
                        delta = target_hero.pos - e.pos
                        if delta.length_squared() > 0:
                            for turn in (-13, 0, 13):
                                vel = delta.normalize().rotate(turn) * 410
                                self.projectiles.append(Projectile(Vec2(e.pos), vel, e.damage * 0.82, 1.8, False, self.boss_profile["color"], 7))
                            self.log("MIRROR ABBOT / REFLECTION CASCADE", self.boss_profile["accent"])
                            self.emit_presentation("boss_special")
                    else:
                        for civ in self.civilians:
                            if not civ.extracted:
                                civ.panic = min(1.0, civ.panic + 0.28)
                        self.hero.resolve = max(0.0, self.hero.resolve - 4.0)
                        self.log("LAST CONDUCTOR / PANIC BROADCAST", self.boss_profile["accent"])
                        self.emit_presentation("boss_special")
            was_overridden = e.overridden > 0
            e.overridden = max(0.0, e.overridden - dt)
            if was_overridden and e.overridden <= 0 and e.echo_reanimated:
                e.dead = True
                self.log("ECHO HOST COLLAPSED", HEROES["morrow"]["accent"])
                continue
            if e.overridden > 0:
                target = self._nearest_enemy(e.pos)
                if target and target is not e:
                    d = e.pos.distance_to(target.pos)
                    if d > e.attack_range * 0.75:
                        self._move_toward(e.pos, target.pos, e.speed * 0.9, dt, e.radius)
                    elif e.attack_timer <= 0:
                        e.attack_timer = e.attack_delay
                        target.hp -= e.damage * 1.45
                        self.emit_presentation("enemy_melee")
                        self.emit_presentation("impact_enemy")
                        if target.hp <= 0 and not target.dead:
                            target.dead = True
                            if target.is_boss:
                                self.boss_defeated = True
                                self.boss_phase_note = "SOVEREIGN DEFEATED"
                                self.log(f"{self.boss_profile['name']} DEFEATED", self.boss_profile["accent"])
                                self.emit_presentation("boss_down")
                            self.log("OVERRIDDEN HOST DESTROYED A THREAT", (104, 255, 180))
                            self.emit_presentation("enemy_down")
                continue

            echo_target = self._nearest_active_echo(e.pos, 330.0 if e.is_boss else 270.0)
            if echo_target is not None:
                echo_distance = e.pos.distance_to(echo_target.pos)
                if echo_distance > e.attack_range * 0.78:
                    self._move_toward(e.pos, echo_target.pos, e.speed, dt, e.radius)
                elif e.attack_timer <= 0 and self._line_clear(e.pos, echo_target.pos):
                    e.attack_timer = e.attack_delay
                    echo_target.hp -= e.damage
                    self.behavior_counts["echo_damage_absorbed"] += int(round(e.damage))
                    e.pose, e.pose_timer = ("FIRE" if e.attack_range > 120 else "STRIKE"), 0.30
                    echo_target.hit_flash = 0.22
                    self.emit_presentation("enemy_melee" if e.attack_range <= 120 else "enemy_ranged")
                    self.emit_presentation("impact_enemy")
                    if echo_target.hp <= 0:
                        echo_target.dead = True
                        echo_target.overridden = 0.0
                        self.log("ECHO HOST ABSORBED THE ATTACK", HEROES["morrow"]["accent"])
                continue

            d = e.pos.distance_to(target_hero.pos)
            if target_hero is h and h.key == "vesper" and h.intent in {"SEEKING RELIQUARY", "RETURNING TO GATE", "EVADING DIRECT PRESSURE"} and d > 285:
                # Vesper's ghost operative doctrine reduces unnecessary pursuit
                # while she remains focused on a non-combat objective.
                continue
            if e.kind == "cantor":
                # Support unit heals its nearest ally before attacking.
                ally = min((a for a in self.enemies if not a.dead and a is not e and a.hp < a.max_hp), key=lambda a: e.pos.distance_squared_to(a.pos), default=None)
                if ally and e.pos.distance_to(ally.pos) < 260 and e.attack_timer <= 0:
                    ally.hp = min(ally.max_hp, ally.hp + 11)
                    e.attack_timer = 1.8
                    e.pose, e.pose_timer = "CHANNEL", 0.8
                    continue
            if d > e.attack_range * 0.78:
                self._move_toward(e.pos, target_hero.pos, e.speed, dt, e.radius)
            elif e.attack_timer <= 0 and self._line_clear(e.pos, target_hero.pos):
                e.attack_timer = e.attack_delay
                if e.attack_range > 120:
                    direction = target_hero.pos - e.pos
                    if direction.length_squared() > 0:
                        self.projectiles.append(Projectile(Vec2(e.pos), direction.normalize() * 370, e.damage, 1.6, False, e.color, 6))
                        e.pose, e.pose_timer = "FIRE", 0.28
                        self.emit_presentation("enemy_ranged")
                else:
                    e.pose, e.pose_timer = "STRIKE", 0.30
                    self.emit_presentation("enemy_melee")
                    self._damage_party_member(target_hero, e.damage)

    def _update_projectiles(self, dt: float) -> None:
        alive: list[Projectile] = []
        for p in self.projectiles:
            p.pos += p.vel * dt
            p.life -= dt
            blocker = self._world_object_at(p.pos, "projectiles")
            if blocker is not None:
                impact_scale = 0.78 if p.friendly else 0.46
                self._damage_world_obstacle(blocker, p.damage * impact_scale, "PROJECTILE")
                continue
            if p.life <= 0 or not WORLD.collidepoint(p.pos):
                continue
            if p.friendly:
                hit = None
                for e in self.enemies:
                    if not e.dead and e.overridden <= 0 and p.pos.distance_to(e.pos) < p.radius + e.radius:
                        hit = e
                        break
                if hit:
                    hit.hp -= p.damage
                    hit.hit_flash = 0.20
                    self.emit_presentation("impact_enemy")
                    if hit.hp <= 0 and not hit.dead:
                        hit.dead = True
                        self.hero.kills += 1
                        if self.hero.key == "nyx":
                            self.hero.hp = min(self.hero.max_hp, self.hero.hp + 13.0)
                            self.hero.resolve = min(self.hero.max_resolve, self.hero.resolve + 3.0)
                        elif self.hero.key == "circuit":
                            self.hero.hp = min(self.hero.max_hp, self.hero.hp + 5.0)
                            self.hero.resolve = min(self.hero.max_resolve, self.hero.resolve + 1.5)
                        if hit.is_boss:
                            self.boss_defeated = True
                            self.boss_phase_note = "SOVEREIGN DEFEATED"
                            self.log(f"{self.boss_profile['name']} DEFEATED", self.boss_profile["accent"])
                            self.emit_presentation("boss_down")
                        if self.quest_key == "purge":
                            self.objective_progress += 1
                        self.log(f"{hit.kind.upper()} DISMANTLED", hit.color)
                        self.emit_presentation("enemy_down")
                    continue
            else:
                struck = next((member for member in self._living_party() if p.pos.distance_to(member.pos) < p.radius + 18), None)
                if struck is not None:
                    self._damage_party_member(struck, p.damage)
                    continue
            alive.append(p)
        self.projectiles = alive

    def _update_actor_motion(self, dt: float, old_hero: Vec2, old_sidekicks: list[Vec2], old_enemies: list[Vec2], old_civilians: list[Vec2]) -> None:
        h = self.hero
        h.anim_clock += dt
        if h.anim_clock >= 0.085:
            h.anim_clock %= 0.085
            h.anim_frame = (h.anim_frame + 1) % 4
        for e in self.enemies:
            e.anim_clock += dt
            if e.anim_clock >= 0.11:
                e.anim_clock %= 0.11
                e.anim_frame = (e.anim_frame + 1) % 4
        for c in self.civilians:
            c.anim_clock += dt
            if c.anim_clock >= 0.13:
                c.anim_clock %= 0.13
                c.anim_frame = (c.anim_frame + 1) % 4
        h.velocity = (h.pos - old_hero) / max(dt, 1e-6)
        if h.velocity.length_squared() > 9:
            h.facing = h.velocity.normalize()
            h.walk_phase += dt * (6.0 + h.velocity.length() / 65.0)
        h.pose_timer = max(0.0, h.pose_timer - dt)
        h.hit_flash = max(0.0, h.hit_flash - dt)
        if h.pose_timer <= 0:
            if h.velocity.length_squared() > 100:
                h.pose = "RUN" if h.velocity.length() > h.speed * 0.82 else "MOVE"
            elif h.intent in {"SETTING GHOST OVERRIDE", "SANCTUARY PROTOCOL"}:
                h.pose = "CHANNEL"
            else:
                h.pose = "READY"

        for member, old in zip(self.sidekicks, old_sidekicks):
            member.anim_clock += dt
            if member.anim_clock >= 0.085:
                member.anim_clock %= 0.085
                member.anim_frame = (member.anim_frame + 1) % 4
            member.velocity = (member.pos - old) / max(dt, 1e-6)
            if member.velocity.length_squared() > 9:
                member.facing = member.velocity.normalize()
                member.walk_phase += dt * (6.0 + member.velocity.length() / 65.0)
            member.pose_timer = max(0.0, member.pose_timer - dt)
            member.hit_flash = max(0.0, member.hit_flash - dt)
            if member.hp <= 0:
                member.pose = "DOWNED"
            elif member.pose_timer <= 0:
                member.pose = "MOVE" if member.velocity.length_squared() > 100 else "READY"

        for e, old in zip(self.enemies, old_enemies):
            e.velocity = (e.pos - old) / max(dt, 1e-6)
            if e.velocity.length_squared() > 9:
                e.facing = e.velocity.normalize()
                e.walk_phase += dt * (5.0 + e.velocity.length() / 70.0)
            e.pose_timer = max(0.0, e.pose_timer - dt)
            e.hit_flash = max(0.0, e.hit_flash - dt)
            if e.pose_timer <= 0:
                e.pose = "MOVE" if e.velocity.length_squared() > 100 else ("OVERRIDDEN" if e.overridden > 0 else "READY")

        for civ, old in zip(self.civilians, old_civilians):
            civ.velocity = (civ.pos - old) / max(dt, 1e-6)
            if civ.velocity.length_squared() > 9:
                civ.facing = civ.velocity.normalize()
                civ.walk_phase += dt * 5.5
                civ.pose = "ESCORTED"
            elif civ.rescued:
                civ.pose = "FOLLOWING"
            else:
                civ.pose = "WAITING"
            threat = self._nearest_enemy(civ.pos)
            panic = max(0.0, min(1.0, 1.0 - (civ.pos.distance_to(threat.pos) / 360.0))) if threat else 0.0
            panic_factor = 0.42 if self.equipment_key == "beacon" else 1.0
            if self.aftermath_key == "open_index":
                panic_factor *= 0.75
            civ.panic = panic * panic_factor

    def inspect_actor_at(self, pos: Vec2) -> dict:
        candidates: list[tuple[float, dict]] = [(self.hero.pos.distance_to(pos), {"type": "hero", "index": 0})]
        candidates.extend((e.pos.distance_to(pos), {"type": "enemy", "index": i}) for i, e in enumerate(self.enemies) if not e.dead)
        candidates.extend((c.pos.distance_to(pos), {"type": "civilian", "index": i}) for i, c in enumerate(self.civilians) if not c.extracted)
        distance, selection = min(candidates, key=lambda item: item[0])
        if distance <= 58:
            self.inspection = selection
        return dict(self.inspection)

    def inspected_actor(self) -> dict:
        kind = self.inspection.get("type", "hero")
        index = int(self.inspection.get("index", 0))
        if kind == "enemy" and 0 <= index < len(self.enemies):
            e = self.enemies[index]
            spec = self.boss_profile if e.is_boss else ENEMY_VARIANTS[self.quest_key][e.kind]
            return {
                "type": "enemy", "name": spec["name"], "role": spec["role"],
                "origin": spec["origin"], "body": spec["body"], "weapon": spec["weapon"],
                "behavior": spec["behavior"], "weakness": spec["weakness"],
                "hp": e.hp, "max_hp": e.max_hp, "pose": e.pose,
                "condition": (self.boss_phase_note if e.is_boss else ("OVERRIDDEN" if e.overridden > 0 else ("CRITICAL" if e.hp/e.max_hp < .25 else ("DAMAGED" if e.hp/e.max_hp < .65 else "FUNCTIONAL")))),
                "field_condition": "SIGNATURE SOVEREIGN" if e.is_boss else "CONTRACT HOSTILE",
                "color": spec.get("color", e.color),
            }
        if kind == "civilian" and 0 <= index < len(self.civilians):
            c = self.civilians[index]
            spec = CIVILIAN_ROLES[c.role_index % len(CIVILIAN_ROLES)]
            return {
                "type": "civilian", "name": spec["role"], "role": "CIVILIAN / ESCORT SUBJECT",
                "origin": spec["detail"], "body": spec["visual"], "weapon": "UNARMED",
                "behavior": "Following hero" if c.rescued else "Awaiting rescue link",
                "weakness": "Vulnerable to nearby combat pressure", "hp": 1, "max_hp": 1,
                "pose": c.pose, "condition": "LINKED" if c.rescued else ("PANICKED" if c.panic > .5 else "STRANDED"),
                "color": (96, 255, 212) if c.rescued else (218, 230, 240),
            }
        h = self.hero
        spec = HEROES[h.key]
        ratio = h.hp / max(1.0, h.max_hp)
        return {
            "type": "hero", "name": spec["name"], "role": spec["title"],
            "origin": spec["origin"], "body": spec["body"], "weapon": spec["weapon_detail"],
            "behavior": h.reason, "weakness": spec["weakness"], "hp": h.hp, "max_hp": h.max_hp,
            "pose": h.pose, "condition": "CRITICAL" if ratio < .25 else ("WOUNDED" if ratio < .60 else ("STRAINED" if h.stress > 50 else "COMBAT READY")),
            "color": spec["color"], "ability": spec["ability_detail"], "armor": spec["armor"],
            "mission_kit": self.equipment["name"], "equipment_note": self.equipment_note,
            "field_condition": h.field_condition, "corruption": round(h.corruption, 1),
        }

    def _finalize_result(self) -> None:
        if self.result_finalized or self.status == "ACTIVE":
            return
        h = self.hero
        fit = float(self.fit["score"])
        if self.status == "SUCCESS":
            if fit >= 0.78:
                self.strain_delta = -6
                self.result_consequence = "CONFIDENCE REINFORCED"
            elif fit >= 0.52:
                self.strain_delta = 3 + int(h.stress / 35.0)
                self.result_consequence = "FIELD FATIGUE"
            else:
                self.strain_delta = 10 + int(h.stress / 22.0)
                self.result_consequence = "MISMATCH STRAIN"
        else:
            self.strain_delta = 10 + int((1.0 - fit) * 15.0) + int(h.stress / 24.0)
            if h.hp / max(1.0, h.max_hp) < 0.22:
                self.result_consequence = "CRITICAL WOUND"
            elif h.resolve < 18:
                self.result_consequence = "RESOLVE SHOCK"
            else:
                self.result_consequence = "MISSION TRAUMA"
        if h.key == "morrow" and h.corruption >= 55:
            self.strain_delta += 4
            if self.status == "SUCCESS":
                self.result_consequence = "ECHO CONTAMINATION"
        if self.order_key != "balanced" and self.order_override_seconds > self.order_follow_seconds * 1.25:
            self.strain_delta += 2
        if self.equipment_fit["score"] >= 0.80:
            self.strain_delta -= 2
        elif self.equipment_fit["score"] < 0.45:
            self.strain_delta += 3
        self.strain_delta = max(-10, min(30, self.strain_delta))
        reward = contract_reward(
            self.quest_key, self.status, self.time,
            h.hp / max(1.0, h.max_hp),
            self.complication_resolved, self.order_status,
        )
        self.reward_credits = int(reward["credits"])
        self.reward_renown = int(reward["renown"])
        self.reward_notes = list(reward["notes"])
        if self.boss_defeated:
            self.reward_credits += 350
            self.reward_renown += 1
            self.reward_notes.append("SIGNATURE SOVEREIGN")
        if self.support:
            self.reward_notes.append(f"HEX LINK MASTERY {self.support_mastery}")
        if self.aftermath_key != "none":
            self.reward_notes.append(self.aftermath["name"])
        self.result_finalized = True

    def _check_end(self) -> None:
        if self.status != "ACTIVE":
            return
        h = self.hero
        if self.quest_key == "purge" and self.boss_spawned and self.boss_defeated and not any(not e.dead and e.overridden <= 0 for e in self.enemies):
            self.status = "SUCCESS"
            self.objective_progress = self.total_objectives
            self.result_reason = "The Ashen Choir was completely purged"
            self.log("CONTRACT COMPLETE", (110, 255, 188))
        elif self.quest_key == "recovery" and self.artifact_collected and self.boss_defeated and h.pos.distance_to(self.extraction_point) < 60:
            self.status = "SUCCESS"
            self.objective_progress = self.total_objectives
            self.result_reason = "The Blackglass Reliquary reached extraction"
            self.log("RELIQUARY EXTRACTED", (110, 255, 188))
        elif self.quest_key == "rescue":
            if all(c.rescued for c in self.civilians) and self.boss_defeated and h.pos.distance_to(self.extraction_point) < 70:
                for c in self.civilians:
                    c.extracted = True
                    self.emit_presentation("objective")
                self.status = "SUCCESS"
                self.result_reason = "All three pilgrims survived extraction"
                self.log("ALL PILGRIMS EXTRACTED", (110, 255, 188))
        if self.time > (145 if self.quest_key == "rescue" else 125) and self.status == "ACTIVE":
            self.status = "FAILED"
            self.result_reason = "Contract window expired"
            self.log("CONTRACT WINDOW EXPIRED", (255, 65, 92))

    def update(self, dt: float) -> None:
        for obj in self.world_obstacles:
            obj.update(dt)
        if self.status != "ACTIVE":
            return
        dt = min(dt, 0.05)
        self.time += dt
        old_hero = Vec2(self.hero.pos)
        old_sidekicks = [Vec2(member.pos) for member in self.sidekicks]
        old_enemies = [Vec2(e.pos) for e in self.enemies]
        old_civilians = [Vec2(c.pos) for c in self.civilians]
        mismatch_pressure = max(0.0, 0.58 - float(self.fit["score"]))
        self.hero.stress = min(100.0, self.hero.stress + dt * mismatch_pressure * 2.0)
        self.hero.resolve = max(0.0, self.hero.resolve - dt * mismatch_pressure * 0.32)
        if self.hero.key == "morrow":
            self.hero.corruption = max(0.0, self.hero.corruption - dt * (0.22 if self.support_key == "morrow" else 0.12))
            if self.hero.corruption > 70:
                self.hero.stress = min(100.0, self.hero.stress + dt * 0.65)
                self.hero.resolve = max(0.0, self.hero.resolve - dt * 0.22)
        self._update_hero(dt)
        self._update_sidekicks(dt)
        self._update_enemies(dt)
        self._update_projectiles(dt)
        self._update_complication(dt)
        self._update_actor_motion(dt, old_hero, old_sidekicks, old_enemies, old_civilians)
        self._check_end()
        self._finalize_result()

    def objective_text(self) -> str:
        if self.quest_key == "purge":
            return (f"DEFEAT {self.boss_profile['name']}" if self.boss_spawned and not self.boss_defeated else f"PURGE HOSTILES  {self.objective_progress}/{self.total_objectives}")
        if self.quest_key == "recovery":
            if not self.artifact_collected:
                return "SECURE THE BLACKGLASS RELIQUARY"
            return (f"BREAK {self.boss_profile['name']}" if self.boss_spawned and not self.boss_defeated else "RETURN RELIQUARY TO EXTRACTION")
        return (f"SILENCE {self.boss_profile['name']}" if self.boss_spawned and not self.boss_defeated else f"LOCATE PILGRIMS  {self.objective_progress}/{self.total_objectives}")

    def report(self) -> dict:
        return {
            "hero": self.hero_key,
            "quest": self.quest_key,
            "status": self.status,
            "reason": self.result_reason,
            "time": round(self.time, 3),
            "hero_hp": round(self.hero.hp, 2),
            "kills": self.hero.kills,
            "rescued": self.hero.rescued,
            "artifact": self.artifact_collected,
            "objective_progress": self.objective_progress,
            "objective_total": self.total_objectives,
            "quest_fit_percent": self.fit["percent"],
            "quest_fit_rating": self.fit["rating"],
            "hero_order": self.order_key,
            "equipment": self.equipment_key,
            "equipment_name": self.equipment["name"],
            "equipment_fit_percent": self.equipment_fit["percent"],
            "equipment_fit_rating": self.equipment_fit["rating"],
            "equipment_note": self.equipment_note,
            "support_hero": self.support_key,
            "support_name": self.support["name"] if self.support else "NONE",
            "support_note": self.support_note,
            "support_mastery": self.support_mastery,
            "sidekicks": list(self.sidekick_keys),
            "party_size": self.party_size,
            "sidekick_downs": self.sidekick_downs,
            "enemy_scale_initial": int(getattr(self, "enemy_scale_initial", 0)),
            "enemy_scale_complication": int(getattr(self, "enemy_scale_complication", 0)),
            "chain_chapter": self.chain_chapter,
            "aftermath": self.aftermath_key,
            "aftermath_name": self.aftermath["name"],
            "aftermath_note": self.aftermath_note,
            "consumable_used": self.consumable_used,
            "order_name": self.order["name"],
            "order_status": self.order_status,
            "order_follow_seconds": round(self.order_follow_seconds, 2),
            "order_override_seconds": round(self.order_override_seconds, 2),
            "complication": self.complication["key"],
            "complication_name": self.complication["name"],
            "complication_triggered": self.complication_triggered,
            "complication_resolved": self.complication_resolved,
            "complication_note": self.complication_note,
            "resolve": round(self.hero.resolve, 2),
            "stress": round(self.hero.stress, 2),
            "starting_strain": round(self.hero.starting_strain, 2),
            "field_condition": self.hero.field_condition,
            "corruption": round(self.hero.corruption, 2),
            "animation_frame": self.hero.anim_frame,
            "strain_delta": self.strain_delta,
            "consequence": self.result_consequence,
            "reward_credits": self.reward_credits,
            "reward_renown": self.reward_renown,
            "reward_notes": list(self.reward_notes),
            "behavior_counts": dict(self.behavior_counts),
            "decision_scores": list(self.hero.decision_scores),
            "site": self.environment["site"],
            "district": self.environment["district"],
            "site_code": self.environment["site_code"],
            "environment_hazard": self.environment["hazard"],
            "signature_boss": self.boss_profile["name"],
            "boss_spawned": self.boss_spawned,
            "boss_defeated": self.boss_defeated,
            "world_layout": self.world_layout_name,
            "world_objects": len(self.world_obstacles),
            "world_destructible": sum(1 for o in self.world_obstacles if o.destructible),
            "world_destroyed_cover": sum(1 for o in self.world_obstacles if o.destroyed),
            "boss_phase": self.boss_phase_note,
            "enemy_variants": sorted({(self.boss_profile["name"] if e.is_boss else ENEMY_VARIANTS[self.quest_key][e.kind]["name"]) for e in self.enemies}),
            "actor_detail": {
                "hero_pose": self.hero.pose,
                "hero_condition": self.inspected_actor()["condition"] if self.inspection.get("type") == "hero" else None,
                "enemy_archetypes": sorted({e.kind for e in self.enemies}),
                "civilian_roles": [CIVILIAN_ROLES[c.role_index % len(CIVILIAN_ROLES)]["role"] for c in self.civilians],
            },
        }
