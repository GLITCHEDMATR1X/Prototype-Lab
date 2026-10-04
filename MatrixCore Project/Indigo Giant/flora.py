"""Alien flora for The Indigo Giant.

Pass 38 adds the first plant: the BLOOD BRANCH, a waist-to-shoulder-high red
coral-like growth.

* Standing close to an intact branch slowly heals the human (and the giant, who
  kneels near it). Each branch holds a limited pool of sap that refills slowly,
  so one plant cannot heal forever.
* Smashing a branch (the giant punches it, or the human breaks it with E held)
  turns it into a stump and drops a few SCRAPS. The stump regrows after a while.
  Healing now versus materials for later is the survival choice.

Placement is deterministic per 48 m world cell, so the same plants are always in
the same places.  Only cells near the active actor are instanced; smashed state is
remembered per plant id when cells stream out and back in.
"""
from __future__ import annotations

import math
import random
import zlib

from panda3d.core import (
    Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter,
    NodePath, Point3, Vec3, Vec4,
)

CELL_SIZE = 72.0                   # Pass 42: sparser — a branch is something you walk toward
ACTIVE_RADIUS_CELLS = 3            # ~250 m around the player; far enough for giant view
BRANCH_CHANCE = 0.42               # chance a cell grows a branch (Pass 48: the one common plant - both giants eat it)
MAX_SLOPE_DEG = 11.0               # branches root on level ground, not on dune faces
BRANCH_HEIGHT = 2.4                # metres; a human stands chest-high to one
HUMAN_HEAL_RADIUS = 2.6
GIANT_HEAL_RADIUS = 9.5
HUMAN_HEAL_RATE = 7.0              # health per second while in range and sap remains
GIANT_HEAL_RATE = 3.0
SAP_MAX = 70.0                     # total health one branch can give before resting
SAP_REFILL_RATE = 0.8              # sap per second while nobody draws from it
SCRAPS_PER_BRANCH = 4
REGROW_SECONDS = 240.0
SCRAP_HUMAN_PICKUP = 1.4
SCRAP_GIANT_PICKUP = 6.0
SMASH_RANGE_GIANT = 8.0
SMASH_RANGE_HUMAN = 2.2
SAFE_START_OFFSET = (-7.5, -9.0)   # one guaranteed branch near the start, relative to the human
PLANT_GROW_SECONDS = 120.0         # Pass 43: a planted seed becomes a full branch in 2 minutes
SCRAP_LIFETIME = 180.0             # Pass 44: unpicked scraps sink back into the sand
POISON_TINT = (1.05, 2.9, 3.1, 1.0)     # Pass 47: a poisoned branch turns pale pink-white
MAX_SCRAPS = 80                    # Pass 44: hard cap; the oldest go first

_TRUNK = Vec4(0.42, 0.06, 0.07, 1.0)
_TIP = Vec4(0.86, 0.22, 0.20, 1.0)
_STUMP = Vec4(0.30, 0.10, 0.09, 1.0)
_SCRAP = Vec4(0.70, 0.13, 0.12, 1.0)


# ---------------------------------------------------------------------------
# Geometry (built once per variant, then instanced)
# ---------------------------------------------------------------------------
def _tube(writer_set, start: Point3, end: Point3, r0: float, r1: float, c0: Vec4, c1: Vec4, sides: int = 5):
    vw, nw, cw, tris, base = writer_set
    axis = end - start
    length = axis.length()
    if length < 1e-6:
        return 0
    axis /= length
    ref = Vec3(0, 0, 1) if abs(axis.z) < 0.9 else Vec3(1, 0, 0)
    u = axis.cross(ref)
    u.normalize()
    v = axis.cross(u)
    for ring, (centre, radius, colour) in enumerate(((start, r0, c0), (end, r1, c1))):
        for i in range(sides):
            a = 2.0 * math.pi * i / sides
            n = u * math.cos(a) + v * math.sin(a)
            vw.addData3(centre + n * radius)
            nw.addData3(n)
            cw.addData4(colour)
    for i in range(sides):
        j = (i + 1) % sides
        a0, a1 = base + i, base + j
        b0, b1 = base + sides + i, base + sides + j
        tris.addVertices(a0, a1, b1)
        tris.addVertices(a0, b1, b0)
    return sides * 2


