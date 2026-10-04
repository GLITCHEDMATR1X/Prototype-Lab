"""Pass 39 world content: finds, sea-shell shelters and far landmarks.

All placement is deterministic per world seed (crc32-based, like flora.py), so the same
things are always in the same places.  State (dug, patched, moved, visited) is kept per
object id for the whole session; only objects near the focus are instanced.
"""
from __future__ import annotations

import math
import random

from panda3d.core import Point3, Vec3

import desert_geom as geom
from flora import _stable_seed

# ---------------------------------------------------------------- finds
FIND_CELL = 110.0                  # Pass 42: sparser, so each find is a small event
FIND_CHANCE = 0.55
ACTIVE_RADIUS = 280.0
MAX_SLOPE_DEG = 9.0                # things rest on level ground, not on dune faces
FIND_KINDS = (('pod', 26), ('gourd', 18), ('fibre', 18), ('resin', 12), ('shard', 14), ('nothing', 12))
FIND_YIELD = {'pod': ('pod', 2), 'gourd': ('gourd', 1), 'fibre': ('fibre', 2), 'resin': ('resin', 1),
              'shard': ('shard', 2), 'nothing': (None, 0)}
FIND_NAMES = {'pod': 'moss pods', 'gourd': 'a water gourd', 'fibre': 'dune fibre', 'resin': 'amber resin',
              'shard': 'shell shards', 'nothing': 'only sand'}
START_FIND_OFFSET = (6.0, 8.0)

# ---------------------------------------------------------------- shells
SHELL_CELL = 150.0
SHELL_CHANCE = 0.42
SHELL_CRACKED_CHANCE = 0.55
START_SHELL_OFFSET = (10.0, -4.0)
SHELL_FLIP_TIME = 0.9
# Pass 55: walk-in shells
SHELL_PREPARE_RADIUS = 700.0       # shell sites are chosen (ground levelled) beyond any built ground
SHELL_LEVEL_PAD = 0.6              # the sand under a shell is levelled out to its rim + this...
SHELL_LEVEL_BLEND = 7.0            # ...then blends back into the dunes over this
BODY_RADIUS = 0.32                 # how close your body comes to a shell's wall
INSIDE_Q = 0.80                    # you count as gone in once within 80% of the shell's radius...
OUTSIDE_Q = 1.0                    # ...and as out again only past its rim (standing against a wall is inside)
# Pass 56: the walls follow the real shape. You walk through the mouth where its arch clears
# your head, and inside you walk wherever the roof does (not up into the low edge of the dome).
HEAD_CLEAR = 1.90                  # m: the human is 1.83 m
MOUTH_WALK_DEG = geom.mouth_walkable_deg()
FUNNEL_DEG = 14.0                  # Pass 57: brushing the doorframe this close to the opening...
FUNNEL_RATE = 0.9                  # ...slides you into the doorway (this much of each step)
ROOM_Q = math.sqrt(1.0 - ((HEAD_CLEAR + geom.SHELL_THICK) / geom.SHELL_H) ** 2)   # ~0.66 of the radius
MOUTH_REACH = 2.6                  # E steps you in from this close to the mouth
GIANT_FOOT_PAD = 1.5               # the giants step around shells (their feet are this wide)

# ---------------------------------------------------------------- landmarks
LANDMARK_COUNT = 8
LANDMARK_RINGS = (330.0, 560.0, 800.0, 1080.0)   # metres from the start: a long journey out
LANDMARK_GHOST = 0.07             # Pass 45: past the fog line a landmark is only a 7% ghost
LANDMARK_KINDS = ('ribs', 'spire', 'bead')
LANDMARK_LORE = (
    "Ribs of something that once walked here. It lay down facing the same way you are.",
    "A spire twisted like a shell. The wind hums through it in two notes.",
    "A glass bead the size of a hill. Your reflection is very small inside it.",
    "Bones, scoured white. Tiny footprints circle them — older than yours.",
    "The spire is warm on the shaded side. Something lived in its hollows.",
    "Inside the bead the sand is cool and dry. Someone slept here once.",
    "The ribs are hung with dried fibre, knotted by small hands.",
    "The last marker. From here, every other one is visible on the horizon.",
)


def _weighted(rng: random.Random, table):
    total = sum(w for _, w in table)
    x = rng.uniform(0, total)
    for name, w in table:
        x -= w
        if x <= 0:
            return name
    return table[-1][0]


def slope_deg(field, x: float, y: float) -> float:
    return math.degrees(math.acos(max(-1.0, min(1.0, field.normal(x, y).z))))


