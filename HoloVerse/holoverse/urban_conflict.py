"""Urban ring: dystopian ruins and a never-ending robot war (Pass 282.53).

Pure data and simulation (no Panda3D), so it can be validated headless.

Ruins
-----
``ruin_sector(sector, r0, r1, height_fn)`` turns the accepted Pass 282.39
structure records (holoverse/urban_region.py) into shattered buildings:
an intact lower block, a jagged broken crown, exposed girders, rubble at
the base, plus burnt-out cars, concrete barricades, watch towers and
burning barrels in the open ground.  Every solid also yields a collision
record (oriented box) so the player cannot walk through it.

War
---
Two robot factions fight at skirmish sites around the ring:
  * SCRAP  - rust-orange bipedal walkers with amber visors and arm cannons;
  * CHOIR  - gunmetal four-legged spider tanks with cyan sensor strips.
At Sable's post both factions push in and attack Sable.  Sable strafes,
shoots them down and is never damaged: hits only light her shield.
Destroyed robots collapse, then a replacement walks in a few seconds later.

``Battle.update(dt)`` returns render events (shots, deaths, respawns, shield
hits); the visual layer only draws them.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from holoverse.urban_region import generate_urban_structures, point_inside_structure, URBAN_CORRIDOR_DEGREES

TAU = math.tau
SCRAP = "scrap"
CHOIR = "choir"
SABLE = "sable"

RUIN_SINK = 1.5                 # buildings sink into the stepped Urban terrain
SITE_CLEARANCE = 46.0
SITE_ACTIVE_RADIUS = 650.0

FACADE_TONES = (
    (0.34, 0.31, 0.28), (0.38, 0.31, 0.25), (0.29, 0.29, 0.31), (0.41, 0.34, 0.28),
)
CONCRETE = (0.40, 0.37, 0.34)
RUBBLE = (0.36, 0.33, 0.30)
STEEL = (0.20, 0.17, 0.15)
WRECK_TONES = ((0.16, 0.11, 0.09), (0.12, 0.12, 0.13), (0.22, 0.14, 0.10))
WARNING_RED = (1.0, 0.10, 0.06)
FIRE = (1.0, 0.45, 0.10)


def _unit(*values) -> float:
    h = 2166136261
    for v in values:
        h ^= int(v) & 0xFFFFFFFF
        h = (h * 16777619) & 0xFFFFFFFF
    h ^= h >> 15
    h = (h * 0x2C1B3C6D) & 0xFFFFFFFF
    h ^= h >> 12
    return h / 4294967296.0


def _angle_delta(a: float, b: float) -> float:
    return abs((a - b + math.pi) % TAU - math.pi)


def in_corridor(angle: float, half_width: float = 0.060) -> bool:
    return any(_angle_delta(angle, math.radians(d)) <= half_width for d in URBAN_CORRIDOR_DEGREES)


@dataclass
class OBox:
    """Oriented solid: centre x/y, base z, size, heading (radians)."""
    x: float
    y: float
    z0: float
    sx: float
    sy: float
    sz: float
    heading: float
    kind: str = "plain"        # facade | plain | emissive | fire
    rgb: tuple = (0.3, 0.3, 0.3)
    seed: float = 0.0


@dataclass
class OObstacle:
    x: float
    y: float
    sx: float
    sy: float
    heading: float
    top: float

    def contains(self, px: float, py: float, pad: float) -> bool:
        dx, dy = px - self.x, py - self.y
        c, s = math.cos(-self.heading), math.sin(-self.heading)
        lx, ly = dx * c - dy * s, dx * s + dy * c
        return abs(lx) <= self.sx * 0.5 + pad and abs(ly) <= self.sy * 0.5 + pad


@dataclass
class SectorRuins:
    sector: int
    boxes: list = field(default_factory=list)
    obstacles: list = field(default_factory=list)
    fires: list = field(default_factory=list)          # (x, y, z) smoke sources
    towers: list = field(default_factory=list)         # (x, y, light z) searchlight towers
    structures: list = field(default_factory=list)


def _local(x, y, heading, lx, ly):
    c, s = math.cos(heading), math.sin(heading)
    return x + lx * c - ly * s, y + lx * s + ly * c


def _open_spot(structs, x, y, pad):
    return not any(point_inside_structure(x, y, item, padding=pad) for item in structs)


CORRIDOR_LANE_HALF = 42.0       # a clear road down the middle of each travel corridor
PROP_CLEAR_RADIUS = 26.0        # small debris may come this close to a keep-clear centre


def ruin_sector(sector: int, r0: float, r1: float, height_fn, sector_count: int = 48, keep_clear=()) -> SectorRuins:
    """Ruined city content for one Urban sector (deterministic).

    ``keep_clear`` is a list of (x, y, radius) areas (Sable's post, the travel
    landing): no collapsed blocks inside the radius, and no debris within
    PROP_CLEAR_RADIUS of the centre.  Travel corridors keep an open road
    CORRIDOR_LANE_HALF metres either side of the corridor line.
    """
    structs = generate_urban_structures(int(sector), float(r0), float(r1), sector_count=sector_count)
    out = SectorRuins(int(sector), structures=structs)
    for k, item in enumerate(structs):
        seed = int(sector) * 1000 + k
        ground = float(height_fn(item.x, item.y)) - RUIN_SINK
        tone = FACADE_TONES[int(item.tone) % len(FACADE_TONES)]
        low_t = 0.38 + 0.30 * _unit(seed, 1)
        if item.kind == "damaged":
            low_t *= 0.7
        low_h = item.sz * low_t
        out.boxes.append(OBox(item.x, item.y, ground, item.sx, item.sy, low_h, item.heading, "facade", tone, seed))
        top_z = ground + low_h
        # Broken crown: a grid of columns with ragged heights, some missing.
        nx = 2 + int(_unit(seed, 2) * 2)
        ny = 2
        cw, cd = item.sx / nx, item.sy / ny
        tallest = top_z
        for i in range(nx):
            for j in range(ny):
                lx = -item.sx * 0.5 + cw * (i + 0.5)
                ly = -item.sy * 0.5 + cd * (j + 0.5)
                u = _unit(seed, 10 + i * 7 + j)
                if u < 0.22:
                    # Collapsed bay: bare girders sticking out of the slab.
                    for g in range(2):
                        gx, gy = _local(item.x, item.y, item.heading, lx + (g - 0.5) * cw * 0.5, ly)
                        out.boxes.append(OBox(gx, gy, top_z, 0.55, 0.55, 3.0 + 9.0 * _unit(seed, 40 + i * 5 + j * 3 + g), item.heading, "plain", STEEL, seed))
                    continue
                h = (item.sz - low_h) * (0.25 + 0.75 * u)
                if item.kind == "damaged":
                    h *= 0.6
                cx, cy = _local(item.x, item.y, item.heading, lx, ly)
                out.boxes.append(OBox(cx, cy, top_z, cw * 0.96, cd * 0.96, h, item.heading, "facade", tone, seed + i * 3 + j))
                tallest = max(tallest, top_z + h)
                if _unit(seed, 60 + i + j * 3) < 0.35:
                    # Torn floor slab hanging off the edge.
                    sx_, sy_ = _local(item.x, item.y, item.heading, lx + cw * 0.15, ly)
                    out.boxes.append(OBox(sx_, sy_, top_z + h, cw * 0.7, cd * 0.5, 0.45, item.heading + 0.12, "plain", CONCRETE, seed))
        if _unit(seed, 90) < 0.55:
            bx, by = _local(item.x, item.y, item.heading, (_unit(seed, 91) - 0.5) * item.sx * 0.5, (_unit(seed, 92) - 0.5) * item.sy * 0.5)
            out.boxes.append(OBox(bx, by, tallest, 0.6, 0.6, 5.0, item.heading, "plain", STEEL, seed))
            out.boxes.append(OBox(bx, by, tallest + 5.0, 1.0, 1.0, 0.8, item.heading, "emissive", WARNING_RED, seed))
        out.obstacles.append(OObstacle(item.x, item.y, item.sx, item.sy, item.heading, tallest))
        # Rubble around the base.
        for m in range(6 + int(_unit(seed, 100) * 6)):
            side = _unit(seed, 110 + m)
            along = (_unit(seed, 130 + m) - 0.5)
            if side < 0.5:
                lx, ly = along * item.sx, (item.sy * 0.5 + 1.5 + 5.0 * _unit(seed, 150 + m)) * (1 if side < 0.25 else -1)
            else:
                lx, ly = (item.sx * 0.5 + 1.5 + 5.0 * _unit(seed, 150 + m)) * (1 if side < 0.75 else -1), along * item.sy
            rx, ry = _local(item.x, item.y, item.heading, lx, ly)
            size = 1.0 + 2.8 * _unit(seed, 170 + m)
            out.boxes.append(OBox(rx, ry, float(height_fn(rx, ry)) - 0.3, size, size * (0.6 + 0.6 * _unit(seed, 190 + m)), 0.5 + 1.6 * _unit(seed, 210 + m), _unit(seed, 230 + m) * TAU, "plain", RUBBLE, seed))
        if _unit(seed, 250) < 0.45:
            fx, fy = _local(item.x, item.y, item.heading, 0.0, 0.0)
            out.fires.append((fx, fy, tallest))

    # Open-ground debris of a long war.
    a0 = TAU * sector / sector_count
    a1 = TAU * (sector + 1) / sector_count
    span = r1 - r0

    def spot(salt, pad, allow_corridor=False, large=False):
        for attempt in range(12):
            ang = a0 + (a1 - a0) * (0.05 + 0.90 * _unit(sector, salt, attempt, 1))
            rad = r0 + span * (0.08 + 0.84 * _unit(sector, salt, attempt, 2))
            lateral = min(_angle_delta(ang, math.radians(d)) for d in URBAN_CORRIDOR_DEGREES) * rad
            if not allow_corridor and lateral < CORRIDOR_LANE_HALF + pad:
                continue
            x, y = math.cos(ang) * rad, math.sin(ang) * rad
            if any(math.hypot(x - cx, y - cy) < (cr if large else PROP_CLEAR_RADIUS) for cx, cy, cr in keep_clear):
                continue
            if _open_spot(structs, x, y, pad):
                return x, y, ang
        return None

    # Secondary collapsed blocks fill the gaps between the accepted structures.
    placed = []
    for q in range(14):
        s = spot(500 + q, 22.0, large=True)
        if s is None:
            continue
        x, y, ang = s
        if any(math.hypot(x - qx, y - qy) < 38.0 for qx, qy in placed):
            continue
        placed.append((x, y))
        seed = int(sector) * 1000 + 600 + q
        hd = ang + (math.pi * 0.5 if q % 2 else 0.0)
        sx = 18.0 + 22.0 * _unit(seed, 1)
        sy = 14.0 + 18.0 * _unit(seed, 2)
        h = 8.0 + 30.0 * _unit(seed, 3)
        z = float(height_fn(x, y)) - RUIN_SINK
        tone = FACADE_TONES[q % len(FACADE_TONES)]
        out.boxes.append(OBox(x, y, z, sx, sy, h * 0.55, hd, "facade", tone, seed))
        top = z + h * 0.55
        for i in range(2):
            u = _unit(seed, 10 + i)
            if u < 0.3:
                continue
            lx = (i - 0.5) * sx * 0.5
            cx, cy = _local(x, y, hd, lx, 0.0)
            hh = h * 0.45 * u
            out.boxes.append(OBox(cx, cy, top, sx * 0.48, sy * 0.92, hh, hd, "facade", tone, seed + i))
            top_i = top + hh
            gx, gy = _local(x, y, hd, lx + sx * 0.18, sy * 0.3)
            out.boxes.append(OBox(gx, gy, top_i, 0.5, 0.5, 2.0 + 6.0 * _unit(seed, 20 + i), hd, "plain", STEEL, seed))
        out.obstacles.append(OObstacle(x, y, sx, sy, hd, z + h))
        for m in range(4):
            rx, ry = _local(x, y, hd, (_unit(seed, 30 + m) - 0.5) * (sx + 8.0), (sy * 0.5 + 2.0) * (1 if m % 2 else -1))
            size = 1.2 + 2.4 * _unit(seed, 40 + m)
            out.boxes.append(OBox(rx, ry, float(height_fn(rx, ry)) - 0.3, size, size * 0.8, 0.6 + 1.4 * _unit(seed, 50 + m), _unit(seed, 60 + m) * TAU, "plain", RUBBLE, seed))
        if _unit(seed, 70) < 0.35:
            out.fires.append((x, y, top))

    for w in range(7):
        s = spot(1000 + w, 4.0)
        if s is None:
            continue
        x, y, ang = s
        hd = _unit(sector, w, 1100) * TAU
        z = float(height_fn(x, y))
        tone = WRECK_TONES[w % len(WRECK_TONES)]
        out.boxes.append(OBox(x, y, z, 4.6, 2.0, 1.0, hd, "plain", tone, w))
        cx, cy = _local(x, y, hd, -0.3, 0.0)
        out.boxes.append(OBox(cx, cy, z + 1.0, 2.2, 1.8, 0.7, hd, "plain", (0.08, 0.07, 0.07), w))
        out.obstacles.append(OObstacle(x, y, 4.6, 2.0, hd, z + 1.7))
        if _unit(sector, w, 1150) < 0.4:
            out.boxes.append(OBox(cx, cy, z + 1.7, 0.9, 0.9, 0.5, hd, "fire", FIRE, w))
            out.fires.append((cx, cy, z + 2.0))
    for b in range(3):
        s = spot(2000 + b, 8.0, allow_corridor=True)
        if s is None:
            continue
        x, y, ang = s
        tangent = ang + math.pi * 0.5
        count = 4 + int(_unit(sector, b, 2100) * 4)
        for k in range(count):
            off = (k - count * 0.5) * 3.9
            bx, by = x + math.cos(tangent) * off, y + math.sin(tangent) * off
            if not _open_spot(structs, bx, by, 1.5):
                continue
            if any(math.hypot(bx - cx, by - cy) < PROP_CLEAR_RADIUS for cx, cy, _cr in keep_clear):
                continue
            z = float(height_fn(bx, by))
            hd = tangent + (_unit(sector, b, k, 2200) - 0.5) * 0.35
            out.boxes.append(OBox(bx, by, z, 3.4, 0.8, 1.05, hd, "plain", CONCRETE, k))
            out.boxes.append(OBox(bx, by, z + 1.05, 3.2, 0.12, 0.10, hd, "emissive", (0.95, 0.55, 0.08), k))
            out.obstacles.append(OObstacle(bx, by, 3.4, 0.8, hd, z + 1.05))
    if sector % 2 == 0:
        s = spot(3000, 10.0)
        if s is not None:
            x, y, ang = s
            z = float(height_fn(x, y))
            for lx, ly in ((-1.4, -1.4), (1.4, -1.4), (1.4, 1.4), (-1.4, 1.4)):
                px, py = _local(x, y, ang, lx, ly)
                out.boxes.append(OBox(px, py, z, 0.35, 0.35, 16.0, ang, "plain", STEEL, 0))
            out.boxes.append(OBox(x, y, z + 16.0, 4.2, 4.2, 0.6, ang, "plain", STEEL, 0))
            out.boxes.append(OBox(x, y, z + 16.6, 3.6, 3.6, 2.2, ang, "plain", (0.14, 0.12, 0.11), 0))
            out.boxes.append(OBox(x, y, z + 18.8, 1.0, 1.0, 0.8, ang, "emissive", WARNING_RED, 0))
            out.obstacles.append(OObstacle(x, y, 3.4, 3.4, ang, z + 19.6))
            out.towers.append((x, y, z + 18.2))
    for f in range(5):
        s = spot(4000 + f, 2.5)
        if s is None:
            continue
        x, y, ang = s
        z = float(height_fn(x, y))
        out.boxes.append(OBox(x, y, z, 0.9, 0.9, 1.2, 0.0, "plain", (0.18, 0.12, 0.08), f))
        out.boxes.append(OBox(x, y, z + 1.2, 0.8, 0.8, 0.35, 0.0, "fire", FIRE, f))
        out.obstacles.append(OObstacle(x, y, 0.9, 0.9, 0.0, z + 1.5))
    return out


def resolve_move(obstacles, px, py, nx, ny, radius=0.9, z=None):
    """Axis-separated sliding against oriented obstacles (same contract as metropolis_layout)."""
    def blocked(x, y):
        for ob in obstacles:
            if z is not None and z > ob.top + 1.0:
                continue
            if ob.contains(x, y, radius):
                return True
        return False

    if not blocked(nx, ny):
        return nx, ny, False
    if not blocked(nx, py):
        return nx, py, True
    if not blocked(px, ny):
        return px, ny, True
    if blocked(px, py):
        return nx, ny, True
    return px, py, True


# --------------------------------------------------------------------------
# Battle simulation
# --------------------------------------------------------------------------
UNIT_STATS = {
    #        hp   speed  range  cooldown  damage  hit   aim height
    SCRAP: (4.0, 5.5, 42.0, 0.95, 1.0, 0.55, 3.8),
    CHOIR: (4.0, 4.2, 48.0, 1.35, 1.5, 0.50, 2.8),
}
SABLE_FIRE_INTERVAL = 0.55
SABLE_HIT_CHANCE = 0.92
SABLE_RANGE = 62.0
SABLE_STRAFE = 22.0
DYING_SECONDS = 1.4
RESPAWN_SECONDS = (6.0, 10.0)


@dataclass
class Unit:
    uid: str
    team: str
    x: float
    y: float
    heading: float
    spawn: tuple
    hp: float
    state: str = "alive"          # alive | dying | dead
    timer: float = 0.0
    cooldown: float = 0.0
    target: str = ""
    walked: float = 0.0           # metres walked (drives the leg animation)
    aim: float = 0.0              # turret / arm aim heading
    phase: float = 0.0            # per-unit sidestep phase


@dataclass
class Site:
    key: str
    x: float
    y: float
    tangent: float                 # direction along which the two sides face off
    sable: bool = False


def sector_site(sector: int, r0: float, r1: float, height_fn=None, sector_count: int = 48):
    """Open battleground for a sector skirmish, or None if the sector is too built up."""
    structs = generate_urban_structures(int(sector), float(r0), float(r1), sector_count=sector_count)
    a0 = TAU * sector / sector_count
    a1 = TAU * (sector + 1) / sector_count
    for attempt in range(24):
        ang = a0 + (a1 - a0) * (0.15 + 0.70 * _unit(sector, attempt, 501))
        if in_corridor(ang, 0.075):
            continue
        rad = r0 + (r1 - r0) * (0.20 + 0.60 * _unit(sector, attempt, 503))
        x, y = math.cos(ang) * rad, math.sin(ang) * rad
        if _open_spot(structs, x, y, SITE_CLEARANCE):
            return Site(f"s{int(sector)}", x, y, ang + math.pi * 0.5)
    return None


class Battle:
    """One battleground.  Deterministic for a given seed."""

    def __init__(self, site: Site, seed: int, *, per_side: int = 3, sable_hostiles: int = 6):
        self.site = site
        self.rng = random.Random(seed)
        self.units = []
        self.time = 0.0
        self.sable_pos = (site.x, site.y, 8.0)
        self.sable_heading = 0.0
        self.sable_cooldown = 0.0
        self.sable_target = ""
        self.sable_kills = 0
        self.shield_hits = 0
        self.deaths = 0
        tx, ty = math.cos(site.tangent), math.sin(site.tangent)
        if site.sable:
            for k in range(int(sable_hostiles)):
                team = SCRAP if k % 2 == 0 else CHOIR
                side = 1.0 if k % 2 == 0 else -1.0
                dist = 58.0 + 34.0 * self.rng.random()
                sx = site.x + tx * side * dist + (self.rng.random() - 0.5) * 30.0
                sy = site.y + ty * side * dist + (self.rng.random() - 0.5) * 30.0
                self._add(f"{site.key}-{team}-{k}", team, sx, sy)
        else:
            for team, side in ((SCRAP, 1.0), (CHOIR, -1.0)):
                for k in range(int(per_side)):
                    lateral = (k - (per_side - 1) * 0.5) * 9.0
                    sx = site.x + tx * side * 34.0 - ty * lateral
                    sy = site.y + ty * side * 34.0 + tx * lateral
                    self._add(f"{site.key}-{team}-{k}", team, sx, sy)

    def _add(self, uid, team, x, y):
        hp = UNIT_STATS[team][0]
        heading = math.atan2(self.site.y - y, self.site.x - x)
        self.units.append(Unit(uid, team, x, y, heading, (x, y), hp, cooldown=self.rng.random() * 1.5, aim=heading, phase=self.rng.random() * 6.0))

    def unit(self, uid):
        for u in self.units:
            if u.uid == uid:
                return u
        return None

    def _enemies(self, u):
        if self.site.sable:
            return []
        return [o for o in self.units if o.team != u.team and o.state == "alive"]

    def update(self, dt: float, *, sable_pos=None, sable_active: bool = True, ground=lambda x, y: 0.0):
        """Advance the battle; returns render events."""
        dt = max(0.0, min(0.1, float(dt)))
        self.time += dt
        events = []
        if sable_pos is not None:
            self.sable_pos = tuple(sable_pos)
        for u in self.units:
            team_hp, speed, rng_, cooldown, damage, hit_chance, aim_h = UNIT_STATS[u.team]
            if u.state == "dying":
                u.timer -= dt
                if u.timer <= 0.0:
                    u.state = "dead"
                    u.timer = self.rng.uniform(*RESPAWN_SECONDS)
                continue
            if u.state == "dead":
                u.timer -= dt
                if u.timer <= 0.0:
                    u.state = "alive"
                    u.hp = team_hp
                    u.x = u.spawn[0] + (self.rng.random() - 0.5) * 12.0
                    u.y = u.spawn[1] + (self.rng.random() - 0.5) * 12.0
                    u.cooldown = 1.0 + self.rng.random()
                    events.append(("respawn", u.uid))
                continue
            # Pick a target.
            if self.site.sable:
                tx, ty, tz = self.sable_pos
                target_id = SABLE
            else:
                enemies = self._enemies(u)
                if not enemies:
                    continue
                tgt = min(enemies, key=lambda o: (o.x - u.x) ** 2 + (o.y - u.y) ** 2)
                tx, ty = tgt.x, tgt.y
                tz = ground(tgt.x, tgt.y) + UNIT_STATS[tgt.team][6]
                target_id = tgt.uid
            u.target = target_id
            dx, dy = tx - u.x, ty - u.y
            dist = math.hypot(dx, dy)
            want = math.atan2(dy, dx)
            u.aim = want
            engage = rng_ * (0.80 if self.site.sable else 0.70)
            if dist > engage:
                step = min(speed * dt, dist - engage)
                u.x += math.cos(want) * step
                u.y += math.sin(want) * step
                u.walked += step
                u.heading = want
            else:
                # Hold the line with a slow sidestep so the fight reads alive.
                side = math.sin(self.time * 0.6 + u.phase)
                u.x += -math.sin(want) * side * speed * 0.25 * dt
                u.y += math.cos(want) * side * speed * 0.25 * dt
                u.walked += abs(side) * speed * 0.25 * dt
                u.heading = want
            u.cooldown -= dt
            if dist <= rng_ and u.cooldown <= 0.0 and (sable_active or not self.site.sable):
                u.cooldown = cooldown * (0.8 + 0.4 * self.rng.random())
                hit = self.rng.random() < hit_chance
                muzzle = (u.x + math.cos(want) * 1.4, u.y + math.sin(want) * 1.4, ground(u.x, u.y) + aim_h)
                miss = (0.0, 0.0, 0.0) if hit else ((self.rng.random() - 0.5) * 6.0, (self.rng.random() - 0.5) * 6.0, (self.rng.random() - 0.3) * 4.0)
                end = (tx + miss[0], ty + miss[1], tz + miss[2])
                events.append(("shot", u.uid, muzzle, end, hit, target_id))
                if hit:
                    if target_id == SABLE:
                        self.shield_hits += 1
                        events.append(("shield", end))
                    else:
                        tgt = self.unit(target_id)
                        tgt.hp -= damage
                        if tgt.hp <= 0.0 and tgt.state == "alive":
                            self._kill(tgt, events)
        if self.site.sable and sable_active:
            self.sable_cooldown -= dt
            alive = [o for o in self.units if o.state == "alive"]
            sx, sy, sz = self.sable_pos
            in_range = [o for o in alive if math.hypot(o.x - sx, o.y - sy) <= SABLE_RANGE]
            if in_range:
                tgt = self.unit(self.sable_target)
                if tgt is None or tgt.state != "alive" or tgt not in in_range:
                    tgt = min(in_range, key=lambda o: (o.x - sx) ** 2 + (o.y - sy) ** 2)
                    self.sable_target = tgt.uid
                self.sable_heading = math.atan2(tgt.y - sy, tgt.x - sx)
                if self.sable_cooldown <= 0.0:
                    self.sable_cooldown = SABLE_FIRE_INTERVAL
                    hit = self.rng.random() < SABLE_HIT_CHANCE
                    tz = ground(tgt.x, tgt.y) + UNIT_STATS[tgt.team][6]
                    end = (tgt.x, tgt.y, tz) if hit else (tgt.x + (self.rng.random() - 0.5) * 5.0, tgt.y + (self.rng.random() - 0.5) * 5.0, tz)
                    events.append(("shot", SABLE, (sx, sy, sz), end, hit, tgt.uid))
                    if hit:
                        tgt.hp -= 1.0
                        if tgt.hp <= 0.0:
                            self._kill(tgt, events)
                            self.sable_kills += 1
        return events

    def _kill(self, u, events):
        u.state = "dying"
        u.timer = DYING_SECONDS
        u.hp = 0.0
        self.deaths += 1
        events.append(("death", u.uid))

    def sable_offset(self, t: float):
        """Sable's combat strafe around her post (x, y offsets in metres along the site tangent)."""
        tx, ty = math.cos(self.site.tangent), math.sin(self.site.tangent)
        a = math.sin(t * 0.37) * SABLE_STRAFE
        b = math.sin(t * 0.61 + 1.3) * SABLE_STRAFE * 0.45
        return tx * a - ty * b, ty * a + tx * b
