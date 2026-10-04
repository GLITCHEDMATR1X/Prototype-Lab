"""Pass 46 — geometry for the hidden places of the wide world.

Every place kind is built from simple procedural parts (lumpy rocks, boxes, tubes, domes) in
the same vertex format as the rest of the world, so it goes through the sketch shader, the
fog and the shadows like everything else. Sizes are in metres (the human is 1.8 m, Indigo
about 20 m).
"""
from __future__ import annotations

import math
import random

from panda3d.core import NodePath, Point3, Vec3, Vec4

from desert_geom import Mesh

# ---------------------------------------------------------------- palette
BONE = Vec4(0.90, 0.86, 0.78, 1.0)
BONE_DARK = Vec4(0.66, 0.60, 0.52, 1.0)
SANDSTONE = Vec4(0.82, 0.62, 0.50, 1.0)
SANDSTONE_DARK = Vec4(0.62, 0.45, 0.38, 1.0)
STONE = Vec4(0.62, 0.58, 0.64, 1.0)
STONE_DARK = Vec4(0.44, 0.41, 0.47, 1.0)
GLASS = Vec4(0.74, 0.86, 0.90, 1.0)
GLASS_DEEP = Vec4(0.44, 0.60, 0.72, 1.0)
WATER = Vec4(0.36, 0.56, 0.62, 1.0)
WATER_EDGE = Vec4(0.58, 0.70, 0.66, 1.0)
REED = Vec4(0.52, 0.60, 0.40, 1.0)
REED_TIP = Vec4(0.78, 0.74, 0.50, 1.0)
HUSK = Vec4(0.62, 0.54, 0.64, 1.0)
HUSK_DARK = Vec4(0.40, 0.34, 0.44, 1.0)
THATCH = Vec4(0.66, 0.56, 0.38, 1.0)
CHAR = Vec4(0.20, 0.18, 0.18, 1.0)
INDIGO_STONE = Vec4(0.40, 0.44, 0.66, 1.0)
INDIGO_STONE_DARK = Vec4(0.26, 0.28, 0.46, 1.0)
PETRIFIED = Vec4(0.60, 0.52, 0.47, 1.0)
PETRIFIED_DARK = Vec4(0.40, 0.33, 0.30, 1.0)
SALT = Vec4(0.95, 0.94, 0.92, 1.0)
SALT_BLUE = Vec4(0.80, 0.88, 0.94, 1.0)
PAINT = (Vec4(0.66, 0.20, 0.15, 1.0), Vec4(0.30, 0.38, 0.72, 1.0), Vec4(0.86, 0.80, 0.62, 1.0))
PALE = Vec4(0.96, 0.95, 0.98, 1.0)          # the pale bloom: white, not glowing
PALE_VEIN = Vec4(0.78, 0.80, 0.88, 1.0)
PALE_LEAF = Vec4(0.80, 0.84, 0.80, 1.0)
SOIL = Vec4(0.28, 0.24, 0.24, 1.0)


def _mix(a: Vec4, b: Vec4, t: float) -> Vec4:
    return a + (b - a) * max(0.0, min(1.0, t))


# ---------------------------------------------------------------- parts
def rock(m: Mesh, centre: Point3, rx: float, ry: float, rz: float, colour: Vec4, rng: random.Random,
         lump: float = 0.16, dark: Vec4 | None = None, phi_max: float = math.pi):
    segs = 10
    bumps = {(r, k): rng.uniform(-lump, lump) for r in range(8) for k in range(segs)}
    dark = dark or colour * 0.8

    def radial(r, k):
        return 1.0 + bumps[(r, k % segs)]

    def shade(r, k, c):
        return _mix(c, dark, r / 7.0 * 0.8 + bumps[(r, k % segs)])

    m.ellipsoid(centre, rx, ry, rz, colour, rings=7, segments=segs, phi_max=phi_max, radial=radial, shade=shade)


def box(m: Mesh, centre: Point3, w: float, d: float, h: float, colour: Vec4, heading: float = 0.0,
        tilt: float = 0.0, dark: Vec4 | None = None):
    """A slab / block, rotated `heading` degrees about Z and leaned `tilt` degrees about X."""
    hr, tr = math.radians(heading), math.radians(tilt)
    ch, sh, ct, st = math.cos(hr), math.sin(hr), math.cos(tr), math.sin(tr)
    dark = dark or colour * 0.8

    def xf(v: Vec3) -> Vec3:
        y, z = v.y * ct - v.z * st, v.y * st + v.z * ct          # lean
        return Vec3(v.x * ch - y * sh, v.x * sh + y * ch, z)    # turn

    faces = ((Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)), (Vec3(-1, 0, 0), Vec3(0, -1, 0), Vec3(0, 0, 1)),
             (Vec3(0, 1, 0), Vec3(-1, 0, 0), Vec3(0, 0, 1)), (Vec3(0, -1, 0), Vec3(1, 0, 0), Vec3(0, 0, 1)),
             (Vec3(0, 0, 1), Vec3(1, 0, 0), Vec3(0, 1, 0)), (Vec3(0, 0, -1), Vec3(-1, 0, 0), Vec3(0, 1, 0)))
    half = Vec3(w / 2, d / 2, h / 2)
    for n, u, v in faces:
        base = m.rows
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            local = Vec3(n.x * half.x + su * u.x * half.x + sv * v.x * half.x,
                         n.y * half.y + su * u.y * half.y + sv * v.y * half.y,
                         n.z * half.z + su * u.z * half.z + sv * v.z * half.z)
            p = centre + xf(local)
            c = _mix(colour, dark, 0.55 * (0.5 - local.z / max(h, 1e-6)))
            m.vertex(p, xf(n), c)
        m.tri(base, base + 1, base + 2)
        m.tri(base, base + 2, base + 3)


