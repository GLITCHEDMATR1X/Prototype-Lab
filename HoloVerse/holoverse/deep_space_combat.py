"""HoloSpace defence wings (Pass 282.76).

Every dimension planet and Dyson Prime has a defence perimeter.  The planets sit in the
unreachable sky layer, so "getting close" is measured the same way Dyson Prime's distance is:
the distance flown *toward* that body (travel along its sky direction, never below zero).

* Approaching a perimeter shows a warning; crossing it pulls the ship out of supercruise
  ("INTERDICTED") and a defence wing launches from that direction.
* Wing ships orbit the player and fire bolts.  Two-thirds of a perimeter back out (or every
  ship destroyed) and the wing breaks off.
* Each wing ship takes three laser hits.

Performance: at most MAX_ENEMIES ships and MAX_BOLTS bolts exist; everything is plain Python
vectors with one small node each, positioned with the same floating origin as the rock fields.
"""
from __future__ import annotations

import math
from random import Random

from panda3d.core import (
    ColorBlendAttrib,
    LineSegs,
    NodePath,
    Point2,
    Point3,
    TransparencyAttrib,
    Vec3,
)

PLANET_GUARD_RANGE = 400_000.0     # metres flown toward a planet before its wing launches
DYSON_GUARD_AU = 30.0               # Dyson Prime's wing launches inside this distance
WARN_FRACTION = 0.70                # perimeter warning from here
RELEASE_FRACTION = 0.66             # wing breaks off when the approach drops below this share
PLANET_WING = 3
DYSON_WING = 5
MAX_ENEMIES = 6
MAX_BOLTS = 32

ENEMY_HP = 3
ENEMY_RADIUS = 22.0
ENEMY_MAX_SPEED = 270.0             # below the player's top speed: you can always run
ENEMY_ACCEL = 150.0
ENEMY_ORBIT = 430.0
ENEMY_FIRE_RANGE = 1700.0
ENEMY_RETREAT_TIME = 12.0
BOLT_SPEED = 950.0
BOLT_LIFE = 2.6
BOLT_DAMAGE = 5.0
BOLT_SPREAD = 0.040

ENEMY_RED = (1.00, 0.30, 0.24)
SHIP_SCALE = 1.6                    # interceptors are about 24 m long


def _ship_mesh(mesh_cls):
    """A small angular interceptor: fuselage, swept wings, tail fins (built once, instanced)."""
    m = mesh_cls("holospace-guard-ship", normals=True)
    hull = (0.24, 0.24, 0.28, 1.0)
    dark = (0.12, 0.12, 0.15, 1.0)
    accent = (0.70, 0.16, 0.14, 1.0)
    m.box((0.0, 0.0, 0.0), (3.2, 15.0, 2.6), hull)          # fuselage (nose toward +Y)
    m.box((0.0, 7.6, 0.0), (1.6, 3.0, 1.4), accent)         # nose
    m.box((0.0, -1.0, 0.0), (17.0, 5.2, 0.6), dark)         # wings
    for side in (-1.0, 1.0):
        m.box((side * 8.4, -2.5, 0.0), (0.8, 7.0, 3.4), accent)   # wing-tip fins
    m.box((0.0, -6.8, 1.4), (0.6, 3.0, 3.4), dark)          # tail fin
    return m.node()