def _grow(rng: random.Random, segments: list, start: Point3, direction: Vec3, length: float,
          radius: float, depth: int):
    direction = Vec3(direction)
    direction.normalize()
    end = start + direction * length
    segments.append((start, end, radius, radius * 0.62, depth))
    if depth <= 0:
        return
    for _ in range(2 if depth > 1 else rng.choice((1, 2, 3))):
        spread = math.radians(rng.uniform(24, 46))
        turn = rng.uniform(0, 2 * math.pi)
        side = Vec3(math.cos(turn), math.sin(turn), 0)
        new_dir = direction * math.cos(spread) + side * math.sin(spread)
        new_dir.z = max(new_dir.z, 0.25)
        _grow(rng, segments, end, new_dir, length * rng.uniform(0.62, 0.78), radius * 0.62, depth - 1)


def build_branch_geom(variant_seed: int) -> GeomNode:
    rng = random.Random(variant_seed)
    segments: list = []
    trunk_len = BRANCH_HEIGHT * 0.36
    for k in range(rng.choice((2, 3))):
        lean = Vec3(rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25), 1.0)
        base = Point3(rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), -0.05)
        _grow(rng, segments, base, lean, trunk_len * rng.uniform(0.85, 1.1), 0.075, 3)
    max_depth = 3
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData('blood_branch', fmt, Geom.UHStatic)
    vw, nw, cw = GeomVertexWriter(vdata, 'vertex'), GeomVertexWriter(vdata, 'normal'), GeomVertexWriter(vdata, 'color')
    tris = GeomTriangles(Geom.UHStatic)
    rows = 0
    for start, end, r0, r1, depth in segments:
        t0 = 1.0 - (depth + 1) / (max_depth + 1)
        t1 = 1.0 - depth / (max_depth + 1)
        c0 = _TRUNK + (_TIP - _TRUNK) * t0
        c1 = _TRUNK + (_TIP - _TRUNK) * t1
        rows += _tube((vw, nw, cw, tris, rows), start, end, r0, r1, c0, c1)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode('blood_branch_geom')
    node.addGeom(geom)
    return node


def build_stump_geom() -> GeomNode:
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData('blood_stump', fmt, Geom.UHStatic)
    vw, nw, cw = GeomVertexWriter(vdata, 'vertex'), GeomVertexWriter(vdata, 'normal'), GeomVertexWriter(vdata, 'color')
    tris = GeomTriangles(Geom.UHStatic)
    rows = 0
    rng = random.Random(9)
    for k in range(3):
        a = k * 2.1
        top = Point3(math.cos(a) * 0.12, math.sin(a) * 0.12, rng.uniform(0.18, 0.32))
        rows += _tube((vw, nw, cw, tris, rows), Point3(0, 0, -0.05), top, 0.08, 0.05, _STUMP, _STUMP * 0.8)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode('blood_stump_geom')
    node.addGeom(geom)
    return node


def build_scrap_geom() -> GeomNode:
    """Small faceted shard (octahedron), ~0.22 m."""
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData('scrap', fmt, Geom.UHStatic)
    vw, nw, cw = GeomVertexWriter(vdata, 'vertex'), GeomVertexWriter(vdata, 'normal'), GeomVertexWriter(vdata, 'color')
    tris = GeomTriangles(Geom.UHStatic)
    top, bottom = Point3(0, 0, 0.16), Point3(0, 0, 0.0)
    ring = [Point3(math.cos(a) * 0.09, math.sin(a) * 0.09, 0.07) for a in (0, math.pi / 2, math.pi, 1.5 * math.pi)]
    rows = 0
    for i in range(4):
        a, b = ring[i], ring[(i + 1) % 4]
        for tip in (top, bottom):
            n = (a - tip).cross(b - tip)
            if tip is bottom:
                n = -n
            n.normalize()
            for p in (tip, a, b):
                vw.addData3(p)
                nw.addData3(n)
                cw.addData4(_SCRAP if tip is top else _SCRAP * 0.7)
            if tip is top:
                tris.addVertices(rows, rows + 1, rows + 2)
            else:
                tris.addVertices(rows, rows + 2, rows + 1)
            rows += 3
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode('scrap_geom')
    node.addGeom(geom)
    return node