def chain(m: Mesh, points, r0: float, r1: float, c0: Vec4, c1: Vec4, sides: int = 7):
    n = len(points) - 1
    for i in range(n):
        a, b = i / n, (i + 1) / n
        m.tube(points[i], points[i + 1], r0 + (r1 - r0) * a, r0 + (r1 - r0) * b + 0.01,
               _mix(c0, c1, a), _mix(c0, c1, b), sides)


def disc(m: Mesh, centre: Point3, radius: float, inner: Vec4, outer: Vec4, segments: int = 28):
    base = m.rows
    m.vertex(centre, Vec3(0, 0, 1), inner)
    for k in range(segments):
        a = 2 * math.pi * k / segments
        m.vertex(centre + Vec3(math.cos(a) * radius, math.sin(a) * radius, 0), Vec3(0, 0, 1), outer)
    for k in range(segments):
        m.tri(base, base + 1 + k, base + 1 + (k + 1) % segments)


# ---------------------------------------------------------------- kinds
def _skull(m, rng):
    def skip(r, k):
        th = 360.0 * (k + 0.5) / 20
        eye = r in (3, 4) and (abs(th - 70) < 12 or abs(th - 110) < 12)
        door = r >= 5 and abs(th - 270) < 34                  # a low way in at the back
        return eye or door

    def shade(r, k, c):
        return _mix(BONE, BONE_DARK, r / 7.0 * 0.7 + (0.15 if k % 3 == 0 else 0.0))

    m.ellipsoid(Point3(0, 0, 1.5), 11.0, 13.0, 9.5, BONE, rings=7, segments=20, phi_max=math.pi * 0.62,
                skip=skip, shade=shade)
    m.tube(Point3(-8, 10.5, 5.5), Point3(8, 10.5, 5.5), 1.3, 1.3, BONE_DARK, BONE, 8)       # brow
    for side in (-1, 1):
        m.tube(Point3(side * 9.5, 8, 1.5), Point3(side * 6, 12.5, 0.4), 1.2, 0.9, BONE, BONE_DARK, 7)   # cheek
    for i in range(9):                                         # upper teeth
        x = -5.5 + i * 1.4
        m.tube(Point3(x, 12.4, 1.4), Point3(x * 1.02, 12.9, -0.4), 0.45, 0.2, BONE, BONE_DARK, 5)
    jaw = [Point3(-9, 2 + rng.uniform(-1, 1), 0.2), Point3(-6, 13, 0.6), Point3(0, 16, 0.8),
           Point3(6, 13, 0.6), Point3(9, 2, 0.2)]
    chain(m, [p + Vec3(rng.uniform(4, 7), 6, -0.3) for p in jaw], 1.1, 1.0, BONE_DARK, BONE)


def _arch(m, rng):
    for side in (-1, 1):
        z = 0.0
        for k in range(4):
            h = rng.uniform(2.6, 3.4)
            rock(m, Point3(side * 8.5 + rng.uniform(-0.4, 0.4), rng.uniform(-0.3, 0.3), z + h * 0.5),
                 2.6 - k * 0.2, 2.2 - k * 0.15, h * 0.62, SANDSTONE if k % 2 else SANDSTONE_DARK, rng, 0.12,
                 dark=SANDSTONE_DARK)
            z += h * 0.9
    pts = [Point3(-8.5 + 17.0 * i / 10, 0, 11.0 + 5.2 * math.sin(math.pi * i / 10)) for i in range(11)]
    chain(m, pts, 2.3, 2.3, SANDSTONE_DARK, SANDSTONE, 8)
    for _ in range(5):                                          # fallen pieces
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(5, 12)
        rock(m, Point3(math.cos(a) * d, math.sin(a) * d, 0.4), rng.uniform(0.8, 1.8), rng.uniform(0.7, 1.5),
             rng.uniform(0.6, 1.2), SANDSTONE, rng, 0.2, dark=SANDSTONE_DARK)


def _oasis(m, rng):
    disc(m, Point3(0, 0, 0.32), 8.5, WATER, WATER_EDGE, 32)       # just above the levelled sand
    for k in range(16):                                         # shore stones
        a = 2 * math.pi * k / 16 + rng.uniform(-0.1, 0.1)
        d = 8.8 + rng.uniform(-0.3, 0.6)
        rock(m, Point3(math.cos(a) * d, math.sin(a) * d, 0.1), rng.uniform(0.4, 0.9), rng.uniform(0.3, 0.7),
             rng.uniform(0.2, 0.45), STONE, rng, 0.2, dark=STONE_DARK)
    for _clump in range(9):                                     # reeds at the water's edge
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(7.2, 9.6)
        cx, cy = math.cos(a) * d, math.sin(a) * d
        for _ in range(rng.randint(6, 10)):
            base = Point3(cx + rng.uniform(-0.8, 0.8), cy + rng.uniform(-0.8, 0.8), 0.0)
            tip = base + Vec3(rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35), rng.uniform(1.2, 2.4))
            m.tube(base, tip, 0.05, 0.015, REED, REED_TIP, 4)
    for _palm in range(3):                                      # drooping moon-palms
        a = rng.uniform(0, 2 * math.pi)
        base = Point3(math.cos(a) * 10.5, math.sin(a) * 10.5, 0)
        lean = Vec3(-math.cos(a), -math.sin(a), 0) * 0.5
        pts = [base + lean * (i * i * 0.18) + Vec3(0, 0, i * 1.3) for i in range(6)]
        chain(m, pts, 0.32, 0.18, SANDSTONE_DARK, THATCH, 6)
        top = pts[-1]
        for f in range(7):
            fa = 2 * math.pi * f / 7
            mid = top + Vec3(math.cos(fa) * 1.8, math.sin(fa) * 1.8, 0.6)
            end = top + Vec3(math.cos(fa) * 3.2, math.sin(fa) * 3.2, -1.2)
            m.tube(top, mid, 0.12, 0.08, REED, REED, 4)
            m.tube(mid, end, 0.08, 0.02, REED, REED_TIP, 4)