class DefenceWings:
    def __init__(self, flight, mesh_cls, radial_texture, billboard):
        self.flight = flight
        self.app = flight.app
        self.rng = Random(0xDEF3)
        self.enemies: list = []
        self.bolts: list = []
        self.zones: dict = {}               # key -> {"approach": m, "engaged": bool, "warned": bool}
        self.engaged_key = None
        self.engaged_title = ""
        self.root = flight.local_root.attachNewNode("holospace-defence")
        self.root.setLight(flight.sun_np)
        self.root.setLight(flight.amb_np)
        self.template = _ship_mesh(mesh_cls)
        self.glow_tex = radial_texture("holospace-guard-glow", 32, 2.0, core=0.3)
        self._billboard = billboard
        bolt = LineSegs("holospace-guard-bolt")
        bolt.setThickness(3.0 * float(getattr(flight, "line_scale", 1.0)))
        bolt.setColor(1.0, 0.45, 0.30, 1.0)
        bolt.moveTo(0, -9.0, 0)
        bolt.setColor(1.0, 0.85, 0.60, 1.0)
        bolt.drawTo(0, 9.0, 0)
        self.bolt_template = NodePath(bolt.create())
        self.bolt_root = flight.local_root.attachNewNode("holospace-guard-bolts")
        self.bolt_root.setLightOff(1)
        self.bolt_root.setDepthWrite(False)
        self.bolt_root.setTransparency(TransparencyAttrib.MAlpha)
        self.bolt_root.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        self.markers = []
        self._build_markers()

    # ------------------------------------------------------------------ HUD target brackets
    def _build_markers(self) -> None:
        a2d = self.app.aspect2d
        for i in range(MAX_ENEMIES):
            ls = LineSegs(f"holospace-guard-marker-{i}")
            ls.setThickness(1.6 * float(getattr(self.flight, "line_scale", 1.0)))
            ls.setColor(*ENEMY_RED, 0.95)
            s = 0.022
            for (x0, z0), (x1, z1), (x2, z2) in (((-s, s * 0.4), (-s, s), (-s * 0.4, s)), ((s * 0.4, s), (s, s), (s, s * 0.4)),
                                                 ((s, -s * 0.4), (s, -s), (s * 0.4, -s)), ((-s * 0.4, -s), (-s, -s), (-s, -s * 0.4))):
                ls.moveTo(x0, 0, z0)
                ls.drawTo(x1, 0, z1)
                ls.drawTo(x2, 0, z2)
            node = a2d.attachNewNode(ls.create())
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.hide()
            self.markers.append(node)

    def _update_markers(self) -> None:
        app = self.app
        cam = app.camera
        shown = 0
        for enemy in self.enemies:
            if shown >= len(self.markers):
                break
            node = enemy["node"]
            try:
                rel = cam.getRelativePoint(app.render, node.getPos(app.render))
            except Exception:
                continue
            p2 = Point2()
            if rel.y > 1.0 and app.camLens.project(Point3(rel), p2):
                marker = self.markers[shown]
                aspect = app.camLens.getAspectRatio()
                marker.setPos(p2.x * aspect, 0, p2.y)
                d = math.sqrt(rel.x * rel.x + rel.y * rel.y + rel.z * rel.z)
                marker.setScale(max(0.6, min(1.6, 900.0 / max(1.0, d))))
                marker.setAlphaScale(1.0 if enemy["state"] == "attack" else 0.45)
                marker.show()
                shown += 1
        for marker in self.markers[shown:]:
            marker.hide()

    # ------------------------------------------------------------------ perimeters
    def _zone_list(self):
        flight = self.flight
        zones = []
        planets = getattr(flight, "planets", None)
        for p in list(getattr(planets, "planets", []) or []):
            rec = p.get("record")
            key = str(getattr(rec, "dimension_id", "") or id(p))
            zones.append((key, str(getattr(rec, "title", "PLANET")), Vec3(p["dir"]), "planet"))
        zones.append(("dyson", "DYSON PRIME", Vec3(flight.dyson_dir), "dyson"))
        return zones

    def track_travel(self, step: Vec3) -> None:
        """Called with the ship's movement each frame (world metres)."""
        for key, _title, direction, kind in self._zone_list():
            if kind != "planet":
                continue
            zone = self.zones.setdefault(key, {"approach": 0.0, "engaged": False, "warned": False})
            zone["approach"] = max(0.0, zone["approach"] + float(step.dot(direction)))

    def _zone_fraction(self, key, kind) -> float:
        if kind == "dyson":
            flight = self.flight
            from holoverse.deep_space import DYSON_START_AU
            au = flight.dyson_distance_au()
            return max(0.0, (DYSON_START_AU - au) / max(1e-6, DYSON_START_AU - DYSON_GUARD_AU))
        zone = self.zones.get(key)
        return (zone["approach"] / PLANET_GUARD_RANGE) if zone else 0.0

    def nearest_perimeter(self):
        """(fraction of the way to the closest perimeter, its name) for the HUD."""
        best = (0.0, "")
        for key, title, _d, kind in self._zone_list():
            f = self._zone_fraction(key, kind)
            if f > best[0]:
                best = (f, title)
        return best

    def _check_perimeters(self) -> None:
        flight = self.flight
        for key, title, direction, kind in self._zone_list():
            zone = self.zones.setdefault(key, {"approach": 0.0, "engaged": False, "warned": False})
            f = self._zone_fraction(key, kind)
            if not zone["engaged"]:
                if f >= 1.0:
                    zone["engaged"] = True
                    zone["warned"] = True
                    self._launch_wing(key, title, direction, DYSON_WING if kind == "dyson" else PLANET_WING)
                elif f >= WARN_FRACTION and not zone["warned"]:
                    zone["warned"] = True
                    flight.flash(f"{title.upper()}  //  DEFENCE PERIMETER AHEAD", 2.6)
                elif f < WARN_FRACTION * 0.8:
                    zone["warned"] = False
            elif f < RELEASE_FRACTION:
                zone["engaged"] = False
                zone["warned"] = False
                if self.engaged_key == key:
                    self._release(f"{title.upper()} DEFENCE  //  BREAKING OFF")

    def _launch_wing(self, key, title, direction: Vec3, count: int) -> None:
        flight = self.flight
        if flight.mode != "normal":
            flight.interdict(f"INTERDICTED  //  {title.upper()} DEFENCE")
        self.engaged_key = key
        self.engaged_title = title
        sx, sy, sz = flight.pos
        d = Vec3(direction)
        d.normalize()
        side = d.cross(Vec3(0, 0, 1))
        if side.lengthSquared() < 1e-4:
            side = Vec3(1, 0, 0)
        side.normalize()
        up = side.cross(d)
        for i in range(max(0, min(count, MAX_ENEMIES - len(self.enemies)))):
            offset = d * self.rng.uniform(1300.0, 1900.0) + side * self.rng.uniform(-500.0, 500.0) + up * self.rng.uniform(-300.0, 300.0)
            self._spawn((sx + offset.x, sy + offset.y, sz + offset.z), -d * 120.0)
        flight.flash(f"HOSTILES  //  {title.upper()} DEFENCE WING", 2.8)

    def _spawn(self, pos, vel: Vec3) -> None:
        holder = self.root.attachNewNode("holospace-guard")
        body = holder.attachNewNode("holospace-guard-body")
        body.setScale(SHIP_SCALE)
        self.template.instanceTo(body)
        glow = self._billboard(holder, "holospace-guard-engine", self.glow_tex, 3.2 * SHIP_SCALE, (1.0, 0.45, 0.25, 0.9), (0, -8.2 * SHIP_SCALE, 0))
        glow.setLightOff(1)
        self.enemies.append({
            "node": holder, "pos": list(pos), "vel": Vec3(vel), "hp": ENEMY_HP, "state": "attack",
            "fire": self.rng.uniform(1.4, 2.4), "phase": self.rng.uniform(0, math.tau), "retreat": 0.0, "hit_flash": 0.0,
        })

    def _release(self, message: str) -> None:
        for enemy in self.enemies:
            enemy["state"] = "retreat"
        self.engaged_key = None
        if self.enemies:
            self.flight.flash(message, 2.2)

    # ------------------------------------------------------------------ frame
    def update(self, dt: float) -> None:
        flight = self.flight
        self._check_perimeters()
        sx, sy, sz = flight.pos
        anchor = flight.anchor
        ship = Vec3(sx, sy, sz)
        keep = []
        for e in self.enemies:
            px, py, pz = e["pos"]
            pos = Vec3(px, py, pz)
            to_ship = ship - pos
            dist = to_ship.length()
            if e["state"] == "attack":
                e["phase"] += dt * 0.55
                orbit = Vec3(math.cos(e["phase"]), math.sin(e["phase"]), 0.35 * math.sin(e["phase"] * 1.7)) * ENEMY_ORBIT
                target = ship + orbit
                want = target - pos
                if want.lengthSquared() > 1.0:
                    want.normalize()
                want *= ENEMY_MAX_SPEED
            else:
                e["retreat"] += dt
                away = -to_ship
                if away.lengthSquared() > 1.0:
                    away.normalize()
                want = away * ENEMY_MAX_SPEED * 1.2
            delta = want - e["vel"]
            step = ENEMY_ACCEL * dt
            if delta.length() > step:
                delta.normalize()
                delta *= step
            e["vel"] = e["vel"] + delta
            pos = pos + e["vel"] * dt
            e["pos"] = [pos.x, pos.y, pos.z]
            node = e["node"]
            node.setPos(anchor.x + pos.x - sx, anchor.y + pos.y - sy, anchor.z + pos.z - sz)
            face = Point3(anchor.x, anchor.y, anchor.z) if e["state"] == "attack" else node.getPos() + e["vel"]
            node.lookAt(face)
            if e["hit_flash"] > 0.0:
                e["hit_flash"] = max(0.0, e["hit_flash"] - dt)
                node.setColorScale(1.0 + 6.0 * e["hit_flash"], 1.0 + 2.0 * e["hit_flash"], 1.0, 1.0)
            elif node.hasColorScale():
                node.clearColorScale()
            if e["state"] == "attack" and dist < ENEMY_FIRE_RANGE and not flight.dead:
                e["fire"] -= dt
                if e["fire"] <= 0.0:
                    e["fire"] = self.rng.uniform(1.6, 2.6)
                    self._fire(pos, ship, flight.vel)
            if e["state"] == "retreat" and (e["retreat"] > ENEMY_RETREAT_TIME or dist > 7000.0):
                node.removeNode()
                continue
            keep.append(e)
        self.enemies = keep
        if self.engaged_key is not None and not self.enemies:
            self.engaged_key = None
        self._update_bolts(dt)
        self._update_markers()

    def _fire(self, pos: Vec3, ship: Vec3, ship_vel: Vec3) -> None:
        if len(self.bolts) >= MAX_BOLTS:
            return
        rel = ship - pos
        lead = rel.length() / BOLT_SPEED
        aim = ship + ship_vel * lead * 0.8 - pos
        if aim.lengthSquared() < 1.0:
            return
        aim.normalize()
        aim += Vec3(self.rng.uniform(-1, 1), self.rng.uniform(-1, 1), self.rng.uniform(-1, 1)) * BOLT_SPREAD
        aim.normalize()
        node = self.bolt_template.instanceTo(self.bolt_root)
        self.bolts.append({"node": node, "pos": [pos.x, pos.y, pos.z], "vel": aim * BOLT_SPEED, "life": BOLT_LIFE})

    def _update_bolts(self, dt: float) -> None:
        flight = self.flight
        sx, sy, sz = flight.pos
        anchor = flight.anchor
        keep = []
        hit_r = 9.0 + 6.0                    # ship radius plus the bolt's length tolerance
        for b in self.bolts:
            b["life"] -= dt
            px, py, pz = b["pos"]
            v = b["vel"]
            nx, ny, nz = px + v.x * dt, py + v.y * dt, pz + v.z * dt
            # closest approach of this frame's segment to the ship
            seg = Vec3(nx - px, ny - py, nz - pz)
            rel = Vec3(sx - px, sy - py, sz - pz)
            ln2 = seg.lengthSquared()
            t = max(0.0, min(1.0, rel.dot(seg) / ln2)) if ln2 > 1e-6 else 0.0
            closest = rel - seg * t
            if not flight.dead and closest.lengthSquared() < hit_r * hit_r:
                flight.take_damage(BOLT_DAMAGE, "hit")
                b["node"].removeNode()
                continue
            if b["life"] <= 0.0:
                b["node"].removeNode()
                continue
            b["pos"] = [nx, ny, nz]
            node = b["node"]
            node.setPos(anchor.x + nx - sx, anchor.y + ny - sy, anchor.z + nz - sz)
            node.lookAt(node.getPos() + v)
            keep.append(b)
        self.bolts = keep

    # ------------------------------------------------------------------ player weapon
    def ray_hit(self, origin, direction: Vec3, max_range: float):
        """Nearest wing ship along the ray: (distance, enemy) or None."""
        best = None
        ox, oy, oz = origin
        for e in self.enemies:
            px, py, pz = e["pos"]
            rx, ry, rz = px - ox, py - oy, pz - oz
            t = rx * direction.x + ry * direction.y + rz * direction.z
            if t <= 0.0 or t > max_range + ENEMY_RADIUS:
                continue
            miss2 = rx * rx + ry * ry + rz * rz - t * t
            if miss2 > ENEMY_RADIUS * ENEMY_RADIUS:
                continue
            hit_t = t - math.sqrt(max(0.0, ENEMY_RADIUS * ENEMY_RADIUS - miss2))
            if best is None or hit_t < best[0]:
                best = (hit_t, e)
        return best

    def damage(self, enemy, amount: int = 1) -> bool:
        """Apply laser damage; True when the ship is destroyed."""
        enemy["hp"] -= amount
        enemy["hit_flash"] = 0.25
        if enemy["state"] == "retreat":
            enemy["state"] = "attack"
        if enemy["hp"] > 0:
            return False
        if not enemy["node"].isEmpty():
            enemy["node"].removeNode()
        try:
            self.enemies.remove(enemy)
        except ValueError:
            pass
        if not self.enemies and self.engaged_key is not None:
            self.flight.flash(f"{self.engaged_title.upper()} DEFENCE WING DESTROYED", 2.4)
            self.engaged_key = None
        return True

    # ------------------------------------------------------------------ lifecycle
    def clear(self, reset_zones: bool = False) -> None:
        for e in self.enemies:
            if not e["node"].isEmpty():
                e["node"].removeNode()
        for b in self.bolts:
            if not b["node"].isEmpty():
                b["node"].removeNode()
        self.enemies = []
        self.bolts = []
        self.engaged_key = None
        for marker in self.markers:
            marker.hide()
        if reset_zones:
            self.zones = {}

    def hide_ui(self) -> None:
        for marker in self.markers:
            marker.hide()

    def report(self) -> dict:
        frac, name = self.nearest_perimeter()
        return {"enemies": len(self.enemies), "bolts": len(self.bolts), "engaged": self.engaged_title if self.engaged_key else "",
                "nearest_perimeter": name, "nearest_perimeter_fraction": round(frac, 3)}
