from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Dict, List, Optional, Tuple

Coord = Tuple[int, int]

BASE_BOARD_SIZE = 8
MAX_BOARD_SIZE = 16
MAX_JOURNEY_SECTORS = 5
BOARD_SIZE = BASE_BOARD_SIZE  # compatibility name used by earlier pass notes/tests
NODE_IDS = {"patch", "die", "memory", "core", "extract"}
ABILITY_INVENTORY_MAX = 3
ABILITY_DROP_BASE_CHANCE = 0.55
ABILITY_KINDS = ("arc", "patch", "blink", "snare")
ABILITY_PREFIXES = ("Echo", "Null", "Vector", "Fracture", "Signal", "Glitch")
ABILITY_CORES = ("Burst", "Bloom", "Blink", "Snare", "Surge", "Fold")

SECTOR_NAMES = {
    1: "Archive Gate",
    2: "Signal Causeway",
    3: "Fracture Expanse",
    4: "Outer Signal Grid",
    5: "Matrix Horizon",
}

SECTOR_TAGLINES = {
    1: "Recover the first memory path.",
    2: "The board widens and the route pushes outward.",
    3: "The visible route opens into a wider fracture field.",
    4: "Outer lanes unfold around the squad.",
    5: "The largest current route sector reaches the Matrix Horizon.",
}

SECTOR_THREAT_LABELS = {
    1: "LOW",
    2: "RISING",
    3: "FOCUSED",
    4: "WIDE",
    5: "HORIZON",
}

SECTOR_CHALLENGE_NOTES = {
    1: "Training pressure: base hostile response and short corruption pulses.",
    2: "Rising pressure: tougher enemies and longer corruption pulses.",
    3: "Focused pressure: route starts with more fracture risk and stronger hostile attacks.",
    4: "Wide pressure: the board is larger, giving more route choices and slightly wider hazard spread.",
    5: "Horizon pressure: largest current board with extra distance and steady hostile scaling, not a spike.",
}


@dataclass
class Unit:
    unit_id: str
    name: str
    team: str
    role: str
    pos: Coord
    hp: int
    max_hp: int
    move: int
    attack_range: int
    attack_power: int
    acted: bool = False
    moved: bool = False

    @property
    def alive(self) -> bool:
        return self.hp > 0


@dataclass
class RuleNode:
    node_id: str
    name: str
    pos: Coord
    effect: str
    captured_by: Optional[str] = None


@dataclass
class Tile:
    pos: Coord
    state: str = "stable"  # stable, memory, corrupted, fracture, anchor, signal, extraction, void
    owner: Optional[str] = None
    turns_corrupted: int = 0
    turns_fractured: int = 0


@dataclass
class OneShotAbility:
    ability_id: str
    name: str
    kind: str
    potency: int
    radius: int
    range: int
    source_enemy: str
    pos: Optional[Coord] = None
    collected: bool = False

    def short_label(self) -> str:
        return f"{self.name} [{self.kind.upper()}]"