def _glassfield(m, rng):
    disc(m, Point3(0, 0, 0.04), 9.0, GLASS_DEEP * 0.9, SANDSTONE * 0.95, 24)
    for _ in range(17):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0, 8.0)
        p = Point3(math.cos(a) * d, math.sin(a) * d, -0.2)
        pts = [p]
        height = rng.uniform(1.5, 4.2)
        for s in range(4):
            p = p + Vec3(rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35), height / 4)
            pts.append(p)
        chain(m, pts, rng.uniform(0.18, 0.32), 0.03, GLASS_DEEP, GLASS, 5)
        if rng.random() < 0.6:                                  # a branch
            b = pts[2]
            m.tube(b, b + Vec3(rng.uniform(-0.9, 0.9), rng.uniform(-0.9, 0.9), rng.uniform(0.4, 1.0)),
                   0.09, 0.02, GLASS_DEEP, GLASS, 4)


def _hoodoos(m, rng):
    for t in range(rng.randint(4, 5)):
        a = 2 * math.pi * t / 5 + rng.uniform(-0.4, 0.4)
        d = rng.uniform(3.0, 9.5)
        x, y = math.cos(a) * d, math.sin(a) * d
        z = 0.0
        stack = rng.randint(4, 6)
        width = rng.uniform(2.2, 3.0)
        for k in range(stack):
            h = rng.uniform(2.4, 3.6)
            w = width * (1.0 - 0.1 * k)
            rock(m, Point3(x + rng.uniform(-0.3, 0.3), y + rng.uniform(-0.3, 0.3), z + h * 0.5), w, w * 0.9,
                 h * 0.6, SANDSTONE if k % 2 else SANDSTONE_DARK, rng, 0.14, dark=SANDSTONE_DARK)
            z += h * 0.88
        rock(m, Point3(x, y, z + 0.7), width * 1.35, width * 1.2, 1.0, STONE, rng, 0.1, dark=STONE_DARK)


def _ring(m, rng):
    n = 9
    stones = []
    for k in range(n):
        a = 2 * math.pi * k / n
        fallen = k in (3, 7)
        h = rng.uniform(4.2, 6.0)
        c = Point3(math.cos(a) * 10.0, math.sin(a) * 10.0, 0)
        heading = math.degrees(a) + 90
        if fallen:
            box(m, c + Vec3(0, 0, 0.5), 1.3, h, 1.0, STONE, heading + rng.uniform(-20, 20), 0, STONE_DARK)
        else:
            box(m, c + Vec3(0, 0, h / 2 - 0.3), 1.3, 0.9, h, STONE, heading, rng.uniform(-6, 6), STONE_DARK)
        stones.append((c, h, fallen))
    for k in (0, 5):                                            # two lintels
        (c1, h1, _), (c2, h2, _) = stones[k], stones[(k + 1) % n]
        mid = (c1 + c2) * 0.5
        top = min(h1, h2) - 0.3
        heading = math.degrees(math.atan2(c2.y - c1.y, c2.x - c1.x))
        box(m, Point3(mid.x, mid.y, top + 0.45), (c2 - c1).length() + 1.6, 1.0, 0.9, STONE, heading, 0, STONE_DARK)
    box(m, Point3(0, 0, 0.35), 3.2, 2.0, 0.8, STONE_DARK, rng.uniform(0, 180), 0, STONE_DARK * 0.8)


def _wreck(m, rng):
    def skip(r, k):
        return r <= 2 and 3 <= k <= 9                            # split open along the top

    def shade(r, k, c):
        return _mix(HUSK, HUSK_DARK, abs(math.sin(k * 0.8)) * 0.5 + r / 10 * 0.3)

    m.ellipsoid(Point3(0, 0, 2.6), 4.4, 13.5, 4.2, HUSK, rings=10, segments=16, phi_max=math.pi, skip=skip, shade=shade)
    for i in range(7):                                          # glassy ribs arching over the split
        y = -9 + i * 3.0
        pts = [Point3(-4.2 * math.cos(math.pi * s / 6), y, 2.6 + 5.8 * math.sin(math.pi * s / 6)) for s in range(7)]
        chain(m, pts, 0.35, 0.35, GLASS_DEEP, GLASS, 6)
    m.ellipsoid(Point3(6.5, -4, 1.4), 1.6, 1.6, 1.6, GLASS, rings=6, segments=10)       # the lens, fallen out
    for _ in range(5):                                          # dried tendrils
        a = rng.uniform(-0.6, 0.6)
        p = Point3(rng.uniform(-2, 2), 13, 0.4)
        pts = [p]
        for s in range(5):
            p = p + Vec3(math.sin(a) * 2 + rng.uniform(-0.5, 0.5), 2.0, 0)
            pts.append(Point3(p.x, p.y, 0.25))
        chain(m, pts, 0.3, 0.06, HUSK_DARK, HUSK, 5)


def _camp(m, rng):
    for k in range(3):                                          # little huts, not shelters for you
        a = 2 * math.pi * k / 3 + 0.4
        c = Point3(math.cos(a) * 5.0, math.sin(a) * 5.0, 0)
        door = math.degrees(a + math.pi) % 360

        def skip(r, s, door=door):
            th = 360.0 * (s + 0.5) / 12
            return r >= 3 and abs((th - door + 180) % 360 - 180) < 30

        m.ellipsoid(c, 1.5, 1.5, 1.3, THATCH, rings=5, segments=12, phi_max=math.pi / 2, skip=skip,
                    shade=lambda r, s, col: _mix(col, THATCH * 0.75, (s % 2) * 0.4))
    for k in range(9):                                          # cold fire pit
        a = 2 * math.pi * k / 9
        rock(m, Point3(math.cos(a) * 1.1, math.sin(a) * 1.1, 0.05), 0.3, 0.26, 0.22, STONE, rng, 0.2, dark=STONE_DARK)
    disc(m, Point3(0, 0, 0.03), 0.9, CHAR, CHAR * 1.4, 12)
    for side in (-1, 1):                                        # drying rack
        m.tube(Point3(side * 1.6, -3.2, 0), Point3(side * 1.6, -3.2, 2.1), 0.06, 0.05, SANDSTONE_DARK, SANDSTONE_DARK, 5)
    m.tube(Point3(-1.8, -3.2, 2.0), Point3(1.8, -3.2, 2.0), 0.05, 0.05, SANDSTONE_DARK, SANDSTONE_DARK, 5)
    for i in range(6):
        x = -1.3 + i * 0.52
        m.tube(Point3(x, -3.2, 2.0), Point3(x + rng.uniform(-0.1, 0.1), -3.2, rng.uniform(0.9, 1.4)), 0.035, 0.02,
               THATCH, REED_TIP, 4)
    m.tube(Point3(3.2, 2.5, 0), Point3(3.2, 2.5, 2.6), 0.09, 0.07, BONE_DARK, BONE, 5)     # a bone totem
    m.ellipsoid(Point3(3.2, 2.5, 2.9), 0.35, 0.4, 0.32, BONE, rings=5, segments=8)