def _stable_seed(*parts) -> int:
    """Deterministic across runs (Python's str hash is randomised per process)."""
    return zlib.crc32(repr(parts).encode('utf-8'))


# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------
class BloodBranch:
    __slots__ = ('pid', 'pos', 'variant', 'heading', 'smashed', 'regrow_left', 'sap', 'node', 'stump', 'drawing', 'grow',
                 'poisoned', 'eaten_at')

    def __init__(self, pid, pos: Point3, variant: int, heading: float):
        self.pid = pid
        self.pos = pos
        self.variant = variant
        self.heading = heading
        self.smashed = False
        self.regrow_left = 0.0
        self.sap = SAP_MAX
        self.node = None
        self.stump = None
        self.drawing = False
        self.grow = 1.0            # < 1 while a planted seedling grows
        self.poisoned = False      # Pass 47: pale-bloom scraps worked into it - the Red Giant's last meal
        self.eaten_at = None       # Pass 48: flora clock time the Red Giant ate it (a clue)


class Scrap:
    __slots__ = ('pos', 'node', 'age')

    def __init__(self, pos: Point3, node):
        self.pos = pos
        self.node = node
        self.age = 0.0


class FloraField:
    def __init__(self, render: NodePath, field, seed: int, start_hint: Point3):
        self.render = render
        self.field = field
        self.seed = int(seed)
        self.root = render.attachNewNode('flora')
        self.variants = [NodePath(build_branch_geom(self.seed * 31 + i)) for i in range(4)]
        self.stump_proto = NodePath(build_stump_geom())
        self.scrap_proto = NodePath(build_scrap_geom())
        self.branches: dict = {}          # pid -> BloodBranch (every plant ever seen)
        self.active_cells: set = set()
        self.cell_members: dict = {}      # cell -> [pid]
        self._grid: dict = {}             # Pass 49: cell -> branches, for every branch ever grown
        self._indexed: set = set()
        self.poisoned: dict = {}          # Pass 49: pid -> poisoned branch still standing
        self.scraps: list = []
        self.planted: list = []
        self.active: dict = {}            # Pass 44: pid -> branch currently instanced (the per-frame set)
        self.regrowing: dict = {}         # pid -> smashed branch, near or far
        self.time = 0.0
        # Guarantee one plant beside the start so the loop is discoverable at once.
        sx, sy = start_hint.x + SAFE_START_OFFSET[0], start_hint.y + SAFE_START_OFFSET[1]
        self._start_branch = BloodBranch(('start', 0), Point3(sx, sy, field.height(sx, sy)), 0, 30.0)
        self.branches[self._start_branch.pid] = self._start_branch
        self._index(self._start_branch)

    # ----- placement --------------------------------------------------------
    def _cell_plants(self, cx: int, cy: int):
        rng = random.Random(_stable_seed(self.seed, cx, cy, 'blood'))
        pids = []
        if rng.random() < BRANCH_CHANCE:
            count = 1 if rng.random() < 0.7 else 2
            for k in range(count):
                best = None
                for _ in range(6):
                    x = (cx + rng.uniform(0.12, 0.88)) * CELL_SIZE
                    y = (cy + rng.uniform(0.12, 0.88)) * CELL_SIZE
                    slope = math.degrees(math.acos(max(-1.0, min(1.0, self.field.normal(x, y).z))))
                    if hasattr(self.field, 'is_clear') and not self.field.is_clear(x, y):
                        slope = 90.0             # Pass 46: not inside a place
                    if best is None or slope < best[0]:
                        best = (slope, x, y)
                if best[0] > MAX_SLOPE_DEG:
                    continue
                _slope, x, y = best
                pid = (cx, cy, k)
                if pid not in self.branches:
                    self.branches[pid] = BloodBranch(pid, Point3(x, y, self.field.height(x, y)),
                                                     rng.randrange(len(self.variants)), rng.uniform(0, 360))
                self._index(self.branches[pid])
                pids.append(pid)
        return pids

    def update_active(self, focus: Point3):
        fx, fy = math.floor(focus.x / CELL_SIZE), math.floor(focus.y / CELL_SIZE)
        wanted = {(fx + dx, fy + dy) for dx in range(-ACTIVE_RADIUS_CELLS, ACTIVE_RADIUS_CELLS + 1)
                  for dy in range(-ACTIVE_RADIUS_CELLS, ACTIVE_RADIUS_CELLS + 1)}
        for cell in self.active_cells - wanted:
            for pid in self.cell_members.pop(cell, []):
                self._despawn(self.branches[pid])
        for cell in wanted - self.active_cells:
            pids = self._cell_plants(*cell)
            self.cell_members[cell] = pids
            for pid in pids:
                self._spawn(self.branches[pid])
        self.active_cells = wanted
        if self._start_branch.node is None and self._start_branch.stump is None:
            self._spawn(self._start_branch)
        reach = (ACTIVE_RADIUS_CELLS + 0.5) * CELL_SIZE
        for b in self.planted:
            near = math.hypot(b.pos.x - focus.x, b.pos.y - focus.y) <= reach
            if near and b.node is None and b.stump is None:
                self._spawn(b)
            elif not near and (b.node is not None or b.stump is not None):
                self._despawn(b)

    def _index(self, b: BloodBranch):
        if b.pid in self._indexed:
            return
        self._indexed.add(b.pid)
        cell = (math.floor(b.pos.x / CELL_SIZE), math.floor(b.pos.y / CELL_SIZE))
        self._grid.setdefault(cell, []).append(b)

    def branches_near(self, p: Point3, radius: float):
        """Every known branch within about `radius` of p (cell index, not a scan of all)."""
        r = int(math.ceil(radius / CELL_SIZE))
        fx, fy = math.floor(p.x / CELL_SIZE), math.floor(p.y / CELL_SIZE)
        for cx in range(fx - r, fx + r + 1):
            for cy in range(fy - r, fy + r + 1):
                yield from self._grid.get((cx, cy), ())

    def set_poisoned(self, b: BloodBranch, poisoned: bool = True):
        b.poisoned = poisoned
        if poisoned:
            self.poisoned[b.pid] = b
            if b.node is not None:
                b.node.setColorScale(*POISON_TINT)
        else:
            self.poisoned.pop(b.pid, None)

    def plant(self, pos: Point3, heading: float = 0.0) -> BloodBranch:
        """Grow a new branch from a seed (Pass 43)."""
        pid = ('planted', len(self.planted))
        b = BloodBranch(pid, Point3(pos), len(self.planted) % len(self.variants), heading)
        b.grow = 0.15
        b.sap = 0.0
        self.branches[pid] = b
        self.planted.append(b)
        self._index(b)
        self._spawn(b)
        return b

    def _spawn(self, b: BloodBranch):
        self._despawn(b)
        if b.smashed:
            b.stump = self.root.attachNewNode('stump')
            self.stump_proto.instanceTo(b.stump)
            b.stump.setPos(b.pos)
            b.stump.setH(b.heading)
        else:
            b.node = self.root.attachNewNode(f'blood_branch_{b.pid}')
            self.variants[b.variant].instanceTo(b.node)
            b.node.setPos(b.pos)
            b.node.setH(b.heading)
            if b.grow < 1.0:
                b.node.setScale(b.grow)
            if b.poisoned:
                b.node.setColorScale(*POISON_TINT)       # red veins gone the colour of bone
        self.active[b.pid] = b

    def _despawn(self, b: BloodBranch):
        for attr in ('node', 'stump'):
            np_ = getattr(b, attr)
            if np_ is not None:
                np_.removeNode()
                setattr(b, attr, None)
        self.active.pop(b.pid, None)

    def live_branches(self):
        return list(self.active.values())

    # ----- queries ----------------------------------------------------------
    def nearest_intact(self, p: Point3, radius: float, healthy_only: bool = False):
        best, best_d = None, radius
        for b in self.active.values():
            if b.smashed or b.node is None or b.grow < 1.0 or (healthy_only and b.poisoned):
                continue
            d = math.hypot(b.pos.x - p.x, b.pos.y - p.y)
            if d <= best_d:
                best, best_d = b, d
        return best

    # ----- actions ----------------------------------------------------------
    def heal_amount(self, p: Point3, radius: float, rate: float, dt: float, wanted: float) -> float:
        """Draw sap from the nearest intact branch in range; returns health gained."""
        b = self.nearest_intact(p, radius, healthy_only=True)       # Pass 47: poisoned sap does not heal
        if b is None or wanted <= 0.0 or b.sap <= 0.0:
            return 0.0
        gain = min(rate * dt, wanted, b.sap)
        b.sap -= gain
        b.drawing = True
        return gain

    def smash(self, b: BloodBranch, crumbs: int = SCRAPS_PER_BRANCH) -> int:
        if b is None or b.smashed:
            return 0
        b.smashed = True
        self.set_poisoned(b, False)
        b.regrow_left = REGROW_SECONDS
        b.sap = 0.0
        self.regrowing[b.pid] = b
        if b.pid in self.active:            # Pass 49: a branch eaten out of sight stays out of the frame loop
            self._spawn(b)
        rng = random.Random(_stable_seed(self.seed, b.pid, 'scrap', int(self.time)))
        for i in range(crumbs):
            a = 2 * math.pi * (i + rng.random() * 0.6) / crumbs
            r = rng.uniform(0.6, 1.4)
            x, y = b.pos.x + math.cos(a) * r, b.pos.y + math.sin(a) * r
            pos = Point3(x, y, self.field.height(x, y) + 0.02)
            node = self.root.attachNewNode('scrap')
            self.scrap_proto.instanceTo(node)
            node.setPos(pos)
            node.setH(rng.uniform(0, 360))
            self.scraps.append(Scrap(pos, node))
        while len(self.scraps) > MAX_SCRAPS:
            self.scraps.pop(0).node.removeNode()
        return crumbs

    def collect_scraps(self, p: Point3, radius: float, capacity_left: int) -> int:
        if capacity_left <= 0 or not self.scraps:
            return 0
        taken = 0
        keep = []
        for s in self.scraps:
            if taken < capacity_left and math.hypot(s.pos.x - p.x, s.pos.y - p.y) <= radius:
                s.node.removeNode()
                taken += 1
            else:
                keep.append(s)
        self.scraps = keep
        return taken

    # ----- per frame --------------------------------------------------------
    def update(self, dt: float):
        """Pass 44: only the instanced branches, the regrowing ones and the seedlings are
        touched each frame - not every plant ever streamed in."""
        self.time += dt
        for pid, b in list(self.regrowing.items()):
            b.regrow_left -= dt
            if b.regrow_left <= 0.0:
                b.smashed = False
                b.eaten_at = None
                b.sap = SAP_MAX * 0.5
                del self.regrowing[pid]
                if b.stump is not None:
                    self._spawn(b)
        for b in self.planted:
            if b.grow < 1.0:
                b.grow = min(1.0, b.grow + dt / PLANT_GROW_SECONDS)
                if b.node is not None:
                    b.node.setScale(b.grow)
                if b.grow >= 1.0:
                    b.sap = SAP_MAX * 0.5
        glow_phase = 0.5 + 0.5 * math.sin(self.time * 6.0)
        for b in self.active.values():
            if b.smashed or b.grow < 1.0:
                continue
            if not b.drawing:
                b.sap = min(SAP_MAX, b.sap + SAP_REFILL_RATE * dt)
            if b.node is not None:
                # Gentle breathing sway; a healing branch pulses brighter.
                b.node.setP(math.sin(self.time * 0.9 + b.pos.x * 0.13) * 2.2)
                if b.poisoned:
                    b.node.setColorScale(*POISON_TINT)
                else:
                    glow = 1.0 + (0.35 * glow_phase if b.drawing else 0.0)
                    fill = 0.55 + 0.45 * (b.sap / SAP_MAX)
                    b.node.setColorScale(glow * fill + (1 - fill) * 0.55, fill * glow, fill * glow, 1.0)
            b.drawing = False
        keep = []
        for sc in self.scraps:
            sc.age += dt
            if sc.age >= SCRAP_LIFETIME:
                sc.node.removeNode()
                continue
            sc.node.setH(sc.node.getH() + 40.0 * dt)
            keep.append(sc)
        self.scraps = keep