@dataclass
class GameState:
    width: int = BASE_BOARD_SIZE
    height: int = BASE_BOARD_SIZE
    sector_index: int = 1
    sector_name: str = ""
    cleared_sectors: List[str] = field(default_factory=list)
    turn: str = "player"
    round_index: int = 1
    phase: str = "player_action"
    cursor: Coord = (1, 1)
    selected_unit_id: Optional[str] = "gleebs"
    memory_collected: bool = False
    core_destroyed: bool = False
    extraction_reached: bool = False
    action_die_claimed: bool = False
    overclock_charges: int = 0
    ability_counter: int = 0
    rng_seed: int = 1301
    ability_inventory: List[OneShotAbility] = field(default_factory=list)
    ability_pickups: Dict[str, OneShotAbility] = field(default_factory=dict)
    last_ability_used: Optional[str] = None
    grid_link_charge: int = 0
    log: List[str] = field(default_factory=list)
    tiles: Dict[Coord, Tile] = field(default_factory=dict)
    units: Dict[str, Unit] = field(default_factory=dict)
    nodes: Dict[str, RuleNode] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.sector_index = max(1, min(MAX_JOURNEY_SECTORS, int(self.sector_index)))
        if self.rng_seed == 1301:
            self.rng_seed = 1300 + self.sector_index
        self.width = min(MAX_BOARD_SIZE, BASE_BOARD_SIZE + (self.sector_index - 1) * 2)
        self.height = min(MAX_BOARD_SIZE, BASE_BOARD_SIZE + (self.sector_index - 1) * 2)
        self.sector_name = self.sector_name or SECTOR_NAMES.get(self.sector_index, f"Sector {self.sector_index}")
        layout = self._layout_positions()
        if not self.tiles:
            self._generate_tiles(layout)
        if not self.units:
            self._generate_units(layout)
        if not self.nodes:
            self._generate_nodes(layout)
        if not self.log:
            if self.sector_index == 2:
                self.log_event(f"{self.sector_name} online. Synchronize both Signal Relays to collapse the route lock.")
            elif self.sector_index == 3:
                self.log_event(f"{self.sector_name} online. Stabilize all three Fracture Anchors with Gleebs Patch Pulse.")
            elif self.sector_index == 4:
                self.log_event(f"{self.sector_name} online. Hold both Outer Uplinks through two hostile response cycles.")
            elif self.sector_index == 5:
                self.log_event(f"{self.sector_name} online. Align both Horizon Relays, stabilize the Horizon Fracture, then hold both relays through hostile response.")
            else:
                self.log_event(f"{self.sector_name} online. Extraction Gate is locked until the Core breaks.")

    def _layout_positions(self) -> Dict[str, Coord]:
        layout = {
            "gleebs": (1, 1),
            "guard": (0, 1),
            "runner": (1, 0),
            "patch": (1, self.height - 2),
            "die": (min(self.width - 4, 3 + (self.sector_index - 1) * 2), min(self.height - 4, 3 + (self.sector_index - 1) * 2)),
            "memory": (self.width - 3, self.height - 3),
            "core": (self.width - 2, self.height - 2),
            "extract": (0, self.height - 1),
            "anomaly": (self.width - 2, self.height - 3),
            "sentry": (self.width - 3, self.height - 1),
        }
        if self.sector_index == 4:
            # Put the two required uplinks on opposite outer lanes so the 14x14
            # board width becomes an actual tactical commitment.
            layout["patch"] = (1, self.height - 2)
            layout["memory"] = (self.width - 2, 1)
        if self.sector_index == 5:
            # The finale reuses two distant lanes plus a central fracture so the
            # player has to synthesize the objective language learned earlier.
            layout["patch"] = (2, self.height - 3)
            layout["memory"] = (self.width - 3, 2)
            layout["die"] = (self.width // 2, self.height // 2)
            layout["core"] = (self.width - 2, self.height - 2)
        return layout

    def _generate_tiles(self, layout: Dict[str, Coord]) -> None:
        for y in range(self.height):
            for x in range(self.width):
                self.tiles[(x, y)] = Tile(pos=(x, y))
        self.tiles[layout["memory"]].state = "memory"
        self.tiles[layout["core"]].state = "corrupted"
        self.tiles[layout["patch"]].state = "anchor"
        self.tiles[layout["die"]].state = "signal"
        self.tiles[layout["extract"]].state = "anchor"
        if self.sector_index == 3:
            # Sector 3 turns the existing patch/die/memory positions into persistent
            # fracture objectives. They remain hazardous until Gleebs stabilizes
            # them with the already-existing Patch Pulse action.
            for node_id in ("patch", "die", "memory"):
                tile = self.tiles[layout[node_id]]
                tile.state = "fracture"
                tile.turns_fractured = 9999
        if self.sector_index == 4:
            # Sector 4 uses the wide board as the objective: two distant uplinks
            # must be held simultaneously rather than merely touched once.
            self.tiles[layout["patch"]].state = "signal"
            self.tiles[layout["memory"]].state = "signal"
        if self.sector_index == 5:
            # Stage 1 begins with two Horizon Relays. The center fracture is
            # activated only after both relays are aligned.
            self.tiles[layout["patch"]].state = "signal"
            self.tiles[layout["memory"]].state = "signal"
            self.tiles[layout["die"]].state = "signal"
        # Later sectors visibly add more journey terrain without changing the core rules.
        if self.sector_index >= 2:
            for pos in ((self.width - 1, 1), (self.width - 1, 2), (2, self.height - 1)):
                if self.in_bounds(pos) and pos not in layout.values():
                    self.tiles[pos].state = "signal"
        if self.sector_index >= 2:
            for pos in ((self.width - 4, self.height - 3),):
                if self.in_bounds(pos) and pos not in layout.values():
                    self.tiles[pos].state = "fracture"
                    self.tiles[pos].turns_fractured = self.fracture_warning_duration()
        if self.sector_index >= 3:
            for pos in ((self.width - 1, self.height - 4), (self.width - 4, self.height - 1)):
                if self.in_bounds(pos) and pos not in layout.values():
                    self.tiles[pos].state = "fracture"
                    self.tiles[pos].turns_fractured = self.fracture_warning_duration()
        if self.sector_index >= 4:
            # Bigger-world sectors gain readable side lanes so the wider board does not feel empty.
            mid_x = self.width // 2
            mid_y = self.height // 2
            for pos in ((mid_x, 1), (mid_x, self.height - 2), (1, mid_y), (self.width - 2, mid_y)):
                if self.in_bounds(pos) and pos not in layout.values():
                    self.tiles[pos].state = "signal"
            for pos in ((self.width - 5, self.height - 5), (3, self.height - 4)):
                if self.in_bounds(pos) and pos not in layout.values():
                    self.tiles[pos].state = "fracture"
                    self.tiles[pos].turns_fractured = self.fracture_warning_duration()
        if self.sector_index >= 5:
            # Horizon boards add distant anchor islands for longer tactical journeys.
            for pos in ((self.width - 2, 1), (2, self.height - 2), (self.width // 2, self.height // 2)):
                if self.in_bounds(pos) and pos not in layout.values():
                    self.tiles[pos].state = "anchor"
            for pos in ((self.width - 6, 2), (2, self.height - 6), (self.width - 3, self.height - 6)):
                if self.in_bounds(pos) and pos not in layout.values():
                    self.tiles[pos].state = "fracture"
                    self.tiles[pos].turns_fractured = self.fracture_warning_duration()

    def _generate_units(self, layout: Dict[str, Coord]) -> None:
        # Gentle progression ramp. Sector 1 remains approachable; later sectors
        # add only small enemy stat bumps so the journey feels more dangerous without a spike.
        sector_bonus = self.sector_index - 1
        anomaly_attack_bonus = 1 if self.sector_index >= 3 else 0
        sentry_attack_bonus = 1 if self.sector_index >= 2 else 0
        self.units = {
            "gleebs": Unit("gleebs", "Gleebs", "player", "Glitch Guide", layout["gleebs"], 10, 10, 3, 1, 2),
            "guard": Unit("guard", "Fracture Guard", "player", "Anchor Tank", layout["guard"], 12, 12, 2, 1, 3),
            "runner": Unit("runner", "Phase Runner", "player", "Flanker", layout["runner"], 8, 8, 4, 1, 2),
            "anomaly": Unit(
                "anomaly", "Corrupted Anomaly", "enemy", "Debug Hunter", layout["anomaly"],
                7 + sector_bonus, 7 + sector_bonus, 2, 1, 2 + anomaly_attack_bonus
            ),
            "sentry": Unit(
                "sentry", "Rule Sentry", "enemy", "Ranged Firewall", layout["sentry"],
                5 + sector_bonus, 5 + sector_bonus, 1, 2, 1 + sentry_attack_bonus
            ),
        }
        if self.sector_index >= 4:
            echo_pos = (self.width - 5, max(2, self.height - 6))
            if echo_pos not in {u.pos for u in self.units.values()}:
                self.units["anomaly_echo"] = Unit(
                    "anomaly_echo", "Echo Anomaly", "enemy", "Debug Hunter", echo_pos,
                    6 + sector_bonus, 6 + sector_bonus, 2, 1, 2
                )
        if self.sector_index >= 5:
            sentry_pos = (self.width - 6, self.height - 2)
            if sentry_pos not in {u.pos for u in self.units.values()}:
                self.units["sentry_echo"] = Unit(
                    "sentry_echo", "Horizon Sentry", "enemy", "Ranged Firewall", sentry_pos,
                    5 + sector_bonus, 5 + sector_bonus, 1, 2, 2
                )

    def _generate_nodes(self, layout: Dict[str, Coord]) -> None:
        if self.sector_index == 2:
            self.nodes = {
                "patch": RuleNode("patch", "Signal Relay Beta", layout["patch"], "Synchronize with Relay Alpha to collapse the route lock"),
                "die": RuleNode("die", "Action Die", layout["die"], "Claimed die gives the next attack an overclock bonus"),
                "memory": RuleNode("memory", "Signal Relay Alpha", layout["memory"], "Synchronize with Relay Beta to collapse the route lock"),
                "core": RuleNode("core", "Route Lock", layout["core"], "Collapses automatically when both Signal Relays are synchronized"),
                "extract": RuleNode("extract", "Extraction Gate", layout["extract"], "Opens after both Signal Relays synchronize"),
            }
            return
        if self.sector_index == 3:
            self.nodes = {
                "patch": RuleNode("patch", "Fracture Anchor West", layout["patch"], "Stabilize from an adjacent tile with Gleebs Patch Pulse"),
                "die": RuleNode("die", "Fracture Anchor Center", layout["die"], "Stabilize from an adjacent tile with Gleebs Patch Pulse"),
                "memory": RuleNode("memory", "Fracture Anchor East", layout["memory"], "Stabilize from an adjacent tile with Gleebs Patch Pulse"),
                "core": RuleNode("core", "Stability Gate", layout["core"], "Collapses automatically after all three Fracture Anchors stabilize"),
                "extract": RuleNode("extract", "Extraction Gate", layout["extract"], "Opens after all three Fracture Anchors stabilize"),
            }
            return
        if self.sector_index == 4:
            self.nodes = {
                "patch": RuleNode("patch", "Outer Uplink West", layout["patch"], "Hold with any living squad unit while the East Uplink is also occupied"),
                "die": RuleNode("die", "Action Die", layout["die"], "Claimed die gives the next attack an overclock bonus"),
                "memory": RuleNode("memory", "Outer Uplink East", layout["memory"], "Hold with any living squad unit while the West Uplink is also occupied"),
                "core": RuleNode("core", "Grid Bridge Lock", layout["core"], "Collapses after both Outer Uplinks survive two hostile response cycles together"),
                "extract": RuleNode("extract", "Extraction Gate", layout["extract"], "Opens after the Grid Bridge stabilizes"),
            }
            return
        if self.sector_index == 5:
            self.nodes = {
                "patch": RuleNode("patch", "Horizon Relay West", layout["patch"], "Stage 1: align this relay with any squad unit; Stage 3: hold it through hostile response"),
                "die": RuleNode("die", "Horizon Fracture", layout["die"], "Stage 2: stabilize from an adjacent tile with Gleebs Patch Pulse"),
                "memory": RuleNode("memory", "Horizon Relay East", layout["memory"], "Stage 1: align this relay with any squad unit; Stage 3: hold it through hostile response"),
                "core": RuleNode("core", "Matrix Horizon Core", layout["core"], "Collapses automatically after the three-stage Horizon sequence"),
                "extract": RuleNode("extract", "Final Extraction Gate", layout["extract"], "Opens after the Horizon sequence is complete"),
            }
            return
        self.nodes = {
            "patch": RuleNode("patch", "Patch Rule Node", layout["patch"], "Captured node weakens future corruption pulses"),
            "die": RuleNode("die", "Action Die", layout["die"], "Claimed die gives the next attack an overclock bonus"),
            "memory": RuleNode("memory", "Memory Node", layout["memory"], "Unlocks the Game Master Core"),
            "core": RuleNode("core", "Game Master Core", layout["core"], "Break this rule object to open extraction"),
            "extract": RuleNode("extract", "Extraction Gate", layout["extract"], "Opens after the Core breaks; reach it to continue the journey"),
        }

    def log_event(self, message: str) -> None:
        self.log.append(message)
        del self.log[:-8]

    def ability_drop_chance(self) -> float:
        # Slightly more chance later in the route, but still random and not guaranteed.
        return min(0.75, ABILITY_DROP_BASE_CHANCE + (self.sector_index - 1) * 0.08)

    def inventory_ability(self) -> Optional[OneShotAbility]:
        return self.ability_inventory[0] if self.ability_inventory else None

    def ability_summary(self) -> str:
        if not self.ability_inventory:
            return "EMPTY"
        return ", ".join(ability.short_label() for ability in self.ability_inventory[:ABILITY_INVENTORY_MAX])

    def _ability_rng(self, enemy_id: str, pos: Coord) -> random.Random:
        salt = sum(ord(ch) for ch in enemy_id) + pos[0] * 37 + pos[1] * 53
        return random.Random(self.rng_seed + self.round_index * 101 + self.ability_counter * 17 + salt)

    def generate_procedural_ability(self, enemy_id: str, pos: Coord) -> OneShotAbility:
        rng = self._ability_rng(enemy_id, pos)
        kind = rng.choice(ABILITY_KINDS)
        potency = 1 + rng.randint(1, 2) + (1 if self.sector_index >= 3 and kind in {"arc", "snare"} else 0)
        radius = 1 if kind in {"patch", "snare"} else 0
        ability_range = 3 if kind in {"arc", "patch", "snare"} else 4
        if kind == "blink":
            ability_range = 4 + (1 if self.sector_index >= 3 else 0)
            potency = 0
            radius = 0
        prefix = rng.choice(ABILITY_PREFIXES)
        core = rng.choice(ABILITY_CORES)
        themed_core = {
            "arc": "Surge",
            "patch": "Bloom",
            "blink": "Blink",
            "snare": "Snare",
        }.get(kind, core)
        self.ability_counter += 1
        return OneShotAbility(
            ability_id=f"a{self.sector_index}_{self.round_index}_{self.ability_counter}",
            name=f"{prefix} {themed_core}",
            kind=kind,
            potency=potency,
            radius=radius,
            range=ability_range,
            source_enemy=enemy_id,
            pos=pos,
        )

    def force_spawn_ability_drop(self, enemy_id: str, pos: Coord, kind: Optional[str] = None) -> OneShotAbility:
        ability = self.generate_procedural_ability(enemy_id, pos)
        if kind in ABILITY_KINDS:
            ability.kind = kind
            themed_core = {"arc": "Surge", "patch": "Bloom", "blink": "Blink", "snare": "Snare"}[kind]
            ability.name = f"{ability.name.split()[0]} {themed_core}"
            ability.radius = 1 if kind in {"patch", "snare"} else 0
            ability.range = 4 if kind == "blink" else 3
            ability.potency = 0 if kind == "blink" else max(2, ability.potency)
        ability.pos = pos
        self.ability_pickups[ability.ability_id] = ability
        self.log_event(f"One-shot ability dropped: {ability.short_label()}.")
        return ability

    def _maybe_spawn_ability_drop(self, enemy: Unit) -> Optional[OneShotAbility]:
        if len(self.ability_pickups) >= 4:
            return None
        rng = self._ability_rng(enemy.unit_id, enemy.pos)
        if rng.random() > self.ability_drop_chance():
            self.log_event(f"{enemy.name} left no stable ability fragment.")
            return None
        return self.force_spawn_ability_drop(enemy.unit_id, enemy.pos)

    def _collect_ability_at_pos(self, unit: Unit, pos: Coord) -> bool:
        pickup_id = None
        for ability_id, ability in self.ability_pickups.items():
            if ability.pos == pos:
                pickup_id = ability_id
                break
        if pickup_id is None:
            return False
        if len(self.ability_inventory) >= ABILITY_INVENTORY_MAX:
            self.log_event("Ability cache full. Spend a one-shot ability before collecting more.")
            return False
        ability = self.ability_pickups.pop(pickup_id)
        ability.collected = True
        ability.pos = None
        self.ability_inventory.append(ability)
        self.log_event(f"{unit.name} recovered one-shot ability: {ability.short_label()}.")
        return True

    def _positions_in_radius(self, center: Coord, radius: int) -> List[Coord]:
        positions: List[Coord] = []
        for pos in self.tiles:
            if self.distance(center, pos) <= radius:
                positions.append(pos)
        return positions

    def use_current_ability(self) -> bool:
        unit = self.selected_unit()
        ability = self.inventory_ability()
        self.last_ability_used = None
        if not ability:
            self.log_event("No one-shot ability loaded.")
            return False
        if not unit:
            self.log_event("Select a squad unit before using an ability.")
            return False
        if self.turn != "player":
            self.log_event("Ability link is locked during hostile response.")
            return False
        if unit.acted:
            self.log_event(f"{unit.name} already used an action this turn.")
            return False
        if self.distance(unit.pos, self.cursor) > ability.range:
            self.log_event(f"{ability.name} target is out of range.")
            return False

        used = False
        if ability.kind == "arc":
            target = self.unit_at(self.cursor, team="enemy")
            if not target:
                self.log_event("Arc ability needs a hostile target.")
                return False
            target.hp = max(0, target.hp - ability.potency)
            self.log_event(f"{unit.name} fired {ability.name}: {target.name} took {ability.potency}.")
            if not target.alive:
                self.log_event(f"{target.name} destabilized.")
                self._maybe_spawn_ability_drop(target)
            used = True
        elif ability.kind == "patch":
            stabilized = 0
            healed = 0
            for pos in self._positions_in_radius(self.cursor, ability.radius):
                tile = self.tiles[pos]
                if tile.state in {"corrupted", "fracture"}:
                    tile.state = "stable"
                    tile.turns_corrupted = 0
                    tile.turns_fractured = 0
                    stabilized += 1
                ally = self.unit_at(pos, team="player")
                if ally and ally.hp < ally.max_hp:
                    before = ally.hp
                    ally.hp = min(ally.max_hp, ally.hp + max(1, ability.potency))
                    healed += ally.hp - before
            self.log_event(f"{unit.name} released {ability.name}: {stabilized} tiles patched, {healed} HP restored.")
            used = True
        elif ability.kind == "blink":
            if self.unit_at(self.cursor) or self.tiles[self.cursor].state == "void":
                self.log_event("Blink target must be an empty stable board tile.")
                return False
            unit.pos = self.cursor
            unit.moved = True
            self._resolve_tile_entry(unit, self.tiles[self.cursor])
            self.log_event(f"{unit.name} spent {ability.name} and blinked to {self.cursor}.")
            used = True
        elif ability.kind == "snare":
            target = self.unit_at(self.cursor, team="enemy")
            if not target:
                self.log_event("Snare ability needs a hostile target.")
                return False
            damage = max(1, ability.potency - 1)
            target.hp = max(0, target.hp - damage)
            target.move = max(0, target.move - 1)
            self.tiles[target.pos].state = "fracture"
            self.tiles[target.pos].turns_fractured = max(self.tiles[target.pos].turns_fractured, 2)
            self.log_event(f"{unit.name} cast {ability.name}: {target.name} snared and took {damage}.")
            if not target.alive:
                self.log_event(f"{target.name} destabilized.")
                self._maybe_spawn_ability_drop(target)
            used = True
        if not used:
            return False
        unit.acted = True
        spent = self.ability_inventory.pop(0)
        self.last_ability_used = spent.short_label()
        self.log_event(f"{spent.name} consumed.")
        return True

    def in_bounds(self, pos: Coord) -> bool:
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def unit_at(self, pos: Coord, team: Optional[str] = None) -> Optional[Unit]:
        for unit in self.units.values():
            if unit.alive and unit.pos == pos and (team is None or unit.team == team):
                return unit
        return None

    def selected_unit(self) -> Optional[Unit]:
        if self.selected_unit_id is None:
            return None
        unit = self.units.get(self.selected_unit_id)
        if unit and unit.alive:
            return unit
        return None

    def distance(self, a: Coord, b: Coord) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def adjacent_positions(self, center: Coord) -> List[Coord]:
        results: List[Coord] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pos = (center[0] + dx, center[1] + dy)
            if self.in_bounds(pos):
                results.append(pos)
        return results

    def is_node_position(self, pos: Coord) -> bool:
        return any(node.pos == pos for node in self.nodes.values())

    def journey_tagline(self) -> str:
        return SECTOR_TAGLINES.get(self.sector_index, "Route expansion active.")

    def threat_label(self) -> str:
        return SECTOR_THREAT_LABELS.get(self.sector_index, "UNKNOWN")

    def challenge_note(self) -> str:
        return SECTOR_CHALLENGE_NOTES.get(self.sector_index, "Route pressure active.")

    def corruption_pulse_duration(self) -> int:
        # Slightly extends hazard persistence by sector while keeping Patch Node meaningful.
        base = 2 + self.sector_index
        return max(1, base - 2) if self.patch_node_captured() else base

    def fracture_warning_duration(self) -> int:
        base = 2 + (1 if self.sector_index >= 3 else 0)
        return max(1, base - 1) if self.patch_node_captured() else base

    def can_expand_journey(self) -> bool:
        return self.victory() and self.sector_index < MAX_JOURNEY_SECTORS

    def journey_complete(self) -> bool:
        return self.victory() and self.sector_index >= MAX_JOURNEY_SECTORS

    def journey_route_text(self) -> str:
        route: List[str] = []
        for index in range(1, MAX_JOURNEY_SECTORS + 1):
            name = SECTOR_NAMES[index]
            if index < self.sector_index or name in self.cleared_sectors:
                route.append(f"{index}:sealed")
            elif index == self.sector_index:
                route.append(f"{index}:active")
            else:
                route.append(f"{index}:locked")
        return "  ".join(route)

    def expand_after_victory(self) -> bool:
        if not self.can_expand_journey():
            self.log_event("No new sector is available from this state.")
            return False
        completed = [*self.cleared_sectors, self.sector_name]
        next_state = GameState(sector_index=self.sector_index + 1, cleared_sectors=completed)
        self.__dict__.update(next_state.__dict__)
        self.log_event(f"Journey expanded into {self.sector_name}. Board size {self.width}x{self.height}.")
        return True

    def move_cursor(self, dx: int, dy: int) -> Coord:
        x, y = self.cursor
        nx = max(0, min(self.width - 1, x + dx))
        ny = max(0, min(self.height - 1, y + dy))
        self.cursor = (nx, ny)
        return self.cursor

    def set_cursor(self, pos: Coord) -> bool:
        if not self.in_bounds(pos):
            return False
        self.cursor = pos
        return True

    def select_at_cursor(self) -> bool:
        unit = self.unit_at(self.cursor, team="player")
        if not unit:
            self.selected_unit_id = None
            self.log_event("No squad unit on target tile.")
            return False
        if self.turn != "player":
            self.log_event("Cannot select during hostile/system phase.")
            return False
        self.selected_unit_id = unit.unit_id
        self.log_event(f"Selected {unit.name}.")
        return True

    def legal_moves(self, unit_id: str) -> List[Coord]:
        unit = self.units[unit_id]
        if not unit.alive or unit.moved:
            return []
        options: List[Coord] = []
        for pos, tile in self.tiles.items():
            if self.distance(unit.pos, pos) <= unit.move and not self.unit_at(pos):
                if tile.state != "void":
                    options.append(pos)
        return options

    def legal_attack_tiles(self, unit_id: str, include_empty: bool = True) -> List[Coord]:
        unit = self.units[unit_id]
        if not unit.alive or unit.acted:
            return []
        options: List[Coord] = []
        for pos in self.tiles:
            if pos == unit.pos:
                continue
            if self.distance(unit.pos, pos) <= unit.attack_range:
                if include_empty or self.unit_at(pos, team="enemy"):
                    options.append(pos)
        core = self.nodes["core"]
        if self.memory_collected and self.distance(unit.pos, core.pos) <= unit.attack_range:
            if core.pos not in options:
                options.append(core.pos)
        return options

    def patch_node_captured(self) -> bool:
        node = self.nodes.get("patch")
        return bool(node and node.captured_by == "player")

    def signal_relays_synchronized(self) -> bool:
        return self.sector_index == 2 and self.memory_collected and self.patch_node_captured()

    def _resolve_sector2_relay_sync(self) -> None:
        if not self.signal_relays_synchronized() or self.core_destroyed:
            return
        self.core_destroyed = True
        self.nodes["core"].captured_by = "player"
        self.tiles[self.nodes["extract"].pos].state = "extraction"
        self.log_event("Signal Relays synchronized. Route Lock collapsed; Extraction Gate opened.")

    def sector3_fracture_anchor_ids(self) -> Tuple[str, ...]:
        return ("patch", "die", "memory") if self.sector_index == 3 else tuple()

    def fracture_anchor_count(self) -> int:
        if self.sector_index != 3:
            return 0
        return sum(1 for node_id in self.sector3_fracture_anchor_ids() if self.nodes[node_id].captured_by == "player")

    def fracture_anchors_stabilized(self) -> bool:
        return self.sector_index == 3 and self.fracture_anchor_count() == 3

    def _resolve_sector3_fracture_completion(self) -> None:
        if not self.fracture_anchors_stabilized() or self.core_destroyed:
            return
        # Preserve the shared journey/victory contract without making Sector 3
        # replay the Memory -> attack Core sequence. The gate falls automatically.
        self.memory_collected = True
        self.core_destroyed = True
        self.nodes["core"].captured_by = "player"
        self.tiles[self.nodes["extract"].pos].state = "extraction"
        self.log_event("All Fracture Anchors stabilized. Stability Gate collapsed; Extraction Gate opened.")

    def sector4_grid_uplink_ids(self) -> Tuple[str, ...]:
        return ("patch", "memory") if self.sector_index == 4 else tuple()

    def sector4_uplink_occupied(self, node_id: str) -> bool:
        if self.sector_index != 4 or node_id not in self.sector4_grid_uplink_ids():
            return False
        unit = self.unit_at(self.nodes[node_id].pos, team="player")
        return bool(unit and unit.alive)

    def sector4_both_uplinks_occupied(self) -> bool:
        return self.sector_index == 4 and all(self.sector4_uplink_occupied(node_id) for node_id in self.sector4_grid_uplink_ids())

    def _resolve_sector4_grid_hold(self) -> None:
        if self.sector_index != 4 or self.core_destroyed:
            return
        if self.sector4_both_uplinks_occupied():
            self.grid_link_charge = min(2, self.grid_link_charge + 1)
            self.log_event(f"Outer Uplinks held through hostile response: Grid Bridge {self.grid_link_charge}/2.")
        elif self.grid_link_charge:
            self.grid_link_charge = 0
            self.log_event("Outer Uplink formation broke. Grid Bridge charge reset.")
        if self.grid_link_charge >= 2:
            self.memory_collected = True
            self.core_destroyed = True
            for node_id in self.sector4_grid_uplink_ids():
                self.nodes[node_id].captured_by = "player"
            self.nodes["core"].captured_by = "player"
            self.tiles[self.nodes["extract"].pos].state = "extraction"
            self.log_event("Grid Bridge stabilized. Bridge Lock collapsed; Extraction Gate opened.")


    def sector5_horizon_relay_ids(self) -> Tuple[str, ...]:
        return ("patch", "memory") if self.sector_index == 5 else tuple()

    def sector5_relays_aligned(self) -> bool:
        return self.sector_index == 5 and all(self.nodes[node_id].captured_by == "player" for node_id in self.sector5_horizon_relay_ids())

    def sector5_fracture_stabilized(self) -> bool:
        return self.sector_index == 5 and self.nodes["die"].captured_by == "player"

    def sector5_horizon_stage(self) -> int:
        if self.sector_index != 5:
            return 0
        if self.core_destroyed:
            return 4
        if not self.sector5_relays_aligned():
            return 1
        if not self.sector5_fracture_stabilized():
            return 2
        return 3

    def sector5_relay_occupied(self, node_id: str) -> bool:
        if self.sector_index != 5 or node_id not in self.sector5_horizon_relay_ids():
            return False
        unit = self.unit_at(self.nodes[node_id].pos, team="player")
        return bool(unit and unit.alive)

    def sector5_both_relays_occupied(self) -> bool:
        return self.sector_index == 5 and all(self.sector5_relay_occupied(node_id) for node_id in self.sector5_horizon_relay_ids())

    def _resolve_sector5_relay_alignment(self) -> None:
        if self.sector_index != 5 or not self.sector5_relays_aligned() or self.memory_collected:
            return
        self.memory_collected = True
        fracture = self.tiles[self.nodes["die"].pos]
        fracture.state = "fracture"
        fracture.turns_fractured = 9999
        self.log_event("Horizon Relays aligned. Central Horizon Fracture exposed; Gleebs must stabilize it.")

    def _resolve_sector5_final_hold(self) -> None:
        if self.sector_index != 5 or self.core_destroyed or not self.sector5_fracture_stabilized():
            return
        if self.sector5_both_relays_occupied():
            self.grid_link_charge = 1
            self.core_destroyed = True
            self.nodes["core"].captured_by = "player"
            self.tiles[self.nodes["extract"].pos].state = "extraction"
            self.log_event("Both Horizon Relays survived hostile response. Matrix Horizon Core collapsed; final Extraction opened.")
        elif self.grid_link_charge:
            self.grid_link_charge = 0

    def extraction_open(self) -> bool:
        return self.core_destroyed and not self.extraction_reached

    def move_selected_to_cursor(self) -> bool:
        unit = self.selected_unit()
        if not unit:
            self.log_event("No unit selected.")
            return False
        if unit.moved:
            self.log_event(f"{unit.name} already moved this turn.")
            return False
        if self.cursor not in self.legal_moves(unit.unit_id):
            self.log_event("Move blocked: target tile is outside legal movement range.")
            return False
        unit.pos = self.cursor
        unit.moved = True
        tile = self.tiles[self.cursor]
        tile.owner = unit.team
        self.log_event(f"{unit.name} moved to {self.cursor}.")
        self._resolve_tile_entry(unit, tile)
        return True

    def _resolve_tile_entry(self, unit: Unit, tile: Tile) -> None:
        pos = tile.pos
        if self.sector_index == 5 and pos in {self.nodes[node_id].pos for node_id in self.sector5_horizon_relay_ids()}:
            for node_id in self.sector5_horizon_relay_ids():
                node = self.nodes[node_id]
                if pos == node.pos and node.captured_by != "player":
                    node.captured_by = "player"
                    self.log_event(f"{unit.name} aligned {node.name}.")
                    self._resolve_sector5_relay_alignment()
                    break
        if self.sector_index != 4 and tile.state == "anchor" and pos == self.nodes["patch"].pos and not self.patch_node_captured():
            self.nodes["patch"].captured_by = "player"
            if self.sector_index == 2:
                self.log_event(f"{unit.name} synchronized Signal Relay Beta.")
                self._resolve_sector2_relay_sync()
            else:
                self.log_event("Gleebs notes: Patch Rule Node captured. System pulses softened.")
        if self.sector_index != 5 and tile.state == "signal" and pos == self.nodes["die"].pos and not self.action_die_claimed:
            self.action_die_claimed = True
            self.overclock_charges += 1
            self.nodes["die"].captured_by = "player"
            self.log_event(f"{unit.name} claimed the Action Die. Next attack gains Overclock +2.")
        if self.sector_index != 4 and tile.state == "memory" and not self.memory_collected:
            if self.sector_index == 2 and unit.team == "player":
                self.memory_collected = True
                self.nodes["memory"].captured_by = "player"
                self.log_event(f"{unit.name} synchronized Signal Relay Alpha.")
                self._resolve_sector2_relay_sync()
            elif unit.unit_id == "gleebs":
                self.memory_collected = True
                self.nodes["memory"].captured_by = "player"
                self.log_event("Gleebs captured the Memory Node. Core is now vulnerable.")
        if tile.state == "extraction" and self.core_destroyed and not self.extraction_reached and unit.team == "player":
            self.extraction_reached = True
            self.nodes["extract"].captured_by = "player"
            if self.sector_index < MAX_JOURNEY_SECTORS:
                self.log_event(f"{unit.name} reached the Extraction Gate. Sector sealed; route can expand.")
            else:
                self.log_event(f"{unit.name} reached the final Extraction Gate. Journey sealed.")
        self._collect_ability_at_pos(unit, pos)
        if tile.state == "corrupted":
            unit.hp = max(1, unit.hp - 1)
            self.log_event(f"{unit.name} took 1 corruption damage.")
        if tile.state == "fracture":
            unit.hp = max(1, unit.hp - 1)
            self.log_event(f"{unit.name} crossed a fracture warning tile and lost 1 HP.")

    def use_gleebs_patch_pulse(self) -> bool:
        unit = self.selected_unit()
        if not unit or unit.unit_id != "gleebs":
            self.log_event("Patch Pulse requires selecting Gleebs.")
            return False
        if unit.acted:
            self.log_event("Gleebs already used an action this turn.")
            return False
        if self.distance(unit.pos, self.cursor) > 1:
            self.log_event("Patch Pulse target must be adjacent to Gleebs.")
            return False
        ally = self.unit_at(self.cursor, team="player")
        if ally and ally.hp < ally.max_hp:
            before = ally.hp
            ally.hp = min(ally.max_hp, ally.hp + 2)
            unit.acted = True
            self.log_event(f"Gleebs patched {ally.name}: HP {before}->{ally.hp}.")
            return True
        tile = self.tiles[self.cursor]
        if self.sector_index == 3:
            for node_id in self.sector3_fracture_anchor_ids():
                node = self.nodes[node_id]
                if self.cursor == node.pos and node.captured_by != "player":
                    tile.state = "stable"
                    tile.turns_corrupted = 0
                    tile.turns_fractured = 0
                    node.captured_by = "player"
                    unit.acted = True
                    self.log_event(f"Gleebs stabilized {node.name} ({self.fracture_anchor_count()}/3).")
                    self._resolve_sector3_fracture_completion()
                    return True
        if self.sector_index == 5 and self.sector5_relays_aligned() and not self.sector5_fracture_stabilized():
            node = self.nodes["die"]
            if self.cursor == node.pos:
                tile.state = "stable"
                tile.turns_corrupted = 0
                tile.turns_fractured = 0
                node.captured_by = "player"
                unit.acted = True
                self.log_event("Gleebs stabilized the Horizon Fracture. Final stage: occupy both Horizon Relays through hostile response.")
                return True
        if tile.state in {"corrupted", "fracture"}:
            tile.state = "stable"
            tile.turns_corrupted = 0
            tile.turns_fractured = 0
            unit.acted = True
            self.log_event(f"Gleebs Patch Pulse stabilized tile {self.cursor}.")
            return True
        self.log_event("Patch Pulse found nothing unstable or wounded at target.")
        return False

    def attack_cursor(self) -> bool:
        attacker = self.selected_unit()
        if not attacker:
            self.log_event("No unit selected.")
            return False
        if attacker.acted:
            self.log_event(f"{attacker.name} already acted this turn.")
            return False
        if self.distance(attacker.pos, self.cursor) > attacker.attack_range:
            self.log_event("Target is out of range.")
            return False
        bonus = 2 if self.overclock_charges > 0 else 0
        core = self.nodes["core"]
        if self.cursor == core.pos:
            if self.sector_index == 2:
                self.log_event("Route Lock is controlled by the two Signal Relays; it cannot be attacked directly.")
                return False
            if self.sector_index == 3:
                self.log_event("Stability Gate is bound to the Fracture Anchors; it cannot be attacked directly.")
                return False
            if self.sector_index == 4:
                self.log_event("Grid Bridge Lock is controlled by simultaneous Outer Uplink occupation; it cannot be attacked directly.")
                return False
            if self.sector_index == 5:
                self.log_event("Matrix Horizon Core is bound to the three-stage Horizon sequence; it cannot be attacked directly.")
                return False
            if not self.memory_collected:
                self.log_event("Core is locked until Gleebs captures the Memory Node.")
                return False
            self.core_destroyed = True
            self.tiles[self.nodes["extract"].pos].state = "extraction"
            attacker.acted = True
            if bonus:
                self.overclock_charges -= 1
            self.log_event(f"{attacker.name} broke the Game Master Core{' with Overclock' if bonus else ''}. Extraction Gate opened.")
            return True
        target = self.unit_at(self.cursor, team="enemy")
        if not target:
            self.log_event("No hostile target on tile.")
            return False
        damage = attacker.attack_power + bonus
        target.hp = max(0, target.hp - damage)
        attacker.acted = True
        if bonus:
            self.overclock_charges -= 1
        self.log_event(f"{attacker.name} hit {target.name} for {damage}{' using Overclock' if bonus else ''}.")
        if not target.alive:
            self.log_event(f"{target.name} destabilized.")
            self._maybe_spawn_ability_drop(target)
        return True

    def end_player_turn(self) -> None:
        if self.turn != "player" or self.victory() or self.defeat():
            return
        self.turn = "enemy"
        self.phase = "enemy_action"
        self.selected_unit_id = None
        self.log_event("Hostile response started.")
        self.enemy_phase()
        self.system_phase()
        self.start_player_turn()

    def _active_objective_pos(self) -> Coord:
        if self.sector_index == 2:
            if not self.memory_collected:
                return self.nodes["memory"].pos
            if not self.patch_node_captured():
                return self.nodes["patch"].pos
            return self.nodes["extract"].pos
        if self.sector_index == 3:
            for node_id in self.sector3_fracture_anchor_ids():
                if self.nodes[node_id].captured_by != "player":
                    return self.nodes[node_id].pos
            return self.nodes["extract"].pos
        if self.sector_index == 4:
            if not self.core_destroyed:
                # Guide hostile pressure toward whichever wide-lane uplink is not
                # currently occupied; the player still needs both simultaneously.
                for node_id in self.sector4_grid_uplink_ids():
                    if not self.sector4_uplink_occupied(node_id):
                        return self.nodes[node_id].pos
                return self.nodes["core"].pos
            return self.nodes["extract"].pos
        if self.sector_index == 5:
            if not self.sector5_relays_aligned():
                for node_id in self.sector5_horizon_relay_ids():
                    if self.nodes[node_id].captured_by != "player":
                        return self.nodes[node_id].pos
            elif not self.sector5_fracture_stabilized():
                return self.nodes["die"].pos
            elif not self.core_destroyed:
                for node_id in self.sector5_horizon_relay_ids():
                    if not self.sector5_relay_occupied(node_id):
                        return self.nodes[node_id].pos
                return self.nodes["core"].pos
            return self.nodes["extract"].pos
        if not self.memory_collected:
            return self.nodes["memory"].pos
        if not self.core_destroyed:
            return self.nodes["core"].pos
        return self.nodes["extract"].pos

    def _enemy_target_key(self, enemy: Unit, player: Unit) -> Tuple[float, int, int, str]:
        """Deterministic tactical target priority; lower tuples are preferred."""
        objective = self._active_objective_pos()
        hp_ratio = player.hp / max(1, player.max_hp)

        # Sector 2 uses two squad-capturable Signal Relays instead of the
        # Gleebs-only Memory gate, so hostile pressure follows proximity there.
        if self.sector_index in {2, 4} and not self.core_destroyed:
            objective_rank = self.distance(player.pos, objective)
        elif self.sector_index == 5 and not self.core_destroyed:
            if self.sector5_horizon_stage() == 2:
                objective_rank = 0 if player.unit_id == "gleebs" else 2
            else:
                objective_rank = self.distance(player.pos, objective)
        elif not self.memory_collected:
            objective_rank = 0 if player.unit_id == "gleebs" else 2
        else:
            # Later objectives can be attacked/reached by the whole squad.
            # Treat whoever is closest to the active objective as the largest
            # immediate mission threat.
            objective_rank = self.distance(player.pos, objective)

        # Vulnerability matters after mission pressure; enemy distance is the
        # final spatial tie-break so behavior stays comprehensible.
        return (float(objective_rank), int(hp_ratio * 1000), self.distance(enemy.pos, player.pos), player.unit_id)

    def _enemy_spacing_penalty(self, enemy: Unit, pos: Coord) -> int:
        penalty = 0
        for other in self.units.values():
            if other.team != "enemy" or not other.alive or other.unit_id == enemy.unit_id:
                continue
            d = self.distance(pos, other.pos)
            if d == 1:
                penalty += 3
            elif d == 2:
                penalty += 1
        return penalty

    def _enemy_open_neighbors(self, enemy: Unit) -> List[Coord]:
        result: List[Coord] = []
        for cand in self.adjacent_positions(enemy.pos):
            if self.unit_at(cand):
                continue
            if self.tiles[cand].state == "void":
                continue
            result.append(cand)
        return result

    def _enemy_attack(self, enemy: Unit, target: Unit) -> None:
        target.hp = max(0, target.hp - enemy.attack_power)
        self.log_event(f"{enemy.name} struck {target.name} for {enemy.attack_power}.")
        if not target.alive:
            self.log_event(f"{target.name} was forced offline.")

    def _enemy_step_hunter(self, enemy: Unit, target: Unit) -> None:
        current_dist = self.distance(enemy.pos, target.pos)
        candidates = self._enemy_open_neighbors(enemy)
        if not candidates:
            return

        improving = [p for p in candidates if self.distance(p, target.pos) < current_dist]
        if not improving:
            return

        # Pursue the target, then prefer the lane with more breathing room.
        best = min(
            improving,
            key=lambda p: (self.distance(p, target.pos), self._enemy_spacing_penalty(enemy, p), p[1], p[0]),
        )
        enemy.pos = best
        self.log_event(f"{enemy.name} hunted {target.name} to {enemy.pos}.")

    def _enemy_step_sentry(self, enemy: Unit, target: Unit) -> bool:
        """Reposition a ranged sentry toward its preferred firing distance."""
        desired = max(1, enemy.attack_range)
        current_dist = self.distance(enemy.pos, target.pos)
        candidates = self._enemy_open_neighbors(enemy)
        if not candidates:
            return False

        if current_dist < desired:
            # Back off if a clean tile restores useful range.
            safer = [p for p in candidates if self.distance(p, target.pos) > current_dist]
            if not safer:
                return False
            best = min(
                safer,
                key=lambda p: (abs(self.distance(p, target.pos) - desired), self._enemy_spacing_penalty(enemy, p), p[1], p[0]),
            )
            enemy.pos = best
            self.log_event(f"{enemy.name} reopened firing distance from {target.name} at {enemy.pos}.")
            return True

        if current_dist > desired:
            closing = [p for p in candidates if self.distance(p, target.pos) < current_dist]
            if not closing:
                return False
            best = min(
                closing,
                key=lambda p: (abs(self.distance(p, target.pos) - desired), self._enemy_spacing_penalty(enemy, p), p[1], p[0]),
            )
            enemy.pos = best
            self.log_event(f"{enemy.name} established a firing lane at {enemy.pos}.")
            return True

        return False

    def enemy_phase(self) -> None:
        enemies = [u for u in self.units.values() if u.team == "enemy" and u.alive]
        if not enemies:
            return

        for enemy in enemies:
            # Rebuild this list for every enemy because an earlier hostile may
            # have defeated one of the squad during the same phase.
            players = [u for u in self.units.values() if u.team == "player" and u.alive]
            if not players:
                break
            target = min(players, key=lambda u: self._enemy_target_key(enemy, u))
            dist = self.distance(enemy.pos, target.pos)

            if enemy.role == "Ranged Firewall":
                # Sentries preserve their firing envelope when possible. If
                # already at useful range they shoot; if crowded, they step
                # back instead of behaving like melee attackers.
                if dist < enemy.attack_range and self._enemy_step_sentry(enemy, target):
                    continue
                if self.distance(enemy.pos, target.pos) <= enemy.attack_range:
                    self._enemy_attack(enemy, target)
                else:
                    self._enemy_step_sentry(enemy, target)
                continue

            if dist <= enemy.attack_range:
                self._enemy_attack(enemy, target)
            else:
                self._enemy_step_hunter(enemy, target)

    def _enemy_step_toward(self, enemy: Unit, target_pos: Coord) -> None:
        """Compatibility wrapper retained for older callers/tests."""
        target = self.unit_at(target_pos, team="player")
        if target is not None:
            self._enemy_step_hunter(enemy, target)

    def system_phase(self) -> None:
        self.phase = "system_event"
        pulse_pos = ((self.round_index + 2 + self.sector_index) % self.width, (self.round_index * 2 + 1) % self.height)
        if self.is_node_position(pulse_pos):
            pulse_pos = ((pulse_pos[0] + 1) % self.width, pulse_pos[1])
        tile = self.tiles[pulse_pos]
        if tile.state in {"stable", "fracture"}:
            tile.state = "corrupted"
            tile.turns_corrupted = self.corruption_pulse_duration()
            tile.turns_fractured = 0
            suffix = "weakened by Patch Node" if self.patch_node_captured() else f"threat {self.threat_label().lower()}"
            self.log_event(f"System Event: tile {pulse_pos} became corrupted ({suffix}).")
            self._fracture_neighbors(pulse_pos)
        if self.patch_node_captured():
            for pos in self.adjacent_positions(self.nodes["patch"].pos):
                t = self.tiles[pos]
                if t.state == "corrupted" and t.turns_corrupted > 0:
                    t.turns_corrupted = 1
                    self.log_event(f"Patch Node softened corruption near {pos}.")
        self._tick_tile_timers()

    def _fracture_neighbors(self, pulse_pos: Coord) -> None:
        for pos in self.adjacent_positions(pulse_pos):
            t = self.tiles[pos]
            if t.state == "stable" and not self.is_node_position(pos):
                t.state = "fracture"
                t.turns_fractured = self.fracture_warning_duration()
        self.log_event("System Event: adjacent stable tiles flickered into fracture warnings.")

    def _tick_tile_timers(self) -> None:
        for pos, t in self.tiles.items():
            protected = {self.nodes["core"].pos, self.nodes["extract"].pos}
            if self.sector_index == 3:
                protected.update(self.nodes[node_id].pos for node_id in self.sector3_fracture_anchor_ids())
            if pos in protected:
                continue
            if t.state == "corrupted" and t.turns_corrupted > 0:
                t.turns_corrupted -= 1
                if t.turns_corrupted == 0:
                    t.state = "stable"
                    self.log_event(f"Tile {pos} stabilized.")
            elif t.state == "fracture" and t.turns_fractured > 0:
                t.turns_fractured -= 1
                if t.turns_fractured == 0:
                    t.state = "stable"

    def start_player_turn(self) -> None:
        self.round_index += 1
        self.turn = "player"
        self.phase = "player_action"
        self._resolve_sector4_grid_hold()
        self._resolve_sector5_final_hold()
        for unit in self.units.values():
            if unit.team == "player" and unit.alive:
                unit.moved = False
                unit.acted = False
        self.log_event(f"Round {self.round_index} started.")

    def victory(self) -> bool:
        return self.memory_collected and self.core_destroyed and self.extraction_reached

    def defeat(self) -> bool:
        return not any(u.alive for u in self.units.values() if u.team == "player")

    def objective_text(self) -> str:
        if self.can_expand_journey():
            return "Sector sealed: expand the route"
        if self.journey_complete():
            return "Journey Complete"
        if self.defeat():
            return "Simulation Lost"
        if self.sector_index == 2 and not self.core_destroyed:
            alpha = "SYNC" if self.memory_collected else "OPEN"
            beta = "SYNC" if self.patch_node_captured() else "OPEN"
            return f"Main: synchronize Signal Relays A[{alpha}] + B[{beta}]"
        if self.sector_index == 3 and not self.core_destroyed:
            return f"Main: stabilize Fracture Anchors {self.fracture_anchor_count()}/3 with Gleebs Patch Pulse"
        if self.sector_index == 4 and not self.core_destroyed:
            west = "HELD" if self.sector4_uplink_occupied("patch") else "OPEN"
            east = "HELD" if self.sector4_uplink_occupied("memory") else "OPEN"
            return f"Main: hold Outer Uplinks W[{west}] E[{east}] | Grid Bridge {self.grid_link_charge}/2"
        if self.sector_index == 5 and not self.core_destroyed:
            stage = self.sector5_horizon_stage()
            if stage == 1:
                aligned = sum(1 for node_id in self.sector5_horizon_relay_ids() if self.nodes[node_id].captured_by == "player")
                return f"Final 1/3: align Horizon Relays {aligned}/2"
            if stage == 2:
                return "Final 2/3: Gleebs stabilize Horizon Fracture"
            west = "HELD" if self.sector5_relay_occupied("patch") else "OPEN"
            east = "HELD" if self.sector5_relay_occupied("memory") else "OPEN"
            return f"Final 3/3: hold Horizon Relays W[{west}] E[{east}] through hostile response"
        if not self.memory_collected:
            open_optional = []
            if not self.patch_node_captured():
                open_optional.append("Patch Node")
            if not self.action_die_claimed:
                open_optional.append("Action Die")
            if open_optional:
                return f"Optional: {', '.join(open_optional)} | Main: Gleebs to Memory Node"
            return "Main: move Gleebs to Memory Node"
        if not self.core_destroyed:
            return "Break the Game Master Core"
        return "Reach the Extraction Gate"

    def mission_progress_percent(self) -> int:
        if self.victory():
            return 100
        if self.sector_index == 3:
            points = 10 + self.fracture_anchor_count() * 20
            if self.core_destroyed:
                points += 10
            if self.extraction_reached:
                points += 30
            return min(100, points)
        if self.sector_index == 4:
            held = sum(1 for node_id in self.sector4_grid_uplink_ids() if self.sector4_uplink_occupied(node_id))
            points = 10 + held * 15 + self.grid_link_charge * 20
            if self.core_destroyed:
                points += 20
            if self.extraction_reached:
                points += 20
            return min(100, points)
        if self.sector_index == 5:
            aligned = sum(1 for node_id in self.sector5_horizon_relay_ids() if self.nodes[node_id].captured_by == "player")
            points = 10 + aligned * 15
            if self.sector5_fracture_stabilized():
                points += 25
            if self.core_destroyed:
                points += 25
            if self.extraction_reached:
                points += 10
            return min(100, points)
        points = 10
        if self.patch_node_captured():
            points += 18 if self.sector_index == 2 else 12
        if self.action_die_claimed:
            points += 12
        if self.ability_inventory or self.ability_pickups:
            points += 6
        if self.memory_collected:
            points += 20 if self.sector_index == 2 else 26
        if self.core_destroyed:
            points += 20
        if self.extraction_reached:
            points += 20
        return min(100, points)

    def journey_progress_percent(self) -> int:
        sealed_count = len(self.cleared_sectors) + (1 if self.victory() else 0)
        return int((sealed_count / MAX_JOURNEY_SECTORS) * 100)

    def completion_percent(self) -> int:
        # Prototype milestone completeness, not mission progress.
        return 100

    def snapshot(self) -> dict:
        return {
            "turn": self.turn,
            "round_index": self.round_index,
            "phase": self.phase,
            "cursor": self.cursor,
            "selected_unit_id": self.selected_unit_id,
            "sector_index": self.sector_index,
            "sector_name": self.sector_name,
            "sector_tagline": self.journey_tagline(),
            "threat_label": self.threat_label(),
            "challenge_note": self.challenge_note(),
            "corruption_pulse_duration": self.corruption_pulse_duration(),
            "fracture_warning_duration": self.fracture_warning_duration(),
            "cleared_sectors": list(self.cleared_sectors),
            "can_expand_journey": self.can_expand_journey(),
            "journey_complete": self.journey_complete(),
            "journey_route_text": self.journey_route_text(),
            "journey_progress_percent": self.journey_progress_percent(),
            "memory_collected": self.memory_collected,
            "core_destroyed": self.core_destroyed,
            "extraction_reached": self.extraction_reached,
            "extraction_open": self.extraction_open(),
            "action_die_claimed": self.action_die_claimed,
            "overclock_charges": self.overclock_charges,
            "ability_drop_chance": round(self.ability_drop_chance(), 2),
            "ability_summary": self.ability_summary(),
            "last_ability_used": self.last_ability_used,
            "grid_link_charge": self.grid_link_charge,
            "sector4_uplinks_occupied": {node_id: self.sector4_uplink_occupied(node_id) for node_id in self.sector4_grid_uplink_ids()},
            "sector5_horizon_stage": self.sector5_horizon_stage(),
            "sector5_relays_aligned": self.sector5_relays_aligned(),
            "sector5_fracture_stabilized": self.sector5_fracture_stabilized(),
            "sector5_relays_occupied": {node_id: self.sector5_relay_occupied(node_id) for node_id in self.sector5_horizon_relay_ids()},
            "ability_inventory": [ability.__dict__ for ability in self.ability_inventory],
            "ability_pickups": {aid: ability.__dict__ for aid, ability in self.ability_pickups.items()},
            "patch_node_captured": self.patch_node_captured(),
            "victory": self.victory(),
            "defeat": self.defeat(),
            "objective_text": self.objective_text(),
            "mission_progress_percent": self.mission_progress_percent(),
            "prototype_completion_percent": self.completion_percent(),
            "nodes": {
                nid: {
                    "name": node.name,
                    "pos": node.pos,
                    "effect": node.effect,
                    "captured_by": node.captured_by,
                }
                for nid, node in self.nodes.items()
            },
            "units": {
                uid: {
                    "name": unit.name,
                    "team": unit.team,
                    "role": unit.role,
                    "pos": unit.pos,
                    "hp": unit.hp,
                    "max_hp": unit.max_hp,
                    "move": unit.move,
                    "attack_range": unit.attack_range,
                    "attack_power": unit.attack_power,
                    "moved": unit.moved,
                    "acted": unit.acted,
                    "alive": unit.alive,
                }
                for uid, unit in self.units.items()
            },
            "tiles": {
                f"{pos[0]},{pos[1]}": {
                    "state": tile.state,
                    "owner": tile.owner,
                    "turns_corrupted": tile.turns_corrupted,
                    "turns_fractured": tile.turns_fractured,
                }
                for pos, tile in self.tiles.items()
            },
            "log": list(self.log),
        }


def create_game_for_sector(sector_index: int, cleared_sectors: Optional[List[str]] = None) -> GameState:
    return GameState(sector_index=sector_index, cleared_sectors=list(cleared_sectors or []), rng_seed=1300 + sector_index)


def create_default_game() -> GameState:
    return create_game_for_sector(1)