def _statue(m, rng):
    def st(r, k, c):
        return _mix(c, INDIGO_STONE_DARK, 0.25 + 0.25 * math.sin(k * 1.7 + r))

    box(m, Point3(0, 1, 1.0), 20.0, 16.0, 2.0, STONE, 0, 0, STONE_DARK)                  # plinth
    for side in (-1, 1):
        m.tube(Point3(side * 3.6, -0.5, 4.2), Point3(side * 8.5, 5.5, 3.6), 2.8, 2.4, INDIGO_STONE_DARK, INDIGO_STONE, 9)
        m.tube(Point3(side * 8.5, 5.5, 3.6), Point3(-side * 2.5, 7.5, 3.0), 2.3, 1.8, INDIGO_STONE, INDIGO_STONE_DARK, 9)
        m.tube(Point3(side * 5.6, 0.2, 16.5), Point3(side * 7.4, 3.2, 10.5), 1.8, 1.6, INDIGO_STONE, INDIGO_STONE_DARK, 8)
        m.tube(Point3(side * 7.4, 3.2, 10.5), Point3(side * 6.2, 6.4, 5.6), 1.6, 1.3, INDIGO_STONE_DARK, INDIGO_STONE, 8)
        m.ellipsoid(Point3(side * 5.8, 6.8, 5.2), 1.5, 1.8, 1.0, INDIGO_STONE, rings=5, segments=10)
    m.ellipsoid(Point3(0, 0, 11.5), 5.8, 4.0, 7.2, INDIGO_STONE, rings=8, segments=14, shade=st)
    m.tube(Point3(0, 0, 17.5), Point3(0, 0.3, 19.6), 1.5, 1.4, INDIGO_STONE_DARK, INDIGO_STONE, 8)
    m.ellipsoid(Point3(0, 0.6, 22.6), 2.9, 3.3, 3.9, INDIGO_STONE, rings=8, segments=14, shade=st)
    for side in (-1, 1):                                        # closed eyes: two dark lines
        m.tube(Point3(side * 0.5, 3.5, 23.1), Point3(side * 1.7, 3.2, 23.0), 0.14, 0.12,
               INDIGO_STONE_DARK * 0.7, INDIGO_STONE_DARK * 0.7, 4)
    for _ in range(6):                                          # sand drifted against the plinth
        a = rng.uniform(0, 2 * math.pi)
        rock(m, Point3(math.cos(a) * 10.5, math.sin(a) * 9 + 1, 0.2), rng.uniform(2, 4), rng.uniform(1.5, 3),
             0.9, SANDSTONE, rng, 0.1, dark=SANDSTONE_DARK, phi_max=math.pi / 2)


def _hand(m, rng):
    m.tube(Point3(0, 0, -1.5), Point3(0.4, 0.2, 4.5), 2.6, 2.3, SANDSTONE_DARK, SANDSTONE, 9)        # wrist
    m.ellipsoid(Point3(0.5, 0.3, 7.2), 3.4, 1.8, 3.6, SANDSTONE, rings=7, segments=12)                # palm
    for f in range(4):
        x = -2.3 + f * 1.55
        base = Point3(x, 0.3, 10.2)
        curl = rng.uniform(0.25, 0.6)
        length = (3.2, 3.8, 3.6, 2.9)[f]
        pts = [base]
        ang = 0.0
        for _s in range(3):
            ang += curl
            pts.append(pts[-1] + Vec3(0, math.sin(ang) * length, math.cos(ang) * length))
        chain(m, pts, 0.75, 0.55, SANDSTONE, SANDSTONE_DARK, 7)
    thumb = [Point3(3.4, 0.6, 6.5), Point3(5.2, 2.0, 8.8), Point3(5.6, 3.6, 10.6)]
    chain(m, thumb, 0.85, 0.6, SANDSTONE, SANDSTONE_DARK, 7)
    for _ in range(6):
        a = rng.uniform(0, 2 * math.pi)
        rock(m, Point3(math.cos(a) * 4.5, math.sin(a) * 4.5, 0.2), rng.uniform(1.2, 2.2), rng.uniform(1.0, 1.8),
             0.8, SANDSTONE, rng, 0.14, dark=SANDSTONE_DARK, phi_max=math.pi / 2)