def level_spot(field, rng: random.Random, cx: int, cy: int, cell: float, tries: int = 7,
               max_slope: float = MAX_SLOPE_DEG):
    """Flattest of a few random spots in a cell, or None when the whole cell is dune face."""
    best = None
    clear = getattr(field, 'is_clear', None)
    for _ in range(tries):
        x = (cx + rng.uniform(0.12, 0.88)) * cell
        y = (cy + rng.uniform(0.12, 0.88)) * cell
        s = slope_deg(field, x, y)
        if clear is not None and not clear(x, y):
            s = 90.0                             # Pass 46: inside a place - never here
        if best is None or s < best[0]:
            best = (s, x, y)
    return None if best[0] > max_slope else (best[1], best[2])


def resting_z(field, x: float, y: float, radius: float) -> float:
    """Lowest ground under a footprint, so no edge floats above the sand."""
    zs = [field.height(x, y)]
    for k in range(8):
        a = k * math.pi / 4
        zs.append(field.height(x + math.cos(a) * radius, y + math.sin(a) * radius))
    return min(zs)


def _flat(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


class Find:
    __slots__ = ('pid', 'pos', 'kind', 'dug', 'sensed', 'node', 'reveal', 'reveal_t')

    def __init__(self, pid, pos: Point3, kind: str):
        self.pid, self.pos, self.kind = pid, pos, kind
        self.dug = False
        self.sensed = False
        self.node = self.reveal = None
        self.reveal_t = 0.0


class FindField:
    def __init__(self, render, field, seed: int, start_hint: Point3, shadow_mask):
        self.render, self.field, self.seed = render, field, int(seed)
        self.root = render.attachNewNode('finds')
        self.shadow_mask = shadow_mask
        self.mounds = [geom.build_mound(self.seed * 7 + i) for i in range(3)]
        self.reveals = {k: geom.build_reveal(k) for k, _ in FIND_KINDS}
        self.finds: dict = {}
        self.cells: set = set()
        self.dug_pids: set = set()
        self.active: dict = {}            # Pass 44: pid -> find currently instanced
        self.revealing: list = []
        self.time = 0.0
        sx, sy = start_hint.x + START_FIND_OFFSET[0], start_hint.y + START_FIND_OFFSET[1]
        self.finds[('start', 0)] = Find(('start', 0), Point3(sx, sy, field.height(sx, sy)), 'gourd')

    def _cell(self, cx, cy):
        rng = random.Random(_stable_seed(self.seed, cx, cy, 'find'))
        if rng.random() >= FIND_CHANCE:
            return
        spot = level_spot(self.field, rng, cx, cy, FIND_CELL)
        if spot is None:
            return
        x, y = spot
        pid = (cx, cy)
        if pid not in self.finds:
            f = Find(pid, Point3(x, y, resting_z(self.field, x, y, 0.7)), _weighted(rng, FIND_KINDS))
            f.dug = repr(pid) in self.dug_pids          # restored from a saved journey
            self.finds[pid] = f

    def update_active(self, focus: Point3):
        r = int(math.ceil(ACTIVE_RADIUS / FIND_CELL))
        fx, fy = math.floor(focus.x / FIND_CELL), math.floor(focus.y / FIND_CELL)
        for cx in range(fx - r, fx + r + 1):
            for cy in range(fy - r, fy + r + 1):
                if (cx, cy) not in self.cells:
                    self.cells.add((cx, cy))
                    self._cell(cx, cy)
        # Pass 44: only look at finds in nearby cells (plus the ones already shown), not every
        # find ever generated - that list grows with every kilometre travelled.
        nearby = [self.finds[c] for c in ((cx, cy) for cx in range(fx - r - 1, fx + r + 2)
                                          for cy in range(fy - r - 1, fy + r + 2)) if c in self.finds]
        start = self.finds.get(('start', 0))
        if start is not None:
            nearby.append(start)
        for f in set(nearby) | set(self.active.values()):
            near = _flat(f.pos, focus) <= ACTIVE_RADIUS
            if near and not f.dug and f.node is None:
                f.node = self.root.attachNewNode('find')
                self.mounds[_stable_seed(f.pid) % len(self.mounds)].instanceTo(f.node)
                f.node.setPos(f.pos)
                f.node.setH((f.pos.x * 37.0) % 360.0)
                self.active[f.pid] = f
            elif (not near or f.dug) and f.node is not None:
                self._clear(f)

    def _clear(self, f: Find):
        if f.node is not None:
            f.node.removeNode()
            f.node = None
        self.active.pop(f.pid, None)

    def nearest(self, p: Point3, radius: float):
        best, best_d = None, radius
        for f in self.active.values():
            if f.dug or f.node is None:
                continue
            d = _flat(f.pos, p)
            if d <= best_d:
                best, best_d = f, d
        return best

    def sense(self, origin: Point3, radius: float):
        """Mark un-sensed finds within radius as sensed. Returns them, nearest first."""
        found = []
        for f in self.active.values():
            if f.dug or f.sensed or f.node is None:
                continue
            d = _flat(f.pos, origin)
            if d <= radius:
                found.append((d, f))
        found.sort(key=lambda t: t[0])
        for _, f in found:
            f.sensed = True
        return [f for _, f in found]

    def dig(self, f: Find):
        if f.dug:
            return None, 0
        f.dug = True
        self._clear(f)
        f.reveal = self.root.attachNewNode('reveal')
        self.reveals[f.kind].instanceTo(f.reveal)
        f.reveal.setPos(f.pos)
        f.reveal_t = 2.5
        self.revealing.append(f)
        return FIND_YIELD[f.kind]

    def update(self, dt: float, eye: Point3 | None = None):
        self.time += dt
        keep = []
        for f in self.revealing:
            if f.reveal is None:
                continue
            f.reveal_t -= dt
            f.reveal.setZ(f.pos.z + 0.25 + 0.15 * math.sin(self.time * 3.0))
            f.reveal.setH(f.reveal.getH() + 60 * dt)
            if f.reveal_t <= 0:
                f.reveal.removeNode()
                f.reveal = None
            else:
                keep.append(f)
        self.revealing = keep


# ====================================================================== shells
class Shell:
    __slots__ = ('pid', 'pos', 'heading', 'state', 'node', 'held', 'occupied', 'shake', 'flip_t', 'shown_state')

    def __init__(self, pid, pos: Point3, heading: float, state: str):
        self.pid, self.pos, self.heading, self.state = pid, pos, heading, state
        self.node = None
        self.held = False
        self.occupied = False
        self.shake = 0.0          # 0..1 while the red giant heaves at it
        self.flip_t = 0.0         # > 0 while the overturn animation plays
        self.shown_state = None

    def entrance_point(self) -> Point3:
        h = math.radians(self.heading)
        # entrance faces local +Y
        return Point3(self.pos.x - math.sin(h) * geom.SHELL_RY * 1.2, self.pos.y + math.cos(h) * geom.SHELL_RY * 1.2,
                      self.pos.z)


class ShellField:
    def __init__(self, render, field, seed: int, start_hint: Point3):
        self.render, self.field, self.seed = render, field, int(seed)
        self.root = render.attachNewNode('shells')
        self.protos = {'intact': geom.build_shell(False, self.seed), 'cracked': geom.build_shell(True, self.seed + 1)}
        self.shells: dict = {}
        self.visible: dict = {}           # Pass 44: pid -> shell currently instanced
        self.cells: set = set()
        self.changed: list = []           # Pass 55: (x, y, radius) ground levelled, for the terrain to rebuild
        self._levelled: set = set()       # Pass 57: spots already levelled (a shell loaded or set down twice)
        sx, sy = start_hint.x + START_SHELL_OFFSET[0], start_hint.y + START_SHELL_OFFSET[1]
        self._level(sx, sy)
        self.shells[('start', 0)] = Shell(('start', 0), Point3(sx, sy, resting_z(field, sx, sy, geom.SHELL_RX)),
                                          200.0, 'cracked')

    def _level(self, x: float, y: float):
        """Pass 55: flatten the sand under a shell, so its floor is level and no side is buried,
        and keep other things (finds, branches) from being placed inside it."""
        key = (round(x, 1), round(y, 1))
        if key in self._levelled:
            return
        self._levelled.add(key)
        inner = geom.SHELL_RX + SHELL_LEVEL_PAD
        outer = inner + SHELL_LEVEL_BLEND
        if hasattr(self.field, 'add_flat_zone'):
            self.field.add_flat_zone(x, y, inner, outer, on_current=True)
            self.changed.append((x, y, outer))
        if hasattr(self.field, 'add_clear_zone'):
            self.field.add_clear_zone(x, y, inner + 1.0)

    def _cell(self, cx, cy):
        rng = random.Random(_stable_seed(self.seed, cx, cy, 'shell'))
        if rng.random() >= SHELL_CHANCE:
            return
        spot = level_spot(self.field, rng, cx, cy, SHELL_CELL)
        if spot is None:
            return
        x, y = spot
        pid = (cx, cy)
        if pid not in self.shells:
            state = 'cracked' if rng.random() < SHELL_CRACKED_CHANCE else 'intact'
            self._level(x, y)
            self.shells[pid] = Shell(pid, Point3(x, y, resting_z(self.field, x, y, geom.SHELL_RX)),
                                     rng.uniform(0, 360), state)

    def update_active(self, focus: Point3):
        # Pass 55: sites are chosen out to SHELL_PREPARE_RADIUS (beyond the built ground), so the
        # levelled sand is part of the terrain from the start; only those within ACTIVE_RADIUS show
        r = int(math.ceil(SHELL_PREPARE_RADIUS / SHELL_CELL))
        fx, fy = math.floor(focus.x / SHELL_CELL), math.floor(focus.y / SHELL_CELL)
        for cx in range(fx - r, fx + r + 1):
            for cy in range(fy - r, fy + r + 1):
                if (cx, cy) not in self.cells:
                    self.cells.add((cx, cy))
                    self._cell(cx, cy)
        for s in self.shells.values():
            near = s.held or s.occupied or _flat(s.pos, focus) <= ACTIVE_RADIUS
            if near:
                self._show(s)
            elif s.node is not None:
                s.node.removeNode()
                s.node = None
                s.shown_state = None
                self.visible.pop(s.pid, None)

    def _show(self, s: Shell):
        visual = 'intact' if s.state in ('intact', 'flipped') else 'cracked'
        if s.node is None or s.shown_state != visual:
            if s.node is not None:
                s.node.removeNode()
            s.node = self.root.attachNewNode(f'shell_{s.pid}')
            self.protos[visual].instanceTo(s.node)
            s.shown_state = visual
            self.visible[s.pid] = s
        self._pose(s)

    def _pose(self, s: Shell):
        if s.node is None or s.held:
            return
        s.node.setPos(s.pos)
        s.node.setHpr(s.heading, 0, 0)
        if s.state == 'flipped' and s.flip_t <= 0.0:
            s.node.setR(180.0)
            s.node.setZ(s.pos.z + geom.SHELL_H * 0.92)

    def set_state(self, s: Shell, state: str):
        s.state = state
        if s.node is not None:
            self._show(s)

    def start_flip(self, s: Shell):
        s.state = 'flipped'
        s.flip_t = SHELL_FLIP_TIME
        s.shake = 0.0
        s.occupied = False

    def settle(self, s: Shell):
        """Pass 57: level the sand where a shell lies and rest it on that. Used for shells set
        down by a giant and for every shell a saved journey restores (their ground was never
        levelled after a load before)."""
        self._level(s.pos.x, s.pos.y)
        s.pos = Point3(s.pos.x, s.pos.y, resting_z(self.field, s.pos.x, s.pos.y, geom.SHELL_RX))
        if s.node is not None and not s.held:
            self._pose(s)

    def place(self, s: Shell, pos: Point3, heading: float):
        s.held = False
        s.pos = Point3(pos.x, pos.y, pos.z)
        s.heading = heading
        if s.state == 'flipped':
            s.state = 'intact'      # a giant sets it down the right way up
        self.settle(s)              # Pass 57: on level sand, wherever it is set down
        self._show(s)

    def nearest(self, p: Point3, radius: float, states=None):
        best, best_d = None, radius
        for s in self.visible.values():
            if s.node is None or s.held:
                continue
            if states is not None and s.state not in states:
                continue
            d = _flat(s.pos, p)
            if d <= best_d:
                best, best_d = s, d
        return best

    # ------------------------------------------------------------ Pass 55: walking in and out
    @staticmethod
    def _local(s, p: Point3):
        """p in the shell's own frame: (x, y), with the mouth toward +y."""
        h = math.radians(s.heading)
        dx, dy = p.x - s.pos.x, p.y - s.pos.y
        return dx * math.cos(h) + dy * math.sin(h), -dx * math.sin(h) + dy * math.cos(h)

    @staticmethod
    def _q(lx: float, ly: float, pad: float = 0.0) -> float:
        """How far out a point is, as a fraction of the shell's rim grown by pad (1.0 = on it)."""
        return math.hypot(lx / (geom.SHELL_RX + pad), ly / (geom.SHELL_RY + pad))

    @staticmethod
    def _in_mouth(lx: float, ly: float) -> bool:
        if ly <= 0.0:
            return False
        ang = math.degrees(math.atan2(ly, lx))
        return abs(ang - 90.0) <= MOUTH_WALK_DEG

    def walkable(self, s) -> bool:
        """A shell standing still on the ground (not carried, not mid-flip)."""
        return s.node is not None and not s.held and s.flip_t <= 0.0

    def inside(self, p: Point3, states=('intact', 'cracked'), limit: float = INSIDE_Q):
        """The shell p stands inside (within `limit` of its rim radius), or None."""
        for s in self.visible.values():
            if not self.walkable(s) or s.state not in states:
                continue
            if abs(s.pos.x - p.x) > geom.SHELL_RX + 1.0 or abs(s.pos.y - p.y) > geom.SHELL_RX + 1.0:
                continue
            if self._q(*self._local(s, p)) <= limit:
                return s
        return None

    def at_mouth(self, p: Point3, states=('intact',)):
        """The shell whose mouth p is standing at (outside it), or None."""
        best, best_d = None, MOUTH_REACH
        for s in self.visible.values():
            if not self.walkable(s) or s.state not in states:
                continue
            d = _flat(s.entrance_point(), p)
            if d <= best_d and self._q(*self._local(s, p)) > INSIDE_Q:
                best, best_d = s, d
        return best

    def collide(self, old: Point3, new: Point3) -> Point3:
        """Keep a walker from passing through a shell's wall; only the mouth lets you in or out.
        Inside, you walk where you can stand upright (Pass 56: not into the low rim of the dome,
        where your head would come through the roof); from outside you stop at the outer face.
        A shell lying upside down (the red one flipped it) is solid. Returns the corrected point."""
        for s in self.visible.values():
            if not self.walkable(s):
                continue
            reach = geom.SHELL_RX + 1.5
            if abs(s.pos.x - new.x) > reach or abs(s.pos.y - new.y) > reach:
                continue
            nx, ny = self._local(s, new)
            if s.state == 'flipped':
                if self._q(nx, ny, BODY_RADIUS) < 1.0:
                    new = self._push(s, nx, ny, BODY_RADIUS, new)
                continue
            if self._in_mouth(nx, ny):
                continue                                         # walking through the mouth
            ox, oy = self._local(s, old)
            if self._in_mouth(ox, oy) and self._q(nx, ny) > ROOM_Q and self._q(nx, ny, BODY_RADIUS) < 1.0:
                # Pass 57: in the doorway its sides are straight walls: slide along them (keep how
                # far in you are, stay inside the opening) rather than being pushed back out
                edge = math.radians(90.0 + math.copysign(MOUTH_WALK_DEG - 0.05,
                                                         math.degrees(math.atan2(ny, nx)) - 90.0))
                r = math.hypot(nx, ny)
                new = self._to_world(s, math.cos(edge) * r, math.sin(edge) * r, new)
                continue
            step = math.hypot(new.x - old.x, new.y - old.y)
            if self._q(*self._local(s, old)) < 0.5 * (ROOM_Q + 1.0):
                if self._q(nx, ny) > ROOM_Q:                      # inside: as far as the roof allows
                    new = self._funnel(s, nx, ny, step, lambda x, y: self._to_q(s, x, y, ROOM_Q, new)) \
                        or self._to_q(s, nx, ny, ROOM_Q, new)
            elif self._q(nx, ny, BODY_RADIUS) < 1.0:             # outside: the wall's outer face
                new = self._funnel(s, nx, ny, step, lambda x, y: self._push(s, x, y, BODY_RADIUS, new)) \
                    or self._push(s, nx, ny, BODY_RADIUS, new)
        return new

    @staticmethod
    def _funnel(s, lx: float, ly: float, step: float, onto):
        """Pass 57: stopped by the doorframe close to the opening, you slide along it into the
        doorway instead of sticking (like a person turning their shoulder). None when too far off."""
        if ly <= 0.0 or step <= 1e-6:
            return None
        ang = math.degrees(math.atan2(ly, lx))
        off = ang - 90.0
        if abs(off) > MOUTH_WALK_DEG + FUNNEL_DEG:
            return None
        r = math.hypot(lx, ly)
        turn = min(abs(off) - (MOUTH_WALK_DEG - 1.0), math.degrees(FUNNEL_RATE * step / max(r, 0.5)))
        if turn <= 0.0:
            return None
        a2 = math.radians(ang - math.copysign(turn, off))
        return onto(math.cos(a2) * r, math.sin(a2) * r)

    @staticmethod
    def _to_world(s, lx: float, ly: float, new: Point3) -> Point3:
        h = math.radians(s.heading)
        return Point3(s.pos.x + lx * math.cos(h) - ly * math.sin(h),
                      s.pos.y + lx * math.sin(h) + ly * math.cos(h), new.z)

    @staticmethod
    def _to_q(s, lx: float, ly: float, q_to: float, new: Point3) -> Point3:
        """Move a point along its ray from the shell's centre to q_to of the rim."""
        q = ShellField._q(lx, ly)
        if q < 1e-6:
            return new
        k = q_to / q
        lx, ly = lx * k, ly * k
        h = math.radians(s.heading)
        return Point3(s.pos.x + lx * math.cos(h) - ly * math.sin(h),
                      s.pos.y + lx * math.sin(h) + ly * math.cos(h), new.z)

    @staticmethod
    def _push(s, lx: float, ly: float, pad: float, new: Point3) -> Point3:
        """Move a point along its ray from the shell's centre onto the (padded) rim."""
        q = ShellField._q(lx, ly, pad)
        if q < 1e-6:
            lx, ly, q = 0.0, -1.0, 1.0 / (geom.SHELL_RY + pad)
        lx, ly = lx / q, ly / q
        h = math.radians(s.heading)
        return Point3(s.pos.x + lx * math.cos(h) - ly * math.sin(h),
                      s.pos.y + lx * math.sin(h) + ly * math.cos(h), new.z)

    def keep_out(self, old: Point3, new: Point3, pad: float = GIANT_FOOT_PAD) -> Point3:
        """Pass 55: a giant steps around shells rather than through them. Only a step that goes
        further in is stopped (a shell set down on top of a giant never traps it)."""
        for s in self.visible.values():
            if not self.walkable(s):
                continue
            reach = geom.SHELL_RX + pad + 1.0
            if abs(s.pos.x - new.x) > reach or abs(s.pos.y - new.y) > reach:
                continue
            nx, ny = self._local(s, new)
            qn = self._q(nx, ny, pad)
            ox, oy = self._local(s, old)
            if qn < 1.0 and qn < self._q(ox, oy, pad):
                # walking straight at the middle there is nothing to slide along: lean to one side
                step = math.hypot(nx - ox, ny - oy)
                r = math.hypot(ox, oy) or 1.0
                tangential = abs((nx - ox) * -oy / r + (ny - oy) * ox / r)
                if step > 1e-6 and tangential < 0.3 * step:
                    nx, ny = nx + oy / r * 0.5 * step, ny - ox / r * 0.5 * step
                new = self._push(s, nx, ny, pad, new)
        return new

    def clear_point(self, p: Point3, toward: Point3, pad: float = GIANT_FOOT_PAD) -> Point3:
        """A spot to walk to: p, or if p is under (or right beside) a shell, the nearest spot
        just clear of it - on p's own side, so Indigo walks round to you rather than stopping on
        the far side (Pass 57). Only a spot near the very middle uses the side facing `toward`."""
        for s in self.visible.values():
            if not self.walkable(s):
                continue
            lx, ly = self._local(s, p)
            if self._q(lx, ly, pad) < 1.0:
                if self._q(lx, ly) < 0.35:
                    lx, ly = self._local(s, toward)
                    if math.hypot(lx, ly) < 1e-3:
                        lx, ly = 0.0, 1.0
                return self._push(s, lx, ly, pad, Point3(p))
        return p

    @staticmethod
    def inner_spot(s) -> Point3:
        """Where you stand after stepping in: a little back from the middle."""
        h = math.radians(s.heading)
        d = -geom.SHELL_RY * 0.2
        return Point3(s.pos.x - math.sin(h) * d, s.pos.y + math.cos(h) * d, s.pos.z)

    def shade_circles(self, offset: Vec3):
        out = []
        for s in self.visible.values():
            if s.node is None or s.held:
                continue
            out.append((s.pos.x + offset.x * geom.SHELL_H * 0.5, s.pos.y + offset.y * geom.SHELL_H * 0.5,
                        geom.SHELL_RX * 0.95))
        return out

    def update(self, dt: float, time: float):
        for s in self.visible.values():
            if s.node is None or s.held:
                continue
            if s.flip_t > 0.0:
                s.flip_t = max(0.0, s.flip_t - dt)
                k = 1.0 - s.flip_t / SHELL_FLIP_TIME
                s.node.setPos(s.pos.x, s.pos.y, s.pos.z + math.sin(k * math.pi) * 2.0 + geom.SHELL_H * 0.92 * k)
                s.node.setR(180.0 * k)
            elif s.shake > 0.0:
                s.node.setR(math.sin(time * 23.0) * 6.0 * s.shake)
                s.node.setP(math.sin(time * 17.0) * 3.0 * s.shake)
            elif s.state != 'flipped' and (s.node.getR() != 0.0 or s.node.getP() != 0.0):
                s.node.setHpr(s.heading, 0, 0)


# =================================================================== landmarks
def landmark_sites(seed: int, start_x: float, start_y: float):
    """Deterministic landmark layout (idx, x, y, kind, heading).

    Needed before the terrain is built, so the ground under each landmark can be levelled
    (TerrainField.add_flat_zone): they no longer jut out of the side of a dune.
    """
    rng = random.Random(_stable_seed(int(seed), 'landmarks'))
    sites = []
    for i in range(LANDMARK_COUNT):
        a = 2 * math.pi * i / LANDMARK_COUNT + rng.uniform(-0.3, 0.3)
        d = LANDMARK_RINGS[i % len(LANDMARK_RINGS)] + rng.uniform(-40, 40)
        kind = LANDMARK_KINDS[i % len(LANDMARK_KINDS)]
        sites.append((i, start_x + math.cos(a) * d, start_y + math.sin(a) * d, kind, rng.uniform(0, 360)))
    return sites


CHAPTER_SIZE = 5
CHAPTER_FIRST_RING = 1300.0
CHAPTER_RING_STEP = 650.0
_LORE_WHAT = (
    "A {kind} older than the dunes around it.",
    "Another {kind}, leaning into the wind.",
    "The {kind} is scored with long, patient marks.",
    "Half the {kind} is buried; the other half watches the horizon.",
    "Sand pours slowly through the {kind}, like a clock.",
    "Someone stacked small stones at the foot of the {kind}.",
    "The {kind} hums when Nyx leans close.",
    "Shade pools under the {kind} like water.",
)
_LORE_DETAIL = (
    "Nyx stays a long time, very still.",
    "There are small handprints, worn almost smooth.",
    "Far off, something answers the wind in two notes.",
    "Nyx touches it gently, as if it remembers.",
    "The air is cooler here, and quiet.",
    "You feel watched, then you feel welcome.",
    "A shell has been placed here with care.",
    "The next shape is already faint on the horizon.",
)
_KIND_WORDS = {'ribs': 'ribcage', 'spire': 'spire', 'bead': 'glass bead'}


def chapter_sites(seed: int, start_x: float, start_y: float, chapter: int, first_idx: int):
    """Landmarks for trail chapter >= 2: a wider ring each time, so the journey never ends."""
    rng = random.Random(_stable_seed(int(seed), 'chapter', chapter))
    base = CHAPTER_FIRST_RING + (chapter - 2) * CHAPTER_RING_STEP
    offsets = [0.0, 120.0, 240.0, 360.0, 480.0]
    rng.shuffle(offsets)
    a0 = rng.uniform(0, 2 * math.pi)
    sites = []
    for k in range(CHAPTER_SIZE):
        a = a0 + 2 * math.pi * k / CHAPTER_SIZE + rng.uniform(-0.35, 0.35)
        d = base + offsets[k] + rng.uniform(-50, 50)
        kind = LANDMARK_KINDS[(first_idx + k) % len(LANDMARK_KINDS)]
        sites.append((first_idx + k, start_x + math.cos(a) * d, start_y + math.sin(a) * d, kind, rng.uniform(0, 360)))
    return sites


def chapter_lore(seed: int, idx: int, kind: str) -> str:
    rng = random.Random(_stable_seed(int(seed), 'lore', idx))
    return rng.choice(_LORE_WHAT).format(kind=_KIND_WORDS[kind]) + ' ' + rng.choice(_LORE_DETAIL)


def landmark_flat_zones(sites):
    """(x, y, inner, outer) levelling discs for TerrainField."""
    out = []
    for _i, x, y, kind, _h in sites:
        r = geom.LANDMARK_SHAPES[kind][0]
        out.append((x, y, r + 8.0, r + 40.0))
    return out


class Landmark:
    __slots__ = ('idx', 'pos', 'kind', 'heading', 'revealed', 'visited', 'links', 'node', 'lore')

    def __init__(self, idx, pos, kind, heading, lore):
        self.idx, self.pos, self.kind, self.heading, self.lore = idx, pos, kind, heading, lore
        self.revealed = False
        self.visited = False
        self.links = []
        self.node = None


class LandmarkField:
    """A handful of far-off landmarks, standing on levelled ground.

    Pass 42: no glowing beacons.  Pass 45: landmarks share the world's fog; beyond it only a
    faint ghost of their shape remains in the haze — you find them by looking, and Indigo
    turns toward the ones it senses.  Visiting one lets Indigo
    sense the landmarks linked to it: a non-linear trail you can follow in any order.
    """

    def __init__(self, render, field, seed: int, start: Point3, shadow_mask):
        self.render, self.field, self.seed = render, field, int(seed)
        self.root = render.attachNewNode('landmarks')
        # Pass 45: landmarks sit in the same fog as everything else (the player asked for the
        # haze to blanket them); only a faint ghost remains past the fog line.
        self.root.setShaderInput('fog_floor', LANDMARK_GHOST)
        self.shadow_mask = shadow_mask
        self.items: list[Landmark] = []
        lore = list(LANDMARK_LORE)
        for i, x, y, kind, heading in landmark_sites(seed, start.x, start.y):
            self.items.append(Landmark(i, Point3(x, y, field.height(x, y)), kind, heading, lore[i]))
        self.start = Point3(start)
        self.chapter = 1
        self._link_and_build(self.items)
        for lm in sorted(self.items, key=lambda o: _flat(o.pos, start))[:2]:
            self.reveal(lm)

    def _link_and_build(self, new_items):
        for lm in new_items:
            others = sorted((o for o in self.items if o is not lm), key=lambda o: _flat(o.pos, lm.pos))
            lm.links = [o.idx for o in others[:2] if not o.visited] or [o.idx for o in others[:2]]
        for lm in new_items:
            lm.node = self.root.attachNewNode(f'landmark_{lm.idx}')
            model = geom.build_landmark(lm.kind, _stable_seed(self.seed, lm.idx))
            model.reparentTo(lm.node)
            model.setScale(geom.LANDMARK_SCALE)
            sink = (1.2 if lm.kind == 'ribs' else 0.4) * geom.LANDMARK_SCALE
            lm.node.setPos(lm.pos.x, lm.pos.y, lm.pos.z - sink)
            lm.node.setH(lm.heading)

    def chapter_sites(self, chapter: int):
        return chapter_sites(self.seed, self.start.x, self.start.y, chapter, len(self.items))

    def add_chapter(self, near: Point3 | None = None):
        """Open the next ring of the trail (terrain zones must already be levelled)."""
        self.chapter += 1
        new = []
        for i, x, y, kind, heading in self.chapter_sites(self.chapter):
            new.append(Landmark(i, Point3(x, y, self.field.height(x, y)), kind, heading,
                                chapter_lore(self.seed, i, kind)))
        self.items.extend(new)
        self._link_and_build(new)
        ref = near if near is not None else self.start
        for lm in sorted(new, key=lambda o: _flat(o.pos, ref))[:2]:
            self.reveal(lm)
        return new

    def all_visited(self) -> bool:
        return all(lm.visited for lm in self.items)

    def reveal(self, lm: Landmark) -> bool:
        if lm.revealed:
            return False
        lm.revealed = True
        return True

    def nearest(self, p: Point3, radius: float):
        best, best_d = None, radius
        for lm in self.items:
            if lm.visited:
                continue
            d = _flat(lm.pos, p) - geom.LANDMARK_SHAPES[lm.kind][0]
            if d <= best_d:
                best, best_d = lm, d
        return best

    def nearest_unvisited_revealed(self, p: Point3):
        cands = [lm for lm in self.items if lm.revealed and not lm.visited]
        return min(cands, key=lambda lm: _flat(lm.pos, p)) if cands else None

    def visit(self, lm: Landmark):
        """Returns (cache items dict, newly revealed landmarks)."""
        if lm.visited:
            return {}, []
        lm.visited = True
        lm.revealed = True
        newly = [self.items[i] for i in lm.links if self.reveal(self.items[i])]
        cache = {'pod': 2, 'gourd': 1, 'fibre': 2, 'resin': 1}
        return cache, newly

    def shade_circles(self, offset: Vec3):
        out = []
        for lm in self.items:
            r, h = geom.LANDMARK_SHAPES[lm.kind]
            out.append((lm.pos.x + offset.x * h * 0.45, lm.pos.y + offset.y * h * 0.45, r))
        return out

    def visited_count(self) -> int:
        return sum(1 for lm in self.items if lm.visited)

    def update(self, time: float, eye: Point3 | None = None):
        return None
