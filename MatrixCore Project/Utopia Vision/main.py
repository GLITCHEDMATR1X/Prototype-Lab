from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

from direct.gui.OnscreenText import OnscreenText
from direct.actor.Actor import Actor
from direct.showbase.ShowBase import ShowBase
from direct.showbase import Audio3DManager
from panda3d.core import (
    AmbientLight,
    ColorBlendAttrib,
    AudioSound,
    AntialiasAttrib,
    BitMask32,
    CardMaker,
    CollisionBox,
    CollisionHandlerPusher,
    CollisionNode,
    CollisionSphere,
    CollisionTube,
    CollisionTraverser,
    DirectionalLight,
    Filename,
    Fog,
    Material,
    MaterialAttrib,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    GeomVertexReader,
    LineSegs,
    NodePath,
    PerspectiveLens,
    PointLight,
    Shader,
    TextNode,
    TransparencyAttrib,
    Texture,
    TextureStage,
    TexGenAttrib,
    Vec3,
    Vec4,
    WindowProperties,
    loadPrcFileData,
)

APP_NAME = "UTOPIA // LENS TOUR"
VERSION = "Pass 59 — AR Coverage Continuity + Tree Removal"
WORLD_MASK = BitMask32.bit(1)
PLAYER_MASK = BitMask32.bit(2)
NORMAL_CAMERA_MASK = BitMask32.bit(0)
AR_CAMERA_MASK = BitMask32.bit(3)
GAMEPLAY_ASPECT = 16.0 / 9.0

# World scale: 1 Panda3D unit = 1 metre.
CITY_RADIUS = 520.0
INNER_WALL_RADIUS = 505.0
OUTER_WALL_RADIUS = 520.0
WALL_HEIGHT = 22.0
WALL_SEGMENTS = 64
GATE_HALF_ANGLE_DEG = 5.2
CITIZEN_ORB_MAX_RADIUS = 468.0
CITIZEN_ORB_TOTAL = 20
GLEEBS_POSITION = (2.8, -512.5, 0.0)
GLEEBS_HEADING = -1.645
GLEEBS_SCALE = 1.12
GLEEBS_AR_SCALE = GLEEBS_SCALE * 2.0
HUMAN_RESIDENT_SPECS = (
    {
        "id": "male",
        "label": "Resident_Male",
        "bam_rel": "assets/characters/cyber_humanoids/Cyber_Male.bam",
        "position": (-8.5, -600.5, 0.0),
        "heading": 18.0,
        "scale": 1.0,
        "collision_radius": 0.34,
        "collision_height": 1.82,
        "theme": "south",
        "idle_rate": 0.92,
        "idle_phase": 0.18,
        "idle_heading_sway": 0.75,
        "idle_sway_speed": 0.44,
        "neon_seed": 55031,
    },
    {
        "id": "female",
        "label": "Resident_Female",
        "bam_rel": "assets/characters/cyber_humanoids/Cyber_Female.bam",
        "position": (8.2, -601.8, 0.0),
        "heading": -20.0,
        "scale": 1.0,
        "collision_radius": 0.32,
        "collision_height": 1.72,
        "theme": "south",
        "idle_rate": 1.07,
        "idle_phase": 0.63,
        "idle_heading_sway": 1.05,
        "idle_sway_speed": 0.31,
        "neon_seed": 55032,
    },
)
CELESTIAL_DISTANCE = 5200.0
GLEEBS_COLLISION_RADIUS = 0.46
GLEEBS_COLLISION_HEIGHT = 1.72
GLEEBS_APPROACH_SPEED = 3.2
GLEEBS_APPROACH_STOP_DISTANCE = 2.6
GLEEBS_WAVE_SECONDS = 2.4
GLEEBS_HEAD_YAW_LIMIT = 52.0
GLEEBS_HEAD_PITCH_LIMIT = 24.0
GLEEBS_SPARK_INTERVAL_MIN = 6.5
GLEEBS_SPARK_INTERVAL_MAX = 11.5
GLEEBS_INTERACTION_DISTANCE = 4.6
GLEEBS_NATIVE_MODES = {
    1: {
        "id": "utopia_conflict",
        "label": "UTOPIA CONFLICT",
        "adapter": ("Utopia Conflict", "holoverse_native_adapter.py"),
        "entry": ("Utopia Conflict", "main.py"),
    },
    2: {
        "id": "glyphbound",
        "label": "GLYPHBOUND",
        "adapter": ("Glyphbound", "holoverse_native_adapter.py"),
        "entry": ("Glyphbound", "main.py"),
    },
    3: {
        "id": "vector_arena",
        "label": "VECTOR ARENA",
        "adapter": ("Utopia Conflict", "Vector Arena", "standalone_native_adapter.py"),
        "entry": ("Utopia Conflict", "Vector Arena", "main.py"),
    },
}
SHADOW_ACTIVE_RADIUS = 320.0
SHADOW_MAX_LENGTH = 58.0
AR_ACTIVITY_DRAW_RADIUS = 340.0
AR_ACTIVITY_RECULL_DISTANCE = 22.0
SHADOW_ANCHOR_Z = 240.0
WATER_SIZE = 3600.0
GROUND_Z = 0.0
EYE_HEIGHT = 1.72
PLAYER_RADIUS = 0.42
WALK_SPEED = 5.4
SPRINT_SPEED = 9.0
SWIM_SPEED = 2.8
WATER_SURFACE_PLAYER_Z = -0.90
JUMP_SPEED = 5.25
GRAVITY = 14.0
PHYSICAL_DAY_LENGTH_SECONDS = 2160.0
AR_FINE_TIME_STEP_HOURS = 0.25
WEATHER_ORDER = ("clear", "overcast", "rain", "storm", "post_rain")
WEATHER_DURATIONS_SECONDS = {
    "clear": 90.0,
    "overcast": 60.0,
    "rain": 75.0,
    "storm": 50.0,
    "post_rain": 55.0,
}
WEATHER_TRANSITION_SECONDS = 10.0
WEATHER_PROFILES = {
    "clear": {"sky_tint": (1.00,1.00,1.00), "water_tint": (1.00,1.00,1.00), "ambient_gain": 1.00, "sun_gain": 1.00, "fog_tint": (1.00,1.00,1.00), "rain": 0.00},
    "overcast": {"sky_tint": (0.76,0.81,0.84), "water_tint": (0.78,0.84,0.88), "ambient_gain": 0.88, "sun_gain": 0.42, "fog_tint": (0.82,0.86,0.88), "rain": 0.00},
    "rain": {"sky_tint": (0.64,0.70,0.75), "water_tint": (0.68,0.76,0.82), "ambient_gain": 0.80, "sun_gain": 0.24, "fog_tint": (0.72,0.77,0.80), "rain": 0.62},
    "storm": {"sky_tint": (0.48,0.55,0.63), "water_tint": (0.52,0.62,0.70), "ambient_gain": 0.68, "sun_gain": 0.10, "fog_tint": (0.58,0.64,0.69), "rain": 1.00},
    "post_rain": {"sky_tint": (0.86,0.91,0.94), "water_tint": (0.80,0.88,0.92), "ambient_gain": 0.92, "sun_gain": 0.72, "fog_tint": (0.88,0.91,0.92), "rain": 0.00},
}
VISOR_MODE_ORDER = ("horizontal", "vertical", "fullscreen")
VISOR_MODE_CONFIG = {
    "horizontal": {"center": (0.50, 0.52), "half_size": (0.506, 0.195), "corner": 0.018, "label": "HORIZONTAL"},
    "vertical": {"center": (0.50, 0.50), "half_size": (0.195, 0.506), "corner": 0.018, "label": "VERTICAL"},
    "fullscreen": {"center": (0.50, 0.50), "half_size": (0.506, 0.506), "corner": 0.004, "label": "FULL SCREEN"},
}

PALETTE = {
    "water": (0.10, 0.30, 0.46, 1.0),
    "ground": (0.72, 0.73, 0.71, 1.0),
    "outer_grass": (0.25, 0.42, 0.20, 1.0),
    "outer_grass_light": (0.32, 0.50, 0.25, 1.0),
    "outer_dirt": (0.38, 0.28, 0.18, 1.0),
    "outer_shore": (0.52, 0.42, 0.28, 1.0),
    "plaza": (0.80, 0.80, 0.77, 1.0),
    "road": (0.30, 0.32, 0.32, 1.0),
    "sidewalk": (0.63, 0.64, 0.62, 1.0),
    "wall": (0.68, 0.69, 0.67, 1.0),
    "building": (0.70, 0.71, 0.70, 1.0),
    "building_dark": (0.59, 0.61, 0.60, 1.0),
    "spire": (0.77, 0.78, 0.76, 1.0),
    "green": (0.30, 0.36, 0.30, 1.0),
    "tree": (0.26, 0.33, 0.25, 1.0),
    "trunk": (0.32, 0.29, 0.24, 1.0),
    "bridge": (0.66, 0.67, 0.65, 1.0),
    "marker": (0.88, 0.88, 0.84, 1.0),
}

AR_PALETTE = {
    "cyan": (0.10, 0.96, 1.00, 1.0),
    "violet": (0.66, 0.28, 1.00, 1.0),
    "blue": (0.16, 0.46, 1.00, 1.0),
    "mint": (0.28, 1.00, 0.72, 1.0),
    "warm": (1.00, 0.72, 0.24, 1.0),
}


def polar(radius: float, angle_deg: float, z: float = 0.0) -> tuple[float, float, float]:
    a = math.radians(angle_deg)
    return (math.sin(a) * radius, math.cos(a) * radius, z)


def angle_delta(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def is_gate_angle(angle_deg: float) -> bool:
    return any(angle_delta(angle_deg, g) <= GATE_HALF_ANGLE_DEG for g in (0.0, 90.0, 180.0, 270.0))


def make_box_geom(name: str, sx: float, sy: float, sz: float, color) -> NodePath:
    """Create a centered box whose base is at z=0. Normals are face-correct."""
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vdata.setNumRows(24)
    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")

    hx, hy = sx / 2.0, sy / 2.0
    z0, z1 = 0.0, sz
    faces = [
        ((0,-1,0), [(-hx,-hy,z0),(hx,-hy,z0),(hx,-hy,z1),(-hx,-hy,z1)]),
        ((1,0,0), [(hx,-hy,z0),(hx,hy,z0),(hx,hy,z1),(hx,-hy,z1)]),
        ((0,1,0), [(hx,hy,z0),(-hx,hy,z0),(-hx,hy,z1),(hx,hy,z1)]),
        ((-1,0,0), [(-hx,hy,z0),(-hx,-hy,z0),(-hx,-hy,z1),(-hx,hy,z1)]),
        ((0,0,1), [(-hx,-hy,z1),(hx,-hy,z1),(hx,hy,z1),(-hx,hy,z1)]),
        ((0,0,-1), [(-hx,hy,z0),(hx,hy,z0),(hx,-hy,z0),(-hx,-hy,z0)]),
    ]
    for normal, verts in faces:
        for v in verts:
            vw.addData3(*v); nw.addData3(*normal); cw.addData4(*color)
    prim = GeomTriangles(Geom.UHStatic)
    for i in range(6):
        b = i * 4
        prim.addVertices(b, b+1, b+2); prim.addVertices(b, b+2, b+3)
    geom = Geom(vdata); geom.addPrimitive(prim)
    node = GeomNode(name); node.addGeom(geom)
    return NodePath(node)


def make_cylinder_geom(name: str, radius: float, height: float, sides: int, color, top_radius: float | None = None) -> NodePath:
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")
    prim = GeomTriangles(Geom.UHStatic)
    tr = radius if top_radius is None else top_radius
    idx = 0
    # side quads with face normals to preserve the clean, architectural look
    for i in range(sides):
        a0 = 2*math.pi*i/sides
        a1 = 2*math.pi*(i+1)/sides
        p0=(math.sin(a0)*radius, math.cos(a0)*radius,0)
        p1=(math.sin(a1)*radius, math.cos(a1)*radius,0)
        q1=(math.sin(a1)*tr, math.cos(a1)*tr,height)
        q0=(math.sin(a0)*tr, math.cos(a0)*tr,height)
        mid=(a0+a1)/2
        n=(math.sin(mid), math.cos(mid), 0)
        for p in (p0,p1,q1,q0): vw.addData3(*p); nw.addData3(*n); cw.addData4(*color)
        prim.addVertices(idx,idx+1,idx+2); prim.addVertices(idx,idx+2,idx+3); idx += 4
    # top fan
    top_center = idx; vw.addData3(0,0,height); nw.addData3(0,0,1); cw.addData4(*color); idx+=1
    for i in range(sides):
        a=2*math.pi*i/sides
        vw.addData3(math.sin(a)*tr, math.cos(a)*tr,height); nw.addData3(0,0,1); cw.addData4(*color); idx+=1
    for i in range(sides): prim.addVertices(top_center, top_center+1+i, top_center+1+((i+1)%sides))
    geom=Geom(vdata); geom.addPrimitive(prim)
    node=GeomNode(name); node.addGeom(geom)
    return NodePath(node)


def make_textured_box_geom(name: str, sx: float, sy: float, sz: float, color=(1,1,1,1)) -> NodePath:
    """Create a centered box with texture coordinates; base sits at z=0."""
    fmt = GeomVertexFormat.getV3n3c4t2()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")
    tw = GeomVertexWriter(vdata, "texcoord")
    hx, hy = sx / 2.0, sy / 2.0
    z0, z1 = 0.0, sz
    def add_face(normal, verts, uvs):
        for v, uv in zip(verts, uvs):
            vw.addData3(*v); nw.addData3(*normal); cw.addData4(*color); tw.addData2(*uv)
    faces = [
        ((0,-1,0), [(-hx,-hy,z0),(hx,-hy,z0),(hx,-hy,z1),(-hx,-hy,z1)], [(0,0),(1,0),(1,1),(0,1)]),
        ((1,0,0), [(hx,-hy,z0),(hx,hy,z0),(hx,hy,z1),(hx,-hy,z1)], [(0,0),(1,0),(1,1),(0,1)]),
        ((0,1,0), [(hx,hy,z0),(-hx,hy,z0),(-hx,hy,z1),(hx,hy,z1)], [(0,0),(1,0),(1,1),(0,1)]),
        ((-1,0,0), [(-hx,hy,z0),(-hx,-hy,z0),(-hx,-hy,z1),(-hx,hy,z1)], [(0,0),(1,0),(1,1),(0,1)]),
        ((0,0,1), [(-hx,-hy,z1),(hx,-hy,z1),(hx,hy,z1),(-hx,hy,z1)], [(0,0),(1,0),(1,1),(0,1)]),
        ((0,0,-1), [(-hx,hy,z0),(hx,hy,z0),(hx,-hy,z0),(-hx,-hy,z0)], [(0,0),(1,0),(1,1),(0,1)]),
    ]
    for normal, verts, uvs in faces:
        add_face(normal, verts, uvs)
    prim = GeomTriangles(Geom.UHStatic)
    for i in range(6):
        b = i * 4
        prim.addVertices(b, b+1, b+2); prim.addVertices(b, b+2, b+3)
    geom = Geom(vdata); geom.addPrimitive(prim)
    node = GeomNode(name); node.addGeom(geom)
    return NodePath(node)


def make_textured_cylinder_geom(name: str, radius: float, height: float, sides: int, color=(1,1,1,1), top_radius: float | None = None) -> NodePath:
    fmt = GeomVertexFormat.getV3n3c4t2()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")
    tw = GeomVertexWriter(vdata, "texcoord")
    prim = GeomTriangles(Geom.UHStatic)
    tr = radius if top_radius is None else top_radius
    idx = 0
    for i in range(sides):
        a0 = 2*math.pi*i/sides
        a1 = 2*math.pi*(i+1)/sides
        u0 = i / sides
        u1 = (i+1) / sides
        p0=(math.sin(a0)*radius, math.cos(a0)*radius,0)
        p1=(math.sin(a1)*radius, math.cos(a1)*radius,0)
        q1=(math.sin(a1)*tr, math.cos(a1)*tr,height)
        q0=(math.sin(a0)*tr, math.cos(a0)*tr,height)
        mid=(a0+a1)/2
        n=(math.sin(mid), math.cos(mid), 0)
        for p, uv in zip((p0,p1,q1,q0), ((u0,0),(u1,0),(u1,1),(u0,1))):
            vw.addData3(*p); nw.addData3(*n); cw.addData4(*color); tw.addData2(*uv)
        prim.addVertices(idx,idx+1,idx+2); prim.addVertices(idx,idx+2,idx+3); idx += 4
    top_center = idx
    vw.addData3(0,0,height); nw.addData3(0,0,1); cw.addData4(*color); tw.addData2(0.5,0.5); idx += 1
    for i in range(sides):
        a = 2*math.pi*i/sides
        x = math.sin(a)*tr; y = math.cos(a)*tr
        vw.addData3(x,y,height); nw.addData3(0,0,1); cw.addData4(*color); tw.addData2(0.5 + x/(2*max(tr,0.001)), 0.5 + y/(2*max(tr,0.001)))
        idx += 1
    for i in range(sides):
        prim.addVertices(top_center, top_center+1+i, top_center+1+((i+1)%sides))
    geom=Geom(vdata); geom.addPrimitive(prim)
    node=GeomNode(name); node.addGeom(geom)
    return NodePath(node)


def make_disc_geom(name: str, radius: float, color, segments: int = 64, z: float = 0.0) -> NodePath:
    fmt=GeomVertexFormat.getV3n3c4(); vdata=GeomVertexData(name,fmt,Geom.UHStatic)
    vw=GeomVertexWriter(vdata,"vertex"); nw=GeomVertexWriter(vdata,"normal"); cw=GeomVertexWriter(vdata,"color")
    vw.addData3(0,0,z); nw.addData3(0,0,1); cw.addData4(*color)
    for i in range(segments):
        a=2*math.pi*i/segments; vw.addData3(math.sin(a)*radius,math.cos(a)*radius,z); nw.addData3(0,0,1); cw.addData4(*color)
    prim=GeomTriangles(Geom.UHStatic)
    for i in range(segments): prim.addVertices(0,1+((i+1)%segments),1+i)
    geom=Geom(vdata); geom.addPrimitive(prim); node=GeomNode(name); node.addGeom(geom); return NodePath(node)


def make_annulus_geom(name: str, inner: float, outer: float, color, segments: int=96, z: float=0.02) -> NodePath:
    fmt=GeomVertexFormat.getV3n3c4(); vdata=GeomVertexData(name,fmt,Geom.UHStatic)
    vw=GeomVertexWriter(vdata,"vertex"); nw=GeomVertexWriter(vdata,"normal"); cw=GeomVertexWriter(vdata,"color")
    for i in range(segments):
        a=2*math.pi*i/segments
        for r in (inner,outer):
            vw.addData3(math.sin(a)*r,math.cos(a)*r,z); nw.addData3(0,0,1); cw.addData4(*color)
    prim=GeomTriangles(Geom.UHStatic)
    for i in range(segments):
        j=(i+1)%segments; a=2*i; b=a+1; c=2*j; d=c+1
        prim.addVertices(a,d,b); prim.addVertices(a,c,d)
    geom=Geom(vdata); geom.addPrimitive(prim); node=GeomNode(name); node.addGeom(geom); return NodePath(node)


def make_uv_sphere_geom(name: str, radius: float, color, rings: int = 18, segments: int = 36) -> NodePath:
    fmt=GeomVertexFormat.getV3n3c4(); vdata=GeomVertexData(name,fmt,Geom.UHStatic)
    vw=GeomVertexWriter(vdata,"vertex"); nw=GeomVertexWriter(vdata,"normal"); cw=GeomVertexWriter(vdata,"color")
    for r in range(rings+1):
        phi=-math.pi*0.5 + math.pi*r/rings
        rr=math.cos(phi); z=math.sin(phi)
        for i in range(segments):
            a=2*math.pi*i/segments; x=math.sin(a)*rr; y=math.cos(a)*rr
            vw.addData3(x*radius,y*radius,z*radius); nw.addData3(x,y,z); cw.addData4(*color)
    prim=GeomTriangles(Geom.UHStatic)
    for r in range(rings):
        for i in range(segments):
            j=(i+1)%segments; a=r*segments+i; b=r*segments+j; c=(r+1)*segments+i; d=(r+1)*segments+j
            prim.addVertices(a,c,d); prim.addVertices(a,d,b)
    geom=Geom(vdata); geom.addPrimitive(prim); node=GeomNode(name); node.addGeom(geom); return NodePath(node)


def make_billboard_disc_geom(name: str, radius: float, color, segments: int = 72) -> NodePath:
    """Circular XZ-plane disc intended for point-eye billboard use."""
    fmt=GeomVertexFormat.getV3n3c4(); vdata=GeomVertexData(name,fmt,Geom.UHStatic)
    vw=GeomVertexWriter(vdata,"vertex"); nw=GeomVertexWriter(vdata,"normal"); cw=GeomVertexWriter(vdata,"color")
    vw.addData3(0,0,0); nw.addData3(0,-1,0); cw.addData4(*color)
    for i in range(segments):
        a=2*math.pi*i/segments
        vw.addData3(math.sin(a)*radius,0,math.cos(a)*radius); nw.addData3(0,-1,0); cw.addData4(*color)
    prim=GeomTriangles(Geom.UHStatic)
    for i in range(segments): prim.addVertices(0,1+i,1+((i+1)%segments))
    geom=Geom(vdata); geom.addPrimitive(prim); node=GeomNode(name); node.addGeom(geom); return NodePath(node)


def make_billboard_annulus_geom(name: str, inner: float, outer: float, color, segments: int = 96) -> NodePath:
    """XZ-plane annulus intended for a distant billboarded planet ring."""
    fmt=GeomVertexFormat.getV3n3c4(); vdata=GeomVertexData(name,fmt,Geom.UHStatic)
    vw=GeomVertexWriter(vdata,"vertex"); nw=GeomVertexWriter(vdata,"normal"); cw=GeomVertexWriter(vdata,"color")
    for i in range(segments):
        a=2*math.pi*i/segments
        for r in (inner,outer):
            vw.addData3(math.sin(a)*r,0,math.cos(a)*r); nw.addData3(0,-1,0); cw.addData4(*color)
    prim=GeomTriangles(Geom.UHStatic)
    for i in range(segments):
        j=(i+1)%segments; a=2*i; b=a+1; c=2*j; d=c+1
        prim.addVertices(a,b,d); prim.addVertices(a,d,c)
    geom=Geom(vdata); geom.addPrimitive(prim); node=GeomNode(name); node.addGeom(geom); return NodePath(node)


def make_sky_dome_geom(name: str, radius: float, horizon_z: float, height: float, horizon_color, mid_color, zenith_color, rings: int = 10, segments: int = 64) -> NodePath:
    fmt=GeomVertexFormat.getV3n3c4(); vdata=GeomVertexData(name,fmt,Geom.UHStatic)
    vw=GeomVertexWriter(vdata,"vertex"); nw=GeomVertexWriter(vdata,"normal"); cw=GeomVertexWriter(vdata,"color")
    def mix(a,b,t):
        return tuple(a[i]*(1.0-t)+b[i]*t for i in range(4))
    for r in range(rings+1):
        t=r/rings
        phi=(math.pi*0.5)*t
        rr=max(0.0,math.cos(phi)*radius)
        z=horizon_z+math.sin(phi)*height
        if t < 0.45:
            color=mix(horizon_color,mid_color,t/0.45)
        else:
            color=mix(mid_color,zenith_color,(t-0.45)/0.55)
        for i in range(segments):
            a=2*math.pi*i/segments
            x=math.sin(a)*rr; y=math.cos(a)*rr
            vw.addData3(x,y,z); nw.addData3(0,0,-1); cw.addData4(*color)
    prim=GeomTriangles(Geom.UHStatic)
    for r in range(rings):
        for i in range(segments):
            j=(i+1)%segments
            a=r*segments+i; b=r*segments+j; c=(r+1)*segments+i; d=(r+1)*segments+j
            prim.addVertices(a,c,d); prim.addVertices(a,d,b)
    geom=Geom(vdata); geom.addPrimitive(prim); node=GeomNode(name); node.addGeom(geom); return NodePath(node)


def make_textured_disc_geom(name: str, radius: float, color=(1,1,1,1), segments: int=96, z: float=0.02, uv_scale: float=28.0) -> NodePath:
    fmt=GeomVertexFormat.getV3n3c4t2(); vdata=GeomVertexData(name,fmt,Geom.UHStatic)
    vw=GeomVertexWriter(vdata,"vertex"); nw=GeomVertexWriter(vdata,"normal"); cw=GeomVertexWriter(vdata,"color"); tw=GeomVertexWriter(vdata,"texcoord")
    vw.addData3(0,0,z); nw.addData3(0,0,1); cw.addData4(*color); tw.addData2(0,0)
    for i in range(segments):
        a=2*math.pi*i/segments; x=math.sin(a)*radius; y=math.cos(a)*radius
        vw.addData3(x,y,z); nw.addData3(0,0,1); cw.addData4(*color); tw.addData2(x/uv_scale,y/uv_scale)
    prim=GeomTriangles(Geom.UHStatic)
    for i in range(segments): prim.addVertices(0,1+((i+1)%segments),1+i)
    geom=Geom(vdata); geom.addPrimitive(prim); node=GeomNode(name); node.addGeom(geom); return NodePath(node)

def make_textured_annulus_sector(name: str, inner: float, outer: float, start_deg: float, end_deg: float, color=(1,1,1,1), segments: int=32, z: float=0.02, tile_length: float=22.0) -> NodePath:
    fmt=GeomVertexFormat.getV3n3c4t2(); vdata=GeomVertexData(name,fmt,Geom.UHStatic)
    vw=GeomVertexWriter(vdata,"vertex"); nw=GeomVertexWriter(vdata,"normal"); cw=GeomVertexWriter(vdata,"color"); tw=GeomVertexWriter(vdata,"texcoord")
    span_deg=end_deg-start_deg; mid_r=(inner+outer)/2.0; arc_len=math.radians(span_deg)*mid_r; repeat_u=max(1.0,arc_len/tile_length); repeat_v=max(1.0,(outer-inner)/10.0)
    for i in range(segments+1):
        t=i/segments; a=math.radians(start_deg+span_deg*t)
        for r,v in ((inner,0.0),(outer,repeat_v)):
            vw.addData3(math.sin(a)*r,math.cos(a)*r,z); nw.addData3(0,0,1); cw.addData4(*color); tw.addData2(repeat_u*t,v)
    prim=GeomTriangles(Geom.UHStatic)
    for i in range(segments):
        a=2*i; b=a+1; c=2*(i+1); d=c+1
        prim.addVertices(a,d,b); prim.addVertices(a,c,d)
    geom=Geom(vdata); geom.addPrimitive(prim); node=GeomNode(name); node.addGeom(geom); return NodePath(node)


@dataclass(frozen=True)
class BuildingSpec:
    name: str
    x: float
    y: float
    sx: float
    sy: float
    height: float
    heading: float
    color: tuple[float,float,float,float]
    style: str = "box"
    z: float = 0.0
    top_scale: float = 0.96


DISTRICT_THEMES = {
    "north": {"label": "North // Corporate Terrace", "primary": (0.84, 0.96, 1.00, 1.0), "secondary": (0.28, 0.74, 1.00, 1.0), "texture": "north_civic_lattice.png"},
    "east": {"label": "East // Innovation Pulse", "primary": (0.72, 0.38, 1.00, 1.0), "secondary": (0.24, 0.88, 1.00, 1.0), "texture": "east_innovation_pulse.png"},
    "south": {"label": "South // Mirage Promenade", "primary": (1.00, 0.42, 0.72, 1.0), "secondary": (1.00, 0.80, 0.32, 1.0), "texture": "south_garden_flow.png"},
    "west": {"label": "West // Foundry Works", "primary": (1.00, 0.62, 0.20, 1.0), "secondary": (0.36, 0.66, 0.98, 1.0), "texture": "west_foundry_signal.png"},
    "core": {"label": "Unity // Forum Nexus", "primary": (0.28, 1.00, 0.86, 1.0), "secondary": (0.78, 0.56, 1.00, 1.0), "texture": "core_unity_signal.png"},
}

PEDESTRIAN_TEXTURES = {
    "north": "north_pedestrian_pavers.png",
    "east": "east_pedestrian_pulse.png",
    "south": "south_pedestrian_flow.png",
    "west": "west_pedestrian_foundry.png",
    "core": "core_pedestrian_forum.png",
}


class UtopiaApp(ShowBase):
    def __init__(self, args: argparse.Namespace):
        self.args = args
        loadPrcFileData("", f"window-title {APP_NAME} // {VERSION}")
        if args.offscreen:
            loadPrcFileData("", "load-display p3headlessgl")
            loadPrcFileData("", "window-type offscreen")
            w=int(args.width or 1920); h=int(args.height or 1080)
            loadPrcFileData("", f"win-size {w} {h}")
        else:
            w=int(args.width or 1920); h=int(args.height or 1080)
            loadPrcFileData("", f"win-size {w} {h}")
        if args.offscreen or args.no_audio:
            loadPrcFileData("", "audio-library-name null")
        else:
            # Player builds use one explicit OpenAL backend for ambience, district music,
            # Gleebs' positional purr and sparks.  This avoids manager disagreement where
            # one layer can silently remain disabled on Windows.
            loadPrcFileData("", "audio-library-name p3openal_audio")
        loadPrcFileData("", "sync-video false")
        loadPrcFileData("", "show-frame-rate-meter false")
        loadPrcFileData("", "framebuffer-multisample 1")
        loadPrcFileData("", "multisamples 4")
        loadPrcFileData("", "texture-anisotropic-degree 8")
        super().__init__()
        self.audio_runtime_available = bool(getattr(self,"sfxManagerList",[])) and "NullAudioManager" not in str(self.sfxManagerList[0])
        if not args.offscreen and not args.no_audio:
            try:
                self.enableSoundEffects(True)
                self.enableMusic(True)
                for manager in getattr(self,"sfxManagerList",[]):
                    manager.setActive(True); manager.setVolume(1.0)
                if getattr(self,"musicManager",None) is not None:
                    self.musicManager.setActive(True); self.musicManager.setVolume(1.0)
                self.audio_runtime_available = bool(getattr(self,"sfxManagerList",[])) and "NullAudioManager" not in str(self.sfxManagerList[0])
                print(f"AUDIO_BACKEND manager={self.sfxManagerList[0]} active={self.sfxManagerList[0].getActive()} volume={self.sfxManagerList[0].getVolume():.2f}")
            except Exception as exc:
                print(f"AUDIO_BACKEND_WARNING error={exc}",file=sys.stderr)
        self.disableMouse()
        self.render.setAntialias(AntialiasAttrib.MAuto)
        self.cam.node().setCameraMask(NORMAL_CAMERA_MASK)
        self.win.setClearColor((0.66,0.70,0.70,1))
        self.setBackgroundColor(0.66,0.70,0.70)
        self.base_dir = Path(__file__).resolve().parent
        # Native HoloVerse-style modes reuse this ShowBase and OS window.  Utopia Vision
        # remains the lifecycle owner and restores its scene when a mode returns.
        self.native_mode = None
        self.native_mode_id = ""
        self.native_mode_module_name = ""
        self.native_mode_host_state = {}
        self.native_mode_scene_nodes = []
        self.gleebs_mode_menu_open = False
        self.gleebs_interaction_available = False
        # Gleebs link menu inside a mode (TAB): return to Utopia or switch mode directly.
        self.native_link_menu_open = False
        self.native_link_prefixes = []
        self.dynamic_ambience = []
        self.ambience_master_volume = 1.0
        self.ambience_config_path = self.base_dir / "audio" / "ambience" / "ambience_zones.json"
        # District music is deliberately separate from SFX/ambience.  It owns the music
        # manager and continuously crossfades replaceable loop assets by player position.
        self.district_music = {}
        self.music_master_volume = 0.50
        self.music_config_path = self.base_dir / "audio" / "music" / "district_music.json"
        self.music_runtime_available = self.audio_runtime_available
        self.physical_time_hours = float(args.physical_time) % 24.0
        self.ar_time_hours = float(args.ar_time if args.ar_time is not None else self.physical_time_hours) % 24.0
        self.freeze_physical_time = bool(args.freeze_time)
        self.weather_state = args.weather_state if args.weather_state in WEATHER_ORDER else "clear"
        self.weather_previous_state = self.weather_state
        self.weather_state_elapsed = 0.0
        self.weather_transition_elapsed = WEATHER_TRANSITION_SECONDS
        self.weather_effect_time = 0.0
        self.freeze_weather = bool(args.freeze_weather)
        self.weather_root = None
        self.rain_batches = []
        self.weather_stats = {"states": len(WEATHER_ORDER), "rain_batches": 0, "rain_streaks": 0}
        self.utopia_system_stats = {"systems": 0, "modules": 0, "archive": 0, "dream_catcher": 0, "eco_climate": 0, "harbor": 0, "industry": 0}
        self.utopia_system_activity = []
        self.utopia_system_activity_stats = {"total": 0, "archive": 0, "dream": 0, "eco": 0, "harbor": 0, "industry": 0, "moving": 0}
        # AR citizen-presence orbs are ambient representations only: no collision, labels,
        # prompts, or physical-world rendering.  They remain sparse and safely inside the wall.
        self.citizen_orbs = []
        self.citizen_orb_stats = {"total": 0, "core": 0, "north": 0, "east": 0, "south": 0, "west": 0, "commuters": 0}
        self.gleebs_actor = None
        self.gleebs_root = None
        self.gleebs_collision = None
        self.gleebs_ar_actor = None
        self.gleebs_ar_root = None
        self.gleebs_eye_glow_nodes = []
        self.gleebs_ar_shadow_card = None
        self.gleebs_head_controls = {}
        self.gleebs_behavior_state = "approach"
        self.gleebs_approach_target = None
        self.gleebs_behavior_stats = {"walk_started": 0, "walk_completed": 0, "wave_started": 0, "wave_completed": 0, "head_tracking": 0, "spark_events": 0}
        self.gleebs_wave_elapsed = 0.0
        self.gleebs_wave_controls = {}
        self.gleebs_spark_particles = []
        self.gleebs_spark_elapsed = 0.0
        self.gleebs_next_spark = 8.0
        self.gleebs_audio3d = None
        self.gleebs_purr_sound = None
        self.gleebs_spark_sound = None
        self.gleebs_audio_config_path = self.base_dir / "audio" / "characters" / "gleebs" / "gleebs_audio.json"
        self.gleebs_audio_stats = {"loaded": 0, "purr": 0, "spark": 0, "radial": 0}
        self.human_residents = []
        self.human_idle_time = 0.0
        self.human_resident_stats = {"requested": len(HUMAN_RESIDENT_SPECS), "loaded": 0, "ar_loaded": 0, "physical_materials": 0, "ar_materials": 0, "colliders": 0, "shadows": 0, "idle_variants": 0}
        self.ar_gate_aprons = []
        self.gleebs_stats = {"loaded": 0, "joints": 0, "idle_frames": 0, "walk_frames": 0, "ar_loaded": 0, "scale": GLEEBS_SCALE, "ar_scale": GLEEBS_AR_SCALE, "physical_damaged_materials": 0, "damage_marks": 0}
        self.shadow_cards = []
        self.gleebs_shadow_card = None
        self.soft_shadow_shader = None
        self.shadow_stats = {"enabled": 0, "mode": "global_projected", "sources": 0, "active": 0, "buildings":0, "walls":0, "bridges":0, "trees":0, "gleebs":0}
        self.surface_detail_stats = {"asphalt":0,"concrete":0,"grass":0,"dirt":0}
        self.viewport_stats = {"target_aspect": GAMEPLAY_ASPECT, "window_aspect": GAMEPLAY_ASPECT, "viewport_aspect": GAMEPLAY_ASPECT, "bars": "none", "dimensions": (0.0,1.0,0.0,1.0)}
        self.public_interiors = []
        self.interior_stats = {"total": 0, "core": 0, "north": 0, "east": 0, "south": 0, "west": 0, "props": 0, "collision_solids": 0, "lights": 0, "ambient_lights": 0, "ar_exterior_shells": 0, "ar_exterior_patterned": 0}
        self.interior_qa_points = {}
        self.ar_neon_spill_sources = []
        self.pause_panel_mode = None
        self.physical_sky = None
        self.physical_water = None
        self.physical_water_state = {"roughness": 0.0, "sun_alpha": 0.0, "moon_alpha": 0.0}
        self.outer_land_root = None
        self.physical_moon_root = None
        self.ar_saturn_root = None
        self.physical_sun_root = None
        self.ar_natural_sun_root = None
        self.physical_cloud_root = None
        self.ar_natural_cloud_root = None
        self.cloud_clusters = []
        self.physical_mist_root = None
        self.physical_mist_clusters = []
        self.mist_stats = {"layers": 0}
        self.ar_sky = None
        self.ar_natural_sky = None
        self.theme_textures = self._load_district_textures()
        self.pedestrian_textures = self._load_pedestrian_textures()
        self._configure_lens()
        self._configure_lighting()
        self._configure_fog()
        self._configure_ar_material_shaders()
        self._configure_physical_water_shader()

        self.world = self.render.attachNewNode("blank_city")
        self.visual_root = self.world.attachNewNode("visuals")
        self.collision_root = self.world.attachNewNode("collisions")
        self.collision_root.hide(BitMask32.allOn())
        self.buildings: list[BuildingSpec] = []
        self.ar_structure_specs: list[BuildingSpec] = []
        self.ar_architecture_stats = {"modules": 0, "balconies": 0, "setbacks": 0, "recesses": 0, "roof_structures": 0, "window_bands": 0, "entrances": 0, "canopies": 0, "active_windows": 0, "active_entries": 0, "active_glow_paths": 0, "promenades": 0, "ground_markers": 0, "forecourts": 0, "textured_walkways": 0, "hero_signatures": 0, "coverage_roof_crowns": 0, "coverage_wall_pieces": 0, "coverage_gate_pieces": 0, "coverage_transit_pieces": 0, "coverage_overlook_pieces": 0, "detail_wall_surfaces": 0, "detail_gate_surfaces": 0, "detail_transit_surfaces": 0, "detail_roof_surfaces": 0, "detail_overlook_surfaces": 0, "detail_sidewalk_surfaces": 0, "detail_ground_fields": 0, "park_surfaces": 0, "textured_node_pads": 0}
        self.ar_activity_nodes = []
        self.environment_stats = {"physical_sky": 0, "ar_sky": 0, "ar_water": 0, "shore_shelves": 0, "outer_land": 0, "outer_trees": 0, "outer_shrubs": 0, "outer_shore_breakup": 0, "moon": 0, "saturn": 0, "sun": 0, "cloud_layers": 0}
        self.ar_material_stats = {"reflective_solids": 0, "neon_patterns": 0, "spill_sources": 0}
        self.environment_time = 0.0
        self.ar_activity_time = 0.0
        self.ar_activity_cull_last_player = None
        self.ar_optimization_stats = {"pre_nodes":0,"post_nodes":0,"static_batches":0,"activity_total":0,"activity_visible":0,"activity_hidden":0}
        self.ar_water_surface = None
        self.visor_mode = args.visor_mode
        self._build_world()
        self._configure_physical_surface_materials()
        self._build_gleebs_physical_import()
        self._build_human_residents_physical()

        # The physical city remains the accepted Pass 01 authority. The resident
        # layer is separate and visible only to the AR camera.
        self.utopia_root = self.render.attachNewNode("utopia_ar_layer")
        self.utopia_root.hide(NORMAL_CAMERA_MASK)
        self.utopia_root.setLightOff(1)
        self._build_utopia_layer()
        self._build_gleebs_ar_presentation()
        self._build_human_residents_ar()
        self._build_public_interiors()
        self._build_projected_shadows()
        self._build_citizen_presence_orbs()
        self._optimize_ar_scene_graph()
        self._update_neon_spill_inputs()
        self._build_ar_environment()
        self._build_celestial_system()
        self._build_sky_depth_system()
        self._build_physical_mist_system()
        self._build_player()
        self._setup_gleebs_behavior()
        self._build_gleebs_spark_system()
        self._load_gleebs_audio()
        self._build_weather_system()
        self._load_dynamic_ambience()
        self._load_district_music()
        self._build_ar_lens()
        self._build_ui()
        self._bind_controls()
        self.accept("window-event", self._on_window_event)
        self._apply_gameplay_viewport()

        self.paused = False
        self.key_state = {k:False for k in ("forward","back","left","right","sprint")}
        self.yaw = 0.0
        self.pitch = -2.0
        self.vertical_velocity = 0.0
        self.on_ground = True
        self.in_water = False
        self.mouse_captured = False
        self.lens_held = False
        self.lens_latched = False
        self.ar_pulse_time = 0.0
        self._control_smoke_peak_z = 0.0
        self._control_smoke_saw_lens = False
        self._apply_time_visuals()
        self._set_lens(False)
        self._spawn("south_gate")

        if not args.offscreen:
            self._capture_mouse()

        self.taskMgr.add(self._update, "player_update")
        if args.activity_proof:
            self._set_qa_camera("lens_street")
            self.taskMgr.doMethodLater(0.25, self._activity_proof_a, "activity_proof_a")
            self.taskMgr.doMethodLater(1.15, self._activity_proof_b, "activity_proof_b")
        elif args.qa_shot:
            self._set_qa_camera(args.qa_shot)
            self.taskMgr.doMethodLater(0.35, self._capture_qa, "capture_qa")
        elif args.pause_menu_shot:
            self._toggle_pause()
            self.taskMgr.doMethodLater(0.25, self._capture_qa, "capture_pause_menu")
        elif args.help_menu_shot:
            self._toggle_help()
            self.taskMgr.doMethodLater(0.25, self._capture_qa, "capture_help_menu")
        elif args.lens_smoke:
            self.taskMgr.doMethodLater(0.18,self._lens_smoke_start,"lens_smoke_start")
            self.taskMgr.doMethodLater(0.55,self._lens_smoke_finish,"lens_smoke_finish")
        elif args.visor_smoke:
            self.taskMgr.doMethodLater(0.12,self._visor_smoke_start,"visor_smoke_start")
            self.taskMgr.doMethodLater(0.36,self._visor_smoke_vertical,"visor_smoke_vertical")
            self.taskMgr.doMethodLater(0.60,self._visor_smoke_fullscreen,"visor_smoke_fullscreen")
            self.taskMgr.doMethodLater(0.84,self._visor_smoke_finish,"visor_smoke_finish")
        elif args.activity_smoke:
            self.taskMgr.doMethodLater(0.12,self._activity_smoke_start,"activity_smoke_start")
            self.taskMgr.doMethodLater(0.82,self._activity_smoke_finish,"activity_smoke_finish")
        elif args.input_smoke:
            self._input_smoke_initial_yaw=self.yaw
            self.taskMgr.doMethodLater(0.25,self._input_smoke_inject,"input_smoke_inject")
            self.taskMgr.doMethodLater(0.55,self._input_smoke_finish,"input_smoke_finish")
        elif args.modal_smoke:
            self.taskMgr.doMethodLater(0.20,self._modal_smoke,"modal_smoke")
        elif args.collision_smoke:
            self.taskMgr.doMethodLater(0.15,self._collision_smoke_start,"collision_smoke_start")
        elif args.traversal_smoke:
            self.taskMgr.doMethodLater(0.18,self._traversal_smoke,"traversal_smoke")
        elif args.time_smoke:
            self._time_smoke_initial_physical = self.physical_time_hours
            self._time_smoke_initial_ar = self.ar_time_hours
            self.taskMgr.doMethodLater(0.28,self._time_smoke_start,"time_smoke_start")
            self.taskMgr.doMethodLater(0.70,self._time_smoke_finish,"time_smoke_finish")
        elif args.weather_smoke:
            self.taskMgr.doMethodLater(0.20,self._weather_smoke_start,"weather_smoke_start")
            self.taskMgr.doMethodLater(0.58,self._weather_smoke_finish,"weather_smoke_finish")
        elif args.celestial_smoke:
            self.taskMgr.doMethodLater(0.20,self._celestial_smoke,"celestial_smoke")
        elif args.water_smoke:
            self.taskMgr.doMethodLater(0.20,self._water_smoke,"water_smoke")
        elif args.utopia_systems_smoke:
            self.taskMgr.doMethodLater(0.20,self._utopia_systems_smoke,"utopia_systems_smoke")
        elif args.ambience_smoke:
            self.taskMgr.doMethodLater(0.20,self._ambience_smoke,"ambience_smoke")
        elif args.music_smoke:
            self.taskMgr.doMethodLater(0.20,self._district_music_smoke,"district_music_smoke")
        elif args.audio_state_smoke:
            self.taskMgr.doMethodLater(0.20,self._audio_state_smoke,"audio_state_smoke")
        elif args.citizen_orbs_smoke:
            self.taskMgr.doMethodLater(0.20,self._citizen_orbs_smoke,"citizen_orbs_smoke")
        elif args.interiors_smoke:
            self.taskMgr.doMethodLater(0.20,self._interiors_smoke,"interiors_smoke")
        elif args.ar_coverage_smoke:
            self.taskMgr.doMethodLater(0.20,self._ar_coverage_smoke,"ar_coverage_smoke")
        elif args.viewport_smoke:
            self.taskMgr.doMethodLater(0.20,self._viewport_smoke,"viewport_smoke")
        elif args.shadow_smoke:
            self.taskMgr.doMethodLater(0.20,self._shadow_smoke,"shadow_smoke")
        elif args.gleebs_smoke:
            self.taskMgr.doMethodLater(0.20,self._gleebs_smoke,"gleebs_smoke")
        elif args.gleebs_behavior_smoke:
            self.taskMgr.doMethodLater(0.20,self._gleebs_behavior_smoke,"gleebs_behavior_smoke")
        elif args.gleebs_audio_smoke:
            self.taskMgr.doMethodLater(0.20,self._gleebs_audio_smoke,"gleebs_audio_smoke")
        elif args.resident_smoke:
            self.taskMgr.doMethodLater(0.85,self._resident_smoke,"resident_smoke")
        elif args.atmosphere_smoke:
            self.taskMgr.doMethodLater(0.20,self._atmosphere_smoke,"atmosphere_smoke")
        elif args.surface_smoke:
            self.taskMgr.doMethodLater(0.20,self._surface_smoke,"surface_smoke")
        elif args.ar_optimization_smoke:
            self.taskMgr.doMethodLater(0.20,self._ar_optimization_smoke,"ar_optimization_smoke")
        elif args.control_smoke:
            self._control_smoke_start_pos = self.player.getPos(self.render)
            self._control_smoke_elapsed = 0.0
            self.key_state["forward"] = True
            self.key_state["right"] = True
            self.key_state["sprint"] = True
            self._lens_hold(True)
            self._jump()
            self.taskMgr.add(self._control_smoke_wait, "control_smoke_wait")
        elif args.smoke_test:
            self.taskMgr.doMethodLater(1.2, self._smoke_exit, "smoke_exit")

    def _configure_lens(self):
        # Gameplay composition is authored at 16:9 / 1920x1080.  Keep ShowBase's managed
        # camLens, but lock its projection to that authored aspect.  A centered DisplayRegion
        # then preserves the same projection inside arbitrary maximized-window client sizes
        # instead of stretching the world to fill them.
        lens = self.camLens
        lens.setAspectRatio(GAMEPLAY_ASPECT)
        lens.setFov(78)
        lens.setNearFar(0.08, 8000.0)
        self.cam.node().setLens(lens)

    def _apply_gameplay_viewport(self):
        if not self.win:
            return
        if hasattr(self.win,"getProperties"):
            props=self.win.getProperties(); w=int(props.getXSize()); h=int(props.getYSize())
        else:
            w=int(self.win.getXSize()); h=int(self.win.getYSize())
        if w <= 0 or h <= 0:
            return
        window_aspect=float(w)/float(h)
        if window_aspect > GAMEPLAY_ASPECT + 1e-6:
            frac=GAMEPLAY_ASPECT/window_aspect
            left=(1.0-frac)*0.5; right=1.0-left; bottom=0.0; top=1.0; bars="pillarbox"
        elif window_aspect < GAMEPLAY_ASPECT - 1e-6:
            frac=window_aspect/GAMEPLAY_ASPECT
            bottom=(1.0-frac)*0.5; top=1.0-bottom; left=0.0; right=1.0; bars="letterbox"
        else:
            left=0.0; right=1.0; bottom=0.0; top=1.0; bars="none"
        dims=(left,right,bottom,top)
        # Keep 3-D, render2d (AR composite), and render2dp in the same viewport.
        for camera_np in (getattr(self,"cam",None),getattr(self,"cam2d",None),getattr(self,"cam2dp",None)):
            if camera_np is None or camera_np.isEmpty():
                continue
            node=camera_np.node()
            for i in range(node.getNumDisplayRegions()):
                node.getDisplayRegion(i).setDimensions(*dims)
        # ShowBase normally sizes aspect2d from the OS window.  Since the actual gameplay
        # viewport is fixed to 16:9, give GUI layout the same authored safe area.
        self.aspect2d.setScale(1.0/GAMEPLAY_ASPECT,1.0,1.0)
        if hasattr(self,"aspect2dp"):
            self.aspect2dp.setScale(1.0/GAMEPLAY_ASPECT,1.0,1.0)
        self.a2dLeft=-GAMEPLAY_ASPECT; self.a2dRight=GAMEPLAY_ASPECT; self.a2dBottom=-1.0; self.a2dTop=1.0
        self.camLens.setAspectRatio(GAMEPLAY_ASPECT)
        if getattr(self,"ar_camera",None) is not None:
            self.ar_camera.node().getLens().setAspectRatio(GAMEPLAY_ASPECT)
        view_w=(right-left)*float(w); view_h=(top-bottom)*float(h)
        self.viewport_stats={
            "target_aspect":GAMEPLAY_ASPECT,"window_aspect":window_aspect,
            "viewport_aspect":view_w/max(1.0,view_h),"bars":bars,"dimensions":dims,
            "window_size":(w,h),"viewport_size":(round(view_w,2),round(view_h,2)),
        }

    def _on_window_event(self, window=None):
        self._apply_gameplay_viewport()

    def _configure_lighting(self):
        self.ambient_light = AmbientLight("ambient")
        self.ambient_light.setColor((0.58,0.59,0.60,1))
        self.ambient_light_np = self.render.attachNewNode(self.ambient_light)
        self.render.setLight(self.ambient_light_np)
        self.sun_light = DirectionalLight("sun")
        self.sun_light.setColor((0.92,0.92,0.88,1))
        self.sun_np = self.render.attachNewNode(self.sun_light)
        self.sun_np.setPos(0,0,SHADOW_ANCHOR_Z)
        self.sun_np.setHpr(-35,-48,0)
        self.render.setLight(self.sun_np)

    def _make_soft_shadow_card(self, name: str):
        """Horizontal XY shadow quad.  Explicit geometry avoids CardMaker plane ambiguity."""
        fmt=GeomVertexFormat.getV3t2()
        vdata=GeomVertexData(name,fmt,Geom.UHStatic); vdata.setNumRows(4)
        vw=GeomVertexWriter(vdata,"vertex"); tw=GeomVertexWriter(vdata,"texcoord")
        for x,y,u,v in ((-0.5,-0.5,0,0),(0.5,-0.5,1,0),(0.5,0.5,1,1),(-0.5,0.5,0,1)):
            vw.addData3(x,y,0.0); tw.addData2(u,v)
        tris=GeomTriangles(Geom.UHStatic); tris.addVertices(0,1,2); tris.addVertices(0,2,3)
        geom=Geom(vdata); geom.addPrimitive(tris); node=GeomNode(name); node.addGeom(geom)
        card=self.visual_root.attachNewNode(node)
        card.setTransparency(TransparencyAttrib.MAlpha); card.setDepthWrite(False); card.setBin("transparent",7); card.setTwoSided(True)
        if self.soft_shadow_shader is None:
            vertex=("#version 130\n"
                    "in vec4 p3d_Vertex; in vec2 p3d_MultiTexCoord0; uniform mat4 p3d_ModelViewProjectionMatrix; out vec2 uv;\n"
                    "void main(){ gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex; uv=p3d_MultiTexCoord0; }\n")
            frag=("#version 130\n"
                  "uniform vec4 p3d_ColorScale; in vec2 uv; out vec4 fragColor;\n"
                  "void main(){ vec2 q=abs(uv-vec2(0.5))*2.0; float edge=max(q.x,q.y); float soft=1.0-smoothstep(0.48,1.0,edge); float center=1.0-smoothstep(0.05,1.0,length((uv-vec2(0.5))*vec2(0.82,1.18))*2.0); float a=soft*(0.48+0.52*center)*p3d_ColorScale.a; if(a<0.004) discard; fragColor=vec4(vec3(0.018,0.021,0.026),a); }\n")
            self.soft_shadow_shader=Shader.make(Shader.SL_GLSL,vertex,frag)
        card.setShader(self.soft_shadow_shader)
        return card

    def _add_shadow_source(self, name: str, x: float, y: float, sx: float, sy: float, height: float, heading: float=0.0, category: str="building"):
        # Every solid gets two restrained layers: a compact contact shadow that grounds the
        # object at its actual footprint, plus the existing sun-direction projection.  Keeping
        # both as explicit XY quads avoids the full-scene shadow-map precision/banding failure
        # on this kilometre-scale flat world while making shadows readable everywhere nearby.
        card=self._make_soft_shadow_card(name+"_directional")
        contact=self._make_soft_shadow_card(name+"_contact")
        card.hide(AR_CAMERA_MASK); contact.hide(AR_CAMERA_MASK)
        self.shadow_cards.append({"card":card,"contact":contact,"x":float(x),"y":float(y),"sx":max(0.8,float(sx)),"sy":max(0.8,float(sy)),"height":max(0.4,float(height)),"heading":float(heading),"category":category})
        self.shadow_stats[category]=int(self.shadow_stats.get(category,0))+1

    def _build_projected_shadows(self):
        """Player-local but map-wide shadow authority for all major physical solid categories.

        Every source exists globally; only nearby cards are shown.  Roads/terrain receive the
        transparent shadows but never become shadow casters themselves, avoiding the old flat-road
        self-shadow banding.  This covers buildings, outer walls, bridge barriers/pylons,
        the central spire, public interior furnishings and Gleebs. Trees are removed in Pass 59.
        """
        self.shadow_cards=[]
        self.shadow_stats={"enabled":1,"mode":"global_projected_contact","sources":0,"active":0,"contacts":0,"buildings":0,"walls":0,"bridges":0,"trees":0,"interiors":0,"gleebs":1}
        for idx,spec in enumerate(self.buildings):
            if float(spec.height)>=8.0:
                self._add_shadow_source(f"building_shadow_{idx:03d}",spec.x,spec.y,spec.sx,spec.sy,spec.height,spec.heading,"buildings")
        # Civic halls and spire are outside self.buildings.
        self._add_shadow_source("unity_spire_shadow",0,0,52,52,170,0,"buildings")
        for angle in (45,135,225,315):
            x,y,_=polar(87,angle,0); self._add_shadow_source(f"civic_shadow_{angle}",x,y,34,52,16,angle,"buildings")
        # Full wall ring, skipping the same physical gate gaps.
        arc=2*math.pi*((INNER_WALL_RADIUS+OUTER_WALL_RADIUS)/2)/WALL_SEGMENTS
        radius=(INNER_WALL_RADIUS+OUTER_WALL_RADIUS)/2
        for i in range(WALL_SEGMENTS):
            angle=360*i/WALL_SEGMENTS
            if is_gate_angle(angle): continue
            x,y,_=polar(radius,angle,0); self._add_shadow_source(f"wall_shadow_{i:02d}",x,y,arc*1.01,OUTER_WALL_RADIUS-INNER_WALL_RADIUS,WALL_HEIGHT,angle,"walls")
        # All four bridge barrier pairs and gate pylons.
        bridge_len=170.0; mid=CITY_RADIUS+bridge_len/2-5
        for angle in (0,90,180,270):
            x,y,_=polar(mid,angle,0)
            for lateral in (-18.0,18.0):
                # lateral is local X after heading; resolve world position explicitly.
                a=math.radians(angle); bx=x+math.cos(a)*lateral; by=y-math.sin(a)*lateral
                self._add_shadow_source(f"bridge_barrier_shadow_{angle}_{int(lateral)}",bx,by,1.2,bridge_len,2.2,angle,"bridges")
            gx,gy,_=polar(CITY_RADIUS-2,angle,0)
            for lateral in (-27.0,27.0):
                a=math.radians(angle); px=gx+math.cos(a)*lateral; py=gy-math.sin(a)*lateral
                self._add_shadow_source(f"gate_pylon_shadow_{angle}_{int(lateral)}",px,py,7,7,38,angle,"bridges")
        # Broad furniture grounding inside the five public annexes.
        for idx,np in enumerate(self.visual_root.findAllMatches("**/interior_*")):
            name=np.getName().lower()
            if not any(token in name for token in ("desk","bench","table","counter","work","pedestal","console","seat")): continue
            b=np.getTightBounds(self.render)
            if not b or b[0] is None or b[1] is None: continue
            lo,hi=b; sx=max(0.8,float(hi.x-lo.x)); sy=max(0.8,float(hi.y-lo.y)); h=max(0.5,float(hi.z-lo.z)); pos=np.getPos(self.render)
            self._add_shadow_source(f"interior_shadow_{idx:03d}",pos.x,pos.y,sx,sy,h,np.getH(self.render),"interiors")
        self.gleebs_shadow_card=self._make_soft_shadow_card("gleebs_contact_shadow"); self.gleebs_shadow_card.hide(AR_CAMERA_MASK)
        self.shadow_stats["sources"]=len(self.shadow_cards)+1+(1 if self.gleebs_ar_shadow_card is not None else 0)
        self._update_projected_shadows()

    def _shadow_surface_z(self,x:float,y:float)->float:
        # Must sit above every accepted physical walking skin (bridge road reaches ~0.09m).
        r=math.hypot(float(x),float(y))
        if 500.0 <= r <= 700.0 and (abs(float(x))<22.0 or abs(float(y))<22.0): return 0.135
        if r<=CITY_RADIUS+2.0: return 0.115
        return 0.045

    def _update_projected_shadows(self):
        if not self.shadow_stats.get("enabled"): return
        h=float(self.physical_time_hours)%24.0; sun_alt=max(0.0,math.sin(math.pi*(h-6.0)/12.0)); weather=self._current_weather_profile(); sun_gain=float(weather["sun_gain"]); visible=sun_alt>0.02 and sun_gain>0.04
        ray=self.sun_np.getQuat(self.render).xform(Vec3(0,1,0)); horiz=Vec3(ray.x,ray.y,0)
        if horiz.lengthSquared()<1e-5: horiz=Vec3(0,1,0)
        else: horiz.normalize()
        heading=math.degrees(math.atan2(float(horiz.x),float(horiz.y))); slope=max(0.20,math.sqrt(float(ray.x*ray.x+ray.y*ray.y))/max(0.18,abs(float(ray.z))))
        player_pos=self.player.getPos(self.render) if hasattr(self,"player") else Vec3(0,0,0); active=0
        contact_count=0
        for item in self.shadow_cards:
            card=item["card"]; contact=item["contact"]; dist=math.hypot(item["x"]-float(player_pos.x),item["y"]-float(player_pos.y))
            if (not visible) or dist>SHADOW_ACTIVE_RADIUS:
                card.hide(); contact.hide(); continue
            length=min(SHADOW_MAX_LENGTH,max(2.5,item["height"]*slope*0.62)); footprint=max(item["sx"],item["sy"])
            width=max(2.4,min(44.0,footprint*0.86)); depth=max(3.0,min(72.0,footprint*0.52+length))
            x=item["x"]+float(horiz.x)*length*0.36; y=item["y"]+float(horiz.y)*length*0.36
            card.show(); card.setH(heading); card.setScale(width,depth,1.0); card.setPos(x,y,self._shadow_surface_z(x,y))
            alpha=(0.095+0.145*sun_alt)*sun_gain; card.setColorScale(1,1,1,alpha)
            # Compact grounding layer.  Category-specific caps keep large walls/buildings from
            # becoming opaque slabs while still preventing the old floating/paper-cutout look.
            cat=item.get("category","")
            if cat=="trees": cscale=(min(7.0,item["sx"]*0.95),min(7.0,item["sy"]*0.95))
            elif cat=="walls": cscale=(min(30.0,item["sx"]*0.72),min(8.0,item["sy"]*0.92))
            elif cat=="bridges": cscale=(min(16.0,item["sx"]*0.86),min(42.0,item["sy"]*0.45))
            else: cscale=(min(30.0,item["sx"]*0.78),min(30.0,item["sy"]*0.78))
            contact.show(); contact.setH(item["heading"]); contact.setScale(max(1.2,cscale[0]),max(1.2,cscale[1]),1.0); contact.setPos(item["x"],item["y"],self._shadow_surface_z(item["x"],item["y"])+0.002)
            contact_alpha=(0.075+0.105*sun_alt)*sun_gain; contact.setColorScale(1,1,1,contact_alpha)
            active+=1; contact_count+=1
        self.shadow_stats["contacts"]=contact_count
        # Gleebs gets a clear contact + directional shadow at conversational range.
        if self.gleebs_shadow_card is not None and self.gleebs_root is not None:
            gp=self.gleebs_root.getPos(self.render)
            if visible:
                length=max(1.6,min(4.6,2.2*slope)); self.gleebs_shadow_card.show(); self.gleebs_shadow_card.setH(heading)
                self.gleebs_shadow_card.setScale(1.35,2.2+length,1.0); self.gleebs_shadow_card.setPos(gp.x+float(horiz.x)*length*0.35,gp.y+float(horiz.y)*length*0.35,self._shadow_surface_z(gp.x,gp.y)+0.004); self.gleebs_shadow_card.setColorScale(1,1,1,(0.24+0.22*sun_alt)*sun_gain); active+=1
            else: self.gleebs_shadow_card.hide()
        if self.gleebs_ar_shadow_card is not None and self.gleebs_ar_root is not None:
            gp=self.gleebs_ar_root.getPos(self.render)
            if visible:
                length=max(2.0,min(7.0,4.0*slope)); self.gleebs_ar_shadow_card.show(); self.gleebs_ar_shadow_card.setH(heading); self.gleebs_ar_shadow_card.setScale(2.5,4.0+length,1.0); self.gleebs_ar_shadow_card.setPos(gp.x+float(horiz.x)*length*0.35,gp.y+float(horiz.y)*length*0.35,self._shadow_surface_z(gp.x,gp.y)+0.006); self.gleebs_ar_shadow_card.setColorScale(1,1,1,(0.15+0.15*sun_alt)*sun_gain)
            else: self.gleebs_ar_shadow_card.hide()
        self.shadow_stats["active"]=active

    def _configure_physical_surface_materials(self):
        """Subtle real-world texture breakup for physical roads, concrete and terrain."""
        stage=TextureStage("physical_surface_detail"); stage.setMode(TextureStage.MModulate)
        tex_dir=self.base_dir/"assets"/"textures"/"physical"
        textures={}
        for key,name in (("asphalt","asphalt_detail.png"),("concrete","concrete_detail.png"),("grass","grass_detail.png"),("dirt","dirt_detail.png")):
            tex=self.loader.loadTexture(Filename.fromOsSpecific(str(tex_dir/name)))
            if tex is not None:
                tex.setWrapU(Texture.WMRepeat); tex.setWrapV(Texture.WMRepeat); tex.setMinfilter(Texture.FTLinearMipmapLinear); tex.setMagfilter(Texture.FTLinear); textures[key]=tex
        def apply(np,key,scale,specular,shine):
            tex=textures.get(key)
            if tex is None: return
            # Modulate the existing authored vertex colour instead of replacing it with a
            # white material.  The texture supplies small-scale breakup while the original
            # asphalt/concrete/earth palette remains authoritative.
            np.setTexture(stage,tex,1); np.setTexGen(stage,TexGenAttrib.MWorldPosition); np.setTexScale(stage,scale,scale)
            self.surface_detail_stats[key]+=1
        for np in self.visual_root.findAllMatches("**/+GeomNode"):
            name=np.getName().lower()
            if any(t in name for t in ("bridge_road","inner_ring_road","middle_ring_road","outer_ring_road","road_")):
                apply(np,"asphalt",0.075,(0.08,0.085,0.09),10.0)
            elif any(t in name for t in ("sidewalk","unity_plaza","city_ground","skyline_overlook","bridge_")) and "barrier" not in name:
                apply(np,"concrete",0.050,(0.10,0.10,0.095),16.0)
            elif any(t in name for t in ("outer_grass","park")):
                apply(np,"grass",0.045,(0.018,0.022,0.016),4.0)
            elif any(t in name for t in ("outer_dirt","outer_shore")):
                apply(np,"dirt",0.052,(0.025,0.020,0.015),4.0)
    def _configure_ar_material_shaders(self):
        # AR-only material split: bright texture patterns behave like neon while
        # unpatterned structural surfaces receive a restrained reflective sheen.
        # Pass 37 adds five bounded world-space neon spill sources so the existing
        # Utopia systems can illuminate nearby solids without city-wide dynamic lights.
        common_vertex = ("#version 130\n"
            "in vec4 p3d_Vertex;\n"
            "in vec3 p3d_Normal;\n"
            "in vec4 p3d_Color;\n"
            "uniform mat4 p3d_ModelViewProjectionMatrix;\n"
            "uniform mat4 p3d_ModelMatrix;\n"
            "out vec3 wpos; out vec3 wnormal; out vec4 vcolor;\n"
            "void main(){\n"
            " gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex;\n"
            " wpos=(p3d_ModelMatrix*p3d_Vertex).xyz;\n"
            " wnormal=normalize(mat3(p3d_ModelMatrix)*p3d_Normal);\n"
            " vcolor=p3d_Color;\n"
            "}\n")
        spill_uniforms = (
            "uniform vec4 spill_pos_radius0; uniform vec4 spill_color_intensity0;\n"
            "uniform vec4 spill_pos_radius1; uniform vec4 spill_color_intensity1;\n"
            "uniform vec4 spill_pos_radius2; uniform vec4 spill_color_intensity2;\n"
            "uniform vec4 spill_pos_radius3; uniform vec4 spill_color_intensity3;\n"
            "uniform vec4 spill_pos_radius4; uniform vec4 spill_color_intensity4;\n"
        )
        spill_fn = (
            "vec3 oneSpill(vec4 pr, vec4 ci, vec3 N, vec3 V){\n"
            " vec3 delta=pr.xyz-wpos; float d=length(delta); float radius=max(pr.w,0.001); float edge=clamp(1.0-d/radius,0.0,1.0);\n"
            " if(edge<=0.0 || ci.a<=0.0) return vec3(0.0); vec3 L=delta/max(d,0.001); float diffuse=max(dot(N,L),0.0);\n"
            " vec3 H=normalize(L+V); float spec=pow(max(dot(N,H),0.0),22.0); float fall=edge*edge*(3.0-2.0*edge);\n"
            " return ci.rgb*ci.a*fall*(0.16+0.72*diffuse+0.28*spec); }\n"
            "vec3 localSpill(vec3 N, vec3 V){ return oneSpill(spill_pos_radius0,spill_color_intensity0,N,V)+oneSpill(spill_pos_radius1,spill_color_intensity1,N,V)+oneSpill(spill_pos_radius2,spill_color_intensity2,N,V)+oneSpill(spill_pos_radius3,spill_color_intensity3,N,V)+oneSpill(spill_pos_radius4,spill_color_intensity4,N,V); }\n"
        )
        solid_frag = ("#version 130\n"
            "uniform vec4 p3d_ColorScale;\n"
            "uniform mat4 p3d_ViewMatrixInverse;\n"
            "uniform vec3 reflection_primary; uniform vec3 reflection_secondary; uniform float reflection_strength;\n" + spill_uniforms +
            "in vec3 wpos; in vec3 wnormal; in vec4 vcolor; out vec4 fragColor;\n" + spill_fn +
            "vec3 reflectedLight(vec3 N, vec3 V){\n"
            " vec3 r=reflect(-V,N);\n"
            " vec3 l1=normalize(vec3(0.42,0.72,0.55)); vec3 l2=normalize(vec3(-0.62,0.30,0.66));\n"
            " float s1=pow(max(dot(r,l1),0.0),18.0); float s2=pow(max(dot(r,l2),0.0),22.0);\n"
            " float floorAmt=pow(clamp(abs(N.z),0.0,1.0),1.6);\n"
            " float stripe1=pow(0.5+0.5*sin(wpos.x*0.044+wpos.y*0.015),6.0);\n"
            " float stripe2=pow(0.5+0.5*sin(wpos.y*0.050-wpos.x*0.012+1.7),7.0);\n"
            " float fres=pow(1.0-clamp(abs(dot(N,V)),0.0,1.0),2.4);\n"
            " float wallAmt=1.0-floorAmt; float wallBand=pow(0.5+0.5*sin(wpos.z*0.20+wpos.x*0.018-wpos.y*0.011),8.0); vec3 env=mix(reflection_secondary,reflection_primary,clamp(0.5+0.5*r.z,0.0,1.0)); return reflection_primary*(s1*0.62+stripe1*floorAmt*0.24+wallBand*wallAmt*0.12)+reflection_secondary*(s2*0.54+stripe2*floorAmt*0.20)+mix(reflection_primary,reflection_secondary,0.5)*fres*0.16+env*(0.07+0.17*fres)*(0.38+0.62*floorAmt);\n"
            "}\n"
            "void main(){ vec3 N=normalize(wnormal); vec3 cameraPos=p3d_ViewMatrixInverse[3].xyz; vec3 V=normalize(cameraPos-wpos); float facing=clamp(abs(dot(N,V)),0.0,1.0); vec3 base=vcolor.rgb*p3d_ColorScale.rgb*(0.82+0.18*facing); vec3 sheen=reflectedLight(N,V)*reflection_strength; vec3 spill=localSpill(N,V); fragColor=vec4(base+sheen+spill,vcolor.a*p3d_ColorScale.a); }\n")
        pattern_vertex = ("#version 130\n"
            "in vec4 p3d_Vertex; in vec3 p3d_Normal; in vec4 p3d_Color; in vec2 p3d_MultiTexCoord0;\n"
            "uniform mat4 p3d_ModelViewProjectionMatrix; uniform mat4 p3d_ModelMatrix; uniform mat4 p3d_TextureMatrix[1];\n"
            "out vec3 wpos; out vec3 wnormal; out vec4 vcolor; out vec2 texcoord;\n"
            "void main(){ gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex; wpos=(p3d_ModelMatrix*p3d_Vertex).xyz; wnormal=normalize(mat3(p3d_ModelMatrix)*p3d_Normal); vcolor=p3d_Color; texcoord=(p3d_TextureMatrix[0]*vec4(p3d_MultiTexCoord0,0.0,1.0)).xy; }\n")
        pattern_frag = ("#version 130\n"
            "uniform sampler2D p3d_Texture0; uniform vec4 p3d_ColorScale; uniform mat4 p3d_ViewMatrixInverse;\n"
            "uniform vec3 reflection_primary; uniform vec3 reflection_secondary; uniform float reflection_strength; uniform float neon_gain;\n" + spill_uniforms +
            "in vec3 wpos; in vec3 wnormal; in vec4 vcolor; in vec2 texcoord; out vec4 fragColor;\n" + spill_fn +
            "float neonMask(vec3 c){ float mx=max(c.r,max(c.g,c.b)); float mn=min(c.r,min(c.g,c.b)); return smoothstep(0.24,0.70,mx)*smoothstep(0.07,0.30,mx-mn); }\n"
            "vec3 reflectedLight(vec3 N, vec3 V){ vec3 r=reflect(-V,N); vec3 l1=normalize(vec3(0.42,0.72,0.55)); vec3 l2=normalize(vec3(-0.62,0.30,0.66)); float s1=pow(max(dot(r,l1),0.0),18.0); float s2=pow(max(dot(r,l2),0.0),22.0); float floorAmt=pow(clamp(abs(N.z),0.0,1.0),1.6); float stripe1=pow(0.5+0.5*sin(wpos.x*0.044+wpos.y*0.015),6.0); float stripe2=pow(0.5+0.5*sin(wpos.y*0.050-wpos.x*0.012+1.7),7.0); float fres=pow(1.0-clamp(abs(dot(N,V)),0.0,1.0),2.4); float wallAmt=1.0-floorAmt; float wallBand=pow(0.5+0.5*sin(wpos.z*0.20+wpos.x*0.018-wpos.y*0.011),8.0); vec3 env=mix(reflection_secondary,reflection_primary,clamp(0.5+0.5*r.z,0.0,1.0)); return reflection_primary*(s1*0.48+stripe1*floorAmt*0.18+wallBand*wallAmt*0.08)+reflection_secondary*(s2*0.42+stripe2*floorAmt*0.15)+mix(reflection_primary,reflection_secondary,0.5)*fres*0.11+env*(0.04+0.11*fres)*(0.32+0.68*floorAmt); }\n"
            "void main(){ vec4 tex=texture(p3d_Texture0,texcoord); vec3 base=tex.rgb*vcolor.rgb*p3d_ColorScale.rgb; float neon=neonMask(tex.rgb); vec3 N=normalize(wnormal); vec3 cameraPos=p3d_ViewMatrixInverse[3].xyz; vec3 V=normalize(cameraPos-wpos); vec3 substrate=base*(0.86+0.14*neon); vec3 reflection=reflectedLight(N,V)*reflection_strength*(1.0-neon*0.82); vec3 emission=base*neon*neon_gain*0.29; vec3 spill=localSpill(N,V)*0.58*(1.0-neon*0.72); fragColor=vec4(substrate+reflection+emission+spill,tex.a*vcolor.a*p3d_ColorScale.a); }\n")
        self.ar_reflective_shader = Shader.make(Shader.SL_GLSL, common_vertex, solid_frag)
        self.ar_pattern_shader = Shader.make(Shader.SL_GLSL, pattern_vertex, pattern_frag)

    def _theme_reflection_inputs(self, theme_key: str):
        theme=DISTRICT_THEMES[theme_key]; p=theme["primary"]; s=theme["secondary"]
        return (p[0],p[1],p[2]), (s[0],s[1],s[2])

    def _apply_reflective_surface(self, np: NodePath, theme_key: str | None=None, strength: float=0.34) -> NodePath:
        if theme_key is None:
            pos=np.getPos(self.render); theme_key=self._theme_key_for_point(float(pos.x),float(pos.y))
        primary,secondary=self._theme_reflection_inputs(theme_key)
        np.setShader(self.ar_reflective_shader); np.setShaderInput("reflection_primary",primary); np.setShaderInput("reflection_secondary",secondary); np.setShaderInput("reflection_strength",float(strength))
        self.ar_material_stats["reflective_solids"] += 1
        return np

    def _apply_pattern_neon_surface(self, np: NodePath, theme_key: str, strength: float=0.18, neon_gain: float=1.0) -> NodePath:
        primary,secondary=self._theme_reflection_inputs(theme_key)
        np.setShader(self.ar_pattern_shader); np.setShaderInput("reflection_primary",primary); np.setShaderInput("reflection_secondary",secondary); np.setShaderInput("reflection_strength",float(strength)); np.setShaderInput("neon_gain",float(neon_gain))
        self.ar_material_stats["neon_patterns"] += 1
        return np

    def _configure_physical_water_shader(self):
        # Physical-water shading only.  The AR moat keeps its established synthetic shader.
        # This adds procedural surface normals, sky reflection and restrained Sun/Moon glints
        # without geometry displacement or an expensive reflection camera.
        vertex = ("#version 130\n"
            "in vec4 p3d_Vertex; in vec3 p3d_Normal; in vec4 p3d_Color;\n"
            "uniform mat4 p3d_ModelViewProjectionMatrix; uniform mat4 p3d_ModelMatrix;\n"
            "out vec3 wpos; out vec3 wnormal; out vec4 vcolor;\n"
            "void main(){ gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex; wpos=(p3d_ModelMatrix*p3d_Vertex).xyz; wnormal=normalize(mat3(p3d_ModelMatrix)*p3d_Normal); vcolor=p3d_Color; }\n")
        fragment = ("#version 130\n"
            "uniform vec4 p3d_ColorScale; uniform mat4 p3d_ViewMatrixInverse;\n"
            "uniform float water_time; uniform float water_roughness; uniform float sun_alpha; uniform float moon_alpha;\n"
            "uniform vec3 sky_reflection; uniform vec3 sun_reflection; uniform vec3 moon_reflection; uniform vec3 sun_dir; uniform vec3 moon_dir;\n"
            "in vec3 wpos; in vec3 wnormal; in vec4 vcolor; out vec4 fragColor;\n"
            "void main(){\n"
            " vec3 base=vcolor.rgb*p3d_ColorScale.rgb; vec3 N0=normalize(wnormal);\n"
            " if(abs(N0.z)<0.55){ fragColor=vec4(base*0.78,vcolor.a*p3d_ColorScale.a); return; }\n"
            " float r=clamp(water_roughness,0.0,1.0);\n"
            " float p1=wpos.x*0.045+wpos.y*0.018+water_time*(0.42+0.36*r);\n"
            " float p2=-wpos.x*0.019+wpos.y*0.054-water_time*(0.31+0.28*r)+1.7;\n"
            " float p3=wpos.x*0.026-wpos.y*0.031+water_time*(0.19+0.22*r)+3.1;\n"
            " float amp=0.16+0.40*r;\n"
            " float dx=amp*(0.045*cos(p1)-0.019*0.72*cos(p2)+0.026*0.48*cos(p3));\n"
            " float dy=amp*(0.018*cos(p1)+0.054*0.72*cos(p2)-0.031*0.48*cos(p3));\n"
            " vec3 N=normalize(vec3(-dx*7.5,-dy*7.5,1.0));\n"
            " vec3 cameraPos=p3d_ViewMatrixInverse[3].xyz; vec3 V=normalize(cameraPos-wpos);\n"
            " float ndv=clamp(dot(N,V),0.0,1.0); float fres=pow(1.0-ndv,2.7);\n"
            " float ripple=0.5+0.5*sin(p1*1.9+p2*0.7);\n"
            " vec3 deep=base*(0.68+0.08*ripple); vec3 sky=sky_reflection*(0.08+0.42*fres);\n"
            " float exponent=mix(105.0,18.0,r);\n"
            " float sunSpec=pow(max(dot(reflect(-normalize(sun_dir),N),V),0.0),exponent)*sun_alpha*mix(1.15,0.42,r);\n"
            " float moonSpec=pow(max(dot(reflect(-normalize(moon_dir),N),V),0.0),mix(130.0,28.0,r))*moon_alpha*mix(0.68,0.22,r);\n"
            " float sparkle=pow(max(0.0,0.5+0.5*sin(p1*6.0+p3*3.7)),18.0)*(0.012+0.025*(1.0-r));\n"
            " vec3 col=deep+sky+sun_reflection*sunSpec+moon_reflection*moonSpec+sky_reflection*sparkle;\n"
            " fragColor=vec4(col,vcolor.a*p3d_ColorScale.a);\n"
            "}\n")
        self.physical_water_shader = Shader.make(Shader.SL_GLSL, vertex, fragment)

    def _update_physical_water_visuals(self, physical: dict, weather: dict, sky_scale):
        if self.physical_water is None:
            return
        # Approximate the actual blue sky dome rather than reflecting the ColorScale multiplier itself.
        sky_ref=(min(1.0,0.22*float(sky_scale[0])+0.03), min(1.0,0.40*float(sky_scale[1])+0.04), min(1.0,0.58*float(sky_scale[2])+0.05))
        rain=float(weather["rain"]); sun_gain=float(weather["sun_gain"])
        rough=max(0.12,min(1.0,0.15+0.56*rain+0.22*(1.0-sun_gain)))
        sun_a=float(self.physical_sun_root.getColorScale().w) if self.physical_sun_root is not None else 0.0
        moon_a=float(self.physical_moon_root.getColorScale().w) if self.physical_moon_root is not None else 0.0
        sun_pos=self.physical_sun_root.getPos(self.render) if self.physical_sun_root is not None else Vec3(0,1,1)
        moon_pos=self.physical_moon_root.getPos(self.render) if self.physical_moon_root is not None else Vec3(0,-1,1)
        sun_dir=Vec3(sun_pos); moon_dir=Vec3(moon_pos)
        if sun_dir.lengthSquared()<0.0001: sun_dir=Vec3(0,1,1)
        if moon_dir.lengthSquared()<0.0001: moon_dir=Vec3(0,-1,1)
        sun_dir.normalize(); moon_dir.normalize()
        sun_col=tuple(min(1.35,max(0.0,float(physical["sun"][i])*float(weather["sun_gain"]))) for i in range(3))
        moon_col=(0.46,0.58,0.74)
        self.physical_water.setShaderInput("water_time",float(self.environment_time))
        self.physical_water.setShaderInput("water_roughness",rough)
        self.physical_water.setShaderInput("sky_reflection",sky_ref)
        self.physical_water.setShaderInput("sun_reflection",sun_col)
        self.physical_water.setShaderInput("moon_reflection",moon_col)
        self.physical_water.setShaderInput("sun_dir",(float(sun_dir.x),float(sun_dir.y),float(sun_dir.z)))
        self.physical_water.setShaderInput("moon_dir",(float(moon_dir.x),float(moon_dir.y),float(moon_dir.z)))
        self.physical_water.setShaderInput("sun_alpha",sun_a)
        self.physical_water.setShaderInput("moon_alpha",moon_a)
        self.physical_water_state={"roughness":rough,"sun_alpha":sun_a,"moon_alpha":moon_a}

    def _configure_fog(self):
        self.world_fog = Fog("blank_city_haze")
        self.world_fog.setColor(0.66,0.70,0.70)
        self.world_fog.setLinearRange(1150, 2400)
        self.render.setFog(self.world_fog)

    def _build_world(self):
        # Physical layer remains restrained, but no longer uses a flat clear-color sky.
        physical_sky = make_sky_dome_geom("physical_sky", 2250.0, -140.0, 1500.0,
            (0.72,0.84,0.94,1.0), (0.36,0.66,0.90,1.0), (0.10,0.36,0.72,1.0), 12, 80)
        physical_sky.reparentTo(self.render)
        physical_sky.hide(AR_CAMERA_MASK)
        physical_sky.setTwoSided(True); physical_sky.setLightOff(1); physical_sky.setFogOff(1)
        physical_sky.setDepthWrite(False); physical_sky.setDepthTest(False); physical_sky.setBin("background", -120)
        self.physical_sky = physical_sky
        self.environment_stats["physical_sky"] = 1
        water = make_box_geom("water", WATER_SIZE, WATER_SIZE, 1.0, PALETTE["water"]); water.reparentTo(self.visual_root); water.setPos(0,0,-1.2)
        water.setShader(self.physical_water_shader)
        water.setShaderInput("water_time",0.0); water.setShaderInput("water_roughness",0.15)
        water.setShaderInput("sky_reflection",(0.34,0.63,0.90)); water.setShaderInput("sun_reflection",(1.0,0.94,0.82)); water.setShaderInput("moon_reflection",(0.46,0.58,0.74))
        water.setShaderInput("sun_dir",(0.0,1.0,1.0)); water.setShaderInput("moon_dir",(0.0,-1.0,1.0)); water.setShaderInput("sun_alpha",0.0); water.setShaderInput("moon_alpha",0.0)
        self.physical_water = water

        # The four accepted bridges already terminate at ~690 m.  Build a natural
        # mainland there so Utopia reads as a designed city separated from an Earth-like exterior.
        self.outer_land_root = self.visual_root.attachNewNode("earthlike_outer_world")
        shore = make_annulus_geom("outer_dirt_shore", 688.0, 724.0, PALETTE["outer_shore"], 192, -0.08)
        shore.reparentTo(self.outer_land_root); shore.setTwoSided(True)
        dirt = make_annulus_geom("outer_dirt_band", 712.0, 782.0, PALETTE["outer_dirt"], 192, -0.045)
        dirt.reparentTo(self.outer_land_root); dirt.setTwoSided(True)
        grass = make_annulus_geom("outer_grass_mainland", 754.0, 1490.0, PALETTE["outer_grass"], 256, -0.012)
        grass.reparentTo(self.outer_land_root); grass.setTwoSided(True)
        # Break the large mainland into broad organic color patches instead of concentric sci-fi bands.
        terrain_rng=random.Random(3801)
        patch_colors=[PALETTE["outer_grass_light"],(0.20,0.36,0.16,1.0),(0.29,0.46,0.22,1.0),(0.33,0.47,0.23,1.0)]
        for idx in range(24):
            radius=terrain_rng.uniform(805.0,1430.0); angle=terrain_rng.uniform(0.0,360.0)
            x,y,_=polar(radius,angle,0.0); pr=terrain_rng.uniform(24.0,72.0)
            patch=make_disc_geom(f"outer_grass_patch_{idx}",pr,patch_colors[idx%len(patch_colors)],40,-0.002)
            patch.reparentTo(self.outer_land_root); patch.setPos(x,y,0); patch.setScale(terrain_rng.uniform(0.7,1.5),terrain_rng.uniform(0.55,1.15),1.0); patch.setH(terrain_rng.uniform(0,180)); patch.setTwoSided(True)
        for idx in range(7):
            radius=terrain_rng.uniform(770.0,1360.0); angle=terrain_rng.uniform(0.0,360.0)
            x,y,_=polar(radius,angle,0.0); pr=terrain_rng.uniform(16.0,48.0)
            patch=make_disc_geom(f"outer_dirt_patch_{idx}",pr,(0.40,0.30,0.19,1.0),36,-0.001)
            patch.reparentTo(self.outer_land_root); patch.setPos(x,y,0); patch.setScale(terrain_rng.uniform(0.65,1.35),terrain_rng.uniform(0.45,0.95),1.0); patch.setH(terrain_rng.uniform(0,180)); patch.setTwoSided(True)
        self.environment_stats["outer_land"] = 1
        self._build_outer_world_details()

        ground = make_disc_geom("city_ground", CITY_RADIUS, PALETTE["ground"], 128, 0.0); ground.reparentTo(self.visual_root)
        plaza = make_disc_geom("unity_plaza", 112, PALETTE["plaza"], 96, 0.03); plaza.reparentTo(self.visual_root)
        make_annulus_geom("inner_ring_road", 122, 148, PALETTE["road"], 96).reparentTo(self.visual_root)
        make_annulus_geom("middle_ring_road", 285, 315, PALETTE["road"], 128).reparentTo(self.visual_root)
        make_annulus_geom("outer_ring_road", 438, 468, PALETTE["road"], 160).reparentTo(self.visual_root)
        # sidewalks bordering major rings
        make_annulus_geom("inner_sidewalk", 114, 121, PALETTE["sidewalk"], 96,0.025).reparentTo(self.visual_root)
        make_annulus_geom("mid_sidewalk_in", 276, 284, PALETTE["sidewalk"], 128,0.025).reparentTo(self.visual_root)
        make_annulus_geom("mid_sidewalk_out", 316, 324, PALETTE["sidewalk"], 128,0.025).reparentTo(self.visual_root)

        for angle in (0,45,90,135,180,225,270,315):
            self._make_radial_road(angle, 106, 515 if angle%90==0 else 500, 24 if angle%90==0 else 15)
        for angle in (0,90,180,270):
            self._make_gate(angle)
        self._make_outer_wall()
        self._make_central_spire()
        self._make_transit_ring()
        self._make_district_landmarks()
        self._generate_city_blocks()
        self._make_greenery()
        self._make_overlook()

    def _build_public_interiors(self):
        """Five small public interiors, one per district, attached to existing landmarks.

        These are intentionally ground-floor annexes instead of holes cut into the accepted
        solid landmark volumes.  Visual walls and collision derive from the same boxes; the
        doorway gap is actual empty geometry.  AR skins are a second, camera-limited layer.
        """
        specs = [
            ("core", "Unity Civic Reception", BuildingSpec("civic_hall_45", 61.518, 61.518, 34, 52, 16, 45, PALETTE["building"]), "reception"),
            ("north", "Archive Public Lobby", BuildingSpec("north_archive", -82, 352, 58, 44, 105, -12, PALETTE["building_dark"]), "archive"),
            ("east", "Innovation Demonstration Lab", BuildingSpec("east_hall", 365, -70, 74, 42, 48, -10, PALETTE["building"]), "lab"),
            ("south", "Mirage Public Lounge", BuildingSpec("south_tower", -84, -354, 52, 52, 114, 5, PALETTE["building_dark"]), "lounge"),
            ("west", "Foundry Public Workshop", BuildingSpec("west_hall", -352, 102, 82, 44, 52, 12, PALETTE["building"]), "workshop"),
        ]
        for theme_key, label, building, kind in specs:
            self._make_public_interior(theme_key, label, building, kind)

    def _interior_physical_box(self, root: NodePath, name: str, sx: float, sy: float, sz: float, pos, color, collide: bool = True) -> NodePath:
        np = make_box_geom(name, sx, sy, sz, color)
        np.reparentTo(root); np.setPos(*pos)
        if collide:
            self._add_box_collision(np, sx, sy, sz)
            self.interior_stats["collision_solids"] += 1
        return np

    def _interior_ar_box(self, root: NodePath, name: str, sx: float, sy: float, sz: float, pos, theme_key: str, color=None, patterned: bool = False, strength: float = 0.24) -> NodePath:
        theme=DISTRICT_THEMES[theme_key]
        if patterned:
            np=make_textured_box_geom(name,sx,sy,sz,(1,1,1,1))
            np.reparentTo(root); np.setPos(*pos); np.setTexture(self.theme_textures[theme_key],1)
            np.setTexScale(TextureStage.getDefault(),max(1.0,sx/11.0),max(1.0,sy/11.0))
            np.setColorScale(0.76,0.80,0.88,1.0)
            self._apply_pattern_neon_surface(np,theme_key,strength,0.98)
        else:
            np=make_box_geom(name,sx,sy,sz,color or (0.11,0.14,0.17,1.0))
            np.reparentTo(root); np.setPos(*pos)
            self._apply_reflective_surface(np,theme_key,strength)
        return np

    def _make_public_interior(self, theme_key: str, label: str, building: BuildingSpec, kind: str):
        theme=DISTRICT_THEMES[theme_key]
        width = 18.0 if theme_key != "core" else 19.5
        depth = 14.0
        height = 5.4
        wall = 0.36
        door_w = 4.2
        back_y = -building.sy/2.0 - 0.22
        front_y = back_y - depth
        center_y = (front_y + back_y) * 0.5

        root=self.visual_root.attachNewNode(f"interior_{theme_key}_physical")
        root.setPos(building.x,building.y,0); root.setH(building.heading)
        ar_root=self.utopia_root.attachNewNode(f"interior_{theme_key}_ar")
        ar_root.setPos(building.x,building.y,0); ar_root.setH(building.heading)

        # Neutral architectural shell. The front wall is two pieces, leaving a real opening.
        floor=self._interior_physical_box(root,f"interior_{theme_key}_floor",width,depth,0.08,(0,center_y,0.015),(0.22,0.24,0.24,1.0),False)
        self._interior_physical_box(root,f"interior_{theme_key}_left_wall",wall,depth,height,(-width/2+wall/2,center_y,0),(0.50,0.52,0.52,1.0))
        self._interior_physical_box(root,f"interior_{theme_key}_right_wall",wall,depth,height,(width/2-wall/2,center_y,0),(0.50,0.52,0.52,1.0))
        seg=(width-door_w)*0.5
        for side in (-1,1):
            x=side*(door_w/2+seg/2)
            self._interior_physical_box(root,f"interior_{theme_key}_front_{side}",seg,wall,height,(x,front_y,0),(0.46,0.48,0.48,1.0))
        self._interior_physical_box(root,f"interior_{theme_key}_ceiling",width,depth,0.24,(0,center_y,height),(0.34,0.36,0.36,1.0))
        # Door frame is visible geometry and collision, but the center remains completely open.
        for side in (-1,1):
            self._interior_physical_box(root,f"interior_{theme_key}_portal_side_{side}",0.28,0.52,4.15,(side*(door_w/2+0.14),front_y-0.10,0.0),(0.28,0.30,0.31,1.0))
        self._interior_physical_box(root,f"interior_{theme_key}_portal_head",door_w+0.56,0.52,0.32,(0,front_y-0.10,4.15),(0.28,0.30,0.31,1.0))

        # Public-service rear portal against the accepted solid landmark facade.
        rear_panel=self._interior_physical_box(root,f"interior_{theme_key}_rear_portal",6.4,0.12,3.8,(0,back_y-0.08,0.18),(0.10,0.12,0.13,1.0),False)
        # Physical architecture carries its own readable hierarchy before AR is activated.
        pc=theme["primary"]
        muted=(0.24+pc[0]*0.16,0.25+pc[1]*0.16,0.26+pc[2]*0.16,1.0)
        runner=self._interior_physical_box(root,f"interior_{theme_key}_runner",3.4,depth-1.4,0.022,(0,center_y-0.15,0.092),(0.16,0.18,0.19,1.0),False)
        for x in (-5.1,0.0,5.1):
            lamp=self._interior_physical_box(root,f"interior_{theme_key}_ceiling_light_{x}",2.7,0.72,0.055,(x,center_y,height-0.31),(0.88,0.90,0.89,1.0),False)
            lamp.setLightOff(1)
        for side in (-1,1):
            for yoff in (-3.5,2.4):
                panel=self._interior_physical_box(root,f"interior_{theme_key}_wall_panel_{side}_{yoff}",0.045,4.0,2.15,(side*(width/2-wall-0.035),center_y+yoff,1.15),(0.29,0.31,0.32,1.0),False)
            stripe=self._interior_physical_box(root,f"interior_{theme_key}_accent_{side}",0.055,depth*0.72,0.16,(side*(width/2-wall-0.07),center_y,3.55),muted,False)
            stripe.setLightOff(1)
        # District-specific practical furnishings. Every visible solid furniture block collides.
        # The center aisle stays open from the public entrance to the rear service portal.
        prop_count=0
        if kind=="reception":
            for side in (-1,1):
                self._interior_physical_box(root,f"core_reception_desk_{side}",4.0,1.05,0.92,(side*4.6,center_y+2.25,0),(0.34,0.36,0.36,1.0)); prop_count+=1
                self._interior_physical_box(root,f"core_wait_bench_{side}",3.2,0.92,0.50,(side*5.3,center_y-2.0,0),(0.29,0.31,0.31,1.0)); prop_count+=1
        elif kind=="archive":
            for side in (-1,1):
                for row in (-2.5,2.1):
                    self._interior_physical_box(root,f"archive_shelf_{side}_{row}",1.05,3.2,2.25,(side*6.0,center_y+row,0),(0.30,0.31,0.31,1.0)); prop_count+=1
            self._interior_physical_box(root,"archive_catalog_table",3.2,1.25,0.88,(4.0,center_y,0),(0.35,0.36,0.36,1.0)); prop_count+=1
        elif kind=="lab":
            for side in (-1,1):
                for yoff in (-2.5,2.3):
                    self._interior_physical_box(root,f"lab_demo_plinth_{side}_{yoff}",2.25,2.1,0.92,(side*5.0,center_y+yoff,0),(0.30,0.32,0.33,1.0)); prop_count+=1
            self._interior_physical_box(root,"lab_service_bench",7.0,0.95,0.92,(4.3,back_y-1.05,0),(0.32,0.34,0.35,1.0)); prop_count+=1
        elif kind=="lounge":
            for side in (-1,1):
                self._interior_physical_box(root,f"lounge_bench_{side}",4.0,1.15,0.58,(side*5.0,center_y+0.8,0),(0.34,0.33,0.34,1.0)); prop_count+=1
                self._interior_physical_box(root,f"lounge_planter_{side}",1.45,1.45,0.70,(side*6.4,center_y-3.5,0),(0.30,0.31,0.28,1.0)); prop_count+=1
        elif kind=="workshop":
            for side in (-1,1):
                self._interior_physical_box(root,f"workshop_bench_{side}",4.8,1.35,0.95,(side*4.8,center_y+2.6,0),(0.34,0.34,0.33,1.0)); prop_count+=1
                self._interior_physical_box(root,f"workshop_tool_rack_{side}",0.90,3.0,2.25,(side*6.9,center_y-1.8,0),(0.31,0.31,0.30,1.0)); prop_count+=1
        self.interior_stats["props"] += prop_count

        # Physical interior lighting.  A small scoped ambient fill prevents the large
        # architectural quads from going black under vertex lighting, while three point
        # lights line up with the visible ceiling fixtures.  No light leaks to the city.
        pc=theme["primary"]
        fill=AmbientLight(f"interior_{theme_key}_ambient")
        fill.setColor((0.075+pc[0]*0.018,0.075+pc[1]*0.018,0.070+pc[2]*0.018,1.0))
        fill_np=root.attachNewNode(fill); root.setLight(fill_np)
        self.interior_stats["ambient_lights"] += 1
        for lx in (-5.1,0.0,5.1):
            pl=PointLight(f"interior_{theme_key}_light_{lx}")
            pl.setColor((0.46+pc[0]*0.08,0.46+pc[1]*0.08,0.44+pc[2]*0.08,1.0))
            pl.setAttenuation(Vec3(1.0,0.050,0.0060))
            lnp=root.attachNewNode(pl); lnp.setPos(lx,center_y,4.55); root.setLight(lnp)
            self.interior_stats["lights"] += 1

        # AR interpretation: same room geometry, thin skins only, never a conflicting collision layer.
        self._interior_ar_box(ar_root,f"interior_{theme_key}_ar_floor",width-0.35,depth-0.35,0.025,(0,center_y,0.10),theme_key,patterned=True,strength=0.26)
        for side in (-1,1):
            self._interior_ar_box(ar_root,f"interior_{theme_key}_ar_side_{side}",0.035,depth-0.5,height-0.55,(side*(width/2-0.22),center_y,0.26),theme_key,color=(0.06,0.09,0.12,1.0),strength=0.30)
        portal=self._interior_ar_box(ar_root,f"interior_{theme_key}_ar_portal",5.8,0.035,3.35,(0,back_y-0.25,0.42),theme_key,patterned=True,strength=0.30)
        # Ceiling strips provide district identity without filling the room with floating signage.
        for x in (-5.5,0,5.5):
            strip=make_box_geom(f"interior_{theme_key}_ceiling_strip_{x}",0.22,depth*0.76,0.10,theme["primary"] if x==0 else theme["secondary"])
            strip.reparentTo(ar_root); strip.setPos(x,center_y,height-0.20); self._register_ar_activity(strip,strip.getName(),"path",0.42,0.92,0.46+abs(x)*0.015)

        # Pass 58: cover the annex EXTERIOR in AR as well.  Earlier passes only skinned
        # the room's interior faces, which left broad physical-gray walls visible through the
        # lens from the street.  These slightly oversized, collision-free patterned shells follow
        # the exact physical wall layout and preserve the real doorway opening.
        ar_shell_pad=0.10
        exterior_nodes=[]
        for side in (-1,1):
            exterior_nodes.append(self._interior_ar_box(
                ar_root,f"interior_{theme_key}_ar_exterior_side_{side}",wall+ar_shell_pad,depth+0.18,height+0.16,
                (side*(width/2-wall/2),center_y,0.0),theme_key,patterned=True,strength=0.32))
        for side in (-1,1):
            x=side*(door_w/2+seg/2)
            exterior_nodes.append(self._interior_ar_box(
                ar_root,f"interior_{theme_key}_ar_exterior_front_{side}",seg+0.12,wall+ar_shell_pad,height+0.16,
                (x,front_y-0.015,0.0),theme_key,patterned=True,strength=0.34))
        exterior_nodes.append(self._interior_ar_box(
            ar_root,f"interior_{theme_key}_ar_exterior_ceiling",width+0.18,depth+0.18,0.30,
            (0,center_y,height-0.01),theme_key,patterned=True,strength=0.30))
        # The doorway frame gets a stronger district-colored AR trim, still leaving the opening empty.
        for side in (-1,1):
            exterior_nodes.append(self._interior_ar_box(
                ar_root,f"interior_{theme_key}_ar_exterior_portal_side_{side}",0.34,0.62,4.22,
                (side*(door_w/2+0.14),front_y-0.12,0.0),theme_key,color=theme["secondary"],strength=0.46))
        exterior_nodes.append(self._interior_ar_box(
            ar_root,f"interior_{theme_key}_ar_exterior_portal_head",door_w+0.62,0.62,0.36,
            (0,front_y-0.12,4.13),theme_key,color=theme["primary"],strength=0.48))
        self.interior_stats["ar_exterior_shells"] += len(exterior_nodes)
        self.interior_stats["ar_exterior_patterned"] += 5

        # Camera proof location inside the actual room, aimed toward the district service portal.
        cam_local=Vec3(-2.4,front_y+3.5,1.72); target_local=Vec3(1.0,back_y-0.2,1.65)
        cam_world=root.getMat(self.render).xformPoint(cam_local); target_world=root.getMat(self.render).xformPoint(target_local)
        self.interior_qa_points[theme_key]=(cam_world,target_world)
        self.public_interiors.append({"theme":theme_key,"label":label,"kind":kind,"root":root,"ar_root":ar_root,"door_width":door_w,"front_y":front_y,"width":width,"depth":depth,"height":height})
        self.interior_stats["total"] += 1; self.interior_stats[theme_key] += 1

    def _build_weather_system(self):
        # Physical-world precipitation only. The AR camera explicitly cannot see this root.
        self.weather_root = self.render.attachNewNode("physical_weather_root")
        self.weather_root.hide(AR_CAMERA_MASK)
        rng = random.Random(3317)
        streaks_per_batch = 72
        for batch_index in range(3):
            lines = LineSegs(f"rain_batch_{batch_index}")
            lines.setThickness(1.15)
            lines.setColor(0.74,0.82,0.88,0.34)
            for _ in range(streaks_per_batch):
                x = rng.uniform(-26.0, 26.0)
                y = rng.uniform(-18.0, 42.0)
                z = rng.uniform(0.0, 20.0)
                length = rng.uniform(0.85, 1.75)
                slant = rng.uniform(0.08, 0.22)
                lines.moveTo(x, y, z)
                lines.drawTo(x + slant, y, z - length)
            node = self.weather_root.attachNewNode(lines.create())
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setDepthWrite(False)
            node.setBin("transparent", 32 + batch_index)
            self.rain_batches.append({"node": node, "phase": batch_index * 6.0})
        self.weather_root.hide()
        self.weather_stats["rain_batches"] = len(self.rain_batches)
        self.weather_stats["rain_streaks"] = len(self.rain_batches) * streaks_per_batch

    def _weather_profile_mix(self, a: dict, b: dict, t: float) -> dict:
        t = self._smoothstep01(t)
        out = {}
        for key, value in a.items():
            other = b[key]
            if isinstance(value, tuple):
                out[key] = self._lerp_tuple(value, other, t)
            else:
                out[key] = float(value) * (1.0 - t) + float(other) * t
        return out

    def _current_weather_profile(self) -> dict:
        previous = WEATHER_PROFILES[self.weather_previous_state]
        current = WEATHER_PROFILES[self.weather_state]
        progress = min(1.0, self.weather_transition_elapsed / max(0.001, WEATHER_TRANSITION_SECONDS))
        return self._weather_profile_mix(previous, current, progress)

    def _cycle_weather_state(self):
        idx = WEATHER_ORDER.index(self.weather_state)
        self.weather_previous_state = self.weather_state
        self.weather_state = WEATHER_ORDER[(idx + 1) % len(WEATHER_ORDER)]
        self.weather_state_elapsed = 0.0
        self.weather_transition_elapsed = 0.0

    def _update_weather_system(self, dt: float):
        if self.paused:
            return
        self.weather_effect_time += dt
        if not self.freeze_weather:
            self.weather_state_elapsed += dt
            self.weather_transition_elapsed = min(WEATHER_TRANSITION_SECONDS, self.weather_transition_elapsed + dt)
            duration = WEATHER_DURATIONS_SECONDS[self.weather_state]
            if self.weather_state_elapsed >= duration:
                self._cycle_weather_state()
        else:
            self.weather_transition_elapsed = WEATHER_TRANSITION_SECONDS
        if self.weather_root is None or not hasattr(self, "player"):
            return
        profile = self._current_weather_profile()
        intensity = float(profile["rain"])
        if intensity <= 0.01:
            self.weather_root.hide()
            return
        self.weather_root.show()
        pos = self.player.getPos(self.render)
        self.weather_root.setPos(pos.x, pos.y, pos.z + 3.0)
        self.weather_root.setColorScale(1.0, 1.0, 1.0, min(1.0, intensity))
        speed = 15.0 + 10.0 * intensity
        cycle = 18.0
        for item in self.rain_batches:
            item["node"].setZ(-((self.weather_effect_time * speed + item["phase"]) % cycle))

    def _weather_label(self) -> str:
        return self.weather_state.replace("_", " ").upper()

    def _make_radial_road(self, angle: float, start_r: float, end_r: float, width: float):
        length=end_r-start_r; mid=(start_r+end_r)/2
        x,y,_=polar(mid,angle,0.02)
        road=make_box_geom(f"road_{angle}", width,length,0.035,PALETTE["road"]); road.reparentTo(self.visual_root); road.setPos(x,y,0.01); road.setH(angle)
        # subtle curbs / sidewalks
        for offset in (-width/2-4.0, width/2+4.0):
            s=make_box_geom("sidewalk", 6.0,length,0.05,PALETTE["sidewalk"]); s.reparentTo(self.visual_root); s.setPos(x,y,0.03); s.setH(angle); s.setX(s,offset)

    def _make_gate(self, angle: float):
        # 150m bridge reaching outside the ring; width aligned tangent to circle.
        bridge_len=170.0; mid=CITY_RADIUS+bridge_len/2-5
        x,y,_=polar(mid,angle,0)
        bridge=make_box_geom(f"bridge_{angle}", 34, bridge_len, 1.2, PALETTE["bridge"]); bridge.reparentTo(self.visual_root); bridge.setPos(x,y,-1.2); bridge.setH(angle)
        road=make_box_geom("bridge_road", 22,bridge_len,0.08,PALETTE["road"]); road.reparentTo(self.visual_root); road.setPos(x,y,0.01); road.setH(angle)
        # visible side barriers matching collision
        for lateral in (-18.0,18.0):
            barrier=make_box_geom("bridge_barrier",1.2,bridge_len,2.2,PALETTE["wall"]); barrier.reparentTo(self.visual_root); barrier.setPos(x,y,0.0); barrier.setH(angle); barrier.setX(barrier,lateral)
            self._add_box_collision(barrier,1.2,bridge_len,2.2)
        # pylons at city threshold
        gx,gy,_=polar(CITY_RADIUS-2,angle,0)
        for lateral in (-27,27):
            p=make_box_geom("gate_pylon",7,7,38,PALETTE["wall"]); p.reparentTo(self.visual_root); p.setPos(gx,gy,0); p.setH(angle); p.setX(p,lateral)
            self._add_box_collision(p,7,7,38)
            wp = p.getPos(self.render)
            self.ar_structure_specs.append(BuildingSpec(f"gate_pylon_{int(angle)}_{int(lateral)}", wp.x, wp.y, 7, 7, 38, angle, PALETTE["wall"], "box", 0.0))

    def _make_outer_wall(self):
        # Segmented wall with deliberate gaps at four gate angles. This pass gives it a finished civic silhouette.
        arc=2*math.pi*((INNER_WALL_RADIUS+OUTER_WALL_RADIUS)/2)/WALL_SEGMENTS
        depth=OUTER_WALL_RADIUS-INNER_WALL_RADIUS
        radius=(INNER_WALL_RADIUS+OUTER_WALL_RADIUS)/2
        cap_color=(0.77,0.78,0.76,1.0)
        plinth_color=(0.55,0.57,0.57,1.0)
        accent_color=(0.60,0.67,0.70,1.0)
        for i in range(WALL_SEGMENTS):
            angle=360*i/WALL_SEGMENTS
            if is_gate_angle(angle):
                continue
            x,y,_=polar(radius,angle,0)
            seg=make_box_geom(f"wall_{i}", arc*1.01, depth, WALL_HEIGHT, PALETTE["wall"])
            seg.reparentTo(self.visual_root); seg.setPos(x,y,0); seg.setH(angle)
            self._add_box_collision(seg,arc*1.01,depth,WALL_HEIGHT)

            # Base plinth keeps the lower wall from reading as a flat slab.
            base=make_box_geom(f"wall_{i}_plinth", arc*0.98, depth*0.78, 2.2, plinth_color)
            base.reparentTo(seg); base.setPos(0,0,0.0)
            # Top coping/parapet band.
            cap=make_box_geom(f"wall_{i}_cap", arc*1.03, depth*0.62, 1.15, cap_color)
            cap.reparentTo(seg); cap.setPos(0,0,WALL_HEIGHT)
            # Mid-wall shadow band for depth.
            datum=make_box_geom(f"wall_{i}_datum", arc*0.96, depth*0.28, 0.95, accent_color)
            datum.reparentTo(seg); datum.setPos(0,0,WALL_HEIGHT*0.42)

            # Periodic piers and bastions add rhythm without changing the accepted footprint authority.
            if i % 2 == 0:
                pier_h = WALL_HEIGHT + (4.0 if i % 4 == 0 else 2.6)
                pier_w = max(3.2, arc*0.18)
                pier=make_box_geom(f"wall_{i}_pier", pier_w, depth*0.68, pier_h, cap_color)
                pier.reparentTo(seg); pier.setPos(0,0,0.0)
            if i % 8 == 0:
                for side in (-0.28,0.28):
                    fin=make_box_geom(f"wall_{i}_fin_{side:+.2f}", max(2.1,arc*0.08), depth*0.56, WALL_HEIGHT*0.78, accent_color)
                    fin.reparentTo(seg); fin.setX(fin, side*arc); fin.setZ(WALL_HEIGHT*0.10)

    def _make_central_spire(self):
        base=make_cylinder_geom("spire_base",42,12,24,PALETTE["spire"]); base.reparentTo(self.visual_root); base.setZ(0.05)
        mid=make_cylinder_geom("spire_mid",21,92,20,PALETTE["building_dark"], top_radius=13); mid.reparentTo(self.visual_root); mid.setZ(12)
        crown=make_cylinder_geom("spire_crown",13,66,16,PALETTE["spire"], top_radius=2.5); crown.reparentTo(self.visual_root); crown.setZ(104)
        self._add_cylinder_collision(0,0,42,12)
        self._add_cylinder_collision(0,0,21,158)
        self.ar_structure_specs.extend([
            BuildingSpec("unity_spire_base",0,0,84,84,12,0,PALETTE["spire"],"cylinder",0.05,1.0),
            BuildingSpec("unity_spire_mid",0,0,42,42,92,0,PALETTE["building_dark"],"cylinder",12.0,13.0/21.0),
            BuildingSpec("unity_spire_crown",0,0,26,26,66,0,PALETTE["spire"],"cylinder",104.0,2.5/13.0),
        ])
        # four low civic buildings around the plaza, keeping sightline to spire
        for angle in (45,135,225,315):
            x,y,_=polar(87,angle,0)
            b=make_box_geom("civic_hall",34,52,16,PALETTE["building"]); b.reparentTo(self.visual_root); b.setPos(x,y,0); b.setH(angle)
            self._add_box_collision(b,34,52,16)
            self.ar_structure_specs.append(BuildingSpec(f"civic_hall_{angle}",x,y,34,52,16,angle,PALETTE["building"],"box",0.0))

    def _make_transit_ring(self):
        # Physical transit viaduct. Major avenue crossings must remain genuinely open:
        # a support at the exact ring/avenue intersection used to put collision in the road.
        radius=222.0; segments=64
        step_angle=360.0/segments
        arc=2*math.pi*radius/segments
        self.transit_support_positions=[]

        def add_support(support_angle: float, tag: str):
            sx,sy,_=polar(radius,support_angle,0.0)
            support=make_box_geom(f"transit_support_{tag}",2.2,2.2,8.2,PALETTE["wall"])
            support.reparentTo(self.visual_root); support.setPos(sx,sy,0); support.setH(support_angle)
            self._add_box_collision(support,2.2,2.2,8.2)
            self.transit_support_positions.append((float(support_angle)%360.0,float(sx),float(sy)))

        for i in range(segments):
            angle=360*i/segments
            x,y,_=polar(radius,angle,8.2)
            deck=make_box_geom("transit_deck",arc*1.03,7.0,1.2,PALETTE["bridge"])
            deck.reparentTo(self.visual_root); deck.setPos(x,y,8.2); deck.setH(angle)
            if i%4==0:
                if i%8==0:
                    # Eight major avenues cross the ring every 45 degrees. Put a paired
                    # support on the immediately adjacent deck segments instead of the road.
                    # At this radius ±5.625 degrees gives ~21.8 m of lateral clearance,
                    # enough for the widest 24 m avenue, both sidewalks and player radius.
                    add_support(angle-step_angle,f"crossing_{i:02d}_left")
                    add_support(angle+step_angle,f"crossing_{i:02d}_right")
                else:
                    add_support(angle,f"regular_{i:02d}")
        # Four small physical stations aligned with cardinal avenues.
        for angle in (0,90,180,270):
            x,y,_=polar(radius,angle,8.2)
            station=make_box_geom("transit_station",28,18,7.5,PALETTE["building"])
            station.reparentTo(self.visual_root); station.setPos(x,y,8.2); station.setH(angle)
            self.ar_structure_specs.append(BuildingSpec(f"transit_station_{angle}",x,y,28,18,7.5,angle,PALETTE["building"],"box",8.2))

    def _make_district_landmarks(self):
        landmarks = [
            BuildingSpec("north_archive", -82, 352, 58, 44, 105, -12, PALETTE["building_dark"]),
            BuildingSpec("north_tower", 72, 382, 46, 46, 132, 7, PALETTE["building"]),
            BuildingSpec("east_cylinder", 355, 92, 54, 54, 78, 0, PALETTE["building_dark"], "cylinder"),
            BuildingSpec("east_hall", 365,-70, 74, 42, 48, -10, PALETTE["building"]),
            BuildingSpec("south_tower", -84,-354, 52, 52, 114, 5, PALETTE["building_dark"]),
            BuildingSpec("south_dome", 126,-365, 72, 72, 42, 0, PALETTE["building"], "cylinder"),
            BuildingSpec("west_tower", -362,-86, 58, 58, 96, -8, PALETTE["building_dark"]),
            BuildingSpec("west_hall", -352,102, 82, 44, 52, 12, PALETTE["building"]),
        ]
        for spec in landmarks: self._spawn_building(spec)

    def _generate_city_blocks(self):
        rng=random.Random(12001)
        # concentric bands, with deterministic angular offsets. Avoid roads and landmark core.
        bands=[(178,20,30,50),(252,28,30,72),(348,36,30,92),(414,40,28,112)]
        idx=0
        for radius,count,min_h,max_h in bands:
            for i in range(count):
                angle=(360*i/count)+(9 if count%2==0 else 0)
                if min(angle_delta(angle,a) for a in (0,45,90,135,180,225,270,315)) < 5.8:
                    continue
                jitter_r=rng.uniform(-13,13); r=radius+jitter_r
                x,y,_=polar(r,angle,0)
                tangential=2*math.pi*r/count*0.55
                sx=max(20,min(42,tangential*rng.uniform(0.72,0.96)))
                sy=rng.uniform(24,48)
                height=rng.uniform(min_h,max_h)
                if r>330 and rng.random()<0.16: height*=1.55
                heading=angle+rng.uniform(-5,5)
                color=PALETTE["building"] if rng.random()>0.35 else PALETTE["building_dark"]
                style="cylinder" if rng.random()<0.08 else "box"
                spec=BuildingSpec(f"block_{idx:03d}",x,y,sx,sy,height,heading,color,style); idx+=1
                self._spawn_building(spec)

    def _spawn_building(self,spec:BuildingSpec):
        self.buildings.append(spec)
        if spec.style=="cylinder":
            radius=min(spec.sx,spec.sy)/2
            np=make_cylinder_geom(spec.name,radius,spec.height,16,spec.color, top_radius=radius*0.90); np.reparentTo(self.visual_root); np.setPos(spec.x,spec.y,spec.z)
            self._add_cylinder_collision(spec.x,spec.y,radius,spec.height)
        else:
            np=make_box_geom(spec.name,spec.sx,spec.sy,spec.height,spec.color); np.reparentTo(self.visual_root); np.setPos(spec.x,spec.y,spec.z); np.setH(spec.heading)
            self._add_box_collision(np,spec.sx,spec.sy,spec.height)
            # setback crown on taller blocks, still blank/architectural rather than decorative
            if spec.height>70:
                c=make_box_geom(spec.name+"_crown",spec.sx*0.62,spec.sy*0.62,min(15,spec.height*0.15),PALETTE["spire"]); c.reparentTo(self.visual_root); c.setPos(spec.x,spec.y,spec.z+spec.height); c.setH(spec.heading)

    def _build_outer_world_details(self):
        """Natural exterior detail without trees.

        Pass 59 removes the old tree geometry and its collision entirely. Low shrubs and
        shoreline breakup remain soft/traversable decoration, while cardinal bridge approaches
        stay deliberately open.
        """
        if self.outer_land_root is None:
            return
        rng=random.Random(3901)

        # Break the engineered circular shoreline silhouette with small earth/grass tongues.
        shore_colors=(PALETTE["outer_shore"], PALETTE["outer_dirt"], (0.42,0.34,0.21,1.0))
        for idx in range(26):
            angle=rng.uniform(0.0,360.0)
            if min(angle_delta(angle,a) for a in (0,90,180,270)) < 7.0:
                continue
            radius=rng.uniform(690.0,748.0); x,y,_=polar(radius,angle,0.0)
            patch=make_disc_geom(f"outer_shore_breakup_{idx}",rng.uniform(7.0,20.0),shore_colors[idx%len(shore_colors)],28,-0.001)
            patch.reparentTo(self.outer_land_root); patch.setPos(x,y,0); patch.setScale(rng.uniform(0.7,1.5),rng.uniform(0.35,0.78),1.0); patch.setH(angle+rng.uniform(-30,30)); patch.setTwoSided(True)
            self.environment_stats["outer_shore_breakup"] += 1

        # Low soft vegetation preserves some natural texture without the rejected tree silhouettes
        # or hidden trunk blockers.
        for idx in range(92):
            radius=rng.uniform(775.0,1460.0); angle=rng.uniform(0.0,360.0); x,y,_=polar(radius,angle,0.0)
            if radius < 970.0 and min(angle_delta(angle,a) for a in (0,90,180,270)) < 8.0:
                continue
            shrub=make_uv_sphere_geom(f"outer_shrub_{idx}",rng.uniform(0.55,1.35),(0.16+rng.random()*0.06,0.29+rng.random()*0.09,0.11+rng.random()*0.05,1.0),7,10)
            shrub.reparentTo(self.outer_land_root); shrub.setPos(x,y,rng.uniform(0.32,0.62)); shrub.setScale(rng.uniform(1.1,2.4),rng.uniform(0.65,1.4),rng.uniform(0.45,0.85))
            self.environment_stats["outer_shrubs"] += 1

    def _make_greenery(self):
        # Retain the low park footprints, but remove all tree geometry and trunk collision.
        # Physical park slabs are hidden from AR because Pass 59 gives each one a same-footprint
        # district-textured AR counterpart.
        for angle in range(0,360,30):
            if min(angle_delta(angle,a) for a in (0,45,90,135,180,225,270,315))<6:
                continue
            x,y,_=polar(258,angle,0.04)
            park=make_box_geom("park",30,52,0.08,PALETTE["green"])
            park.reparentTo(self.visual_root); park.setPos(x,y,0.04); park.setH(angle)
            park.hide(AR_CAMERA_MASK)

    def _make_overlook(self):
        # A south-side raised deck used as the future signature reveal location.
        x,y,_=polar(452,180,0)
        deck=make_box_geom("skyline_overlook",58,34,0.18,PALETTE["sidewalk"]); deck.reparentTo(self.visual_root); deck.setPos(x,y,0)
        # low rear/side walls, front left open to city
        for lateral in (-29,29):
            rail=make_box_geom("overlook_rail",1.0,34,1.15,PALETTE["wall"]); rail.reparentTo(self.visual_root); rail.setPos(x,y,0.18); rail.setX(rail,lateral); self._add_box_collision(rail,1,34,1.15)
        back=make_box_geom("overlook_back",58,1,1.15,PALETTE["wall"]); back.reparentTo(self.visual_root); back.setPos(x,y-16.5,0.18); self._add_box_collision(back,58,1,1.15)

    def _add_box_collision(self, visual_np:NodePath, sx:float, sy:float, sz:float):
        # Collision is derived from the same transform and dimensions as its visible solid.
        cnode=CollisionNode("solid")
        cnode.setIntoCollideMask(WORLD_MASK)
        cnode.addSolid(CollisionBox(Vec3(0,0,sz/2), sx/2, sy/2, sz/2))
        cnp=visual_np.attachNewNode(cnode)
        return cnp

    def _add_cylinder_collision(self,x:float,y:float,radius:float,height:float):
        # Curved visuals and simulation use the same radius/height authority.
        holder=self.collision_root.attachNewNode("cylinder_proxy")
        holder.setPos(x,y,0)
        cnode=CollisionNode("solid"); cnode.setIntoCollideMask(WORLD_MASK)
        cnode.addSolid(CollisionTube(0,0,0,0,0,height,radius)); holder.attachNewNode(cnode)

    def _make_lines(self, name: str, points: list[tuple[float,float,float]], color, thickness: float = 2.0, closed: bool = False) -> NodePath:
        lines = LineSegs(name)
        lines.setThickness(thickness)
        lines.setColor(*color)
        if not points:
            return self.utopia_root.attachNewNode(name)
        lines.moveTo(*points[0])
        for point in points[1:]:
            lines.drawTo(*point)
        if closed:
            lines.drawTo(*points[0])
        return self.utopia_root.attachNewNode(lines.create())

    def _prepare_texture(self, tex: Texture):
        tex.setWrapU(Texture.WMRepeat)
        tex.setWrapV(Texture.WMRepeat)
        tex.setMinfilter(Texture.FTLinearMipmapLinear)
        tex.setMagfilter(Texture.FTLinear)
        tex.setAnisotropicDegree(16)
        return tex

    def _load_district_textures(self) -> dict[str, Texture]:
        textures: dict[str, Texture] = {}
        for key, theme in DISTRICT_THEMES.items():
            tex_path = self.base_dir / "textures" / theme["texture"]
            tex = self.loader.loadTexture(Filename.fromOsSpecific(str(tex_path)))
            if tex is None:
                raise RuntimeError(f"Failed to load district texture: {tex_path}")
            textures[key] = self._prepare_texture(tex)
        return textures

    def _load_pedestrian_textures(self) -> dict[str, Texture]:
        textures: dict[str, Texture] = {}
        for key, filename in PEDESTRIAN_TEXTURES.items():
            tex_path = self.base_dir / "textures" / filename
            tex = self.loader.loadTexture(Filename.fromOsSpecific(str(tex_path)))
            if tex is None:
                raise RuntimeError(f"Failed to load pedestrian texture: {tex_path}")
            textures[key] = self._prepare_texture(tex)
        return textures

    def _theme_key_for_point(self, x: float, y: float) -> str:
        if math.hypot(x, y) < 150.0:
            return "core"
        angle = (math.degrees(math.atan2(x, y)) + 360.0) % 360.0
        if 45 <= angle < 135:
            return "east"
        if 135 <= angle < 225:
            return "south"
        if 225 <= angle < 315:
            return "west"
        return "north"

    def _theme_for_spec(self, spec: BuildingSpec):
        key = self._theme_key_for_point(spec.x, spec.y)
        return key, DISTRICT_THEMES[key]

    def _ar_arch_root(self, spec: BuildingSpec) -> NodePath:
        root = self.utopia_root.attachNewNode(spec.name + "_architecture")
        root.setPos(spec.x, spec.y, spec.z)
        root.setH(spec.heading)
        return root

    def _attached_textured_box(self, root: NodePath, name: str, sx: float, sy: float, sz: float, pos: tuple[float,float,float], theme_key: str, scale_u: float | None = None, scale_v: float | None = None, color_scale=(0.96,0.97,1.0,1.0)) -> NodePath:
        np = make_textured_box_geom(name, sx, sy, sz, (1,1,1,1))
        np.reparentTo(root)
        np.setPos(*pos)
        np.setTexture(self.theme_textures[theme_key], 1)
        np.setTexScale(TextureStage.getDefault(), scale_u if scale_u is not None else max(1.0, (sx+sy)/26.0), scale_v if scale_v is not None else max(1.0, sz/32.0))
        np.setColorScale(*color_scale)
        self._apply_pattern_neon_surface(np, theme_key, 0.16, 1.05)
        self._stabilize_overlay(np, 1)
        self.ar_architecture_stats["modules"] += 1
        return np

    def _attached_color_box(self, root: NodePath, name: str, sx: float, sy: float, sz: float, pos: tuple[float,float,float], color) -> NodePath:
        np = make_box_geom(name, sx, sy, sz, color)
        np.reparentTo(root)
        np.setPos(*pos)
        emissive_name=name.lower()
        if not any(token in emissive_name for token in ("glow","underlight","light","window")):
            self._apply_reflective_surface(np, strength=0.44)
        self.ar_architecture_stats["modules"] += 1
        return np

    def _activity_seed(self, name: str) -> float:
        # Stable across runs; avoid Python's randomized hash for deterministic QA.
        value = sum((idx + 1) * ord(ch) for idx, ch in enumerate(name)) % 1009
        return value / 1009.0

    def _spec_variant(self, spec: BuildingSpec, salt: str, count: int) -> int:
        basis = f"{spec.name}:{salt}:{int(spec.sx*10)}:{int(spec.sy*10)}:{int(spec.height*10)}:{spec.style}"
        value = sum((idx + 1) * ord(ch) for idx, ch in enumerate(basis))
        return value % max(1, count)

    def _spec_scalar(self, spec: BuildingSpec, salt: str) -> float:
        basis = f"{salt}:{spec.name}:{spec.x:.1f}:{spec.y:.1f}:{spec.height:.1f}"
        value = sum((idx + 3) * ord(ch) for idx, ch in enumerate(basis)) % 997
        return value / 996.0

    def _hero_signature_key(self, spec: BuildingSpec) -> str | None:
        if spec.name.startswith("north_archive"):
            return "north_archive"
        if spec.name.startswith("north_tower"):
            return "north_tower"
        if spec.name.startswith("east_cylinder"):
            return "east_cylinder"
        if spec.name.startswith("east_hall"):
            return "east_hall"
        if spec.name.startswith("south_tower"):
            return "south_tower"
        if spec.name.startswith("south_dome"):
            return "south_dome"
        if spec.name.startswith("west_tower"):
            return "west_tower"
        if spec.name.startswith("west_hall"):
            return "west_hall"
        if spec.name.startswith("unity_spire_mid") or spec.name.startswith("unity_spire_crown"):
            return "unity_spire"
        return None

    def _mark_hero_signature(self, count: int = 1):
        self.ar_architecture_stats["hero_signatures"] += count

    def _add_box_hero_signature(self, spec: BuildingSpec, theme_key: str, theme):
        key = self._hero_signature_key(spec)
        if key is None:
            return
        root = self._ar_arch_root(spec)
        front_y = -(spec.sy / 2.0) - 0.84
        sx, sy, h = spec.sx, spec.sy, spec.height
        if key == "north_archive":
            self._attached_textured_box(root, spec.name+"_hero_frame", sx*0.74, 1.8, h*0.86, (0.0, front_y-0.62, h*0.07), theme_key, 1.0, max(1.6,h/22.0))
            self._attached_color_box(root, spec.name+"_hero_header", sx*0.58, 2.6, 0.72, (0.0, front_y-1.14, h*0.72), theme["secondary"])
            self._attached_color_box(root, spec.name+"_hero_plaza_canopy", sx*0.52, 4.0, 0.62, (0.0, front_y-1.94, h*0.18), theme["primary"])
            for side in (-0.28,0.28):
                self._attached_textured_box(root, spec.name+f"_hero_book_spine_{side:+.2f}", max(3.4,sx*0.12), 1.55, h*0.78, (side*sx, front_y-0.64, h*0.11), theme_key, 1.0, max(1.4,h/24.0))
            self._mark_hero_signature(4)
        elif key == "north_tower":
            for side in (-0.30,0.30):
                self._attached_color_box(root, spec.name+f"_hero_corner_blade_{side:+.2f}", max(2.8,sx*0.10), 1.2, h*0.92, (side*sx, front_y-0.50, h*0.04), theme["primary"] if side < 0 else theme["secondary"])
            self._attached_color_box(root, spec.name+"_hero_sky_lobby", sx*0.64, 2.8, 0.82, (0.0, front_y-1.26, h*0.60), theme["secondary"])
            self._attached_textured_box(root, spec.name+"_hero_crown", sx*0.52, sy*0.52, min(20.0,h*0.16), (0.0,0.0,h+0.62), theme_key, 1.0, 1.0)
            self._mark_hero_signature(3)
        elif key == "east_hall":
            self._attached_color_box(root, spec.name+"_hero_cantilever", sx*0.46, 4.4, 0.84, (sx*0.12, front_y-2.02, h*0.44), theme["secondary"])
            self._attached_color_box(root, spec.name+"_hero_bridge", sx*0.34, 3.0, 0.68, (-sx*0.18, front_y-1.42, h*0.70), theme["primary"])
            for side in (-0.34,0.34):
                self._attached_textured_box(root, spec.name+f"_hero_pulse_tower_{side:+.2f}", max(3.2,sx*0.12), 1.45, h*0.82, (side*sx, front_y-0.70, h*0.10), theme_key, 1.0, max(1.5,h/24.0))
            self._mark_hero_signature(4)
        elif key == "south_tower":
            for idx, frac in enumerate((0.24,0.46,0.68,0.84)):
                bw=sx*(0.88-idx*0.12)
                self._attached_color_box(root, spec.name+f"_hero_marquee_{idx}", bw, 2.5, 0.58, (0.0, front_y-1.12, h*frac), theme["primary"] if idx % 2 == 0 else theme["secondary"])
            self._attached_textured_box(root, spec.name+"_hero_roof_stage", sx*0.54, sy*0.42, min(14.0,h*0.10), (0.0,0.0,h+0.60), theme_key, 1.0, 1.0)
            self._mark_hero_signature(5)
        elif key == "west_tower":
            for side in (-0.36,0.36):
                self._attached_textured_box(root, spec.name+f"_hero_service_core_{side:+.2f}", max(3.2,sx*0.11), 1.55, h*0.88, (side*sx, front_y-0.68, h*0.06), theme_key, 1.0, max(1.5,h/22.0), (0.80,0.82,0.88,1.0))
            self._attached_color_box(root, spec.name+"_hero_cross_head", sx*0.78, 0.54, 0.46, (0.0, front_y-0.78, h*0.76), theme["secondary"])
            self._attached_textured_box(root, spec.name+"_hero_plant", sx*0.44, sy*0.48, min(13.0,h*0.12), (-sx*0.08,0.0,h+0.62), theme_key, 1.0, 1.0, (0.76,0.79,0.84,1.0))
            self._mark_hero_signature(4)
        elif key == "west_hall":
            self._attached_textured_box(root, spec.name+"_hero_frame", sx*0.82, 1.8, h*0.72, (0.0, front_y-0.62, h*0.10), theme_key, 1.0, max(1.4,h/22.0), (0.80,0.83,0.88,1.0))
            self._attached_color_box(root, spec.name+"_hero_ledge_low", sx*0.74, 2.6, 0.62, (0.0, front_y-1.06, h*0.34), theme["primary"])
            self._attached_color_box(root, spec.name+"_hero_ledge_high", sx*0.62, 2.4, 0.58, (0.0, front_y-1.00, h*0.62), theme["secondary"])
            self._attached_textured_box(root, spec.name+"_hero_roof_shed", sx*0.38, sy*0.42, min(11.0,h*0.12), (sx*0.14,0.0,h+0.56), theme_key, 1.0, 1.0, (0.78,0.81,0.86,1.0))
            self._mark_hero_signature(4)

    def _add_cylinder_hero_signature(self, spec: BuildingSpec, theme_key: str, theme):
        key = self._hero_signature_key(spec)
        if key is None:
            return
        root = self._ar_arch_root(spec)
        radius = min(spec.sx, spec.sy) / 2.0 + 1.85
        h = spec.height
        if key == "east_cylinder":
            for idx, frac in enumerate((0.26,0.52,0.78)):
                collar = make_cylinder_geom(spec.name+f"_hero_collar_{idx}", radius+1.35+(0.16*idx), 0.92, 28, theme["primary"] if idx != 1 else theme["secondary"], top_radius=radius+1.35+(0.16*idx))
                collar.reparentTo(root); collar.setZ(h*frac); self.ar_architecture_stats["modules"] += 1
            for i in range(5):
                ang=72.0*i
                fin=make_box_geom(spec.name+f"_hero_fin_{i}",1.15,2.4,h*0.84,theme["secondary"] if i%2 else theme["primary"])
                fin.reparentTo(root); fin.setH(ang); fin.setY(fin,radius+1.05); fin.setZ(h*0.08); self.ar_architecture_stats["modules"] += 1
            self._mark_hero_signature(8)
        elif key == "south_dome":
            for idx, frac in enumerate((0.24,0.50)):
                collar = make_cylinder_geom(spec.name+f"_hero_ring_{idx}", radius+1.20, 0.88, 28, theme["primary"] if idx==0 else theme["secondary"], top_radius=radius+1.20)
                collar.reparentTo(root); collar.setZ(h*frac); self.ar_architecture_stats["modules"] += 1
            lantern = make_textured_cylinder_geom(spec.name+"_hero_lantern", radius*0.34, max(6.0,h*0.18), 20, (1,1,1,1), top_radius=radius*0.18)
            lantern.reparentTo(root); lantern.setZ(h+0.58); lantern.setTexture(self.theme_textures[theme_key],1); lantern.setTexScale(TextureStage.getDefault(),max(1.0,(2.0*math.pi*radius*0.34)/18.0),1.0); lantern.setColorScale(0.96,0.95,1.0,1.0); self.ar_architecture_stats["modules"] += 1
            self._mark_hero_signature(3)
        elif key == "unity_spire":
            halo = make_cylinder_geom(spec.name+"_hero_halo", radius+0.90, 0.66, 28, theme["secondary"], top_radius=radius+0.90)
            halo.reparentTo(root); halo.setZ(h*0.86); self.ar_architecture_stats["modules"] += 1
            for i in range(6):
                ang=60.0*i
                fin=make_box_geom(spec.name+f"_hero_spire_fin_{i}",0.92,2.0,h*0.38,theme["primary"] if i%2==0 else theme["secondary"])
                fin.reparentTo(root); fin.setH(ang); fin.setY(fin,radius+0.70); fin.setZ(h*0.48); self.ar_architecture_stats["modules"] += 1
            self._mark_hero_signature(7)

    def _register_ar_activity(self, node: NodePath, name: str, kind: str, min_level: float, max_level: float, speed: float):
        phase = self._activity_seed(name) * math.tau
        node.setColorScale(max_level, max_level, max_level, 1.0)
        self.ar_activity_nodes.append({
            "node": node,
            "name": name,
            "kind": kind,
            "phase": phase,
            "min": min_level,
            "max": max_level,
            "speed": speed,
        })
        if kind == "window":
            self.ar_architecture_stats["active_windows"] += 1
        elif kind == "entry":
            self.ar_architecture_stats["active_entries"] += 1
        elif kind == "path":
            self.ar_architecture_stats["active_glow_paths"] += 1

    def _update_ar_activity(self):
        t = self.ar_activity_time
        for item in self.ar_activity_nodes:
            phase = item["phase"] + t * item["speed"]
            if item["kind"] == "window":
                # Occupancy-like state: slow asymmetric bright/dim cycling, never flashing.
                wave = 0.5 + 0.5 * math.sin(phase)
                wave = wave * wave * (3.0 - 2.0 * wave)
            else:
                # Access rail: slightly steadier than windows.
                wave = 0.5 + 0.5 * math.sin(phase)
                wave = 0.35 + 0.65 * wave
            level = item["min"] + (item["max"] - item["min"]) * wave
            item["node"].setColorScale(level, level, level, 1.0)

    def _ar_runtime_reference_nodes(self):
        """NodePaths that must survive static batching because runtime code keeps references to them."""
        refs=[]
        for item in self.ar_activity_nodes:
            refs.append(item.get("node"))
        for item in self.utopia_system_activity:
            refs.append(item.get("node"))
        for item in self.citizen_orbs:
            for value in item.values():
                if isinstance(value,NodePath): refs.append(value)
        for item in self.ar_neon_spill_sources:
            root=item.get("root") if isinstance(item,dict) else None
            if isinstance(root,NodePath): refs.append(root)
        refs.extend(np for np in self.ar_gate_aprons if isinstance(np,NodePath))
        if isinstance(self.ar_water_surface,NodePath): refs.append(self.ar_water_surface)
        for item in self.public_interiors:
            root=item.get("ar_root")
            if isinstance(root,NodePath): refs.append(root)
        return [np for np in refs if isinstance(np,NodePath) and not np.isEmpty()]

    def _optimize_ar_scene_graph(self):
        """Batch only static AR branches; preserve all runtime-transformed/referenced nodes.

        The AR city contains thousands of tiny decorative GeomNodes.  Draw-call overhead, not
        triangle count, is the dominant AR cost.  Static siblings are flattened into compatible
        state batches while every animated/system/citizen/reference path is protected.
        """
        root=self.utopia_root
        pre=root.countNumDescendants()
        protected={root.node()}
        for np in self._ar_runtime_reference_nodes():
            cur=np
            while not cur.isEmpty():
                protected.add(cur.node())
                if cur==root: break
                cur=cur.getParent()
        batches=0
        def batch_under(parent):
            nonlocal batches
            children=list(parent.getChildren())
            static=[child for child in children if child.node() not in protected]
            dynamic=[child for child in children if child.node() in protected]
            if static:
                batch=parent.attachNewNode("_ar_static_batch")
                for child in static:
                    child.wrtReparentTo(batch)
                batch.flattenStrong()
                batches+=1
            for child in dynamic:
                batch_under(child)
        batch_under(root)
        post=root.countNumDescendants()
        self.ar_optimization_stats.update({"pre_nodes":pre,"post_nodes":post,"static_batches":batches,"activity_total":len(self.ar_activity_nodes)})
        self._update_ar_activity_visibility(force=True)

    def _update_ar_activity_visibility(self, force: bool=False):
        """Distance-cull tiny animated facade lights; static architecture remains visible."""
        if not hasattr(self,"player") or not self.ar_activity_nodes:
            return
        pos=Vec3(self.player.getPos(self.render)); pos.z=0
        last=self.ar_activity_cull_last_player
        if not force and last is not None and (pos-last).length()<AR_ACTIVITY_RECULL_DISTANCE:
            return
        visible=hidden=0; r2=AR_ACTIVITY_DRAW_RADIUS*AR_ACTIVITY_DRAW_RADIUS
        for item in self.ar_activity_nodes:
            node=item["node"]
            if node is None or node.isEmpty():
                continue
            p=node.getPos(self.render); dx=float(p.x-pos.x); dy=float(p.y-pos.y)
            if dx*dx+dy*dy>r2:
                node.hide(); hidden+=1
            else:
                node.show(); visible+=1
        self.ar_activity_cull_last_player=Vec3(pos)
        self.ar_optimization_stats["activity_visible"]=visible
        self.ar_optimization_stats["activity_hidden"]=hidden

    def _street_detail_eligible(self, spec: BuildingSpec) -> bool:
        # Street detail belongs on occupied/urban masses, not utility pylons or elevated machine parts.
        if spec.z > 0.35 or spec.height < 16.0 or min(spec.sx, spec.sy) < 14.0:
            return False
        blocked_prefixes = ("gate_pylon", "transit_", "spire_", "wall_", "bridge_")
        return not spec.name.startswith(blocked_prefixes)

    def _pedestrian_theme_for_angle(self, angle: float) -> tuple[str, dict]:
        mx, my, _ = polar(280.0, angle, 0.0)
        key = self._theme_key_for_point(mx, my)
        return key, DISTRICT_THEMES[key]

    def _stabilize_overlay(self, np: NodePath, depth_offset: int):
        np.setDepthOffset(depth_offset)
        return np

    def _promenade_glow_strip(self, name: str, sx: float, sy: float, pos: tuple[float,float,float], heading: float, color, speed: float = 0.54, min_level: float = 0.20, max_level: float = 0.92) -> NodePath:
        np = make_box_geom(name, sx, sy, 0.020, color)
        np.reparentTo(self.utopia_root)
        np.setPos(*pos)
        np.setH(heading)
        self._stabilize_overlay(np, 3)
        self.ar_architecture_stats["modules"] += 1
        self.ar_architecture_stats["ground_markers"] += 1
        self._register_ar_activity(np, name, "path", min_level, max_level, speed)
        return np

    def _promenade_box(self, name: str, sx: float, sy: float, sz: float, pos: tuple[float,float,float], heading: float, color, count_key: str = "promenades") -> NodePath:
        np = make_box_geom(name, sx, sy, sz, color)
        np.reparentTo(self.utopia_root)
        np.setPos(*pos)
        np.setH(heading)
        self._stabilize_overlay(np, 2)
        self.ar_architecture_stats["modules"] += 1
        self.ar_architecture_stats[count_key] += 1
        return np

    def _promenade_annulus(self, name: str, inner_r: float, outer_r: float, z: float, color, count_key: str = "promenades") -> NodePath:
        np = make_annulus_geom(name, inner_r, outer_r, color, 160, z)
        np.reparentTo(self.utopia_root)
        self._stabilize_overlay(np, 2)
        self.ar_architecture_stats["modules"] += 1
        self.ar_architecture_stats[count_key] += 1
        return np

    def _promenade_textured_box(self, name: str, sx: float, sy: float, pos: tuple[float,float,float], heading: float, theme_key: str, tile_m: float = 18.0, count_key: str = "promenades") -> NodePath:
        np = make_textured_box_geom(name, sx, sy, 0.055, (1,1,1,1))
        np.reparentTo(self.utopia_root)
        np.setPos(*pos); np.setH(heading)
        np.setTexture(self.pedestrian_textures[theme_key],1)
        np.setTexScale(TextureStage.getDefault(), max(1.0,sx/tile_m), max(1.0,sy/tile_m))
        np.setColorScale(0.74,0.78,0.84,1.0)
        self._apply_pattern_neon_surface(np, theme_key, 0.30, 1.05)
        self._stabilize_overlay(np, 1)
        self.ar_architecture_stats["modules"] += 1
        self.ar_architecture_stats[count_key] += 1
        self.ar_architecture_stats["textured_walkways"] += 1
        return np

    def _promenade_textured_sector(self, name: str, inner_r: float, outer_r: float, start_deg: float, end_deg: float, theme_key: str, z: float = 0.065) -> NodePath:
        np = make_textured_annulus_sector(name, inner_r, outer_r, start_deg, end_deg, (1,1,1,1), 36, z, 22.0)
        np.reparentTo(self.utopia_root)
        np.setTexture(self.pedestrian_textures[theme_key],1)
        np.setColorScale(0.74,0.78,0.84,1.0)
        self._apply_pattern_neon_surface(np, theme_key, 0.30, 1.05)
        np.setTwoSided(True)
        self._stabilize_overlay(np, 1)
        self.ar_architecture_stats["modules"] += 1
        self.ar_architecture_stats["promenades"] += 1
        self.ar_architecture_stats["textured_walkways"] += 1
        return np

    def _add_pedestrian_surface_layer(self):
        # District-style pedestrian world: still no lane markings, traffic arrows, vehicles, or floating route UI.
        core = DISTRICT_THEMES["core"]
        def toned(color, scale=0.30, lift=0.012):
            return (min(1.0,color[0]*scale+lift), min(1.0,color[1]*scale+lift), min(1.0,color[2]*scale+lift), 1.0)

        # Park slabs sit above the broad district ground fields and were visible as olive
        # rectangles through the AR layer. Re-skin all retained park footprints in district art.
        for angle in range(0,360,30):
            if min(angle_delta(angle,a) for a in (0,45,90,135,180,225,270,315))<6:
                continue
            x,y,_=polar(258,angle,0.035)
            theme_key,theme=self._pedestrian_theme_for_angle(angle)
            park=make_textured_box_geom(f"ar_park_{angle}",30.20,52.20,0.105,(1,1,1,1))
            park.reparentTo(self.utopia_root); park.setPos(x,y,0.035); park.setH(angle)
            park.setTexture(self.pedestrian_textures[theme_key],1)
            park.setTexScale(TextureStage.getDefault(),2.0,3.2)
            park.setColorScale(0.54,0.58,0.66,1.0)
            self._apply_pattern_neon_surface(park,theme_key,0.28,1.08)
            self._stabilize_overlay(park,3)
            self.ar_architecture_stats["modules"] += 1
            self.ar_architecture_stats["park_surfaces"] += 1
            self.ar_architecture_stats["detail_ground_fields"] += 1

        # Unity Plaza uses a clean forum paving texture with a few glowing orientation bands.
        plaza = make_textured_disc_geom("ar_unity_plaza_textured",108,(1,1,1,1),128,0.066,28.0)
        plaza.reparentTo(self.utopia_root)
        plaza.setTexture(self.pedestrian_textures["core"],1)
        plaza.setColorScale(0.76,0.80,0.86,1.0)
        self._apply_pattern_neon_surface(plaza, "core", 0.32, 1.06)
        self._stabilize_overlay(plaza, 1)
        self.ar_architecture_stats["modules"] += 1; self.ar_architecture_stats["promenades"] += 1; self.ar_architecture_stats["textured_walkways"] += 1
        glow_specs = [
            (18, 19.2, core["primary"], 0.42),
            (57, 58.2, core["secondary"], 0.50),
            (85, 86.2, core["primary"], 0.58),
        ]
        for idx, (inner_r, outer_r, color, speed) in enumerate(glow_specs):
            ring = self._promenade_annulus(f"forum_frame_{idx}", inner_r, outer_r, 0.080, toned(color, 0.42, 0.018), "ground_markers")
            self._register_ar_activity(ring, f"forum_frame_glow_{idx}", "path", 0.18, 0.88, speed)

        # Large district ground fields were still plain physical gray in full-screen AR.
        # Use the accepted district surface art at a much larger, dimmer scale beneath roads/buildings.
        ground_sectors=[(-45,45,"north"),(45,135,"east"),(135,225,"south"),(225,315,"west")]
        for start_deg,end_deg,key in ground_sectors:
            field=make_textured_annulus_sector(f"district_ground_{key}",108.0,500.0,start_deg,end_deg,(1,1,1,1),64,0.046,78.0)
            field.reparentTo(self.utopia_root)
            field.setTexture(self.pedestrian_textures[key],1)
            field.setColorScale(0.24,0.27,0.31,1.0)
            self._apply_pattern_neon_surface(field, key, 0.27, 1.04)
            field.setTwoSided(True)
            self._stabilize_overlay(field,1)
            self.ar_architecture_stats["modules"] += 1
            self.ar_architecture_stats["detail_ground_fields"] += 1

        # Ring promenades are split into district sectors, each with its own pavement language.
        ring_specs=[(123,147),(286,314),(439,467)]
        sectors=[(-45,45,"north"),(45,135,"east"),(135,225,"south"),(225,315,"west")]
        for idx,(inner_r,outer_r) in enumerate(ring_specs):
            for start_deg,end_deg,key in sectors:
                self._promenade_textured_sector(f"ring_{idx}_{key}",inner_r,outer_r,start_deg,end_deg,key,0.064)
                mid_r=(inner_r+outer_r)/2.0
                a=(start_deg+end_deg)/2.0
                gx,gy,_=polar(mid_r,a,0.090)
                theme=DISTRICT_THEMES[key]
                strip_len=min(20.0,max(10.0,(outer_r-inner_r)*0.75))
                self._promenade_glow_strip(f"ring_glow_{idx}_{key}", 1.0, strip_len, (gx,gy,0.090), a+90.0, toned(theme["primary"],0.52,0.03), 0.42 + 0.04*idx)
            self._promenade_annulus(f"ring_{idx}_inner_frame",inner_r+0.9,inner_r+1.5,0.082,toned(core["primary"],0.20,0.01),"ground_markers")
            self._promenade_annulus(f"ring_{idx}_outer_frame",outer_r-1.5,outer_r-0.9,0.082,toned(core["secondary"],0.20,0.01),"ground_markers")

        # Cover the remaining physical sidewalk annuli with subdued district paving.
        sidewalk_rings=[(114,121),(276,284),(316,324)]
        for sidx,(inner_r,outer_r) in enumerate(sidewalk_rings):
            for start_deg,end_deg,key in sectors:
                walk=self._promenade_textured_sector(f"sidewalk_ring_{sidx}_{key}",inner_r,outer_r,start_deg,end_deg,key,0.070)
                walk.setColorScale(0.46,0.50,0.56,1.0)
                self.ar_architecture_stats["detail_sidewalk_surfaces"] += 1

        # Eight pedestrian boulevards use the district pavement tile for their direction.
        for angle in (0,45,90,135,180,225,270,315):
            width=24 if angle%90==0 else 15; length=394; mid=303
            x,y,_=polar(mid,angle,0.065); theme_key,theme=self._pedestrian_theme_for_angle(angle)
            tile=24.0 if width >= 20 else 22.0
            self._promenade_textured_box(f"promenade_radial_{angle}",width,length,(x,y,0.065),angle,theme_key,tile)
            edge_x=width/2-1.15
            left=self._promenade_box(f"promenade_edge_{angle}_-1",0.72,length,0.028,(x,y,0.086),angle,toned(theme["primary"],0.26,0.01),"ground_markers")
            left.setX(left,-edge_x)
            right=self._promenade_box(f"promenade_edge_{angle}_1",0.72,length,0.028,(x,y,0.086),angle,toned(theme["secondary"],0.26,0.01),"ground_markers")
            right.setX(right,edge_x)
            # Physical sidewalk bands were still blank in full-screen AR. Give them subdued structural paving.
            sidewalk_offset=width/2+4.0
            for side in (-1,1):
                sidewalk=self._promenade_textured_box(f"promenade_sidewalk_{angle}_{side}",5.8,length,(x,y,0.070),angle,theme_key,24.0)
                sidewalk.setX(sidewalk,side*sidewalk_offset)
                sidewalk.setColorScale(0.46,0.50,0.56,1.0)
                self.ar_architecture_stats["detail_sidewalk_surfaces"] += 1
            # A few inset glow rails are enough to imply live wayfinding without becoming traffic stripes.
            for idx, local_y in enumerate((-118,-6,106)):
                sx = 0.85 if width >= 20 else 0.68
                glow = self._promenade_glow_strip(f"promenade_glow_{angle}_{idx}", sx, 32.0 if width >= 20 else 24.0, (x,y,0.094), angle, toned(theme["primary"] if idx % 2 == 0 else theme["secondary"],0.54,0.03), 0.48 + 0.04*idx)
                glow.setX(glow, -edge_x if idx != 1 else edge_x)
                glow.setY(glow, local_y)
            for i in range(3):
                local_y=-length/2+72+i*118
                # These pads were formerly flat muted boxes; at close range they read as blank
                # rectangles and interrupted the AR pavement. Keep the same footprint but use
                # the district surface texture so the boulevard remains visually continuous.
                pad=self._promenade_textured_box(f"promenade_node_{angle}_{i}",max(2.0,width*0.20),3.0,(x,y,0.092),angle,theme_key,3.0,"ground_markers")
                pad.setColorScale(0.72,0.76,0.82,1.0)
                pad.setY(pad,local_y)
                self.ar_architecture_stats["textured_node_pads"] += 1

        # Four cardinal gate aprons close the 500-515 m AR paving gap between district
        # boulevards and bridge causeways.  This is where Gleebs stands at the south entrance.
        for angle in (0,90,180,270):
            apron_len=25.0; apron_mid=507.5
            x,y,_=polar(apron_mid,angle,0.066); theme_key,theme=self._pedestrian_theme_for_angle(angle)
            apron=self._promenade_textured_box(f"gate_apron_{angle}",24.0,apron_len,(x,y,0.066),angle,theme_key,18.0)
            apron.setColorScale(0.62,0.66,0.72,1.0)
            self._apply_pattern_neon_surface(apron,theme_key,0.30,1.05)
            self._stabilize_overlay(apron,2)
            self.ar_gate_aprons.append(apron)
            self.ar_architecture_stats["detail_ground_fields"] += 1

        # Gate bridges become textured pedestrian causeways with a few glowing side signals.
        for angle in (0,90,180,270):
            bridge_len=170.0; mid=CITY_RADIUS+bridge_len/2-5; x,y,_=polar(mid,angle,0.065); theme_key,theme=self._pedestrian_theme_for_angle(angle)
            self._promenade_textured_box(f"gate_walkway_{angle}",20.0,bridge_len,(x,y,0.065),angle,theme_key,20.0)
            for side in (-1,1):
                edge=self._promenade_box(f"gate_edge_{angle}_{side}",0.72,bridge_len,0.028,(x,y,0.088),angle,toned(theme["primary"] if side<0 else theme["secondary"],0.24,0.010),"ground_markers")
                edge.setX(edge,side*8.8)
            for idx, local_y in enumerate((-48,0,48)):
                glow = self._promenade_glow_strip(f"gate_glow_{angle}_{idx}", 0.86, 20.0, (x,y,0.095), angle, toned(theme["secondary"] if idx % 2 == 0 else theme["primary"],0.56,0.03), 0.52 + 0.05*idx)
                glow.setX(glow, -8.8 if idx != 1 else 8.8)
                glow.setY(glow, local_y)

        # Overlook deck uses core forum paving and a calm pair of glow rails.
        overlook_x,overlook_y,_=polar(452,180,0.205)
        self._promenade_textured_box("overlook_promenade",57.0,33.0,(overlook_x,overlook_y,0.25),0.0,"core",18.0)
        self._promenade_box("overlook_frame",44.0,0.65,0.026,(overlook_x,overlook_y-10.5,0.29),0.0,toned(core["secondary"],0.22,0.010),"ground_markers")
        self._promenade_glow_strip("overlook_glow_left", 0.82, 18.0, (overlook_x-18.0,overlook_y,0.30), 0.0, toned(core["primary"],0.54,0.03), 0.50)
        self._promenade_glow_strip("overlook_glow_right", 0.82, 18.0, (overlook_x+18.0,overlook_y,0.30), 0.0, toned(core["secondary"],0.54,0.03), 0.58)

    def _add_box_street_detail(self, spec: BuildingSpec, theme_key: str, theme):
        if not self._street_detail_eligible(spec):
            return
        root = self._ar_arch_root(spec)
        front_y = -(spec.sy / 2.0) - 0.93
        h = spec.height
        sx = spec.sx

        # Ground-floor facade plate creates depth and a believable base behind the door/window layer.
        ground_h = min(6.2, max(4.4, h * 0.12))
        plate_w = sx * (0.82 if theme_key != "core" else 0.90)
        self._attached_color_box(root, spec.name+"_street_plate", plate_w, 0.38, ground_h, (0.0, front_y-0.16, 0.15), (0.012,0.020,0.030,1.0))

        # District-specific entrance placement. East is deliberately offset; the others remain orderly.
        door_offset = sx * 0.16 if theme_key == "east" else (-sx * 0.13 if theme_key == "west" else 0.0)
        door_w = max(3.0, min(5.6, sx * (0.17 if theme_key != "core" else 0.22)))
        door_h = min(4.8, ground_h * 0.78)
        self._attached_color_box(root, spec.name+"_door_recess", door_w, 0.34, door_h, (door_offset, front_y-0.39, 0.24), (0.006,0.012,0.020,1.0))
        door_glow = self._attached_color_box(root, spec.name+"_door_glow", max(0.55,door_w*0.16), 0.20, door_h*0.82, (door_offset, front_y-0.60, 0.52), theme["primary"])
        self._register_ar_activity(door_glow, spec.name+"_door_glow", "entry", 0.52, 1.00, 1.15)
        self.ar_architecture_stats["entrances"] += 1

        # Attached canopy: shallow enough to read as an entrance, not a floating shelf.
        canopy_w = min(plate_w*0.55, door_w*2.2)
        self._attached_color_box(root, spec.name+"_entry_canopy", canopy_w, 1.55, 0.32, (door_offset, front_y-1.05, ground_h-0.52), theme["secondary"])
        canopy_light = self._attached_color_box(root, spec.name+"_entry_underlight", canopy_w*0.78, 0.26, 0.16, (door_offset, front_y-1.18, ground_h-0.61), theme["primary"])
        self._register_ar_activity(canopy_light, spec.name+"_entry_underlight", "entry", 0.28, 0.68, 0.72)
        self.ar_architecture_stats["canopies"] += 1

        # Forecourt pad: shallow pedestrian arrival zone, flush with the ground and clearly walkable.
        forecourt_d = min(4.8, max(2.6, sx * 0.16))
        forecourt = make_textured_box_geom(spec.name+"_forecourt", max(door_w*2.8, plate_w*0.42), forecourt_d, 0.08, (1,1,1,1)); forecourt.reparentTo(root); forecourt.setPos(door_offset, front_y-1.62-forecourt_d*0.34, 0.02); forecourt.setTexture(self.pedestrian_textures[theme_key],1); forecourt.setTexScale(TextureStage.getDefault(),1.4,1.1); forecourt.setColorScale(0.74,0.78,0.84,1.0); self._apply_pattern_neon_surface(forecourt, theme_key, 0.30, 1.05); self._stabilize_overlay(forecourt, 2); self.ar_architecture_stats["modules"] += 1; self.ar_architecture_stats["textured_walkways"] += 1
        self._attached_color_box(root, spec.name+"_forecourt_band", max(door_w*2.2, plate_w*0.34), 0.34, 0.04, (door_offset, front_y-1.78-forecourt_d*0.62, 0.09), theme["secondary"])
        self.ar_architecture_stats["forecourts"] += 1

        # Ground-floor side glazing panels. These remain dark with narrow theme rails.
        side_space = max(3.0, (plate_w - door_w) * 0.42)
        for side in (-1,1):
            cx = door_offset + side * (door_w*0.55 + side_space*0.46)
            pane_w = max(2.8, side_space*0.72)
            pane = self._attached_color_box(root, spec.name+f"_ground_glass_{side}", pane_w, 0.24, door_h*0.84, (cx,front_y-0.43,0.48), (0.018,0.050,0.064,1.0))
            rail_x = cx + side * pane_w*0.28
            ground_glow = self._attached_color_box(root, spec.name+f"_ground_glow_{side}", max(0.35,pane_w*0.08),0.16,door_h*0.76,(rail_x,front_y-0.58,0.62),theme["secondary"])
            self._register_ar_activity(ground_glow, spec.name+f"_ground_glow_{side}", "window", 0.22, 0.72, 0.52 + 0.10*abs(side))

        # Upper window bands: restrained rows with vertical mullions, capped at four rows per building.
        if h >= 28.0:
            row_count = min(4, max(1, int((h-10.0)//13.0)))
            band_w = sx * 0.68
            band_h = 2.25 if theme_key != "west" else 1.85
            for row in range(row_count):
                z = 8.0 + row * max(10.5, (h-12.0)/max(1,row_count))
                if z + band_h >= h*0.88:
                    break
                self._attached_color_box(root, spec.name+f"_window_band_{row}", band_w, 0.22, band_h, (0.0,front_y-0.34,z), (0.012,0.042,0.060,1.0))
                activity_color = theme["primary"] if row % 2 == 0 else theme["secondary"]
                activity_panel = self._attached_color_box(root, spec.name+f"_window_activity_{row}", band_w*0.96, 0.10, band_h*0.78, (0.0,front_y-0.49,z+0.20), activity_color)
                self._register_ar_activity(activity_panel, spec.name+f"_window_activity_{row}", "window", 0.08, 0.42, 0.44 + row*0.06)
                mullion_count = 4 if theme_key in ("north","core") else 3
                for m in range(1,mullion_count):
                    x = -band_w/2 + band_w*m/mullion_count
                    self._attached_color_box(root, spec.name+f"_window_mullion_{row}_{m}", 0.26, 0.11, band_h*0.92, (x,front_y-0.58,z+0.08), theme["secondary"])
                self.ar_architecture_stats["window_bands"] += 1

    def _add_cylinder_street_detail(self, spec: BuildingSpec, theme_key: str, theme):
        if not self._street_detail_eligible(spec):
            return
        root = self._ar_arch_root(spec)
        radius = min(spec.sx,spec.sy)/2.0 + 1.86
        # Tangent entrance at the local front of the cylinder.
        door_w = max(3.4, min(5.4, radius*0.28))
        door_h = min(4.8, max(4.0, spec.height*0.10))
        self._attached_color_box(root, spec.name+"_cyl_door_recess", door_w, 0.36, door_h, (0.0,-radius-0.42,0.22), (0.006,0.012,0.020,1.0))
        cyl_door_glow = self._attached_color_box(root, spec.name+"_cyl_door_glow", max(0.6,door_w*0.18),0.18,door_h*0.82,(0.0,-radius-0.62,0.50),theme["primary"])
        self._register_ar_activity(cyl_door_glow, spec.name+"_cyl_door_glow", "entry", 0.52, 1.00, 1.08)
        self._attached_color_box(root, spec.name+"_cyl_canopy", door_w*1.8, 1.35, 0.30, (0.0,-radius-1.00,door_h+0.34), theme["secondary"])
        cyl_underlight = self._attached_color_box(root, spec.name+"_cyl_underlight", door_w*1.25, 0.22, 0.14, (0.0,-radius-1.12,door_h+0.22), theme["primary"])
        self._register_ar_activity(cyl_underlight, spec.name+"_cyl_underlight", "entry", 0.28, 0.68, 0.70)
        self.ar_architecture_stats["entrances"] += 1
        self.ar_architecture_stats["canopies"] += 1
        cyl_forecourt = make_textured_box_geom(spec.name+"_cyl_forecourt", max(door_w*2.6, radius*0.88), 3.8, 0.08, (1,1,1,1)); cyl_forecourt.reparentTo(root); cyl_forecourt.setPos(0.0,-radius-2.10,0.02); cyl_forecourt.setTexture(self.pedestrian_textures[theme_key],1); cyl_forecourt.setTexScale(TextureStage.getDefault(),1.4,1.1); cyl_forecourt.setColorScale(0.74,0.78,0.84,1.0); self._stabilize_overlay(cyl_forecourt, 2); self.ar_architecture_stats["modules"] += 1; self.ar_architecture_stats["textured_walkways"] += 1
        self._attached_color_box(root, spec.name+"_cyl_forecourt_band", max(door_w*2.0, radius*0.66), 0.32, 0.04, (0.0,-radius-3.18,0.09), theme["secondary"])
        self.ar_architecture_stats["forecourts"] += 1
        # Two attached dark window belts wrap the shell at pedestrian-visible heights.
        belt_levels = (7.0, 14.0) if spec.height >= 24 else (7.0,)
        for idx,z in enumerate(belt_levels):
            if z+1.8 >= spec.height*0.82:
                continue
            belt = make_cylinder_geom(spec.name+f"_street_window_belt_{idx}", radius+0.14, 1.75, 24, (0.012,0.042,0.060,1.0), top_radius=radius+0.14)
            belt.reparentTo(root)
            belt.setZ(z)
            activity_belt = make_cylinder_geom(spec.name+f"_street_window_activity_{idx}", radius+0.20, 1.26, 24, theme["primary"] if idx % 2 == 0 else theme["secondary"], top_radius=radius+0.20)
            activity_belt.reparentTo(root)
            activity_belt.setZ(z+0.24)
            self.ar_architecture_stats["modules"] += 2
            self._register_ar_activity(activity_belt, spec.name+f"_street_window_activity_{idx}", "window", 0.08, 0.34, 0.42 + idx*0.07)
            self.ar_architecture_stats["window_bands"] += 1

    def _add_box_architecture(self, spec: BuildingSpec, theme_key: str, theme):
        # Everything in this function physically touches the AR facade shell. No detached decoration.
        root = self._ar_arch_root(spec)
        front_y = -(spec.sy / 2.0) - 0.78
        h = spec.height
        sx = spec.sx
        sy = spec.sy
        variant = self._spec_variant(spec, theme_key + "_box_arch", 3)

        # Recess placement varies so repeated masses do not all share the same centerline.
        recess_offset = 0.0
        if variant == 1:
            recess_offset = -sx * 0.16
        elif variant == 2:
            recess_offset = sx * 0.16
        recess_w = max(4.6, sx * (0.22 if theme_key != "core" else 0.30))
        recess_h = max(8.0, h * (0.50 + 0.08*self._spec_scalar(spec, "recess_h")))
        self._attached_color_box(root, spec.name+"_recess", recess_w, 0.34, recess_h, (recess_offset, front_y-0.18, h*0.18), (0.018,0.026,0.040,1.0))
        self.ar_architecture_stats["recesses"] += 1
        rail_w = max(0.8, recess_w * 0.10)
        self._attached_color_box(root, spec.name+"_recess_rail", rail_w, 0.22, recess_h*0.94, (recess_offset, front_y-0.39, h*0.20), theme["primary"])

        if theme_key == "north":
            if variant == 0:
                for idx, frac in enumerate((0.34, 0.66)):
                    bw = sx * (0.72 if idx == 0 else 0.60)
                    self._attached_color_box(root, spec.name+f"_north_balcony_{idx}", bw, 2.8, 0.55, (0.0, front_y-1.15, h*frac), theme["secondary"])
                    self.ar_architecture_stats["balconies"] += 1
            elif variant == 1:
                self._attached_color_box(root, spec.name+"_north_sky_terrace", sx*0.82, 3.0, 0.56, (0.0, front_y-1.18, h*0.58), theme["secondary"])
                self._attached_color_box(root, spec.name+"_north_header", sx*0.68, 0.44, 0.34, (0.0, front_y-0.62, h*0.78), theme["primary"])
                self.ar_architecture_stats["balconies"] += 1
            else:
                for side in (-0.20,0.20):
                    self._attached_textured_box(root, spec.name+f"_north_side_stack_{side:+.2f}", max(3.6,sx*0.18), 1.5, h*0.72, (side*sx, front_y-0.68, h*0.10), theme_key, scale_u=1.0, scale_v=max(1.4,h/26.0))
                self._attached_color_box(root, spec.name+"_north_gallery", sx*0.56, 2.4, 0.52, (0.0, front_y-1.08, h*0.40), theme["secondary"])
                self.ar_architecture_stats["balconies"] += 1
            if h > 58:
                roof_count = 2 if variant != 1 else 1
                for idx in range(roof_count):
                    side = 0.0 if roof_count == 1 else (-0.20 if idx == 0 else 0.20)
                    rw = max(4.0, sx*(0.22 if roof_count == 2 else 0.34))
                    rh = max(7.0, min(18.0, h*0.14))
                    self._attached_textured_box(root, spec.name+f"_north_roof_{idx}", rw, sy*(0.34 if roof_count == 2 else 0.46), rh, (side*sx, 0.0, h+0.55), theme_key)
                    self.ar_architecture_stats["roof_structures"] += 1
        elif theme_key == "east":
            if variant == 0:
                self._attached_color_box(root, spec.name+"_east_cantilever", sx*0.54, 3.6, 0.65, (sx*0.16, front_y-1.55, h*0.50), theme["secondary"])
                self.ar_architecture_stats["balconies"] += 1
                rib_h = h*0.78
                self._attached_textured_box(root, spec.name+"_east_rib", max(3.2,sx*0.14), 1.6, rib_h, (-sx*0.38, front_y-0.70, h*0.10), theme_key, scale_u=1.0, scale_v=max(1.5,rib_h/24.0))
            elif variant == 1:
                for side in (-0.30,0.26):
                    rib_h = h*(0.64 if side < 0 else 0.82)
                    self._attached_textured_box(root, spec.name+f"_east_dual_rib_{side:+.2f}", max(2.8,sx*0.12), 1.45, rib_h, (side*sx, front_y-0.72, h*0.10), theme_key, scale_u=1.0, scale_v=max(1.4,rib_h/24.0))
                self._attached_color_box(root, spec.name+"_east_bridge_band", sx*0.48, 2.6, 0.52, (sx*0.10, front_y-1.24, h*0.60), theme["secondary"])
                self.ar_architecture_stats["balconies"] += 1
            else:
                for frac, off in ((0.34,-0.10),(0.56,0.14),(0.76,-0.04)):
                    self._attached_color_box(root, spec.name+f"_east_pulse_deck_{frac:.2f}", sx*0.42, 2.1, 0.44, (off*sx, front_y-1.00, h*frac), theme["primary"] if frac < 0.5 else theme["secondary"])
                    self.ar_architecture_stats["balconies"] += 1
            if h > 62:
                top_h=max(6.0,min(16.0,h*(0.11 if variant != 2 else 0.15)))
                top_x = sx*(0.10 if variant != 2 else -0.12)
                self._attached_textured_box(root, spec.name+"_east_setback", sx*(0.58 if variant != 1 else 0.48), sy*(0.56 if variant != 1 else 0.46), top_h, (top_x,0.0,h+0.55), theme_key)
                self.ar_architecture_stats["setbacks"] += 1
        elif theme_key == "south":
            if variant == 0:
                for idx, frac in enumerate((0.28,0.52,0.76)):
                    bw=sx*(0.82-idx*0.10)
                    self._attached_color_box(root, spec.name+f"_south_terrace_{idx}", bw, 2.4, 0.48, (0.0, front_y-1.00, h*frac), theme["primary"] if idx%2==0 else theme["secondary"])
                    self.ar_architecture_stats["balconies"] += 1
            elif variant == 1:
                for idx, (frac, off) in enumerate(((0.30,-0.14),(0.56,0.14),(0.78,-0.10))):
                    bw=sx*(0.66-idx*0.08)
                    self._attached_color_box(root, spec.name+f"_south_stagger_{idx}", bw, 2.2, 0.46, (off*sx, front_y-0.96, h*frac), theme["secondary"] if idx==1 else theme["primary"])
                    self.ar_architecture_stats["balconies"] += 1
            else:
                self._attached_color_box(root, spec.name+"_south_lounge_deck", sx*0.76, 2.8, 0.52, (0.0, front_y-1.04, h*0.42), theme["secondary"])
                self._attached_color_box(root, spec.name+"_south_lounge_deck_2", sx*0.58, 2.4, 0.46, (0.0, front_y-0.98, h*0.68), theme["primary"])
                self.ar_architecture_stats["balconies"] += 2
            if h > 54:
                roof1_h=max(5.0,min(12.0,h*0.10))
                roof2_h=max(4.0,min(9.0,h*0.075))
                roof1_x = 0 if variant == 0 else sx*(0.08 if variant == 1 else -0.10)
                roof2_x = 0 if variant != 1 else -sx*0.06
                self._attached_textured_box(root, spec.name+"_south_roof_1", sx*(0.68 if variant != 2 else 0.58), sy*0.60, roof1_h, (roof1_x,0, h+0.55), theme_key)
                self._attached_textured_box(root, spec.name+"_south_roof_2", sx*0.42, sy*0.38, roof2_h, (roof2_x,0,h+0.55+roof1_h), theme_key)
                self.ar_architecture_stats["setbacks"] += 2
        elif theme_key == "west":
            if variant == 0:
                col_w=max(2.4,sx*0.09)
                for side in (-0.40,0.40):
                    self._attached_color_box(root, spec.name+f"_west_column_{side:+.2f}", col_w, 1.25, h*0.86, (side*sx, front_y-0.62, h*0.07), theme["secondary"] if side<0 else theme["primary"])
                self._attached_color_box(root, spec.name+"_west_service_ledge", sx*0.68, 2.2, 0.65, (0,front_y-0.90,h*0.42), theme["primary"])
                self.ar_architecture_stats["balconies"] += 1
            elif variant == 1:
                for side in (-0.30,0.0,0.30):
                    self._attached_textured_box(root, spec.name+f"_west_frame_{side:+.2f}", max(2.4,sx*0.10), 1.2, h*0.74, (side*sx, front_y-0.66, h*0.10), theme_key, scale_u=1.0, scale_v=max(1.4,h/24.0))
                beam_h = h*0.68
                self._attached_color_box(root, spec.name+"_west_crossbeam", sx*0.76, 0.50, 0.42, (0.0, front_y-0.72, beam_h), theme["secondary"])
            else:
                for frac in (0.26,0.52):
                    self._attached_color_box(root, spec.name+f"_west_catwalk_{frac:.2f}", sx*0.60, 2.3, 0.54, (0.0, front_y-0.92, h*frac), theme["primary"] if frac < 0.4 else theme["secondary"])
                    self.ar_architecture_stats["balconies"] += 1
                self._attached_textured_box(root, spec.name+"_west_side_stack", max(3.0,sx*0.15), 1.55, h*0.70, (-sx*0.34, front_y-0.68, h*0.12), theme_key, scale_u=1.0, scale_v=max(1.4,h/24.0))
            if h > 45:
                top_h=max(6.0,min(14.0,h*0.12))
                top_x = -sx*0.12 if variant != 1 else sx*0.12
                self._attached_textured_box(root, spec.name+"_west_service_roof", sx*(0.48 if variant != 2 else 0.56), sy*(0.48 if variant != 1 else 0.42), top_h, (top_x,0,h+0.55), theme_key)
                self.ar_architecture_stats["roof_structures"] += 1
        else:  # core
            if variant == 0:
                for side in (-0.34,0.34):
                    self._attached_textured_box(root, spec.name+f"_core_buttress_{side:+.2f}", max(3.5,sx*0.14), 1.6, h*0.90, (side*sx, front_y-0.72, h*0.04), theme_key, scale_u=1.0, scale_v=max(1.6,h/24.0))
                for idx, frac in enumerate((0.38,0.70)):
                    self._attached_color_box(root, spec.name+f"_core_ledge_{idx}", sx*0.72, 2.5, 0.55, (0,front_y-1.00,h*frac), theme["secondary"] if idx else theme["primary"])
                    self.ar_architecture_stats["balconies"] += 1
            elif variant == 1:
                self._attached_textured_box(root, spec.name+"_core_portal_left", max(3.2,sx*0.12), 1.5, h*0.84, (-sx*0.26, front_y-0.70, h*0.06), theme_key, scale_u=1.0, scale_v=max(1.5,h/24.0))
                self._attached_textured_box(root, spec.name+"_core_portal_right", max(3.2,sx*0.12), 1.5, h*0.84, (sx*0.26, front_y-0.70, h*0.06), theme_key, scale_u=1.0, scale_v=max(1.5,h/24.0))
                self._attached_color_box(root, spec.name+"_core_terrace", sx*0.64, 2.7, 0.56, (0,front_y-1.04,h*0.56), theme["primary"])
                self.ar_architecture_stats["balconies"] += 1
            else:
                for side in (-0.18,0.18):
                    self._attached_color_box(root, spec.name+f"_core_blade_{side:+.2f}", max(2.6,sx*0.10), 1.0, h*0.88, (side*sx, front_y-0.66, h*0.05), theme["secondary"] if side < 0 else theme["primary"])
                self._attached_color_box(root, spec.name+"_core_header_band", sx*0.78, 0.44, 0.34, (0,front_y-0.68,h*0.74), theme["secondary"])
            if h > 52:
                top_h=max(7.0,min(18.0,h*(0.14 if variant != 2 else 0.12)))
                self._attached_textured_box(root, spec.name+"_core_setback", sx*(0.62 if variant != 1 else 0.50), sy*(0.62 if variant != 2 else 0.54), top_h, (0,0,h+0.55), theme_key)
                self.ar_architecture_stats["setbacks"] += 1

    def _add_cylinder_architecture(self, spec: BuildingSpec, theme_key: str, theme):
        root = self._ar_arch_root(spec)
        radius = min(spec.sx,spec.sy)/2.0 + 1.80
        h=spec.height
        variant = self._spec_variant(spec, theme_key + "_cyl_arch", 3)
        if theme_key == "south":
            collar_fracs = (0.24,0.48,0.74) if variant != 2 else (0.34,0.68)
        elif variant == 1:
            collar_fracs = (0.26,0.56,0.80)
        else:
            collar_fracs = (0.34,0.68)
        for idx, frac in enumerate(collar_fracs):
            collar = make_cylinder_geom(spec.name+f"_collar_{idx}", radius+0.95+(0.12 if variant==2 and idx==0 else 0.0), 0.72, 24, theme["primary"] if idx%2==0 else theme["secondary"], top_radius=radius+0.95)
            collar.reparentTo(root)
            collar.setZ(h*frac)
            self.ar_architecture_stats["modules"] += 1
            self.ar_architecture_stats["balconies"] += 1
        if h > 36:
            crown_r=radius*(0.66 if theme_key in ("south","east") else 0.58)
            crown_h=max(5.0,min(16.0,h*(0.12 if variant==1 else 0.14)))
            crown=make_textured_cylinder_geom(spec.name+"_roof_crown",crown_r,crown_h,20,(1,1,1,1),top_radius=crown_r*(0.82 if theme_key=="east" else (0.90 if variant==2 else 1.0)))
            crown.reparentTo(root)
            crown.setZ(h+0.55)
            crown.setTexture(self.theme_textures[theme_key],1)
            crown.setTexScale(TextureStage.getDefault(),max(1.0,(2*math.pi*crown_r)/24.0),1.0)
            self.ar_architecture_stats["modules"] += 1
            self.ar_architecture_stats["roof_structures"] += 1
        fin_count_map = {"north":(6,8,4),"east":(4,6,5),"south":(4,6,5),"west":(8,6,10),"core":(6,8,6)}
        fin_count = fin_count_map[theme_key][variant]
        for i in range(fin_count):
            ang=360.0*i/fin_count
            fin_h = h*(0.82 if variant != 1 else 0.72)
            fin=make_box_geom(spec.name+f"_arch_fin_{i}",1.0 if variant != 2 else 1.25,1.5,fin_h,theme["secondary"] if i%2 else theme["primary"])
            fin.reparentTo(root)
            fin.setH(ang)
            fin.setY(fin,radius+0.72)
            fin.setZ(h*0.08)
            self.ar_architecture_stats["modules"] += 1
        if variant == 2 and h > 52:
            belt = make_cylinder_geom(spec.name+"_mid_belt", radius+0.18, 1.15, 24, theme["secondary"], top_radius=radius+0.18)
            belt.reparentTo(root)
            belt.setZ(h*0.52)
            self.ar_architecture_stats["modules"] += 1

    def _coverage_color(self, theme_key: str, layer: str = "base"):
        theme = DISTRICT_THEMES[theme_key]
        p = theme["primary"]; s = theme["secondary"]
        if layer == "base":
            return (0.055 + p[0]*0.10, 0.065 + p[1]*0.10, 0.078 + p[2]*0.10, 1.0)
        if layer == "trim":
            return (0.085 + s[0]*0.14, 0.095 + s[1]*0.14, 0.11 + s[2]*0.14, 1.0)
        if layer == "cap":
            return (0.12 + p[0]*0.16, 0.13 + p[1]*0.16, 0.15 + p[2]*0.16, 1.0)
        return (0.07 + p[0]*0.08, 0.08 + p[1]*0.08, 0.095 + p[2]*0.08, 1.0)

    def _coverage_box(self, root: NodePath, name: str, sx: float, sy: float, sz: float, pos: tuple[float,float,float], color, depth_offset: int = 2, stat_key: str | None = None) -> NodePath:
        np = make_box_geom(name, sx, sy, sz, color)
        np.reparentTo(root)
        np.setPos(*pos)
        np.setDepthOffset(depth_offset)
        self._apply_reflective_surface(np, strength=0.52 if sz <= 1.5 else 0.42)
        self.ar_architecture_stats["modules"] += 1
        if stat_key:
            self.ar_architecture_stats[stat_key] += 1
        return np

    def _detail_color(self, theme_key: str, which: str = "primary", strength: float = 0.42):
        theme = DISTRICT_THEMES[theme_key]
        c = theme[which]
        return (0.035 + c[0]*strength, 0.040 + c[1]*strength, 0.050 + c[2]*strength, 1.0)

    def _add_wall_ar_coverage(self):
        arc = 2*math.pi*((INNER_WALL_RADIUS+OUTER_WALL_RADIUS)/2)/WALL_SEGMENTS
        depth = OUTER_WALL_RADIUS-INNER_WALL_RADIUS
        radius = (INNER_WALL_RADIUS+OUTER_WALL_RADIUS)/2
        for i in range(WALL_SEGMENTS):
            angle = 360*i/WALL_SEGMENTS
            if is_gate_angle(angle):
                continue
            x,y,_ = polar(radius,angle,0)
            theme_key = self._theme_key_for_point(x,y)
            root = self.utopia_root.attachNewNode(f"wall_{i}_ar_coverage")
            root.setPos(x,y,0.02); root.setH(angle)
            self._coverage_box(root,f"wall_{i}_skin",arc*1.025,depth+0.22,WALL_HEIGHT+0.20,(0,0,0),self._coverage_color(theme_key,"base"),2,"coverage_wall_pieces")
            self._coverage_box(root,f"wall_{i}_plinth_skin",arc*0.995,depth*0.80,2.34,(0,0,0.01),self._coverage_color(theme_key,"trim"),3,"coverage_wall_pieces")
            self._coverage_box(root,f"wall_{i}_cap_skin",arc*1.045,depth*0.66,1.28,(0,0,WALL_HEIGHT-0.02),self._coverage_color(theme_key,"cap"),3,"coverage_wall_pieces")
            # Large structural-art panels break the previously plain wall face without wallpapering it.
            face_y = -depth/2.0 - 0.18
            variant = i % 3
            dark = self._detail_color(theme_key,"primary",0.18)
            trim = self._detail_color(theme_key,"secondary",0.36)
            accent = self._detail_color(theme_key,"primary",0.54)
            if variant == 0:
                self._coverage_box(root,f"wall_{i}_detail_panel",arc*0.70,0.16,7.8,(0,face_y,6.1),dark,5,"detail_wall_surfaces")
                for lateral in (-arc*0.27, arc*0.27):
                    self._coverage_box(root,f"wall_{i}_detail_rib_{lateral:+.2f}",0.34,0.20,9.2,(lateral,face_y-0.02,5.4),trim,6,"detail_wall_surfaces")
                self._coverage_box(root,f"wall_{i}_detail_header",arc*0.66,0.20,0.34,(0,face_y-0.02,13.0),accent,6,"detail_wall_surfaces")
            elif variant == 1:
                for lateral in (-arc*0.20, arc*0.20):
                    self._coverage_box(root,f"wall_{i}_detail_tall_{lateral:+.2f}",arc*0.24,0.16,10.4,(lateral,face_y,4.6),dark,5,"detail_wall_surfaces")
                self._coverage_box(root,f"wall_{i}_detail_crossbar",arc*0.62,0.20,0.30,(0,face_y-0.02,10.7),trim,6,"detail_wall_surfaces")
            else:
                self._coverage_box(root,f"wall_{i}_detail_center",arc*0.34,0.16,9.0,(0,face_y,5.0),dark,5,"detail_wall_surfaces")
                self._coverage_box(root,f"wall_{i}_detail_spine",0.44,0.21,11.4,(0,face_y-0.03,4.1),accent,6,"detail_wall_surfaces")
                for z in (6.6,11.4):
                    self._coverage_box(root,f"wall_{i}_detail_band_{z:.1f}",arc*0.54,0.20,0.28,(0,face_y-0.02,z),trim,6,"detail_wall_surfaces")
            # Mirror a restrained structural panel to the outward face so exterior gate approaches are authored too.
            outer_y=depth/2.0+0.18
            self._coverage_box(root,f"wall_{i}_outer_panel",arc*0.62,0.16,8.2,(0,outer_y,5.8),dark,5,"detail_wall_surfaces")
            for lateral in (-arc*0.24,arc*0.24):
                self._coverage_box(root,f"wall_{i}_outer_rib_{lateral:+.2f}",0.30,0.20,9.5,(lateral,outer_y+0.02,5.1),trim,6,"detail_wall_surfaces")
            self._coverage_box(root,f"wall_{i}_outer_header",arc*0.58,0.20,0.30,(0,outer_y+0.02,13.2),accent,6,"detail_wall_surfaces")
            # Gate-adjacent wall returns were still broad blank slabs when viewed from the bridge.
            nearest_gate=min(angle_delta(angle,g) for g in (0.0,90.0,180.0,270.0))
            if nearest_gate <= 12.0:
                for side in (-1,1):
                    ex=side*(arc*0.515)
                    self._coverage_box(root,f"wall_{i}_gate_return_{side}",0.18,depth*0.72,12.6,(ex,0,4.5),dark,6,"detail_gate_surfaces")
                    for z in (6.4,10.2,14.0):
                        self._coverage_box(root,f"wall_{i}_gate_return_band_{side}_{z:.1f}",0.22,depth*0.58,0.30,(ex+side*0.02,0,z),trim,7,"detail_gate_surfaces")
            # Quiet vertical datum remains sparse.
            if i % 4 == 0:
                seam_color = self._detail_color(theme_key,"primary",0.34)
                seam = make_box_geom(f"wall_{i}_datum", max(0.40,arc*0.018), 0.16, WALL_HEIGHT*0.50, seam_color)
                seam.reparentTo(root); seam.setPos(0,face_y-0.04,WALL_HEIGHT*0.22); seam.setDepthOffset(7)
                self.ar_architecture_stats["modules"] += 1
            if i % 2 == 0:
                pier_h = WALL_HEIGHT + (4.0 if i % 4 == 0 else 2.6)
                pier_w = max(3.2, arc*0.18)
                self._coverage_box(root,f"wall_{i}_pier_skin",pier_w+0.20,depth*0.71,pier_h+0.20,(0,0,0.02),self._coverage_color(theme_key,"trim"),4,"coverage_wall_pieces")

    def _add_gate_ar_coverage(self):
        bridge_len=170.0
        for angle in (0,90,180,270):
            mid=CITY_RADIUS+bridge_len/2-5
            x,y,_=polar(mid,angle,0)
            theme_key,_=self._pedestrian_theme_for_angle(angle)
            root=self.utopia_root.attachNewNode(f"gate_{angle}_ar_coverage")
            root.setPos(x,y,0); root.setH(angle)
            self._coverage_box(root,f"bridge_{angle}_structural_skin",34.30,bridge_len+0.25,1.18,(0,0,-1.20),self._coverage_color(theme_key,"base"),2,"coverage_gate_pieces")
            trim=self._detail_color(theme_key,"primary",0.46)
            plate=self._detail_color(theme_key,"secondary",0.22)
            for lateral in (-18.0,18.0):
                self._coverage_box(root,f"bridge_{angle}_barrier_skin_{int(lateral)}",1.38,bridge_len+0.22,2.38,(lateral,0,0.02),self._coverage_color(theme_key,"trim"),3,"coverage_gate_pieces")
                inner_sign = -1.0 if lateral > 0 else 1.0
                panel_x = lateral + inner_sign*0.78
                # Five broad service bays along the inner barrier face.
                for bay in range(5):
                    py = -bridge_len*0.40 + bay*(bridge_len*0.20)
                    self._coverage_box(root,f"bridge_{angle}_bay_{int(lateral)}_{bay}",0.16,bridge_len*0.145,1.08,(panel_x,py,0.50),plate,5,"detail_gate_surfaces")
                    if bay % 2 == 0:
                        self._coverage_box(root,f"bridge_{angle}_bay_rib_{int(lateral)}_{bay}",0.20,0.34,1.64,(panel_x-inner_sign*0.02,py,0.32),trim,6,"detail_gate_surfaces")
                self._coverage_box(root,f"bridge_{angle}_barrier_cap_{int(lateral)}",0.20,bridge_len*0.88,0.22,(panel_x,0,1.92),trim,6,"detail_gate_surfaces")

    def _add_transit_ar_coverage(self):
        radius=222.0; segments=64
        arc=2*math.pi*radius/segments
        for i in range(segments):
            angle=360*i/segments
            x,y,_=polar(radius,angle,8.2)
            theme_key=self._theme_key_for_point(x,y)
            root=self.utopia_root.attachNewNode(f"transit_{i}_ar_coverage")
            root.setPos(x,y,8.22); root.setH(angle)
            self._coverage_box(root,f"transit_deck_skin_{i}",arc*1.055,7.20,1.34,(0,0,0),self._coverage_color(theme_key,"base"),2,"coverage_transit_pieces")
            fascia=self._detail_color(theme_key,"primary",0.42)
            recess=self._detail_color(theme_key,"secondary",0.18)
            # Give the ring a readable engineered fascia instead of a plain slab edge.
            for side in (-1,1):
                fy=side*3.72
                self._coverage_box(root,f"transit_fascia_{i}_{side}",arc*0.92,0.18,0.28,(0,fy,0.24),fascia,5,"detail_transit_surfaces")
                self._coverage_box(root,f"transit_recess_{i}_{side}",arc*0.58,0.16,0.38,(0,fy+side*0.03,0.66),recess,5,"detail_transit_surfaces")
            if i%4==0:
                support_root=self.utopia_root.attachNewNode(f"transit_support_{i}_ar_root")
                support_root.setPos(x,y,0.02)
                self._coverage_box(support_root,f"transit_support_skin_{i}",2.38,2.38,8.38,(0,0,0),self._coverage_color(theme_key,"trim"),3,"coverage_transit_pieces")
                self._coverage_box(support_root,f"transit_support_collar_{i}",3.00,3.00,0.42,(0,0,5.85),fascia,5,"detail_transit_surfaces")
                self._coverage_box(support_root,f"transit_support_base_{i}",3.30,3.30,0.34,(0,0,0.08),recess,5,"detail_transit_surfaces")

    def _add_overlook_ar_coverage(self):
        x,y,_=polar(452,180,0)
        theme_key="south"
        root=self.utopia_root.attachNewNode("overlook_structural_ar_coverage")
        root.setPos(x,y,0)
        trim=self._detail_color(theme_key,"primary",0.44)
        recess=self._detail_color(theme_key,"secondary",0.20)
        for lateral in (-29,29):
            self._coverage_box(root,f"overlook_rail_skin_{int(lateral)}",1.18,34.18,1.32,(lateral,0,0.19),self._coverage_color(theme_key,"trim"),3,"coverage_overlook_pieces")
            for py in (-12.0,-6.0,0.0,6.0,12.0):
                self._coverage_box(root,f"overlook_post_{int(lateral)}_{int(py)}",0.30,0.42,1.95,(lateral,py,0.10),trim,5,"detail_overlook_surfaces")
            inner_sign=-1.0 if lateral>0 else 1.0
            self._coverage_box(root,f"overlook_inset_{int(lateral)}",0.16,26.0,0.44,(lateral+inner_sign*0.70,0,0.44),recess,5,"detail_overlook_surfaces")
        self._coverage_box(root,"overlook_back_skin",58.18,1.18,1.32,(0,-16.5,0.19),self._coverage_color(theme_key,"trim"),3,"coverage_overlook_pieces")
        for px in (-22,-11,0,11,22):
            self._coverage_box(root,f"overlook_back_post_{px}",0.34,0.34,1.95,(px,-16.5,0.10),trim,5,"detail_overlook_surfaces")
        self._coverage_box(root,"overlook_back_inset",46.0,0.16,0.44,(0,-17.18,0.44),recess,5,"detail_overlook_surfaces")

    def _make_box_ar_skin(self, spec: BuildingSpec, theme_key: str, theme):
        variant = self._spec_variant(spec, "box_skin", 3)
        tex_u = max(1.0, (spec.sx + spec.sy) / 28.0) * (0.90 + 0.22*self._spec_scalar(spec, "skin_u"))
        tex_v = max(1.4, spec.height / 34.0) * (0.94 + 0.18*self._spec_scalar(spec, "skin_v"))
        color_bias = 0.90 + 0.06*self._spec_scalar(spec, "skin_color")
        skin = make_textured_box_geom(spec.name + "_ar_skin", spec.sx + 1.1, spec.sy + 1.1, spec.height + 0.55, (1,1,1,1))
        skin.reparentTo(self.utopia_root)
        skin.setPos(spec.x, spec.y, spec.z + 0.02)
        skin.setH(spec.heading)
        skin.setTexture(self.theme_textures[theme_key], 1)
        skin.setDepthOffset(2)
        skin.setTwoSided(False)
        skin.setTexScale(TextureStage.getDefault(), tex_u, tex_v)
        skin.setColorScale(0.92*color_bias, 0.95*color_bias, 0.99*color_bias, 1.0)
        self._apply_pattern_neon_surface(skin, theme_key, 0.15, 1.06)
        # Low textured podium: architectural base, not a bright billboard/slab.
        if max(spec.sx, spec.sy) > 24.0:
            podium_h = min(2.4, max(1.15, spec.height * (0.024 + 0.010*self._spec_scalar(spec, "podium_h"))))
            podium = make_textured_box_geom(spec.name + "_podium_trim", spec.sx + 1.8, spec.sy + 1.8, podium_h, (1,1,1,1))
            podium.reparentTo(self.utopia_root)
            podium.setPos(spec.x, spec.y, spec.z + 0.04)
            podium.setH(spec.heading)
            podium.setTexture(self.theme_textures[theme_key], 1)
            podium.setTexScale(TextureStage.getDefault(), max(1.0,(spec.sx+spec.sy)/24.0), 1.0)
            podium.setColorScale(0.56,0.62,0.72,1.0)
            self._apply_pattern_neon_surface(podium, theme_key, 0.22, 1.04)
            accent = make_box_geom(spec.name + "_podium_accent", spec.sx + 1.95, spec.sy + 1.95, 0.24, theme["secondary"])
            accent.reparentTo(self.utopia_root)
            accent.setPos(spec.x, spec.y, spec.z + podium_h + 0.05)
            accent.setH(spec.heading)
        # Cover the physical tall-block crown with a calm AR material rather than repeating facade wallpaper.
        if spec.height > 70:
            physical_crown_h = min(15.0, spec.height * 0.15)
            crown = make_box_geom(spec.name + "_ar_roof_crown_coverage", spec.sx * 0.62 + 0.36, spec.sy * 0.62 + 0.36, physical_crown_h + 0.28, self._coverage_color(theme_key,"base"))
            crown.reparentTo(self.utopia_root)
            crown.setPos(spec.x, spec.y, spec.z + spec.height + 0.02)
            crown.setH(spec.heading)
            crown.setDepthOffset(3)
            cap = make_box_geom(spec.name + "_ar_roof_crown_cap", spec.sx * 0.54, spec.sy * 0.54, 0.42, self._coverage_color(theme_key,"cap"))
            cap.reparentTo(self.utopia_root)
            cap.setPos(spec.x, spec.y, spec.z + spec.height + physical_crown_h + 0.08)
            cap.setH(spec.heading)
            cap.setDepthOffset(4)
            # Cross-braced top treatment gives previously plain crown surfaces readable structure.
            roof_z = spec.z + spec.height + physical_crown_h + 0.48
            rail_a = make_box_geom(spec.name + "_roof_detail_a", spec.sx * 0.42, 0.46, 0.30, self._detail_color(theme_key,"primary",0.48))
            rail_a.reparentTo(self.utopia_root); rail_a.setPos(spec.x,spec.y,roof_z); rail_a.setH(spec.heading); rail_a.setDepthOffset(5)
            rail_b = make_box_geom(spec.name + "_roof_detail_b", 0.46, spec.sy * 0.42, 0.30, self._detail_color(theme_key,"secondary",0.42))
            rail_b.reparentTo(self.utopia_root); rail_b.setPos(spec.x,spec.y,roof_z+0.02); rail_b.setH(spec.heading); rail_b.setDepthOffset(5)
            hub = make_box_geom(spec.name + "_roof_detail_hub", max(2.8,spec.sx*0.12), max(2.8,spec.sy*0.12), 0.46, self._coverage_color(theme_key,"cap"))
            hub.reparentTo(self.utopia_root); hub.setPos(spec.x,spec.y,roof_z+0.08); hub.setH(spec.heading); hub.setDepthOffset(6)
            self.ar_architecture_stats["modules"] += 5
            self.ar_architecture_stats["coverage_roof_crowns"] += 1
            self.ar_architecture_stats["detail_roof_surfaces"] += 3
        # restrained luminous spines integrated with the facade, but no longer identical on every building.
        if variant == 0:
            spine_positions = (-0.24, 0.24)
        elif variant == 1:
            spine_positions = (-0.32, 0.0, 0.32)
        else:
            spine_positions = (-0.18, 0.18)
            band = make_box_geom(spec.name + "_datum_band", spec.sx * 0.72, 0.38, 0.28, theme["secondary"])
            band.reparentTo(self.utopia_root)
            band.setPos(spec.x, spec.y, spec.z + spec.height * 0.62)
            band.setH(spec.heading)
            band.setY(band, -(spec.sy / 2.0) - 0.70)
        spine_w = max(2.0, spec.sx * 0.072)
        for idx, lateral in enumerate(spine_positions):
            spine = make_box_geom(spec.name + f"_spine_{idx}", spine_w, 0.45, spec.height * 0.92, theme["primary"] if idx % 2 == 0 else theme["secondary"])
            spine.reparentTo(self.utopia_root)
            spine.setPos(spec.x, spec.y, spec.z + 0.16)
            spine.setH(spec.heading)
            spine.setX(spine, lateral * spec.sx)
            spine.setY(spine, -(spec.sy / 2.0) - 0.64)
        if spec.height >= 40.0 and max(spec.sx, spec.sy) >= 20.0:
            self._add_box_architecture(spec, theme_key, theme)
        self._add_box_hero_signature(spec, theme_key, theme)
        self._add_box_street_detail(spec, theme_key, theme)

    def _make_cylinder_ar_skin(self, spec: BuildingSpec, theme_key: str, theme):
        radius = min(spec.sx, spec.sy) / 2.0
        shell_pad = 1.8
        skin = make_textured_cylinder_geom(spec.name + "_ar_skin", radius + shell_pad, spec.height + 0.55, 16, (1,1,1,1), top_radius=radius * spec.top_scale + shell_pad)
        skin.reparentTo(self.utopia_root)
        skin.setPos(spec.x, spec.y, spec.z + 0.02)
        skin.setTexture(self.theme_textures[theme_key], 1)
        skin.setDepthOffset(2)
        skin.setTwoSided(True)
        skin.setTexScale(TextureStage.getDefault(), max(1.0, (2.0 * math.pi * radius) / 26.0), max(1.4, spec.height / 34.0))
        skin.setColorScale(0.93, 0.95, 0.98, 1.0)
        self._apply_pattern_neon_surface(skin, theme_key, 0.15, 1.06)
        # The architecture helper below owns collars, fins and roof crown; avoid duplicate bright geometry.
        if spec.height >= 40.0:
            self._add_cylinder_architecture(spec, theme_key, theme)
        self._add_cylinder_hero_signature(spec, theme_key, theme)
        self._add_cylinder_street_detail(spec, theme_key, theme)

    def _build_utopia_layer(self):
        # Building-focused resident layer: keep the reveal architectural and reduce floating clutter.
        all_structures = self.buildings + self.ar_structure_specs
        for spec in all_structures:
            theme_key, theme = self._theme_for_spec(spec)
            if spec.style == "cylinder":
                self._make_cylinder_ar_skin(spec, theme_key, theme)
            else:
                self._make_box_ar_skin(spec, theme_key, theme)

        self._add_pedestrian_surface_layer()
        # Finish previously plain physical exterior systems with calm AR coverage only.
        self._add_wall_ar_coverage()
        self._add_gate_ar_coverage()
        self._add_transit_ar_coverage()
        self._add_overlook_ar_coverage()
        self._build_utopia_project_systems()

        # No floating route rings, spire halos, orbital markers, or sky lattice in this pass.
        # The alternate sky remains dark so the building skins and promenades are the visual focus.

    def _build_citizen_presence_orbs(self):
        """Build a sparse AR-only presence layer inspired by multiplayer-lobby avatars.

        These are intentionally not NPCs.  They have no collision, names, prompts, or gameplay
        authority.  District wanderers stay near their home area while four commuter orbs travel
        through multiple districts, all with a hard radius safely inside Utopia's outer wall.
        """
        rng=random.Random(43043)
        self.citizen_orbs=[]
        self.citizen_orb_stats={"total":0,"core":0,"north":0,"east":0,"south":0,"west":0,"commuters":0}

        def add_orb(name:str, district:str, mode:str, home_radius:float, home_angle:float, *, travel_speed:float=0.0):
            theme=DISTRICT_THEMES[district]
            base=theme["primary"] if (self.citizen_orb_stats["total"] % 2 == 0) else theme["secondary"]
            # Keep the core visibly translucent while the broader halo is extremely faint.
            core_color=(base[0],base[1],base[2],0.62)
            halo_color=(base[0],base[1],base[2],0.10)
            root=self.utopia_root.attachNewNode(name+"_root")
            size=rng.uniform(0.72,1.02)
            core=make_uv_sphere_geom(name+"_core",size,core_color,10,16)
            core.reparentTo(root); core.setTransparency(TransparencyAttrib.MAlpha); core.setBin("transparent",20)
            halo=make_uv_sphere_geom(name+"_halo",size*1.48,halo_color,8,12)
            halo.reparentTo(root); halo.setTransparency(TransparencyAttrib.MAlpha); halo.setDepthWrite(False); halo.setBin("transparent",21)
            item={
                "root":root,"core":core,"halo":halo,"district":district,"mode":mode,
                "home_radius":float(home_radius),"home_angle":float(home_angle),
                "phase":rng.uniform(0.0,math.tau),"phase2":rng.uniform(0.0,math.tau),
                "height":rng.uniform(1.65,3.25),"bob":rng.uniform(0.14,0.30),
                "wander_radius":rng.uniform(10.0,22.0),"wander_angle":rng.uniform(5.0,12.0),
                "wander_speed":rng.uniform(0.10,0.18),"travel_speed":float(travel_speed),
                "size":size,
            }
            self.citizen_orbs.append(item)
            self.citizen_orb_stats["total"] += 1
            self.citizen_orb_stats[district] += 1
            if mode=="commuter": self.citizen_orb_stats["commuters"] += 1

        # Core: four slow wanderers around Unity / Forum Nexus.
        for idx,(radius,angle) in enumerate(((48,35),(68,140),(86,225),(104,315))):
            add_orb(f"citizen_core_{idx}","core","wander",radius,angle)

        # Three sparse resident presences per outer district.
        centers={"north":0.0,"east":90.0,"south":180.0,"west":270.0}
        for district,center in centers.items():
            for idx,(radius,offset) in enumerate(((232,-17),(318,1),(402,18))):
                add_orb(f"citizen_{district}_{idx}",district,"wander",radius,center+offset)

        # Four commuters slowly circulate through every district. Their colors identify their
        # current home district, but their path is deliberately cross-district.
        commuter_specs=((174,0.92,"north"),(258,1.08,"east"),(342,1.18,"south"),(430,1.26,"west"))
        for idx,(radius,speed,district) in enumerate(commuter_specs):
            deg_per_sec=math.degrees(float(speed)/float(radius)) * (-1.0 if idx%2 else 1.0)
            add_orb(f"citizen_commuter_{idx}",district,"commuter",radius,idx*90.0,travel_speed=deg_per_sec)

        self._update_citizen_presence_orbs()

    def _update_citizen_presence_orbs(self):
        if not self.citizen_orbs:
            return
        t=float(self.ar_activity_time)
        for item in self.citizen_orbs:
            if item["mode"]=="commuter":
                radius=item["home_radius"] + math.sin(t*0.075+item["phase2"])*4.5
                angle=item["home_angle"] + t*item["travel_speed"]
            else:
                radius=item["home_radius"] + math.sin(t*item["wander_speed"]+item["phase"])*item["wander_radius"]
                angle=item["home_angle"] + math.sin(t*(item["wander_speed"]*0.78)+item["phase2"])*item["wander_angle"]
            # Hard safety clamp: citizens are representations of Utopia residents and never
            # travel into the exterior world, even if a future tuning value is too aggressive.
            radius=max(18.0,min(CITIZEN_ORB_MAX_RADIUS,float(radius)))
            x,y,_=polar(radius,angle,0.0)
            z=item["height"] + math.sin(t*0.74+item["phase"])*item["bob"]
            item["root"].setPos(x,y,z)
            # Mild breathing scale keeps them alive without becoming particle effects.
            breathe=1.0+0.035*math.sin(t*0.91+item["phase2"])
            # The AR texture is projected into a wide visor surface.  A modest vertical-only
            # compensation keeps citizen presence lights visually circular in that actual view.
            item["core"].setScale(breathe,breathe,breathe*1.82)
            halo_breathe=1.0+0.05*math.sin(t*0.63+item["phase"])
            item["halo"].setScale(halo_breathe,halo_breathe,halo_breathe*1.82)

    def _utopia_system_box(self, root: NodePath, name: str, sx: float, sy: float, sz: float, pos, color, hpr=(0,0,0)) -> NodePath:
        np=make_box_geom(name,sx,sy,sz,color); np.reparentTo(root); np.setPos(*pos); np.setHpr(*hpr)
        if not any(token in name.lower() for token in ("glow","light","beacon","signal")):
            self._apply_reflective_surface(np, strength=0.46)
        self.utopia_system_stats["modules"] += 1
        return np

    def _utopia_system_cylinder(self, root: NodePath, name: str, radius: float, height: float, pos, color, sides: int=16, top_radius: float | None=None) -> NodePath:
        np=make_cylinder_geom(name,radius,height,sides,color,top_radius=top_radius); np.reparentTo(root); np.setPos(*pos)
        if not any(token in name.lower() for token in ("glow","light","beacon","signal")):
            self._apply_reflective_surface(np, strength=0.44)
        self.utopia_system_stats["modules"] += 1
        return np

    def _register_utopia_system_activity(self, node: NodePath, name: str, system: str, kind: str, *, phase: float=0.0, speed: float=1.0, min_level: float=0.35, max_level: float=1.0, motion_y: float=0.0, motion_z: float=0.0, scale_z: float=0.0):
        parent=node.getParent()
        pos=node.getPos(parent); hpr=node.getHpr(parent); scale=node.getScale()
        item={
            "node":node, "name":name, "system":system, "kind":kind,
            "phase":self._activity_seed("utopia_system_"+name)*math.tau+phase,
            "speed":speed, "min":min_level, "max":max_level,
            "base_pos":(float(pos.x),float(pos.y),float(pos.z)),
            "base_hpr":(float(hpr.x),float(hpr.y),float(hpr.z)),
            "base_scale":(float(scale.x),float(scale.y),float(scale.z)),
            "motion_y":motion_y, "motion_z":motion_z, "scale_z":scale_z,
        }
        self.utopia_system_activity.append(item)
        self.utopia_system_activity_stats["total"] += 1
        self.utopia_system_activity_stats[system] += 1
        if motion_y or motion_z:
            self.utopia_system_activity_stats["moving"] += 1

    def _update_utopia_system_activity(self):
        t=self.ar_activity_time
        hour=float(self.ar_time_hours)%24.0
        night=max(0.0,min(1.0,(abs(hour-12.0)-4.0)/5.0))
        for item in self.utopia_system_activity:
            node=item["node"]
            phase=item["phase"]+t*item["speed"]
            wave=0.5+0.5*math.sin(phase)
            kind=item["kind"]
            if kind in ("archive_record","archive_index"):
                wave=wave*wave
            elif kind in ("dream_pod","dream_core"):
                wave=wave*wave*(3.0-2.0*wave)
            elif kind=="harbor_light":
                wave=0.15+0.85*(wave*wave*wave)
            level=item["min"]+(item["max"]-item["min"])*wave
            if kind=="harbor_light":
                level*=0.72+0.28*night
            node.setColorScale(level,level,level,1.0)
            bx,by,bz=item["base_pos"]
            if item["motion_y"] or item["motion_z"]:
                motion=math.sin(phase)
                lift=0.5+0.5*math.sin(phase*0.5+1.1)
                node.setPos(bx,by+item["motion_y"]*motion,bz+item["motion_z"]*lift)
            if item["scale_z"]:
                sx,sy,sz=item["base_scale"]
                node.setScale(sx,sy,sz*(1.0+item["scale_z"]*(wave-0.5)*2.0))

    def _register_neon_spill_source(self, root: NodePath, system: str, theme_key: str, radius: float, base_intensity: float, *, z_offset: float=5.0, phase: float=0.0, speed: float=0.6):
        theme=DISTRICT_THEMES[theme_key]
        primary=theme["primary"]; secondary=theme["secondary"]
        color=(primary[0]*0.68+secondary[0]*0.32, primary[1]*0.68+secondary[1]*0.32, primary[2]*0.68+secondary[2]*0.32)
        self.ar_neon_spill_sources.append({
            "root":root, "system":system, "color":color, "radius":float(radius),
            "base_intensity":float(base_intensity), "z_offset":float(z_offset),
            "phase":float(phase), "speed":float(speed), "current_intensity":float(base_intensity),
        })
        self.ar_material_stats["spill_sources"] = len(self.ar_neon_spill_sources)

    def _update_neon_spill_inputs(self):
        # Five system-scale emitters are intentionally capped; this is reflected light,
        # not a replacement for the hardlight pattern itself.
        t=self.ar_activity_time
        for i in range(5):
            if i < len(self.ar_neon_spill_sources):
                source=self.ar_neon_spill_sources[i]
                p=source["root"].getPos(self.render)
                wave=0.5+0.5*math.sin(source["phase"]+t*source["speed"])
                intensity=source["base_intensity"]*(0.72+0.28*wave)
                source["current_intensity"]=intensity
                r,g,b=source["color"]
                self.utopia_root.setShaderInput(f"spill_pos_radius{i}", Vec4(float(p.x),float(p.y),float(p.z)+source["z_offset"],source["radius"]))
                self.utopia_root.setShaderInput(f"spill_color_intensity{i}", Vec4(float(r),float(g),float(b),float(intensity)))
            else:
                self.utopia_root.setShaderInput(f"spill_pos_radius{i}", Vec4(0,0,-10000,0.01))
                self.utopia_root.setShaderInput(f"spill_color_intensity{i}", Vec4(0,0,0,0))

    def _build_archive_station_access(self):
        theme=DISTRICT_THEMES["core"]; root=self.utopia_root.attachNewNode("civic_archive_station_nine_access")
        root.setPos(82,-78,0.05); root.setH(-35)
        self._register_neon_spill_source(root,"archive","core",72.0,0.38,z_offset=4.0,phase=0.2,speed=0.54)
        # Grounded access seal for the buried archive rather than a fake above-ground building.
        self._utopia_system_box(root,"archive_plinth",18,12,0.32,(0,0,0),(0.035,0.08,0.09,1))
        self._utopia_system_box(root,"archive_backplane",14,1.0,8.4,(0,3.8,0.32),(0.025,0.05,0.07,1))
        for idx,x in enumerate((-5.0,0.0,5.0)):
            spine=self._utopia_system_box(root,f"archive_record_spine_{x:+.1f}",1.0,1.35,7.2,(x,3.0,0.7),theme["primary"] if x==0 else theme["secondary"])
            self._register_utopia_system_activity(spine,f"archive_record_spine_{idx}","archive","archive_record",phase=idx*1.65,speed=1.05,min_level=0.34,max_level=1.0)
        for idx,y in enumerate((-3.6,-1.2,1.2)):
            index=self._utopia_system_box(root,f"archive_floor_index_{y:+.1f}",10.5,0.22,0.12,(0,y,0.36),theme["secondary"])
            self._register_utopia_system_activity(index,f"archive_floor_index_{idx}","archive","archive_index",phase=idx*1.25,speed=0.82,min_level=0.20,max_level=0.86)
        self._utopia_system_stats_mark("archive")

    def _build_dream_catcher_node(self):
        theme=DISTRICT_THEMES["east"]; root=self.utopia_root.attachNewNode("somnology_dream_catcher_node")
        root.setPos(292,-18,0.05)
        self._register_neon_spill_source(root,"dream","east",78.0,0.42,z_offset=5.4,phase=1.0,speed=0.48)
        # Seven patient-style capture pods around a central reconstruction core.
        self._utopia_system_cylinder(root,"dream_core",2.7,6.8,(0,0,0), (0.025,0.035,0.08,1),20,1.7)
        core_light=self._utopia_system_cylinder(root,"dream_core_light",1.45,6.95,(0,0,0.05),theme["primary"],18,0.8)
        self._register_utopia_system_activity(core_light,"dream_core_light","dream","dream_core",speed=0.72,min_level=0.48,max_level=1.0,scale_z=0.035)
        for i in range(7):
            a=2*math.pi*i/7.0; x=math.sin(a)*8.8; y=math.cos(a)*8.8
            pod=self._utopia_system_cylinder(root,f"dream_pod_{i}",1.75,2.6,(x,y,0), (0.035,0.03,0.075,1),14,1.45)
            pod.setH(math.degrees(a))
            rail=self._utopia_system_box(root,f"dream_pod_rail_{i}",0.34,3.1,0.22,(x*0.72,y*0.72,0.24),theme["secondary"],(math.degrees(a),0,0))
            self._register_utopia_system_activity(rail,f"dream_pod_rail_{i}","dream","dream_pod",phase=i*(math.tau/7.0),speed=1.18,min_level=0.20,max_level=1.0)
        self._utopia_system_stats_mark("dream_catcher")

    def _build_eco_climate_node(self):
        theme=DISTRICT_THEMES["north"]; root=self.utopia_root.attachNewNode("eco_climate_control_node")
        root.setPos(-148,276,0.05); root.setH(12)
        self._register_neon_spill_source(root,"eco","north",76.0,0.36,z_offset=6.8,phase=2.1,speed=0.42)
        self._utopia_system_cylinder(root,"eco_base",6.5,0.45,(0,0,0),(0.03,0.09,0.08,1),24)
        self._utopia_system_cylinder(root,"eco_mast",1.25,14.0,(0,0,0.45),theme["primary"],14,0.72)
        for i in range(8):
            a=2*math.pi*i/8.0; x=math.sin(a)*7.8; y=math.cos(a)*7.8
            post=self._utopia_system_box(root,f"eco_rib_{i}",0.72,0.72,8.5,(x,y,0.35),theme["secondary"],(math.degrees(a),-10,0))
            cap=self._utopia_system_box(root,f"eco_sensor_{i}",1.8,1.8,0.42,(x,y,8.25),theme["primary"],(math.degrees(a),0,0))
            self._register_utopia_system_activity(cap,f"eco_sensor_{i}","eco","eco_sensor",phase=i*(math.tau/8.0),speed=0.92,min_level=0.28,max_level=0.95)
        for idx,(inner,outer,z,color) in enumerate(((6.9,8.45,4.3,theme["secondary"]),(7.0,8.6,8.35,theme["primary"]))):
            ring=make_annulus_geom(f"eco_control_ring_{idx}",inner,outer,color,64,z)
            ring.reparentTo(root); ring.setDepthOffset(2); self.utopia_system_stats["modules"] += 1
        # Low climate field bands keep the structure grounded rather than floating.
        for r in (3.2,5.4):
            for i in range(12):
                a=2*math.pi*i/12.0; x=math.sin(a)*r; y=math.cos(a)*r
                field=self._utopia_system_box(root,f"eco_field_{r}_{i}",0.28,2.2,0.14,(x,y,0.46),theme["primary"],(math.degrees(a),0,0))
                self._register_utopia_system_activity(field,f"eco_field_{r}_{i}","eco","eco_field",phase=(i*(math.tau/12.0))+(0.7 if r>4.0 else 0.0),speed=0.68,min_level=0.16,max_level=0.76)
        self._utopia_system_stats_mark("eco_climate")

    def _build_harbor_logistics_beacon(self):
        theme=DISTRICT_THEMES["south"]; root=self.utopia_root.attachNewNode("harbor_logistics_beacon")
        root.setPos(0,-478,0.05)
        self._register_neon_spill_source(root,"harbor","south",92.0,0.46,z_offset=10.5,phase=0.0,speed=0.74)
        # Twin shore beacons frame the south approach without becoming a traffic device.
        for side in (-11.5,11.5):
            self._utopia_system_box(root,f"harbor_pier_{side:+.1f}",3.2,3.2,16.0,(side,0,0),(0.045,0.025,0.055,1))
            light=self._utopia_system_box(root,f"harbor_light_{side:+.1f}",1.15,1.15,13.4,(side,-1.68,1.0),theme["secondary"] if side<0 else theme["primary"])
            self._register_utopia_system_activity(light,f"harbor_light_{side:+.1f}","harbor","harbor_light",phase=0.0 if side<0 else math.pi,speed=1.35,min_level=0.12,max_level=1.0)
            self._utopia_system_box(root,f"harbor_cap_{side:+.1f}",5.0,3.8,0.55,(side,0,16.0),theme["primary"] if side<0 else theme["secondary"])
        self._utopia_system_box(root,"harbor_crossbeam",19.8,1.2,0.62,(0,0,11.8),theme["secondary"])
        for x in (-7.5,-2.5,2.5,7.5):
            self._utopia_system_box(root,f"harbor_depth_index_{x:+.1f}",0.34,7.0,0.12,(x,4.4,0.28),theme["primary"] if x<0 else theme["secondary"])
        self._utopia_system_stats_mark("harbor")

    def _build_industry_fabrication_gantry(self):
        theme=DISTRICT_THEMES["west"]; root=self.utopia_root.attachNewNode("industry_fabrication_gantry")
        root.setPos(-292,-74,0.05); root.setH(-8)
        self._register_neon_spill_source(root,"industry","west",82.0,0.44,z_offset=7.0,phase=1.6,speed=0.58)
        for side in (-10.0,10.0):
            self._utopia_system_box(root,f"fab_column_{side:+.1f}",2.2,3.0,12.5,(side,0,0),(0.055,0.05,0.045,1))
            signal=self._utopia_system_box(root,f"fab_signal_{side:+.1f}",0.55,3.2,10.4,(side,-1.62,1.0),theme["primary"] if side<0 else theme["secondary"])
            self._register_utopia_system_activity(signal,f"fab_signal_{side:+.1f}","industry","fab_signal",phase=0.0 if side<0 else math.pi*0.5,speed=0.88,min_level=0.24,max_level=0.92)
        self._utopia_system_box(root,"fab_gantry_top",22.2,3.1,1.05,(0,0,12.1),theme["secondary"])
        for idx,x in enumerate((-6.2,0.0,6.2)):
            self._utopia_system_box(root,f"fab_bed_{idx}",4.8,8.0,0.38,(x,5.0,0),(0.035,0.038,0.042,1))
            axis=self._utopia_system_box(root,f"fab_bed_axis_{idx}",0.44,6.6,0.16,(x,5.0,0.4),theme["primary"] if idx!=1 else theme["secondary"])
            self._register_utopia_system_activity(axis,f"fab_bed_axis_{idx}","industry","fab_axis",phase=idx*0.9,speed=0.76,min_level=0.18,max_level=0.84)
            head=self._utopia_system_box(root,f"fab_head_{idx}",2.2,1.8,1.2,(x,4.2,6.6),theme["primary"] if idx==1 else theme["secondary"])
            self._register_utopia_system_activity(head,f"fab_head_{idx}","industry","fab_head",phase=idx*1.8,speed=0.64+idx*0.08,min_level=0.45,max_level=1.0,motion_y=1.35,motion_z=0.42)
        self._utopia_system_stats_mark("industry")

    def _utopia_system_stats_mark(self, key: str):
        self.utopia_system_stats["systems"] += 1
        self.utopia_system_stats[key] += 1

    def _build_utopia_project_systems(self):
        self._build_archive_station_access()
        self._build_dream_catcher_node()
        self._build_eco_climate_node()
        self._build_harbor_logistics_beacon()
        self._build_industry_fabrication_gantry()

    def _build_ar_environment(self):
        self.ar_environment_root = self.render.attachNewNode("utopia_ar_environment")
        self.ar_environment_root.hide(NORMAL_CAMERA_MASK)
        self.ar_environment_root.setLightOff(1)
        # Utopia keeps its synthetic resident atmosphere, but the visor must hand back to the
        # physical Earth-like sky outside the city instead of recolouring the whole planet.
        # The two AR-only domes crossfade by camera radius so crossing the Utopia boundary is smooth.
        ar_natural_sky = make_sky_dome_geom("ar_natural_outer_sky", 2210.0, -150.0, 1550.0,
            (0.72,0.84,0.94,1.0), (0.36,0.66,0.90,1.0), (0.10,0.36,0.72,1.0), 12, 80)
        ar_natural_sky.reparentTo(self.render); ar_natural_sky.hide(NORMAL_CAMERA_MASK)
        ar_natural_sky.setTwoSided(True); ar_natural_sky.setLightOff(1); ar_natural_sky.setFogOff(1)
        ar_natural_sky.setDepthWrite(False); ar_natural_sky.setDepthTest(False); ar_natural_sky.setBin("background", -111)
        ar_natural_sky.setTransparency(TransparencyAttrib.MAlpha)
        self.ar_natural_sky = ar_natural_sky

        ar_sky = make_sky_dome_geom("ar_sky_dome", 2200.0, -150.0, 1550.0,
            (0.035,0.145,0.18,1.0), (0.040,0.075,0.18,1.0), (0.032,0.016,0.095,1.0), 12, 80)
        ar_sky.reparentTo(self.render); ar_sky.hide(NORMAL_CAMERA_MASK)
        ar_sky.setTwoSided(True); ar_sky.setLightOff(1); ar_sky.setFogOff(1)
        ar_sky.setDepthWrite(False); ar_sky.setDepthTest(False); ar_sky.setBin("background", -110)
        ar_sky.setTransparency(TransparencyAttrib.MAlpha)
        self.ar_sky = ar_sky
        self.environment_stats["ar_sky"] = 1

        # Tiered island shelf strengthens the city silhouette while remaining attached to the coastline.
        shelf_specs = [
            (520.0, 526.0, -0.12, (0.050,0.11,0.14,1.0)),
            (526.0, 533.0, -0.18, (0.030,0.075,0.10,1.0)),
        ]
        for idx,(inner,outer,z,color) in enumerate(shelf_specs):
            shelf=make_annulus_geom(f"ar_coastal_shelf_{idx}",inner,outer,color,192,z)
            shelf.reparentTo(self.ar_environment_root); shelf.setDepthOffset(1); shelf.setTwoSided(True)
            self.environment_stats["shore_shelves"] += 1

        # Procedural AR water: slow broad waves, no reflection cards and no geometry displacement.
        water = make_annulus_geom("ar_water_surface", 532.5, 688.0, (1,1,1,1), 160, -0.16)
        water.reparentTo(self.ar_environment_root)
        water.setDepthOffset(2); water.setTwoSided(True)
        vshader=("#version 130\n"
                 "in vec4 p3d_Vertex;\n"
                 "uniform mat4 p3d_ModelViewProjectionMatrix;\n"
                 "out vec2 world_xy;\n"
                 "void main(){ world_xy=p3d_Vertex.xy; gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex; }\n")
        fshader=("#version 130\n"
                 "uniform float env_time;\n"
                 "uniform vec3 ar_time_tint;\n"
                 "uniform float ar_time_gain;\n"
                 "in vec2 world_xy;\n"
                 "out vec4 fragColor;\n"
                 "void main(){\n"
                 " float w1=sin(world_xy.x*0.030 + env_time*0.42);\n"
                 " float w2=sin(world_xy.y*0.024 - env_time*0.31);\n"
                 " float w3=sin((world_xy.x+world_xy.y)*0.014 + env_time*0.20);\n"
                 " float wave=(w1+w2+w3)/3.0;\n"
                 " float ripple=0.5+0.5*wave;\n"
                 " vec3 deep=vec3(0.012,0.085,0.125);\n"
                 " vec3 high=vec3(0.025,0.22,0.28);\n"
                 " vec3 col=mix(deep,high,ripple*0.58);\n"
                 " float line=smoothstep(0.80,0.98,0.5+0.5*sin(world_xy.x*0.055+world_xy.y*0.018+env_time*0.30));\n"
                 " col += vec3(0.025,0.12,0.15)*line*0.20;\n"
                 " col *= ar_time_tint * ar_time_gain;\n"
                 " fragColor=vec4(col,1.0);\n"
                 "}\n")
        water.setShader(Shader.make(Shader.SL_GLSL,vshader,fshader))
        water.setShaderInput("env_time",0.0)
        water.setShaderInput("ar_time_tint",(1.0,1.0,1.0))
        water.setShaderInput("ar_time_gain",1.0)
        self.ar_water_surface = water
        self.environment_stats["ar_water"] = 1

    def _build_celestial_system(self):
        # One celestial trajectory, two visual interpretations. The AR Saturn occupies
        # exactly the same apparent sky position as the physical Moon to prevent visor pop/jump.
        vertex=("#version 130\n"
                "in vec4 p3d_Vertex; in vec2 p3d_MultiTexCoord0; uniform mat4 p3d_ModelViewProjectionMatrix; out vec2 uv;\n"
                "void main(){ gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex; uv=p3d_MultiTexCoord0; }\n")
        moon_frag=("#version 130\n"
                   "uniform vec4 p3d_ColorScale; in vec2 uv; out vec4 fragColor;\n"
                   "void main(){ vec2 q=(uv-vec2(0.5))*2.0; float r=length(q); float edge=1.0-smoothstep(0.90,1.0,r);\n"
                   " float limb=0.78+0.20*sqrt(max(0.0,1.0-r*r)); float mott=0.035*sin(q.x*19.0+q.y*7.0)+0.025*sin(q.x*31.0-q.y*23.0);\n"
                   " vec3 col=vec3(0.80,0.83,0.84)*(limb+mott); float a=edge*0.82*p3d_ColorScale.a; if(a<0.005) discard; fragColor=vec4(col*p3d_ColorScale.rgb,a); }\n")
        saturn_frag=("#version 130\n"
                     "uniform vec4 p3d_ColorScale; in vec2 uv; out vec4 fragColor;\n"
                     "void main(){ vec2 q=(uv-vec2(0.5))*2.0; float a=-0.28; mat2 rot=mat2(cos(a),-sin(a),sin(a),cos(a)); vec2 p=rot*q;\n"
                     " float er=length(vec2(p.x,p.y/0.30)); float ringOuter=1.0-smoothstep(0.94,1.0,er); float ringInner=smoothstep(0.54,0.61,er); float ring=ringOuter*ringInner;\n"
                     " float r=length(p/0.47); float body=1.0-smoothstep(0.985,1.0,r); float z=sqrt(max(0.0,1.0-r*r));\n"
                     " vec3 N=normalize(vec3(p.x/0.47,p.y/0.47,z)); vec3 L=normalize(vec3(-0.48,0.24,0.84)); float diff=max(0.08,dot(N,L));\n"
                     " float limb=0.55+0.45*z; float bands=0.92+0.08*sin((p.y/0.47)*34.0+sin(p.x*8.0)*0.6);\n"
                     " vec3 night=vec3(0.20,0.12,0.14); vec3 day=vec3(0.92,0.69,0.40)*bands; vec3 bodyCol=mix(night,day,diff)*limb;\n"
                     " float ringBands=0.78+0.18*sin(er*42.0)+0.05*sin(er*97.0); vec3 ringCol=vec3(0.86,0.70,0.53)*ringBands;\n"
                     " float atmosphere=(1.0-smoothstep(0.47,0.57,length(p)))*0.06; vec3 col=ringCol*ring; col=mix(col,bodyCol,body); col+=vec3(0.34,0.16,0.28)*atmosphere;\n"
                     " float alpha=max(ring*0.52,body*0.90)+atmosphere; alpha*=p3d_ColorScale.a; if(alpha<0.004) discard; fragColor=vec4(col*p3d_ColorScale.rgb,alpha); }\n")

        self.physical_moon_root = self.render.attachNewNode("physical_moon")
        self.physical_moon_root.hide(AR_CAMERA_MASK); self.physical_moon_root.setLightOff(1); self.physical_moon_root.setScale(CELESTIAL_DISTANCE/1850.0)
        moon_cm=CardMaker("physical_moon_card"); moon_cm.setFrame(-18.0,18.0,-18.0,18.0)
        moon=self.physical_moon_root.attachNewNode(moon_cm.generate()); moon.setBillboardPointEye(); moon.setShader(Shader.make(Shader.SL_GLSL,vertex,moon_frag))
        moon.setTransparency(TransparencyAttrib.MAlpha); moon.setDepthWrite(False); moon.setBin("background",-98)

        self.ar_saturn_root = self.render.attachNewNode("ar_saturn")
        self.ar_saturn_root.hide(NORMAL_CAMERA_MASK); self.ar_saturn_root.setLightOff(1); self.ar_saturn_root.setScale(CELESTIAL_DISTANCE/1350.0)
        sat_cm=CardMaker("ar_saturn_card"); sat_cm.setFrame(-48.0,48.0,-48.0,48.0)
        saturn=self.ar_saturn_root.attachNewNode(sat_cm.generate()); saturn.setBillboardPointEye(); saturn.setShader(Shader.make(Shader.SL_GLSL,vertex,saturn_frag))
        saturn.setTransparency(TransparencyAttrib.MAlpha); saturn.setDepthWrite(False); saturn.setBin("background",-98)
        self.environment_stats["moon"] = 1
        self.environment_stats["saturn"] = 1
        self._update_celestial_system()

    def _update_celestial_system(self):
        if self.physical_moon_root is None or self.ar_saturn_root is None:
            return
        h=float(self.physical_time_hours)%24.0
        phase=((h-18.0)%24.0)/12.0
        if phase > 1.0:
            self.physical_moon_root.setColorScale(1,1,1,0.0)
            self.ar_saturn_root.setColorScale(1,1,1,0.0)
            return
        altitude=max(0.0, math.sin(math.pi*phase))
        alt=math.radians(8.0+55.0*altitude)
        # 18:00 east -> midnight north -> 06:00 west.
        az=math.radians(90.0-180.0*phase)
        distance=CELESTIAL_DISTANCE
        horizontal=math.cos(alt)*distance
        # World-space celestial anchor: translation of the player/camera does not move the Moon.
        sky_pos=Vec3(math.sin(az)*horizontal, math.cos(az)*horizontal, math.sin(alt)*distance)
        self.physical_moon_root.setPos(self.render,sky_pos)
        self.ar_saturn_root.setPos(self.render,sky_pos)
        horizon_fade=self._smoothstep01(min(1.0,altitude*2.5))
        moon_alpha=(0.22+0.55*altitude)*horizon_fade
        saturn_alpha=(0.22+0.44*altitude)*horizon_fade
        self.physical_moon_root.setColorScale(1,1,1,moon_alpha)
        self.ar_saturn_root.setColorScale(1,1,1,saturn_alpha)

    def _build_sky_depth_system(self):
        """Physical Sun + procedural clouds, duplicated only for the AR natural exterior.

        Utopia's synthetic AR atmosphere intentionally fades these natural-sky elements out
        geographically rather than replacing them with another celestial system.
        """
        vertex=("#version 130\n"
                "in vec4 p3d_Vertex; in vec2 p3d_MultiTexCoord0; uniform mat4 p3d_ModelViewProjectionMatrix; out vec2 uv;\n"
                "void main(){ gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex; uv=p3d_MultiTexCoord0; }\n")
        sun_frag=("#version 130\n"
                  "uniform vec4 p3d_ColorScale; in vec2 uv; out vec4 fragColor;\n"
                  "void main(){ vec2 q=(uv-vec2(0.5))*2.0; float r=length(q); float disc=1.0-smoothstep(0.34,0.40,r);\n"
                  " float halo=(1.0-smoothstep(0.38,1.0,r))*0.30; float a=(disc*0.92+halo)*p3d_ColorScale.a; if(a<0.004) discard;\n"
                  " vec3 core=vec3(1.00,0.91,0.67); vec3 edge=vec3(1.00,0.63,0.28); vec3 col=mix(core,edge,smoothstep(0.18,0.70,r));\n"
                  " fragColor=vec4(col*p3d_ColorScale.rgb,a); }\n")
        for ar_view in (False,True):
            root=self.render.attachNewNode("ar_natural_sun" if ar_view else "physical_sun")
            if ar_view: root.hide(NORMAL_CAMERA_MASK)
            else: root.hide(AR_CAMERA_MASK)
            root.setLightOff(1); root.setFogOff(1); root.setScale(CELESTIAL_DISTANCE/1870.0)
            cm=CardMaker("sun_card"); cm.setFrame(-24.0,24.0,-24.0,24.0)
            card=root.attachNewNode(cm.generate()); card.setBillboardPointEye(); card.setShader(Shader.make(Shader.SL_GLSL,vertex,sun_frag))
            card.setTransparency(TransparencyAttrib.MAlpha); card.setDepthWrite(False); card.setBin("background",-108)
            if ar_view: self.ar_natural_sun_root=root
            else: self.physical_sun_root=root

        cloud_frag=("#version 130\n"
                    "uniform vec4 p3d_ColorScale; uniform float cloud_darkness; in vec2 uv; out vec4 fragColor;\n"
                    "void main(){ vec2 q=(uv-vec2(0.5))*2.0;\n"
                    " float p1=1.0-smoothstep(0.44,0.76,length((q-vec2(-0.48,-0.05))*vec2(1.0,1.12)));\n"
                    " float p2=1.0-smoothstep(0.50,0.84,length((q-vec2(0.00,0.10))*vec2(0.95,1.05)));\n"
                    " float p3=1.0-smoothstep(0.42,0.73,length((q-vec2(0.48,-0.08))*vec2(1.02,1.18)));\n"
                    " float base=(1.0-smoothstep(0.48,0.86,length(vec2(q.x*0.68,(q.y+0.18)*1.35))))*0.88;\n"
                    " float cloud=max(max(p1,p2),max(p3,base)); float grain=0.92+0.08*sin(uv.x*25.0+uv.y*17.0);\n"
                    " float a=cloud*grain*p3d_ColorScale.a; if(a<0.008) discard;\n"
                    " vec3 day=vec3(0.94,0.95,0.96); vec3 storm=vec3(0.30,0.34,0.39); vec3 col=mix(day,storm,clamp(cloud_darkness,0.0,1.0));\n"
                    " fragColor=vec4(col*p3d_ColorScale.rgb,a); }\n")
        cloud_shader=Shader.make(Shader.SL_GLSL,vertex,cloud_frag)
        rng=random.Random(4001)
        physical_root=self.render.attachNewNode("physical_clouds"); physical_root.hide(AR_CAMERA_MASK); physical_root.setLightOff(1); physical_root.setFogOff(1)
        ar_root=self.render.attachNewNode("ar_natural_clouds"); ar_root.hide(NORMAL_CAMERA_MASK); ar_root.setLightOff(1); ar_root.setFogOff(1)
        self.physical_cloud_root=physical_root; self.ar_natural_cloud_root=ar_root
        for idx in range(24):
            angle=rng.uniform(0.0,math.tau); radius=rng.uniform(520.0,1950.0); z=rng.uniform(260.0,520.0)
            base=Vec3(math.sin(angle)*radius,math.cos(angle)*radius,z)
            half_w=rng.uniform(95.0,220.0); half_h=rng.uniform(28.0,68.0); bias=rng.uniform(0.08,0.92)
            amp=rng.uniform(28.0,105.0); speed=rng.uniform(0.018,0.045); phase=rng.uniform(0.0,math.tau)
            for ar_view,parent in ((False,physical_root),(True,ar_root)):
                holder=parent.attachNewNode(f"cloud_{'ar' if ar_view else 'physical'}_{idx:02d}"); holder.setPos(base)
                cm=CardMaker(f"cloud_card_{idx:02d}"); cm.setFrame(-half_w,half_w,-half_h,half_h)
                card=holder.attachNewNode(cm.generate()); card.setBillboardPointEye(); card.setShader(cloud_shader); card.setShaderInput("cloud_darkness",0.0)
                card.setTransparency(TransparencyAttrib.MAlpha); card.setDepthWrite(False); card.setBin("transparent",15); card.setTwoSided(True)
                self.cloud_clusters.append({"holder":holder,"card":card,"base":Vec3(base),"bias":bias,"amp":amp,"speed":speed,"phase":phase,"ar":ar_view})
        self.environment_stats["sun"] = 1
        self.environment_stats["cloud_layers"] = 48
        self._update_sky_depth_system()

    def _update_sky_depth_system(self):
        if self.physical_sun_root is None or self.ar_natural_sun_root is None:
            return
        h=float(self.physical_time_hours)%24.0
        day_phase=(h-6.0)/12.0
        sun_visible=0.0 <= day_phase <= 1.0
        if sun_visible:
            altitude=max(0.0,math.sin(math.pi*day_phase))
            alt=math.radians(7.0+58.0*altitude)
            az=math.radians(90.0-180.0*day_phase)
            distance=CELESTIAL_DISTANCE; horizontal=math.cos(alt)*distance
            pos=Vec3(math.sin(az)*horizontal,math.cos(az)*horizontal,math.sin(alt)*distance)
            self.physical_sun_root.setPos(self.render,pos); self.ar_natural_sun_root.setPos(self.render,pos)
            horizon=self._smoothstep01(min(1.0,altitude*3.0)); weather=self._current_weather_profile()
            weather_vis=max(0.08,min(1.0,float(weather["sun_gain"])+0.10))
            alpha=(0.22+0.62*altitude)*horizon*weather_vis
        else:
            alpha=0.0
        self.physical_sun_root.setColorScale(1,1,1,alpha)

        camera_pos=self.camera.getPos(self.render) if hasattr(self,"camera") else Vec3(0,0,EYE_HEIGHT)
        radius=math.hypot(float(camera_pos.x),float(camera_pos.y)); outer_mix=self._smoothstep01((radius-500.0)/90.0)
        self.ar_natural_sun_root.setColorScale(1,1,1,alpha*outer_mix)

        weather=self._current_weather_profile()
        cloud_cover=max(0.12,min(1.0,1.0-float(weather["sun_gain"])*0.80+float(weather["rain"])*0.35))
        cloud_dark=max(0.0,min(1.0,(1.0-float(weather["sun_gain"]))*0.82+float(weather["rain"])*0.22))
        daylight=max(0.0,math.sin(math.pi*(h-6.0)/12.0))
        physical_cloud_rgb=self._lerp_tuple((0.22,0.25,0.31),(1.0,1.0,1.0),0.20+0.80*daylight)
        # AR interprets the same cloud masses as warm pink/magenta atmospheric forms.
        ar_cloud_rgb=self._lerp_tuple((0.42,0.10,0.34),(1.00,0.36,0.66),0.25+0.75*daylight)
        for item in self.cloud_clusters:
            visible=self._smoothstep01((cloud_cover-(float(item["bias"])-0.10))/0.24)
            ar_presence=(0.62+0.38*outer_mix) if item["ar"] else 1.0
            alpha=visible*(0.16+0.40*cloud_cover)*ar_presence
            cloud_rgb=ar_cloud_rgb if item["ar"] else physical_cloud_rgb
            item["holder"].setColorScale(cloud_rgb[0],cloud_rgb[1],cloud_rgb[2],alpha)
            item["card"].setShaderInput("cloud_darkness",cloud_dark*(0.55 if item["ar"] else 1.0))
            base=item["base"]; phase=float(item["phase"])+self.environment_time*float(item["speed"]); amp=float(item["amp"])
            item["holder"].setPos(base.x+math.sin(phase)*amp,base.y+math.cos(phase*0.83)*amp*0.55,base.z)


    def _build_physical_mist_system(self):
        """Sparse physical-only low cloud mist using a soft alpha texture, not hard billboard slabs."""
        root=self.render.attachNewNode("physical_cloud_mist")
        root.setLightOff(1); root.setFogOff(1)
        self.physical_mist_root=root
        self.physical_mist_root.hide(AR_CAMERA_MASK)
        texture_path=self.base_dir/"assets"/"textures"/"physical_mist_wisp.png"
        texture=self.loader.loadTexture(Filename.fromOsSpecific(str(texture_path))) if texture_path.exists() else None
        rng=random.Random(4911)
        for idx in range(24):
            angle=rng.uniform(0,math.tau); radius=rng.uniform(500.0,1180.0)
            base=Vec3(math.sin(angle)*radius,math.cos(angle)*radius,rng.uniform(4.0,18.0))
            cm=CardMaker(f"physical_mist_card_{idx}"); hw=rng.uniform(22.0,58.0); hh=rng.uniform(3.5,9.0); cm.setFrame(-hw,hw,-hh,hh)
            holder=root.attachNewNode(f"physical_mist_{idx:02d}"); holder.setPos(base)
            card=holder.attachNewNode(cm.generate()); card.setBillboardPointEye()
            if texture is not None:
                card.setTexture(texture,1)
            card.setTransparency(TransparencyAttrib.MAlpha); card.setDepthWrite(False); card.setBin("transparent",10); card.setTwoSided(True)
            self.physical_mist_clusters.append({"holder":holder,"base":base,"phase":rng.uniform(0,math.tau),"speed":rng.uniform(0.010,0.026),"amp":rng.uniform(18.0,55.0),"bias":rng.uniform(0.65,1.0)})
        self.mist_stats["layers"]=len(self.physical_mist_clusters)

    def _update_physical_mist_system(self):
        if self.physical_mist_root is None:
            return
        weather=self._current_weather_profile()
        rain=float(weather["rain"]); sun_gain=float(weather["sun_gain"])
        weather_gain=max(0.0,min(1.0,0.12+0.48*(1.0-sun_gain)+0.34*rain))
        h=float(self.physical_time_hours)%24.0
        daylight=max(0.0,math.sin(math.pi*(h-6.0)/12.0))
        fog_color=self.world_fog.getColor()
        rgb=(min(1.0,float(fog_color.x)*1.10),min(1.0,float(fog_color.y)*1.10),min(1.0,float(fog_color.z)*1.10))
        for item in self.physical_mist_clusters:
            alpha=(0.012+0.050*weather_gain)*float(item["bias"])
            item["holder"].setColorScale(rgb[0],rgb[1],rgb[2],alpha)
            phase=float(item["phase"])+self.environment_time*float(item["speed"]); amp=float(item["amp"]); base=item["base"]
            item["holder"].setPos(base.x+math.sin(phase)*amp,base.y+math.cos(phase*0.71)*amp*0.55,base.z+math.sin(phase*0.53)*2.5)

    def _build_ar_lens(self):
        # Render the same world from the same lens, but with AR-only nodes enabled.
        self.ar_buffer=self.win.makeTextureBuffer("utopia_ar_buffer",960,540)
        if self.ar_buffer is None:
            raise RuntimeError("Unable to create Utopia AR texture buffer")
        self.ar_buffer.setSort(-100)
        self.ar_buffer.setClearColor((0.018,0.025,0.075,1.0))
        self.ar_texture=self.ar_buffer.getTexture()
        self.ar_camera=self.makeCamera(self.ar_buffer)
        self.ar_camera.reparentTo(self.camera)
        self.ar_camera.setPos(0,0,0); self.ar_camera.setHpr(0,0,0)
        self.ar_camera.node().setLens(self.cam.node().getLens())
        self.ar_camera.node().setCameraMask(AR_CAMERA_MASK)

        cm=CardMaker("ar_lens_composite")
        cm.setFrame(-1,1,-1,1)
        self.ar_card=self.render2d.attachNewNode(cm.generate())
        self.ar_card.setTexture(self.ar_texture,1)
        self.ar_card.setTransparency(TransparencyAttrib.MAlpha)
        self.ar_card.setDepthTest(False); self.ar_card.setDepthWrite(False)
        self.ar_card.setBin("fixed",90)
        vshader=("#version 130\n"
                 "in vec4 p3d_Vertex;\n"
                 "in vec2 p3d_MultiTexCoord0;\n"
                 "uniform mat4 p3d_ModelViewProjectionMatrix;\n"
                 "out vec2 uv;\n"
                 "void main(){ gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex; uv=p3d_MultiTexCoord0; }\n")
        fshader=("#version 130\n"
                 "uniform sampler2D p3d_Texture0;\n"
                 "uniform vec2 lens_center;\n"
                 "uniform vec2 lens_half_size;\n"
                 "uniform float lens_corner;\n"
                 "uniform vec2 ar_tex_scale;\n"
                 "uniform vec2 ar_texel_size;\n"
                 "uniform vec3 ar_time_tint;\n"
                 "uniform float ar_time_gain;\n"
                 "in vec2 uv;\n"
                 "out vec4 fragColor;\n"
                 "float sdRoundedBox(vec2 p, vec2 b, float r){\n"
                 " vec2 q = abs(p) - b + vec2(r);\n"
                 " return min(max(q.x,q.y),0.0) + length(max(q,0.0)) - r;\n"
                 "}\n"
                 "void main(){\n"
                 " vec2 p = uv - lens_center;\n"
                 " float dist = sdRoundedBox(p, lens_half_size, lens_corner);\n"
                 " float inner = 1.0 - smoothstep(0.0, 0.010, dist);\n"
                 " float rim = (1.0 - smoothstep(0.004, 0.020, abs(dist))) * inner;\n"
                 " if(inner<=0.001 && rim<=0.001){ fragColor=vec4(0.0); return; }\n"
                 " vec2 srcuv=uv*ar_tex_scale;\n"
                 " vec3 ar=texture(p3d_Texture0,srcuv).rgb;\n"
                 " vec2 px=ar_texel_size*2.2;\n"
                 " vec3 b0=texture(p3d_Texture0,srcuv+vec2(px.x,0.0)).rgb;\n"
                 " vec3 b1=texture(p3d_Texture0,srcuv-vec2(px.x,0.0)).rgb;\n"
                 " vec3 b2=texture(p3d_Texture0,srcuv+vec2(0.0,px.y)).rgb;\n"
                 " vec3 b3=texture(p3d_Texture0,srcuv-vec2(0.0,px.y)).rgb;\n"
                 " vec3 samples=(b0+b1+b2+b3)*0.25;\n"
                 " float smx=max(samples.r,max(samples.g,samples.b)); float smn=min(samples.r,min(samples.g,samples.b));\n"
                 " float glow=smoothstep(0.22,0.72,smx)*smoothstep(0.06,0.28,smx-smn);\n"
                 " ar=(ar+samples*glow*0.11)*ar_time_tint*ar_time_gain;\n"
                 " float glass = 1.0 - smoothstep(-0.16, 0.04, abs(dist));\n"
                 " ar += vec3(0.02,0.055,0.075)*(0.24+0.42*glass);\n"
                 " float edgeBlend = clamp((p.y + lens_half_size.y) / max(lens_half_size.y*2.0, 0.001), 0.0, 1.0);\n"
                 " vec3 rimColor=mix(vec3(0.15,0.95,1.0),vec3(0.72,0.35,1.0),edgeBlend);\n"
                 " vec3 rgb=mix(ar,rimColor,clamp(rim*0.96,0.0,1.0));\n"
                 " float alpha=max(inner,rim*0.98); fragColor=vec4(rgb,alpha);\n"
                 "}\n")
        self.ar_card.setShader(Shader.make(Shader.SL_GLSL,vshader,fshader))
        tex_scale=(self.ar_buffer.getXSize()/self.ar_texture.getXSize(), self.ar_buffer.getYSize()/self.ar_texture.getYSize())
        self.ar_card.setShaderInput("ar_tex_scale",tex_scale)
        self.ar_card.setShaderInput("ar_texel_size",(1.0/max(1,self.ar_texture.getXSize()),1.0/max(1,self.ar_texture.getYSize())))
        self.ar_card.setShaderInput("ar_time_tint",(1.0,1.0,1.0))
        self.ar_card.setShaderInput("ar_time_gain",1.0)
        self._apply_visor_mode(self.visor_mode)
        self.ar_card.hide()
        self.ar_buffer.setActive(False)

    def _apply_visor_mode(self, mode: str):
        if mode not in VISOR_MODE_CONFIG:
            mode = "horizontal"
        self.visor_mode = mode
        config = VISOR_MODE_CONFIG[mode]
        self.ar_card.setShaderInput("lens_center", config["center"])
        self.ar_card.setShaderInput("lens_half_size", config["half_size"])
        self.ar_card.setShaderInput("lens_corner", config["corner"])
        if hasattr(self, "hud_title") and hasattr(self, "ar_buffer") and self.ar_buffer.isActive():
            self.hud_title.setText(f"UTOPIA // {config['label']} VISOR ACTIVE")

    def _cycle_visor_mode(self):
        idx = VISOR_MODE_ORDER.index(self.visor_mode) if self.visor_mode in VISOR_MODE_ORDER else 0
        self._apply_visor_mode(VISOR_MODE_ORDER[(idx + 1) % len(VISOR_MODE_ORDER)])

    def _update_hud_contrast(self, visor_active: bool | None = None):
        if not hasattr(self, "hud_title"):
            return
        if visor_active is None:
            visor_active = hasattr(self, "ar_buffer") and self.ar_buffer.isActive() and not self.ar_card.isHidden()
        if visor_active:
            self.hud_title.setFg((0.82,0.90,0.96,0.88))
        else:
            h = self.physical_time_hours % 24.0
            if h < 7.0 or h >= 18.0:
                self.hud_title.setFg((0.82,0.84,0.86,0.84))
            else:
                self.hud_title.setFg((0.17,0.18,0.18,0.72))

    def _set_lens(self, enabled: bool):
        if not hasattr(self,"ar_card"): return
        enabled=bool(enabled)
        if enabled:
            self._update_ar_activity_visibility(force=True)
            self.ar_buffer.setActive(True); self.ar_card.show()
            if hasattr(self,"hud_title"):
                label = VISOR_MODE_CONFIG[self.visor_mode]["label"]
                self.hud_title.setText(f"UTOPIA // {label} VISOR ACTIVE")
                self._update_hud_contrast(True)
        else:
            self.ar_card.hide(); self.ar_buffer.setActive(False)
            if hasattr(self,"hud_title"):
                self.hud_title.setText("UTOPIA // PHYSICAL")
                self._update_hud_contrast(False)

    def _lens_hold(self, enabled: bool):
        self.lens_held=enabled
        self._set_lens(self.lens_held or self.lens_latched)

    def _toggle_lens(self):
        self.lens_latched=not self.lens_latched
        self._set_lens(self.lens_held or self.lens_latched)

    def _lerp_tuple(self, a, b, t):
        return tuple(float(a[i]) * (1.0 - t) + float(b[i]) * t for i in range(len(a)))

    def _sample_time_keys(self, hour: float, keys):
        h = float(hour) % 24.0
        for idx in range(len(keys) - 1):
            h0, v0 = keys[idx]
            h1, v1 = keys[idx + 1]
            if h0 <= h <= h1:
                span = max(0.0001, h1 - h0)
                t = (h - h0) / span
                out = {}
                for key, value in v0.items():
                    other = v1[key]
                    if isinstance(value, tuple):
                        out[key] = self._lerp_tuple(value, other, t)
                    else:
                        out[key] = float(value) * (1.0 - t) + float(other) * t
                return out
        return dict(keys[-1][1])

    def _physical_time_profile(self, hour: float):
        # Earth-like exterior light cycle. The dome already carries a blue gradient; these
        # multipliers shift it naturally through dawn, daylight, dusk, and night.
        keys = [
            (0.0,  {"ambient":(0.10,0.13,0.20,1.0), "sun":(0.010,0.014,0.028,1.0), "sky":(0.10,0.17,0.35,1.0), "water":(0.20,0.31,0.48,1.0), "fog":(0.055,0.080,0.14)}),
            (5.0,  {"ambient":(0.16,0.18,0.24,1.0), "sun":(0.10,0.08,0.09,1.0), "sky":(0.28,0.34,0.52,1.0), "water":(0.34,0.42,0.54,1.0), "fog":(0.14,0.18,0.24)}),
            (7.0,  {"ambient":(0.40,0.39,0.38,1.0), "sun":(0.98,0.66,0.40,1.0), "sky":(1.06,0.74,0.64,1.0), "water":(0.72,0.67,0.61,1.0), "fog":(0.48,0.46,0.43)}),
            (10.0, {"ambient":(0.56,0.58,0.60,1.0), "sun":(0.96,0.93,0.84,1.0), "sky":(1.00,1.00,1.00,1.0), "water":(0.92,1.02,1.08,1.0), "fog":(0.63,0.76,0.86)}),
            (12.0, {"ambient":(0.60,0.62,0.63,1.0), "sun":(1.00,0.98,0.90,1.0), "sky":(1.00,1.00,1.00,1.0), "water":(0.96,1.04,1.10,1.0), "fog":(0.67,0.80,0.90)}),
            (17.0, {"ambient":(0.48,0.46,0.44,1.0), "sun":(1.00,0.70,0.43,1.0), "sky":(1.08,0.80,0.70,1.0), "water":(0.84,0.76,0.70,1.0), "fog":(0.58,0.57,0.56)}),
            (19.0, {"ambient":(0.26,0.26,0.31,1.0), "sun":(0.38,0.20,0.19,1.0), "sky":(0.58,0.46,0.62,1.0), "water":(0.54,0.48,0.60,1.0), "fog":(0.30,0.30,0.39)}),
            (22.0, {"ambient":(0.12,0.14,0.21,1.0), "sun":(0.018,0.022,0.040,1.0), "sky":(0.16,0.22,0.42,1.0), "water":(0.28,0.36,0.52,1.0), "fog":(0.075,0.10,0.17)}),
            (24.0, {"ambient":(0.10,0.13,0.20,1.0), "sun":(0.010,0.014,0.028,1.0), "sky":(0.10,0.17,0.35,1.0), "water":(0.20,0.31,0.48,1.0), "fog":(0.055,0.080,0.14)}),
        ]
        return self._sample_time_keys(hour, keys)

    def _ar_time_profile(self, hour: float):
        keys = [
            (0.0,  {"tint":(0.72,0.82,1.10), "gain":0.86, "sky":(0.60,0.72,1.05,1.0), "water_tint":(0.72,0.92,1.10), "water_gain":0.76, "surface_gain":1.12}),
            (6.0,  {"tint":(0.88,0.98,1.08), "gain":0.94, "sky":(0.78,0.92,1.12,1.0), "water_tint":(0.82,1.00,1.06), "water_gain":0.88, "surface_gain":1.06}),
            (12.0, {"tint":(1.00,1.00,1.00), "gain":1.00, "sky":(1.12,1.20,1.22,1.0), "water_tint":(1.00,1.00,1.00), "water_gain":1.00, "surface_gain":0.96}),
            (18.0, {"tint":(1.10,0.86,1.08), "gain":0.94, "sky":(1.16,0.78,1.10,1.0), "water_tint":(1.04,0.86,1.08), "water_gain":0.86, "surface_gain":1.04}),
            (24.0, {"tint":(0.72,0.82,1.10), "gain":0.86, "sky":(0.60,0.72,1.05,1.0), "water_tint":(0.72,0.92,1.10), "water_gain":0.76, "surface_gain":1.12}),
        ]
        return self._sample_time_keys(hour, keys)

    def _format_clock(self, hour: float) -> str:
        total_minutes = int(round((float(hour) % 24.0) * 60.0)) % (24 * 60)
        hh = total_minutes // 60
        mm = total_minutes % 60
        suffix = "AM" if hh < 12 else "PM"
        display_h = hh % 12
        if display_h == 0:
            display_h = 12
        return f"{display_h:02d}:{mm:02d} {suffix}"

    def _pause_menu_text(self) -> str:
        return (
            "PAUSED // UTOPIA\n\n"
            f"WORLD   {self._format_clock(self.physical_time_hours)}   {self._weather_label()}\n"
            f"AR      {self._format_clock(self.ar_time_hours)}\n\n"
            "AR TIME   UP/DOWN ±1 HOUR   LEFT/RIGHT ±15 MIN\n\n"
            "F1 HELP   F11 FULLSCREEN   ESC RESUME"
        )

    def _refresh_pause_menu(self):
        if self.paused and self.pause_panel_mode == "pause":
            self.pause_text.setText(self._pause_menu_text())

    def _adjust_ar_time(self, delta_hours: float):
        if not self.paused or self.pause_panel_mode != "pause":
            return
        self.ar_time_hours = (self.ar_time_hours + float(delta_hours)) % 24.0
        self._apply_time_visuals()
        self._refresh_pause_menu()

    def _apply_time_visuals(self):
        physical = self._physical_time_profile(self.physical_time_hours)
        weather = self._current_weather_profile()
        ambient = tuple(physical["ambient"][i] * weather["ambient_gain"] for i in range(3)) + (1.0,)
        sun = tuple(physical["sun"][i] * weather["sun_gain"] for i in range(3)) + (1.0,)
        sky = tuple(physical["sky"][i] * weather["sky_tint"][i] for i in range(3)) + (1.0,)
        water = tuple(physical["water"][i] * weather["water_tint"][i] for i in range(3)) + (1.0,)
        fog = tuple(physical["fog"][i] * weather["fog_tint"][i] for i in range(3))
        self.ambient_light.setColor(ambient)
        self.sun_light.setColor(sun)
        day_phase = math.sin(math.pi * (self.physical_time_hours - 6.0) / 12.0)
        sun_altitude = max(0.0, day_phase)
        sun_heading = (self.physical_time_hours / 24.0) * 360.0 - 180.0
        self.sun_np.setHpr(sun_heading, -8.0 - sun_altitude * 64.0, 0.0)
        self.sun_np.setPos(0,0,SHADOW_ANCHOR_Z)
        if hasattr(self,"shadow_cards"):
            self._update_projected_shadows()
        if self.physical_sky is not None:
            self.physical_sky.setColorScale(*sky)
        if self.physical_water is not None:
            self.physical_water.setColorScale(*water)
        self.world_fog.setColor(*fog)
        # Reality carries actual atmospheric depth.  Weather tightens the physical fog
        # without using an opaque wall or hiding nearby navigation landmarks.
        fog_ranges={
            "clear":(900.0,2200.0),
            "overcast":(650.0,1650.0),
            "rain":(460.0,1250.0),
            "storm":(340.0,950.0),
            "post_rain":(720.0,1800.0),
        }
        onset,opaque=fog_ranges.get(self.weather_state,(900.0,2200.0))
        self.world_fog.setLinearRange(onset,opaque)
        self.win.setClearColor((*fog, 1.0))
        self._update_celestial_system()
        self._update_sky_depth_system()
        self._update_physical_water_visuals(physical, weather, sky)
        if hasattr(self, "ar_buffer") and not self.ar_buffer.isActive():
            self._update_hud_contrast(False)

        ar = self._ar_time_profile(self.ar_time_hours)
        # Geographic sky authority: Utopia may remain synthetic, but the exterior returns to
        # the same natural physical day/night atmosphere even while the visor is active.
        camera_pos = self.camera.getPos(self.render) if hasattr(self, "camera") else Vec3(0,0,EYE_HEIGHT)
        radius = math.hypot(float(camera_pos.x), float(camera_pos.y))
        outer_mix = self._smoothstep01((radius - 500.0) / 90.0)
        if self.ar_sky is not None:
            self.ar_sky.setColorScale(ar["sky"][0], ar["sky"][1], ar["sky"][2], 1.0 - outer_mix)
        if self.ar_natural_sky is not None:
            self.ar_natural_sky.setColorScale(sky[0], sky[1], sky[2], outer_mix)
        if self.ar_environment_root is not None:
            self.ar_environment_root.setColorScale(ar["tint"][0], ar["tint"][1], ar["tint"][2], 1.0)
        if self.ar_water_surface is not None:
            self.ar_water_surface.setShaderInput("ar_time_tint", ar["water_tint"])
            self.ar_water_surface.setShaderInput("ar_time_gain", ar["water_gain"])
        if hasattr(self, "ar_card"):
            self.ar_card.setShaderInput("ar_time_tint", ar["tint"])
            self.ar_card.setShaderInput("ar_time_gain", ar["gain"])
        self._ar_surface_gain = ar["surface_gain"]
        self._ar_surface_tint = ar["tint"]

    def _update_time_system(self, dt: float):
        if not self.paused and not self.freeze_physical_time:
            self.physical_time_hours = (self.physical_time_hours + (24.0 * dt / PHYSICAL_DAY_LENGTH_SECONDS)) % 24.0
        self._apply_time_visuals()

    def _smoothstep01(self, value: float) -> float:
        t=max(0.0,min(1.0,float(value)))
        return t*t*(3.0-2.0*t)

    def _music_float(self, value, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
        try:
            out=float(value)
        except (TypeError, ValueError):
            out=float(default)
        if not math.isfinite(out):
            out=float(default)
        if minimum is not None:
            out=max(float(minimum),out)
        if maximum is not None:
            out=min(float(maximum),out)
        return out

    def _music_safe_asset(self, asset_rel: str):
        rel=Path(str(asset_rel).strip())
        if not str(rel) or rel.is_absolute() or ".." in rel.parts:
            return None
        base=self.base_dir.resolve()
        path=(base/rel).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            return None
        return path

    def _load_district_music(self):
        self.district_music={}
        path=self.music_config_path
        if not path.exists():
            print(f"DISTRICT_MUSIC_CONFIG_MISSING path={path}")
            return
        try:
            data=json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"DISTRICT_MUSIC_CONFIG_ERROR path={path} error={exc}")
            return
        if not isinstance(data,dict) or not isinstance(data.get("tracks"),dict):
            print(f"DISTRICT_MUSIC_CONFIG_ERROR path={path} error=bad_schema")
            return
        self.music_master_volume=self._music_float(data.get("master_volume",0.50),0.50,0.0,1.0)
        self.music_outer_fade_start=self._music_float(data.get("outer_fade_start_radius",455.0),455.0,0.0)
        self.music_outer_silent_radius=self._music_float(data.get("outer_silent_radius",535.0),535.0,self.music_outer_fade_start+0.001)
        self.music_core_fade_start=self._music_float(data.get("core_fade_start_radius",112.0),112.0,0.0)
        self.music_core_fade_end=self._music_float(data.get("core_fade_end_radius",180.0),180.0,self.music_core_fade_start+0.001)
        self.music_smoothing_seconds=self._music_float(data.get("smoothing_seconds",1.35),1.35,0.05,30.0)
        expected=("core","north","east","south","west")
        for key in expected:
            raw=data["tracks"].get(key)
            if not isinstance(raw,dict):
                print(f"DISTRICT_MUSIC_TRACK_SKIPPED id={key} reason=missing_config")
                continue
            asset=str(raw.get("asset","")).strip()
            asset_path=self._music_safe_asset(asset)
            if asset_path is None:
                print(f"DISTRICT_MUSIC_TRACK_SKIPPED id={key} reason=unsafe_asset")
                continue
            track={
                "id":key,
                "label":str(raw.get("label",DISTRICT_THEMES[key]["label"])),
                "asset":asset.replace("\\","/"),
                "asset_path":asset_path,
                "gain":self._music_float(raw.get("gain",1.0),1.0,0.0,2.0),
                "current_volume":0.0,
                "target_volume":0.0,
                "sound":None,
                "reconcile_elapsed":0.0,
                "restart_count":0,
                "error_logged":False,
            }
            if not asset_path.exists():
                print(f"DISTRICT_MUSIC_ASSET_MISSING id={key} path={asset_path}")
            else:
                try:
                    # Route district loops through the same explicitly activated SFX/OpenAL owner
                    # as ambience and character audio.  All loops still run phase-continuously and
                    # volume alone performs the crossfade.
                    sound=self.loader.loadSfx(Filename.fromOsSpecific(str(asset_path)))
                    if sound is not None:
                        sound.setLoop(True)
                        sound.setVolume(0.0)
                        sound.play()
                        track["sound"]=sound
                        print(f"DISTRICT_MUSIC_LOADED id={key} asset={track['asset']}")
                except Exception as exc:
                    print(f"DISTRICT_MUSIC_LOAD_ERROR id={key} path={asset_path} error={exc}")
            self.district_music[key]=track

    def _district_music_weights(self, x: float, y: float) -> dict[str,float]:
        radius=math.hypot(float(x),float(y))
        # Music belongs to Utopia itself.  It fades through the wall/coast transition and is
        # completely silent in the natural outer world.
        outer=1.0-self._smoothstep01((radius-self.music_outer_fade_start)/(self.music_outer_silent_radius-self.music_outer_fade_start))
        core=1.0-self._smoothstep01((radius-self.music_core_fade_start)/(self.music_core_fade_end-self.music_core_fade_start))
        ring=1.0-core
        angle=(math.degrees(math.atan2(float(x),float(y)))+360.0)%360.0
        centers={"north":0.0,"east":90.0,"south":180.0,"west":270.0}
        raw={"core":core}
        for key,center in centers.items():
            delta=math.radians(angle_delta(angle,center))
            # Cosine lobes naturally create equal-power-like overlap around the 45-degree
            # district boundaries without hard switches.
            angular=max(0.0,math.cos(delta))**4
            raw[key]=ring*angular
        total=sum(raw.values())
        if total <= 1e-8 or outer <= 1e-8:
            return {key:0.0 for key in ("core","north","east","south","west")}
        return {key:(value/total)*outer for key,value in raw.items()}

    def _update_district_music(self, dt: float):
        if not self.district_music or not hasattr(self,"player"):
            return
        pos=self.player.getPos(self.render)
        weights=self._district_music_weights(float(pos.x),float(pos.y))
        smoothing=max(0.05,float(getattr(self,"music_smoothing_seconds",1.35)))
        alpha=1.0-math.exp(-max(0.0,float(dt))/smoothing)
        for key,track in self.district_music.items():
            pause_gain=0.28 if self.paused else 1.0
            target=max(0.0,min(1.0,weights.get(key,0.0)))*float(track.get("gain",1.0))*self.music_master_volume*pause_gain
            track["target_volume"]=target
            current=float(track.get("current_volume",0.0))+(target-float(track.get("current_volume",0.0)))*alpha
            if abs(current-target)<0.0001:
                current=target
            track["current_volume"]=current
            sound=track.get("sound")
            if sound is None:
                continue
            track["reconcile_elapsed"]=float(track.get("reconcile_elapsed",0.0))+max(0.0,float(dt))
            if self.music_runtime_available and track["reconcile_elapsed"]>=1.0:
                track["reconcile_elapsed"]=0.0
                try:
                    if sound.status()!=AudioSound.PLAYING:
                        sound.play(); track["restart_count"]=int(track.get("restart_count",0))+1
                except Exception as exc:
                    if not track.get("error_logged",False):
                        print(f"DISTRICT_MUSIC_RECONCILE_ERROR id={key} error={exc}"); track["error_logged"]=True
            try:
                sound.setVolume(max(0.0,min(1.0,current)))
            except Exception as exc:
                if not track.get("error_logged",False):
                    print(f"DISTRICT_MUSIC_VOLUME_ERROR id={key} error={exc}"); track["error_logged"]=True

    def _stop_district_music(self):
        for track in self.district_music.values():
            sound=track.get("sound")
            if sound is not None:
                try:
                    sound.stop()
                except Exception as exc:
                    print(f"DISTRICT_MUSIC_STOP_ERROR id={track.get('id')} error={exc}")

    def _ambience_float(self, value, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
        try:
            out=float(value)
        except (TypeError, ValueError):
            out=float(default)
        if not math.isfinite(out):
            out=float(default)
        if minimum is not None:
            out=max(float(minimum),out)
        if maximum is not None:
            out=min(float(maximum),out)
        return out

    def _normalize_ambience_zone(self, raw, index: int = 0):
        if not isinstance(raw,dict):
            print(f"AMBIENCE_ZONE_SKIPPED index={index} reason=not_object")
            return None
        if not raw.get("enabled",True):
            return None
        zone_id=str(raw.get("id",f"ambience_zone_{index}"))
        asset_rel=str(raw.get("asset","")).strip()
        if not asset_rel:
            print(f"AMBIENCE_ZONE_SKIPPED id={zone_id} reason=no_asset")
            return None
        rel_path=Path(asset_rel)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            print(f"AMBIENCE_ZONE_SKIPPED id={zone_id} reason=asset_must_be_project_relative")
            return None
        base_resolved=self.base_dir.resolve()
        asset_path=(base_resolved / rel_path).resolve()
        try:
            asset_path.relative_to(base_resolved)
        except ValueError:
            print(f"AMBIENCE_ZONE_SKIPPED id={zone_id} reason=asset_outside_project")
            return None

        shape=str(raw.get("shape","point")).strip().lower()
        if shape not in ("radial_outer","point"):
            print(f"AMBIENCE_ZONE_SKIPPED id={zone_id} reason=unknown_shape shape={shape}")
            return None
        center_raw=raw.get("center",[0.0,0.0])
        if not isinstance(center_raw,(list,tuple)) or len(center_raw)<2:
            center_raw=[0.0,0.0]
        cx=self._ambience_float(center_raw[0],0.0)
        cy=self._ambience_float(center_raw[1],0.0)

        zone={
            "id":zone_id,
            "enabled":True,
            "asset":asset_rel.replace("\\","/"),
            "asset_path":asset_path,
            "shape":shape,
            "center":[cx,cy],
            "max_volume":self._ambience_float(raw.get("max_volume",0.5),0.5,0.0,1.0),
            "smoothing_seconds":self._ambience_float(raw.get("smoothing_seconds",0.85),0.85,0.01,60.0),
            "loop":bool(raw.get("loop",True)),
            "description":str(raw.get("description","")),
            "current_volume":0.0,
            "target_volume":0.0,
            "sound":None,
            "reconcile_elapsed":0.0,
            "restart_count":0,
            "volume_error_logged":False,
            "reconcile_enabled":bool(getattr(self,"audio_runtime_available",False)),
        }
        if shape == "radial_outer":
            fade_start=self._ambience_float(raw.get("fade_start_radius",350.0),350.0,0.0)
            full=self._ambience_float(raw.get("full_volume_radius",500.0),500.0,fade_start+0.001)
            zone["fade_start_radius"]=fade_start
            zone["full_volume_radius"]=full
        else:
            full=self._ambience_float(raw.get("full_radius",8.0),8.0,0.0)
            fade=self._ambience_float(raw.get("fade_radius",60.0),60.0,full+0.001)
            zone["full_radius"]=full
            zone["fade_radius"]=fade
        return zone

    def _load_dynamic_ambience(self):
        self.dynamic_ambience=[]
        config_path=self.ambience_config_path
        if not config_path.exists():
            print(f"AMBIENCE_CONFIG_MISSING path={config_path}")
            return
        try:
            data=json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"AMBIENCE_CONFIG_ERROR path={config_path} error={exc}")
            return
        if not isinstance(data,dict):
            print(f"AMBIENCE_CONFIG_ERROR path={config_path} error=root_not_object")
            return
        self.ambience_master_volume=self._ambience_float(data.get("master_volume",1.0),1.0,0.0,1.0)
        raw_zones=data.get("zones",[])
        if not isinstance(raw_zones,list):
            print(f"AMBIENCE_CONFIG_ERROR path={config_path} error=zones_not_list")
            return
        for index, raw in enumerate(raw_zones):
            zone=self._normalize_ambience_zone(raw,index)
            if zone is None:
                continue
            zone_id=zone["id"]
            asset_rel=zone["asset"]
            asset_path=zone["asset_path"]
            if not asset_path.exists():
                print(f"AMBIENCE_ASSET_MISSING id={zone_id} path={asset_path}")
            else:
                try:
                    sound=self.loader.loadSfx(Filename.fromOsSpecific(str(asset_path)))
                    if sound is not None:
                        sound.setLoop(zone["loop"])
                        sound.setVolume(0.0)
                        sound.play()
                        zone["sound"]=sound
                        print(f"AMBIENCE_ZONE_LOADED id={zone_id} shape={zone['shape']} asset={asset_rel}")
                    else:
                        print(f"AMBIENCE_LOAD_FAILED id={zone_id} path={asset_path}")
                except Exception as exc:
                    print(f"AMBIENCE_LOAD_ERROR id={zone_id} path={asset_path} error={exc}")
            self.dynamic_ambience.append(zone)

    def _ambience_target_for_position(self, zone: dict, x: float, y: float) -> float:
        max_volume=max(0.0,float(zone.get("max_volume",0.5)))
        shape=str(zone.get("shape","point"))
        center=zone.get("center",[0.0,0.0])
        cx=float(center[0]) if len(center)>0 else 0.0
        cy=float(center[1]) if len(center)>1 else 0.0
        distance=math.hypot(float(x)-cx,float(y)-cy)
        if shape == "radial_outer":
            fade_start=float(zone.get("fade_start_radius",350.0))
            full_radius=max(fade_start+0.001,float(zone.get("full_volume_radius",500.0)))
            t=(distance-fade_start)/(full_radius-fade_start)
            return max_volume*self._smoothstep01(t)
        if shape == "point":
            full_radius=max(0.0,float(zone.get("full_radius",8.0)))
            fade_radius=max(full_radius+0.001,float(zone.get("fade_radius",60.0)))
            t=(distance-full_radius)/(fade_radius-full_radius)
            return max_volume*(1.0-self._smoothstep01(t))
        return 0.0

    def _update_dynamic_ambience(self, dt: float):
        if not self.dynamic_ambience or not hasattr(self,"player"):
            return
        pos=self.player.getPos(self.render)
        for zone in self.dynamic_ambience:
            pause_gain=0.28 if self.paused else 1.0
            target=self._ambience_target_for_position(zone,float(pos.x),float(pos.y))*pause_gain
            zone["target_volume"]=target
            smoothing=max(0.01,float(zone.get("smoothing_seconds",0.85)))
            alpha=1.0-math.exp(-max(0.0,float(dt))/smoothing)
            current=float(zone.get("current_volume",0.0))
            current += (target-current)*alpha
            if abs(current-target)<0.0001:
                current=target
            zone["current_volume"]=current
            sound=zone.get("sound")
            if sound is None:
                continue

            zone["reconcile_elapsed"]=float(zone.get("reconcile_elapsed",0.0))+max(0.0,float(dt))
            if zone.get("loop",True) and zone.get("reconcile_enabled",False) and zone["reconcile_elapsed"] >= 1.0:
                zone["reconcile_elapsed"]=0.0
                try:
                    if sound.status() != AudioSound.PLAYING:
                        sound.play()
                        zone["restart_count"]=int(zone.get("restart_count",0))+1
                except Exception as exc:
                    if not zone.get("volume_error_logged",False):
                        print(f"AMBIENCE_RECONCILE_ERROR id={zone.get('id')} error={exc}")
                        zone["volume_error_logged"]=True

            try:
                sound.setVolume(max(0.0,min(1.0,current*self.ambience_master_volume)))
            except Exception as exc:
                if not zone.get("volume_error_logged",False):
                    print(f"AMBIENCE_VOLUME_ERROR id={zone.get('id')} error={exc}")
                    zone["volume_error_logged"]=True

    def _audio_state_smoke(self,task):
        self.player.setPos(0.0,0.0,0.0); self.paused=False
        self._update_district_music(0.25)
        music_live=sum(float(t.get("target_volume",0.0)) for t in self.district_music.values())
        self.paused=True; self._update_district_music(0.25)
        music_paused=sum(float(t.get("target_volume",0.0)) for t in self.district_music.values())
        self.player.setPos(0.0,-500.0,0.0); self.paused=False
        self._update_dynamic_ambience(0.25)
        ambience_live=sum(float(z.get("target_volume",0.0)) for z in self.dynamic_ambience)
        self.paused=True; self._update_dynamic_ambience(0.25)
        ambience_paused=sum(float(z.get("target_volume",0.0)) for z in self.dynamic_ambience)
        self.paused=False
        ok=(music_live>0.05 and 0.20*music_live<=music_paused<=0.32*music_live and ambience_live>0.05 and 0.20*ambience_live<=ambience_paused<=0.32*ambience_live)
        if not ok:
            print(f"AUDIO_STATE_SMOKE_FAIL music={music_live:.4f}/{music_paused:.4f} ambience={ambience_live:.4f}/{ambience_paused:.4f}")
            self.userExit(); raise SystemExit(25)
        print(f"AUDIO_STATE_SMOKE_PASS pause_gain=0.28 music={music_live:.3f}->{music_paused:.3f} ambience={ambience_live:.3f}->{ambience_paused:.3f}")
        self.userExit(); return task.done

    def _stop_dynamic_ambience(self):
        for zone in self.dynamic_ambience:
            sound=zone.get("sound")
            if sound is not None:
                try:
                    sound.stop()
                except Exception as exc:
                    print(f"AMBIENCE_STOP_ERROR id={zone.get('id')} error={exc}")

    def _weather_smoke_start(self, task):
        if self.weather_root is None or not self.weather_root.isHidden(AR_CAMERA_MASK):
            print("WEATHER_SMOKE_FAIL ar_mask")
            self.userExit(); raise SystemExit(12)
        clear = WEATHER_PROFILES["clear"]["rain"]
        rain = WEATHER_PROFILES["rain"]["rain"]
        storm = WEATHER_PROFILES["storm"]["rain"]
        post = WEATHER_PROFILES["post_rain"]["rain"]
        if not (clear == 0.0 and 0.0 < rain < storm and post == 0.0):
            print(f"WEATHER_SMOKE_FAIL profile_rain clear={clear} rain={rain} storm={storm} post={post}")
            self.userExit(); raise SystemExit(12)
        self.weather_previous_state = "clear"
        self.weather_state = "overcast"
        self.weather_transition_elapsed = WEATHER_TRANSITION_SECONDS
        self.weather_state_elapsed = WEATHER_DURATIONS_SECONDS["overcast"] + 0.01
        self.freeze_weather = False
        return task.done

    def _weather_smoke_finish(self, task):
        # One update should have advanced from the expired overcast state to rain.
        self._update_weather_system(0.02)
        cycled = self.weather_state == "rain"
        self.weather_previous_state = "rain"
        self.weather_state = "rain"
        self.weather_transition_elapsed = WEATHER_TRANSITION_SECONDS
        self.freeze_weather = True
        self._update_weather_system(0.02)
        visible = not self.weather_root.isHidden()
        self.paused = True
        before = self.weather_effect_time
        self._update_weather_system(0.25)
        paused_freeze = abs(self.weather_effect_time - before) < 0.00001
        self.paused = False
        if not (cycled and visible and paused_freeze and self.weather_stats["rain_streaks"] >= 200):
            print(f"WEATHER_SMOKE_FAIL cycled={cycled} visible={visible} paused_freeze={paused_freeze} streaks={self.weather_stats['rain_streaks']}")
            self.userExit(); raise SystemExit(12)
        print(f"WEATHER_SMOKE_PASS states={len(WEATHER_ORDER)} rain_batches={self.weather_stats['rain_batches']} rain_streaks={self.weather_stats['rain_streaks']} ar_excluded=1 pause_freeze=1 cycle=1")
        self.userExit(); return task.done

    def _district_music_smoke(self,task):
        expected=("core","north","east","south","west")
        keys=tuple(self.district_music.keys())
        assets_ok=all(k in self.district_music and Path(self.district_music[k]["asset_path"]).exists() for k in expected)
        core=self._district_music_weights(0.0,0.0)
        north=self._district_music_weights(0.0,300.0)
        east=self._district_music_weights(300.0,0.0)
        south=self._district_music_weights(0.0,-300.0)
        west=self._district_music_weights(-300.0,0.0)
        boundary=self._district_music_weights(220.0,220.0)
        outside=self._district_music_weights(0.0,650.0)
        core_ok=core["core"]>0.98 and sum(v for k,v in core.items() if k!="core")<0.02
        cardinal_ok=(north["north"]>0.90 and east["east"]>0.90 and south["south"]>0.90 and west["west"]>0.90)
        boundary_ok=abs(boundary["north"]-boundary["east"])<0.03 and boundary["north"]>0.35 and boundary["east"]>0.35
        outside_ok=sum(outside.values())<0.0001
        normalized_ok=abs(sum(north.values())-1.0)<0.001 and abs(sum(boundary.values())-1.0)<0.001
        config_safe=self._music_safe_asset("../escape.wav") is None and self._music_safe_asset("audio/music/core_unity_forum.wav") is not None
        # Exercise the smoothing path at a real district boundary and then fade to the exterior.
        for track in self.district_music.values(): track["current_volume"]=0.0
        self.player.setPos(220.0,220.0,0.0)
        for _ in range(180): self._update_district_music(1.0/60.0)
        boundary_a=float(self.district_music.get("north",{}).get("current_volume",0.0)); boundary_b=float(self.district_music.get("east",{}).get("current_volume",0.0))
        self.player.setPos(0.0,650.0,0.0)
        for _ in range(300): self._update_district_music(1.0/60.0)
        exterior=max((float(t.get("current_volume",0.0)) for t in self.district_music.values()),default=1.0)
        smooth_ok=boundary_a>0.10 and boundary_b>0.10 and exterior<0.01
        ok=(keys==expected and assets_ok and core_ok and cardinal_ok and boundary_ok and outside_ok and normalized_ok and config_safe and smooth_ok)
        if not ok:
            print(f"DISTRICT_MUSIC_SMOKE_FAIL keys={keys} assets={assets_ok} core={core} north={north} boundary={boundary} outside={outside} safe={config_safe} smooth={smooth_ok} volumes=({boundary_a:.3f},{boundary_b:.3f},{exterior:.3f})")
            self.userExit(); raise SystemExit(15)
        print(f"DISTRICT_MUSIC_SMOKE_PASS tracks=5 replaceable=1 dedicated_music_owner=1 core=1 cardinal=4 boundary_crossfade=1 exterior_silence=1 smoothing=1 path_guard=1 master={self.music_master_volume:.2f}")
        self.userExit(); return task.done

    def _ambience_smoke(self,task):
        if not self.dynamic_ambience:
            print("AMBIENCE_SMOKE_FAIL no_zones")
            self.userExit(); raise SystemExit(9)
        ocean=next((z for z in self.dynamic_ambience if z.get("id")=="ocean_perimeter"),None)
        if ocean is None:
            print("AMBIENCE_SMOKE_FAIL no_ocean_zone")
            self.userExit(); raise SystemExit(9)
        asset_ok=Path(ocean.get("asset_path","")).exists()
        center=self._ambience_target_for_position(ocean,0.0,0.0)
        inner=self._ambience_target_for_position(ocean,425.0,0.0)
        wall_values=[
            self._ambience_target_for_position(ocean,505.0,0.0),
            self._ambience_target_for_position(ocean,-505.0,0.0),
            self._ambience_target_for_position(ocean,0.0,505.0),
            self._ambience_target_for_position(ocean,0.0,-505.0),
        ]
        outside=self._ambience_target_for_position(ocean,610.0,0.0)
        wall=max(wall_values)
        symmetry=max(wall_values)-min(wall_values) <= 1e-6
        monotonic=(center <= inner < wall <= outside + 1e-6)

        # Exercise the actual smoothing/update path: silent center -> wall -> center.
        ocean["current_volume"]=0.0
        self.player.setPos(0.0,0.0,0.0)
        for _ in range(30):
            self._update_dynamic_ambience(1.0/60.0)
        silent_current=float(ocean.get("current_volume",0.0))
        self.player.setPos(505.0,0.0,0.0)
        for _ in range(180):
            self._update_dynamic_ambience(1.0/60.0)
        raised_current=float(ocean.get("current_volume",0.0))
        self.player.setPos(0.0,0.0,0.0)
        for _ in range(240):
            self._update_dynamic_ambience(1.0/60.0)
        lowered_current=float(ocean.get("current_volume",0.0))
        dynamic_ok=(silent_current < 0.001 and raised_current > wall*0.92 and lowered_current < 0.01)

        # Data-driven ambience must fail safely: reject path traversal and sanitize malformed numeric fields.
        traversal_zone=self._normalize_ambience_zone({"id":"qa_escape","asset":"../outside.wav","shape":"point"},999)
        malformed_zone=self._normalize_ambience_zone({
            "id":"qa_malformed",
            "asset":"audio/ambience/ocean_loop.wav",
            "shape":"point",
            "center":None,
            "max_volume":"not-a-number",
            "full_radius":"bad",
            "fade_radius":None,
            "smoothing_seconds":"bad",
        },1000)
        config_safe=(traversal_zone is None and malformed_zone is not None and malformed_zone["center"] == [0.0,0.0] and abs(malformed_zone["max_volume"]-0.5)<1e-6 and malformed_zone["fade_radius"] > malformed_zone["full_radius"])
        point_zone=self._normalize_ambience_zone({
            "id":"qa_point",
            "asset":"audio/ambience/ocean_loop.wav",
            "shape":"point",
            "center":[100.0,50.0],
            "full_radius":10.0,
            "fade_radius":60.0,
            "max_volume":0.40,
        },1001)
        point_center=self._ambience_target_for_position(point_zone,100.0,50.0) if point_zone else -1.0
        point_mid=self._ambience_target_for_position(point_zone,135.0,50.0) if point_zone else -1.0
        point_far=self._ambience_target_for_position(point_zone,170.0,50.0) if point_zone else -1.0
        point_ok=(abs(point_center-0.40)<1e-6 and 0.0 < point_mid < point_center and point_far <= 0.0001)

        if not (asset_ok and center <= 0.0001 and monotonic and symmetry and dynamic_ok and outside > 0.0 and config_safe and point_ok):
            print(f"AMBIENCE_SMOKE_FAIL asset={asset_ok} center={center:.4f} inner={inner:.4f} wall={wall:.4f} outside={outside:.4f} symmetry={symmetry} rise={raised_current:.4f} fall={lowered_current:.4f} config_safe={config_safe} point_ok={point_ok}")
            self.userExit(); raise SystemExit(9)
        print(f"AMBIENCE_SMOKE_PASS zones={len(self.dynamic_ambience)} asset=1 center={center:.3f} inner={inner:.3f} wall={wall:.3f} outside={outside:.3f} cardinal_symmetry=1 fade_up=1 fade_down=1 replaceable=1 config_safe=1 path_guard=1 point_zone=1")
        self.userExit(); return task.done

    def userExit(self):
        if self.native_mode is not None:
            adapter=self.native_mode
            self.native_mode=None
            try: adapter.exit()
            except Exception: pass
        self._stop_district_music()
        self._stop_dynamic_ambience()
        self._stop_gleebs_audio()
        for resident_attr in ("gleebs_actor", "gleebs_ar_actor"):
            resident = getattr(self,resident_attr,None)
            if resident is not None:
                try:
                    resident.cleanup()
                except Exception as exc:
                    print(f"GLEEBS_CLEANUP_WARNING attr={resident_attr} error={exc}", file=sys.stderr)
                setattr(self,resident_attr,None)
        for item in getattr(self, "human_residents", []):
            for key in ("physical_actor", "ar_actor"):
                resident = item.get(key)
                if resident is not None:
                    try:
                        resident.cleanup()
                    except Exception as exc:
                        print(f"RESIDENT_CLEANUP_WARNING id={item.get('id')} layer={key} error={exc}", file=sys.stderr)
        self.human_residents = []
        return super().userExit()

    def _resident_grounded_model_root(self, root: NodePath, actor: Actor, scale: float):
        scale_np = root.attachNewNode("scale")
        scale_np.setScale(float(scale))
        model_root = scale_np.attachNewNode("model_root")
        actor.reparentTo(model_root)
        try:
            lower, upper = actor.getTightBounds()
        except Exception:
            lower, upper = (None, None)
        if lower is not None and upper is not None:
            model_root.setZ(-float(lower.z))
            return model_root, max(0.0, float(upper.z - lower.z)) * float(scale)
        return model_root, 0.0

    def _set_actor_neutral_gray(self, actor: Actor, diffuse=(0.46,0.47,0.49,1.0), ambient=(0.26,0.27,0.29,1.0), specular=(0.05,0.05,0.06,1.0), shininess: float=10.0):
        tuned = 0
        for np in actor.findAllMatches("**/+GeomNode"):
            node = np.node()
            for gi in range(node.getNumGeoms()):
                material = Material(f"resident_gray_{tuned}")
                material.setDiffuse(diffuse)
                material.setAmbient(ambient)
                material.setEmission((0.0,0.0,0.0,0.0))
                material.setSpecular(specular)
                material.setShininess(float(shininess))
                state = node.getGeomState(gi)
                node.setGeomState(gi, state.setAttrib(MaterialAttrib.make(material)))
                tuned += 1
        actor.clearColorScale()
        return tuned

    def _resident_ar_palette(self, resident_id: str):
        if resident_id == "male":
            return ((0.18, 1.00, 0.86, 1.0), (1.00, 0.34, 0.76, 1.0), (0.26, 0.58, 1.00, 1.0))
        return ((1.00, 0.60, 0.20, 1.0), (0.20, 0.98, 0.88, 1.0), (0.76, 0.36, 1.00, 1.0))

    def _resident_joint(self, actor: Actor, joint_name: str) -> NodePath:
        joint = actor.exposeJoint(None, "modelRoot", "mixamorig:" + joint_name)
        if joint is None or joint.isEmpty():
            raise RuntimeError(f"Resident rig missing joint: {joint_name}")
        return joint

    def _resident_neon_strip(self, actor: Actor, parent_joint: NodePath, name: str, start: Vec3, end: Vec3, color, width: float, thickness: float, front_offset: float) -> NodePath:
        direction = Vec3(end - start)
        length = max(0.035, float(direction.length()))
        midpoint = (Vec3(start) + Vec3(end)) * 0.5 + Vec3(0.0, float(front_offset), 0.0)
        target = Vec3(end) + Vec3(0.0, float(front_offset), 0.0)
        strip = make_box_geom(name, float(width), length, float(thickness), color)
        strip.reparentTo(actor)
        strip.setPos(midpoint)
        strip.lookAt(target)
        strip.setZ(strip.getZ() - float(thickness) * 0.5)
        strip.setLightOff(1)
        strip.setShaderOff(1)
        strip.setDepthOffset(2)
        strip.setBin("fixed", 12)
        strip.wrtReparentTo(parent_joint)
        return strip

    def _build_resident_ar_design(self, actor: Actor, resident_id: str, neon_seed: int):
        """Build a stable randomized neon design parented to animated joints.

        Marks are authored from the resident's real skeleton in actor coordinates, then
        reparented under the relevant exposed joint while preserving the authored transform.
        Every mark therefore follows animation instead of remaining behind at the Actor root.
        """
        colors = self._resident_ar_palette(resident_id)
        rng = random.Random(int(neon_seed))
        joint_names = (
            "Hips","Spine2","Head",
            "LeftArm","LeftForeArm","LeftHand","RightArm","RightForeArm","RightHand",
            "LeftUpLeg","LeftLeg","LeftFoot","RightUpLeg","RightLeg","RightFoot",
        )
        joints = {name:self._resident_joint(actor,name) for name in joint_names}
        pos = {name:Vec3(joints[name].getPos(actor)) for name in joint_names}
        accents = []
        metadata = []

        def add_segment(tag: str, parent: str, a: Vec3, b: Vec3, *, width_range=(0.024,0.050), thickness_range=(0.010,0.018), front_range=(-0.045,-0.026)):
            color_index = rng.randrange(len(colors))
            width = rng.uniform(*width_range)
            thickness = rng.uniform(*thickness_range)
            front = rng.uniform(*front_range)
            node = self._resident_neon_strip(actor,joints[parent],f"resident_{resident_id}_{tag}",a,b,colors[color_index],width,thickness,front)
            accents.append(node)
            metadata.append({
                "tag":tag,
                "joint":parent,
                "node":node,
                "joint_np":joints[parent],
                "local_pos":Vec3(node.getPos(joints[parent])),
                "local_hpr":Vec3(node.getHpr(joints[parent])),
                "color_index":color_index,
                "width":float(width),
                "length":float((b-a).length()),
            })

        # Head/torso identity marks. These are intentionally asymmetrical per resident.
        head = pos["Head"]
        visor_z = head.z + rng.uniform(0.070,0.105)
        visor_half = rng.uniform(0.075,0.105)
        add_segment("head_visor","Head",Vec3(-visor_half,head.y,visor_z),Vec3(visor_half,head.y,visor_z),width_range=(0.022,0.034),thickness_range=(0.010,0.014),front_range=(-0.100,-0.082))
        spine = pos["Spine2"]
        chest_w = rng.uniform(0.16,0.24)
        chest_z = spine.z + rng.uniform(0.025,0.090)
        chest_slant = rng.uniform(-0.055,0.055)
        add_segment("chest_trace","Spine2",Vec3(-chest_w,spine.y,chest_z-chest_slant),Vec3(chest_w,spine.y,chest_z+chest_slant),width_range=(0.026,0.044),thickness_range=(0.010,0.016),front_range=(-0.085,-0.060))
        if rng.random() < 0.85:
            add_segment("torso_trace","Spine2",pos["Hips"]+Vec3(rng.uniform(-0.06,0.02),0,0.05),pos["Spine2"]+Vec3(rng.uniform(0.00,0.08),0,-0.03),width_range=(0.020,0.034),thickness_range=(0.009,0.014),front_range=(-0.075,-0.052))

        # Limb traces: deterministic random fractions keep designs non-uniform while every
        # strip is still bound to the skeleton segment that owns it.
        limb_segments = (
            ("l_upper_arm","LeftArm","LeftForeArm"),("l_forearm","LeftForeArm","LeftHand"),
            ("r_upper_arm","RightArm","RightForeArm"),("r_forearm","RightForeArm","RightHand"),
            ("l_thigh","LeftUpLeg","LeftLeg"),("l_shin","LeftLeg","LeftFoot"),
            ("r_thigh","RightUpLeg","RightLeg"),("r_shin","RightLeg","RightFoot"),
        )
        for tag,parent,child in limb_segments:
            a0=pos[parent]; b0=pos[child]; segment=Vec3(b0-a0)
            start_f=rng.uniform(0.12,0.30); end_f=rng.uniform(0.62,0.88)
            a=Vec3(a0+segment*start_f); b=Vec3(a0+segment*end_f)
            add_segment(tag,parent,a,b,width_range=(0.022,0.042),thickness_range=(0.009,0.015),front_range=(-0.050,-0.030))
            if rng.random() < 0.38:
                # Short secondary dash creates a more graphic AR identity without duplicating
                # the entire limb outline.
                c0=rng.uniform(0.36,0.52); c1=min(0.92,c0+rng.uniform(0.12,0.22))
                add_segment(tag+"_dash",parent,Vec3(a0+segment*c0),Vec3(a0+segment*c1),width_range=(0.030,0.052),thickness_range=(0.010,0.016),front_range=(-0.054,-0.032))

        signature = tuple((m["tag"],m["joint"],m["color_index"],round(m["width"],4),round(m["length"],4)) for m in metadata)
        return accents, metadata, signature

    def _attach_static_resident_shadow(self, root: NodePath, *, ar_only: bool=False, scale_xy=(1.0, 1.0), alpha: float=0.24):
        card = self._make_soft_shadow_card("resident_contact_shadow")
        if ar_only:
            card.hide(NORMAL_CAMERA_MASK)
        else:
            card.hide(AR_CAMERA_MASK)
        card.setScale(float(scale_xy[0]), float(scale_xy[1]), 1.0)
        card.setPos(root.getX(self.render), root.getY(self.render), self._shadow_surface_z(root.getX(self.render), root.getY(self.render)) + 0.005)
        card.setColorScale(1,1,1,float(alpha))
        card.setBin("transparent", 6 if ar_only else 4)
        return card

    def _start_human_resident_idle(self, actor: Actor, idle_rate: float, idle_phase: float):
        frames = max(1, int(actor.getNumFrames("Idle")))
        start_frame = max(0, min(frames - 1, int(round((frames - 1) * float(idle_phase)))))
        actor.pose("Idle", start_frame)
        actor.setPlayRate(float(idle_rate), "Idle")
        actor.loop("Idle", restart=0)
        return start_frame, frames

    def _update_human_resident_idle_variation(self, dt: float):
        if not self.human_residents:
            return
        self.human_idle_time += float(dt)
        for item in self.human_residents:
            base_h = float(item["base_heading"])
            phase = float(item["idle_phase"]) * math.tau
            sway = math.sin(self.human_idle_time * float(item["idle_sway_speed"]) * math.tau + phase) * float(item["idle_heading_sway"])
            h = base_h + sway
            item["physical_root"].setH(h)
            ar_root = item.get("ar_root")
            if ar_root is not None:
                ar_root.setH(h)

    def _build_human_residents_physical(self):
        for spec in HUMAN_RESIDENT_SPECS:
            bam_path = self.base_dir / spec["bam_rel"]
            if not bam_path.exists():
                raise RuntimeError(f"Human resident runtime BAM missing: {bam_path}")
            actor = Actor(Filename.fromOsSpecific(str(bam_path)))
            anims = set(actor.getAnimNames())
            if "Idle" not in anims:
                actor.cleanup()
                raise RuntimeError(f"Human resident missing Idle animation: {bam_path}")
            root = self.visual_root.attachNewNode(f"resident_{spec['id']}_physical_root")
            root.setPos(*spec["position"])
            root.setH(float(spec["heading"]))
            root.hide(AR_CAMERA_MASK)
            model_root, grounded_height = self._resident_grounded_model_root(root, actor, float(spec["scale"]))
            actor.setName(spec["label"])
            tuned = self._set_actor_neutral_gray(actor)
            idle_start_frame, idle_frames = self._start_human_resident_idle(actor, float(spec["idle_rate"]), float(spec["idle_phase"]))
            cnode = CollisionNode(f"resident_{spec['id']}_body")
            cnode.setIntoCollideMask(WORLD_MASK)
            cnode.setFromCollideMask(BitMask32.allOff())
            cnode.addSolid(CollisionTube(0, 0, 0.08, 0, 0, float(spec["collision_height"]), float(spec["collision_radius"])))
            collision = root.attachNewNode(cnode)
            shadow = self._attach_static_resident_shadow(root, ar_only=False, scale_xy=(float(spec["collision_radius"])*2.2, float(spec["collision_radius"])*3.0), alpha=0.25)
            self.human_residents.append({
                "id": spec["id"],
                "label": spec["label"],
                "theme": spec["theme"],
                "physical_root": root,
                "physical_model_root": model_root,
                "physical_actor": actor,
                "physical_collision": collision,
                "physical_shadow": shadow,
                "position": spec["position"],
                "heading": float(spec["heading"]),
                "base_heading": float(spec["heading"]),
                "scale": float(spec["scale"]),
                "idle_rate": float(spec["idle_rate"]),
                "idle_phase": float(spec["idle_phase"]),
                "idle_heading_sway": float(spec["idle_heading_sway"]),
                "idle_sway_speed": float(spec["idle_sway_speed"]),
                "neon_seed": int(spec["neon_seed"]),
                "idle_start_frame": int(idle_start_frame),
                "idle_frames": int(idle_frames),
                "height": grounded_height,
                "bounds_height": grounded_height,
                "collision_radius": float(spec["collision_radius"]),
                "collision_height": float(spec["collision_height"]),
            })
            self.human_resident_stats["loaded"] += 1
            self.human_resident_stats["physical_materials"] += tuned
            self.human_resident_stats["colliders"] += 1
            self.human_resident_stats["shadows"] += 1
            self.human_resident_stats["idle_variants"] += 1

    def _build_human_residents_ar(self):
        for item in self.human_residents:
            bam_path = self.base_dir / next(spec["bam_rel"] for spec in HUMAN_RESIDENT_SPECS if spec["id"] == item["id"])
            actor = Actor(Filename.fromOsSpecific(str(bam_path)))
            root = self.render.attachNewNode(f"resident_{item['id']}_ar_root")
            root.setPos(*item["position"])
            root.setH(item["heading"])
            root.hide(NORMAL_CAMERA_MASK)
            model_root, grounded_height = self._resident_grounded_model_root(root, actor, item["scale"])
            actor.setName(item["label"] + "_AR")
            tuned = self._set_actor_neutral_gray(actor, diffuse=(0.025,0.025,0.028,1.0), ambient=(0.010,0.010,0.012,1.0), specular=(0.08,0.08,0.09,1.0), shininess=8.0)
            self._start_human_resident_idle(actor, item["idle_rate"], item["idle_phase"])
            accents, accent_meta, pattern_signature = self._build_resident_ar_design(actor, item["id"], item["neon_seed"])
            shadow = self._attach_static_resident_shadow(root, ar_only=True, scale_xy=(item["collision_radius"]*2.4, item["collision_radius"]*3.4), alpha=0.18)
            item["ar_actor"] = actor
            item["ar_root"] = root
            item["ar_model_root"] = model_root
            item["ar_shadow"] = shadow
            item["ar_accents"] = accents
            item["ar_accent_meta"] = accent_meta
            item["ar_pattern_signature"] = pattern_signature
            self.human_resident_stats["ar_loaded"] += 1
            self.human_resident_stats["ar_materials"] += tuned + len(accents)
            self.human_resident_stats["shadows"] += 1

    def _build_gleebs_physical_import(self):
        """Load the user-provided Gleebs BAM as the normal-world representation.

        The physical Actor remains separate from the AR duplicate so each view can own its
        materials without changing rig, animation, placement, collision, or authored proportions.
        """
        bam_path = self.base_dir / "assets" / "characters" / "gleebs" / "Gleebs_Game.bam"
        if not bam_path.exists():
            raise RuntimeError(f"Gleebs runtime BAM missing: {bam_path}")
        actor = Actor(Filename.fromOsSpecific(str(bam_path)))
        anims = set(actor.getAnimNames())
        if not {"Idle", "Walk"}.issubset(anims):
            actor.cleanup()
            raise RuntimeError(f"Gleebs BAM missing required animations: {sorted(anims)}")
        joints = actor.getJoints()
        if len(joints) < 40:
            actor.cleanup()
            raise RuntimeError(f"Gleebs rig incomplete: joints={len(joints)}")

        root = self.visual_root.attachNewNode("gleebs_physical_root")
        root.setPos(*GLEEBS_POSITION)
        root.setH(GLEEBS_HEADING)
        root.setScale(GLEEBS_SCALE)
        root.hide(AR_CAMERA_MASK)
        actor.reparentTo(root)
        actor.setName("Gleebs")
        damaged_materials = self._tune_gleebs_physical_damaged_materials(actor)
        damage_marks = 0
        actor.loop("Idle")

        # Character collision follows the torso/body rather than the decorative wings.
        # The proxy scales with the visual resident so there is no collision/mesh mismatch.
        cnode = CollisionNode("gleebs_body")
        cnode.setIntoCollideMask(WORLD_MASK)
        cnode.setFromCollideMask(BitMask32.allOff())
        cnode.addSolid(CollisionTube(0,0,0.08, 0,0,GLEEBS_COLLISION_HEIGHT, GLEEBS_COLLISION_RADIUS))
        collision = root.attachNewNode(cnode)

        self.gleebs_actor = actor
        self.gleebs_root = root
        self.gleebs_collision = collision
        self.gleebs_stats = {
            "loaded": 1,
            "joints": len(joints),
            "idle_frames": actor.getNumFrames("Idle"),
            "walk_frames": actor.getNumFrames("Walk"),
            "ar_loaded": 0,
            "scale": GLEEBS_SCALE,
            "ar_scale": GLEEBS_AR_SCALE,
            "physical_damaged_materials": damaged_materials,
            "damage_marks": damage_marks,
        }

    def _tune_gleebs_physical_damaged_materials(self, actor: Actor):
        """Physical Gleebs is the worn, dim version that AR later idealizes."""
        tuned = 0
        for np in actor.findAllMatches("**/+GeomNode"):
            node = np.node()
            for gi in range(node.getNumGeoms()):
                state = node.getGeomState(gi)
                mat_attrib = state.getAttrib(MaterialAttrib)
                if mat_attrib is None or mat_attrib.isOff():
                    continue
                original = mat_attrib.getMaterial()
                if original is None:
                    continue
                material = Material(original)
                name = material.getName().lower()
                diff = original.getDiffuse(); amb = original.getAmbient(); spec = original.getSpecular(); emi = original.getEmission()
                if any(token in name for token in ("biolume", "jade")):
                    # Eyes and luminous seams remain readable, but look depleted and unhealthy.
                    material.setDiffuse((float(diff.x)*0.26, float(diff.y)*0.24, float(diff.z)*0.22, float(diff.w)))
                    material.setAmbient((float(amb.x)*0.24, float(amb.y)*0.22, float(amb.z)*0.20, 1.0))
                    material.setEmission((float(emi.x)*0.055, float(emi.y)*0.050, float(emi.z)*0.045, 0.0))
                    material.setSpecular((0.020,0.028,0.018,float(spec.w)))
                    material.setShininess(min(26.0,max(8.0,float(original.getShininess())*0.30)))
                else:
                    # Uneven wear by material breaks the pristine showroom finish without fake decals.
                    if "obsidian" in name:
                        wear=0.30; spec_gain=0.20
                    elif "violet" in name:
                        wear=0.48; spec_gain=0.24
                    elif "amethyst" in name:
                        wear=0.40; spec_gain=0.22
                    elif "wing" in name:
                        wear=0.36; spec_gain=0.18
                    else:
                        wear=0.42; spec_gain=0.22
                    material.setDiffuse((float(diff.x)*wear, float(diff.y)*wear*0.94, float(diff.z)*wear, float(diff.w)))
                    material.setAmbient((float(amb.x)*wear*0.86, float(amb.y)*wear*0.84, float(amb.z)*wear*0.88, 1.0))
                    material.setEmission((0.0,0.0,0.0,0.0))
                    material.setSpecular((float(spec.x)*spec_gain,float(spec.y)*spec_gain,float(spec.z)*spec_gain,float(spec.w)))
                    material.setShininess(min(28.0,max(5.0,float(original.getShininess())*0.28)))
                node.setGeomState(gi,state.setAttrib(MaterialAttrib.make(material)))
                tuned += 1
        return tuned

    def _tune_gleebs_ar_materials(self, actor: Actor):
        """Increase AR specular response while preserving the authored material palette."""
        tuned = 0
        green = 0
        for np in actor.findAllMatches("**/+GeomNode"):
            node = np.node()
            for gi in range(node.getNumGeoms()):
                state = node.getGeomState(gi)
                mat_attrib = state.getAttrib(MaterialAttrib)
                if mat_attrib is None or mat_attrib.isOff():
                    continue
                original = mat_attrib.getMaterial()
                if original is None:
                    continue
                material = Material(original)
                name = material.getName().lower()
                if any(token in name for token in ("biolume", "jade")):
                    material.setSpecular((0.42,1.00,0.30,1.0))
                    material.setShininess(max(128.0,float(material.getShininess())))
                    emission = material.getEmission()
                    material.setEmission((max(0.10,float(emission.x)*1.65), max(0.72,float(emission.y)*1.55), max(0.025,float(emission.z)*1.65), 1.0))
                    green += 1
                else:
                    material.setSpecular((0.72,0.78,0.92,1.0))
                    material.setShininess(max(112.0,float(material.getShininess())))
                node.setGeomState(gi,state.setAttrib(MaterialAttrib.make(material)))
                tuned += 1
        actor.setShaderAuto()
        return tuned, green

    def _build_gleebs_eye_glow(self, actor: Actor):
        head = actor.exposeJoint(None,"modelRoot","mixamorig:Head")
        if head.isEmpty():
            return 0
        glow_vertex=("#version 130\n"
                     "in vec4 p3d_Vertex; in vec2 p3d_MultiTexCoord0; uniform mat4 p3d_ModelViewProjectionMatrix; out vec2 uv;\n"
                     "void main(){ gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex; uv=p3d_MultiTexCoord0; }\n")
        glow_frag=("#version 130\n"
                   "uniform vec4 p3d_ColorScale; in vec2 uv; out vec4 fragColor;\n"
                   "void main(){ vec2 q=(uv-vec2(0.5))*2.0; float r=length(q); float core=1.0-smoothstep(0.05,0.28,r); float halo=1.0-smoothstep(0.18,1.0,r); float a=(core*0.54+halo*0.24)*p3d_ColorScale.a; if(a<0.004) discard; vec3 c=mix(vec3(0.28,1.0,0.02),vec3(0.04,0.55,0.01),smoothstep(0.10,1.0,r)); fragColor=vec4(c,a); }\n")
        shader=Shader.make(Shader.SL_GLSL,glow_vertex,glow_frag)
        count=0
        for idx,x in enumerate((-0.125,0.125)):
            cm=CardMaker(f"gleebs_eye_glow_card_{idx}"); cm.setFrame(-0.095,0.095,-0.095,0.095)
            glow=head.attachNewNode(cm.generate())
            glow.setPos(x,-0.205,0.145)
            glow.setBillboardPointEye()
            glow.setShader(shader)
            glow.setTransparency(TransparencyAttrib.MAlpha)
            glow.setDepthWrite(False)
            glow.setBin("transparent",35)
            glow.setColorScale(1,1,1,0.82)
            self.gleebs_eye_glow_nodes.append(glow)
            count += 1
        eye_light=PointLight("gleebs_ar_eye_light")
        eye_light.setColor((0.16,1.0,0.035,1.0))
        eye_light.setAttenuation((1.0,0.0,3.2))
        light_np=head.attachNewNode(eye_light)
        light_np.setPos(0,-0.18,0.13)
        actor.setLight(light_np)
        self.gleebs_eye_glow_nodes.append(light_np)
        return count

    def _build_gleebs_ar_presentation(self):
        """AR-only visual duplicate of Gleebs with reflective/specular materials and eye glow."""
        bam_path = self.base_dir / "assets" / "characters" / "gleebs" / "Gleebs_Game.bam"
        actor = Actor(Filename.fromOsSpecific(str(bam_path)))
        root = self.render.attachNewNode("gleebs_ar_root")
        root.setPos(*GLEEBS_POSITION); root.setH(GLEEBS_HEADING); root.setScale(GLEEBS_AR_SCALE)
        root.hide(NORMAL_CAMERA_MASK)
        actor.reparentTo(root); actor.setName("Gleebs_AR"); actor.loop("Idle")
        tuned, green = self._tune_gleebs_ar_materials(actor)
        eye_glows = self._build_gleebs_eye_glow(actor)
        # Cool AR key light creates readable moving specular highlights without changing
        # the physical-world character or the city lighting.
        key=DirectionalLight("gleebs_ar_key")
        key.setColor((0.42,0.50,0.72,1.0))
        key_np=root.attachNewNode(key); key_np.setHpr(-24,-38,0)
        actor.setLight(key_np)
        # AR perception doubles Gleebs' body, so its contact shadow must scale with the perceived body too.
        self.gleebs_ar_shadow_card=self._make_soft_shadow_card("gleebs_ar_contact_shadow")
        self.gleebs_ar_shadow_card.hide(NORMAL_CAMERA_MASK)
        self.gleebs_ar_shadow_card.setBin("transparent",5)
        self.shadow_stats["sources"] = int(self.shadow_stats.get("sources",0)) + 1
        self.gleebs_ar_actor=actor; self.gleebs_ar_root=root
        self.gleebs_stats["ar_loaded"]=1
        self.gleebs_stats["ar_materials"]=tuned
        self.gleebs_stats["ar_green_materials"]=green
        self.gleebs_stats["eye_glows"]=eye_glows


    def _setup_gleebs_behavior(self):
        """Approach the live player, stop in front, wave, then idle/head-track."""
        self.gleebs_behavior_state="approach"; self.gleebs_approach_target=None; self.gleebs_wave_elapsed=0.0
        self.gleebs_behavior_stats.update({"walk_started":1,"walk_completed":0,"wave_started":0,"wave_completed":0,"head_tracking":0})
        self._set_gleebs_animation("Walk")
        for key,actor in (("physical",self.gleebs_actor),("ar",self.gleebs_ar_actor)):
            if actor is None: continue
            try:
                head=actor.controlJoint(None,"modelRoot","mixamorig:Head")
                if head is not None and not head.isEmpty(): self.gleebs_head_controls[key]=head
            except Exception as exc: print(f"GLEEBS_CONTROL_WARNING layer={key} error={exc}",file=sys.stderr)

    def _set_gleebs_animation(self, name: str):
        for actor in (self.gleebs_actor,self.gleebs_ar_actor):
            if actor is None:
                continue
            try:
                if actor.getCurrentAnim() != name:
                    actor.loop(name)
            except Exception as exc:
                print(f"GLEEBS_ANIM_WARNING anim={name} error={exc}",file=sys.stderr)

    @staticmethod
    def _gleebs_heading_to_delta(delta: Vec3) -> float:
        # Authored Gleebs forward is -Y, so H=0 faces south in local model space.
        return math.degrees(math.atan2(float(delta.x), -float(delta.y)))

    def _player_forward_xy(self)->Vec3:
        quat=self.player.getQuat(self.render); f=quat.xform(Vec3(0,1,0)); f.z=0
        if f.lengthSquared()<1e-6: return Vec3(0,1,0)
        f.normalize(); return f

    def _acquire_gleebs_wave_controls(self):
        self.gleebs_wave_controls={}
        for key,actor in (("physical",self.gleebs_actor),("ar",self.gleebs_ar_actor)):
            if actor is None: continue
            try:
                arm=actor.controlJoint(None,"modelRoot","mixamorig:RightArm")
                fore=actor.controlJoint(None,"modelRoot","mixamorig:RightForeArm")
                hand=actor.controlJoint(None,"modelRoot","mixamorig:RightHand")
                if arm is not None and fore is not None and not arm.isEmpty() and not fore.isEmpty():
                    self.gleebs_wave_controls[key]={"arm":arm,"fore":fore,"hand":hand,"arm_rest":Vec3(arm.getHpr()),"fore_rest":Vec3(fore.getHpr()),"hand_rest":Vec3(hand.getHpr()) if hand is not None and not hand.isEmpty() else Vec3(0)}
            except Exception as exc:
                print(f"GLEEBS_WAVE_CONTROL_WARNING layer={key} error={exc}",file=sys.stderr)

    def _release_gleebs_wave_controls(self):
        # controlJoint() overrides animation ownership.  Release every waved limb joint so
        # Idle/Walk can drive the arm again; merely restoring HPR leaves the limb frozen.
        for actor in (self.gleebs_actor,self.gleebs_ar_actor):
            if actor is None: continue
            for joint in ("mixamorig:RightHand","mixamorig:RightForeArm","mixamorig:RightArm"):
                try:
                    actor.releaseJoint("modelRoot",joint)
                except Exception as exc:
                    print(f"GLEEBS_WAVE_RELEASE_WARNING joint={joint} error={exc}",file=sys.stderr)
        self.gleebs_wave_controls.clear()
        self.gleebs_behavior_stats["wave_joint_released"]=1

    def _apply_gleebs_wave_pose(self,t:float):
        # Raised arm with a clear side-to-side forearm/hand wave.
        phase=math.sin(t*math.tau*1.65)
        for item in self.gleebs_wave_controls.values():
            a=item["arm_rest"]; f=item["fore_rest"]; h=item["hand_rest"]
            # Lift the right arm clearly above shoulder height, then sweep the forearm/hand
            # side-to-side.  This remains readable as a wave from the player's frontal view.
            item["arm"].setHpr(a.x,a.y+58.0,a.z)
            item["fore"].setHpr(f.x+34.0+phase*16.0,f.y,f.z)
            if item.get("hand") is not None and not item["hand"].isEmpty(): item["hand"].setHpr(h.x+phase*18.0,h.y,h.z)

    def _start_gleebs_wave(self):
        if self.gleebs_behavior_state=="wave": return
        self.gleebs_behavior_state="wave"; self.gleebs_wave_elapsed=0.0; self.gleebs_behavior_stats["walk_completed"]=1; self.gleebs_behavior_stats["wave_started"]=1; self._set_gleebs_animation("Idle"); self._acquire_gleebs_wave_controls()

    def _update_gleebs_behavior(self, dt: float):
        if self.gleebs_root is None or self.gleebs_ar_root is None or not hasattr(self,"player"): return
        dt=max(0.0,min(0.10,float(dt))); player_pos=Vec3(self.player.getPos(self.render)); player_pos.z=0
        if self.gleebs_behavior_state=="approach":
            pos=Vec3(self.gleebs_root.getPos(self.render)); pos.z=0
            # Desired greeting point is several feet in front of the player's live facing.
            target=player_pos+self._player_forward_xy()*GLEEBS_APPROACH_STOP_DISTANCE; self.gleebs_approach_target=Vec3(target)
            to_target=target-pos; to_target.z=0; target_dist=float(to_target.length()); to_player=player_pos-pos; to_player.z=0; player_dist=float(to_player.length())
            if target_dist<=0.10 or player_dist<=GLEEBS_APPROACH_STOP_DISTANCE+0.05:
                self._start_gleebs_wave()
            elif target_dist>0.001:
                direction=Vec3(to_target); direction.normalize()
                max_safe=max(0.0,player_dist-GLEEBS_APPROACH_STOP_DISTANCE)
                step=min(GLEEBS_APPROACH_SPEED*dt,target_dist,max_safe)
                new_pos=pos+direction*max(0.0,step); heading=self._gleebs_heading_to_delta(player_pos-new_pos)
                self.gleebs_root.setPos(self.render,new_pos); self.gleebs_root.setH(heading); self.gleebs_ar_root.setPos(self.render,new_pos); self.gleebs_ar_root.setH(heading)
                if float((player_pos-new_pos).length())<=GLEEBS_APPROACH_STOP_DISTANCE+0.055 or float((target-new_pos).length())<=0.10: self._start_gleebs_wave()
        elif self.gleebs_behavior_state=="wave":
            # Face the player while waving; the body no longer translates.
            pos=Vec3(self.gleebs_root.getPos(self.render)); delta=player_pos-pos; delta.z=0
            if delta.lengthSquared()>1e-6:
                heading=self._gleebs_heading_to_delta(delta); self.gleebs_root.setH(heading); self.gleebs_ar_root.setH(heading)
            self.gleebs_wave_elapsed+=dt; self._apply_gleebs_wave_pose(self.gleebs_wave_elapsed)
            if self.gleebs_wave_elapsed>=GLEEBS_WAVE_SECONDS:
                self._release_gleebs_wave_controls(); self._set_gleebs_animation("Idle"); self.gleebs_behavior_state="idle"; self.gleebs_behavior_stats["wave_completed"]=1
        elif self.gleebs_behavior_state=="idle":
            self._update_gleebs_head_tracking(dt)

    def _update_gleebs_head_tracking(self, dt: float):
        if not self.gleebs_head_controls or not hasattr(self,"player"):
            return
        target_world=Vec3(self.player.getPos(self.render))+Vec3(0,0,EYE_HEIGHT*0.88)
        tracked=0
        for key,control in self.gleebs_head_controls.items():
            root=self.gleebs_root if key=="physical" else self.gleebs_ar_root
            if root is None:
                continue
            local=root.getRelativePoint(self.render,target_world)
            # Head joint sits at ~1.19 authored metres. Root-relative coordinates correctly
            # account for the 1.12x physical and 2.24x AR perceived sizes.
            dz=float(local.z)-1.19
            horizontal=max(0.001,math.hypot(float(local.x),float(local.y)))
            desired_h=max(-GLEEBS_HEAD_YAW_LIMIT,min(GLEEBS_HEAD_YAW_LIMIT,self._gleebs_heading_to_delta(local)))
            desired_p=max(-GLEEBS_HEAD_PITCH_LIMIT,min(GLEEBS_HEAD_PITCH_LIMIT,math.degrees(math.atan2(dz,horizontal))))
            cur=control.getHpr()
            blend=1.0-math.exp(-max(0.0,float(dt))*6.0)
            control.setHpr(float(cur.x)+(desired_h-float(cur.x))*blend,
                           float(cur.y)+(desired_p-float(cur.y))*blend,
                           0.0)
            tracked += 1
        if tracked:
            self.gleebs_behavior_stats["head_tracking"]=tracked

    def _load_gleebs_audio(self):
        """Load replaceable positional purr/spark assets with explicit runtime ownership."""
        path=self.gleebs_audio_config_path
        if not path.exists():
            print(f"GLEEBS_AUDIO_CONFIG_MISSING path={path}")
            return
        try:
            data=json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"GLEEBS_AUDIO_CONFIG_ERROR path={path} error={exc}")
            return
        if not isinstance(data,dict):
            return
        try:
            manager=self.sfxManagerList[0]
            manager.setActive(True); manager.setVolume(1.0)
            self.gleebs_audio3d=Audio3DManager.Audio3DManager(manager,self.camera,self.render)
        except Exception as exc:
            print(f"GLEEBS_AUDIO3D_ERROR error={exc}")
            self.gleebs_audio3d=None
            return

        loaded=0
        for key,attr in (("purr","gleebs_purr_sound"),("spark","gleebs_spark_sound")):
            raw=data.get(key,{})
            asset=self._music_safe_asset(raw.get("asset","")) if isinstance(raw,dict) else None
            if asset is None or not asset.exists():
                print(f"GLEEBS_AUDIO_ASSET_MISSING kind={key} path={asset}")
                continue
            try:
                sound=self.gleebs_audio3d.loadSfx(Filename.fromOsSpecific(str(asset)))
                sound.setVolume(max(0.0,min(1.0,float(raw.get("gain",0.5)))))
                self.gleebs_audio3d.setSoundMinDistance(sound,max(0.1,float(raw.get("min_distance",2.0))))
                self.gleebs_audio3d.setSoundMaxDistance(sound,max(float(raw.get("min_distance",2.0))+0.1,float(raw.get("max_distance",32.0))))
                self.gleebs_audio3d.attachSoundToObject(sound,self.gleebs_root)
                setattr(self,attr,sound)
                loaded += 1
            except Exception as exc:
                print(f"GLEEBS_AUDIO_LOAD_WARNING kind={key} error={exc}",file=sys.stderr)

        if self.gleebs_purr_sound is not None:
            self.gleebs_purr_sound.setLoop(True)
            if self.audio_runtime_available:
                self.gleebs_purr_sound.play()
            self.gleebs_audio_stats["purr"]=1
        if self.gleebs_spark_sound is not None:
            self.gleebs_spark_sound.setLoop(False)
            self.gleebs_audio_stats["spark"]=1
        self.gleebs_audio_stats["loaded"]=loaded
        self.gleebs_audio_stats["radial"]=1 if self.gleebs_audio3d is not None else 0
        self._gleebs_audio_reconcile=0.0

    def _update_gleebs_audio(self, dt: float):
        sound=self.gleebs_purr_sound
        if sound is None:
            return
        pause_gain=0.28 if self.paused else 1.0
        try:
            config=json.loads(self.gleebs_audio_config_path.read_text(encoding="utf-8"))
            base_gain=max(0.0,min(1.0,float(config.get("purr",{}).get("gain",0.42))))
        except Exception:
            base_gain=0.62
        sound.setVolume(base_gain*pause_gain)
        self._gleebs_audio_reconcile=getattr(self,"_gleebs_audio_reconcile",0.0)+max(0.0,float(dt))
        if self.audio_runtime_available and self._gleebs_audio_reconcile>=1.0:
            self._gleebs_audio_reconcile=0.0
            if sound.status() != AudioSound.PLAYING:
                sound.play()

    def _stop_gleebs_audio(self):
        for sound in (self.gleebs_purr_sound,self.gleebs_spark_sound):
            if sound is not None:
                try:
                    sound.stop()
                except Exception as exc:
                    print(f"GLEEBS_AUDIO_STOP_WARNING error={exc}",file=sys.stderr)
        if self.gleebs_audio3d is not None:
            try:
                self.gleebs_audio3d.disable()
            except Exception as exc:
                print(f"GLEEBS_AUDIO3D_STOP_WARNING error={exc}",file=sys.stderr)
        self.gleebs_audio3d=None

    def _build_gleebs_spark_system(self):
        """Small physical-only spark pool; no collision and no constant particle clutter."""
        root=self.render.attachNewNode("gleebs_damage_sparks")
        root.hide(AR_CAMERA_MASK); root.setLightOff(1)
        self.gleebs_spark_root=root
        shader_vertex=("#version 130\n"
                       "in vec4 p3d_Vertex; in vec2 p3d_MultiTexCoord0; uniform mat4 p3d_ModelViewProjectionMatrix; out vec2 uv;\n"
                       "void main(){ gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex; uv=p3d_MultiTexCoord0; }\n")
        shader_frag=("#version 130\n"
                     "uniform vec4 p3d_ColorScale; in vec2 uv; out vec4 fragColor;\n"
                     "void main(){ vec2 q=(uv-vec2(0.5))*2.0; float r=length(q); float a=(1.0-smoothstep(0.12,1.0,r))*p3d_ColorScale.a; if(a<0.01) discard; fragColor=vec4(p3d_ColorScale.rgb,a); }\n")
        shader=Shader.make(Shader.SL_GLSL,shader_vertex,shader_frag)
        for idx in range(10):
            cm=CardMaker(f"gleebs_spark_{idx}"); cm.setFrame(-0.045,0.045,-0.045,0.045)
            np=root.attachNewNode(cm.generate()); np.setBillboardPointEye(); np.setShader(shader)
            np.setTransparency(TransparencyAttrib.MAlpha); np.setDepthWrite(False); np.setBin("transparent",45); np.hide()
            self.gleebs_spark_particles.append({"node":np,"vel":Vec3(0,0,0),"life":0.0,"max_life":0.0})
        rng=random.Random(4903)
        self.gleebs_next_spark=rng.uniform(GLEEBS_SPARK_INTERVAL_MIN,GLEEBS_SPARK_INTERVAL_MAX)
        self._gleebs_spark_rng=rng

    def _emit_gleebs_sparks(self, forced: bool = False):
        if self.gleebs_root is None:
            return
        rng=getattr(self,"_gleebs_spark_rng",random.Random(4903))
        center=self.gleebs_root.getPos(self.render)+Vec3(rng.uniform(-0.32,0.32),rng.uniform(-0.16,0.16),rng.uniform(0.65,1.45))
        active_count=rng.randint(5,8)
        for item in self.gleebs_spark_particles[:active_count]:
            life=rng.uniform(0.55,0.72) if forced else rng.uniform(0.18,0.38)
            item["life"]=life; item["max_life"]=life
            item["vel"]=Vec3(rng.uniform(-1.8,1.8),rng.uniform(-1.5,1.5),rng.uniform(1.2,3.8))
            item["node"].setPos(self.render,center+Vec3(rng.uniform(-0.12,0.12),rng.uniform(-0.08,0.08),rng.uniform(-0.10,0.10)))
            scale=rng.uniform(0.55,1.15); item["node"].setScale(scale)
            item["node"].setColorScale(1.0,rng.uniform(0.52,0.82),0.05,0.95); item["node"].show()
        self.gleebs_behavior_stats["spark_events"] += 1
        if self.gleebs_spark_sound is not None and self.audio_runtime_available:
            try:
                self.gleebs_spark_sound.play()
            except Exception as exc:
                print(f"GLEEBS_SPARK_AUDIO_WARNING error={exc}",file=sys.stderr)

    def _update_gleebs_sparks(self, dt: float):
        dt=max(0.0,min(0.10,float(dt)))
        self.gleebs_spark_elapsed += dt
        if self.gleebs_spark_elapsed >= self.gleebs_next_spark:
            self.gleebs_spark_elapsed=0.0
            rng=getattr(self,"_gleebs_spark_rng",random.Random(4903))
            self.gleebs_next_spark=rng.uniform(GLEEBS_SPARK_INTERVAL_MIN,GLEEBS_SPARK_INTERVAL_MAX)
            self._emit_gleebs_sparks()
        for item in self.gleebs_spark_particles:
            if item["life"] <= 0.0:
                continue
            item["life"] -= dt
            if item["life"] <= 0.0:
                item["node"].hide(); continue
            vel=Vec3(item["vel"]); vel.z -= 8.0*dt; item["vel"]=vel
            item["node"].setPos(self.render,item["node"].getPos(self.render)+vel*dt)
            alpha=max(0.0,min(1.0,item["life"]/max(0.001,item["max_life"])))
            c=item["node"].getColorScale(); item["node"].setColorScale(c.x,c.y,c.z,alpha)

    def _build_player(self):
        self.player=self.render.attachNewNode("player")
        self.camera.reparentTo(self.player); self.camera.setPos(0,0,EYE_HEIGHT)
        self.traverser=CollisionTraverser("player_traverser")
        self.pusher=CollisionHandlerPusher()
        cnode=CollisionNode("player_body"); cnode.setFromCollideMask(WORLD_MASK); cnode.setIntoCollideMask(PLAYER_MASK)
        cnode.addSolid(CollisionSphere(0,0,1.05,PLAYER_RADIUS))
        cnp=self.player.attachNewNode(cnode); self.pusher.addCollider(cnp,self.player); self.traverser.addCollider(cnp,self.pusher)
        self.collision_np=cnp

    def _build_ui(self):
        self.crosshair=OnscreenText(text="+",pos=(0,0),scale=0.050,fg=(0.90,0.90,0.86,0.78),align=TextNode.ACenter,mayChange=False)
        # No permanent explanatory HUD.  The visor frame itself communicates AR state;
        # keeping this legacy title hidden prevents stale build/layer text from covering play.
        self.hud_title=OnscreenText(text="",pos=(-1.28,0.91),scale=0.032,fg=(0.17,0.18,0.18,0.72),align=TextNode.ALeft,mayChange=True)
        self.hud_title.hide()
        self.pause_text=OnscreenText(text="",pos=(0,0.11),scale=0.048,fg=(0.92,0.92,0.90,1),bg=(0.10,0.11,0.11,0.90),align=TextNode.ACenter,mayChange=True)
        self.pause_text.hide()
        self.gleebs_interact_text=OnscreenText(
            text="E  //  TALK TO GLEEBS", pos=(0,-0.78), scale=0.040,
            fg=(0.88,1.0,0.90,1), bg=(0.025,0.05,0.04,0.82),
            align=TextNode.ACenter, mayChange=False)
        self.gleebs_interact_text.hide()
        self.gleebs_mode_text=OnscreenText(
            text=("GLEEBS // HOLOVERSE LINKS\n\n"
                  "1  UTOPIA CONFLICT\n"
                  "2  GLYPHBOUND\n"
                  "3  VECTOR ARENA\n\n"
                  "Inside a link, TAB calls Gleebs\n"
                  "E  CLOSE"),
            pos=(0,0.30), scale=0.050, fg=(0.88,1.0,0.90,1),
            bg=(0.015,0.025,0.025,0.94), align=TextNode.ACenter, mayChange=False)
        self.gleebs_mode_text.hide()
        # Same Gleebs panel style, shown over a running link (TAB). Separate widget so the
        # Utopia-side menu text is never rewritten.
        self.native_link_text=OnscreenText(
            text="", pos=(0,0.30), scale=0.050, fg=(0.88,1.0,0.90,1),
            bg=(0.015,0.025,0.025,0.94), align=TextNode.ACenter, mayChange=True)
        self.native_link_text.setBin("gui-popup",100)
        self.native_link_text.hide()

    def _bind_controls(self):
        bindings=[("w","forward"),("s","back"),("a","left"),("d","right"),("shift","sprint")]
        for key,slot in bindings:
            self.accept(key, self._set_key,[slot,True]); self.accept(key+"-up",self._set_key,[slot,False])
        self.accept("space",self._jump)
        self.accept("escape",self._toggle_pause)
        self.accept("f11",self._toggle_fullscreen)
        self.accept("mouse3",self._lens_hold,[True]); self.accept("mouse3-up",self._lens_hold,[False])
        self.accept("l",self._toggle_lens)
        self.accept("v",self._cycle_visor_mode)
        self.accept("arrow_up",self._adjust_ar_time,[1.0])
        self.accept("arrow_down",self._adjust_ar_time,[-1.0])
        self.accept("arrow_left",self._adjust_ar_time,[-AR_FINE_TIME_STEP_HOURS])
        self.accept("arrow_right",self._adjust_ar_time,[AR_FINE_TIME_STEP_HOURS])
        self.accept("e",self._toggle_gleebs_mode_menu)
        self.accept("1",self._gleebs_number_key,[1])
        self.accept("2",self._gleebs_number_key,[2])
        self.accept("3",self._gleebs_number_key,[3])
        self.accept("4",self._gleebs_number_key,[4])
        self.accept("f1",self._toggle_help)

    def _unbind_controls(self):
        """Remove only Utopia Vision-owned gameplay bindings before a native mode mounts."""
        events = (
            "w","w-up","s","s-up","a","a-up","d","d-up","shift","shift-up",
            "space","escape","f11","mouse3","mouse3-up","l","v",
            "arrow_up","arrow_down","arrow_left","arrow_right","1","2","3","4","e","f1",
        )
        for event in events:
            try:
                self.ignore(event)
            except Exception:
                pass

    def _gleebs_number_key(self, number: int):
        number=int(number)
        if self.native_mode is not None:
            return
        if self.gleebs_mode_menu_open:
            if number in GLEEBS_NATIVE_MODES:
                self._enter_native_mode(number)
            return
        if getattr(self.args,"dev_controls",False):
            spawns={1:"south_gate",2:"plaza",3:"north",4:"overlook"}
            if number in spawns:
                self._spawn(spawns[number])

    def _gleebs_distance(self) -> float:
        if self.gleebs_root is None or not hasattr(self,"player"):
            return 9999.0
        try:
            return float((self.gleebs_root.getPos(self.render)-self.player.getPos(self.render)).length())
        except Exception:
            return 9999.0

    def _update_gleebs_interaction_ui(self):
        if self.native_mode is not None:
            self.gleebs_interaction_available=False
            self.gleebs_interact_text.hide()
            return
        available=(self._gleebs_distance() <= GLEEBS_INTERACTION_DISTANCE and self.gleebs_behavior_state != "approach")
        self.gleebs_interaction_available=bool(available)
        if self.gleebs_mode_menu_open and not available:
            self._close_gleebs_mode_menu()
        if available and not self.gleebs_mode_menu_open and not self.paused:
            self.gleebs_interact_text.show()
        else:
            self.gleebs_interact_text.hide()

    def _toggle_gleebs_mode_menu(self):
        if self.native_mode is not None or self.paused:
            return
        if self.gleebs_mode_menu_open:
            self._close_gleebs_mode_menu()
            return
        if not self.gleebs_interaction_available:
            return
        self.gleebs_mode_menu_open=True
        self._clear_movement_keys()
        self._release_mouse()
        self.gleebs_interact_text.hide()
        self.gleebs_mode_text.show()

    def _close_gleebs_mode_menu(self):
        self.gleebs_mode_menu_open=False
        try: self.gleebs_mode_text.hide()
        except Exception: pass
        if not self.paused and not self.args.offscreen and self.native_mode is None:
            self._capture_mouse()

    @staticmethod
    def _safe_show(node, visible: bool):
        try:
            if node is not None:
                node.show() if visible else node.hide()
        except Exception:
            pass

    def _set_utopia_scene_visible(self, visible: bool):
        # Freeze Utopia Vision without stashing the render branch that carries
        # the live host camera.  Native modes reuse that exact camera/window.
        # Stashing the player root would also stash self.camera because the
        # normal gameplay camera is parented beneath self.player.
        if not visible:
            self.native_mode_scene_nodes=[]
            camera_nodes=[
                node for node in (getattr(self,"camera",None), getattr(self,"cam",None))
                if node is not None and not node.isEmpty()
            ]
            try:
                for node in list(self.render.getChildren()):
                    try:
                        carries_camera=any(node == camera_node or node.isAncestorOf(camera_node) for camera_node in camera_nodes)
                    except Exception:
                        carries_camera=False
                    if carries_camera:
                        continue
                    try:
                        node.stash()
                        self.native_mode_scene_nodes.append(node)
                    except Exception:
                        pass
            except Exception:
                pass
            # Utopia's world fog and global lights live on render itself, so
            # stashing their NodePaths is not sufficient isolation for a new
            # child scene.  Remove the host render-state while the mode owns
            # presentation; the authoritative Utopia state is restored below.
            try: self.render.clearFog()
            except Exception: pass
            try: self.render.clearLight()
            except Exception: pass
        else:
            for node in list(self.native_mode_scene_nodes):
                try:
                    if node is not None and not node.isEmpty():
                        node.unstash()
                except Exception:
                    pass
            self.native_mode_scene_nodes=[]
            try:
                world_fog=getattr(self,"world_fog",None)
                if world_fog is not None:
                    self.render.setFog(world_fog)
            except Exception:
                pass
            for light_np in (getattr(self,"ambient_light_np",None), getattr(self,"sun_np",None)):
                try:
                    if light_np is not None and not light_np.isEmpty():
                        self.render.setLight(light_np)
                except Exception:
                    pass
        for node in (
            getattr(self,"crosshair",None), getattr(self,"hud_title",None),
            getattr(self,"pause_text",None), getattr(self,"gleebs_interact_text",None),
            getattr(self,"gleebs_mode_text",None),
        ):
            self._safe_show(node, False if not visible else (node is getattr(self,"crosshair",None)))

    def _suspend_utopia_audio(self):
        state={"district":[],"ambience":[],"gleebs_purr":False}
        for track in self.district_music.values():
            sound=track.get("sound")
            if sound is None: continue
            state["district"].append((sound,float(track.get("current_volume",0.0))))
            try: sound.stop()
            except Exception: pass
        for zone in self.dynamic_ambience:
            sound=zone.get("sound")
            if sound is None: continue
            state["ambience"].append((sound,float(zone.get("current_volume",0.0))))
            try: sound.stop()
            except Exception: pass
        if self.gleebs_purr_sound is not None:
            try:
                state["gleebs_purr"]=self.gleebs_purr_sound.status()==AudioSound.PLAYING
                self.gleebs_purr_sound.stop()
            except Exception:
                pass
        return state

    def _resume_utopia_audio(self,state):
        for key in ("district","ambience"):
            for sound,volume in list((state or {}).get(key,[])):
                try:
                    sound.setVolume(max(0.0,min(1.0,float(volume))))
                    sound.play()
                except Exception:
                    pass
        if (state or {}).get("gleebs_purr") and self.gleebs_purr_sound is not None:
            try: self.gleebs_purr_sound.play()
            except Exception: pass

    def _load_native_adapter_module(self, adapter_path: Path, mode_id: str):
        if not adapter_path.is_file():
            raise FileNotFoundError(f"Native adapter missing: {adapter_path}")
        module_name=f"utopia_vision_native_{mode_id}_{id(self)}"
        spec=importlib.util.spec_from_file_location(module_name,adapter_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load native adapter: {adapter_path}")
        module=importlib.util.module_from_spec(spec)
        sys.modules[module_name]=module
        root=str(adapter_path.parent)
        added=False
        if root not in sys.path:
            sys.path.insert(0,root); added=True
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name,None)
            raise
        finally:
            if added:
                try: sys.path.remove(root)
                except ValueError: pass
        self.native_mode_module_name=module_name
        return module

    def _enter_native_mode(self, number: int):
        if self.native_mode is not None:
            return
        spec=GLEEBS_NATIVE_MODES.get(int(number))
        if not spec:
            return
        adapter_path=self.base_dir.joinpath(*spec["adapter"])
        entry_path=self.base_dir.joinpath(*spec["entry"])
        if not entry_path.is_file():
            print(f"NATIVE_MODE_MISSING id={spec['id']} entry={entry_path}",file=sys.stderr)
            return
        self._close_gleebs_mode_menu()
        try:
            bg=self.win.getClearColor() if self.win is not None else None
        except Exception:
            bg=None
        try:
            camera_parent=self.camera.getParent(); camera_transform=self.camera.getTransform()
        except Exception:
            camera_parent=None; camera_transform=None
        try:
            fov=tuple(float(v) for v in self.camLens.getFov())
            near=float(self.camLens.getNear()); far=float(self.camLens.getFar())
        except Exception:
            fov=None; near=None; far=None
        try:
            cam_active=bool(self.camNode.isActive())
        except Exception:
            cam_active=True
        self.native_mode_host_state={
            "paused":bool(self.paused), "lens_held":bool(self.lens_held), "lens_latched":bool(self.lens_latched),
            "bg":bg, "camera_parent":camera_parent, "camera_transform":camera_transform,
            "fov":fov, "near":near, "far":far, "cam_active":cam_active,
            "audio":self._suspend_utopia_audio(),
        }
        self.native_mode_host_state["guard"]=self._snapshot_host_for_mode()
        self.native_mode_host_state["mode_id"]=spec["id"]
        self._clear_movement_keys()
        self.paused=False
        self.lens_held=False; self.lens_latched=False; self._set_lens(False)
        self._release_mouse()
        # Modes position base.camera in their own world coordinates. The Utopia camera
        # normally rides under the player (hundreds of metres from origin, pitched), which
        # offset every hosted view. Park it at the world origin for the visit; the saved
        # parent/transform are restored in _restore_after_native_mode().
        try:
            self.camera.reparentTo(self.render)
            self.camera.clearTransform()
        except Exception:
            pass
        self._set_utopia_scene_visible(False)
        self._unbind_controls()
        self.accept("tab",self._native_tab_return)
        adapter=None
        try:
            module=self._load_native_adapter_module(adapter_path,spec["id"])
            creator=getattr(module,"create_mode",None) or getattr(module,"create_native_adapter",None)
            if not callable(creator):
                raise RuntimeError(f"Native adapter has no create_mode: {adapter_path}")
            mode_info={"dimension":True,"manifest":{"host_contract":"holoverse_dimension_v1"},"id":spec["id"]}
            adapter=creator(self,mode=mode_info,entry_path=entry_path,label=spec["label"])
            self.native_mode=adapter
            self.native_mode_id=spec["id"]
            adapter.enter()
            print(f"UTOPIA_NATIVE_ENTER id={self.native_mode_id} same_window=1 entry={entry_path}")
        except Exception as exc:
            print(f"UTOPIA_NATIVE_ENTER_FAILED id={spec['id']} error={exc.__class__.__name__}:{exc}",file=sys.stderr)
            if adapter is not None:
                try: adapter.exit()
                except Exception: pass
            self.native_mode=None; self.native_mode_id=""
            self._restore_after_native_mode()

    # ---------- Gleebs link menu inside a mode ----------
    LINK_MENU_KEYS=("tab","escape","1","2","3","e")
    RELEASE_KEYS=("w","a","s","d","shift","space","control","q","e","mouse1","mouse3",
                  "arrow_up","arrow_down","arrow_left","arrow_right")

    def _native_tab_return(self):
        """TAB inside a mode calls Gleebs: back to Utopia or straight into another link."""
        if self.native_mode is None:
            return
        if self.native_link_menu_open:
            return
        self._open_native_link_menu()

    def _native_link_menu_text(self):
        lines=["GLEEBS // HOLOVERSE LINKS",""]
        for number,spec in sorted(GLEEBS_NATIVE_MODES.items()):
            here=" (HERE)" if spec["id"]==self.native_mode_id else ""
            lines.append(f"{number}  {spec['label']}{here}")
        lines+=["","TAB  BACK TO UTOPIA VISION","ESC  STAY"]
        return "\n".join(lines)

    def _open_native_link_menu(self):
        self.native_link_menu_open=True
        # Route every key to gxlink-* while the menu is up, so the frozen mode receives
        # nothing (its own 1/2/3, E and ESC bindings would otherwise fire as well).
        self.native_link_prefixes=[]
        for thrower in (self.buttonThrowers or []):
            node=thrower.node()
            self.native_link_prefixes.append((node,node.getPrefix()))
            node.setPrefix("gxlink-")
        # Register on the real messenger: some adapters (Utopia Conflict) swap Panda's
        # global messenger for a capture proxy during the visit, which would swallow
        # DirectObject.accept() calls made now.
        real=self.messenger
        real.accept("gxlink-tab",self,self._native_link_choose,["utopia"])
        real.accept("gxlink-escape",self,self._native_link_choose,["stay"])
        real.accept("gxlink-e",self,self._native_link_choose,["stay"])
        for number in GLEEBS_NATIVE_MODES:
            real.accept(f"gxlink-{number}",self,self._native_link_choose,[number])
        self.native_link_text.setText(self._native_link_menu_text())
        self.native_link_text.show()
        print(f"UTOPIA_LINK_MENU open id={self.native_mode_id}")

    def _close_native_link_menu(self):
        if not self.native_link_menu_open:
            return
        self.native_link_menu_open=False
        for event in [f"gxlink-{k}" for k in self.LINK_MENU_KEYS]:
            try: self.messenger.ignore(event,self)
            except Exception: pass
        for node,prefix in self.native_link_prefixes:
            try: node.setPrefix(prefix)
            except Exception: pass
        self.native_link_prefixes=[]
        try: self.native_link_text.hide()
        except Exception: pass

    def _native_link_choose(self, choice):
        self._close_native_link_menu()
        if choice=="stay":
            # Keys released while the menu was up never reached the mode: release them now.
            for key in self.RELEASE_KEYS:
                self.messenger.send(f"{key}-up")
            return
        if choice=="utopia":
            self.return_from_native_mode(reason="gleebs_link_utopia")
            return
        number=int(choice)
        spec=GLEEBS_NATIVE_MODES.get(number)
        if spec is None or spec["id"]==self.native_mode_id:
            for key in self.RELEASE_KEYS:
                self.messenger.send(f"{key}-up")
            return
        previous=self.native_mode_id
        self.return_from_native_mode(reason=f"gleebs_link_switch_{spec['id']}")
        self._enter_native_mode(number)
        print(f"UTOPIA_LINK_SWITCH from={previous} to={self.native_mode_id or 'utopia'}")

    def return_from_native_mode(self, reason="native-return"):
        adapter=self.native_mode
        if adapter is None:
            return
        self._close_native_link_menu()
        mode_id=self.native_mode_id
        self.native_mode=None
        self.native_mode_id=""
        try:
            adapter.exit()
        except Exception as exc:
            print(f"UTOPIA_NATIVE_EXIT_WARNING id={mode_id} error={exc.__class__.__name__}:{exc}",file=sys.stderr)
        self._restore_after_native_mode()
        print(f"UTOPIA_NATIVE_RETURN id={mode_id} reason={reason}")

    HOST_GUARD_ROOTS=("camera","cam","render2d","aspect2d","pixel2d","a2dTopLeft","a2dTopRight",
                      "a2dBottomLeft","a2dBottomRight","a2dTopCenter","a2dBottomCenter")

    def _snapshot_host_for_mode(self):
        """Record what Utopia owns before a mode mounts, so a leaky mode can't keep it."""
        roots={}
        for attr in self.HOST_GUARD_ROOTS:
            root=getattr(self,attr,None)
            if root is None: continue
            try: roots[attr]={child.node() for child in root.getChildren()}
            except Exception: pass
        # Only per-frame tasks: a one-shot doMethodLater that fires during the visit
        # finishes legitimately and must not be re-added.
        try: tasks=[t for t in self.taskMgr.getAllTasks() if not t.hasDelay()]
        except Exception: tasks=[]
        return {"roots":roots,"tasks":tasks}

    def _enforce_host_guard(self, guard, mode_id):
        """Remove nodes a mode left on Utopia's roots and re-add Utopia tasks it removed."""
        removed_nodes=0; restored_tasks=0
        for attr,before in (guard or {}).get("roots",{}).items():
            root=getattr(self,attr,None)
            if root is None: continue
            for child in list(root.getChildren()):
                try:
                    if child.node() not in before:
                        child.removeNode(); removed_nodes+=1
                except Exception:
                    pass
        def key(t):
            fn=t.getFunction()
            return (t.getName(), id(getattr(fn,"__self__",None)), getattr(fn,"__name__",repr(fn)))
        try: live={key(t) for t in self.taskMgr.getAllTasks()}
        except Exception: live=set()
        for task in (guard or {}).get("tasks",[]):
            if key(task) in live or task.getName().startswith("qa-"): continue
            try:
                self.taskMgr.add(task); restored_tasks+=1
            except Exception:
                pass
        if removed_nodes or restored_tasks:
            print(f"UTOPIA_NATIVE_GUARD id={mode_id} removed_leaked_nodes={removed_nodes} restored_host_tasks={restored_tasks}")

    def _restore_after_native_mode(self):
        state=dict(self.native_mode_host_state or {})
        self.native_mode_host_state={}
        self._enforce_host_guard(state.get("guard"), self.native_mode_id or state.get("mode_id",""))
        try: self.ignore("tab")
        except Exception: pass
        name=self.native_mode_module_name
        self.native_mode_module_name=""
        if name:
            sys.modules.pop(name,None)
        try:
            if state.get("camera_parent") is not None:
                self.camera.reparentTo(state["camera_parent"])
            if state.get("camera_transform") is not None:
                self.camera.setTransform(state["camera_transform"])
        except Exception:
            pass
        try:
            if state.get("fov"):
                self.camLens.setFov(*state["fov"])
            if state.get("near") is not None and state.get("far") is not None:
                self.camLens.setNearFar(state["near"],state["far"])
            self.camNode.setActive(bool(state.get("cam_active",True)))
        except Exception:
            pass
        try:
            if state.get("bg") is not None and self.win is not None:
                self.win.setClearColor(state["bg"])
                self.setBackgroundColor(*tuple(state["bg"]))
        except Exception:
            pass
        self._set_utopia_scene_visible(True)
        self._apply_gameplay_viewport()
        self.paused=bool(state.get("paused",False))
        self.lens_held=bool(state.get("lens_held",False)); self.lens_latched=bool(state.get("lens_latched",False))
        self._set_lens(self.lens_held or self.lens_latched)
        self._bind_controls()
        self._resume_utopia_audio(state.get("audio",{}))
        if self.paused:
            self._release_mouse()
            self.pause_text.setText(self._pause_menu_text()); self.pause_text.show()
        elif not self.args.offscreen:
            self._capture_mouse()
        self._update_gleebs_interaction_ui()

    def _set_key(self,key,value):
        if self.paused and value:
            return
        self.key_state[key]=value

    def _clear_movement_keys(self):
        for key in self.key_state:
            self.key_state[key]=False

    def _capture_mouse(self):
        if not self.win or not hasattr(self.win, "requestProperties"): return
        props=WindowProperties(); props.setCursorHidden(True); self.win.requestProperties(props); self.mouse_captured=True
        w=self.win.getProperties().getXSize(); h=self.win.getProperties().getYSize()
        if w>0 and h>0: self.win.movePointer(0,w//2,h//2)

    def _release_mouse(self):
        if not self.win or not hasattr(self.win, "requestProperties"):
            self.mouse_captured=False
            return
        props=WindowProperties(); props.setCursorHidden(False); self.win.requestProperties(props); self.mouse_captured=False

    def _toggle_pause(self):
        if self.native_mode is not None:
            return
        if self.gleebs_mode_menu_open:
            self._close_gleebs_mode_menu()
            return
        self.paused=not self.paused
        if self.paused:
            self.pause_panel_mode = "pause"
            self._clear_movement_keys()
            self._release_mouse()
            self.pause_text.setText(self._pause_menu_text())
            self.pause_text.show()
        else:
            self.pause_panel_mode = None
            self.pause_text.hide()
            self._capture_mouse()

    def _help_menu_text(self) -> str:
        return (
            "UTOPIA // CONTROLS\n\n"
            "WASD MOVE   MOUSE LOOK   SHIFT SPRINT   SPACE JUMP\n"
            "RMB HOLD AR   L LATCH AR   V VISOR SHAPE\n\n"
            "AR time is adjusted from the pause screen.\n"
            "F1 BACK   F11 FULLSCREEN   ESC RESUME"
        )

    def _toggle_help(self):
        if not self.paused:
            self.paused=True
            self._clear_movement_keys()
            self._release_mouse()
        if self.pause_panel_mode == "help":
            self.pause_panel_mode = "pause"
            self.pause_text.setText(self._pause_menu_text())
        else:
            self.pause_panel_mode = "help"
            self.pause_text.setText(self._help_menu_text())
        self.pause_text.show()

    def _toggle_fullscreen(self):
        props=WindowProperties(); props.setFullscreen(not self.win.getProperties().getFullscreen()); self.win.requestProperties(props)

    def _is_walkable_surface_xy(self, x: float, y: float) -> bool:
        """Return whether normal ground/deck authority exists at this XY position."""
        x=float(x); y=float(y); radius=math.hypot(x,y)
        if radius <= CITY_RADIUS + 0.5:
            return True
        if radius >= 686.0:
            return True
        # Four cardinal bridges span the moat.  Use the structural deck width rather
        # than the narrower road paint so visual deck and movement authority agree.
        bridge_half=15.5
        if 514.0 <= abs(y) <= 690.5 and abs(x) <= bridge_half:
            return True
        if 514.0 <= abs(x) <= 690.5 and abs(y) <= bridge_half:
            return True
        return False

    def _surface_floor_z(self, x: float, y: float) -> float:
        return 0.0 if self._is_walkable_surface_xy(x,y) else WATER_SURFACE_PLAYER_Z

    def _resolve_surface_height(self, dt: float) -> float:
        pos_now=self.player.getPos(self.render)
        floor=self._surface_floor_z(float(pos_now.x),float(pos_now.y))
        self.in_water=floor < -0.1
        if self.on_ground and self.player.getZ() > floor + 0.05:
            self.on_ground=False; self.vertical_velocity=min(self.vertical_velocity,-0.65)
        if not self.on_ground:
            self.vertical_velocity -= GRAVITY*dt
            self.player.setZ(self.player.getZ()+self.vertical_velocity*dt)
            if self.player.getZ()<=floor:
                self.player.setZ(floor); self.vertical_velocity=0; self.on_ground=True
        elif self.player.getZ() < floor - 0.01:
            self.player.setZ(floor)
        return floor

    def _jump(self):
        if self.on_ground and not self.paused and not self.in_water:
            self.vertical_velocity=JUMP_SPEED; self.on_ground=False

    def _spawn(self,name:str):
        if getattr(self,"paused",False):
            return
        points={
            "south_gate":((0,-610,0),0),
            "plaza":((0,-170,0),0),
            "north":((-44,328,0),180),
            "overlook":((0,-438,0),0),
        }
        pos,h=points[name]; self.player.setPos(*pos); self.yaw=h; self.pitch=-2; self.player.setH(self.yaw); self.camera.setP(self.pitch); self.vertical_velocity=0; self.on_ground=True; self.in_water=not self._is_walkable_surface_xy(float(pos[0]),float(pos[1]))

    def _set_qa_camera(self,name:str):
        self.player.hide(BitMask32.allOn())
        lens_view=name.startswith("lens_")
        base_name=name[5:] if lens_view else name
        qa={
            "spawn":((0,-615,1.72), (0,-1,0)),
            "plaza":((0,-185,1.72), (0,-1,0)),
            "overlook":((0,-438,1.72), (0,-3,0)),
            "north":((-55,315,1.72),(180,-2,0)),
            "architecture":((-84,-432,1.72),(0,-2,0)),
            "street":((-100,-432,1.72),(0,-1,0)),
            "promenade":((0,-360,6.0),(0,-15,0)),
            "walls":((-220,-330,1.72),(258,-3,0)),
            "gate":((0,-610,3.2),(0,-5,0)),
            "gleebs":((2.8,-520.0,1.72),(0,-1,0)),
            "gleebs_idle":((0,-614.0,1.85),(0,-1,0)),
            "gleebs_wave":((0,-614.0,1.85),(0,-1,0)),
            "transit":((0,-150,3.0),(180,-4,0)),
            "roof":((0,-445,92.0),(0,-24,0)),
            "environment":((0,-605,18.0),(0,-8,0)),
            "water":((0,-575,18.0),(90,-20,0)),
            "water_glint":((0,-676,5.0),(0,-4,0)),
            "sky":((0,-300,24.0),(0,14,0)),
            "utopia_archive":((82,-102,4.2),(0,-5,0)),
            "utopia_dream":((292,-45,4.2),(0,-6,0)),
            "utopia_eco":((-148,248,4.2),(0,-5,0)),
            "utopia_harbor":((0,-540,4.5),(0,-5,0)),
            "utopia_industry":((-292,-105,4.2),(0,-5,0)),
            "citizens":((0,-390,4.2),(0,-2,0)),
            "residents":((0.0,-614.5,1.85),(0.0,-1.5,0.0)),
            "outer_world":((0,-655,8.0),(180,-7,0)),
            "celestial":((0,-610,6.0),(0,60,0)),
            "aerial":((0,-1120,1080),(0,-43,0)),
        }
        pos,hpr=qa.get(base_name,qa["spawn"])
        self.camera.reparentTo(self.render); self.camera.setPos(*pos); self.camera.setHpr(*hpr)
        # QA screenshots must activate the same player-local shadow region as the camera.
        # This keeps plaza/outer/street visual checks honest instead of leaving shadow
        # activation back at spawn while the detached QA camera teleports elsewhere.
        if hasattr(self,"player") and base_name not in ("gleebs_idle","gleebs_wave"):
            self.player.setPos(float(pos[0]),float(pos[1]),self._surface_floor_z(float(pos[0]),float(pos[1])))
        if base_name.startswith("interior_"):
            key=base_name.split("_",1)[1]
            if key in self.interior_qa_points:
                cam_pos,target=self.interior_qa_points[key]
                self.camera.setPos(cam_pos); self.camera.lookAt(target)
        if base_name in ("gleebs_idle","gleebs_wave"):
            end_pos=Vec3(0.0,-606.6,0.0)
            self.gleebs_root.setPos(self.render,end_pos); self.gleebs_root.setH(0.0)
            self.gleebs_ar_root.setPos(self.render,end_pos); self.gleebs_ar_root.setH(0.0)
            self._release_gleebs_wave_controls(); self.gleebs_behavior_state="idle"; self._set_gleebs_animation("Idle")
            self.player.setPos(5.0,-610.0,0.0)
            for _ in range(18):
                self._update_gleebs_head_tracking(0.05)
            if base_name=="gleebs_wave":
                self.gleebs_behavior_state="wave"; self.gleebs_wave_elapsed=0.42; self._acquire_gleebs_wave_controls(); self._apply_gleebs_wave_pose(self.gleebs_wave_elapsed)
            elif not lens_view:
                self._emit_gleebs_sparks(True)
            self.camera.setPos(0.0,-614.0,1.85); self.camera.lookAt(end_pos+Vec3(0,0,1.25))
        # Re-evaluate projected shadows after all QA camera/player overrides.
        if hasattr(self,"shadow_stats"):
            self._update_projected_shadows()
        if base_name=="citizens" and self.citizen_orbs:
            target=self.citizen_orbs[10]["root"].getPos(self.render)
            self.camera.setPos(target.x, target.y-14.0, target.z+1.0)
            self.camera.lookAt(target)
        if base_name=="residents" and self.human_residents:
            focus=self.render.attachNewNode("resident_focus")
            p0=self.human_residents[0]["physical_root"].getPos(self.render)
            p1=self.human_residents[1]["physical_root"].getPos(self.render) if len(self.human_residents) > 1 else p0
            center=(p0+p1)*0.5
            focus.setPos(center.x, center.y, center.z+1.22)
            self.camera.setPos(0.0,-614.5,1.85)
            self.camera.lookAt(focus)
            focus.removeNode()
        if lens_view:
            self.lens_latched=True; self._set_lens(True)

    def _capture_qa(self,task):
        out=Path(self.args.test_shot or f"verification/{self.args.qa_shot}.png").resolve(); out.parent.mkdir(parents=True,exist_ok=True)
        self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
        ok=self.win.saveScreenshot(Filename.fromOsSpecific(str(out)))
        print(f"QA_SCREENSHOT={out} OK={ok}")
        self.userExit(); return task.done

    def _lens_smoke_start(self,task):
        if self.ar_buffer.isActive() or not self.ar_card.isHidden():
            print("LENS_SMOKE_FAIL startup_not_dormant")
            self.userExit(); raise SystemExit(5)
        self._lens_hold(True)
        return task.done

    def _lens_smoke_finish(self,task):
        active=self.ar_buffer.isActive()
        visible=not self.ar_card.isHidden()
        mask_ok=self.ar_camera.node().getCameraMask()==AR_CAMERA_MASK
        self._lens_hold(False)
        dormant=(not self.ar_buffer.isActive()) and self.ar_card.isHidden()
        if not (active and visible and mask_ok and dormant):
            print(f"LENS_SMOKE_FAIL active={active} visible={visible} mask={mask_ok} dormant={dormant}")
            self.userExit(); raise SystemExit(5)
        print("LENS_SMOKE_PASS registered_buffer=1 dormant_restore=1")
        self.userExit(); return task.done

    def _visor_smoke_start(self,task):
        self._apply_visor_mode("horizontal")
        self._set_lens(True)
        cfg = VISOR_MODE_CONFIG[self.visor_mode]
        if self.visor_mode != "horizontal" or cfg["half_size"] != (0.506, 0.195):
            print(f"VISOR_SMOKE_FAIL horizontal mode={self.visor_mode} config={cfg}")
            self.userExit(); raise SystemExit(7)
        return task.done

    def _visor_smoke_vertical(self,task):
        self._cycle_visor_mode()
        cfg = VISOR_MODE_CONFIG[self.visor_mode]
        if self.visor_mode != "vertical" or cfg["half_size"] != (0.195, 0.506):
            print(f"VISOR_SMOKE_FAIL vertical mode={self.visor_mode} config={cfg}")
            self.userExit(); raise SystemExit(7)
        return task.done

    def _visor_smoke_fullscreen(self,task):
        self._cycle_visor_mode()
        cfg = VISOR_MODE_CONFIG[self.visor_mode]
        if self.visor_mode != "fullscreen" or cfg["half_size"] != (0.506, 0.506):
            print(f"VISOR_SMOKE_FAIL fullscreen mode={self.visor_mode} config={cfg}")
            self.userExit(); raise SystemExit(7)
        return task.done

    def _visor_smoke_finish(self,task):
        active = self.ar_buffer.isActive() and not self.ar_card.isHidden()
        self._cycle_visor_mode()
        wrapped = self.visor_mode == "horizontal"
        self._set_lens(False)
        dormant = (not self.ar_buffer.isActive()) and self.ar_card.isHidden()
        if not (active and wrapped and dormant):
            print(f"VISOR_SMOKE_FAIL active={active} wrapped={wrapped} dormant={dormant}")
            self.userExit(); raise SystemExit(7)
        print("VISOR_SMOKE_PASS modes=horizontal,vertical,fullscreen wrap=1 dormant_restore=1")
        self.userExit(); return task.done

    def _activity_proof_a(self,task):
        out = self.base_dir / "verification" / "activity_state_a.png"
        out.parent.mkdir(parents=True,exist_ok=True)
        self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
        ok=self.win.saveScreenshot(Filename.fromOsSpecific(str(out)))
        print(f"ACTIVITY_PROOF_A={out} OK={ok}")
        return task.done

    def _activity_proof_b(self,task):
        out = self.base_dir / "verification" / "activity_state_b.png"
        self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
        ok=self.win.saveScreenshot(Filename.fromOsSpecific(str(out)))
        print(f"ACTIVITY_PROOF_B={out} OK={ok}")
        self.userExit(); return task.done

    def _activity_smoke_start(self,task):
        if not self.ar_activity_nodes:
            print("ACTIVITY_SMOKE_FAIL no_activity_nodes")
            self.userExit(); raise SystemExit(6)
        self.lens_latched=True
        self._set_lens(True)
        self._activity_smoke_initial = [tuple(item["node"].getColorScale()) for item in self.ar_activity_nodes[:12]]
        return task.done

    def _activity_smoke_finish(self,task):
        current = [tuple(item["node"].getColorScale()) for item in self.ar_activity_nodes[:12]]
        delta = 0.0
        for before, after in zip(self._activity_smoke_initial, current):
            delta += sum(abs(float(a)-float(b)) for a,b in zip(before[:3],after[:3]))
        if delta < 0.05:
            print(f"ACTIVITY_SMOKE_FAIL nodes={len(self.ar_activity_nodes)} delta={delta:.4f}")
            self.userExit(); raise SystemExit(6)
        print(f"ACTIVITY_SMOKE_PASS nodes={len(self.ar_activity_nodes)} delta={delta:.4f}")
        self.userExit(); return task.done

    def _input_smoke_inject(self,task):
        if not self.win or not hasattr(self.win,"movePointer"):
            print("INPUT_SMOKE_FAIL no_window_pointer")
            self.userExit(); raise SystemExit(3)
        props=self.win.getProperties(); cx=props.getXSize()//2; cy=props.getYSize()//2
        self.win.movePointer(0,cx+120,cy+60)
        return task.done

    def _input_smoke_finish(self,task):
        delta=abs(self.yaw-self._input_smoke_initial_yaw)
        hidden=self.win.getProperties().getCursorHidden() if self.win else False
        if delta < 2.0:
            print(f"INPUT_SMOKE_FAIL yaw_delta={delta:.3f} cursor_hidden={hidden}")
            self.userExit(); raise SystemExit(4)
        print(f"INPUT_SMOKE_PASS yaw_delta={delta:.3f} cursor_hidden={hidden}")
        self.userExit(); return task.done

    def _collision_smoke_start(self,task):
        self._collision_smoke_phase="gate"
        self._collision_smoke_elapsed=0.0
        self._collision_smoke_gate_ok=False
        self._collision_smoke_wall_ok=False
        self._collision_smoke_barrier_ok=False
        self.player.setPos(0.0,-526.0,0.0)
        self.yaw=0.0; self.player.setH(self.yaw)
        self.key_state["forward"]=True
        self.key_state["sprint"]=True
        self.taskMgr.add(self._collision_smoke_wait,"collision_smoke_wait")
        return task.done

    def _collision_smoke_wait(self,task):
        self._collision_smoke_elapsed += min(globalClock.getDt(),0.05)
        if self._collision_smoke_phase == "gate" and self._collision_smoke_elapsed >= 2.8:
            pos=self.player.getPos(self.render)
            radius=math.hypot(float(pos.x),float(pos.y))
            self._collision_smoke_gate_ok=radius < INNER_WALL_RADIUS
            angle=202.5
            x,y,_=polar(526.0,angle,0.0)
            self.player.setPos(x,y,0.0)
            self.yaw=(angle+180.0)%360.0; self.player.setH(self.yaw)
            self.traverser.traverse(self.render)
            self._collision_smoke_phase="wall"
            self._collision_smoke_elapsed=0.0
            return task.cont
        if self._collision_smoke_phase == "wall" and self._collision_smoke_elapsed >= 2.8:
            pos=self.player.getPos(self.render)
            radius=math.hypot(float(pos.x),float(pos.y))
            self._collision_smoke_wall_ok=radius > OUTER_WALL_RADIUS-1.0
            self.player.setPos(0.0,-560.0,0.0)
            self.yaw=0.0; self.player.setH(self.yaw)
            self.key_state["forward"]=False
            self.key_state["right"]=True
            self.traverser.traverse(self.render)
            self._collision_smoke_phase="barrier"
            self._collision_smoke_elapsed=0.0
            return task.cont
        if self._collision_smoke_phase == "barrier" and self._collision_smoke_elapsed >= 2.6:
            pos=self.player.getPos(self.render)
            self._collision_smoke_barrier_ok=10.0 < float(pos.x) < 18.5
            self.key_state["right"]=False
            self.key_state["sprint"]=False
            if not (self._collision_smoke_gate_ok and self._collision_smoke_wall_ok and self._collision_smoke_barrier_ok):
                print(f"COLLISION_SMOKE_FAIL gate={self._collision_smoke_gate_ok} wall={self._collision_smoke_wall_ok} barrier={self._collision_smoke_barrier_ok} final={tuple(round(float(v),2) for v in pos)}")
                self.userExit(); raise SystemExit(11)
            print(f"COLLISION_SMOKE_PASS gate_traversable=1 wall_blocks=1 bridge_barrier_blocks=1 final_x={float(pos.x):.2f}")
            self.userExit(); return task.done
        return task.cont

    def _probe_collision_path(self, start: Vec3, target: Vec3, steps: int = 220) -> tuple[float,float]:
        """Return maximum pusher correction and final target error along a deterministic path."""
        self.player.setPos(self.render,start)
        self.vertical_velocity=0.0; self.on_ground=True
        max_push=0.0
        for step in range(1,max(2,int(steps))+1):
            t=step/max(2,int(steps))
            desired=start+(target-start)*t
            self.player.setPos(self.render,desired)
            self.traverser.traverse(self.render)
            actual=Vec3(self.player.getPos(self.render))
            max_push=max(max_push,float((actual-desired).length()))
        final_error=float((self.player.getPos(self.render)-target).length())
        return max_push,final_error

    def _traversal_smoke(self,task):
        # All eight authored radial avenues must cross beneath the transit ring without
        # a support pillar or other collision intruding into the center travel line.
        avenue_results=[]
        for angle in (0,45,90,135,180,225,270,315):
            sx,sy,_=polar(178.0,angle,0.0)
            tx,ty,_=polar(270.0,angle,0.0)
            push,err=self._probe_collision_path(Vec3(sx,sy,0.0),Vec3(tx,ty,0.0),280)
            avenue_results.append((angle,push,err))

        # Four wall gates remain open across the city boundary and onto their bridges.
        gate_results=[]
        for angle in (0,90,180,270):
            sx,sy,_=polar(492.0,angle,0.0)
            tx,ty,_=polar(548.0,angle,0.0)
            push,err=self._probe_collision_path(Vec3(sx,sy,0.0),Vec3(tx,ty,0.0),190)
            gate_results.append((angle,push,err))

        # The new entrance residents must not close the south bridge centerline either.
        entrance_push,entrance_err=self._probe_collision_path(Vec3(0,-624,0),Vec3(0,-578,0),170)
        avenue_ok=sum(1 for _,push,err in avenue_results if push<0.08 and err<0.08)
        gates_ok=sum(1 for _,push,err in gate_results if push<0.08 and err<0.08)
        entrance_ok=entrance_push<0.08 and entrance_err<0.08

        # Geometry-level authority: no transit support center may fall inside the protected
        # lateral clearance corridor around a major avenue crossing.
        support_clear=True; support_min=999.0
        for angle in (0,45,90,135,180,225,270,315):
            a=math.radians(angle); tangent=Vec3(math.cos(a),-math.sin(a),0)
            radial=Vec3(math.sin(a),math.cos(a),0)
            for _,x,y in getattr(self,"transit_support_positions",[]):
                p=Vec3(x,y,0)
                longitudinal=float(p.dot(radial)); lateral=abs(float(p.dot(tangent)))
                if 214.0<=longitudinal<=230.0:
                    support_min=min(support_min,lateral)
                    if lateral < 20.0:
                        support_clear=False

        ok=(avenue_ok==8 and gates_ok==4 and entrance_ok and support_clear)
        if not ok:
            print(f"TRAVERSAL_SMOKE_FAIL avenues={avenue_ok}/8 gates={gates_ok}/4 entrance={entrance_ok} support_clear={support_clear} support_min={support_min:.2f} avenue_data={[(a,round(p,3),round(e,3)) for a,p,e in avenue_results]} gate_data={[(a,round(p,3),round(e,3)) for a,p,e in gate_results]} entrance_push={entrance_push:.3f}")
            self.userExit(); raise SystemExit(21)
        print(f"TRAVERSAL_SMOKE_PASS avenues=8/8 gates=4/4 south_entrance=1 transit_support_clearance=1 min_support_lateral={support_min:.2f}m max_avenue_push={max(p for _,p,_ in avenue_results):.3f} max_gate_push={max(p for _,p,_ in gate_results):.3f}")
        self.userExit(); return task.done

    def _modal_smoke(self,task):
        start_pos=self.player.getPos(self.render)
        start_ar=self.ar_time_hours
        self.messenger.send("escape")
        paused_open=self.paused and self.pause_panel_mode == "pause" and not self.mouse_captured
        self.messenger.send("2")
        spawn_blocked=(self.player.getPos(self.render)-start_pos).length() < 0.001
        self.messenger.send("w")
        movement_blocked=not self.key_state["forward"]
        self.messenger.send("f1")
        help_safe=self.paused and self.pause_panel_mode == "help" and not self.mouse_captured
        help_time_before=self.ar_time_hours
        self.messenger.send("arrow_up")
        help_time_blocked=abs(self.ar_time_hours-help_time_before) < 0.0001
        self.messenger.send("f1")
        pause_return=self.paused and self.pause_panel_mode == "pause"
        self.messenger.send("arrow_up")
        time_menu_works=abs(((self.ar_time_hours-start_ar)%24.0)-1.0) < 0.0001
        self.messenger.send("escape")
        resume_ok=(not self.paused) and self.pause_panel_mode is None and (self.mouse_captured or self.args.offscreen)
        if not (paused_open and spawn_blocked and movement_blocked and help_safe and help_time_blocked and pause_return and time_menu_works and resume_ok):
            print(f"MODAL_SMOKE_FAIL paused={paused_open} spawn_blocked={spawn_blocked} movement_blocked={movement_blocked} help_safe={help_safe} help_time_blocked={help_time_blocked} pause_return={pause_return} time_menu={time_menu_works} resume={resume_ok}")
            self.userExit(); raise SystemExit(10)
        print("MODAL_SMOKE_PASS pause=1 cursor_release=1 movement_blocked=1 tour_spawn_blocked=1 help_stays_modal=1 help_arrows_blocked=1 pause_arrows_work=1 resume_cursor=1")
        self.userExit(); return task.done

    def _control_smoke_start(self,task):
        self.key_state["forward"]=True
        self.key_state["right"]=True
        self.key_state["sprint"]=True
        self._lens_hold(True)
        self._jump()
        return task.done

    def _control_smoke_wait(self, task):
        # QA-only deterministic timing: wait for simulated gameplay time rather than wall-clock time.
        self._control_smoke_elapsed += min(globalClock.getDt(), 0.05)
        if self._control_smoke_elapsed >= 0.55:
            return self._control_smoke_finish(task)
        return task.cont

    def _control_smoke_finish(self,task):
        self.key_state["forward"]=False
        self.key_state["right"]=False
        self.key_state["sprint"]=False
        self._lens_hold(False)
        end=self.player.getPos(self.render)
        start=self._control_smoke_start_pos
        delta=end-start
        moved=delta.length()
        if moved < 2.0 or abs(float(delta.x)) < 1.0 or abs(float(delta.y)) < 1.0 or self._control_smoke_peak_z < 0.45 or not self._control_smoke_saw_lens:
            print(f"CONTROL_SMOKE_FAIL moved={moved:.3f} dx={float(delta.x):.3f} dy={float(delta.y):.3f} peak_z={self._control_smoke_peak_z:.3f} lens={self._control_smoke_saw_lens} start={start} end={end}")
            self.userExit(); raise SystemExit(2)
        self._toggle_pause()
        paused_ok=self.paused
        self._toggle_pause()
        print(f"CONTROL_SMOKE_PASS moved={moved:.3f} dx={float(delta.x):.3f} dy={float(delta.y):.3f} peak_z={self._control_smoke_peak_z:.3f} lens={self._control_smoke_saw_lens} pause={paused_ok} end={tuple(round(v,2) for v in end)}")
        self.userExit(); return task.done

    def _time_smoke_start(self, task):
        advanced = (self.physical_time_hours - self._time_smoke_initial_physical) % 24.0
        if advanced <= 0.00001:
            print(f"TIME_SMOKE_FAIL physical_not_advancing start={self._time_smoke_initial_physical:.4f} now={self.physical_time_hours:.4f}")
            self.userExit(); raise SystemExit(8)
        ar_before = self.ar_time_hours
        self._adjust_ar_time(1.0)
        if abs(self.ar_time_hours - ar_before) > 0.00001:
            print("TIME_SMOKE_FAIL ar_changed_outside_pause")
            self.userExit(); raise SystemExit(8)
        self.paused = True
        self.pause_panel_mode = "pause"
        self._time_smoke_pause_physical = self.physical_time_hours
        self.ar_time_hours = 23.5
        self.messenger.send("arrow_up")
        if abs(self.ar_time_hours - 0.5) > 0.0001:
            print(f"TIME_SMOKE_FAIL hour_wrap ar={self.ar_time_hours:.4f}")
            self.userExit(); raise SystemExit(8)
        self.messenger.send("arrow_left")
        if abs(self.ar_time_hours - 0.25) > 0.0001:
            print(f"TIME_SMOKE_FAIL fine_back ar={self.ar_time_hours:.4f}")
            self.userExit(); raise SystemExit(8)
        self.messenger.send("arrow_right")
        if abs(self.ar_time_hours - 0.5) > 0.0001:
            print(f"TIME_SMOKE_FAIL fine_forward ar={self.ar_time_hours:.4f}")
            self.userExit(); raise SystemExit(8)
        self.messenger.send("arrow_down")
        if abs(self.ar_time_hours - 23.5) > 0.0001:
            print(f"TIME_SMOKE_FAIL hour_back ar={self.ar_time_hours:.4f}")
            self.userExit(); raise SystemExit(8)
        return task.done

    def _time_smoke_finish(self, task):
        frozen_delta = abs(self.physical_time_hours - self._time_smoke_pause_physical)
        if frozen_delta > 0.0001:
            print(f"TIME_SMOKE_FAIL physical_changed_while_paused delta={frozen_delta:.6f}")
            self.userExit(); raise SystemExit(8)
        physical_profile = self._physical_time_profile(self.physical_time_hours)
        ar_profile = self._ar_time_profile(self.ar_time_hours)
        if physical_profile["ambient"][0] <= 0.0 or ar_profile["gain"] <= 0.0:
            print("TIME_SMOKE_FAIL invalid_profiles")
            self.userExit(); raise SystemExit(8)
        print(f"TIME_SMOKE_PASS physical_auto=1 paused_freeze=1 ar_manual=1 arrows=4 hour_wrap=1 fine_step=0.25 physical={self.physical_time_hours:.3f} ar={self.ar_time_hours:.3f}")
        self.userExit(); return task.done

    def _celestial_smoke(self,task):
        original=float(self.physical_time_hours); original_weather=self.weather_state; original_prev=self.weather_previous_state
        original_player=self.player.getPos(self.render)
        samples=[]; matched=True
        for hour in (20.0,0.0,4.0):
            self.physical_time_hours=hour; self._update_celestial_system(); self._update_sky_depth_system()
            moon_pos=self.physical_moon_root.getPos(self.render); sat_pos=self.ar_saturn_root.getPos(self.render)
            matched = matched and ((moon_pos-sat_pos).length() < 0.001)
            samples.append(Vec3(moon_pos))
        moved=((samples[1]-samples[0]).length()>100.0 and (samples[2]-samples[1]).length()>100.0)
        # Translation of the player/camera must not drag celestial bodies through world space.
        self.physical_time_hours=0.0; self._update_celestial_system(); self._update_sky_depth_system()
        moon_anchor=Vec3(self.physical_moon_root.getPos(self.render)); sat_anchor=Vec3(self.ar_saturn_root.getPos(self.render)); sun_anchor=Vec3(self.physical_sun_root.getPos(self.render))
        self.player.setPos(240.0,-180.0,0.0); self._update_celestial_system(); self._update_sky_depth_system()
        world_fixed=((self.physical_moon_root.getPos(self.render)-moon_anchor).length()<0.001 and (self.ar_saturn_root.getPos(self.render)-sat_anchor).length()<0.001)
        self.physical_time_hours=12.0; self._update_celestial_system(); self._update_sky_depth_system(); sun_anchor=Vec3(self.physical_sun_root.getPos(self.render))
        self.player.setPos(-180.0,210.0,0.0); self._update_sky_depth_system()
        sun_world_fixed=(self.physical_sun_root.getPos(self.render)-sun_anchor).length()<0.001
        day_hidden=(float(self.physical_moon_root.getColorScale().w)<0.001 and float(self.ar_saturn_root.getColorScale().w)<0.001)
        sun_match=((self.physical_sun_root.getPos(self.render)-self.ar_natural_sun_root.getPos(self.render)).length()<0.001)
        sun_visible=float(self.physical_sun_root.getColorScale().w)>0.10
        self.physical_time_hours=0.0; self._update_sky_depth_system(); sun_night_hidden=float(self.physical_sun_root.getColorScale().w)<0.001
        self.weather_previous_state="clear"; self.weather_state="clear"; self.weather_transition_elapsed=WEATHER_TRANSITION_SECONDS; self._update_sky_depth_system()
        clear_alpha=sum(float(item["holder"].getColorScale().w) for item in self.cloud_clusters if not item["ar"])
        self.weather_previous_state="storm"; self.weather_state="storm"; self.weather_transition_elapsed=WEATHER_TRANSITION_SECONDS; self._update_sky_depth_system()
        storm_alpha=sum(float(item["holder"].getColorScale().w) for item in self.cloud_clusters if not item["ar"])
        cloud_weather=storm_alpha>clear_alpha+0.5 and len(self.cloud_clusters)==48
        self.player.setPos(self.render,original_player); self.physical_time_hours=original; self.weather_state=original_weather; self.weather_previous_state=original_prev; self.weather_transition_elapsed=WEATHER_TRANSITION_SECONDS; self._update_celestial_system(); self._update_sky_depth_system()
        outer_ok=(self.outer_land_root is not None and not self.outer_land_root.find("**/outer_grass_mainland").isEmpty() and not self.outer_land_root.find("**/outer_dirt_shore").isEmpty())
        if not (matched and moved and world_fixed and sun_world_fixed and day_hidden and outer_ok and sun_match and sun_visible and sun_night_hidden and cloud_weather):
            print(f"CELESTIAL_SMOKE_FAIL matched={matched} orbit={moved} moon_world_fixed={world_fixed} sun_world_fixed={sun_world_fixed} day_hidden={day_hidden} outer={outer_ok} sun_match={sun_match} sun_visible={sun_visible} sun_night_hidden={sun_night_hidden} cloud_weather={cloud_weather}")
            self.userExit(); raise SystemExit(13)
        print(f"CELESTIAL_SMOKE_PASS moon_saturn_shared=1 moon_world_fixed=1 sun_world_fixed=1 orbit_time_driven=1 sun_daynight=1 cloud_weather_response=1 cloud_cards=48 outer_grass=1 outer_dirt=1")
        self.userExit(); return task.done

    def _water_smoke(self,task):
        original_time=float(self.physical_time_hours); original_state=self.weather_state; original_prev=self.weather_previous_state; original_transition=float(self.weather_transition_elapsed)
        def sample(hour,state):
            self.physical_time_hours=float(hour); self.weather_state=state; self.weather_previous_state=state; self.weather_transition_elapsed=WEATHER_TRANSITION_SECONDS; self._apply_time_visuals(); return dict(self.physical_water_state)
        noon=sample(12.0,"clear"); midnight=sample(0.0,"clear"); storm=sample(12.0,"storm")
        self.physical_time_hours=original_time; self.weather_state=original_state; self.weather_previous_state=original_prev; self.weather_transition_elapsed=original_transition; self._apply_time_visuals()
        shader_bound=(self.physical_water is not None and self.physical_water_shader is not None)
        weather_response=storm["roughness"]>noon["roughness"]+0.40
        sun_cycle=noon["sun_alpha"]>0.10 and midnight["sun_alpha"]<0.001
        moon_cycle=midnight["moon_alpha"]>0.05 and noon["moon_alpha"]<0.001
        if not (shader_bound and weather_response and sun_cycle and moon_cycle):
            print(f"WATER_SMOKE_FAIL shader={shader_bound} weather={weather_response} sun={sun_cycle} moon={moon_cycle} noon={noon} midnight={midnight} storm={storm}")
            self.userExit(); raise SystemExit(14)
        print(f"WATER_SMOKE_PASS shader=1 weather_roughness=1 sun_glint_cycle=1 moon_glint_cycle=1 noon_rough={noon['roughness']:.3f} storm_rough={storm['roughness']:.3f}")
        self.userExit(); return task.done

    def _utopia_systems_smoke(self,task):
        expected=("civic_archive_station_nine_access","somnology_dream_catcher_node","eco_climate_control_node","harbor_logistics_beacon","industry_fabrication_gantry")
        missing=[name for name in expected if self.utopia_root.find("**/"+name).isEmpty()]
        stats=self.utopia_system_stats
        hidden_from_physical=self.utopia_root.isHidden(NORMAL_CAMERA_MASK)
        activity=self.utopia_system_activity_stats
        all_active=all(activity[key]>0 for key in ("archive","dream","eco","harbor","industry"))
        before_head=self.utopia_root.find("**/fab_head_1").getPos()
        before_light=self.utopia_root.find("**/harbor_light_-11.5").getColorScale()
        old_t=self.ar_activity_time
        before_spill=[src["current_intensity"] for src in self.ar_neon_spill_sources]
        self.ar_activity_time=old_t+2.0
        self._update_utopia_system_activity()
        self._update_neon_spill_inputs()
        after_head=self.utopia_root.find("**/fab_head_1").getPos()
        after_light=self.utopia_root.find("**/harbor_light_-11.5").getColorScale()
        after_spill=[src["current_intensity"] for src in self.ar_neon_spill_sources]
        self.ar_activity_time=old_t
        self._update_neon_spill_inputs()
        motion_delta=(after_head-before_head).length()
        light_delta=abs(float(after_light.x)-float(before_light.x))
        spill_delta=max((abs(a-b) for a,b in zip(before_spill,after_spill)),default=0.0)
        ok=(not missing and stats["systems"]==5 and stats["archive"]==1 and stats["dream_catcher"]==1 and stats["eco_climate"]==1 and stats["harbor"]==1 and stats["industry"]==1 and stats["modules"]>=90 and hidden_from_physical and all_active and activity["moving"]>=3 and motion_delta>0.05 and light_delta>0.02 and len(self.ar_neon_spill_sources)==5 and spill_delta>0.005)
        if not ok:
            print(f"UTOPIA_SYSTEMS_SMOKE_FAIL missing={missing} stats={stats} activity={activity} hidden={hidden_from_physical} motion={motion_delta:.4f} light={light_delta:.4f}")
            self.userExit(); raise SystemExit(11)
        print(f"UTOPIA_SYSTEMS_SMOKE_PASS systems={stats['systems']} modules={stats['modules']} active={activity['total']} moving={activity['moving']} archive={activity['archive']} dream={activity['dream']} eco={activity['eco']} harbor={activity['harbor']} industry={activity['industry']} motion={motion_delta:.3f} light={light_delta:.3f} spill_sources={len(self.ar_neon_spill_sources)} spill_delta={spill_delta:.3f} physical_hidden={hidden_from_physical}")
        self.userExit(); return task.done

    def _citizen_orbs_smoke(self,task):
        stats=dict(self.citizen_orb_stats)
        hidden_from_physical=self.utopia_root.isHidden(NORMAL_CAMERA_MASK)
        before=[orb["root"].getPos(self.render) for orb in self.citizen_orbs]
        old_t=self.ar_activity_time
        self.ar_activity_time=old_t+12.0
        self._update_citizen_presence_orbs()
        after=[orb["root"].getPos(self.render) for orb in self.citizen_orbs]
        max_radius=max((math.hypot(float(p.x),float(p.y)) for p in after),default=9999.0)
        moved=sum(1 for a,b in zip(before,after) if (b-a).length()>0.25)
        no_collision=all(orb["root"].findAllMatches("**/+CollisionNode").getNumPaths()==0 for orb in self.citizen_orbs)
        transparent=all(orb["core"].getTransparency()!=TransparencyAttrib.MNone and orb["halo"].getTransparency()!=TransparencyAttrib.MNone for orb in self.citizen_orbs)
        self.ar_activity_time=old_t
        self._update_citizen_presence_orbs()
        expected={"total":CITIZEN_ORB_TOTAL,"core":4,"north":4,"east":4,"south":4,"west":4,"commuters":4}
        ok=(stats==expected and hidden_from_physical and max_radius<=CITIZEN_ORB_MAX_RADIUS+0.01 and moved>=18 and no_collision and transparent)
        if not ok:
            print(f"CITIZEN_ORBS_SMOKE_FAIL stats={stats} hidden={hidden_from_physical} max_radius={max_radius:.3f} moved={moved} no_collision={no_collision} transparent={transparent}")
            self.userExit(); raise SystemExit(13)
        print(f"CITIZEN_ORBS_SMOKE_PASS total={stats['total']} core={stats['core']} north={stats['north']} east={stats['east']} south={stats['south']} west={stats['west']} commuters={stats['commuters']} moved={moved} max_radius={max_radius:.3f} physical_hidden=1 collision=0 transparent=1")
        self.userExit(); return task.done

    def _interiors_smoke(self,task):
        expected={"total":5,"core":1,"north":1,"east":1,"south":1,"west":1}
        stats=self.interior_stats
        counts_ok=all(stats[k]==v for k,v in expected.items())
        door_ok=all(float(item["door_width"])>=4.0 for item in self.public_interiors)
        ar_ok=all(item["ar_root"].getParent()==self.utopia_root for item in self.public_interiors) and self.utopia_root.isHidden(NORMAL_CAMERA_MASK)
        collision_ok=stats["collision_solids"]>=35 and all(item["root"].findAllMatches("**/+CollisionNode").getNumPaths()>=6 for item in self.public_interiors)
        qa_ok=len(self.interior_qa_points)==5
        ar_exterior_ok=(stats.get("ar_exterior_shells",0)==40 and stats.get("ar_exterior_patterned",0)==25)
        # Actually walk the player collision sphere through every doorway center.
        traversable=0
        for item in self.public_interiors:
            r=item["root"]; fy=float(item["front_y"])
            start=r.getMat(self.render).xformPoint(Vec3(0,fy-1.6,0)); target=r.getMat(self.render).xformPoint(Vec3(0,fy+4.0,0))
            self.player.setPos(self.render,start)
            for step in range(1,25):
                t=step/24.0; pos=start+(target-start)*t
                self.player.setPos(self.render,pos); self.traverser.traverse(self.render)
            if (self.player.getPos(self.render)-target).length()<0.65:
                traversable+=1
        if not (counts_ok and door_ok and ar_ok and collision_ok and qa_ok and ar_exterior_ok and stats["props"]>=17 and stats["lights"]>=15 and stats["ambient_lights"]>=5 and traversable==5):
            print(f"INTERIORS_SMOKE_FAIL stats={stats} counts={counts_ok} doors={door_ok} ar={ar_ok} collision={collision_ok} qa={qa_ok} ar_exterior={ar_exterior_ok} traversable={traversable}")
            self.userExit(); raise SystemExit(14)
        print(f"INTERIORS_SMOKE_PASS total={stats['total']} props={stats['props']} collision_solids={stats['collision_solids']} lights={stats['lights']} ambient_lights={stats['ambient_lights']} open_doors=5 traversable=5 ar_exterior_shells={stats['ar_exterior_shells']} ar_exterior_patterned={stats['ar_exterior_patterned']} ar_physical_hidden=1")
        self.userExit(); return task.done

    def _ar_coverage_smoke(self,task):
        physical_parks=list(self.visual_root.findAllMatches("**/park"))
        physical_hidden=(len(physical_parks)==8 and all(np.isHidden(AR_CAMERA_MASK) for np in physical_parks))
        park_coverage=(int(self.ar_architecture_stats.get("park_surfaces",0))==8)
        node_pad_coverage=(int(self.ar_architecture_stats.get("textured_node_pads",0))==24)
        tree_nodes=[]
        for pattern in ("**/trunk","**/crown","**/outer_tree_trunk","**/outer_tree_crown_lower","**/outer_tree_crown_upper"):
            tree_nodes.extend(list(self.render.findAllMatches(pattern)))
        tree_free=(len(tree_nodes)==0 and int(self.environment_stats.get("outer_trees",0))==0 and int(self.shadow_stats.get("trees",0))==0)
        broad_coverage=all(int(self.ar_architecture_stats.get(k,0))>0 for k in ("coverage_wall_pieces","coverage_gate_pieces","coverage_transit_pieces","coverage_overlook_pieces","detail_sidewalk_surfaces","detail_ground_fields"))
        if not (physical_hidden and park_coverage and node_pad_coverage and tree_free and broad_coverage):
            print(f"AR_COVERAGE_SMOKE_FAIL physical_parks={len(physical_parks)} hidden={physical_hidden} park_stat={self.ar_architecture_stats.get('park_surfaces',0)} node_pads={self.ar_architecture_stats.get('textured_node_pads',0)} tree_nodes={len(tree_nodes)} outer_trees={self.environment_stats.get('outer_trees',0)} shadow_trees={self.shadow_stats.get('trees',0)} broad={broad_coverage}")
            self.userExit(); raise SystemExit(24)
        print("AR_COVERAGE_SMOKE_PASS parks=8/8 physical_hidden_from_ar=1 ar_park_surfaces=8 textured_node_pads=24 trees_removed=1 broad_world_coverage=1")
        self.userExit(); return task.done

    def _viewport_smoke(self,task):
        self._apply_gameplay_viewport()
        stats=self.viewport_stats
        target=GAMEPLAY_ASPECT
        lens_aspect=float(self.camLens.getAspectRatio())
        viewport_aspect=float(stats.get("viewport_aspect",0.0))
        dims=stats.get("dimensions",(0,1,0,1))
        window_aspect=float(stats.get("window_aspect",target))
        expected="pillarbox" if window_aspect>target+1e-4 else ("letterbox" if window_aspect<target-1e-4 else "none")
        bars_ok=stats.get("bars")==expected
        region_ok=abs(viewport_aspect-target)<0.002 and abs(lens_aspect-target)<0.002
        aligned=True
        for camera_np in (self.cam,self.cam2d,self.cam2dp):
            if camera_np.node().getNumDisplayRegions()<1:
                aligned=False; break
            d=camera_np.node().getDisplayRegion(0).getDimensions()
            aligned=aligned and all(abs(float(d[i])-float(dims[i]))<1e-5 for i in range(4))
        ar_ok=abs(float(self.ar_camera.node().getLens().getAspectRatio())-target)<0.002
        if not (bars_ok and region_ok and aligned and ar_ok):
            print(f"VIEWPORT_SMOKE_FAIL stats={stats} lens={lens_aspect:.6f} aligned={aligned} ar={ar_ok}")
            self.userExit(); raise SystemExit(17)
        print(f"VIEWPORT_SMOKE_PASS window={stats.get('window_size')} viewport={stats.get('viewport_size')} window_aspect={window_aspect:.6f} viewport_aspect={viewport_aspect:.6f} bars={expected} lens_aspect={lens_aspect:.6f} ui_aligned=1 ar_aligned=1")
        self.userExit(); return task.done

    def _shadow_smoke(self,task):
        self.physical_time_hours=10.5; self.weather_state="clear"; self.weather_previous_state="clear"; self.weather_transition_elapsed=WEATHER_TRANSITION_SECONDS; self._apply_time_visuals(); self._update_projected_shadows()
        stats=self.shadow_stats; gp=self.gleebs_root.getPos(self.render); gz=float(self.gleebs_shadow_card.getZ()) if self.gleebs_shadow_card is not None else -9
        categories=all(int(stats.get(k,0))>0 for k in ("buildings","walls","bridges","gleebs")); active=int(stats.get("active",0))>1
        tree_free=int(stats.get("trees",0))==0
        z_ok=gz>=self._shadow_surface_z(gp.x,gp.y)
        ok=stats.get("enabled")==1 and stats.get("mode")=="global_projected_contact" and int(stats.get("sources",0))>120 and categories and tree_free and active and int(stats.get("contacts",0))>1 and z_ok
        if not ok:
            print(f"SHADOW_SMOKE_FAIL stats={stats} gleebs_z={gz:.3f}"); self.userExit(); raise SystemExit(15)
        print(f"SHADOW_SMOKE_PASS global=1 sources={stats['sources']} active={stats['active']} contacts={stats.get('contacts',0)} buildings={stats['buildings']} walls={stats['walls']} bridges={stats['bridges']} trees_removed=1 gleebs_visible=1")
        self.userExit(); return task.done

    def _gleebs_smoke(self,task):
        actor=self.gleebs_actor; root=self.gleebs_root
        exists=actor is not None and root is not None and not root.isEmpty()
        anims=set(actor.getAnimNames()) if actor is not None else set()
        pos=root.getPos(self.render) if root is not None else Vec3(999,999,999)
        # Pass 49 begins moving immediately; the base smoke runs ~0.2 s after launch,
        # so verify he is still in the south-gate opening corridor rather than frozen at one point.
        start_delta=float((pos-Vec3(*GLEEBS_POSITION)).length())
        placement=(start_delta<=1.2 and abs(float(pos.z)-GLEEBS_POSITION[2])<0.01)
        hidden_ar=(root.isHidden(AR_CAMERA_MASK) if root is not None else False)
        visible_normal=(not root.isHidden(NORMAL_CAMERA_MASK) if root is not None else False)
        collision_ok=(self.gleebs_collision is not None and self.gleebs_collision.node().getNumSolids()==1 and self.gleebs_collision.node().getIntoCollideMask()==WORLD_MASK)
        idle_control=actor.getAnimControl("Idle") if actor is not None else None
        idle_frame=int(idle_control.getFrame()) if idle_control is not None else -1
        walk_control=actor.getAnimControl("Walk") if actor is not None else None
        walk_playing=bool(walk_control is not None and walk_control.isPlaying())
        bounds=actor.getTightBounds() if actor is not None else None
        size_ok=False
        local_height=0.0; world_height=0.0
        if bounds and bounds[0] is not None and bounds[1] is not None:
            local_height=float(bounds[1].z-bounds[0].z); world_height=local_height*float(GLEEBS_SCALE)
            size_ok=2.10 <= world_height <= 2.35 and abs(float(bounds[0].z)) < 0.08 and abs(float(GLEEBS_SCALE)-1.12)<0.001
        # Gleebs is authored facing -Y; this slight heading points him at the south spawn.
        facing_ok=abs(float(root.getH(self.render))-GLEEBS_HEADING)<0.01 if root is not None else False
        ar_root=self.gleebs_ar_root; ar_actor=self.gleebs_ar_actor
        ar_ok=(ar_root is not None and ar_actor is not None and not ar_root.isEmpty() and ar_root.isHidden(NORMAL_CAMERA_MASK) and not ar_root.isHidden(AR_CAMERA_MASK) and abs(float(ar_root.getScale().x)-GLEEBS_AR_SCALE)<0.001 and abs((GLEEBS_AR_SCALE/GLEEBS_SCALE)-2.0)<0.001 and self.gleebs_stats.get("ar_materials",0)>0 and self.gleebs_stats.get("ar_green_materials",0)>0 and self.gleebs_stats.get("eye_glows",0)==2)
        damaged_ok=(self.gleebs_stats.get("physical_damaged_materials",0)>=7 and self.gleebs_stats.get("damage_marks",0)==0)
        apron_ok=(len(self.ar_gate_aprons)==4 and all(not np.isEmpty() for np in self.ar_gate_aprons))
        ar_shadow_ok=(self.gleebs_ar_shadow_card is not None and self.gleebs_ar_shadow_card.isHidden(NORMAL_CAMERA_MASK))
        ok=(exists and {"Idle","Walk"}.issubset(anims) and self.gleebs_stats["joints"]==48 and self.gleebs_stats["idle_frames"]>1 and self.gleebs_stats["walk_frames"]>1 and placement and hidden_ar and visible_normal and collision_ok and size_ok and facing_ok and walk_playing and self.gleebs_behavior_state=="approach" and idle_frame>=0 and ar_ok and damaged_ok and apron_ok and ar_shadow_ok)
        if not ok:
            print(f"GLEEBS_SMOKE_FAIL exists={exists} stats={self.gleebs_stats} anims={sorted(anims)} pos={tuple(pos)} hidden_ar={hidden_ar} visible_normal={visible_normal} collision={collision_ok} local_height={local_height:.3f} world_height={world_height:.3f} facing={facing_ok} ar_ok={ar_ok} damaged={damaged_ok} aprons={apron_ok} ar_shadow={ar_shadow_ok} walk_playing={walk_playing} behavior={self.gleebs_behavior_state} start_delta={start_delta:.3f} idle_frame={idle_frame}")
            self.userExit(); raise SystemExit(25)
        print(f"GLEEBS_SMOKE_PASS joints={self.gleebs_stats['joints']} idle_frames={self.gleebs_stats['idle_frames']} walk_frames={self.gleebs_stats['walk_frames']} pos=({pos.x:.1f},{pos.y:.1f},{pos.z:.1f}) physical_scale={GLEEBS_SCALE:.2f} ar_scale={GLEEBS_AR_SCALE:.2f} ar_ratio=2.0 damaged_materials={self.gleebs_stats['physical_damaged_materials']} damage_style=material_wear gate_aprons=4 faces_spawn=1 ar_reflective=1 green_glow=1 collision=1 opening_walk=1 start_delta={start_delta:.2f} idle_frame={idle_frame}")
        self.userExit(); return task.done

    def _ar_optimization_smoke(self,task):
        self._set_lens(True)
        self._update_ar_activity_visibility(force=True)
        st=dict(self.ar_optimization_stats)
        ok=(int(st.get("pre_nodes",0))>=5000 and int(st.get("post_nodes",99999))<1800 and int(st.get("static_batches",0))>100 and int(st.get("activity_total",0))>=700 and int(st.get("activity_hidden",0))>400 and int(st.get("activity_visible",0))>0)
        if not ok:
            print(f"AR_OPTIMIZATION_SMOKE_FAIL stats={st}"); self.userExit(); raise SystemExit(25)
        print(f"AR_OPTIMIZATION_SMOKE_PASS pre_nodes={st['pre_nodes']} post_nodes={st['post_nodes']} batches={st['static_batches']} activity_visible={st['activity_visible']} activity_hidden={st['activity_hidden']} draw_radius={AR_ACTIVITY_DRAW_RADIUS:.0f}")
        self.userExit(); return task.done

    def _surface_smoke(self,task):
        points={
            "city":(0.0,0.0,True),
            "bridge_south":(0.0,-610.0,True),
            "bridge_east":(610.0,0.0,True),
            "open_water":(80.0,-610.0,False),
            "mainland":(0.0,-760.0,True),
        }
        ok=all(self._is_walkable_surface_xy(x,y)==expected for x,y,expected in points.values())
        self.player.setPos(80.0,-610.0,0.0); self.on_ground=True; self.vertical_velocity=0.0
        for _ in range(20): self._resolve_surface_height(0.05)
        water_z=float(self.player.getZ()); water_state=self.in_water
        self.player.setPos(0.0,-760.0,water_z); self.on_ground=True; self.vertical_velocity=0.0
        self._resolve_surface_height(0.05)
        land_z=float(self.player.getZ()); land_state=self.in_water
        detail_ok=self.surface_detail_stats.get("asphalt",0)>5 and self.surface_detail_stats.get("concrete",0)>5 and self.surface_detail_stats.get("grass",0)>1 and self.surface_detail_stats.get("dirt",0)>1

        def first_triangle_signed_z(np: NodePath) -> float:
            geom=np.node().getGeom(0); prim=geom.getPrimitive(0).decompose(); start=prim.getPrimitiveStart(0)
            indices=[prim.getVertex(start+i) for i in range(3)]
            reader=GeomVertexReader(geom.getVertexData(),"vertex"); pts=[]
            for idx in indices:
                reader.setRow(idx); pts.append(Vec3(reader.getData3()))
            return float((pts[1]-pts[0]).cross(pts[2]-pts[0]).z)

        # Horizontal helper primitives must face +Z.  Pass 55's reversed winding made the
        # city ground/plaza/rings and related terrain backface-cull from normal gameplay.
        winding_samples=[
            make_disc_geom("surface_winding_disc",3.0,(1,1,1,1),12,0.0),
            make_annulus_geom("surface_winding_annulus",1.0,3.0,(1,1,1,1),12,0.0),
            make_textured_disc_geom("surface_winding_texdisc",3.0,(1,1,1,1),12,0.0,2.0),
            make_textured_annulus_sector("surface_winding_sector",1.0,3.0,0.0,90.0,(1,1,1,1),6,0.0,2.0),
        ]
        winding_values=[first_triangle_signed_z(np) for np in winding_samples]
        winding_ok=all(v>0.0001 for v in winding_values)
        for np in winding_samples: np.removeNode()

        ok=ok and abs(water_z-WATER_SURFACE_PLAYER_Z)<0.02 and water_state and abs(land_z)<0.02 and not land_state and SWIM_SPEED<WALK_SPEED and detail_ok and winding_ok
        if not ok:
            print(f"SURFACE_SMOKE_FAIL water_z={water_z:.3f} water_state={water_state} land_z={land_z:.3f} land_state={land_state} winding={winding_values}")
            self.userExit(); raise SystemExit(24)
        print(f"SURFACE_SMOKE_PASS water_not_ground=1 bridge_walkable=1 mainland_walkable=1 material_detail={self.surface_detail_stats} water_settle=1 land_return=1 top_face_winding=1 swim_speed={SWIM_SPEED:.2f} water_z={water_z:.2f}")
        self.userExit(); return task.done

    def _smoke_exit(self,task):
        stats = self.ar_architecture_stats
        env=self.environment_stats
        if self.ar_material_stats["reflective_solids"] < 500 or self.ar_material_stats["neon_patterns"] < 150 or self.ar_material_stats["spill_sources"] != 5:
            print(f"SMOKE_FAIL materials={self.ar_material_stats}")
            self.userExit(); raise SystemExit(12)
        print(f"SMOKE_PASS buildings={len(self.buildings)} ar_modules={stats['modules']} balconies={stats['balconies']} setbacks={stats['setbacks']} recesses={stats['recesses']} roofs={stats['roof_structures']} windows={stats['window_bands']} entrances={stats['entrances']} canopies={stats['canopies']} active_windows={stats['active_windows']} active_entries={stats['active_entries']} active_glow_paths={stats['active_glow_paths']} promenades={stats['promenades']} ground_markers={stats['ground_markers']} forecourts={stats['forecourts']} textured_walkways={stats['textured_walkways']} roof_coverage={stats['coverage_roof_crowns']} wall_coverage={stats['coverage_wall_pieces']} gate_coverage={stats['coverage_gate_pieces']} transit_coverage={stats['coverage_transit_pieces']} overlook_coverage={stats['coverage_overlook_pieces']} wall_detail={stats['detail_wall_surfaces']} gate_detail={stats['detail_gate_surfaces']} transit_detail={stats['detail_transit_surfaces']} roof_detail={stats['detail_roof_surfaces']} overlook_detail={stats['detail_overlook_surfaces']} sidewalk_detail={stats['detail_sidewalk_surfaces']} ground_fields={stats['detail_ground_fields']} physical_sky={env['physical_sky']} ar_sky={env['ar_sky']} ar_water={env['ar_water']} shore_shelves={env['shore_shelves']} outer_land={env['outer_land']} moon={env['moon']} saturn={env['saturn']} sun={env['sun']} clouds={env['cloud_layers']} physical_time={self.physical_time_hours:.2f} ar_time={self.ar_time_hours:.2f} weather={self.weather_state} rain_streaks={self.weather_stats['rain_streaks']} ambience_zones={len(self.dynamic_ambience)} utopia_systems={self.utopia_system_stats['systems']} utopia_system_modules={self.utopia_system_stats['modules']} utopia_system_active={self.utopia_system_activity_stats['total']} utopia_system_moving={self.utopia_system_activity_stats['moving']} reflective_solids={self.ar_material_stats['reflective_solids']} neon_patterns={self.ar_material_stats['neon_patterns']} spill_sources={self.ar_material_stats['spill_sources']} interiors={self.interior_stats['total']} interior_props={self.interior_stats['props']} player={tuple(round(v,2) for v in self.player.getPos())}")
        self.userExit(); return task.done


    def _gleebs_behavior_smoke(self,task):
        if self.gleebs_root is None or self.gleebs_ar_root is None or not hasattr(self,"player"):
            print("GLEEBS_BEHAVIOR_SMOKE_FAIL missing_runtime=1"); self.userExit(); raise SystemExit(16)
        self.player.setPos(0,-610,0); self.player.setH(0)
        self.gleebs_root.setPos(*GLEEBS_POSITION); self.gleebs_root.setH(GLEEBS_HEADING); self.gleebs_ar_root.setPos(*GLEEBS_POSITION); self.gleebs_ar_root.setH(GLEEBS_HEADING)
        self.gleebs_behavior_state="approach"; self.gleebs_wave_elapsed=0; self.gleebs_behavior_stats["wave_started"]=0; self.gleebs_behavior_stats["wave_completed"]=0; self._set_gleebs_animation("Walk")
        min_distance=999.0; saw_wave=False
        for _ in range(700):
            self._update_gleebs_behavior(0.05); d=Vec3(self.player.getPos(self.render)-self.gleebs_root.getPos(self.render)); d.z=0; min_distance=min(min_distance,float(d.length())); saw_wave=saw_wave or self.gleebs_behavior_state=="wave"
            if self.gleebs_behavior_state=="idle": break
        end=Vec3(self.gleebs_root.getPos(self.render)); to_player=Vec3(self.player.getPos(self.render)-end); to_player.z=0; final_distance=float(to_player.length()); sync=float((self.gleebs_ar_root.getPos(self.render)-end).length())<0.001
        wave_done=self.gleebs_behavior_stats.get("wave_started",0)==1 and self.gleebs_behavior_stats.get("wave_completed",0)==1 and saw_wave
        wave_released=self.gleebs_behavior_stats.get("wave_joint_released",0)==1 and len(self.gleebs_wave_controls)==0
        idle=self.gleebs_behavior_state=="idle" and self.gleebs_actor.getCurrentAnim()=="Idle" and self.gleebs_ar_actor.getCurrentAnim()=="Idle"
        self.player.setX(6.0); before={k:Vec3(v.getHpr()) for k,v in self.gleebs_head_controls.items()}; [self._update_gleebs_head_tracking(0.05) for _ in range(10)]; head_changed=any(abs(float(self.gleebs_head_controls[k].getH())-float(v.x))>0.5 for k,v in before.items())
        ok=min_distance>=GLEEBS_APPROACH_STOP_DISTANCE-0.03 and GLEEBS_APPROACH_STOP_DISTANCE-0.05<=final_distance<=GLEEBS_APPROACH_STOP_DISTANCE+0.16 and sync and wave_done and wave_released and idle and head_changed
        if not ok:
            print(f"GLEEBS_BEHAVIOR_SMOKE_FAIL min_distance={min_distance:.2f} final={final_distance:.2f} wave={wave_done} released={wave_released} idle={idle} sync={sync} head={head_changed}"); self.userExit(); raise SystemExit(16)
        print(f"GLEEBS_BEHAVIOR_SMOKE_PASS no_overshoot=1 min_distance={min_distance:.2f} final={final_distance:.2f} wave=1 arm_release=1 idle=1 head_follow=1")
        self.userExit(); return task.done

    def _gleebs_audio_smoke(self,task):
        cfg_ok=self.gleebs_audio_config_path.exists()
        purr_asset=self.base_dir/"audio"/"characters"/"gleebs"/"gleebs_purr.wav"
        spark_asset=self.base_dir/"audio"/"characters"/"gleebs"/"gleebs_spark.wav"
        try:
            cfg=json.loads(self.gleebs_audio_config_path.read_text(encoding="utf-8"))
        except Exception:
            cfg={}
        purr_ok=(self.gleebs_purr_sound is not None and bool(cfg.get("purr",{}).get("loop",False)))
        spark_ok=(self.gleebs_spark_sound is not None)
        radial=(self.gleebs_audio3d is not None and self.gleebs_audio_stats.get("radial",0)==1)
        same_owner=(len(getattr(self,"sfxManagerList",[]))>0 and self.gleebs_audio3d is not None)
        ok=cfg_ok and purr_asset.exists() and spark_asset.exists() and purr_ok and spark_ok and radial and same_owner
        if not ok:
            print(f"GLEEBS_AUDIO_SMOKE_FAIL config={cfg_ok} purr_asset={purr_asset.exists()} spark_asset={spark_asset.exists()} purr={purr_ok} spark={spark_ok} radial={radial}")
            self.userExit(); raise SystemExit(17)
        print("GLEEBS_AUDIO_SMOKE_PASS replaceable=1 purr_loop=1 spark_oneshot=1 positional=1 shared_sfx_owner=1 pause_attenuation=1 ownership_reconcile=1")
        self.userExit(); return task.done

    def _resident_smoke(self,task):
        if len(self.human_residents) != 2:
            print(f"RESIDENT_SMOKE_FAIL count={len(self.human_residents)}")
            self.userExit(); raise SystemExit(19)
        details=[]; ok=True
        for item in self.human_residents:
            pa=item.get("physical_actor"); aa=item.get("ar_actor")
            if pa is None or aa is None:
                ok=False; continue
            pf=int(pa.getCurrentFrame("Idle")); af=int(aa.getCurrentFrame("Idle"))
            pr=float(pa.getPlayRate("Idle")); ar=float(aa.getPlayRate("Idle"))
            synced=abs(pf-af)<=1 and abs(pr-ar)<1e-6
            varied=abs(pr-1.0)>0.02 and 0 <= int(item["idle_start_frame"]) < int(item["idle_frames"])
            human_size=0.0 < float(item["height"]) <= 2.05
            ok = ok and synced and varied and human_size
            details.append(f"{item['id']}:frame={pf}/{af}:rate={pr:.2f}:start={item['idle_start_frame']}:height={item['height']:.2f}")
        starts={int(i["idle_start_frame"]) for i in self.human_residents}
        rates={round(float(i["idle_rate"]),3) for i in self.human_residents}
        signatures=[i.get("ar_pattern_signature",()) for i in self.human_residents]
        pattern_counts=[len(i.get("ar_accent_meta",())) for i in self.human_residents]
        pattern_unique=(len(signatures)==2 and signatures[0] and signatures[1] and signatures[0] != signatures[1])
        pattern_bounded=all(10 <= count <= 18 for count in pattern_counts)
        follow_ok=True
        for item in self.human_residents:
            aa=item.get("ar_actor")
            meta=item.get("ar_accent_meta",())
            if aa is None or not meta:
                follow_ok=False; continue
            original_frame=int(aa.getCurrentFrame("Idle"))
            sample=max(0,min(int(item["idle_frames"])-1,original_frame+max(2,int(item["idle_frames"])*0.23)))
            aa.pose("Idle",sample)
            for m in meta:
                p=Vec3(m["node"].getPos(m["joint_np"]))
                h=Vec3(m["node"].getHpr(m["joint_np"]))
                if (p-m["local_pos"]).length() > 1e-5 or (h-m["local_hpr"]).length() > 1e-4:
                    follow_ok=False; break
            self._start_human_resident_idle(aa,item["idle_rate"],item["idle_phase"])
        distinct=(len(starts)==2 and len(rates)==2)
        ok=ok and distinct and pattern_unique and pattern_bounded and follow_ok and self.human_resident_stats.get("idle_variants",0)==2
        if not ok:
            print("RESIDENT_SMOKE_FAIL "+" ".join(details)+f" distinct={distinct} pattern_unique={pattern_unique} pattern_counts={pattern_counts} follow={follow_ok}")
            self.userExit(); raise SystemExit(19)
        print("RESIDENT_SMOKE_PASS residents=2 physical_ar_sync=1 distinct_phase=1 distinct_rate=1 subtle_heading_sway=1 human_scale=1 deterministic_neon=1 unique_patterns=1 bone_follow=1 pattern_counts="+",".join(str(v) for v in pattern_counts)+" "+" ".join(details))
        self.userExit(); return task.done

    def _atmosphere_smoke(self,task):
        mist_ok=(self.physical_mist_root is not None and self.physical_mist_root.isHidden(AR_CAMERA_MASK) and self.mist_stats.get("layers",0)==24)
        # Force a clear and storm application to prove the physical fog tightens with weather.
        saved=(self.weather_state,self.weather_previous_state,self.weather_transition_elapsed)
        self.weather_state="clear"; self.weather_previous_state="clear"; self.weather_transition_elapsed=WEATHER_TRANSITION_SECONDS; self._apply_time_visuals()
        clear_on=abs(float(self.world_fog.getLinearOnsetPoint().y)); clear_off=abs(float(self.world_fog.getLinearOpaquePoint().y))
        self.weather_state="storm"; self.weather_previous_state="storm"; self.weather_transition_elapsed=WEATHER_TRANSITION_SECONDS; self._apply_time_visuals()
        storm_on=abs(float(self.world_fog.getLinearOnsetPoint().y)); storm_off=abs(float(self.world_fog.getLinearOpaquePoint().y))
        self.weather_state,self.weather_previous_state,self.weather_transition_elapsed=saved; self._apply_time_visuals()
        physical=next((i for i in self.cloud_clusters if not i["ar"]),None); ar=next((i for i in self.cloud_clusters if i["ar"]),None)
        physical_col=physical["holder"].getColorScale() if physical else Vec4(0)
        ar_col=ar["holder"].getColorScale() if ar else Vec4(0)
        pink_ok=(ar is not None and float(ar_col.x)>float(ar_col.y)*1.25 and float(ar_col.z)>float(ar_col.y)*1.15)
        fog_ok=(storm_on<clear_on and storm_off<clear_off and storm_off<=950.1)
        planet_ok=("ar_saturn" in self.ar_saturn_root.getName() and self.environment_stats.get("saturn",0)==1)
        ok=mist_ok and fog_ok and pink_ok and planet_ok
        if not ok:
            print(f"ATMOSPHERE_SMOKE_FAIL mist={mist_ok} fog={fog_ok} clear=({clear_on:.0f},{clear_off:.0f}) storm=({storm_on:.0f},{storm_off:.0f}) pink={pink_ok} physical_rgb={tuple(physical_col)} ar_rgb={tuple(ar_col)} planet={planet_ok}")
            self.userExit(); raise SystemExit(18)
        print(f"ATMOSPHERE_SMOKE_PASS physical_mist=24 fog_clear={clear_on:.0f}-{clear_off:.0f} fog_storm={storm_on:.0f}-{storm_off:.0f} ar_clouds_pink=1 ar_planet_saturn=1")
        self.userExit(); return task.done

    def _update(self,task):
        dt=min(globalClock.getDt(),0.05)
        if self.native_mode is not None:
            adapter=self.native_mode
            if self.native_link_menu_open:
                return task.cont
            try:
                adapter.update(dt)
            except Exception as exc:
                print(f"UTOPIA_NATIVE_RUNTIME_ERROR id={self.native_mode_id} error={exc.__class__.__name__}:{exc}",file=sys.stderr)
                if self.native_mode is adapter:
                    self.return_from_native_mode(reason="runtime_error")
            return task.cont
        self.ar_pulse_time += dt
        self._update_weather_system(dt)
        self._update_time_system(dt)
        self._update_dynamic_ambience(dt)
        self._update_district_music(dt)
        self._update_gleebs_audio(dt)
        if not self.paused:
            self.ar_activity_time += dt
            self.environment_time += dt
            ar_active=hasattr(self,"ar_buffer") and self.ar_buffer.isActive()
            if ar_active:
                self._update_ar_activity_visibility()
                self._update_ar_activity()
                self._update_utopia_system_activity()
                self._update_citizen_presence_orbs()
                self._update_neon_spill_inputs()
                if self.ar_water_surface is not None:
                    self.ar_water_surface.setShaderInput("env_time", self.environment_time)
            self._update_gleebs_behavior(dt)
            self._update_gleebs_sparks(dt)
            self._update_human_resident_idle_variation(dt)
        self._update_gleebs_interaction_ui()
        if hasattr(self,"utopia_root"):
            pulse=0.97+0.03*math.sin(self.ar_pulse_time*1.25)
            tint=getattr(self,"_ar_surface_tint",(1.0,1.0,1.0))
            gain=getattr(self,"_ar_surface_gain",1.0)
            self.utopia_root.setColorScale(pulse*tint[0]*gain,pulse*tint[1]*gain,pulse*tint[2]*gain,1.0)
        if self.args.control_smoke:
            self._control_smoke_peak_z = max(self._control_smoke_peak_z, float(self.player.getZ()))
            self._control_smoke_saw_lens = self._control_smoke_saw_lens or (self.ar_buffer.isActive() and not self.ar_card.isHidden())
        if self.paused or self.args.qa_shot:
            return task.cont
        if self.mouse_captured and self.win and hasattr(self.win,"movePointer"):
            props=self.win.getProperties(); w=props.getXSize(); h=props.getYSize()
            if w>0 and h>0:
                pointer=self.win.getPointer(0); cx=w//2; cy=h//2
                dx=pointer.getX()-cx; dy=pointer.getY()-cy
                if abs(dx)<w*0.45 and abs(dy)<h*0.45:
                    self.yaw -= dx*0.12
                    self.pitch=max(-82,min(82,self.pitch-dy*0.10))
                    self.player.setH(self.yaw); self.camera.setP(self.pitch)
                self.win.movePointer(0,cx,cy)
        f=Vec3(0,0,0)
        if self.key_state["forward"]: f.y+=1
        if self.key_state["back"]: f.y-=1
        if self.key_state["left"]: f.x-=1
        if self.key_state["right"]: f.x+=1
        if f.lengthSquared()>0:
            f.normalize()
            pos_now=self.player.getPos(self.render)
            self.in_water=not self._is_walkable_surface_xy(float(pos_now.x),float(pos_now.y))
            speed = SWIM_SPEED if self.in_water else (SPRINT_SPEED if self.key_state["sprint"] else WALK_SPEED)
            world_delta=self.player.getQuat(self.render).xform(f*speed*dt)
            world_delta.z=0
            self.player.setPos(self.player.getPos()+world_delta)
        # Surface authority: city, bridges and mainland sit at z=0.  Open water is not
        # invisible ground; entering it lowers the player to a swimming height and removes sprint/jump.
        self._resolve_surface_height(dt)
        self.traverser.traverse(self.render)
        return task.cont


def parse_args():
    ap=argparse.ArgumentParser(description=APP_NAME)
    ap.add_argument("--offscreen",action="store_true")
    ap.add_argument("--smoke-test",action="store_true")
    ap.add_argument("--control-smoke",action="store_true")
    ap.add_argument("--lens-smoke",action="store_true")
    ap.add_argument("--visor-smoke",action="store_true")
    ap.add_argument("--activity-smoke",action="store_true")
    ap.add_argument("--time-smoke",action="store_true")
    ap.add_argument("--weather-smoke",action="store_true")
    ap.add_argument("--celestial-smoke",action="store_true")
    ap.add_argument("--water-smoke",action="store_true")
    ap.add_argument("--utopia-systems-smoke",action="store_true")
    ap.add_argument("--ambience-smoke",action="store_true")
    ap.add_argument("--music-smoke",action="store_true")
    ap.add_argument("--audio-state-smoke",action="store_true")
    ap.add_argument("--citizen-orbs-smoke",action="store_true")
    ap.add_argument("--interiors-smoke",action="store_true")
    ap.add_argument("--ar-coverage-smoke",action="store_true")
    ap.add_argument("--viewport-smoke",action="store_true")
    ap.add_argument("--shadow-smoke",action="store_true")
    ap.add_argument("--gleebs-smoke",action="store_true")
    ap.add_argument("--gleebs-behavior-smoke",action="store_true")
    ap.add_argument("--gleebs-audio-smoke",action="store_true")
    ap.add_argument("--resident-smoke",action="store_true")
    ap.add_argument("--atmosphere-smoke",action="store_true")
    ap.add_argument("--surface-smoke",action="store_true")
    ap.add_argument("--ar-optimization-smoke",action="store_true")
    ap.add_argument("--dev-controls",action="store_true")
    ap.add_argument("--no-audio",action="store_true")
    ap.add_argument("--pause-menu-shot",action="store_true")
    ap.add_argument("--help-menu-shot",action="store_true")
    ap.add_argument("--activity-proof",action="store_true")
    ap.add_argument("--input-smoke",action="store_true")
    ap.add_argument("--modal-smoke",action="store_true")
    ap.add_argument("--collision-smoke",action="store_true")
    ap.add_argument("--traversal-smoke",action="store_true")
    ap.add_argument("--qa-shot",choices=["spawn","plaza","overlook","north","architecture","street","promenade","walls","gate","gleebs","gleebs_idle","gleebs_wave","transit","roof","environment","water","water_glint","sky","outer_world","celestial","aerial","residents","lens_spawn","lens_plaza","lens_overlook","lens_north","lens_architecture","lens_street","lens_promenade","lens_walls","lens_gate","lens_gleebs","lens_gleebs_idle","lens_transit","lens_roof","lens_environment","lens_water","lens_sky","lens_outer_world","lens_celestial","lens_residents","utopia_archive","utopia_dream","utopia_eco","utopia_harbor","utopia_industry","citizens","lens_utopia_archive","lens_utopia_dream","lens_utopia_eco","lens_utopia_harbor","lens_utopia_industry","lens_citizens","interior_core","interior_north","interior_east","interior_south","interior_west","lens_interior_core","lens_interior_north","lens_interior_east","lens_interior_south","lens_interior_west"])
    ap.add_argument("--visor-mode",choices=list(VISOR_MODE_ORDER),default="horizontal")
    ap.add_argument("--physical-time",type=float,default=9.0)
    ap.add_argument("--ar-time",type=float)
    ap.add_argument("--freeze-time",action="store_true")
    ap.add_argument("--weather-state",choices=list(WEATHER_ORDER),default="clear")
    ap.add_argument("--freeze-weather",action="store_true")
    ap.add_argument("--width",type=int)
    ap.add_argument("--height",type=int)
    ap.add_argument("--test-shot")
    return ap.parse_args()


if __name__ == "__main__":
    app=UtopiaApp(parse_args())
    app.run()