def _tree(m, rng):
    pts, p = [], Point3(0, 0, -1.0)
    for i in range(8):                                          # a twisting petrified trunk
        pts.append(p)
        p = p + Vec3(math.sin(i * 0.7) * 0.6, math.cos(i * 0.5) * 0.5, 2.4)
    chain(m, pts, 2.4, 0.7, PETRIFIED_DARK, PETRIFIED, 9)
    for k in range(6):                                          # bare limbs
        base = pts[3 + k % 5]
        a = rng.uniform(0, 2 * math.pi)
        limb = [base]
        for s in range(3):
            limb.append(limb[-1] + Vec3(math.cos(a) * 2.2, math.sin(a) * 2.2, rng.uniform(0.6, 1.8)))
            a += rng.uniform(-0.5, 0.5)
        chain(m, limb, 0.7 - k * 0.05, 0.12, PETRIFIED, PETRIFIED_DARK, 6)
    for k in range(6):                                          # roots arching into the sand
        a = 2 * math.pi * k / 6 + rng.uniform(-0.3, 0.3)
        d = rng.uniform(4.5, 7.0)
        root = [Point3(math.cos(a) * 1.2, math.sin(a) * 1.2, 1.0), Point3(math.cos(a) * d * 0.6, math.sin(a) * d * 0.6, 1.2),
                Point3(math.cos(a) * d, math.sin(a) * d, -0.4)]
        chain(m, root, 0.9, 0.3, PETRIFIED_DARK, PETRIFIED, 6)


def _nest(m, rng):
    for layer in range(4):                                      # woven ring of reed and bone
        z = 0.4 + layer * 0.7
        for k in range(26):
            a0 = 2 * math.pi * k / 26 + layer * 0.3
            a1 = a0 + rng.uniform(0.35, 0.6)
            r0, r1 = 7.0 + rng.uniform(-0.5, 0.5), 7.0 + rng.uniform(-0.5, 0.5)
            col = BONE if rng.random() < 0.25 else THATCH
            m.tube(Point3(math.cos(a0) * r0, math.sin(a0) * r0, z + rng.uniform(-0.3, 0.3)),
                   Point3(math.cos(a1) * r1, math.sin(a1) * r1, z + rng.uniform(-0.3, 0.3)), 0.22, 0.18, col, col * 0.85, 5)
    disc(m, Point3(0, 0, 0.08), 6.8, THATCH * 0.8, THATCH, 20)
    for k in range(3):                                          # broken egg shells, huge
        a = 2 * math.pi * k / 3 + rng.uniform(-0.3, 0.3)

        def skip(r, s, k=k):
            return r >= 3 and (s + k * 3) % 12 < 5

        m.ellipsoid(Point3(math.cos(a) * 3.0, math.sin(a) * 3.0, 0.0), 1.8, 1.8, 2.3, PALE, rings=6, segments=12,
                    phi_max=math.pi * 0.62, skip=skip)


def _tower(m, rng):
    z, lean = 0.0, rng.uniform(-6, 6)
    for k in range(14):                                         # stepped, spiralling blocks
        h = 1.4
        a = k * 0.55
        off = Vec3(math.sin(math.radians(lean)) * z * 0.18, 0, 0)
        width = 6.0 - k * 0.12
        if k == 3:                                              # the doorway course
            for side in (-1, 1):
                box(m, Point3(side * width * 0.32, 0, z + h / 2) + off, width * 0.36, width, h, SANDSTONE, math.degrees(a) * 0.1, 0, SANDSTONE_DARK)
        elif k < 13 or rng.random() < 0.5:
            box(m, Point3(0, 0, z + h / 2) + off, width, width, h, SANDSTONE if k % 2 else SANDSTONE_DARK,
                math.degrees(a) * 0.1 + rng.uniform(-3, 3), 0, SANDSTONE_DARK)
        z += h
    for _ in range(7):                                          # fallen blocks
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(5, 10)
        box(m, Point3(math.cos(a) * d, math.sin(a) * d, 0.5), 1.8, 1.4, 1.0, SANDSTONE_DARK, rng.uniform(0, 90),
            rng.uniform(-15, 15), SANDSTONE_DARK * 0.8)


def _saltflat(m, rng):
    disc(m, Point3(0, 0, 0.06), 15.0, SALT, SALT * 0.92, 32)
    for _ in range(26):                                         # salt plates pushed up like broken ice
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(1, 13)
        box(m, Point3(math.cos(a) * d, math.sin(a) * d, 0.25), rng.uniform(1.2, 2.6), rng.uniform(0.9, 2.0), 0.18,
            SALT_BLUE if rng.random() < 0.4 else SALT, rng.uniform(0, 180), rng.uniform(8, 38), SALT * 0.85)
    for _ in range(4):                                          # salt pillars
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(4, 11)
        c = Point3(math.cos(a) * d, math.sin(a) * d, 0)
        h = rng.uniform(2.0, 4.5)
        m.tube(c, c + Vec3(0, 0, h), 0.8, 0.35, SALT, SALT_BLUE, 7)


def _totems(m, rng):
    for k in range(7):                                          # a line of carved poles, leaning one way (+Y)
        c = Point3(rng.uniform(-0.6, 0.6), -12 + k * 4.0, 0)
        h = rng.uniform(3.4, 5.0)
        lean = Vec3(0, 0.35, 0)
        m.tube(c, c + Vec3(0, 0, h) + lean * h * 0.3, 0.3, 0.24, PETRIFIED_DARK, PETRIFIED, 6)
        for b in range(3):                                      # painted bands and carved heads
            z = 1.2 + b * (h - 1.6) / 3
            p = c + Vec3(0, 0, z) + lean * z * 0.3
            m.ellipsoid(p, 0.42, 0.42, 0.34, PAINT[(k + b) % 3], rings=4, segments=8)
        m.ellipsoid(c + Vec3(0, 0, h + 0.3) + lean * h * 0.3, 0.45, 0.5, 0.5, BONE, rings=5, segments=8)
    for _ in range(5):                                          # small offerings
        a = rng.uniform(0, 2 * math.pi)
        rock(m, Point3(math.cos(a) * 1.5, -12 + rng.uniform(0, 24), 0.1), 0.25, 0.22, 0.18, STONE, rng, 0.2)


