"""Procedural geometry for desert content (shells, finds, landmarks).

Everything is built once per variant with the same vertex layout as the rest of the
game (GeomVertexFormat.getV3n3c4) so it goes through the sketch shader, and is then
instanced per world object.
"""
from __future__ import annotations

import math
import random

from panda3d.core import (
    Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter,
    NodePath, Point3, Vec3, Vec4,
)


class Mesh:
    """Tiny helper around the vertex writers."""

    def __init__(self, name: str):
        self.name = name
        self.vdata = GeomVertexData(name, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
        self.vw = GeomVertexWriter(self.vdata, 'vertex')
        self.nw = GeomVertexWriter(self.vdata, 'normal')
        self.cw = GeomVertexWriter(self.vdata, 'color')
        self.tris = GeomTriangles(Geom.UHStatic)
        self.rows = 0
        self.pts: list = []           # Pass 56: kept so faces can be wound to match their normals
        self.nrm: list = []

    def vertex(self, p, n, c) -> int:
        self.vw.addData3(p)
        self.nw.addData3(n)
        self.cw.addData4(c)
        self.pts.append(Vec3(p))
        self.nrm.append(Vec3(n))
        self.rows += 1
        return self.rows - 1

    def tri(self, a, b, c):
        self.tris.addVertices(a, b, c)

    def tri_facing(self, a, b, c):
        """Pass 56: a triangle wound so its front face agrees with its vertex normals (lets a
        closed, thick mesh render one-sided)."""
        pa, pb, pc = self.pts[a], self.pts[b], self.pts[c]
        face = (pb - pa).cross(pc - pa)
        if face.lengthSquared() < 1e-14:
            return                                     # degenerate (at a pole)
        if face.dot(self.nrm[a] + self.nrm[b] + self.nrm[c]) < 0.0:
            b, c = c, b
        self.tris.addVertices(a, b, c)

    def quad_facing(self, a, b, c, d):
        """a-b-c-d around the quad, either way round."""
        self.tri_facing(a, b, c)
        self.tri_facing(a, c, d)

    def tube_facing(self, start: Point3, end: Point3, r0: float, r1: float, c0: Vec4, c1: Vec4,
                    sides: int = 7, cap: bool = False):
        """A tapered tube whose faces point outward (optionally capped at the thin end)."""
        axis = end - start
        length = axis.length()
        if length < 1e-6:
            return
        axis /= length
        ref = Vec3(0, 0, 1) if abs(axis.z) < 0.9 else Vec3(1, 0, 0)
        u = axis.cross(ref)
        u.normalize()
        v = axis.cross(u)
        rings = []
        for centre, radius, colour in ((start, r0, c0), (end, r1, c1)):
            ring = []
            for i in range(sides):
                ang = 2.0 * math.pi * i / sides
                n = u * math.cos(ang) + v * math.sin(ang)
                ring.append(self.vertex(centre + n * radius, n, colour))
            rings.append(ring)
        for i in range(sides):
            j = (i + 1) % sides
            self.quad_facing(rings[0][i], rings[0][j], rings[1][j], rings[1][i])
        if cap:
            tip = self.vertex(end + axis * r1 * 0.4, axis, c1)
            for i in range(sides):
                c = self.vertex(self.pts[rings[1][i]], axis, c1)
                d = self.vertex(self.pts[rings[1][(i + 1) % sides]], axis, c1)
                self.tri_facing(c, d, tip)

    def tube(self, start: Point3, end: Point3, r0: float, r1: float, c0: Vec4, c1: Vec4, sides: int = 6):
        axis = end - start
        length = axis.length()
        if length < 1e-6:
            return
        axis /= length
        ref = Vec3(0, 0, 1) if abs(axis.z) < 0.9 else Vec3(1, 0, 0)
        u = axis.cross(ref)
        u.normalize()
        v = axis.cross(u)
        base = self.rows
        for centre, radius, colour in ((start, r0, c0), (end, r1, c1)):
            for i in range(sides):
                a = 2.0 * math.pi * i / sides
                n = u * math.cos(a) + v * math.sin(a)
                self.vertex(centre + n * radius, n, colour)
        for i in range(sides):
            j = (i + 1) % sides
            self.tri(base + i, base + j, base + sides + j)
            self.tri(base + i, base + sides + j, base + sides + i)

    def ellipsoid(self, centre: Point3, rx: float, ry: float, rz: float, colour: Vec4,
                  rings: int = 10, segments: int = 18, phi_max: float = math.pi, skip=None, shade=None, radial=None):
        """Ellipsoid from the top pole down to polar angle phi_max (pi/2 = dome).

        skip(ring, seg) drops individual quads (entrances, holes); shade(ring, seg, colour)
        varies the vertex colour.
        """
        grid = []
        for r in range(rings + 1):
            phi = phi_max * r / rings
            z = math.cos(phi)
            s = math.sin(phi)
            row = []
            for k in range(segments + 1):
                th = 2.0 * math.pi * k / segments
                m = radial(r, k) if radial else 1.0
                p = Point3(centre.x + rx * s * m * math.cos(th), centre.y + ry * s * m * math.sin(th), centre.z + rz * z)
                n = Vec3(s * math.cos(th) / rx, s * math.sin(th) / ry, z / rz)
                n.normalize()
                c = shade(r, k, colour) if shade else colour
                row.append(self.vertex(p, n, c))
            grid.append(row)
        for r in range(rings):
            for k in range(segments):
                if skip is not None and skip(r, k):
                    continue
                a, b, c, d = grid[r][k], grid[r][k + 1], grid[r + 1][k + 1], grid[r + 1][k]
                self.tri(a, d, c)
                self.tri(a, c, b)

    def node(self) -> NodePath:
        geom = Geom(self.vdata)
        geom.addPrimitive(self.tris)
        gn = GeomNode(self.name)
        gn.addGeom(geom)
        return NodePath(gn)


# ---------------------------------------------------------------------------
# Shells — empty sea shells from when this desert was a sea floor
# ---------------------------------------------------------------------------
# Pass 55: big enough to walk into and stand up in (was 1.9 x 1.6 x 1.35, smaller than you).
# Pass 56: domed a little higher (2.7 -> 3.2 m) so the mouth is a doorway set into the front,
# not a bite out of the whole face.
SHELL_RX, SHELL_RY, SHELL_H = 3.4, 3.0, 3.2
# Pass 56: a natural mouth. A rounded arch (not a notch cut along the mesh rows), a thick
# rounded lip that flares out a little, a pearly inside, sand-stained at the foot.
MOUTH_TOP = 2.2                    # height of the arch at its middle (m)
MOUTH_CORE_DEG = 24.0              # half-width of the arch itself (deg)
MOUTH_SHAPE = 2.5                  # superellipse power: 2 = round arch, higher = squarer shoulders
MOUTH_FOOT_DEG = 5.0               # the arch's feet splay out this much more at the sand...
MOUTH_FOOT_H = 0.6                 # ...fading out by this height (m)
MOUTH_HALF_BASE = MOUTH_CORE_DEG + MOUTH_FOOT_DEG   # half-width at the sand (~3 m across)
SHELL_MOUTH_DEG = MOUTH_HALF_BASE  # (older name)
MOUTH_CLEAR = 1.95                 # you walk through wherever the arch is at least this high
SHELL_THICK = 0.14                 # wall thickness, seen at the lip
SHELL_FLARE = 0.05                 # the lip turns out by this fraction of the radius
_PEARL = Vec4(0.93, 0.86, 0.78, 1.0)
_PEARL_DARK = Vec4(0.78, 0.66, 0.60, 1.0)
_PEARL_PINK = Vec4(0.90, 0.70, 0.66, 1.0)
_LIP = Vec4(0.96, 0.84, 0.80, 1.0)
_NACRE = Vec4(0.95, 0.91, 0.90, 1.0)
_NACRE_LILAC = Vec4(0.86, 0.84, 0.93, 1.0)
_NACRE_ROSE = Vec4(0.95, 0.82, 0.84, 1.0)
_SAND_STAIN = Vec4(0.80, 0.71, 0.61, 1.0)
_BARNACLE = Vec4(0.74, 0.71, 0.67, 1.0)


def mouth_half_width(z: float) -> float:
    """Half-width (deg) of the mouth at height z: a rounded arch whose feet splay out a little."""
    if z >= MOUTH_TOP:
        return 0.0
    w = MOUTH_CORE_DEG * (1.0 - (max(0.0, z) / MOUTH_TOP) ** MOUTH_SHAPE) ** (1.0 / MOUTH_SHAPE)
    if z < MOUTH_FOOT_H:
        w += MOUTH_FOOT_DEG * (1.0 - max(0.0, z) / MOUTH_FOOT_H) ** 2
    return w


def mouth_height(a_deg: float) -> float:
    """Height of the mouth's arch a_deg around from its middle (0 beyond the mouth)."""
    a = abs(a_deg)
    if a >= MOUTH_HALF_BASE:
        return 0.0
    lo, hi = 0.0, MOUTH_TOP                   # the half-width falls with height: bisect for it
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        if mouth_half_width(mid) > a:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def mouth_walkable_deg() -> float:
    """Half-width (deg) of the part of the mouth a person walks through upright."""
    return mouth_half_width(MOUTH_CLEAR)


def _shell_columns():
    """Angles (deg) round the shell: fine steps across the mouth so the arch is smooth."""
    cols, th = [], 0.0
    lo, hi = 90.0 - MOUTH_HALF_BASE - 10.0, 90.0 + MOUTH_HALF_BASE + 10.0
    while th < 360.0 - 1e-6:
        cols.append(th)
        if 17.0 - 1e-6 <= abs(th - 90.0) < MOUTH_HALF_BASE + 1.0:
            th += 0.625                      # the arch's steep sides and feet
        elif lo - 1e-6 <= th < hi:
            th += 1.25
        else:
            th += 3.75
    cols.append(360.0)
    return cols


def _smooth(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


def build_shell(cracked: bool, seed: int = 3, barnacles: bool = True) -> NodePath:
    """A ribbed cockle valve lying dome-up, with an arched mouth facing +Y.

    Pass 56: the shell has a real wall - an outer ribbed surface, a pearly inner one and a
    rounded lip joining them all round the rim and the mouth. The mouth is a smooth arch whose
    edge is a little worn; near every edge the shell flares out slightly, like a real lip.
    """
    rng = random.Random(seed)
    rows = 14
    cols = _shell_columns()
    phase = rng.uniform(0.0, 6.28)

    def worn(th):
        # a gentle unevenness along the arch (a few cm along the surface, never teeth), fading
        # to nothing where the arch meets the sand
        a = abs(th - 90.0) / MOUTH_HALF_BASE
        if a >= 1.0:
            return 0.0
        t = math.radians(th - 90.0)
        wobble = 0.012 * math.sin(t * 9.0 + phase) + 0.006 * math.sin(t * 21.0 + 2.0 * phase)
        return wobble * (1.0 - a ** 4)

    def edge_phi(th):
        h = mouth_height(th - 90.0)
        if h <= 0.0:
            return math.pi / 2.0
        return min(math.pi / 2.0, math.acos(min(0.97, h / SHELL_H)) + worn(th))

    ribs = 12

    def rib(th):
        return 0.5 + 0.5 * math.cos(math.radians(th) * ribs)

    def outer_colour(th, phi, z):
        band = _PEARL + (_PEARL_DARK - _PEARL) * (0.9 * (1.0 - rib(th)))
        g = abs(math.degrees(phi) / 30.0 - round(math.degrees(phi) / 30.0))     # growth lines every 30 deg
        band = band + (_PEARL_DARK - band) * (0.10 * (1.0 - _smooth(g / 0.18)))
        band = band + (_PEARL_PINK - band) * (phi / (math.pi / 2.0)) * 0.6
        stain = 0.25 * (1.0 - _smooth(z / 0.45))                                 # sand-stained foot
        return band + (_SAND_STAIN - band) * stain

    def inner_colour(th, phi):
        k = 0.5 + 0.5 * math.sin(math.radians(th) * 3.0 + phi * 5.0 + phase)
        c = _NACRE + (_NACRE_LILAC - _NACRE) * (0.45 * k)
        return c + (_NACRE_ROSE - c) * (0.35 * (1.0 - k)) * (phi / (math.pi / 2.0))

    def normal(th, phi):
        t, sp, cp = math.radians(th), math.sin(phi), math.cos(phi)
        n = Vec3(sp * math.cos(t) / SHELL_RX, sp * math.sin(t) / SHELL_RY, cp / SHELL_H)
        n.normalize()
        return n

    def point(th, phi, edge):
        t, sp = math.radians(th), math.sin(phi)
        # scalloped ribs, strongest toward the rim like a cockle, and a lip that turns out
        grow = 1.0 + 0.06 * (phi / (math.pi / 2.0)) * rib(th)
        grow += SHELL_FLARE * (1.0 - _smooth((edge - phi) / 0.22)) ** 2
        return Point3(SHELL_RX * sp * grow * math.cos(t), SHELL_RY * sp * grow * math.sin(t),
                      SHELL_H * math.cos(phi))

    # cracked shells: a few jagged breaks, away from the mouth and the rim
    holes = []
    if cracked:
        while len(holes) < 5:
            thc = rng.uniform(0.0, 360.0)
            if abs(((thc - 90.0 + 180.0) % 360.0) - 180.0) < MOUTH_HALF_BASE + 22.0:
                continue
            holes.append((thc, math.radians(rng.uniform(18.0, 55.0)), math.radians(rng.uniform(5.0, 8.5)),
                          rng.uniform(0.0, 6.28)))

    def hole_polar(th, phi, hole):
        """(distance, angle, contour radius) of (th, phi) from a hole's centre, in surface terms."""
        thc, phc, rad, ph = hole
        dth = math.radians(((th - thc + 180.0) % 360.0) - 180.0) * math.sin(phc)
        ang = math.atan2(phi - phc, dth)
        edge = rad * (1.0 + 0.30 * math.sin(5.0 * ang + ph) + 0.12 * math.sin(11.0 * ang + 2.0 * ph))
        return math.hypot(dth, phi - phc), ang, edge

    def which_hole(th, phi):
        for hole in holes:
            d, _a, edge = hole_polar(th, phi, hole)
            if d < edge:
                return hole
        return None

    # the grid of (angle, polar angle) on the shell, rows running from the crown to the edge
    ncol = len(cols) - 1
    edges = [edge_phi(th) for th in cols]
    params = [[(th, edges[c] * r / rows) for r in range(rows + 1)] for c, th in enumerate(cols)]
    skipped = {}
    for c in range(ncol):
        for r in range(rows):
            hole = which_hole(0.5 * (cols[c] + cols[c + 1]), 0.5 * (edges[c] + edges[c + 1]) * (r + 0.5) / rows)
            if hole is not None:
                skipped[(c, r)] = hole
    # A broken edge follows the break, not the grid: every corner shared by a kept and a broken
    # cell moves onto the hole's jagged outline.
    for (c, r), hole in skipped.items():
        for vc, vr in ((c, r), (c + 1, r), (c, r + 1), (c + 1, r + 1)):
            cells = [(vc - dc, vr - dr) for dc in (0, 1) for dr in (0, 1)]
            if all(((cc % ncol), rr) in skipped or not 0 <= rr < rows for cc, rr in cells):
                continue                                    # inside the hole: not drawn
            th, phi = params[vc][vr]
            _d, ang, edge = hole_polar(th, phi, hole)
            thc, phc = hole[0], hole[1]
            params[vc][vr] = (thc + math.degrees(math.cos(ang) * edge / math.sin(phc)), phc + math.sin(ang) * edge)
            if vc == 0 or vc == ncol:                       # the seam: keep both copies together
                params[ncol - vc][vr] = (params[vc][vr][0] + (360.0 if vc == 0 else -360.0), params[vc][vr][1])

    m = Mesh('shell_cracked' if cracked else 'shell')
    outer, inner = [], []
    for c, th0 in enumerate(cols):
        o_col, i_col = [], []
        for r in range(rows + 1):
            th, phi = params[c][r]
            p = point(th, phi, edges[c])
            n = normal(th, phi)
            o_col.append(m.vertex(p, n, outer_colour(th, phi, p.z)))
            i_col.append(m.vertex(p - n * SHELL_THICK, -n, inner_colour(th, phi)))
        outer.append(o_col)
        inner.append(i_col)

    for c in range(ncol):
        for r in range(rows):
            if (c, r) in skipped:
                continue
            m.quad_facing(outer[c][r], outer[c + 1][r], outer[c + 1][r + 1], outer[c][r + 1])
            m.quad_facing(inner[c][r], inner[c + 1][r], inner[c + 1][r + 1], inner[c][r + 1])

    # the broken edges: a short wall of shell between the outer and inner surfaces
    for (c, r), hole in skipped.items():
        for dc, dr, a0, a1 in ((0, -1, (c, r), (c + 1, r)), (0, 1, (c, r + 1), (c + 1, r + 1)),
                               (-1, 0, (c, r), (c, r + 1)), (1, 0, (c + 1, r), (c + 1, r + 1))):
            nb = ((c + dc) % ncol, r + dr)
            if nb in skipped or not 0 <= nb[1] < rows:
                continue
            oa, ob = outer[a0[0]][a0[1]], outer[a1[0]][a1[1]]
            ia, ib = inner[a0[0]][a0[1]], inner[a1[0]][a1[1]]
            mid = (m.pts[oa] + m.pts[ob]) * 0.5
            centre = point(hole[0], hole[1], math.pi / 2.0)
            into_hole = Vec3(centre) - mid
            into_hole -= m.nrm[oa] * into_hole.dot(m.nrm[oa])
            if into_hole.lengthSquared() < 1e-10:
                continue
            into_hole.normalize()
            wall = [m.vertex(m.pts[v], into_hole, _PEARL_DARK) for v in (oa, ob, ib, ia)]
            m.quad_facing(*wall)

    # the lip: a rounded bead joining outer and inner all along the rim and the mouth
    bead = 4
    lip_rows = []
    for c in range(len(cols)):
        o, i = m.pts[outer[c][rows]], m.pts[inner[c][rows]]
        n_o = m.nrm[outer[c][rows]]
        d = o - m.pts[outer[c][rows - 1]]              # the surface, carried on past its edge
        d.normalize()
        row = []
        for b in range(bead + 1):
            s = b / bead
            p = o + (i - o) * s + d * (SHELL_THICK * 0.55 * math.sin(math.pi * s))
            n = n_o * math.cos(math.pi * s) + d * math.sin(math.pi * s)
            n.normalize()
            row.append(m.vertex(p, n, _LIP + (_NACRE - _LIP) * (0.6 * s)))
        lip_rows.append(row)
    for c in range(ncol):
        for b in range(bead):
            m.quad_facing(lip_rows[c][b], lip_rows[c + 1][b], lip_rows[c + 1][b + 1], lip_rows[c][b + 1])

    # a few low, squat barnacles on the sides and back (never round the mouth). Pass 56: the
    # old hinge "ears" (they read as horns) are gone.
    for _ in range(3 if barnacles else 0):
        thc = rng.choice((rng.uniform(150.0, 250.0), rng.uniform(290.0, 380.0) % 360.0))
        phc = rng.uniform(70.0, 82.0)
        for _k in range(rng.randint(2, 4)):
            th = thc + rng.uniform(-5.0, 5.0)
            phi = math.radians(min(85.0, phc + rng.uniform(-3.0, 3.0)))
            base, n = point(th, phi, math.pi / 2.0), normal(th, phi)
            rad = rng.uniform(0.06, 0.12)
            m.tube_facing(base - n * 0.02, base + n * rad * 0.7, rad, rad * 0.6, _PEARL_DARK, _BARNACLE,
                          sides=7, cap=True)

    return m.node()


# ---------------------------------------------------------------------------
# Finds — half-buried things; you only know what they are once you dig them up
# ---------------------------------------------------------------------------
_SAND = Vec4(0.80, 0.74, 0.64, 1.0)
_STUB = Vec4(0.50, 0.44, 0.38, 1.0)
_BONE_TIP = Vec4(0.86, 0.82, 0.74, 1.0)


def build_mound(seed: int) -> NodePath:
    rng = random.Random(seed)
    m = Mesh('find_mound')
    m.ellipsoid(Point3(0, 0, -0.05), 0.8, 0.7, 0.34, _SAND, rings=5, segments=12, phi_max=math.pi / 2)
    # something sticking out of the sand
    for _ in range(rng.choice((1, 2))):
        a = rng.uniform(0, 2 * math.pi)
        base = Point3(math.cos(a) * 0.15, math.sin(a) * 0.15, 0.15)
        # a bleached bone / dry stalk poking out of the sand: noticeable up close, natural at a glance
        tip = base + Vec3(rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35), rng.uniform(0.7, 1.2))
        m.tube(base, tip, 0.08, 0.02, _STUB, _BONE_TIP, sides=5)
    return m.node()


REVEAL_COLOURS = {
    'pod': Vec4(0.45, 0.58, 0.40, 1.0),      # moss pods (food)
    'gourd': Vec4(0.84, 0.86, 0.66, 1.0),    # water gourd (food, cools)
    'fibre': Vec4(0.62, 0.52, 0.34, 1.0),
    'resin': Vec4(0.88, 0.56, 0.16, 1.0),
    'shard': Vec4(0.92, 0.84, 0.86, 1.0),
    'nothing': Vec4(0.52, 0.48, 0.44, 1.0),
}


def build_reveal(kind: str) -> NodePath:
    """Small object shown for a moment when a find is dug up."""
    c = REVEAL_COLOURS.get(kind, REVEAL_COLOURS['nothing'])
    m = Mesh(f'reveal_{kind}')
    if kind == 'pod':
        for i in range(3):
            a = i * 2.1
            m.ellipsoid(Point3(math.cos(a) * 0.12, math.sin(a) * 0.12, 0.12), 0.11, 0.11, 0.13, c, 5, 8)
    elif kind == 'gourd':
        m.ellipsoid(Point3(0, 0, 0.2), 0.16, 0.16, 0.24, c, 6, 10)
    elif kind == 'fibre':
        for i in range(7):
            a = i * 0.9
            m.tube(Point3(0, 0, 0), Point3(math.cos(a) * 0.25, math.sin(a) * 0.25, 0.45), 0.02, 0.005, c, c * 1.2, 4)
    elif kind == 'resin':
        m.ellipsoid(Point3(0, 0, 0.1), 0.13, 0.1, 0.1, c, 5, 8)
    elif kind == 'shard':
        m.ellipsoid(Point3(0, 0, 0.1), 0.2, 0.05, 0.14, c, 4, 8)
    else:
        m.ellipsoid(Point3(0, 0, 0.06), 0.14, 0.12, 0.08, c, 4, 8)
    return m.node()


# ---------------------------------------------------------------------------
# Landmarks — the far-off things that make up the non-linear trail
# ---------------------------------------------------------------------------
_BONE = Vec4(0.90, 0.86, 0.78, 1.0)
_BONE_DARK = Vec4(0.70, 0.64, 0.56, 1.0)
_SPIRE = Vec4(0.56, 0.50, 0.64, 1.0)
_BEAD = Vec4(0.30, 0.36, 0.74, 1.0)

LANDMARK_SCALE = 1.7               # Pass 42: bigger, so they hold the horizon from far away
LANDMARK_SHAPES = {
    # kind: (shade / footprint radius, height), already scaled
    'ribs': (6.5 * LANDMARK_SCALE, 9.0 * LANDMARK_SCALE),
    'spire': (3.0 * LANDMARK_SCALE, 26.0 * LANDMARK_SCALE),
    'bead': (6.0 * LANDMARK_SCALE, 9.0 * LANDMARK_SCALE),
}


def build_landmark(kind: str, seed: int) -> NodePath:
    rng = random.Random(seed)
    m = Mesh(f'landmark_{kind}')
    if kind == 'ribs':
        # half-buried ribcage of something enormous
        m.tube(Point3(-12, 0, 0.2), Point3(12, 0, 1.6), 0.9, 0.6, _BONE_DARK, _BONE, 8)
        for i in range(7):
            x = -9 + i * 3.0
            radius = 6.5 - abs(i - 3) * 0.7
            for side in (-1, 1):
                prev = Point3(x, 0, 1.0 + i * 0.1)
                for s in range(1, 8):
                    a = math.pi * 0.5 * s / 7          # 0 = up, pi/2 = out/down
                    p = Point3(x + rng.uniform(-0.2, 0.2), side * radius * math.sin(a),
                               1.0 + radius * 1.25 * math.cos(a) - 0.6 * (s / 7))
                    m.tube(prev, p, 0.42 - s * 0.03, 0.40 - s * 0.03, _BONE, _BONE_DARK, 6)
                    prev = p
    elif kind == 'spire':
        prev = Point3(0, 0, -0.5)
        h = 0.0
        for s in range(10):
            h += 2.6
            twist = s * 0.45
            p = Point3(math.cos(twist) * 0.6, math.sin(twist) * 0.6, h)
            m.tube(prev, p, 2.3 * (1 - s / 10.5), 2.3 * (1 - (s + 1) / 10.5) + 0.1, _SPIRE * 0.85, _SPIRE, 7)
            prev = p
        for k in range(3):
            a = k * 2.1 + 0.4
            base = Point3(math.cos(a) * 1.4, math.sin(a) * 1.4, 7 + k * 4)
            m.tube(base, base + Vec3(math.cos(a) * 3.5, math.sin(a) * 3.5, 2.5), 0.5, 0.08, _SPIRE, _SPIRE * 1.1, 5)
    else:  # bead — a huge glassy sphere half sunk in the dunes, with a hollow
        def skip(r, k):
            return 3 <= r <= 5 and 2 <= k <= 5

        m.ellipsoid(Point3(0, 0, 2.0), 6.0, 6.0, 6.0, _BEAD, rings=12, segments=22, phi_max=math.acos(-0.3), skip=skip)
    np_ = m.node()
    np_.setTwoSided(True)
    return np_
