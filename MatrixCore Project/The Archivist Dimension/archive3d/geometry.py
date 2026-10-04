from __future__ import annotations

import math
from panda3d.core import (
    Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
    GeomVertexWriter, NodePath, TransparencyAttrib, Vec3,
)


def make_box(parent: NodePath, name: str, size=(1.0, 1.0, 1.0), pos=(0, 0, 0), color=(1, 1, 1, 1), transparency=False, texture=None) -> NodePath:
    sx, sy, sz = (float(v) for v in size)
    x0, x1 = -sx * 0.5, sx * 0.5
    y0, y1 = -sy * 0.5, sy * 0.5
    z0, z1 = -sz * 0.5, sz * 0.5
    verts = [
        (x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
        (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1),
    ]
    faces = [(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7)]
    fmt = GeomVertexFormat.getV3n3c4t2()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vdata.setNumRows(24)
    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")
    tw = GeomVertexWriter(vdata, "texcoord")
    prim = GeomTriangles(Geom.UHStatic)
    row = 0
    face_normals = [(0,0,-1),(0,0,1),(0,-1,0),(1,0,0),(0,1,0),(-1,0,0)]
    uvs = ((0,0),(1,0),(1,1),(0,1))
    for face, normal in zip(faces, face_normals):
        for idx, uv in zip(face, uvs):
            vw.addData3f(*verts[idx]); nw.addData3f(*normal); cw.addData4f(*color); tw.addData2f(*uv)
        prim.addVertices(row,row+1,row+2); prim.addVertices(row,row+2,row+3); row += 4
    geom = Geom(vdata); geom.addPrimitive(prim)
    node = GeomNode(name); node.addGeom(geom)
    np = parent.attachNewNode(node); np.setPos(*pos)
    if texture is not None:
        np.setTexture(texture, 1)
    if transparency or color[3] < 0.999:
        np.setTransparency(TransparencyAttrib.MAlpha)
    return np


def make_uv_sphere(
    parent: NodePath,
    name: str,
    radius: float = 1.0,
    pos=(0,0,0),
    color=(1,1,1,1),
    *,
    segments: int = 28,
    rings: int = 16,
    texture=None,
    transparency: bool = False,
) -> NodePath:
    """Create a UV sphere with real UV coordinates so story art can wrap around it."""
    radius = float(radius)
    segments = max(8, int(segments))
    rings = max(4, int(rings))
    fmt = GeomVertexFormat.getV3n3c4t2()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    count = (rings + 1) * (segments + 1)
    vdata.setNumRows(count)
    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")
    tw = GeomVertexWriter(vdata, "texcoord")

    for r in range(rings + 1):
        v = r / rings
        phi = math.pi * v
        sp, cp = math.sin(phi), math.cos(phi)
        for s in range(segments + 1):
            u = s / segments
            theta = math.tau * u
            ct, st = math.cos(theta), math.sin(theta)
            nx, ny, nz = sp * ct, sp * st, cp
            vw.addData3f(nx * radius, ny * radius, nz * radius)
            nw.addData3f(nx, ny, nz)
            cw.addData4f(*color)
            tw.addData2f(u, 1.0 - v)

    prim = GeomTriangles(Geom.UHStatic)
    stride = segments + 1
    for r in range(rings):
        for s in range(segments):
            a = r * stride + s
            b = a + 1
            c = (r + 1) * stride + s
            d = c + 1
            if r != 0:
                prim.addVertices(a, c, b)
            if r != rings - 1:
                prim.addVertices(b, c, d)
    geom = Geom(vdata); geom.addPrimitive(prim)
    node = GeomNode(name); node.addGeom(geom)
    np = parent.attachNewNode(node); np.setPos(*pos)
    if texture is not None:
        np.setTexture(texture, 1)
    if transparency or color[3] < 0.999:
        np.setTransparency(TransparencyAttrib.MAlpha)
    return np


def make_beam_between(parent: NodePath, name: str, a, b, thickness=0.22, color=(1,1,1,1), transparency=False) -> NodePath:
    a = Vec3(*a); b = Vec3(*b)
    delta = b - a
    length = max(0.001, delta.length())
    root = parent.attachNewNode(name)
    root.setPos((a + b) * 0.5)
    root.lookAt(b)
    make_box(root, name + "_mesh", (float(thickness), length, float(thickness)), (0,0,0), color, transparency=transparency)
    return root


def make_ring_segments(parent: NodePath, name: str, radius=5.0, segments=32, thickness=0.10, depth=0.12, color=(1,1,1,1), transparency=False) -> NodePath:
    """Make a segmented ring in the local XY plane; caller can rotate the returned root."""
    root = parent.attachNewNode(name)
    radius = float(radius)
    segments = max(8, int(segments))
    arc = (math.tau * radius / segments) * 0.82
    for i in range(segments):
        a = math.tau * i / segments
        x, y = math.cos(a) * radius, math.sin(a) * radius
        seg = make_box(root, f"{name}_seg_{i:02d}", (float(thickness), arc, float(depth)), (x,y,0), color, transparency=transparency)
        seg.setH(math.degrees(a) + 90.0)
    return root


def make_arch(parent: NodePath, name: str, center, width=6.0, depth=1.0, height=8.0, thickness=0.6, color=(0.1,0.12,0.14,1)) -> NodePath:
    """Legacy helper kept for compatibility with older archive content."""
    root = parent.attachNewNode(name)
    x,y,z = center
    make_box(root, name+"_left", (thickness, depth, height), (-width*0.5+thickness*0.5,0,height*0.5), color)
    make_box(root, name+"_right", (thickness, depth, height), (width*0.5-thickness*0.5,0,height*0.5), color)
    make_box(root, name+"_top", (width, depth, thickness), (0,0,height-thickness*0.5), color)
    root.setPos(x,y,z)
    return root