def _bones(m, rng):
    phase = rng.uniform(0, 2 * math.pi)
    for i in range(34):                                         # a sea-serpent's spine, diving through the sand
        t = i / 33.0
        x = -20 + 40 * t
        y = math.sin(t * 4.5 + phase) * 5.0
        z = 3.2 * math.sin(t * math.pi * 3.0) - 0.4
        if z < -0.6:
            continue
        c = Point3(x, y, max(z, -0.2))
        m.ellipsoid(c, 0.9, 0.7, 0.7, BONE, rings=4, segments=8)
        if i % 2 == 0:
            m.tube(c + Vec3(0, 0, 0.4), c + Vec3(0, 0, 2.0), 0.28, 0.08, BONE, BONE_DARK, 5)        # spine
            for side in (-1, 1):
                m.tube(c, c + Vec3(0, side * 2.4, -1.2), 0.22, 0.06, BONE, BONE_DARK, 5)          # ribs
    m.ellipsoid(Point3(21.5, math.sin(4.5 + phase) * 5.0, 0.6), 2.2, 1.6, 1.4, BONE, rings=6, segments=10)  # skull


def _bloom_bed(m, rng):
    disc(m, Point3(0, 0, 0.05), 3.4, SOIL, SOIL * 1.3, 18)
    for k in range(11):                                         # a ring of pale stones
        a = 2 * math.pi * k / 11 + rng.uniform(-0.1, 0.1)
        rock(m, Point3(math.cos(a) * 3.8, math.sin(a) * 3.8, 0.1), rng.uniform(0.5, 0.9), rng.uniform(0.4, 0.7),
             rng.uniform(0.4, 0.8), SALT, rng, 0.25, dark=STONE)


def _bloom(m, rng):
    _bloom_bed(m, rng)
    stalk = [Point3(0, 0, 0), Point3(0.15, 0.08, 1.0), Point3(0.08, 0.3, 2.0), Point3(-0.2, 0.7, 2.7)]
    chain(m, stalk, 0.10, 0.05, PALE_LEAF, PALE_VEIN, 6)
    head = stalk[-1]
    for k in range(7):                                          # a drooping bell of pale petals
        a = 2 * math.pi * k / 7
        mid = head + Vec3(math.cos(a) * 0.45, math.sin(a) * 0.45 + 0.1, -0.35)
        tip = head + Vec3(math.cos(a) * 0.75, math.sin(a) * 0.75 + 0.2, -0.95)
        m.tube(head, mid, 0.20, 0.16, PALE, PALE, 5)
        m.tube(mid, tip, 0.16, 0.03, PALE, PALE_VEIN, 5)
    m.ellipsoid(head + Vec3(0, 0.05, -0.15), 0.26, 0.26, 0.3, PALE, rings=5, segments=10)
    for k in range(3):                                          # two small buds on side stems
        base = stalk[1] + Vec3(0, 0, 0.3 * k)
        a = rng.uniform(0, 2 * math.pi)
        bud = base + Vec3(math.cos(a) * 0.5, math.sin(a) * 0.5, 0.4)
        m.tube(base, bud, 0.04, 0.03, PALE_LEAF, PALE_LEAF, 4)
        m.ellipsoid(bud, 0.09, 0.09, 0.14, PALE, rings=4, segments=6)
    for k in range(6):                                          # broad pale leaves
        a = 2 * math.pi * k / 6 + 0.3
        m.tube(Point3(0, 0, 0.05), Point3(math.cos(a) * 1.3, math.sin(a) * 1.3, 0.45), 0.24, 0.05, PALE_LEAF, PALE_VEIN, 4)


def _bloom_gone(m, rng):
    _bloom_bed(m, rng)
    m.tube(Point3(0, 0, 0), Point3(0.08, 0.04, 0.35), 0.06, 0.04, PALE_LEAF, SOIL, 5)     # a torn stub


# ---------------------------------------------------------------- Pass 51: the deep desert
LANTERN = Vec4(0.98, 0.84, 0.52, 1.0)          # pale gold; the node is lifted out of the night tint
LANTERN_CORE = Vec4(1.0, 0.95, 0.78, 1.0)
AMETHYST = Vec4(0.62, 0.48, 0.78, 1.0)
AMETHYST_PALE = Vec4(0.86, 0.78, 0.94, 1.0)
RED_STONE = Vec4(0.66, 0.30, 0.24, 1.0)
RED_STONE_DARK = Vec4(0.42, 0.18, 0.16, 1.0)
DEEP_WATER = Vec4(0.10, 0.14, 0.20, 1.0)
MUD = Vec4(0.58, 0.46, 0.38, 1.0)


def _lanterns(m, rng):
    """A ring of small standing stones with pale-gold crowns: only seen by night."""
    for k in range(9):
        a = 2 * math.pi * k / 9 + rng.uniform(-0.08, 0.08)
        c = Point3(math.cos(a) * 6.5, math.sin(a) * 6.5, 0)
        h = rng.uniform(1.2, 2.0)
        m.tube(c, c + Vec3(0, 0, h), 0.42, 0.30, STONE_DARK, STONE, 6)
        m.ellipsoid(c + Vec3(0, 0, h + 0.22), 0.34, 0.34, 0.30, LANTERN, rings=4, segments=8)
    m.ellipsoid(Point3(0, 0, 0.0), 0.9, 0.9, 0.7, LANTERN_CORE, rings=5, segments=10, phi_max=math.pi / 2)
    for k in range(14):                                         # scattered glowing pebbles
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(1.5, 5.5)
        m.ellipsoid(Point3(math.cos(a) * d, math.sin(a) * d, 0.05), 0.16, 0.14, 0.10, LANTERN, rings=3, segments=6)


def _geode(m, rng):
    """A boulder of grey rock split in two and fallen open: the insides lined with violet crystal."""
    for side in (-1, 1):
        c = Point3(side * 4.6, 0, -0.3)
        face = 180.0 if side > 0 else 0.0                     # the broken face looks at the other half

        def open_face(r, k, face=face):
            th = 360.0 * (k + 0.5) / 16
            return abs((th - face + 180) % 360 - 180) < 62

        m.ellipsoid(c, 3.8, 4.4, 5.6, STONE, rings=7, segments=16, phi_max=math.pi * 0.56, skip=open_face,
                    shade=lambda r, k, col: _mix(STONE, STONE_DARK, 0.15 + 0.5 * ((k * 5 + r * 3) % 7) / 7))
        m.ellipsoid(c, 3.3, 3.9, 5.0, AMETHYST, rings=6, segments=16, phi_max=math.pi * 0.56,
                    shade=lambda r, k, col: _mix(AMETHYST_PALE, AMETHYST, r / 6.0))   # the lining, seen through the break
        for _ in range(12):                                     # crystals pointing out of the break
            z = rng.uniform(0.4, 4.2)
            y = rng.uniform(-2.8, 2.8)
            base = c + Vec3(-side * 2.6, y, z)
            m.tube(base, base + Vec3(-side * rng.uniform(0.9, 1.8), rng.uniform(-0.4, 0.4), rng.uniform(-0.2, 0.7)),
                   0.34, 0.02, AMETHYST, AMETHYST_PALE, 5)
    for _ in range(6):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(7, 10)
        rock(m, Point3(math.cos(a) * d, math.sin(a) * d, 0.2), 0.7, 0.6, 0.5, STONE, rng, 0.2, dark=STONE_DARK)
    for _ in range(10):                                         # loose crystal on the sand between the halves
        p = Point3(rng.uniform(-1.2, 1.2), rng.uniform(-3, 3), 0.1)
        m.tube(p, p + Vec3(rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(0.3, 0.8)), 0.16, 0.02,
               AMETHYST, AMETHYST_PALE, 5)


def _small_hut(m, c: Point3, r: float, sunk: float, rng, colour=THATCH):
    door = rng.uniform(0, 360)

    def skip(rr, s):
        th = 360.0 * (s + 0.5) / 12
        return rr >= 3 and abs((th - door + 180) % 360 - 180) < 28

    m.ellipsoid(c + Vec3(0, 0, -sunk), r, r, r * 0.9, colour, rings=5, segments=12, phi_max=math.pi / 2,
                skip=skip, shade=lambda rr, s, col: _mix(col, col * 0.72, (s % 2) * 0.4 + rr * 0.05))


def _village(m, rng):
    """The sunken village: a dozen huts of dried mud, half drowned in sand."""
    for k in range(12):
        a = 2 * math.pi * k / 12 + rng.uniform(-0.2, 0.2)
        d = rng.uniform(8, 19)
        _small_hut(m, Point3(math.cos(a) * d, math.sin(a) * d, 0), rng.uniform(1.4, 2.2), rng.uniform(0.2, 1.1), rng,
                   MUD if k % 3 else THATCH)
    for k in range(16):                                         # the old wall, mostly buried
        a0 = 2 * math.pi * k / 16
        if rng.random() < 0.3:
            continue
        c = Point3(math.cos(a0) * 22.5, math.sin(a0) * 22.5, 0.35)
        box(m, c, 8.0, 0.8, rng.uniform(0.5, 1.4), MUD, math.degrees(a0) + 90, rng.uniform(-6, 6), MUD * 0.78)
    for k in range(9):                                          # the village well
        a = 2 * math.pi * k / 9
        rock(m, Point3(math.cos(a) * 1.2, math.sin(a) * 1.2, 0.2), 0.45, 0.4, 0.45, STONE, rng, 0.15, dark=STONE_DARK)
    disc(m, Point3(0, 0, 0.06), 0.9, DEEP_WATER, DEEP_WATER, 12)
    for _ in range(10):                                         # pots
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(3, 17)
        m.ellipsoid(Point3(math.cos(a) * d, math.sin(a) * d, 0.25), 0.35, 0.35, 0.42, SANDSTONE, rings=5, segments=8)


def _titan(m, rng):
    """The Sleeping Titan: the bones of a giant far bigger than Indigo, lying curled."""
    arc = []
    for i in range(26):                                         # spine: a curled arc
        t = i / 25.0
        a = math.radians(-40 + 250 * t)
        r = 20.0 - 5.0 * t
        z = 2.2 + 1.6 * math.sin(t * math.pi)
        arc.append(Point3(math.cos(a) * r, math.sin(a) * r, z))
    for i, c in enumerate(arc):
        m.ellipsoid(c, 1.5, 1.5, 1.3, BONE, rings=4, segments=8)
        if i % 2 == 0:
            m.tube(c, c + Vec3(0, 0, 3.0), 0.5, 0.15, BONE, BONE_DARK, 5)
    for i in range(4, 16):                                      # ribs arching up and over
        c = arc[i]
        out = Vec3(c.x, c.y, 0)
        out.normalize()
        inward = -out
        top = c + inward * 6.0 + Vec3(0, 0, 12.0 + 3.0 * math.sin(i / 16 * math.pi))
        end = c + inward * 12.0 + Vec3(0, 0, rng.uniform(0.5, 3.5))
        chain(m, [c, c + inward * 1.5 + Vec3(0, 0, 7.0), top, end], 0.9, 0.35, BONE, BONE_DARK, 6)
    head = arc[0] + Vec3(2.0, -5.0, 3.0)                        # the skull, resting on the sand
    m.ellipsoid(head, 6.5, 8.0, 5.5, BONE, rings=7, segments=16, phi_max=math.pi * 0.62,
                skip=lambda r, k: r in (2, 3) and k % 8 in (2, 5),
                shade=lambda r, k, c: _mix(BONE, BONE_DARK, r / 7.0 * 0.7))
    for side in (-1, 1):                                        # an arm bone, the hand open on the sand
        s = arc[18]
        elbow = s + Vec3(side * 6.0, -8.0, 1.0)
        wrist = elbow + Vec3(side * 3.0, -9.0, -1.0)
        chain(m, [s, elbow, wrist], 1.4, 1.0, BONE, BONE_DARK, 7)
        for f in range(4):
            m.tube(wrist, wrist + Vec3(side * (f - 1.5) * 1.3, -4.5, -0.6), 0.45, 0.2, BONE, BONE_DARK, 5)


def _well(m, rng):
    """The Sky Well: a round mouth of cut stone, a dark water far below, broken pillars round it."""
    for k in range(20):                                         # the rim
        a = 2 * math.pi * k / 20
        box(m, Point3(math.cos(a) * 5.4, math.sin(a) * 5.4, 0.75), 1.8, 1.0, 1.5, STONE if k % 2 else STONE_DARK,
            math.degrees(a) + 90, 0, STONE_DARK)
    m.tube(Point3(0, 0, 1.2), Point3(0, 0, 0.3), 4.95, 4.95, STONE_DARK, DEEP_WATER, 24)   # the inner wall, going down
    disc(m, Point3(0, 0, 0.32), 4.95, DEEP_WATER * 0.7, DEEP_WATER * 1.5, 24)             # dark water far below
    for k in range(8):                                          # pillars, some fallen
        a = 2 * math.pi * k / 8 + 0.2
        c = Point3(math.cos(a) * 12.5, math.sin(a) * 12.5, 0)
        if rng.random() < 0.3:
            box(m, c + Vec3(0, 0, 0.7), 8.0, 1.4, 1.4, STONE, math.degrees(a) + rng.uniform(40, 140), 0, STONE_DARK)
            continue
        h = rng.uniform(6.5, 9.5)
        m.tube(c, c + Vec3(0, 0, h), 0.9, 0.8, STONE_DARK, STONE, 8)
        box(m, c + Vec3(0, 0, h + 0.3), 2.2, 2.2, 0.6, STONE, math.degrees(a), 0, STONE_DARK)
    for k in range(4):                                          # steps leading down to the rim
        a = 2 * math.pi * k / 4
        for st in range(3):
            d = 7.0 + st * 1.1
            box(m, Point3(math.cos(a) * d, math.sin(a) * d, 0.25 - st * 0.07), 2.4, 1.0, 0.5 - st * 0.14, STONE,
                math.degrees(a) + 90, 0, STONE_DARK)


def _city(m, rng):
    """The Small City: walls, lanes and a hundred little huts - everything the size of you."""
    for k in range(40):                                         # the wall
        a0 = 2 * math.pi * k / 40
        if k % 10 == 0:
            continue                                            # gates
        c = Point3(math.cos(a0) * 52.0, math.sin(a0) * 52.0, 1.3)
        box(m, c, 8.4, 1.2, rng.uniform(1.8, 3.2), MUD, math.degrees(a0) + 90, rng.uniform(-3, 3), MUD * 0.75)
    for ring, count in ((14.0, 10), (24.0, 16), (34.0, 22), (44.0, 26)):
        for k in range(count):
            a = 2 * math.pi * k / count + rng.uniform(-0.05, 0.05) + ring
            if (k % max(1, count // 4)) == 0:
                continue                                        # lanes to the centre
            _small_hut(m, Point3(math.cos(a) * ring, math.sin(a) * ring, 0), rng.uniform(1.3, 2.0),
                       rng.uniform(0.0, 0.9), rng, MUD if (k + int(ring)) % 3 else THATCH)
    z = 0.0                                                     # the stepped house in the middle
    for step in range(6):
        w = 12.0 - step * 1.8
        box(m, Point3(0, 0, z + 1.0), w, w, 2.0, SANDSTONE if step % 2 else SANDSTONE_DARK, 0, 0, SANDSTONE_DARK)
        z += 2.0
    m.tube(Point3(0, 0, z), Point3(0, 0, z + 3.0), 0.12, 0.08, BONE_DARK, BONE, 5)
    m.ellipsoid(Point3(0, 0, z + 3.3), 0.5, 0.5, 0.5, PAINT[0], rings=4, segments=8)


def _cradle(m, rng):
    """The Red Cradle: a vast broken egg of red stone. The red one began here."""
    def skip(r, k):
        return r <= 1 or (r == 2 and k % 5 in (1, 3)) or (r == 3 and k % 9 == 4)

    m.ellipsoid(Point3(0, 0, -1.0), 11.0, 10.0, 10.0, RED_STONE, rings=8, segments=22, phi_max=math.pi * 0.62,
                skip=skip, shade=lambda r, k, c: _mix(RED_STONE, RED_STONE_DARK, 0.2 + 0.4 * ((k * 7 + r * 3) % 5) / 5))
    for _ in range(14):                                         # shards of shell
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(12, 22)
        box(m, Point3(math.cos(a) * d, math.sin(a) * d, 0.4), rng.uniform(2, 4.5), rng.uniform(1.5, 3), 0.5,
            RED_STONE, rng.uniform(0, 180), rng.uniform(10, 50), RED_STONE_DARK)
    for k in range(6):                                          # little scratched posts: the small people saw it
        a = 2 * math.pi * k / 6 + 0.3
        c = Point3(math.cos(a) * 16.0, math.sin(a) * 16.0, 0)
        m.tube(c, c + Vec3(0, 0, 2.6), 0.18, 0.14, PETRIFIED_DARK, PETRIFIED, 5)
        m.ellipsoid(c + Vec3(0, 0, 2.8), 0.3, 0.3, 0.3, PAINT[0], rings=4, segments=8)


BUILDERS = {'tree': _tree, 'nest': _nest, 'tower': _tower, 'saltflat': _saltflat, 'totems': _totems,
            'bones': _bones, 'bloom': _bloom, 'bloom_gone': _bloom_gone, 'skull': _skull, 'arch': _arch, 'oasis': _oasis, 'glassfield': _glassfield, 'hoodoos': _hoodoos,
            'ring': _ring, 'wreck': _wreck, 'camp': _camp, 'statue': _statue, 'hand': _hand,
            'lanterns': _lanterns, 'geode': _geode, 'village': _village, 'titan': _titan, 'well': _well,
            'city': _city, 'cradle': _cradle}


def build_place(kind: str, seed: int) -> NodePath:
    rng = random.Random(seed)
    m = Mesh(f'place_{kind}')
    BUILDERS[kind](m, rng)
    np_ = m.node()
    np_.setTwoSided(True)
    return np_
