"""
Starfall Salvage - Robot Research Interior Pass
Panda3D 1.10.16 / Python 3.13+

Focus of this pass:
- Preserve the cool procedural ship exterior and first-person interior.
- Preserve the anomaly chunk-warp loop.
- Keep every warp destination as a procedural, explorable solar system.
- Space major celestial bodies even farther apart so systems feel vast instead of crowded.
- Always generate one nearby hero planet with richer surface, atmosphere, moons/rings, fly-by detail, and local orbital points of interest.
- Place a natural black-hole return gateway behind the player so the next system is reached by turning back and warping again.
- Keep the natural galaxy/anomaly direction from Pass 08.
- Keep all geometry generated in Panda3D for stable iteration.
"""

from __future__ import annotations
# Build: 114

import argparse
import importlib.util
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from direct.gui.OnscreenText import OnscreenText
from direct.gui.DirectButton import DirectButton
from direct.showbase.ShowBase import ShowBase

try:
    from holoverse_link import install_exit_report, quit_label, report_to_holoverse
except Exception:  # standalone copies without the bridge keep working
    def install_exit_report(provider): return None
    def quit_label(standalone='QUIT'): return standalone
    def report_to_holoverse(**kw): return False
from direct.task import Task
from panda3d.core import (
    AmbientLight,
    AntialiasAttrib,
    BitMask32,
    CardMaker,
    ColorAttrib,
    ClockObject,
    DirectionalLight,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LineSegs,
    Material,
    NodePath,
    Point2,
    PointLight,
    TextNode,
    TransparencyAttrib,
    Vec3,
    Vec4,
    WindowProperties,
    Filename,
    loadPrcFileData,
)


# -----------------------------
# Panda3D configuration
# -----------------------------
def configure_panda(headless: bool = False) -> None:
    # StarFall shell and moon operations now share the same HoloVerse-style
    # display authority: fixed 16:9 preset windows plus centered safe HUD canvas.
    try:
        worlds_path = Path(__file__).resolve().parent / "Worlds"
        if str(worlds_path) not in sys.path:
            sys.path.insert(0, str(worlds_path))
        from display_config import apply_panda_window_config
        apply_panda_window_config(loadPrcFileData, "Operation StarFall", sys.argv)
    except Exception:
        loadPrcFileData("", "window-title Operation StarFall")
        loadPrcFileData("", "win-size 1920 1080")
        loadPrcFileData("", "fullscreen #f")
        loadPrcFileData("", "undecorated #f")
        loadPrcFileData("", "win-fixed-size #f")
    try:
        from settings_authority import apply_prc_optimization
        apply_prc_optimization(loadPrcFileData, Path(__file__).resolve().parent, sys.argv, headless=headless)
    except Exception:
        loadPrcFileData("", "sync-video false")
        loadPrcFileData("", "show-frame-rate-meter true")
        loadPrcFileData("", "framebuffer-multisample false")
        loadPrcFileData("", "multisamples 0")
        loadPrcFileData("", "garbage-collect-states true")
        loadPrcFileData("", "state-cache true")
        loadPrcFileData("", "transform-cache true")
        loadPrcFileData("", "textures-power-2 up")
    # Pass41 audio authority: normal play may use Panda3D/OpenAL audio, while
    # screenshots, headless tests, and explicit --no-audio runs stay silent.
    if headless or "--no-audio" in sys.argv:
        loadPrcFileData("", "audio-library-name null")
    else:
        loadPrcFileData("", "audio-library-name p3openal_audio")
    if headless:
        loadPrcFileData("", "window-type offscreen")
        loadPrcFileData("", "show-frame-rate-meter false")
        # Under Xvfb, keep Panda3D on the GLX pipe so normal NPOT runtime
        # textures are exercised exactly as they are in the real game. Fall
        # back to tinydisplay only when there is no display server at all.
        if not os.environ.get("DISPLAY"):
            loadPrcFileData("", "load-display p3tinydisplay")


# -----------------------------
# Performance profile
# -----------------------------
# Pass 16 defaults to fast detail for 60 FPS targeting.  Set
# STARFALL_DETAIL=balanced to restore the heavier visual profile.
STARFALL_DETAIL_PROFILE = os.environ.get("STARFALL_DETAIL", "fast").strip().lower()
STARFALL_FAST_PROFILE = STARFALL_DETAIL_PROFILE in {"fast", "performance", "low", "60", "60fps"}

# Pass103: interior-first presentation authority.  Heading 180 faces the
# forward viewport at local -Y; heading 0 faces the rear economy console.
INTERIOR_SPAWN_HEADING = 180.0


def perf_segments(value: int, minimum: int = 8, maximum_fast: int | None = None) -> int:
    value = int(value)
    if not STARFALL_FAST_PROFILE:
        return value
    capped = max(minimum, int(value * 0.58))
    if maximum_fast is not None:
        capped = min(capped, maximum_fast)
    return capped


def perf_count(value: int, minimum: int = 1) -> int:
    value = int(value)
    if not STARFALL_FAST_PROFILE:
        return value
    return max(minimum, int(value * 0.60))


# -----------------------------
# Geometry helpers
# -----------------------------
def make_mat(color: Vec4, emission: Vec4 | None = None, roughness: float = 0.45) -> Material:
    mat = Material()
    mat.setDiffuse(color)
    mat.setAmbient(color * 0.65)
    mat.setSpecular(Vec4(0.8, 0.9, 1.0, 1.0))
    mat.setShininess(32.0 if roughness < 0.5 else 12.0)
    if emission is not None:
        mat.setEmission(emission)
    return mat


def apply_mat(np: NodePath, color: tuple[float, float, float, float], emission: tuple[float, float, float, float] | None = None) -> None:
    np.setColor(*color)
    np.setMaterial(make_mat(Vec4(*color), Vec4(*emission) if emission else None), 1)
    if color[3] < 1.0:
        np.setTransparency(TransparencyAttrib.M_alpha)


def create_box(parent: NodePath, name: str, pos: Vec3, scale: Vec3, color: tuple[float, float, float, float], hpr: Vec3 = Vec3(0, 0, 0), emission: tuple[float, float, float, float] | None = None) -> NodePath:
    fmt = GeomVertexFormat.getV3n3()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")

    sx, sy, sz = scale.x / 2.0, scale.y / 2.0, scale.z / 2.0
    faces = [
        # normal, corners
        (Vec3(0, -1, 0), [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, -sy, sz), (-sx, -sy, sz)]),
        (Vec3(0, 1, 0), [(sx, sy, -sz), (-sx, sy, -sz), (-sx, sy, sz), (sx, sy, sz)]),
        (Vec3(-1, 0, 0), [(-sx, sy, -sz), (-sx, -sy, -sz), (-sx, -sy, sz), (-sx, sy, sz)]),
        (Vec3(1, 0, 0), [(sx, -sy, -sz), (sx, sy, -sz), (sx, sy, sz), (sx, -sy, sz)]),
        (Vec3(0, 0, 1), [(-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]),
        (Vec3(0, 0, -1), [(-sx, sy, -sz), (sx, sy, -sz), (sx, -sy, -sz), (-sx, -sy, -sz)]),
    ]
    tris = GeomTriangles(Geom.UHStatic)
    idx = 0
    for n, corners in faces:
        for c in corners:
            vertex.addData3f(*c)
            normal.addData3f(n)
        tris.addVertices(idx, idx + 1, idx + 2)
        tris.addVertices(idx, idx + 2, idx + 3)
        idx += 4

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    np = parent.attachNewNode(node)
    np.setPos(pos)
    np.setHpr(hpr)
    apply_mat(np, color, emission)
    return np


def create_trapezoid_prism(parent: NodePath, name: str, pos: Vec3, length: float, root_width: float, tip_width: float, thickness: float, color: tuple[float, float, float, float], side: int = 1, hpr: Vec3 = Vec3(0, 0, 0), emission: tuple[float, float, float, float] | None = None) -> NodePath:
    """Creates a swept wing-like prism in local XY with small Z thickness."""
    fmt = GeomVertexFormat.getV3n3()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    zt = thickness / 2.0
    # Local wing starts near fuselage at y=0 and sweeps backward to y=-length.
    # side=1 right, side=-1 left.
    points_top = [
        (0.0, 0.0, zt),
        (side * root_width, -0.55, zt),
        (side * tip_width, -length, zt),
        (0.0, -length * 0.72, zt),
    ]
    points_bottom = [(x, y, -zt) for x, y, _ in points_top]

    faces = [
        (Vec3(0, 0, 1), points_top),
        (Vec3(0, 0, -1), list(reversed(points_bottom))),
        (Vec3(0, -1, 0), [points_top[0], points_bottom[0], points_bottom[1], points_top[1]]),
        (Vec3(side, 0, 0), [points_top[1], points_bottom[1], points_bottom[2], points_top[2]]),
        (Vec3(0, -1, 0), [points_top[2], points_bottom[2], points_bottom[3], points_top[3]]),
        (Vec3(-side, 0, 0), [points_top[3], points_bottom[3], points_bottom[0], points_top[0]]),
    ]
    tris = GeomTriangles(Geom.UHStatic)
    idx = 0
    for n, corners in faces:
        for c in corners:
            vertex.addData3f(*c)
            normal.addData3f(n)
        tris.addVertices(idx, idx + 1, idx + 2)
        tris.addVertices(idx, idx + 2, idx + 3)
        idx += 4
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    np = parent.attachNewNode(node)
    np.setPos(pos)
    np.setHpr(hpr)
    apply_mat(np, color, emission)
    return np


def create_cylinder_y(parent: NodePath, name: str, pos: Vec3, radius: float, length: float, segments: int, color: tuple[float, float, float, float], hpr: Vec3 = Vec3(0, 0, 0), emission: tuple[float, float, float, float] | None = None) -> NodePath:
    fmt = GeomVertexFormat.getV3n3()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    tris = GeomTriangles(Geom.UHStatic)
    half = length / 2.0

    # Side vertices
    for i in range(segments + 1):
        a = (i % segments) / segments * math.tau
        x = math.cos(a) * radius
        z = math.sin(a) * radius
        n = Vec3(x, 0, z).normalized()
        vertex.addData3f(x, -half, z)
        normal.addData3f(n)
        vertex.addData3f(x, half, z)
        normal.addData3f(n)
    for i in range(segments):
        base = i * 2
        tris.addVertices(base, base + 1, base + 3)
        tris.addVertices(base, base + 3, base + 2)

    # Caps
    front_center = (segments + 1) * 2
    vertex.addData3f(0, -half, 0)
    normal.addData3f(0, -1, 0)
    back_center = front_center + 1
    vertex.addData3f(0, half, 0)
    normal.addData3f(0, 1, 0)

    cap_start = back_center + 1
    for i in range(segments):
        a = i / segments * math.tau
        x = math.cos(a) * radius
        z = math.sin(a) * radius
        vertex.addData3f(x, -half, z)
        normal.addData3f(0, -1, 0)
        vertex.addData3f(x, half, z)
        normal.addData3f(0, 1, 0)
    for i in range(segments):
        ni = (i + 1) % segments
        tris.addVertices(front_center, cap_start + ni * 2, cap_start + i * 2)
        tris.addVertices(back_center, cap_start + i * 2 + 1, cap_start + ni * 2 + 1)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    np = parent.attachNewNode(node)
    np.setPos(pos)
    np.setHpr(hpr)
    apply_mat(np, color, emission)
    return np



def create_uv_sphere(parent: NodePath, name: str, pos: Vec3, radius: float, rings: int, sectors: int, color: tuple[float, float, float, float], emission: tuple[float, float, float, float] | None = None) -> NodePath:
    """Small generated sphere used for natural celestial bodies/event horizons."""
    fmt = GeomVertexFormat.getV3n3()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    tris = GeomTriangles(Geom.UHStatic)
    for r in range(rings + 1):
        phi = -math.pi / 2 + math.pi * (r / rings)
        cp = math.cos(phi)
        sp = math.sin(phi)
        for sidx in range(sectors + 1):
            theta = math.tau * (sidx / sectors)
            x = math.cos(theta) * cp
            y = math.sin(theta) * cp
            z = sp
            vertex.addData3f(x * radius, y * radius, z * radius)
            normal.addData3f(x, y, z)
    for r in range(rings):
        for sidx in range(sectors):
            a = r * (sectors + 1) + sidx
            b = a + sectors + 1
            tris.addVertices(a, b, a + 1)
            tris.addVertices(a + 1, b, b + 1)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    np = parent.attachNewNode(node)
    np.setPos(pos)
    apply_mat(np, color, emission)
    if color[3] < 1.0:
        np.setTransparency(TransparencyAttrib.M_alpha)
    return np

def create_annular_arc_y(parent: NodePath, name: str, pos: Vec3, inner_radius: float, outer_radius: float, start_deg: float, end_deg: float, segments: int, color: tuple[float, float, float, float], hpr: Vec3 = Vec3(0, 0, 0), emission: tuple[float, float, float, float] | None = None) -> NodePath:
    """Flat annular arc in local X/Z, facing along local Y. Used for black-hole rings and lensing smears."""
    fmt = GeomVertexFormat.getV3n3()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    tris = GeomTriangles(Geom.UHStatic)
    sweep = end_deg - start_deg
    if abs(sweep) < 0.01:
        sweep = 360.0
    for i in range(segments + 1):
        a = math.radians(start_deg + sweep * (i / segments))
        co, si = math.cos(a), math.sin(a)
        vertex.addData3f(co * outer_radius, 0.0, si * outer_radius)
        normal.addData3f(0, -1, 0)
        vertex.addData3f(co * inner_radius, 0.0, si * inner_radius)
        normal.addData3f(0, -1, 0)
    for i in range(segments):
        base = i * 2
        tris.addVertices(base, base + 1, base + 3)
        tris.addVertices(base, base + 3, base + 2)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    np = parent.attachNewNode(node)
    np.setPos(pos)
    np.setHpr(hpr)
    np.setTwoSided(True)
    apply_mat(np, color, emission)
    if color[3] < 1.0:
        np.setDepthWrite(False)
    return np


def create_lightning_strand(parent: NodePath, name: str, points: list[Vec3], color: tuple[float, float, float, float], thickness: float = 1.5) -> NodePath:
    lines = LineSegs(name)
    lines.setThickness(thickness)
    lines.setColor(*color)
    if points:
        lines.moveTo(points[0])
        for pt in points[1:]:
            lines.drawTo(pt)
    np = parent.attachNewNode(lines.create())
    return np


def create_glow_card(parent: NodePath, name: str, pos: Vec3, scale: float, color: tuple[float, float, float, float], hpr: Vec3 = Vec3(0, 0, 0)) -> NodePath:
    cm = CardMaker(name)
    cm.setFrame(-1, 1, -1, 1)
    np = parent.attachNewNode(cm.generate())
    np.setPos(pos)
    np.setHpr(hpr)
    np.setScale(scale)
    np.setTransparency(TransparencyAttrib.M_alpha)
    np.setColor(*color)
    np.setDepthWrite(False)
    return np


def create_soft_disc_y(parent: NodePath, name: str, pos: Vec3, radius_x: float, radius_z: float, center_color: tuple[float, float, float, float], edge_color: tuple[float, float, float, float] | None = None, segments: int = 48, hpr: Vec3 = Vec3(0, 0, 0)) -> NodePath:
    """Soft elliptical disc in local X/Z facing along Y, using vertex alpha falloff.

    This gives galaxies/nebulae a softer photographic feel than square alpha cards while staying
    procedural and dependency-free.
    """
    if edge_color is None:
        edge_color = (center_color[0], center_color[1], center_color[2], 0.0)
    fmt = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    color = GeomVertexWriter(vdata, "color")
    vertex.addData3f(0, 0, 0)
    color.addData4f(*center_color)
    for i in range(segments + 1):
        a = i / segments * math.tau
        vertex.addData3f(math.cos(a) * radius_x, 0, math.sin(a) * radius_z)
        color.addData4f(*edge_color)
    tris = GeomTriangles(Geom.UHStatic)
    for i in range(1, segments + 1):
        tris.addVertices(0, i, i + 1)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    np = parent.attachNewNode(node)
    np.setPos(pos)
    np.setHpr(hpr)
    np.setTransparency(TransparencyAttrib.M_alpha)
    np.setDepthWrite(False)
    np.setTwoSided(True)
    np.setLightOff(1)
    np.setAttrib(ColorAttrib.makeVertex(), 1)
    return np


def seeded_unit(seed: int) -> float:
    seed = (seed ^ 0x5DEECE66D) & 0x7FFFFFFF
    return ((1103515245 * seed + 12345) & 0x7FFFFFFF) / 0x7FFFFFFF


def create_outline_box(parent: NodePath, name: str, pos: Vec3, scale: Vec3, color: tuple[float, float, float, float], hpr: Vec3 = Vec3(0, 0, 0), thickness: float = 1.5) -> NodePath:
    sx, sy, sz = scale.x / 2.0, scale.y / 2.0, scale.z / 2.0
    corners = [
        Vec3(-sx, -sy, -sz), Vec3(sx, -sy, -sz), Vec3(sx, sy, -sz), Vec3(-sx, sy, -sz),
        Vec3(-sx, -sy, sz), Vec3(sx, -sy, sz), Vec3(sx, sy, sz), Vec3(-sx, sy, sz),
    ]
    edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
    lines = LineSegs(name)
    lines.setThickness(thickness)
    lines.setColor(*color)
    for a, b in edges:
        lines.moveTo(corners[a])
        lines.drawTo(corners[b])
    np = parent.attachNewNode(lines.create())
    np.setPos(pos)
    np.setHpr(hpr)
    return np


@dataclass
class ControlState:
    forward: bool = False
    back: bool = False
    left: bool = False
    right: bool = False
    up: bool = False
    down: bool = False
    roll_l: bool = False
    roll_r: bool = False
    boost: bool = False


@dataclass
class LensTarget:
    name: str
    kind: str
    seed: int
    color: tuple[float, float, float, float]
    root: NodePath


@dataclass
class GameplayTarget:
    name: str
    kind: str
    root: NodePath
    radius: float
    value: int = 0
    collected: bool = False


@dataclass
class ResearchTask:
    title: str
    station: str
    reward: int
    seconds_required: float
    note: str
    progress: float = 0.0
    complete: bool = False


OPERATION_TARGETS = {
    "MIMAS": {"moon": "mimas", "title": "Mimas Snowfield", "status": "READY", "mission": "Frozen crater-pool drill survey with rover support.", "fact": "Mimas is dominated by Herschel crater and a heavily cratered ice-rich surface.", "resources": "dirty snowpack ice, crater lens samples, impact regolith", "tip": "Use sonar over pale crater-floor ice lenses before drilling."},
    "ENCELADUS": {"moon": "enceladus", "title": "Enceladus Ice", "status": "READY", "mission": "Bright ice drilling, robot extraction, and plume-resource recovery.", "fact": "Enceladus has bright resurfaced ice and active south-polar plume terrain.", "resources": "plume ice fiber, brine chemistry, optical crystals", "tip": "Scan for high signal hotspots before cutting a drill hole."},
    "IAPETUS": {"moon": "iapetus", "title": "Iapetus Ridge", "status": "READY", "mission": "Cassini Regio mountain ascent: climb the towering ridge and extract Iapetus-only tholin shards.", "fact": "Iapetus is famous for its giant equatorial ridge and the dark Cassini Regio terrain that coats one hemisphere.", "resources": "Iapetus-only tholin ridge shards, charcoal regolith, ridge fracture cores", "tip": "Start low, climb slowly, switch to GRAPPLE, and probe the mountain band for tholin ridge shards."},
    "TITAN": {"moon": "titan", "title": "Titan Methane Coast", "status": "READY", "mission": "Dense orange-atmosphere survey: map methane lakes, harvest hydrocarbon condensate, and recover tholin sand.", "fact": "Titan has a thick nitrogen-methane atmosphere and stable surface liquids of methane and ethane.", "resources": "liquid methane condensate, ethane tar, tholin sand, haze organics", "tip": "Use sonar along dark shorelines and low basins; methane signals are strongest near lake margins."},
    "MARS": {"moon": "mars", "title": "Mars Snow Caps", "status": "READY", "mission": "Dry-channel and snow-cap survey: traverse rust dunes, inspect polar frost zones, and recover cold-weather mineral samples.", "fact": "Mars has a thin CO₂ atmosphere, bright polar caps, and two small moons named Phobos and Deimos.", "resources": "iron-rich dust, frost cap cores, basalt shards, dry-channel regolith", "tip": "Search bright snow fringes and dry basin channels; sunlight is clearer here than on Titan."},
    "PLUTO": {"moon": "pluto", "title": "Pluto Nitrogen Frontier", "status": "READY", "mission": "Kuiper Belt surface operation: traverse Sputnik Planitia, sample nitrogen frost, and recover volatile ice cores near water-ice mountains.", "fact": "Pluto has nitrogen-ice plains, water-ice mountains, and a very thin atmosphere with layered haze.", "resources": "nitrogen frost, methane ice, tholin regolith, water-ice ridge cores", "tip": "Sweep the bright plain first, then probe the darker mountain margins for stronger mixed-composition returns."},
    "EUROPA": {"moon": "europa", "title": "Europa Depths", "status": "READY", "mission": "Hostile Jovian canyon operation: descend through fractured ice-and-iron ravines, map radiation-scarred walls, and recover subsurface crust samples.", "fact": "Europa is an icy moon of Jupiter with a fractured water-ice shell, strong evidence for a subsurface ocean, and an intense radiation environment.", "resources": "fracture ice cores, oxidant salts, iron-rich crust flakes, sub-ice chemistry traces", "tip": "Follow the canyon floor for safer travel, then scan rusty fracture bands and broken ledges for stronger returns."},
    "TRITON": {"moon": "triton", "title": "Triton Valleys", "status": "READY", "mission": "Neptunian frost-valley operation: cross long frozen trenches, map volatile fans, and recover nitrogen-frost and valley-wall samples.", "fact": "Triton has a very thin nitrogen atmosphere, reflective nitrogen frost, and active geyser-like plumes observed by Voyager 2.", "resources": "nitrogen frost, volatile dust, cryo-clathrate, valley wall ice", "tip": "Follow valley floors and broken shelves, then scan darker frost-fan streaks for stronger volatile returns."},
    "ANOM": {"moon": None, "title": "Anomaly Field", "status": "INTERIOR", "mission": "Review local anomaly telemetry from the Starfall observatory without leaving the ship.", "fact": "The ship keeps anomaly analysis inside the cockpit shell while planetary fieldwork runs through remote drone feeds.", "resources": "probe telemetry, scanner research data, anomaly catalog traces", "tip": "Use the observatory scanners and research stations; there is no normal-player flight handoff."},
}


STARFALL_INPUT_EVENTS = [
    "escape", "m", "h", "f1", "r", "u", "tab", "t", "1", "2", "3", "4", "5",
    "mouse1", "mouse3", "mouse3-up",
    "w", "w-up", "s", "s-up", "a", "a-up", "d", "d-up",
    "space", "space-up", "control", "control-up", "q", "q-up", "e", "e-up",
    "shift", "shift-up",
]

SHELL_UI_CONTRACT_ID = "operation_starfall_shell_ui_v0.1"
SHELL_HUD_LEVELS = ["MINIMAL", "COMPACT", "FULL", "HIDDEN"]
SHELL_SAFE_CANVAS = {"aspect": "16:9", "left": -1.34, "right": 1.34, "top": 0.965, "bottom": -0.965}


def _trim_ui(text: object, limit: int = 64) -> str:
    value = " ".join(str(text or "").replace("\n", " ").split())
    return value if len(value) <= limit else value[:max(0, limit - 3)].rstrip() + "..."


class StarfallShipPrototype(ShowBase):
    def __init__(self, screenshot_mode: str | None = None, screenshot_out: str | None = None):
        super().__init__()
        install_exit_report(self._holoverse_result)
        self.disableMouse()
        self.render.setAntialias(AntialiasAttrib.MAuto)
        self.globalClock = ClockObject.getGlobalClock()
        self.mode = "flight"
        self.screenshot_mode = screenshot_mode
        self.screenshot_out = screenshot_out
        self.controls = ControlState()
        self.ship_velocity = Vec3(0, 0, 0)
        self.ship_pitch = 4.0
        self.ship_yaw = 0.0
        self.ship_roll = 0.0
        self.interior_heading = INTERIOR_SPAWN_HEADING
        self.interior_pitch = 0.0
        self.player_pos = Vec3(0, 176.0, 1.72)
        self.shell_hud_level = "MINIMAL"
        self.hud_visible = True
        self.shell_help_open = False
        self.mouse_captured = True
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.window_centered = False
        self.engine_trails: list[NodePath] = []
        self.anomaly_fx_nodes: list[NodePath] = []
        self.anomaly_hyper_nodes: list[NodePath] = []
        self.anomaly_orbit_nodes: list[NodePath] = []
        self.chunk_haze_nodes: list[NodePath] = []
        self.ship_accent_nodes: list[NodePath] = []
        self.cosmic_twinklers: list[NodePath] = []
        self.organic_cosmic_roots: list[NodePath] = []
        self.hangar_beacons: list[NodePath] = []
        self.docking_clamps: list[NodePath] = []
        self.anchor_scene_nodes: list[NodePath] = []
        self.lens_targets: list[LensTarget] = []
        self.hover_target: LensTarget | None = None
        self.current_chunk_name = "Anchor Drydock"
        self.current_chunk_kind = "station"
        self.current_chunk_seed = 4104
        self.celestial_chunk_root: NodePath | None = None
        self.anomaly_root: NodePath | None = None
        self.lensing_root: NodePath | None = None
        self.warping = False
        self.warp_timer = 0.0
        self.warp_duration = 2.15
        self.warp_swap_done = False
        self.pending_warp_target: LensTarget | None = None
        self.gameplay_targets: list[GameplayTarget] = []
        self.active_gameplay_target: GameplayTarget | None = None
        self.salvage_required = 3
        self.salvage_collected = 0
        self.planet_scanned = False
        self.system_loop_complete = False
        self.systems_completed = 0
        self.credits = 0
        self.last_reward = 0
        self.current_system_value = 0
        self.current_system_rarity = "ANCHOR"
        self.current_sample_value = 16
        self.scanner_upgrade_level = 0
        self.scanner_upgrade_max = 3
        self.research_points = 0
        self.research_tasks: list[ResearchTask] = []
        self.research_task_index = 0
        self.completed_research_count = 0
        self.robot_nodes: list[NodePath] = []
        self.robot_task_lines: list[NodePath] = []
        self.robot_status_lamps: list[NodePath] = []
        self.robot_home_positions: list[Vec3] = []
        # Pass 31: active observatory station selection.  The cockpit is now an interior-first
        # orbital simulator, so these station states drive in-world panels instead of adding HUD clutter.
        self.observatory_stations = [
            ("MIMAS", "MIMAS SNOWFIELD", "READY: crater ice-pool drilling operation"),
            ("IAPETUS", "IAPETUS RIDGE", "READY: equatorial ridge foothill operation"),
            ("ENCELADUS", "ENCELADUS ICE", "READY: plume/ice drilling operation"),
            ("TITAN", "TITAN", "READY: methane coast resource operation"),
            ("MARS", "MARS SNOW CAPS", "READY: dry-channel and snow-cap survey operation"),
            ("PLUTO", "PLUTO", "READY: nitrogen-ice frontier operation"),
            ("EUROPA", "EUROPA DEPTHS", "READY: hostile ice-and-iron canyon operation"),
            ("TRITON", "TRITON VALLEYS", "READY: Neptune-side valley and volatile-frost operation"),
            ("ANOM", "ANOMALY FIELD", "INTERIOR: anomaly telemetry analysis"),
        ]
        self.operation_active = False
        self.operation_app = None
        self.operation_module = None
        self.operation_return_in_progress = False
        self.operation_loading_in_progress = False
        self.pending_operation_code: str | None = None
        self.operation_loading_root: NodePath | None = None
        self.operation_loading_lines: list[NodePath] = []
        # Pass108: moon operations are remote drone feeds viewed from the ship interior.
        # The shell camera/interior remain authoritative while a second Panda camera renders
        # only the planet into the centered 16:9 display region.
        self.operation_display_root: NodePath | None = None
        self.operation_display_surface: NodePath | None = None
        self.operation_display_title = None
        self.operation_display_status = None
        self.operation_feed_camera: NodePath | None = None
        self.operation_feed_display_region = None
        self.operation_feed_lens = None
        self.operation_last_error = ""
        self.operation_shell_snapshot: dict[str, object] | None = None
        self.operation_camera_root: NodePath | None = None
        self.observatory_station_index = 0
        self.observatory_station_lines: list[NodePath] = []
        self.observatory_station_lamps: list[NodePath] = []
        self.pause_menu_open = False
        self.pause_menu_root: NodePath | None = None
        self.shell_help_root: NodePath | None = None
        self.operation_map_open = False
        self.operation_map_root: NodePath | None = None
        self.operation_map_nodes: list[NodePath] = []
        self.scan_held = False
        self.loop_feedback = ""
        self.loop_feedback_timer = 0.0
        self.perf_detail = os.environ.get("STARFALL_DETAIL", "fast").strip().lower()
        self._lensing_accum = 0.0
        self._gameplay_accum = 0.0
        self._cosmic_anim_accum = 0.0
        self._cosmic_anim_phase = 0

        self.flight_root = self.render.attachNewNode("Flight Scene")
        self.interior_root = self.render.attachNewNode("Interior Scene")
        self.interior_root.hide()

        self.setup_lights()
        self.build_space_backdrop()
        self.ship = self.build_ship_exterior(self.flight_root)
        self.build_ship_interior(self.interior_root)
        self.build_hud()
        self.build_operation_display_panel()
        self.build_operation_overlay()
        self.build_pause_menu()
        self.build_shell_help_overlay()
        self.build_saturn_operations_map()
        self.bind_controls()
        self.set_mode(screenshot_mode if screenshot_mode in {"flight", "interior"} else "interior")
        self.update_cabin_console()
        self.update_observatory_station_panels()
        self.taskMgr.add(self.update, "update")

        # Center mouse after the first frame once a window exists.
        self.taskMgr.doMethodLater(0.05, self.capture_mouse, "capture_mouse")
        if screenshot_mode:
            self.taskMgr.doMethodLater(0.45, self.take_screenshot_and_exit, "take_screenshot_and_exit")

    # -----------------------------
    # Setup
    # -----------------------------
    def setup_lights(self) -> None:
        alight = AmbientLight("ambient")
        alight.setColor(Vec4(0.56, 0.62, 0.76, 1))
        self.flight_root.setLight(self.render.attachNewNode(alight))

        key = DirectionalLight("cold key")
        key.setColor(Vec4(1.45, 1.50, 1.62, 1))
        key_np = self.render.attachNewNode(key)
        key_np.setHpr(-35, -42, 0)
        self.flight_root.setLight(key_np)

        rim = DirectionalLight("red rim")
        rim.setColor(Vec4(0.55, 0.12, 0.08, 1))
        rim_np = self.render.attachNewNode(rim)
        rim_np.setHpr(145, -18, 0)
        self.flight_root.setLight(rim_np)

        ship_light = PointLight("ship presentation fill")
        ship_light.setColor(Vec4(1.0, 1.12, 1.28, 1))
        ship_light.setAttenuation((1, 0.018, 0.002))
        ship_light_np = self.render.attachNewNode(ship_light)
        ship_light_np.setPos(0, -9, 6.5)
        self.flight_root.setLight(ship_light_np)

    def bind_controls(self) -> None:
        self._bind_starfall_controls()

    def _unbind_starfall_controls(self) -> None:
        for event in STARFALL_INPUT_EVENTS:
            try:
                self.ignore(event)
            except Exception:
                pass

    def _bind_starfall_controls(self) -> None:
        self._unbind_starfall_controls()
        self.accept("escape", self.handle_escape)
        self.accept("m", self.show_saturn_operations_map)
        self.accept("h", self.toggle_hud)
        self.accept("f1", self.show_shell_help)
        self.accept("r", self.reset_ship)
        self.accept("u", self.buy_scanner_upgrade)
        self.accept("tab", self.cycle_observatory_station)
        self.accept("t", self.cycle_research_task)
        self.accept("1", self.select_observatory_station, [0])
        self.accept("2", self.select_observatory_station, [1])
        self.accept("3", self.select_observatory_station, [2])
        self.accept("4", self.select_observatory_station, [3])
        self.accept("5", self.select_observatory_station, [4])
        self.accept("mouse1", self.handle_primary_click)
        self.accept("mouse3", self.set_scanning, [True])
        self.accept("mouse3-up", self.set_scanning, [False])

        pairs = [
            ("w", "forward"), ("s", "back"), ("a", "left"), ("d", "right"),
            ("space", "up"), ("control", "down"), ("q", "roll_l"), ("e", "roll_r"),
            ("shift", "boost"),
        ]
        for key, attr in pairs:
            self.accept(key, self.set_control, [attr, True])
            self.accept(f"{key}-up", self.set_control, [attr, False])

    def handle_escape(self) -> None:
        if getattr(self, "operation_active", False):
            return
        if getattr(self, "shell_help_open", False):
            self.hide_shell_help()
            return
        if getattr(self, "operation_map_open", False):
            self.hide_saturn_operations_map()
            self.set_loop_feedback("OPS MAP CLOSED", 1.0)
            return
        if getattr(self, "pause_menu_open", False):
            self.hide_pause_menu()
            return
        self.show_pause_menu()

    def set_control(self, attr: str, value: bool) -> None:
        if getattr(self, "operation_active", False) or self._shell_panel_open():
            return
        setattr(self.controls, attr, value)

    def set_scanning(self, value: bool) -> None:
        if getattr(self, "operation_active", False) or self._shell_panel_open():
            return
        self.scan_held = value

    def capture_mouse(self, task: Task) -> int:
        if self.win and self.mouse_captured and hasattr(self.win, "requestProperties"):
            props = WindowProperties()
            props.setCursorHidden(True)
            self.win.requestProperties(props)
            self.center_mouse()
        return Task.done

    def center_mouse(self) -> None:
        if not self.win:
            return
        props = self.win.getProperties()
        cx, cy = props.getXSize() // 2, props.getYSize() // 2
        self.win.movePointer(0, cx, cy)
        self.last_mouse_x = cx
        self.last_mouse_y = cy
        self.window_centered = True

    # -----------------------------
    # Starfall shell menus / operation map
    # -----------------------------
    def _shell_panel_open(self) -> bool:
        return bool(
            getattr(self, "pause_menu_open", False)
            or getattr(self, "operation_map_open", False)
            or getattr(self, "shell_help_open", False)
            or getattr(self, "operation_loading_in_progress", False)
        )

    def _set_shell_cursor_free(self, free: bool) -> None:
        if self.win and hasattr(self.win, "requestProperties"):
            props = WindowProperties()
            props.setCursorHidden(not free)
            self.win.requestProperties(props)
        self.mouse_captured = not free
        if free:
            self.controls = ControlState()
            self.scan_held = False
            self.window_centered = False
        else:
            self.window_centered = False
            self.taskMgr.doMethodLater(0.04, self.capture_mouse, "recapture_mouse_after_shell_ui")

    def _suppress_shell_hud_for_panel(self) -> None:
        self.shell_panel_hud_suppressed = True
        for element in getattr(self, "hud_full_elements", getattr(self, "hud_elements", [])):
            try:
                if element is not None and not element.isEmpty():
                    element.hide()
            except Exception:
                pass
        self.shell_panel_world_label_snapshot = []
        for node in getattr(self, "interior_world_labels", []):
            try:
                if node is not None and not node.isEmpty():
                    was_hidden = bool(node.isHidden())
                    self.shell_panel_world_label_snapshot.append((node, was_hidden))
                    node.hide()
            except Exception:
                pass

    def shell_panel_is_exclusive(self, expected: str) -> bool:
        roots = {
            "pause": getattr(self, "pause_menu_root", None),
            "map": getattr(self, "operation_map_root", None),
            "help": getattr(self, "shell_help_root", None),
        }
        visible = []
        for name, root in roots.items():
            if root is not None and not root.isEmpty() and not root.isHidden():
                visible.append(name)
        hud_hidden = True
        for element in getattr(self, "hud_full_elements", getattr(self, "hud_elements", [])):
            try:
                if element is not None and not element.isEmpty() and not element.isHidden():
                    hud_hidden = False
                    break
            except Exception:
                pass
        world_labels_hidden = True
        for node in getattr(self, "interior_world_labels", []):
            try:
                if node is not None and not node.isEmpty() and not node.isHidden():
                    world_labels_hidden = False
                    break
            except Exception:
                pass
        return visible == [expected] and hud_hidden and world_labels_hidden and not bool(getattr(self, "mouse_captured", True))

    def _restore_shell_hud_after_panel(self) -> None:
        if self._shell_panel_open():
            return
        self.shell_panel_hud_suppressed = False
        for node, was_hidden in getattr(self, "shell_panel_world_label_snapshot", []):
            try:
                if node is not None and not node.isEmpty() and not was_hidden:
                    node.show()
            except Exception:
                pass
        self.shell_panel_world_label_snapshot = []
        self.apply_shell_hud_level(getattr(self, "shell_hud_level", "MINIMAL"))

    def build_pause_menu(self) -> None:
        root = self.aspect2d.attachNewNode("operation_starfall_pause_menu")
        root.setBin("fixed", 14000)
        root.setDepthTest(False)
        root.setDepthWrite(False)
        root.hide()
        self.pause_menu_root = root
        cm = CardMaker("pause_menu_backdrop")
        cm.setFrame(-1.34, 1.34, -0.88, 0.88)
        card = NodePath(cm.generate())
        card.reparentTo(root)
        card.setColor(0.002, 0.012, 0.028, 0.84)
        card.setTransparency(TransparencyAttrib.MAlpha)
        OnscreenText(text="OPERATION STARFALL", parent=root, pos=(0, 0.41), scale=0.055,
                     fg=(0.66, 0.96, 1.0, 1), align=TextNode.ACenter, mayChange=False)
        OnscreenText(text="SHIP SYSTEMS",
                     parent=root, pos=(0, 0.31), scale=0.027, fg=(0.86, 0.95, 1.0, 0.78),
                     align=TextNode.ACenter, mayChange=False)
        self._make_shell_button(root, "RESUME", (0, 0.14), self.hide_pause_menu)
        self._make_shell_button(root, "SATURN OPS MAP", (0, -0.005), self.show_saturn_operations_map)
        self._make_shell_button(root, "HELP / CONTROLS", (0, -0.15), self.show_shell_help)
        self._make_shell_button(root, quit_label("QUIT"), (0, -0.295), self.quit_to_holoverse, frame_color=(0.28, 0.06, 0.05, 0.92))

    def _holoverse_result(self) -> dict:
        done = int(getattr(self, "completed_research_count", 0) or 0)
        line = (f"StarFall logged {done} research task{'s' if done != 1 else ''}. The outer worlds are a little less dark."
                if done else "The ship is still waiting at the edge of the system.")
        return {"completed": done > 0, "signal": "starfall_research" if done else "starfall_visit",
                "gleebs_response": line, "research_completed": done}

    def quit_to_holoverse(self):
        """QUIT button: report to HoloVerse when hosted, then close as before."""
        report_to_holoverse(**self._holoverse_result())
        self.userExit()

    def _make_shell_button(self, parent: NodePath, text: str, pos: tuple[float, float], command, extra_args=None,
                           frame_color=(0.035, 0.12, 0.20, 0.82)) -> DirectButton:
        return DirectButton(parent=parent, text=text, pos=(pos[0], 0, pos[1]), scale=1.0,
                            frameSize=(-0.38, 0.38, -0.045, 0.045), frameColor=frame_color,
                            text_scale=0.038, text_fg=(0.78, 0.96, 1.0, 1.0),
                            relief=1, command=command, extraArgs=extra_args or [])

    def show_pause_menu(self) -> None:
        if getattr(self, "operation_active", False):
            return
        self.hide_saturn_operations_map(keep_cursor=True)
        self.hide_shell_help(keep_cursor=True)
        root = getattr(self, "pause_menu_root", None)
        if root is not None and not root.isEmpty():
            root.show()
        self.pause_menu_open = True
        self._suppress_shell_hud_for_panel()
        self._set_shell_cursor_free(True)
        self.set_loop_feedback("PAUSED", 1.0)

    def hide_pause_menu(self) -> None:
        root = getattr(self, "pause_menu_root", None)
        if root is not None and not root.isEmpty():
            root.hide()
        self.pause_menu_open = False
        if not getattr(self, "operation_map_open", False) and not getattr(self, "shell_help_open", False):
            self._set_shell_cursor_free(False)
        self.set_loop_feedback("RESUMED", 1.0)
        self._restore_shell_hud_after_panel()

    def build_shell_help_overlay(self) -> None:
        root = self.aspect2d.attachNewNode("operation_starfall_shell_help")
        root.setBin("fixed", 14100)
        root.setDepthTest(False)
        root.setDepthWrite(False)
        root.hide()
        self.shell_help_root = root
        cm = CardMaker("shell_help_backdrop")
        cm.setFrame(-1.24, 1.24, -0.72, 0.72)
        card = root.attachNewNode(cm.generate())
        card.setColor(0.002, 0.020, 0.040, 0.86)
        card.setTransparency(TransparencyAttrib.MAlpha)
        OnscreenText(text="STARFALL SHELL HELP", parent=root, pos=(0, 0.48), scale=0.047,
                     fg=(0.70, 0.96, 1.0, 0.98), align=TextNode.ACenter, mayChange=False)
        lines = [
            "ESC: menu / close panels",
            "M or interior LMB: Saturn Ops Map",
            "TAB or 1-5: cycle/select operation stations",
            "Operations are managed from the ship interior",
            "H: shell HUD minimal -> compact -> full -> hidden",
            "Moon worlds: TAB returns to ship; ESC opens moon options",
        ]
        for idx, line in enumerate(lines):
            OnscreenText(text=line, parent=root, pos=(-0.80, 0.32 - idx * 0.105), scale=0.035,
                         fg=(0.84, 0.96, 1.0, 0.88), align=TextNode.ALeft, mayChange=False)
        self._make_shell_button(root, "BACK", (0, -0.39), self.hide_shell_help, frame_color=(0.05, 0.13, 0.19, 0.58))

    def show_shell_help(self) -> None:
        if getattr(self, "operation_active", False):
            return
        self.hide_saturn_operations_map(keep_cursor=True)
        self.hide_pause_menu()
        root = getattr(self, "shell_help_root", None)
        if root is not None and not root.isEmpty():
            root.show()
        self.shell_help_open = True
        self._suppress_shell_hud_for_panel()
        self._set_shell_cursor_free(True)
        self.set_loop_feedback("HELP", 1.0)

    def hide_shell_help(self, keep_cursor: bool = False) -> None:
        root = getattr(self, "shell_help_root", None)
        if root is not None and not root.isEmpty():
            root.hide()
        self.shell_help_open = False
        if not keep_cursor and not getattr(self, "operation_map_open", False) and not getattr(self, "pause_menu_open", False):
            self._set_shell_cursor_free(False)
        self._restore_shell_hud_after_panel()

    def toggle_pause_menu(self) -> None:
        if getattr(self, "pause_menu_open", False):
            self.hide_pause_menu()
        else:
            self.show_pause_menu()

    def _make_ui_arc_disc(self, parent: NodePath, name: str, radius: float, start_angle: float, end_angle: float, color: tuple[float, float, float, float], segments: int = 40) -> NodePath:
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData(name, fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        rgba = GeomVertexWriter(vdata, "color")
        vertex.addData3(0.0, 0.0, 0.0)
        rgba.addData4f(*color)
        sweep = max(1, segments)
        for i in range(sweep + 1):
            t = i / float(sweep)
            ang = start_angle + (end_angle - start_angle) * t
            vertex.addData3(math.cos(ang) * radius, 0.0, math.sin(ang) * radius)
            rgba.addData4f(*color)
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(1, sweep + 1):
            tris.addVertices(0, i, i + 1)
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode(name)
        node.addGeom(geom)
        np = parent.attachNewNode(node)
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setDepthTest(False)
        np.setDepthWrite(False)
        return np

    def _make_ui_disc(self, parent: NodePath, name: str, radius: float, color: tuple[float, float, float, float], segments: int = 40) -> NodePath:
        return self._make_ui_arc_disc(parent, name, radius, 0.0, math.tau, color, segments=segments)

    def _make_ui_circle_line(self, parent: NodePath, name: str, radius: float, color: tuple[float, float, float, float], thickness: float = 1.6, segments: int = 56, y: float = 0.0) -> NodePath:
        segs = LineSegs(name)
        segs.setThickness(thickness)
        segs.setColor(*color)
        for i in range(segments):
            a0 = math.tau * i / segments
            a1 = math.tau * (i + 1) / segments
            segs.moveTo(math.cos(a0) * radius, y, math.sin(a0) * radius)
            segs.drawTo(math.cos(a1) * radius, y, math.sin(a1) * radius)
        np = parent.attachNewNode(segs.create())
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setDepthTest(False)
        np.setDepthWrite(False)
        return np

    def _build_ops_moon_visual(self, parent: NodePath, code: str, x: float, y: float, radius: float, ready: bool) -> NodePath:
        root = parent.attachNewNode(f"ops_map_visual_{code.lower()}")
        root.setPos(x, 0.0, y + 0.052)
        glow = (0.26, 0.76, 1.0, 0.28) if ready else (0.34, 0.38, 0.46, 0.18)
        self._make_ui_circle_line(root, f"{code.lower()}_halo", radius * 1.34, glow, thickness=2.2 if ready else 1.5)

        if code == "MIMAS":
            self._make_ui_disc(root, "mimas_body", radius, (0.78, 0.77, 0.72, 0.98))
            self._make_ui_circle_line(root, "mimas_edge", radius, (0.46, 0.48, 0.50, 0.64), thickness=1.4)
            crater_specs = [(-0.010, 0.006, radius * 0.48, 1.5), (-radius * 0.34, radius * 0.28, radius * 0.17, 1.0), (radius * 0.28, radius * 0.18, radius * 0.13, 1.0), (radius * 0.12, -radius * 0.26, radius * 0.11, 1.0)]
            for idx, (cx, cz, rr, thick) in enumerate(crater_specs):
                crater = root.attachNewNode(f"mimas_crater_{idx}")
                crater.setPos(cx, 0.0, cz)
                self._make_ui_circle_line(crater, f"mimas_crater_line_{idx}", rr, (0.38, 0.40, 0.42, 0.72), thickness=thick)
            self._make_ui_disc(root.attachNewNode("mimas_herschel_pit"), "mimas_herschel_center", radius * 0.08, (0.52, 0.52, 0.50, 0.55)).setPos(-0.010, 0.0, 0.006)
        elif code == "ENCELADUS":
            self._make_ui_disc(root, "enceladus_body", radius, (0.72, 0.90, 1.0, 0.98))
            self._make_ui_disc(root, "enceladus_cap", radius * 0.82, (0.92, 0.98, 1.0, 0.18))
            self._make_ui_circle_line(root, "enceladus_edge", radius, (0.58, 0.86, 1.0, 0.72), thickness=1.4)
            for idx, xoff in enumerate((-0.30, -0.10, 0.10, 0.30)):
                segs = LineSegs(f"enceladus_tiger_{idx}")
                segs.setThickness(1.4)
                segs.setColor(0.20, 0.84, 1.0, 0.82)
                sx = xoff * radius
                segs.moveTo(sx - radius * 0.06, 0.0, -radius * 0.10)
                segs.drawTo(sx, 0.0, -radius * 0.44)
                segs.drawTo(sx + radius * 0.06, 0.0, -radius * 0.72)
                stripe = root.attachNewNode(segs.create())
                stripe.setTransparency(TransparencyAttrib.MAlpha)
        elif code == "IAPETUS":
            self._make_ui_arc_disc(root, "iapetus_dark", radius, math.pi / 2.0, math.pi * 1.5, (0.22, 0.21, 0.19, 0.98), segments=32)
            self._make_ui_arc_disc(root, "iapetus_bright", radius, -math.pi / 2.0, math.pi / 2.0, (0.78, 0.80, 0.82, 0.98), segments=32)
            self._make_ui_circle_line(root, "iapetus_edge", radius, (0.52, 0.56, 0.60, 0.68), thickness=1.4)
            ridge = LineSegs("iapetus_ridge")
            ridge.setThickness(1.6)
            ridge.setColor(0.74, 0.66, 0.46, 0.90)
            ridge.moveTo(-radius * 0.72, 0.0, -radius * 0.02)
            ridge.drawTo(-radius * 0.26, 0.0, radius * 0.06)
            ridge.drawTo(radius * 0.18, 0.0, -radius * 0.01)
            ridge.drawTo(radius * 0.70, 0.0, radius * 0.05)
            root.attachNewNode(ridge.create()).setTransparency(TransparencyAttrib.MAlpha)
            for idx, (cx, cz, rr) in enumerate(((-radius * 0.24, radius * 0.18, radius * 0.12), (radius * 0.22, -radius * 0.08, radius * 0.10))):
                crater = root.attachNewNode(f"iapetus_crater_{idx}")
                crater.setPos(cx, 0.0, cz)
                self._make_ui_circle_line(crater, f"iapetus_crater_line_{idx}", rr, (0.40, 0.42, 0.44, 0.58), thickness=1.0)
        elif code == "TITAN":
            self._make_ui_circle_line(root, "titan_haze", radius * 1.18, (0.98, 0.70, 0.34, 0.42), thickness=2.0)
            self._make_ui_disc(root, "titan_body", radius, (0.92, 0.62, 0.24, 0.92))
            self._make_ui_disc(root, "titan_smog", radius * 0.86, (0.96, 0.78, 0.42, 0.16))
        elif code == "MARS":
            self._make_ui_disc(root, "mars_body", radius, (0.86, 0.44, 0.22, 0.94))
            self._make_ui_disc(root, "mars_cap_north", radius * 0.22, (0.94, 0.95, 0.98, 0.82)).setPos(0.0, 0.0, radius * 0.46)
            self._make_ui_disc(root, "mars_cap_south", radius * 0.18, (0.92, 0.94, 0.98, 0.72)).setPos(0.0, 0.0, -radius * 0.42)
            self._make_ui_circle_line(root, "mars_edge", radius, (0.98, 0.82, 0.62, 0.54), thickness=1.4)
            for idx, (px, pz, rr) in enumerate(((-0.28, 0.12, 0.11), (0.24, -0.04, 0.09))):
                crater = root.attachNewNode(f"mars_crater_{idx}")
                crater.setPos(px * radius, 0.0, pz * radius)
                self._make_ui_circle_line(crater, f"mars_crater_line_{idx}", rr * radius, (0.58, 0.24, 0.12, 0.48), thickness=1.0)
        elif code == "PLUTO":
            self._make_ui_disc(root, "pluto_body", radius, (0.72, 0.82, 0.92, 0.90))
            self._make_ui_circle_line(root, "pluto_edge", radius, (0.88, 0.94, 1.0, 0.55), thickness=1.2)
            heart = root.attachNewNode("pluto_heart")
            self._make_ui_disc(heart, "pluto_heart_left", radius * 0.16, (0.92, 0.94, 0.98, 0.78)).setPos(-radius * 0.10, 0.0, radius * 0.02)
            self._make_ui_disc(heart, "pluto_heart_right", radius * 0.16, (0.92, 0.94, 0.98, 0.78)).setPos(radius * 0.02, 0.0, radius * 0.02)
        elif code == "EUROPA":
            self._make_ui_disc(root, "europa_body", radius, (0.78, 0.82, 0.88, 0.96))
            self._make_ui_circle_line(root, "europa_edge", radius, (0.90, 0.96, 1.0, 0.48), thickness=1.2)
            for idx, zoff in enumerate((-0.30, -0.05, 0.18)):
                segs = LineSegs(f"europa_fracture_{idx}")
                segs.setThickness(1.5)
                segs.setColor(0.92, 0.52, 0.20, 0.82)
                segs.moveTo(-radius * 0.72, 0.0, radius * zoff)
                segs.drawTo(-radius * 0.18, 0.0, radius * (zoff + 0.05))
                segs.drawTo(radius * 0.26, 0.0, radius * (zoff - 0.02))
                segs.drawTo(radius * 0.74, 0.0, radius * (zoff + 0.06))
                root.attachNewNode(segs.create()).setTransparency(TransparencyAttrib.MAlpha)
        elif code == "TRITON":
            self._make_ui_disc(root, "triton_body", radius, (0.72, 0.78, 0.88, 0.96))
            self._make_ui_circle_line(root, "triton_edge", radius, (0.86, 0.94, 1.0, 0.52), thickness=1.2)
            for idx, points in enumerate((
                [(-0.70, 0.16), (-0.30, 0.26), (0.08, 0.10), (0.62, 0.22)],
                [(-0.58, -0.20), (-0.18, -0.04), (0.18, -0.18), (0.70, -0.04)],
            )):
                segs = LineSegs(f"triton_valley_{idx}")
                segs.setThickness(1.5)
                segs.setColor(0.62, 0.72, 0.86, 0.82)
                first = points[0]
                segs.moveTo(first[0] * radius, 0.0, first[1] * radius)
                for px, pz in points[1:]:
                    segs.drawTo(px * radius, 0.0, pz * radius)
                root.attachNewNode(segs.create()).setTransparency(TransparencyAttrib.MAlpha)
        else:
            # Anomaly / generic node: keep readable but less planet-like.
            diamond = LineSegs(f"{code.lower()}_diamond")
            diamond.setThickness(2.1)
            diamond.setColor(0.78, 0.48, 1.0, 0.92)
            pts = [(0.0, radius), (radius, 0.0), (0.0, -radius), (-radius, 0.0), (0.0, radius)]
            diamond.moveTo(pts[0][0], 0.0, pts[0][1])
            for px, pz in pts[1:]:
                diamond.drawTo(px, 0.0, pz)
            root.attachNewNode(diamond.create()).setTransparency(TransparencyAttrib.MAlpha)
            self._make_ui_disc(root, f"{code.lower()}_core", radius * 0.44, (0.72, 0.42, 1.0, 0.52))
        root.setTransparency(TransparencyAttrib.MAlpha)
        return root

    def build_saturn_operations_map(self) -> None:
        root = self.aspect2d.attachNewNode("saturn_operations_map_ui")
        root.setBin("fixed", 13500)
        root.setDepthTest(False)
        root.setDepthWrite(False)
        root.hide()
        self.operation_map_root = root
        self.operation_map_buttons = {}

        cm = CardMaker("saturn_ops_backdrop")
        self.operation_map_backdrop_frame = (-1.34, 1.34, -0.86, 0.86)
        cm.setFrame(*self.operation_map_backdrop_frame)
        card = NodePath(cm.generate())
        card.reparentTo(root)
        card.setColor(0.0, 0.010, 0.026, 0.88)
        card.setTransparency(TransparencyAttrib.MAlpha)
        self.operation_map_nodes.append(card)

        OnscreenText(text="STARFALL OPERATIONS MAP", parent=root, pos=(-1.32, 0.67), scale=0.047,
                     fg=(0.66, 0.96, 1.0, 1.0), align=TextNode.ALeft, mayChange=False)
        OnscreenText(text="Select a destination. READY targets can deploy immediately.",
                     parent=root, pos=(-1.32, 0.590), scale=0.029, fg=(0.88, 0.96, 1.0, 0.82),
                     align=TextNode.ALeft, mayChange=False)

        # Saturn-centered operations diagram.  This is an interface map, not a
        # physical orbit simulator: clean snap positions are more important than
        # exact distance scaling, but rings keep the selectable moon layout readable.
        ring = LineSegs("saturn_ops_orbits")
        ring.setThickness(1.25)
        for radius, alpha in [(0.20, 0.26), (0.34, 0.22), (0.50, 0.18), (0.66, 0.14), (0.78, 0.10)]:
            ring.setColor(0.22, 0.62, 0.90, alpha)
            for i in range(96):
                a0 = math.tau * i / 96
                a1 = math.tau * (i + 1) / 96
                ring.moveTo(math.cos(a0) * radius, 0, math.sin(a0) * radius - 0.03)
                ring.drawTo(math.cos(a1) * radius, 0, math.sin(a1) * radius - 0.03)
        ring_np = root.attachNewNode(ring.create())
        ring_np.setPos(-0.22, 0, -0.02)
        ring_np.setTransparency(TransparencyAttrib.MAlpha)

        # Saturn body + rings at the center of the operations map.
        # Pass72: use a true circular UI disc here; the previous CardMaker
        # body was the last visible square on the map.
        sat_anchor = root.attachNewNode("saturn_ops_saturn_anchor")
        sat_anchor.setPos(-0.22, 0, -0.05)
        sat = self._make_ui_disc(sat_anchor, "saturn_ops_saturn_disc", 0.13, (0.93, 0.76, 0.47, 0.92), segments=56)
        sat.setTransparency(TransparencyAttrib.MAlpha)
        sat_ring = LineSegs("saturn_ops_saturn_ring")
        sat_ring.setThickness(3.0)
        sat_ring.setColor(0.98, 0.88, 0.66, 0.42)
        for i in range(64):
            a0 = math.tau * i / 64
            a1 = math.tau * (i + 1) / 64
            sat_ring.moveTo(math.cos(a0) * 0.23, 0, math.sin(a0) * 0.075 - 0.05)
            sat_ring.drawTo(math.cos(a1) * 0.23, 0, math.sin(a1) * 0.075 - 0.05)
        sat_ring_np = root.attachNewNode(sat_ring.create())
        sat_ring_np.setPos(-0.22, 0, 0.0)
        sat_ring_np.setTransparency(TransparencyAttrib.MAlpha)
        self.operation_map_nodes.extend([ring_np, sat_anchor, sat, sat_ring_np])

        placements = {
            "MIMAS": (-0.34, 0.15, 0.044),
            "IAPETUS": (0.40, 0.04, 0.048),
            "ENCELADUS": (0.14, 0.30, 0.050),
            "TITAN": (0.18, -0.24, 0.060),
            "MARS": (0.56, -0.28, 0.052),
            "PLUTO": (-0.84, -0.35, 0.038),
            "EUROPA": (0.82, 0.28, 0.044),
            "TRITON": (-1.04, -0.04, 0.043),
            "ANOM": (-0.74, 0.46, 0.034),
        }
        for i, (code, title, _purpose) in enumerate(self.observatory_stations):
            target = OPERATION_TARGETS.get(code, {})
            x, y, radius = placements.get(code, (-0.95, 0.35 - i * 0.18, 0.036))
            status = str(target.get("status", "LOCAL"))
            ready = status == "READY" or code == "ANOM"
            fg = (0.84, 0.98, 1.0, 1.0) if ready else (0.56, 0.60, 0.66, 0.95)

            body = self._build_ops_moon_visual(root, code, x, y, radius, ready)
            self.operation_map_nodes.append(body)

            short_name = str(target.get('moon', title)).upper()
            label = f"{short_name}\n{status}"
            label_node = OnscreenText(text=label, parent=root, pos=(x, y - 0.095), scale=0.024,
                                      fg=fg, align=TextNode.ACenter, mayChange=False)
            self.operation_map_nodes.append(label_node)

            # Pass71: invisible click region covers the planet image and label.
            # This removes square node cards while keeping mouse selection reliable.
            hit_w = max(0.120, radius * 2.85)
            hit_h_top = max(0.115, radius * 2.40)
            hit_h_bottom = max(0.135, radius * 2.85)
            btn = DirectButton(parent=root, text="", pos=(x, 0, y + 0.015), scale=1.0,
                               frameSize=(-hit_w, hit_w, -hit_h_bottom, hit_h_top),
                               frameColor=(0.0, 0.0, 0.0, 0.0), relief=None,
                               command=self.select_operation_on_map, extraArgs=[code])
            btn.setTransparency(TransparencyAttrib.MAlpha)
            btn.setDepthTest(False)
            btn.setDepthWrite(False)
            self.operation_map_buttons[code] = btn
            self.operation_map_nodes.append(btn)

        # Side panel owns mission detail so the node labels can stay minimal.
        panel_cm = CardMaker("saturn_ops_target_panel")
        panel_cm.setFrame(-0.02, 0.70, -0.50, 0.50)
        panel = root.attachNewNode(panel_cm.generate())
        panel.setPos(0.62, 0, -0.10)
        panel.setColor(0.015, 0.050, 0.075, 0.82)
        panel.setTransparency(TransparencyAttrib.MAlpha)
        self.operation_map_nodes.append(panel)

        preview_frame = CardMaker("starfall_ops_preview_frame")
        preview_frame.setFrame(-0.25, 0.25, -0.141, 0.141)
        self.operation_map_preview = root.attachNewNode(preview_frame.generate())
        self.operation_map_preview.setPos(0.98, 0, 0.13)
        self.operation_map_preview.setColor(0.05, 0.08, 0.12, 0.94)
        self.operation_map_preview.setTransparency(TransparencyAttrib.MAlpha)
        self.operation_map_preview.setBin("fixed", 5)
        self.operation_map_preview.setDepthTest(False)
        self.operation_map_preview.setDepthWrite(False)
        self.operation_map_nodes.append(self.operation_map_preview)
        self.operation_map_preview_texture_path = None

        preview_border = LineSegs("starfall_ops_preview_border")
        preview_border.setThickness(1.3)
        preview_border.setColor(0.22, 0.62, 0.90, 0.34)
        preview_pts = [(-0.25, -0.141), (0.25, -0.141), (0.25, 0.141), (-0.25, 0.141), (-0.25, -0.141)]
        preview_border.moveTo(preview_pts[0][0], 0.0, preview_pts[0][1])
        for px, pz in preview_pts[1:]:
            preview_border.drawTo(px, 0.0, pz)
        preview_border_np = root.attachNewNode(preview_border.create())
        preview_border_np.setPos(0.98, 0, 0.13)
        preview_border_np.setTransparency(TransparencyAttrib.MAlpha)
        self.operation_map_nodes.append(preview_border_np)

        self.operation_map_selection_text = OnscreenText(text="", parent=root, pos=(0.65, -0.085), scale=0.030,
                                                         fg=(0.90, 0.97, 1.0, 0.90), align=TextNode.ALeft,
                                                         mayChange=True, wordwrap=23)
        self.operation_map_nodes.append(self.operation_map_selection_text)
        self.operation_map_status_text = OnscreenText(text="", parent=root, pos=(0.65, -0.49), scale=0.025,
                                                      fg=(0.72, 0.95, 1.0, 0.88), align=TextNode.ALeft,
                                                      mayChange=True)
        self.operation_map_nodes.append(self.operation_map_status_text)

        self.operation_map_launch_button = DirectButton(parent=root, text="LAUNCH SELECTED OPERATION", pos=(0.98, 0, -0.66),
                                                       scale=1.0, frameSize=(-0.30, 0.30, -0.055, 0.055),
                                                       frameColor=(0.08, 0.24, 0.32, 0.58), text_scale=0.030,
                                                       text_fg=(0.85, 1.0, 1.0, 1.0), relief=1,
                                                       command=self.launch_operation_from_map)
        self.operation_map_nodes.append(self.operation_map_launch_button)
        self.operation_map_back_button = DirectButton(parent=root, text="BACK", pos=(-1.17, 0, -0.69),
                                                     scale=1.0, frameSize=(-0.14, 0.14, -0.046, 0.046),
                                                     frameColor=(0.07, 0.10, 0.14, 0.44), text_scale=0.029,
                                                     text_fg=(0.82, 0.94, 1.0, 0.96), relief=1,
                                                     command=self.hide_saturn_operations_map)
        self.operation_map_nodes.append(self.operation_map_back_button)
        self.operation_map_safe_bounds = {
            "detail_panel": (0.60, 1.32, -0.60, 0.40),
            "preview": (0.73, 1.23, -0.011, 0.271),
            "launch_button": (0.68, 1.28, -0.715, -0.605),
            "back_button": (-1.31, -1.03, -0.736, -0.644),
        }
        self.update_saturn_operations_map()

    def show_saturn_operations_map(self) -> None:
        if getattr(self, "operation_active", False):
            return
        self.hide_pause_menu()
        self.hide_shell_help(keep_cursor=True)
        root = getattr(self, "operation_map_root", None)
        if root is not None and not root.isEmpty():
            root.show()
        self.operation_map_open = True
        self._suppress_shell_hud_for_panel()
        self._set_shell_cursor_free(True)
        self.update_saturn_operations_map()
        self.set_loop_feedback("STARFALL OPS MAP", 1.4)

    def hide_saturn_operations_map(self, keep_cursor: bool = False) -> None:
        root = getattr(self, "operation_map_root", None)
        if root is not None and not root.isEmpty():
            root.hide()
        self.operation_map_open = False
        if not keep_cursor and not getattr(self, "pause_menu_open", False) and not getattr(self, "shell_help_open", False):
            self._set_shell_cursor_free(False)
        self._restore_shell_hud_after_panel()

    def select_operation_on_map(self, code: str) -> None:
        for i, station in enumerate(getattr(self, "observatory_stations", [])):
            if station[0] == code:
                self.observatory_station_index = i
                break
        self.update_observatory_station_panels()
        self.update_saturn_operations_map()
        target = OPERATION_TARGETS.get(code, {})
        if target.get("status") == "READY" or code == "ANOM":
            self.set_loop_feedback(f"TARGET SELECTED: {target.get('title', code).upper()}", 1.3)
        else:
            self.set_loop_feedback(f"{target.get('title', code).upper()} PLANNED", 1.6)

    def update_saturn_operations_map(self) -> None:
        node = getattr(self, "operation_map_selection_text", None)
        if node is None:
            return
        code = self.selected_operation_code()
        target = OPERATION_TARGETS.get(code, {})
        status = str(target.get("status", "LOCAL"))
        launch_word = "READY FOR DEPLOYMENT" if status == "READY" else ("INTERIOR ANALYSIS" if code == "ANOM" else "PLANNED / LOCKED")
        mission = _trim_ui(target.get('mission', 'No mission data'), 42)
        resources = _trim_ui(target.get('resources', 'No resource profile'), 38)
        tip = _trim_ui(target.get('tip', 'No tip loaded'), 42)
        node.setText(
            f"TARGET: {_trim_ui(target.get('title', code), 34)}\n"
            f"STATUS: {status}\n"
            f"TASK: {mission}\n"
            f"FIND: {resources}\n"
            f"TIP: {tip}"
        )
        status_node = getattr(self, "operation_map_status_text", None)
        if status_node is not None:
            status_node.setText(f"{launch_word} // SELECTED NODE: {code}")
        launch_button = getattr(self, "operation_map_launch_button", None)
        if launch_button is not None:
            if status == "READY":
                launch_button["text"] = "LAUNCH SELECTED OPERATION"
                launch_button["frameColor"] = (0.08, 0.24, 0.32, 0.58)
                launch_button["text_fg"] = (0.85, 1.0, 1.0, 1.0)
            elif code == "ANOM":
                launch_button["text"] = "INTERIOR ANALYSIS / NO FLIGHT"
                launch_button["frameColor"] = (0.06, 0.16, 0.22, 0.48)
                launch_button["text_fg"] = (0.74, 0.94, 1.0, 1.0)
            else:
                launch_button["text"] = "OPERATION LOCKED"
                launch_button["frameColor"] = (0.08, 0.08, 0.10, 0.32)
                launch_button["text_fg"] = (0.55, 0.58, 0.62, 0.95)
        for btn_code, btn in getattr(self, "operation_map_buttons", {}).items():
            if btn is None:
                continue
            # Pass71: keep moon/text hit regions active without drawing square boxes.
            btn["frameColor"] = (0.0, 0.0, 0.0, 0.0)
        self._update_operation_map_preview(code)

    def _update_operation_map_preview(self, code: str) -> None:
        preview = getattr(self, "operation_map_preview", None)
        if preview is None or preview.isEmpty():
            return
        target = OPERATION_TARGETS.get(code, {})
        moon_code = str(target.get("moon") or code).lower()
        art_path = Path(__file__).resolve().parent / "assets" / "generated" / f"operation_loading_{moon_code}.png"
        fallback = Path(__file__).resolve().parent / "assets" / "generated" / "operation_loading_enceladus.png"
        chosen = art_path if art_path.exists() else fallback
        if getattr(self, "operation_map_preview_texture_path", None) == str(chosen):
            return
        try:
            tex = self.loader.loadTexture(Filename.fromOsSpecific(str(chosen)))
            preview.setTexture(tex, 1)
            preview.setColor(1.0, 1.0, 1.0, 1.0)
            self.operation_map_preview_texture_path = str(chosen)
        except Exception:
            preview.clearTexture()
            preview.setColor(0.05, 0.08, 0.12, 0.94)
            self.operation_map_preview_texture_path = None

    def launch_operation_from_map(self, code: str | None = None) -> None:
        if code:
            self.select_operation_on_map(code)
        code = self.selected_operation_code()
        target = OPERATION_TARGETS.get(code, {})
        if code == "ANOM":
            self.hide_saturn_operations_map()
            self.set_loop_feedback("ANOMALY ANALYSIS // INTERIOR ONLY", 1.8)
            return
        if target.get("status") != "READY" or not target.get("moon"):
            self.set_loop_feedback(f"{target.get('title', code)} PLANNED", 2.0)
            self.update_saturn_operations_map()
            return
        self.hide_saturn_operations_map()
        self.begin_operation_loading(code)

    # -----------------------------
    # Scene construction
    # -----------------------------
    def build_space_backdrop(self) -> None:
        # Dark background sphere replacement: large cards/points/planet generated from primitives.
        self.setBackgroundColor(0.005, 0.006, 0.014, 1)
        stars = self.flight_root.attachNewNode("Procedural Starfield")
        rng = 1337
        # Small deterministic LCG so no random import/state noise.
        def rand() -> float:
            nonlocal rng
            rng = (1103515245 * rng + 12345) & 0x7FFFFFFF
            return rng / 0x7FFFFFFF
        for i in range(90):
            x = (rand() - 0.5) * 320
            y = (rand() - 0.5) * 320
            z = (rand() - 0.5) * 130 + 22
            s = 0.018 + rand() * 0.058
            warmth = rand()
            # Natural star fields are not all blue-white; mix dim amber, white, and cold blue points.
            col = (0.58 + warmth * 0.34, 0.62 + rand() * 0.26, 0.72 + rand() * 0.28, 1)
            if warmth > 0.72:
                col = (0.95, 0.78 + rand() * 0.15, 0.55 + rand() * 0.20, 1)
            star = create_box(stars, f"star_{i}", Vec3(x, y, z), Vec3(s, s, s), col, emission=(col[0]*0.18, col[1]*0.20, col[2]*0.32, 1))
            star.setBillboardPointEye()

        # Layered dust lanes and sparse bright stars make the scene feel less flat in screenshots.
        for i in range(9):
            x = -52 + i * 13.0
            y = 92 + math.sin(i * 1.7) * 8.0
            z = 18 + math.sin(i * 0.9) * 15.0
            haze = create_glow_card(self.flight_root, f"distant ion dust lane_{i}", Vec3(x, y, z), 8.0 + (i % 3) * 3.0, (0.08, 0.20 + 0.03 * (i % 2), 0.55, 0.055), hpr=Vec3(0, 90, i * 7))
            haze.setDepthWrite(False)
        for i in range(18):
            a = i / 18 * math.tau
            x = math.cos(a) * 82
            y = 104 + math.sin(i * 0.77) * 22
            z = 26 + math.sin(a) * 34
            star = create_glow_card(self.flight_root, f"large parallax star flare_{i}", Vec3(x, y, z), 0.28 + (i % 4) * 0.08, (0.55, 0.74, 1.0, 0.22), hpr=Vec3(0, 90, 0))
            star.setDepthWrite(False)

        if STARFALL_FAST_PROFILE:
            self.build_pass16_fast_space_canvas()
        else:
            self.build_natural_deep_space_layers()
            self.build_visible_anomaly_sky_canvas()
            self.build_cinematic_space_panorama()
            self.build_pass08_flythrough_galaxy_field(self.flight_root, 8808)

        # Broken planet curve and orbital ring silhouettes behind the ship.
        planet = create_cylinder_y(self.flight_root, "Distant cracked planet", Vec3(0, 75, -42), 34, 0.45, 96, (0.03, 0.04, 0.07, 1), hpr=Vec3(90, 0, 0))
        planet.setScale(1.6, 1, 0.55)
        self.anchor_scene_nodes.append(planet)
        station_frame = create_outline_box(self.flight_root, "Station test frame", Vec3(0, 18, 0), Vec3(14, 2.6, 8), (0.06, 0.65, 1.0, 0.45), thickness=2.0)
        self.anchor_scene_nodes.append(station_frame)
        ring_root = self.flight_root.attachNewNode("broken orbital ring")
        self.anchor_scene_nodes.append(ring_root)
        for idx in range(14):
            angle = idx / 14 * math.tau
            x = math.cos(angle) * 44
            z = math.sin(angle) * 10 - 32
            y = 75 + math.sin(angle) * 5
            seg = create_box(ring_root, f"orbital_ring_segment_{idx}", Vec3(x, y, z), Vec3(5.5, 0.14, 0.22), (0.09, 0.13, 0.18, 1), hpr=Vec3(math.degrees(-angle), 0, 12))
            if idx % 3 == 0:
                create_box(seg, f"ring_neon_{idx}", Vec3(0, 0, 0.15), Vec3(4.2, 0.08, 0.045), (0.06, 0.55, 1.0, 1), emission=(0.02, 0.22, 0.5, 1))

        # Docking-bay scene near player for scale and presentation.  It frames the ship without trapping it.
        bay = self.flight_root.attachNewNode("orbital drydock bay")
        self.anchor_scene_nodes.append(bay)
        create_box(bay, "drydock runway deck", Vec3(0, 7.2, -1.55), Vec3(10.8, 24.0, 0.16), (0.035, 0.042, 0.065, 1), emission=(0.002, 0.004, 0.010, 1))
        create_box(bay, "central launch rail", Vec3(0, 7.2, -1.42), Vec3(1.15, 23.0, 0.10), (0.06, 0.075, 0.105, 1), emission=(0.004, 0.008, 0.018, 1))
        for sx in (-1, 1):
            create_box(bay, "drydock side truss", Vec3(sx * 7.8, 7.0, 1.5), Vec3(0.42, 24.0, 0.42), (0.07, 0.08, 0.12, 1), emission=(0.006, 0.008, 0.018, 1))
            create_box(bay, "drydock lower rail glow", Vec3(sx * 3.45, 7.0, -1.23), Vec3(0.16, 23.0, 0.075), (0.0, 0.55, 1.0, 1), emission=(0.0, 0.25, 0.70, 1))
            create_box(bay, "drydock upper guide light", Vec3(sx * 7.15, 7.0, 5.25), Vec3(0.12, 22.0, 0.10), (0.0, 0.40, 0.92, 1), emission=(0.0, 0.18, 0.48, 1))
            create_box(bay, "service catwalk", Vec3(sx * 5.85, 7.0, 1.15), Vec3(1.1, 22.0, 0.12), (0.055, 0.064, 0.086, 1), emission=(0.004, 0.006, 0.014, 1))
            for y in (-2.8, 1.8, 6.4, 11.0, 15.6):
                create_box(bay, "drydock vertical support", Vec3(sx * 7.8, y, 1.55), Vec3(0.50, 0.36, 6.15), (0.08, 0.09, 0.13, 1), emission=(0.006, 0.008, 0.018, 1))
                create_box(bay, "cross bay arch", Vec3(0, y, 5.65), Vec3(15.8, 0.32, 0.36), (0.075, 0.085, 0.125, 1), emission=(0.006, 0.008, 0.018, 1))
                beacon = create_box(bay, "animated docking beacon", Vec3(sx * 7.18, y, 4.85), Vec3(0.18, 0.18, 0.18), (0.0, 0.72, 1.0, 1), emission=(0.0, 0.34, 0.9, 1))
                self.hangar_beacons.append(beacon)
            clamp = create_box(bay, "open docking clamp arm", Vec3(sx * 2.45, -1.75, 0.08), Vec3(0.24, 2.2, 0.24), (0.16, 0.18, 0.23, 1), hpr=Vec3(sx * 22, 0, 0), emission=(0.010, 0.014, 0.026, 1))
            claw = create_box(clamp, "magnetic clamp pad", Vec3(0, -1.18, 0), Vec3(0.62, 0.22, 0.62), (0.0, 0.58, 1.0, 1), emission=(0.0, 0.24, 0.64, 1))
            self.docking_clamps.extend([clamp, claw])
        # Transparent blue bay forcefield at the far end, readable but non-blocking.
        forcefield = create_box(bay, "far bay forcefield plane", Vec3(0, 18.9, 1.15), Vec3(12.8, 0.06, 4.4), (0.0, 0.36, 1.0, 0.14), emission=(0.0, 0.15, 0.45, 1))
        forcefield.setDepthWrite(False)
        create_outline_box(bay, "bay mouth outline", Vec3(0, 18.75, 1.15), Vec3(13.2, 0.05, 4.8), (0.0, 0.64, 1.0, 0.62), thickness=2.0)
        # Pass 05: stronger drydock depth, runway markings, and scale cues.
        for y in (-2.2, 0.6, 3.4, 6.2, 9.0, 11.8, 14.6, 17.4):
            create_box(bay, "angled runway chevron left", Vec3(-1.18, y, -1.31), Vec3(0.85, 0.075, 0.055), (0.0, 0.62, 1.0, 1), hpr=Vec3(0, 0, -22), emission=(0.0, 0.22, 0.62, 1))
            create_box(bay, "angled runway chevron right", Vec3(1.18, y, -1.31), Vec3(0.85, 0.075, 0.055), (0.0, 0.62, 1.0, 1), hpr=Vec3(0, 0, 22), emission=(0.0, 0.22, 0.62, 1))
        for sx in (-1, 1):
            for y in (-1.0, 4.4, 9.8, 15.2):
                create_outline_box(bay, "service gantry cage", Vec3(sx * 5.85, y, 2.92), Vec3(1.25, 1.0, 2.7), (0.0, 0.42, 1.0, 0.30), thickness=1.4)
                create_box(bay, "maintenance pod amber window", Vec3(sx * 6.45, y, 3.15), Vec3(0.06, 0.52, 0.32), (1.0, 0.48, 0.08, 0.75), emission=(0.34, 0.10, 0.012, 1))
        create_glow_card(bay, "bay volumetric blue spill", Vec3(0, 11.5, 3.0), 7.6, (0.0, 0.42, 1.0, 0.07), hpr=Vec3(0, 90, 0))

        self.build_anchor_station_and_anomaly()
        # Start at the anchor drydock near the rare anomaly. The first clicked lensing body
        # now spawns a full procedural solar system around the ship.
        self.current_chunk_name = "Anchor Drydock"
        self.current_chunk_kind = "station"
        self.reseed_lensing_targets(9201)

    # -----------------------------
    def build_pass16_fast_space_canvas(self) -> None:
        """Lightweight natural space backdrop for the 60 FPS profile."""
        canvas = self.flight_root.attachNewNode("pass16 fast natural space canvas")
        canvas.setDepthWrite(False)
        canvas.setTransparency(TransparencyAttrib.M_alpha)
        # A few broad, cheap layers replace the many decorative galaxy objects from earlier passes.
        for i in range(6):
            x = -42 + i * 16.5
            y = 82 + math.sin(i * 1.3) * 10.0
            z = 18 + math.sin(i * 0.75) * 18.0
            col = (0.10 + i * 0.010, 0.18 + (i % 2) * 0.05, 0.42 + (i % 3) * 0.06, 0.050)
            create_soft_disc_y(canvas, "pass16 cheap milky dust lobe", Vec3(x, y, z), 12.0 + (i % 3) * 3.0, 2.4 + (i % 2) * 0.8, col, (col[0], col[1], col[2], 0.0), 24, hpr=Vec3(0, 0, -15 + i * 8))
        # One distant galaxy impression, two arcs plus a core, instead of many clumps.
        g = canvas.attachNewNode("pass16 single fast distant spiral")
        g.setPos(-24, 74, 31)
        g.setScale(1.65)
        g.setHpr(18, 0, -15)
        create_soft_disc_y(g, "pass16 fast galaxy core", Vec3(0, 0, 0), 2.4, 1.05, (1.0, 0.72, 0.40, 0.20), (0.34, 0.16, 0.05, 0.0), 28)
        create_annular_arc_y(g, "pass16 fast galaxy arm A", Vec3(0, 0.04, 0), 1.4, 4.4, 15, 250, 32, (0.32, 0.52, 0.95, 0.105), hpr=Vec3(0, 0, -18), emission=(0.04, 0.08, 0.18, 1))
        create_annular_arc_y(g, "pass16 fast galaxy arm B", Vec3(0, 0.06, 0), 1.6, 4.8, 200, 430, 32, (0.30, 0.48, 0.86, 0.090), hpr=Vec3(0, 0, -18), emission=(0.04, 0.08, 0.16, 1))
        # A few cheap glow points keep depth without extra procedural clusters.
        for i in range(10):
            u = seeded_unit(16000 + i * 17)
            v = seeded_unit(16100 + i * 19)
            star = create_glow_card(canvas, "pass16 cheap bright star", Vec3(-56 + u * 112, 58 + v * 60, -2 + seeded_unit(16200+i) * 42), 0.06 + 0.08 * u, (0.52, 0.68, 1.0, 0.22), hpr=Vec3(0, 90, 0))
            if i % 4 == 0:
                self.cosmic_twinklers.append(star)

    def build_pass16_fast_destination_sky(self, root: NodePath, kind: str, accent: tuple[float, float, float, float], seed: int) -> None:
        """Low-node destination atmosphere for fast mode."""
        fast = root.attachNewNode(f"pass16 fast destination sky {kind}")
        fast.setDepthWrite(False)
        fast.setTransparency(TransparencyAttrib.M_alpha)
        for i in range(5):
            u = seeded_unit(seed + 21000 + i * 23)
            x = -44 + u * 88
            y = 62 + i * 16.0
            z = -8 + seeded_unit(seed + 21100 + i * 17) * 54
            col = (min(1.0, accent[0] * 0.35 + 0.14), min(1.0, accent[1] * 0.35 + 0.18), min(1.0, accent[2] * 0.38 + 0.32), 0.055)
            create_soft_disc_y(fast, "pass16 fast destination gas layer", Vec3(x, y, z), 16.0 + i * 2.2, 1.6 + (i % 2) * 0.45, col, (col[0], col[1], col[2], 0.0), 22, hpr=Vec3(0, 0, -12 + i * 9))
        for i in range(12):
            u = seeded_unit(seed + 22000 + i * 11)
            v = seeded_unit(seed + 22100 + i * 13)
            star = create_glow_card(fast, "pass16 fast destination star", Vec3(-55 + u * 110, 74 + v * 170, -18 + seeded_unit(seed + i) * 70), 0.035 + u * 0.050, (0.50 + accent[0] * 0.20, 0.58 + accent[1] * 0.18, 0.80 + accent[2] * 0.16, 0.22), hpr=Vec3(0, 90, 0))
            if i % 5 == 0:
                self.cosmic_twinklers.append(star)

    def build_natural_deep_space_layers(self) -> None:
        """Pass 06/07: natural background composition inspired by Hubble/Webb galaxy imagery.

        The intent is not a scientific simulation; it is a more believable photographic sky:
        spiral arms, warm galaxy cores, blue star-forming knots, brown dust lanes, and faint
        uneven nebula veils instead of flat arcade rings.
        """
        deep = self.flight_root.attachNewNode("natural deep space backdrop")

        # Large, low-contrast galactic dust glow across the far field.
        for i, (x, y, z, rx, rz, col, h) in enumerate([
            (-74, 128, 34, 38, 5.5, (0.42, 0.48, 0.62, 0.055), -8),
            (-36, 122, 23, 32, 4.8, (0.22, 0.30, 0.48, 0.050), 9),
            (18, 132, 36, 44, 6.4, (0.36, 0.24, 0.48, 0.043), -15),
            (63, 118, 18, 30, 4.2, (0.50, 0.28, 0.18, 0.035), 16),
        ]):
            create_soft_disc_y(deep, f"milky dust veil_{i}", Vec3(x, y, z), rx, rz, col, (col[0], col[1], col[2], 0.0), 64, hpr=Vec3(0, 0, h))

        # Face-on spiral galaxy: warm old-star core, blue arms, reddish star-forming knots,
        # and dark dusty gaps, echoing real spiral reference images.
        galaxy = deep.attachNewNode("distant natural spiral galaxy")
        galaxy.setPos(-54, 142, 34)
        galaxy.setHpr(0, 0, -17)
        create_soft_disc_y(galaxy, "galaxy warm central bulge", Vec3(0, 0, 0), 5.6, 3.0, (1.0, 0.78, 0.42, 0.18), (0.55, 0.38, 0.20, 0.0), 80)
        create_soft_disc_y(galaxy, "galaxy faint outer halo", Vec3(0, -0.01, 0), 13.5, 6.6, (0.40, 0.55, 0.82, 0.050), (0.08, 0.12, 0.22, 0.0), 80)
        for arm in range(2):
            arm_phase = arm * math.pi
            for j in range(30):
                t = j / 45.0
                a = arm_phase + t * 2.35 * math.pi
                r = 2.0 + t * 11.6
                x = math.cos(a) * r
                z = math.sin(a) * r * 0.54
                width = 0.48 + t * 0.64
                alpha = 0.030 + (1.0 - abs(t - 0.56) * 1.6) * 0.028
                create_soft_disc_y(galaxy, "blue spiral arm mist", Vec3(x, 0.02 + j*0.0004, z), width, width*0.38, (0.30, 0.48, 0.82, max(0.010, alpha)), (0.10, 0.14, 0.24, 0.0), 20, hpr=Vec3(0, 0, math.degrees(a) + 18))
                if j % 7 in (1, 5):
                    create_soft_disc_y(galaxy, "pink star forming knot", Vec3(x*1.01, 0.05, z*1.01), 0.32, 0.16, (1.0, 0.28, 0.36, 0.16), (1.0, 0.22, 0.24, 0.0), 16, hpr=Vec3(0, 0, math.degrees(a)))
                if j % 9 == 3:
                    create_soft_disc_y(galaxy, "brown dust lane gap", Vec3(x*0.96, 0.07, z*0.94), 0.70, 0.18, (0.04, 0.025, 0.018, 0.11), (0.0, 0.0, 0.0, 0.0), 16, hpr=Vec3(0, 0, math.degrees(a) - 8))

        # Edge-on galaxy: thin bright disk with a dark dust lane through the middle.
        edge = deep.attachNewNode("edge on dust lane galaxy")
        edge.setPos(72, 148, 43)
        edge.setHpr(0, 0, 8)
        create_soft_disc_y(edge, "edge galaxy amber core", Vec3(0, 0, 0), 4.2, 1.4, (1.0, 0.70, 0.36, 0.16), (0.40, 0.24, 0.11, 0.0), 64)
        create_soft_disc_y(edge, "edge galaxy blue disk", Vec3(0, 0.02, 0), 18.0, 1.6, (0.32, 0.48, 0.78, 0.070), (0.08, 0.11, 0.20, 0.0), 64)
        create_box(edge, "edge galaxy dark dust lane", Vec3(0, 0.04, -0.02), Vec3(26.0, 0.02, 0.16), (0.002, 0.001, 0.001, 0.28), hpr=Vec3(0, 0, 1))

        # Uneven faint nebula cloud, kept low-alpha so it reads as distant gas rather than UI.
        cloud = deep.attachNewNode("faint irregular nebula cloud")
        cloud.setPos(18, 136, 18)
        for i in range(18):
            a = i * 2.399
            r = 4.0 + (i % 6) * 2.0
            x = math.cos(a) * r + math.sin(i * 1.7) * 4.0
            z = math.sin(a) * r * 0.55 + math.cos(i * 0.8) * 2.6
            rx = 3.5 + (i % 5) * 0.8
            rz = 1.2 + (i % 4) * 0.45
            col = (0.36 + (i % 3)*0.06, 0.16 + (i % 5)*0.03, 0.52 + (i % 2)*0.08, 0.030 + (i % 4)*0.006)
            create_soft_disc_y(cloud, "overlapping natural nebula puff", Vec3(x, i*0.003, z), rx, rz, col, (col[0], col[1], col[2], 0.0), 32, hpr=Vec3(0, 0, i * 13))
        for i in range(7):
            create_soft_disc_y(cloud, "nebula dark dust incision", Vec3(-8 + i*2.8, 0.12, 2.5 + math.sin(i)*2.0), 3.0, 0.42, (0.0, 0.0, 0.0, 0.13), (0.0, 0.0, 0.0, 0.0), 24, hpr=Vec3(0, 0, -28 + i*7))

    def build_visible_anomaly_sky_canvas(self) -> None:
        """Composes natural space forms in the same sightline as the anomaly.

        The earlier deep-space layers sit far outside many test-camera angles; this layer makes
        the galaxy/dust improvements visible during actual play while remaining behind the lens.
        """
        canvas = self.flight_root.attachNewNode("visible anomaly sky canvas")
        # Soft background galactic light, like a dim Milky Way band viewed through the drydock.
        for i, spec in enumerate([
            (-28, 54, 16, 18, 2.8, (0.30, 0.38, 0.55, 0.070), -10),
            (-8, 58, 20, 22, 3.0, (0.46, 0.28, 0.42, 0.060), 5),
            (18, 56, 14, 16, 2.2, (0.52, 0.30, 0.18, 0.050), 15),
            (38, 62, 22, 20, 2.5, (0.20, 0.30, 0.50, 0.052), -18),
        ]):
            x, y, z, rx, rz, col, h = spec
            create_soft_disc_y(canvas, f"playline galactic dust glow_{i}", Vec3(x, y, z), rx, rz, col, (col[0], col[1], col[2], 0.0), 64, hpr=Vec3(0, 0, h))
        # A small face-on spiral off to the left of the anomaly, visibly more organic than target boxes.
        g = canvas.attachNewNode("visible small spiral galaxy")
        g.setPos(-22, 58, -5)
        g.setHpr(0, 0, -22)
        create_soft_disc_y(g, "visible galaxy core", Vec3(0, 0, 0), 2.8, 1.35, (1.0, 0.74, 0.42, 0.26), (0.45, 0.25, 0.10, 0.0), 64)
        create_soft_disc_y(g, "visible galaxy halo", Vec3(0, -0.01, 0), 7.0, 3.1, (0.30, 0.46, 0.78, 0.080), (0.06, 0.10, 0.18, 0.0), 64)
        for arm in range(2):
            phase = arm * math.pi
            for j in range(24):
                t = j / 23.0
                a = phase + t * math.pi * 2.15
                r = 0.8 + t * 6.3
                x = math.cos(a) * r
                z = math.sin(a) * r * 0.48
                create_soft_disc_y(g, "visible galaxy spiral arm clump", Vec3(x, 0.02 + j*0.001, z), 0.44 + t*0.34, 0.15 + t*0.07, (0.28, 0.48, 0.86, 0.070), (0.08, 0.12, 0.20, 0.0), 16, hpr=Vec3(0, 0, math.degrees(a)))
                if j % 6 == 2:
                    create_soft_disc_y(g, "visible pink star forming patch", Vec3(x*1.04, 0.05, z*1.02), 0.24, 0.10, (1.0, 0.28, 0.34, 0.22), (1.0, 0.20, 0.20, 0.0), 14, hpr=Vec3(0, 0, math.degrees(a)))
        # Fallback visible natural layers built from proven glow-card / annular-arc primitives.
        # These are intentionally soft and low-contrast so they read as space photography, not UI.
        create_glow_card(canvas, "visible amber galaxy card core", Vec3(-12, 50, -3), 2.2, (1.0, 0.72, 0.35, 0.19), hpr=Vec3(0, 90, 0))
        create_glow_card(canvas, "visible blue galaxy card halo", Vec3(-12, 50.05, -3), 5.8, (0.28, 0.42, 0.78, 0.085), hpr=Vec3(0, 90, 0))
        create_annular_arc_y(canvas, "visible galaxy soft spiral arm A", Vec3(-12, 50.12, -3), 2.0, 4.8, 20, 260, 64, (0.30, 0.50, 0.95, 0.105), hpr=Vec3(0, 0, -18), emission=(0.06, 0.10, 0.20, 1))
        create_annular_arc_y(canvas, "visible galaxy soft spiral arm B", Vec3(-12, 50.16, -3), 2.1, 5.3, 200, 440, 64, (0.32, 0.50, 0.88, 0.088), hpr=Vec3(0, 0, -18), emission=(0.05, 0.09, 0.18, 1))
        create_annular_arc_y(canvas, "visible galaxy brown dust arm A", Vec3(-12, 50.20, -3), 2.5, 2.95, 48, 230, 46, (0.05, 0.025, 0.012, 0.19), hpr=Vec3(0, 0, -18), emission=(0, 0, 0, 1))
        for i in range(9):
            create_glow_card(canvas, f"visible star forming pink knot_{i}", Vec3(-15.7 + i*0.85, 50.28 + i*0.01, -4.7 + math.sin(i)*2.15), 0.18 + (i%3)*0.045, (1.0, 0.23, 0.34, 0.25), hpr=Vec3(0, 90, 0))
        for i in range(7):
            create_glow_card(canvas, f"visible uneven gas patch_{i}", Vec3(-34 + i*10.8, 54 + i*0.05, -7 + math.sin(i*1.2)*4.2), 5.0 + (i%3)*1.4, (0.20 + i*0.015, 0.22, 0.42 + (i%2)*0.10, 0.035), hpr=Vec3(0, 90, -10 + i*5))
        create_glow_card(canvas, "visible edge galaxy bright core", Vec3(24, 52, -6), 1.8, (1.0, 0.68, 0.34, 0.17), hpr=Vec3(0, 90, 0))
        create_box(canvas, "visible edge galaxy luminous disk", Vec3(24, 52.04, -6), Vec3(11.0, 0.03, 0.38), (0.30, 0.42, 0.70, 0.22), hpr=Vec3(0, 0, 9), emission=(0.04, 0.08, 0.16, 1))
        create_box(canvas, "visible edge galaxy dark dust split", Vec3(24, 52.08, -6), Vec3(12.5, 0.03, 0.09), (0.0, 0.0, 0.0, 0.32), hpr=Vec3(0, 0, 9), emission=(0, 0, 0, 1))

        # Dark dust lanes crossing the bright band, based on real dark dust absorption features.
        for i in range(8):
            create_soft_disc_y(canvas, "visible dark galactic dust lane", Vec3(-34 + i*9.0, 62 + i*0.02, -8 + math.sin(i*0.8)*2.6), 5.8, 0.42, (0.0, 0.0, 0.0, 0.16), (0.0, 0.0, 0.0, 0.0), 24, hpr=Vec3(0, 0, -16 + i*5))

    def build_cinematic_space_panorama(self) -> None:
        """Pass 08: visible natural space panorama for normal play screenshots.

        Earlier layers were accurate but too subtle from the third-person camera. This layer
        keeps them natural, but places brighter low-alpha galaxy and dust structures in
        the playable sightlines so the player actually sees space depth behind the drydock.
        """
        pano = self.flight_root.attachNewNode("pass07 cinematic natural space panorama")

        # Big painterly sky plates in the normal flight camera sightline. They are low-detail,
        # low-alpha glow cards so the background reads as real gas/star clouds instead of UI arcs.
        for idx, (x, y, z, scale, col, roll) in enumerate([
            (-56, 42, 30, 19.0, (0.16, 0.24, 0.48, 0.145), -18),
            (-27, 45, 36, 23.0, (0.30, 0.22, 0.46, 0.125), -11),
            (4, 47, 33, 24.0, (0.48, 0.32, 0.22, 0.108), -4),
            (33, 49, 27, 20.0, (0.18, 0.32, 0.54, 0.118), 7),
            (60, 52, 19, 15.0, (0.12, 0.18, 0.36, 0.112), 15),
        ]):
            card = create_glow_card(pano, f"pass07 visible upper nebula wash_{idx}", Vec3(x, y, z), scale, col, hpr=Vec3(0, 90, roll))
            card.setBin("background", 5)
            card.setDepthWrite(False)
            card.setDepthTest(False)
        # Dark interruptions through the nebula plates keep the cloud from looking like one flat color.
        for idx in range(6):
            cut = create_soft_disc_y(pano, "pass07 visible upper dark nebula rift", Vec3(-48 + idx*18.0, 52 + idx*0.03, 25 + math.sin(idx)*6.0), 9.2, 0.62, (0.0, 0.0, 0.0, 0.22), (0.0, 0.0, 0.0, 0.0), 28, hpr=Vec3(0, 0, -12 + idx*5))
            cut.setBin("background", 6)
            cut.setDepthTest(False)

        # Prominent but soft galaxy shapes in the upper play view; these are intentionally
        # translucent so they read as distant space while still being visible in screenshots.
        flight_galaxy = pano.attachNewNode("pass07 flight-visible soft galaxy")
        flight_galaxy.setPos(-48, 35, 21)
        flight_galaxy.setHpr(0, 0, -14)
        for node in [
            create_glow_card(flight_galaxy, "flight galaxy broad amber core", Vec3(0, 0, 0), 3.4, (1.0, 0.68, 0.36, 0.26), hpr=Vec3(0, 90, 0)),
            create_glow_card(flight_galaxy, "flight galaxy blue outer disk", Vec3(0, 0.04, 0), 8.0, (0.24, 0.42, 0.84, 0.15), hpr=Vec3(0, 90, 0)),
        ]:
            node.setDepthTest(False)
        create_annular_arc_y(flight_galaxy, "flight galaxy spiral arc upper", Vec3(0, 0.08, 0), 2.2, 5.9, 12, 236, 72, (0.34, 0.56, 1.0, 0.18), hpr=Vec3(0, 0, -18), emission=(0.06, 0.12, 0.25, 1)).setDepthTest(False)
        create_annular_arc_y(flight_galaxy, "flight galaxy spiral arc lower", Vec3(0, 0.10, 0), 2.0, 6.4, 192, 430, 72, (0.28, 0.48, 0.90, 0.15), hpr=Vec3(0, 0, -18), emission=(0.05, 0.10, 0.22, 1)).setDepthTest(False)
        for i in range(10):
            knot = create_glow_card(flight_galaxy, f"flight galaxy pink knot_{i}", Vec3(-5 + i*1.05, 0.15 + i*0.004, math.sin(i*0.9)*2.8), 0.20+(i%3)*0.04, (1.0, 0.24, 0.34, 0.28), hpr=Vec3(0, 90, 0))
            knot.setDepthTest(False)

        # Lower-left sky forms sit inside the actual third-person camera frame; this makes the
        # visual upgrade visible without changing flight controls or camera behavior.
        low = pano.attachNewNode("pass07 low-frame galaxy and star nursery")
        low.setPos(-58, 35, 4.8)
        low.setHpr(0, 0, -8)
        for node in [
            create_glow_card(low, "low frame galaxy core", Vec3(0, 0, 0), 2.6, (1.0, 0.70, 0.34, 0.42), hpr=Vec3(0, 90, 0)),
            create_glow_card(low, "low frame blue stellar disk", Vec3(0, 0.04, 0), 7.2, (0.24, 0.42, 0.90, 0.20), hpr=Vec3(0, 90, 0)),
            create_glow_card(low, "low frame purple gas veil", Vec3(8.0, 0.06, 1.4), 11.0, (0.34, 0.16, 0.50, 0.11), hpr=Vec3(0, 90, 12)),
        ]:
            node.setDepthTest(False)
        create_annular_arc_y(low, "low frame spiral arm one", Vec3(0, 0.12, 0), 1.8, 5.2, 12, 240, 64, (0.34, 0.56, 1.0, 0.090), hpr=Vec3(0, 0, -14), emission=(0.06, 0.12, 0.28, 1)).setDepthTest(False)
        create_annular_arc_y(low, "low frame spiral arm two", Vec3(0, 0.14, 0), 1.9, 5.7, 190, 430, 64, (0.36, 0.54, 0.92, 0.075), hpr=Vec3(0, 0, -14), emission=(0.05, 0.10, 0.24, 1)).setDepthTest(False)
        for i in range(18):
            n = create_glow_card(low, f"low frame embedded star_{i}", Vec3(-6 + i*0.75, 0.20+i*0.003, math.sin(i*0.8)*2.7), 0.10 + (i%4)*0.035, (0.70, 0.84, 1.0, 0.44), hpr=Vec3(0, 90, 0))
            n.setDepthTest(False)
            if i % 5 == 0:
                self.cosmic_twinklers.append(n)

        # A broad Milky-Way-like diagonal band made of overlapping soft discs and dark gaps.
        band_specs = [
            (-58, 50, 8, 20, 2.6, (0.20, 0.27, 0.45, 0.115), -22),
            (-42, 51, 12, 24, 3.3, (0.28, 0.34, 0.54, 0.125), -18),
            (-24, 53, 17, 28, 3.8, (0.44, 0.38, 0.54, 0.118), -12),
            (-4, 55, 20, 30, 4.2, (0.62, 0.45, 0.34, 0.105), -7),
            (18, 57, 18, 27, 3.6, (0.38, 0.44, 0.62, 0.110), 0),
            (40, 59, 12, 22, 2.8, (0.22, 0.32, 0.52, 0.105), 8),
            (60, 61, 6, 18, 2.2, (0.16, 0.22, 0.38, 0.095), 14),
        ]
        for idx, (x, y, z, rx, rz, col, roll) in enumerate(band_specs):
            create_soft_disc_y(pano, f"pass07 milky star cloud lobe_{idx}", Vec3(x, y, z), rx, rz, col, (col[0], col[1], col[2], 0.0), 72, hpr=Vec3(0, 0, roll))
            if idx % 2 == 1:
                create_soft_disc_y(pano, f"pass07 molecular dust bite_{idx}", Vec3(x + 2.6, y + 0.08, z - 1.0), rx * 0.55, rz * 0.20, (0.0, 0.0, 0.0, 0.20), (0.0, 0.0, 0.0, 0.0), 30, hpr=Vec3(0, 0, roll + 6))

        # A bigger face-on galaxy near the anomaly sightline with less geometric arc appearance.
        big = pano.attachNewNode("pass07 large photographic spiral galaxy")
        big.setPos(-34, 66, 27)
        big.setHpr(0, 0, -19)
        create_soft_disc_y(big, "pass07 spiral amber core glow", Vec3(0, 0, 0), 3.6, 1.7, (1.0, 0.76, 0.42, 0.34), (0.42, 0.22, 0.10, 0.0), 84)
        create_soft_disc_y(big, "pass07 spiral outer stellar halo", Vec3(0, -0.01, 0), 11.8, 5.1, (0.32, 0.48, 0.86, 0.095), (0.05, 0.08, 0.18, 0.0), 84)
        for arm in range(2):
            phase = arm * math.pi + 0.24
            for j in range(26):
                t = j / 37.0
                a = phase + t * math.pi * 2.32
                r = 1.1 + t * 10.2
                x = math.cos(a) * r
                z = math.sin(a) * r * 0.48
                puff = 0.36 + t * 0.44
                alpha = 0.080 * (1.0 - t * 0.30)
                create_soft_disc_y(big, "pass07 spiral cloudy arm", Vec3(x, 0.02 + j * 0.0008, z), puff, puff * 0.33, (0.30, 0.50, 0.92, alpha), (0.06, 0.10, 0.20, 0.0), 18, hpr=Vec3(0, 0, math.degrees(a) + 18))
                if j % 8 in (2, 5):
                    create_soft_disc_y(big, "pass07 rose star nursery knot", Vec3(x * 1.03, 0.06, z * 1.03), 0.22, 0.095, (1.0, 0.24, 0.34, 0.28), (1.0, 0.18, 0.20, 0.0), 14, hpr=Vec3(0, 0, math.degrees(a)))
                if j % 9 == 4:
                    create_soft_disc_y(big, "pass07 spiral dust groove", Vec3(x * 0.98, 0.08, z * 0.98), 0.58, 0.11, (0.0, 0.0, 0.0, 0.11), (0.0, 0.0, 0.0, 0.0), 14, hpr=Vec3(0, 0, math.degrees(a) - 12))

        # Distant galaxy cluster: tiny warm cores with faint blue halos, more natural than isolated dots.
        for i in range(12):
            a = i * 2.39996
            r = 2.5 + (i % 7) * 1.1
            x = 35 + math.cos(a) * r * 1.45
            z = 28 + math.sin(a) * r * 0.68
            y = 68 + (i % 4) * 0.07
            halo = create_soft_disc_y(pano, "pass07 faint galaxy cluster halo", Vec3(x, y, z), 0.82 + (i % 3) * 0.22, 0.30 + (i % 4) * 0.06, (0.26, 0.38, 0.74, 0.075), (0.04, 0.07, 0.14, 0.0), 18, hpr=Vec3(0, 0, (i * 31) % 180))
            core = create_soft_disc_y(pano, "pass07 faint galaxy cluster warm core", Vec3(x, y + 0.018, z), 0.24, 0.10, (1.0, 0.72, 0.38, 0.18), (0.24, 0.12, 0.04, 0.0), 12, hpr=Vec3(0, 0, (i * 31) % 180))
            if i % 5 == 0:
                self.cosmic_twinklers.append(core)

        # Foreground star clouds and a few bright colored stars for scale/depth.
        for i in range(18):
            u = seeded_unit(7000 + i * 37)
            v = seeded_unit(9000 + i * 53)
            w = seeded_unit(12000 + i * 71)
            x = -72 + u * 144
            y = 44 + v * 34
            z = -6 + w * 52
            size = 0.055 + seeded_unit(14000 + i * 19) * 0.16
            warm = seeded_unit(15000 + i * 23)
            if warm > 0.82:
                color = (1.0, 0.78, 0.48, 0.72)
            elif warm < 0.22:
                color = (0.56, 0.76, 1.0, 0.74)
            else:
                color = (0.78, 0.86, 1.0, 0.66)
            star = create_glow_card(pano, f"pass07 bright parallax star_{i}", Vec3(x, y, z), size, color, hpr=Vec3(0, 90, 0))
            if i % 9 == 0:
                self.cosmic_twinklers.append(star)

        # A subtle edge-on galaxy placed where the flight screenshot can actually see it.
        edge = pano.attachNewNode("pass07 visible edge-on galaxy")
        edge.setPos(16, 62, 34)
        edge.setHpr(0, 0, 6)
        create_soft_disc_y(edge, "pass07 edge-on disk glow", Vec3(0, 0, 0), 13.0, 0.95, (0.36, 0.50, 0.82, 0.15), (0.06, 0.09, 0.18, 0.0), 64)
        create_soft_disc_y(edge, "pass07 edge-on golden bulge", Vec3(0, 0.02, 0), 2.2, 0.72, (1.0, 0.66, 0.32, 0.26), (0.34, 0.14, 0.06, 0.0), 48)
        create_box(edge, "pass07 edge-on black dust split", Vec3(0, 0.055, 0), Vec3(19.0, 0.02, 0.11), (0.0, 0.0, 0.0, 0.34), hpr=Vec3(0, 0, 0), emission=(0, 0, 0, 1))

    # Anomaly / chunk-warp system
    # -----------------------------
    def seeded_value(self, seed: int) -> float:
        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
        return seed / 0x7FFFFFFF

    def build_anchor_station_and_anomaly(self) -> None:
        anchor = self.flight_root.attachNewNode("Station anchor around rare anomaly")
        self.anchor_scene_nodes.append(anchor)
        # The player station remains local until a distant solar system is folded in.
        create_cylinder_y(anchor, "station gravity spine", Vec3(0, 24.0, 6.0), 1.15, 9.0, 24, (0.045, 0.052, 0.078, 1), hpr=Vec3(0, 0, 90), emission=(0.005, 0.008, 0.018, 1))
        create_outline_box(anchor, "station anomaly observation gantry", Vec3(0, 24.0, 6.0), Vec3(10.8, 1.0, 3.2), (0.0, 0.60, 1.0, 0.46), thickness=2.0)
        for sx in (-1, 1):
            create_box(anchor, "station tether boom", Vec3(sx * 5.4, 24.0, 6.0), Vec3(0.20, 8.5, 0.20), (0.10, 0.12, 0.17, 1), hpr=Vec3(0, 0, sx * 12), emission=(0.008, 0.012, 0.026, 1))
            create_box(anchor, "anomaly range marker", Vec3(sx * 5.6, 28.1, 6.0), Vec3(0.24, 0.24, 0.24), (0.0, 0.72, 1.0, 1), emission=(0.0, 0.28, 0.78, 1))
            create_box(anchor, "station solar vane", Vec3(sx * 7.4, 23.4, 6.65), Vec3(2.9, 0.08, 1.0), (0.025, 0.08, 0.20, 1), emission=(0.0, 0.035, 0.10, 1))
        self.make_world_text(anchor, "ANOMALY ANCHOR // LOCAL STATION HOLDS POSITION", Vec3(0, 23.10, 8.65), 0.145, (0.0, 0.72, 1.0, 0.78), hpr=Vec3(0, 0, 0))

        self.anomaly_root = self.flight_root.attachNewNode("Rare black-hole anomaly")
        self.anchor_scene_nodes.append(self.anomaly_root)
        self.anomaly_root.setPos(0, 31.0, 7.0)
        # A small stylized black hole: dark core, accretion lanes, photon-ring glow, and offset lensing arcs.
        create_cylinder_y(self.anomaly_root, "event horizon core", Vec3(0, 0, 0), 1.05, 0.12, 48, (0.0, 0.0, 0.004, 1), hpr=Vec3(90, 0, 0), emission=(0.0, 0.0, 0.0, 1))
        create_cylinder_y(self.anomaly_root, "hot accretion disc", Vec3(0, 0.03, 0), 2.0, 0.055, 80, (1.0, 0.42, 0.06, 0.50), hpr=Vec3(90, 0, 0), emission=(0.55, 0.18, 0.02, 1))
        create_cylinder_y(self.anomaly_root, "blue photon ring", Vec3(0, 0.08, 0), 2.55, 0.045, 80, (0.0, 0.68, 1.0, 0.32), hpr=Vec3(90, 0, 0), emission=(0.0, 0.24, 0.75, 1))
        create_glow_card(self.anomaly_root, "bent light halo", Vec3(0, -0.04, 0), 4.0, (0.0, 0.42, 1.0, 0.12), hpr=Vec3(0, 90, 0))
        create_soft_disc_y(self.anomaly_root, "soft warped lens field halo", Vec3(0, -0.08, 0), 4.9, 3.15, (0.08, 0.32, 0.80, 0.035), (0.00, 0.00, 0.00, 0.0), 96, hpr=Vec3(0, 0, -6))
        create_soft_disc_y(self.anomaly_root, "deep natural lens shadow", Vec3(0, -0.075, 0), 3.6, 2.35, (0.0, 0.0, 0.0, 0.18), (0.0, 0.0, 0.0, 0.0), 96, hpr=Vec3(0, 0, 8))
        # Pass 05: layered Einstein-ring arcs and accretion bands, not only filled discs.
        arc_specs = [
            (0.95, 1.18, -20, 205, (1.0, 0.58, 0.12, 0.42), (0.55, 0.20, 0.03, 1), -8),
            (1.22, 1.42, 28, 318, (1.0, 0.18, 0.05, 0.28), (0.48, 0.04, 0.02, 1), 11),
            (1.84, 2.02, 192, 522, (0.0, 0.74, 1.0, 0.24), (0.0, 0.28, 0.70, 1), 0),
            (2.36, 2.50, -140, 160, (0.72, 0.88, 1.0, 0.16), (0.12, 0.22, 0.50, 1), 5),
            (3.05, 3.18, 34, 334, (0.22, 0.58, 1.0, 0.13), (0.04, 0.12, 0.35, 1), -4),
        ]
        for inner, outer, start, end, color, emit, roll in arc_specs:
            arc = create_annular_arc_y(self.anomaly_root, "layered gravitational lens arc", Vec3(0, 0.105, 0), inner, outer, start, end, 72, color, hpr=Vec3(0, 0, roll), emission=emit)
            self.anomaly_fx_nodes.append(arc)
        # Reassert the event horizon in front of the bright sheets so the black hole reads clearly.
        create_cylinder_y(self.anomaly_root, "front event-horizon silhouette", Vec3(0, 0.19, 0), 0.92, 0.045, 64, (0.0, 0.0, 0.002, 1), hpr=Vec3(90, 0, 0), emission=(0.0, 0.0, 0.0, 1))
        black_core = create_uv_sphere(self.anomaly_root, "pass08 spherical event horizon shadow", Vec3(0, 0.245, 0), 1.02, 24, 48, (0.0, 0.0, 0.0, 1), emission=(0.0, 0.0, 0.0, 1))
        black_core.setLightOff(1)
        create_annular_arc_y(self.anomaly_root, "thin white photon edge", Vec3(0, 0.205, 0), 0.96, 1.02, 0, 360, 96, (0.72, 0.88, 1.0, 0.22), hpr=Vec3(0, 0, 0), emission=(0.18, 0.26, 0.42, 1))
        create_soft_disc_y(self.anomaly_root, "pass08 smooth black event shadow", Vec3(0, 0.235, 0), 1.08, 1.08, (0.0, 0.0, 0.0, 0.96), (0.0, 0.0, 0.0, 0.0), 128)
        create_soft_disc_y(self.anomaly_root, "pass08 soft photon bloom against shadow", Vec3(0, 0.238, 0), 1.34, 1.24, (0.12, 0.34, 0.72, 0.080), (0.0, 0.0, 0.0, 0.0), 128)
        for i in range(18):
            # Replace hard line strands with layered luminous clumps that imply curved lens shear.
            a = i / 18 * math.tau
            for j in range(4):
                r = 3.45 + j * 0.42
                x = math.cos(a + j * 0.13) * r
                z = math.sin(a + j * 0.13) * r * 0.56
                y = 0.12 + j * 0.012
                col = (0.22, 0.64, 1.0, 0.070 - j * 0.010)
                filament = create_soft_disc_y(self.anomaly_root, "soft tidal light-shear plume", Vec3(x, y, z), 0.48 + j * 0.10, 0.055 + j * 0.010, col, (col[0], col[1], col[2], 0.0), 18, hpr=Vec3(0, 0, math.degrees(a) + j * 9))
                if j == 0 and i % 5 == 0:
                    self.anomaly_fx_nodes.append(filament)
        self.build_pass20_hyperspatial_disc(self.anomaly_root, 20017, radius_scale=1.0, warm_bias=(1.0, 0.54, 0.12), cool_bias=(0.20, 0.62, 1.0))
        self.build_pass08_natural_anomaly_skin()

    def clear_lensing_targets(self) -> None:
        for target in self.lens_targets:
            target.root.removeNode()
        self.lens_targets.clear()
        self.hover_target = None
        if self.lensing_root:
            self.lensing_root.removeNode()
            self.lensing_root = None

    def reseed_lensing_targets(self, seed: int) -> None:
        self.clear_lensing_targets()
        if not self.anomaly_root:
            return
        self.lensing_root = self.flight_root.attachNewNode("gravitational lens target images")
        # These are not normal markers; they are warped apparent images of far bodies around the black-hole lens.
        catalog = [
            ("Pale Lantern Ice Moon", "ice_moon", (0.45, 0.85, 1.0, 0.72)),
            ("Copper Ring Giant", "ring_giant", (1.0, 0.55, 0.20, 0.72)),
            ("Greenline Colony Wreck", "colony_wreck", (0.15, 1.0, 0.55, 0.72)),
            ("Violet Nebula Gate", "nebula_gate", (0.75, 0.30, 1.0, 0.72)),
            ("Iron Comet Shoal", "comet_shoal", (0.80, 0.88, 1.0, 0.72)),
            ("Red Dwarf Furnace", "red_dwarf", (1.0, 0.18, 0.08, 0.72)),
        ]
        offsets = [(-4.1, -0.1, 2.2), (-2.7, 0.0, -2.5), (0.4, -0.2, 3.35), (2.9, 0.1, -1.95), (4.25, 0.0, 1.25), (1.1, 0.2, -3.65)]
        for i, (name, kind, color) in enumerate(catalog):
            x, y, z = offsets[(i + seed) % len(offsets)]
            root = self.lensing_root.attachNewNode(f"lens target {name}")
            root.setPos(Vec3(x, 31.0 + y, 7.0 + z))
            root.setTag("target_kind", kind)
            target_seed = seed + i * 37
            self.build_pass08_lensing_target_body(root, kind, color, target_seed)
            self.lens_targets.append(LensTarget(name, kind, target_seed, color, root))

    def build_celestial_chunk(self, name: str, kind: str, seed: int) -> None:
        if self.celestial_chunk_root:
            self.celestial_chunk_root.removeNode()
        self.current_chunk_name = name
        self.current_chunk_kind = kind
        self.current_chunk_seed = seed
        self.prepare_system_reward(kind, seed)
        self.reset_gameplay_loop()
        root = self.flight_root.attachNewNode(f"active celestial chunk {name}")
        self.celestial_chunk_root = root

        palettes = {
            "ice_moon": ((0.50, 0.86, 1.0, 1), (0.02, 0.07, 0.13, 1), (0.20, 0.70, 1.0, 0.32)),
            "ring_giant": ((1.0, 0.52, 0.18, 1), (0.15, 0.08, 0.025, 1), (1.0, 0.60, 0.15, 0.28)),
            "colony_wreck": ((0.20, 1.0, 0.56, 1), (0.025, 0.12, 0.075, 1), (0.0, 0.75, 0.34, 0.28)),
            "nebula_gate": ((0.72, 0.28, 1.0, 1), (0.08, 0.025, 0.13, 1), (0.64, 0.20, 1.0, 0.26)),
            "comet_shoal": ((0.80, 0.90, 1.0, 1), (0.05, 0.07, 0.10, 1), (0.42, 0.78, 1.0, 0.26)),
            "red_dwarf": ((1.0, 0.18, 0.055, 1), (0.16, 0.035, 0.025, 1), (1.0, 0.20, 0.06, 0.30)),
            "station": ((0.0, 0.72, 1.0, 1), (0.025, 0.03, 0.045, 1), (0.0, 0.45, 1.0, 0.24)),
        }
        accent, dark, haze = palettes.get(kind, palettes["station"])
        # The clicked destination becomes a rendered far chunk. The station/black hole remain, but the sky and local salvage field change.
        self.setBackgroundColor(dark[0] * 0.18, dark[1] * 0.18, dark[2] * 0.22, 1)
        self.chunk_haze_nodes.clear()
        main_haze = create_glow_card(root, "chunk color haze", Vec3(0, 56, 15), 22.0, haze, hpr=Vec3(0, 90, 0))
        self.chunk_haze_nodes.append(main_haze)
        for i in range(5):
            drift = create_glow_card(root, f"layered destination gas veil_{i}", Vec3(-18 + i * 9.5, 48 + i * 3.8, 7 + math.sin(i) * 8), 8.0 + i * 1.6, (accent[0], accent[1], accent[2], 0.055 + i * 0.010), hpr=Vec3(0, 90, i * 11))
            self.chunk_haze_nodes.append(drift)
        if STARFALL_FAST_PROFILE:
            self.build_pass16_fast_destination_sky(root, kind, accent, seed)
        else:
            self.build_natural_chunk_sky(root, kind, accent, seed)
            self.build_destination_cinematic_layers(root, kind, accent, seed)
            self.build_pass08_destination_flythrough_depth(root, kind, accent, seed)
        self.build_pass09_random_solar_system(root, name, kind, seed, accent)
        return

        if kind == "ring_giant":
            body = create_cylinder_y(root, "active ring giant body", Vec3(17, 68, 3), 8.6, 0.30, 80, (0.48, 0.24, 0.08, 1), hpr=Vec3(90, 0, 0), emission=(0.08, 0.035, 0.012, 1))
            body.setScale(1.25, 1, 0.72)
            create_cylinder_y(root, "ring giant bright rings", Vec3(17, 68, 3), 12.8, 0.08, 96, (1.0, 0.58, 0.18, 0.18), hpr=Vec3(90, 0, -18), emission=(0.30, 0.12, 0.02, 1))
            create_annular_arc_y(root, "ring giant foreground ring gap", Vec3(17, 67.72, 3), 10.8, 13.7, 14, 172, 96, (1.0, 0.70, 0.30, 0.22), hpr=Vec3(0, 0, -18), emission=(0.26, 0.11, 0.025, 1))
            create_annular_arc_y(root, "ring giant rear dust ring", Vec3(17, 67.65, 3), 13.9, 15.2, 200, 522, 104, (0.90, 0.42, 0.16, 0.12), hpr=Vec3(0, 0, -18), emission=(0.18, 0.06, 0.012, 1))
        elif kind == "ice_moon":
            body = create_cylinder_y(root, "pale ice moon", Vec3(-17, 68, 7), 6.4, 0.26, 72, (0.40, 0.78, 0.96, 1), hpr=Vec3(90, 0, 0), emission=(0.04, 0.10, 0.16, 1))
            body.setScale(1.0, 1, 0.88)
            create_glow_card(root, "ice moon cold limb glow", Vec3(-17.4, 67.65, 7.25), 8.0, (0.36, 0.90, 1.0, 0.15), hpr=Vec3(0, 90, 0))
            for i in range(11):
                create_box(body, "ice fracture line", Vec3((i-5)*0.34, 0.18, math.sin(i)*1.18), Vec3(0.045, 0.055, 2.2), (0.0, 0.58, 1.0, 1), hpr=Vec3(0, 0, i*17), emission=(0.0, 0.18, 0.42, 1))
            for i in range(5):
                create_cylinder_y(root, "ice moon shard satellite", Vec3(-23 + i*2.4, 60 + i*1.8, 2 + math.sin(i)*3.4), 0.22 + i*0.035, 0.24, 12, (0.48, 0.82, 1.0, 1), hpr=Vec3(90+i*8, 0, i*17), emission=(0.04, 0.14, 0.24, 1))
        elif kind == "colony_wreck":
            create_outline_box(root, "distant shattered orbital colony", Vec3(-12, 62, 9), Vec3(12, 2.0, 5.5), (0.0, 0.85, 0.42, 0.45), thickness=2.2)
            create_outline_box(root, "colony rotating habitation ring ghost", Vec3(-12, 61.7, 9), Vec3(15.6, 0.4, 7.0), (0.0, 0.70, 0.38, 0.20), hpr=Vec3(0, 0, 11), thickness=1.4)
            for i in range(20):
                x = -17 + (i % 5) * 2.3
                z = 6 + (i // 5) * 1.15
                y = 59 + math.sin(i * 2.1) * 3.0
                create_box(root, "colony hull fragment", Vec3(x, y, z), Vec3(1.4, 0.16, 0.40), (0.08, 0.14, 0.12, 1), hpr=Vec3(i*13, 0, i*17), emission=(0.0, 0.035, 0.025, 1))
        elif kind == "nebula_gate":
            create_glow_card(root, "violet nebula wall", Vec3(0, 66, 7), 18.0, (0.50, 0.12, 1.0, 0.22), hpr=Vec3(0, 90, 0))
            create_outline_box(root, "ancient nebula gate", Vec3(0, 58, 7), Vec3(13, 0.4, 8), (0.72, 0.28, 1.0, 0.55), thickness=2.6)
            create_cylinder_y(root, "gate singular focus", Vec3(0, 58, 7), 1.0, 0.08, 48, (0.70, 0.20, 1.0, 0.46), hpr=Vec3(90, 0, 0), emission=(0.25, 0.06, 0.55, 1))
            create_annular_arc_y(root, "nebula gate rotating glyph outer", Vec3(0, 57.88, 7), 4.4, 4.7, 0, 280, 88, (0.95, 0.48, 1.0, 0.26), hpr=Vec3(0, 0, 0), emission=(0.30, 0.06, 0.55, 1))
            create_annular_arc_y(root, "nebula gate rotating glyph inner", Vec3(0, 57.84, 7), 2.1, 2.32, 72, 430, 88, (0.34, 0.72, 1.0, 0.20), hpr=Vec3(0, 0, 0), emission=(0.08, 0.18, 0.44, 1))
        elif kind == "comet_shoal":
            for i in range(16):
                x = -20 + (i % 8) * 5.8
                y = 54 + (i % 4) * 4.5
                z = 3 + math.sin(i * 1.7) * 5.0
                create_cylinder_y(root, "iron comet core", Vec3(x, y, z), 0.34 + (i % 3) * 0.12, 0.48, 16, (0.38, 0.42, 0.48, 1), hpr=Vec3(i*9, 0, i*11), emission=(0.025, 0.03, 0.04, 1))
                create_box(root, "comet ion tail", Vec3(x + 1.4, y + 1.0, z), Vec3(2.2, 0.08, 0.12), (0.38, 0.78, 1.0, 0.25), hpr=Vec3(i*9, 0, 0), emission=(0.08, 0.22, 0.45, 1))
                create_glow_card(root, "comet tail vapor glow", Vec3(x + 2.1, y + 1.35, z), 1.0 + (i % 4) * 0.18, (0.30, 0.70, 1.0, 0.08), hpr=Vec3(0, 90, 0))
        else:  # red_dwarf or default
            create_cylinder_y(root, "red dwarf star", Vec3(22, 74, 8), 5.8, 0.24, 80, (0.70, 0.09, 0.025, 1), hpr=Vec3(90, 0, 0), emission=(0.55, 0.08, 0.02, 1))
            create_glow_card(root, "red dwarf glare", Vec3(22, 73.8, 8), 10.5, (1.0, 0.12, 0.04, 0.20), hpr=Vec3(0, 90, 0))
            create_annular_arc_y(root, "red dwarf plasma crown", Vec3(22, 73.62, 8), 6.2, 6.7, -45, 255, 96, (1.0, 0.24, 0.06, 0.20), hpr=Vec3(0, 0, 0), emission=(0.44, 0.06, 0.015, 1))
            for i in range(10):
                create_box(root, "furnace salvage shard", Vec3(-12 + i*2.6, 50 + i*1.4, 1.5 + math.sin(i)*3.0), Vec3(1.5, 0.20, 0.34), (0.18, 0.10, 0.08, 1), hpr=Vec3(i*17, 0, i*9), emission=(0.06, 0.018, 0.010, 1))

        # Shared local salvage anchors that prove the world chunk swapped around the player.
        for i in range(14):
            a = (i * 2.399 + seed * 0.001) % math.tau
            radius = 16 + (i % 6) * 2.5
            x = math.cos(a) * radius
            y = 24 + math.sin(a * 0.7) * 6 + i * 1.15
            z = 0.8 + math.sin(a) * 6.0
            frag = create_box(root, "active chunk salvage marker", Vec3(x, y, z), Vec3(0.72 + (i % 3)*0.22, 0.14, 0.22), (accent[0]*0.35, accent[1]*0.35, accent[2]*0.35, 1), hpr=Vec3(i*23, 0, i*11), emission=(accent[0]*0.05, accent[1]*0.05, accent[2]*0.07, 1))
            if i % 5 == 0:
                create_box(frag, "salvage locator blink", Vec3(0, 0, 0.18), Vec3(0.20, 0.05, 0.06), accent, emission=(accent[0]*0.20, accent[1]*0.20, accent[2]*0.35, 1))

    def build_natural_chunk_sky(self, root: NodePath, kind: str, accent: tuple[float, float, float, float], seed: int) -> None:
        """Adds natural-looking far galaxies/nebulae to the active warped chunk.

        Each destination keeps its gameplay identity, but the background now has photographic
        features: uneven dust, star clusters, soft galaxy cores, and darker lanes.
        """
        sky = root.attachNewNode(f"natural sky detail {kind}")
        base_shift = (seed % 31) * 0.37
        # Local star cluster that changes per chunk and gives the destination a unique sky.
        for i in range(30):
            a = i * 2.399 + base_shift
            r = 7.0 + (i % 9) * 1.3
            x = -28 + math.cos(a) * r + (i % 5) * 0.7
            y = 84 + (i % 7) * 0.36
            z = 20 + math.sin(a) * r * 0.62
            size = 0.055 + (i % 4) * 0.018
            color = (
                min(1.0, 0.58 + accent[0] * 0.34 + (i % 3)*0.04),
                min(1.0, 0.58 + accent[1] * 0.28),
                min(1.0, 0.68 + accent[2] * 0.26),
                0.20 if i % 6 == 0 else 0.12,
            )
            create_soft_disc_y(sky, "natural destination star", Vec3(x, y, z), size, size, color, (color[0], color[1], color[2], 0.0), 12)

        # A subtle background galaxy/dust form for each chunk type.
        if kind == "ring_giant":
            center = Vec3(-35, 90, 35)
            create_soft_disc_y(sky, "warm barred spiral background core", center, 5.8, 2.2, (1.0, 0.66, 0.32, 0.12), (0.35, 0.18, 0.08, 0.0), 64, hpr=Vec3(0, 0, -7))
            for i in range(18):
                a = i / 25 * math.pi * 1.75
                r = 2.0 + i * 0.42
                for phase in (0, math.pi):
                    x = center.x + math.cos(a + phase) * r
                    z = center.z + math.sin(a + phase) * r * 0.42
                    create_soft_disc_y(sky, "ring giant distant spiral arm", Vec3(x, center.y + i*0.01, z), 0.52, 0.18, (0.52, 0.62, 0.80, 0.040), (0.08, 0.10, 0.16, 0.0), 16, hpr=Vec3(0, 0, math.degrees(a)))
        elif kind == "nebula_gate":
            for i in range(18):
                a = i * 0.61
                x = -22 + math.cos(a) * (6 + i * 0.28)
                z = 18 + math.sin(a * 1.17) * (5 + i * 0.16)
                rx = 4.0 + (i % 6) * 0.55
                rz = 1.1 + (i % 5) * 0.30
                color = (0.42 + (i%3)*0.05, 0.16 + (i%4)*0.03, 0.72 + (i%2)*0.08, 0.040)
                create_soft_disc_y(sky, "violet natural nebula fold", Vec3(x, 86 + i*0.012, z), rx, rz, color, (color[0], color[1], color[2], 0.0), 28, hpr=Vec3(0, 0, -32 + i*5))
            for i in range(6):
                create_soft_disc_y(sky, "nebula gate dark rift dust", Vec3(-12 + i*4.0, 86.8, 19 + math.sin(i*1.4)*3.0), 3.6, 0.32, (0.0, 0.0, 0.0, 0.15), (0.0, 0.0, 0.0, 0.0), 18, hpr=Vec3(0, 0, -18+i*12))
        elif kind == "ice_moon":
            create_soft_disc_y(sky, "cold blue reflection nebula", Vec3(30, 92, 32), 20, 4.4, (0.26, 0.54, 0.86, 0.052), (0.06, 0.10, 0.16, 0.0), 64, hpr=Vec3(0, 0, 13))
            create_soft_disc_y(sky, "dark molecular cloud lane", Vec3(31, 92.1, 32.1), 18, 0.58, (0.0, 0.0, 0.0, 0.16), (0.0, 0.0, 0.0, 0.0), 32, hpr=Vec3(0, 0, 10))
        elif kind == "colony_wreck":
            create_soft_disc_y(sky, "green airglow dust shell", Vec3(24, 88, 26), 17, 3.2, (0.12, 0.64, 0.36, 0.046), (0.02, 0.08, 0.04, 0.0), 64, hpr=Vec3(0, 0, -19))
            create_soft_disc_y(sky, "far amber galaxy behind wreck", Vec3(40, 96, 42), 7.4, 2.0, (1.0, 0.70, 0.38, 0.09), (0.30, 0.18, 0.08, 0.0), 48, hpr=Vec3(0, 0, 18))
        elif kind == "comet_shoal":
            for i in range(20):
                create_soft_disc_y(sky, "comet shoal diffuse tail field", Vec3(-34 + i*3.2, 88 + i*0.04, 15 + math.sin(i*0.8)*5.0), 3.1, 0.42, (0.30, 0.58, 0.80, 0.044), (0.04, 0.08, 0.12, 0.0), 20, hpr=Vec3(0, 0, 22 + i*2))
        else:
            create_soft_disc_y(sky, "red dwarf dusty emission shell", Vec3(-30, 94, 32), 19, 4.0, (0.78, 0.18, 0.08, 0.055), (0.10, 0.02, 0.01, 0.0), 64, hpr=Vec3(0, 0, -9))
            create_soft_disc_y(sky, "red dwarf dark foreground lane", Vec3(-30, 94.1, 32), 17, 0.50, (0.0, 0.0, 0.0, 0.15), (0.0, 0.0, 0.0, 0.0), 32, hpr=Vec3(0, 0, -7))

    def build_destination_cinematic_layers(self, root: NodePath, kind: str, accent: tuple[float, float, float, float], seed: int) -> None:
        """Pass 08 destination beauty layers.

        The warped chunk should feel like the station is now inside a different astronomical
        neighborhood, not just tinted fog. These layers add extra natural depth while keeping
        the celestial bodies generated from lightweight geometry.
        """
        sky = root.attachNewNode(f"pass07 destination cinematic depth {kind}")
        jitter = (seed % 97) * 0.013

        # Wide diagonal stellar river: more visible than the faint background, but still soft.
        for i in range(9):
            x = -52 + i * 13.0 + math.sin(jitter + i) * 2.3
            y = 72 + i * 0.22
            z = 6 + math.sin(i * 0.78 + jitter) * 11.0 + i * 1.4
            rx = 9.0 + (i % 4) * 2.6
            rz = 1.1 + (i % 3) * 0.44
            alpha = 0.060 + (i % 3) * 0.012
            col = (
                min(1.0, 0.18 + accent[0] * 0.42 + (i % 2) * 0.04),
                min(1.0, 0.20 + accent[1] * 0.32),
                min(1.0, 0.34 + accent[2] * 0.40),
                alpha,
            )
            create_soft_disc_y(sky, "pass07 destination stellar river", Vec3(x, y, z), rx, rz, col, (col[0], col[1], col[2], 0.0), 46, hpr=Vec3(0, 0, -17 + i * 2))
            if i % 3 != 0:
                create_soft_disc_y(sky, "pass07 destination dark river split", Vec3(x + 2.4, y + 0.05, z + 0.3), rx * 0.70, 0.20, (0.0, 0.0, 0.0, 0.17), (0.0, 0.0, 0.0, 0.0), 22, hpr=Vec3(0, 0, -15 + i * 2))

        # Chunk-specific natural sky cue.
        if kind == "red_dwarf":
            create_soft_disc_y(sky, "pass07 red furnace emission nebula", Vec3(-20, 78, 28), 26, 5.2, (0.95, 0.18, 0.065, 0.105), (0.18, 0.03, 0.015, 0.0), 72, hpr=Vec3(0, 0, 8))
            for i in range(5):
                create_soft_disc_y(sky, "pass07 red dwarf smoke lane", Vec3(-30 + i*8.0, 78.1, 27 + math.sin(i)*2.2), 7.0, 0.42, (0.0, 0.0, 0.0, 0.19), (0.0, 0.0, 0.0, 0.0), 24, hpr=Vec3(0, 0, 9+i*3))
        elif kind == "ice_moon":
            create_soft_disc_y(sky, "pass07 icy blue molecular cloud", Vec3(-15, 79, 31), 26, 5.5, (0.22, 0.50, 0.78, 0.095), (0.03, 0.06, 0.12, 0.0), 72, hpr=Vec3(0, 0, -11))
            create_soft_disc_y(sky, "pass07 cold dust absorption lane", Vec3(-13, 79.1, 31), 21, 0.55, (0.0, 0.0, 0.0, 0.19), (0.0, 0.0, 0.0, 0.0), 32, hpr=Vec3(0, 0, -7))
        elif kind == "ring_giant":
            create_soft_disc_y(sky, "pass07 golden zodiacal dust", Vec3(3, 77, 25), 30, 4.1, (1.0, 0.55, 0.18, 0.085), (0.20, 0.10, 0.03, 0.0), 72, hpr=Vec3(0, 0, 4))
            create_soft_disc_y(sky, "pass07 ring giant dark belt shadow", Vec3(5, 77.1, 25), 26, 0.38, (0.0, 0.0, 0.0, 0.18), (0.0, 0.0, 0.0, 0.0), 28, hpr=Vec3(0, 0, 5))
        elif kind == "nebula_gate":
            for i in range(16):
                a = i * 0.74 + jitter
                create_soft_disc_y(sky, "pass07 layered violet nebula petal", Vec3(-10 + math.cos(a)*17, 77 + i*0.025, 23 + math.sin(a)*8), 7.0 + (i%4), 1.4 + (i%3)*0.3, (0.45, 0.15 + (i%3)*0.04, 0.85, 0.066), (0.06, 0.02, 0.12, 0.0), 28, hpr=Vec3(0, 0, math.degrees(a)*0.3))
        elif kind == "colony_wreck":
            create_soft_disc_y(sky, "pass07 green ionized wreck glow", Vec3(-2, 75, 25), 28, 3.7, (0.08, 0.62, 0.36, 0.078), (0.01, 0.06, 0.03, 0.0), 72, hpr=Vec3(0, 0, -5))
            for i in range(14):
                create_glow_card(sky, "pass07 faint emergency beacon star", Vec3(-40+i*6.5, 74+i*0.04, 18+math.sin(i)*8), 0.10+(i%4)*0.035, (0.0, 1.0, 0.55, 0.23), hpr=Vec3(0, 90, 0))
        elif kind == "comet_shoal":
            for i in range(18):
                create_soft_disc_y(sky, "pass07 long comet ion stream background", Vec3(-42+i*4.8, 76+i*0.03, 14+math.sin(i*0.62)*8), 5.2, 0.36, (0.28, 0.62, 1.0, 0.065), (0.02, 0.05, 0.10, 0.0), 20, hpr=Vec3(0, 0, 20+i*1.5))

        # Extra visible point population for all chunks.
        for i in range(46):
            u = seeded_unit(seed + 2100 + i * 73)
            v = seeded_unit(seed + 4100 + i * 41)
            w = seeded_unit(seed + 6100 + i * 19)
            x = -55 + u * 110
            y = 61 + v * 30
            z = -1 + w * 46
            size = 0.055 + seeded_unit(seed + 8100 + i * 7) * 0.10
            color = (min(1.0, 0.58 + accent[0]*0.34), min(1.0, 0.62 + accent[1]*0.28), min(1.0, 0.72 + accent[2]*0.24), 0.38)
            star = create_glow_card(sky, "pass07 destination crisp star", Vec3(x, y, z), size, color, hpr=Vec3(0, 90, 0))
            if i % 13 == 0:
                self.cosmic_twinklers.append(star)


    def make_pass08_micro_galaxy(self, parent: NodePath, name: str, pos: Vec3, scale: float, accent: tuple[float, float, float, float], seed: int, arms: int = 2, thickness: float = 1.0, register_motion: bool = True) -> NodePath:
        """Create a soft 3D-wrapped tiny galaxy you can fly through.

        The galaxy is built from many alpha-falloff discs, star knots, and dark dust lanes placed
        through depth rather than a single flat card.  It remains lightweight, but reads more like a
        volume suspended in space.
        """
        root = parent.attachNewNode(name)
        root.setPos(pos)
        root.setHpr((seed * 23) % 360, -18 + (seed % 37) * 0.55, -9 + (seed % 29) * 0.62)
        root.setScale(scale)
        root.setTransparency(TransparencyAttrib.M_alpha)
        root.setDepthWrite(False)
        if register_motion:
            self.organic_cosmic_roots.append(root)

        warm = (min(1.0, 0.82 + accent[0] * 0.18), min(1.0, 0.58 + accent[1] * 0.22), min(1.0, 0.30 + accent[2] * 0.18), 0.23)
        cool = (min(1.0, 0.18 + accent[0] * 0.18), min(1.0, 0.34 + accent[1] * 0.26), min(1.0, 0.70 + accent[2] * 0.28), 0.12)
        create_soft_disc_y(root, "organic galaxy warm core", Vec3(0, 0, 0), 0.88, 0.44, warm, (warm[0], warm[1] * 0.6, warm[2] * 0.35, 0.0), 48)
        create_soft_disc_y(root, "organic galaxy blue halo", Vec3(0, -0.03, 0), 2.8, 1.18, cool, (0.02, 0.04, 0.09, 0.0), 72, hpr=Vec3(0, 0, 3))
        create_soft_disc_y(root, "organic galaxy vertical star fog", Vec3(0, 0.04, 0), 1.45, 2.05 * thickness, (cool[0], cool[1], cool[2], 0.050), (0.0, 0.0, 0.0, 0.0), 56, hpr=Vec3(0, 0, 92))
        create_soft_disc_y(root, "organic dark dust waist", Vec3(0.08, 0.065, 0.02), 2.85, 0.115, (0.0, 0.0, 0.0, 0.28), (0.0, 0.0, 0.0, 0.0), 34, hpr=Vec3(0, 0, -5 + (seed % 11)))

        knots = 58 if scale < 7 else 74
        for i in range(knots):
            u = seeded_unit(seed + i * 97)
            v = seeded_unit(seed + i * 131)
            arm = i % max(1, arms)
            turns = 1.15 + seeded_unit(seed + 90 + arm * 31) * 0.55
            a = u * math.tau * turns + arm * (math.tau / max(1, arms))
            r = 0.30 + (u ** 0.75) * 2.85
            # Width around the arm gives it a natural uneven lane instead of perfect mathematics.
            lane = (v - 0.5) * (0.17 + r * 0.035)
            x = math.cos(a) * r - math.sin(a) * lane
            z = math.sin(a) * r * 0.48 + math.cos(a) * lane * 0.55
            y = (seeded_unit(seed + i * 43) - 0.5) * (0.42 + thickness * 0.22)
            alpha = 0.075 + seeded_unit(seed + i * 17) * 0.085
            if i % 9 == 0:
                col = (1.0, 0.28 + seeded_unit(seed + i) * 0.20, 0.36, alpha + 0.10)
                rx, rz = 0.15, 0.055
            elif i % 5 == 0:
                col = (0.95, 0.68, 0.36, alpha + 0.065)
                rx, rz = 0.12, 0.045
            else:
                col = (cool[0] + seeded_unit(seed + i * 3) * 0.12, cool[1] + 0.08, min(1.0, cool[2] + 0.18), alpha)
                rx, rz = 0.18 + seeded_unit(seed + i * 19) * 0.18, 0.040 + seeded_unit(seed + i * 23) * 0.055
            node = create_soft_disc_y(root, "organic spiral star cloud knot", Vec3(x, y, z), rx, rz, col, (col[0], col[1], col[2], 0.0), 14, hpr=Vec3(0, 0, math.degrees(a) + seeded_unit(seed + i * 11) * 18.0))
            if i % 17 == 0:
                self.cosmic_twinklers.append(node)
            if i % 13 == 4:
                create_soft_disc_y(root, "organic spiral dust filament", Vec3(x * 0.98, y + 0.025, z * 0.98), 0.36 + r * 0.06, 0.045, (0.0, 0.0, 0.0, 0.18), (0.0, 0.0, 0.0, 0.0), 12, hpr=Vec3(0, 0, math.degrees(a) - 10))
        return root

    def build_pass08_flythrough_galaxy_field(self, parent: NodePath, seed: int) -> None:
        """Add tiny random galaxies as spatial objects, not a flat skybox."""
        field = parent.attachNewNode("pass08 fly-through natural micro-galaxies")
        accents = [
            (0.50, 0.68, 1.0, 1), (1.0, 0.62, 0.30, 1), (0.42, 0.95, 0.72, 1),
            (0.82, 0.45, 1.0, 1), (0.92, 0.88, 1.0, 1), (1.0, 0.30, 0.18, 1),
        ]
        base_positions = [
            Vec3(-38, 33, 17), Vec3(33, 41, 23), Vec3(-15, 55, 34), Vec3(47, 62, 12),
            Vec3(-56, 71, 29), Vec3(18, 49, -1), Vec3(3, 76, 44), Vec3(-28, 25, 6),
        ]
        for i, pos in enumerate(base_positions):
            jitter = Vec3((seeded_unit(seed+i*7)-0.5)*7.0, (seeded_unit(seed+i*11)-0.5)*5.0, (seeded_unit(seed+i*13)-0.5)*4.0)
            self.make_pass08_micro_galaxy(field, f"pass08 fly-through galaxy {i}", pos + jitter, 1.6 + (i % 4) * 0.55, accents[i % len(accents)], seed + i * 313, arms=2 + (i % 2), thickness=0.8 + (i % 3)*0.24)
        # A nearer diffuse star stream the ship can literally pass through.
        for i in range(30):
            u = seeded_unit(seed + 2000 + i * 31)
            v = seeded_unit(seed + 4000 + i * 17)
            w = seeded_unit(seed + 6000 + i * 29)
            x = -42 + u * 84
            y = 20 + v * 70
            z = -4 + w * 34
            col = (0.52 + w * 0.28, 0.62 + v * 0.20, 0.82 + u * 0.16, 0.32)
            star = create_glow_card(field, "pass08 fly-through loose extragalactic star", Vec3(x, y, z), 0.045 + u * 0.07, col, hpr=Vec3(0, 90, 0))
            if i % 10 == 0:
                self.cosmic_twinklers.append(star)

    def build_pass08_natural_anomaly_skin(self) -> None:
        """Wrap the black hole in smooth dust/light volumes and remove the designed-frame feel."""
        if not self.anomaly_root:
            return
        skin = self.anomaly_root.attachNewNode("pass08 organic black-hole skin")
        organic_layers = [
            (3.6, 1.18, 0.110, (1.0, 0.44, 0.08, 0.18), -7),
            (4.25, 1.42, 0.095, (0.88, 0.30, 0.06, 0.12), 9),
            (5.20, 2.10, 0.072, (0.14, 0.45, 1.0, 0.10), -18),
            (6.30, 2.80, 0.052, (0.36, 0.62, 1.0, 0.070), 24),
        ]
        for idx, (rx, rz, y, color, rot) in enumerate(organic_layers):
            layer = create_soft_disc_y(skin, "pass08 flowing accretion haze layer", Vec3(0, y, 0), rx, rz, color, (color[0], color[1], color[2], 0.0), 128, hpr=Vec3(0, 0, rot))
            self.anomaly_fx_nodes.append(layer)
        # Soft dust clumps orbiting around the hole, placed in depth so the ring is not a flat design shape.
        for i in range(18):
            u = seeded_unit(9300 + i * 17)
            a = u * math.tau * 1.35 + (i % 5) * 0.11
            r = 2.0 + seeded_unit(9900 + i * 23) * 3.2
            x = math.cos(a) * r
            z = math.sin(a) * r * (0.38 + seeded_unit(9700 + i * 5) * 0.26)
            y = 0.05 + (seeded_unit(9500 + i * 13)-0.5) * 0.42
            warm = seeded_unit(9100 + i * 19)
            col = (1.0, 0.42 + warm * 0.22, 0.08 + warm * 0.05, 0.055 + warm * 0.050)
            if i % 7 == 0:
                col = (0.22, 0.55, 1.0, 0.055)
            mote = create_soft_disc_y(skin, "pass08 orbital dust mote", Vec3(x, y, z), 0.18 + u * 0.18, 0.038 + u * 0.035, col, (col[0], col[1], col[2], 0.0), 12, hpr=Vec3(0, 0, math.degrees(a)))
            if i % 12 == 0:
                self.anomaly_fx_nodes.append(mote)
        # Tiny background galaxies behind the lens, distorted by the same local warp field.
        for i, pos in enumerate([Vec3(-6.7, -0.25, 4.1), Vec3(6.1, -0.18, -3.0), Vec3(-4.8, -0.22, -4.6)]):
            self.make_pass08_micro_galaxy(skin, f"pass08 galaxy caught behind lens {i}", pos, 0.55 + i*0.12, (0.72, 0.82, 1.0, 1), 10100 + i*211, arms=2, thickness=0.6, register_motion=False)

    def build_pass20_hyperspatial_disc(self, root: NodePath, seed: int, radius_scale: float = 1.0, warm_bias: tuple[float, float, float] = (1.0, 0.54, 0.12), cool_bias: tuple[float, float, float] = (0.26, 0.68, 1.0)) -> None:
        """Add a softer, more 4D-looking folded accretion structure with rounded cross-sections.

        The goal is not a flat disc but a small hyperspatial knot made of interpenetrating
        translucent rings, rounded lens sheets, and offset orbiting motes.
        """
        hyper = root.attachNewNode("pass20 hyperspatial fold shell")
        hyper.setTransparency(TransparencyAttrib.M_alpha)
        base_roll = seed % 360
        fold_specs = [
            (Vec3(0, 18, -18 + base_roll * 0.02), 4.05, 1.88, 0.085, (cool_bias[0], cool_bias[1], cool_bias[2], 0.14)),
            (Vec3(24, -34, 48 + base_roll * 0.03), 3.45, 1.22, 0.060, (warm_bias[0], warm_bias[1], warm_bias[2], 0.14)),
            (Vec3(-32, 26, 92 + base_roll * 0.02), 3.10, 1.32, 0.045, (0.62, 0.40, 1.0, 0.11)),
            (Vec3(58, 42, 10 + base_roll * 0.04), 3.00, 1.08, 0.026, (0.88, 0.94, 1.0, 0.09)),
        ]
        for idx, (hpr, rx, rz, yoff, col) in enumerate(fold_specs):
            fold = hyper.attachNewNode(f"pass20 hyperfold_{idx}")
            fold.setHpr(hpr)
            disc = create_soft_disc_y(fold, "pass20 folded lens sheet", Vec3(0, yoff, 0), rx * radius_scale, rz * radius_scale, col, (col[0], col[1], col[2], 0.0), 120, hpr=Vec3(0, 0, 0))
            rim = create_annular_arc_y(fold, "pass20 folded rim arc", Vec3(0, yoff + 0.012, 0), rx * 0.72 * radius_scale, rx * 0.80 * radius_scale, -32, 322, 72, (col[0], col[1], col[2], col[3] * 1.25), emission=(col[0] * 0.18, col[1] * 0.18, col[2] * 0.22, 1))
            inner = create_soft_disc_y(fold, "pass20 internal fold shadow", Vec3(0, yoff + 0.010, 0), rx * 0.44 * radius_scale, rz * 0.70 * radius_scale, (0.0, 0.0, 0.0, 0.12), (0.0, 0.0, 0.0, 0.0), 84, hpr=Vec3(0, 0, -8 + idx * 11))
            for node in (disc, rim, inner):
                node.setTag("anomaly_anim", "hyper")
                self.anomaly_hyper_nodes.append(node)
                self.anomaly_fx_nodes.append(node)
        # A few offset Einstein hoops in different planes to imply a 4D slice rather than one disc.
        ring_specs = [
            (Vec3(0, 24, 16), 1.42, 1.58, (0.94, 0.98, 1.0, 0.22)),
            (Vec3(44, -34, -26), 1.72, 1.88, (0.22, 0.64, 1.0, 0.20)),
            (Vec3(-38, 36, 58), 1.96, 2.14, (1.0, 0.52, 0.16, 0.20)),
        ]
        for idx, (hpr, inner_r, outer_r, col) in enumerate(ring_specs):
            ring_root = hyper.attachNewNode(f"pass20 impossible_ring_{idx}")
            ring_root.setHpr(hpr)
            ring = create_annular_arc_y(ring_root, "pass20 impossible lens hoop", Vec3(0, 0.18 + idx * 0.022, 0), inner_r * radius_scale, outer_r * radius_scale, 0, 360, 96, col, emission=(col[0] * 0.20, col[1] * 0.20, col[2] * 0.24, 1))
            ring.setTag("anomaly_anim", "hyper")
            self.anomaly_hyper_nodes.append(ring)
            self.anomaly_fx_nodes.append(ring)
        # Orbiting rounded motes on lopsided loops so the structure feels volumetric and wrapped.
        orbit_root = hyper.attachNewNode("pass20 hyper-orbit motes")
        for i in range(12):
            u = seeded_unit(seed + 1200 + i * 17)
            v = seeded_unit(seed + 2200 + i * 29)
            a = u * math.tau
            b = v * math.tau
            r = (2.15 + u * 2.20) * radius_scale
            x = math.cos(a) * r
            y = (math.sin(a * 1.7 + b) * 0.28 + (u - 0.5) * 0.10) * radius_scale
            z = math.sin(a) * r * (0.40 + v * 0.34)
            col = (0.40 + u * 0.30, 0.58 + v * 0.24, 1.0 if i % 3 else 0.86, 0.055 + u * 0.05)
            if i % 4 == 0:
                col = (1.0, 0.50 + u * 0.18, 0.18 + v * 0.08, 0.070)
            mote = create_soft_disc_y(orbit_root, "pass20 hyper-orbit mote", Vec3(x, y, z), (0.20 + u * 0.16) * radius_scale, (0.050 + v * 0.035) * radius_scale, col, (col[0], col[1], col[2], 0.0), 16, hpr=Vec3(0, 0, math.degrees(a) + i * 11))
            mote.setTag("anomaly_anim", "orbit")
            mote.setTag("orbit_index", str(i))
            self.anomaly_orbit_nodes.append(mote)
            if i % 3 == 0:
                self.anomaly_fx_nodes.append(mote)
        # A faint rounded cross-core bloom to make the central slice read as multi-directional, not planar.
        for idx, ang in enumerate((-26, 24, 82)):
            bloom_root = hyper.attachNewNode(f"pass20 core bloom_{idx}")
            bloom_root.setHpr(ang, 22 if idx != 1 else -26, ang * 0.8)
            bloom = create_soft_disc_y(bloom_root, "pass20 core hyperspatial bloom", Vec3(0, 0.16 + idx * 0.01, 0), 1.38 * radius_scale, 0.46 * radius_scale, (0.70, 0.88, 1.0, 0.08), (0.0, 0.0, 0.0, 0.0), 64)
            bloom.setTag("anomaly_anim", "hyper")
            self.anomaly_hyper_nodes.append(bloom)
            self.anomaly_fx_nodes.append(bloom)

    def build_pass08_lensing_target_body(self, root: NodePath, kind: str, color: tuple[float, float, float, float], seed: int) -> None:
        """Organic apparent body used for black-hole target selection."""
        body = root.attachNewNode("pass08 organic lensing body")
        body.setDepthWrite(False)
        # The apparent body is a wrapped volume: a small galaxy/moon/gas cloud plus natural lens smears.
        if kind in {"nebula_gate", "colony_wreck"}:
            self.make_pass08_micro_galaxy(body, "tiny warped apparent galaxy body", Vec3(0, 0.005, 0), 0.26, color, seed + 33, arms=2 + (seed % 2), thickness=0.65, register_motion=False)
        else:
            create_soft_disc_y(body, "soft apparent planet body", Vec3(0, 0.010, 0), 0.28, 0.24, (color[0], color[1], color[2], 0.30), (color[0], color[1], color[2], 0.0), 42)
            create_soft_disc_y(body, "curved body terminator", Vec3(-0.055, 0.018, -0.01), 0.20, 0.23, (0.0, 0.0, 0.0, 0.18), (0.0, 0.0, 0.0, 0.0), 34, hpr=Vec3(0, 0, -12 + (seed % 25)))
            create_soft_disc_y(body, "apparent body atmosphere", Vec3(0, 0.000, 0), 0.46, 0.38, (color[0], color[1], color[2], 0.080), (color[0], color[1], color[2], 0.0), 54)
        for i in range(5):
            offset = (i - 2) * 0.045
            start = -34 + i * 13 + (seed % 19)
            end = 205 + i * 17
            arc = create_annular_arc_y(body, "organic apparent lens smear arc", Vec3(0, 0.030 + i*0.004, offset), 0.42 + i*0.055, 0.48 + i*0.060, start, end, 46, (color[0], color[1], color[2], 0.18 - i*0.018), hpr=Vec3(0, 0, -14 + i*6), emission=(color[0]*0.15, color[1]*0.15, color[2]*0.24, 1))
            self.anomaly_fx_nodes.append(arc)
        for i in range(9):
            u = seeded_unit(seed + i*29)
            a = u * math.tau
            r = 0.42 + seeded_unit(seed + i*31) * 0.38
            create_soft_disc_y(body, "tiny satellites in lens smear", Vec3(math.cos(a)*r, 0.035 + u*0.015, math.sin(a)*r*0.55), 0.045 + u*0.035, 0.020 + u*0.012, (color[0], color[1], color[2], 0.16), (color[0], color[1], color[2], 0.0), 10, hpr=Vec3(0,0,math.degrees(a)))

    def build_pass08_destination_flythrough_depth(self, root: NodePath, kind: str, accent: tuple[float, float, float, float], seed: int) -> None:
        """Add small passable 3D cosmic formations around the warped destination."""
        layer = root.attachNewNode(f"pass08 destination fly-through cosmic formations {kind}")
        offsets = [Vec3(-24, 32, 17), Vec3(26, 38, 26), Vec3(4, 46, 8), Vec3(-42, 54, 31)]
        for i, pos in enumerate(offsets):
            p = pos + Vec3((seeded_unit(seed+i*5)-0.5)*8, (seeded_unit(seed+i*7)-0.5)*6, (seeded_unit(seed+i*11)-0.5)*5)
            local_accent = (
                min(1.0, accent[0] * (0.75 + seeded_unit(seed+i)*0.35) + 0.12),
                min(1.0, accent[1] * (0.70 + seeded_unit(seed+i*2)*0.40) + 0.16),
                min(1.0, accent[2] * (0.75 + seeded_unit(seed+i*3)*0.30) + 0.18),
                1,
            )
            self.make_pass08_micro_galaxy(layer, f"pass08 destination micro galaxy {kind} {i}", p, 1.0 + (i % 3)*0.42, local_accent, seed + 700 + i*173, arms=2 + (i % 2), thickness=0.7 + i*0.08)
        for i in range(18):
            u = seeded_unit(seed + 10000 + i * 19)
            v = seeded_unit(seed + 12000 + i * 23)
            w = seeded_unit(seed + 14000 + i * 31)
            x = -48 + u * 96
            y = 26 + v * 48
            z = -5 + w * 42
            col = (min(1.0, accent[0]*0.45 + 0.38 + u*0.12), min(1.0, accent[1]*0.38 + 0.44 + v*0.10), min(1.0, accent[2]*0.44 + 0.52 + w*0.14), 0.23)
            star = create_glow_card(layer, "pass08 destination fly-through cluster star", Vec3(x,y,z), 0.040 + u*0.055, col, hpr=Vec3(0,90,0))
            if i % 14 == 0:
                self.cosmic_twinklers.append(star)

    def make_pass09_system_name(self, kind: str, seed: int) -> str:
        prefixes = ["Kepler", "Vela", "Aster", "Hale", "Nadir", "Ophir", "Nyx", "Lacaille", "Tarn", "Mira"]
        suffixes = ["Reach", "Shoal", "Fold", "Basin", "Halo", "Drift", "Current", "Sanctum", "Ridge", "Wellspring"]
        p = prefixes[int(seeded_unit(seed + 11) * len(prefixes)) % len(prefixes)]
        q = suffixes[int(seeded_unit(seed + 29) * len(suffixes)) % len(suffixes)]
        code = 100 + int(seeded_unit(seed + 41) * 899)
        theme = {
            "ice_moon": "Cold",
            "ring_giant": "Ringed",
            "colony_wreck": "Ruined",
            "nebula_gate": "Violet",
            "comet_shoal": "Cometary",
            "red_dwarf": "Red-Dwarf",
        }.get(kind, "Uncharted")
        return f"{theme} System {p}-{code} {q}"

    def build_pass09_random_solar_system(self, root: NodePath, name: str, kind: str, seed: int, accent: tuple[float, float, float, float]) -> None:
        """Create a vast explorable solar-system chunk around the ship.

        Pass 11 keeps the procedural-system warp loop, but increases the scale
        separation.  Major bodies are pushed into much farther bands, while one
        nearby hero planet gets extra local orbit detail and soft realistic POIs.
        """
        self.clear_lensing_targets()
        system = root.attachNewNode(f"pass11 vast procedural solar system {name}")
        system.setTransparency(TransparencyAttrib.M_alpha)
        system.setDepthWrite(False)

        star_catalog = [
            ("cool red dwarf", (1.0, 0.20, 0.075, 1), (0.72, 0.08, 0.025, 1), 5.2, 0.62),
            ("orange main-sequence star", (1.0, 0.58, 0.25, 1), (0.82, 0.30, 0.08, 1), 6.4, 0.82),
            ("sunlike yellow-white star", (1.0, 0.86, 0.54, 1), (0.90, 0.55, 0.20, 1), 7.1, 1.0),
            ("blue-white young star", (0.62, 0.78, 1.0, 1), (0.22, 0.42, 0.90, 1), 7.8, 1.22),
            ("small white dwarf", (0.78, 0.90, 1.0, 1), (0.34, 0.56, 1.0, 1), 4.5, 1.38),
            ("dusty protostar", (1.0, 0.42, 0.16, 1), (0.85, 0.22, 0.06, 1), 6.9, 0.74),
        ]
        st_index = int(seeded_unit(seed + 311) * len(star_catalog)) % len(star_catalog)
        star_name, star_color, star_emission, star_radius, light_bias = star_catalog[st_index]
        if kind == "red_dwarf":
            star_name, star_color, star_emission, star_radius, light_bias = star_catalog[0]
        elif kind == "ice_moon":
            star_name, star_color, star_emission, star_radius, light_bias = star_catalog[4]
        elif kind == "ring_giant":
            star_radius += 1.4

        # Push the primary star far forward. It still anchors the system visually,
        # but planets now occupy vastly separated depth bands instead of a tight cluster.
        star_pos = Vec3(0, 360.0, 26.0)
        star = create_uv_sphere(system, f"pass11 very distant {star_name} primary", star_pos, star_radius, 24, 56, star_color, emission=star_emission)
        star.setLightOff(1)
        self.organic_cosmic_roots.append(star)
        for i, mul in enumerate([1.55, 2.35, 3.35, 4.65, 6.2]):
            alpha = max(0.018, 0.145 / (i + 1))
            create_soft_disc_y(system, "pass11 distant stellar glare shell", star_pos + Vec3(0, -0.12 - i * 0.055, 0), star_radius * mul, star_radius * mul * (0.84 + i * 0.04), (star_color[0], star_color[1], star_color[2], alpha), (star_color[0], star_color[1], star_color[2], 0.0), 112, hpr=Vec3(0, 0, (seed + i * 17) % 360))

        # Broad, low-alpha dust planes imply interplanetary scale without drawing hard orbit lines.
        create_soft_disc_y(system, "pass11 immense zodiacal dust sheet", Vec3(0, 210, 18.0), 230, 18.0, (star_color[0], star_color[1]*0.72, star_color[2]*0.55, 0.030), (star_color[0], star_color[1]*0.48, star_color[2]*0.32, 0.0), 112, hpr=Vec3(0, 0, -7 + (seed % 19)))
        for lane in range(7):
            create_soft_disc_y(system, "pass11 far dark interplanetary dust lane", Vec3(-130 + lane * 43.0, 205 + lane * 1.6, 15.0 + math.sin(lane) * 7.5), 39, 0.52, (0.0, 0.0, 0.0, 0.085), (0.0, 0.0, 0.0, 0.0), 34, hpr=Vec3(0, 0, -10 + lane * 3))

        body_accents = [
            (0.36, 0.68, 0.95, 1), (0.72, 0.52, 0.36, 1), (0.42, 0.72, 0.46, 1),
            (0.92, 0.62, 0.28, 1), (0.78, 0.78, 0.84, 1), (0.56, 0.42, 0.82, 1),
            (0.95, 0.36, 0.24, 1),
        ]
        if kind == "ice_moon":
            hero_color = (0.50, 0.84, 1.0, 1)
            hero_kind = "ice"
        elif kind == "red_dwarf":
            hero_color = (0.80, 0.34, 0.20, 1)
            hero_kind = "furnace"
        elif kind == "ring_giant":
            hero_color = (0.82, 0.62, 0.38, 1)
            hero_kind = "ringed"
        elif kind == "nebula_gate":
            hero_color = (0.58, 0.48, 0.92, 1)
            hero_kind = "nebula"
        elif kind == "colony_wreck":
            hero_color = (0.42, 0.70, 0.55, 1)
            hero_kind = "terrestrial"
        else:
            hero_color = (0.62, 0.76, 0.86, 1)
            hero_kind = "cold-rock"

        # Guaranteed nearby detailed planet.  It becomes the immediate exploration landmark,
        # while everything else lives at much larger distances.
        hero_pos = Vec3(-18.0 + (seeded_unit(seed + 1202) - 0.5) * 5.0, 50.0, 8.6 + (seeded_unit(seed + 1203) - 0.5) * 3.0)
        hero_radius = 6.8 + seeded_unit(seed + 1204) * 2.15
        hero_ringed = hero_kind in {"ringed", "nebula"} or seeded_unit(seed + 1205) > 0.70
        hero_gas = hero_kind == "ringed" or seeded_unit(seed + 1206) > 0.68
        self.make_pass09_planet(system, "pass11 nearby detailed hero planet", hero_pos, hero_radius, hero_color, seed + 12000, ringed=hero_ringed, gas_giant=hero_gas, star_bias=light_bias)
        self.add_pass10_hero_planet_detail(system, hero_pos, hero_radius, hero_color, seed + 12100, hero_kind, ringed=hero_ringed)
        self.add_pass11_near_planet_orbital_environment(system, hero_pos, hero_radius, hero_color, seed + 12450, hero_kind, accent)
        self.add_pass12_hero_planet_detail(system, hero_pos, hero_radius, hero_color, seed + 12600, hero_kind, ringed=hero_ringed, gas_giant=hero_gas, accent=accent)
        self.add_pass13_hero_planet_ultra_detail(system, hero_pos, hero_radius, hero_color, seed + 12800, hero_kind, ringed=hero_ringed, gas_giant=hero_gas, accent=accent)
        self.add_pass13_visible_planet_showcase_detail(system, hero_pos, hero_radius, hero_color, seed + 13100, hero_kind, ringed=hero_ringed, gas_giant=hero_gas, accent=accent)
        self.generate_research_tasks(kind, hero_kind, seed + 13300)
        self.spawn_pass14_gameplay_loop(system, hero_pos, hero_radius, hero_color, seed + 13400, hero_kind, accent)

        # Close moons around the hero planet give it playable local scale and fly-by parallax.
        hero_moons = 1 + int(seeded_unit(seed + 12220) * 3)
        for m in range(hero_moons):
            mu = seeded_unit(seed + 12240 + m * 31)
            ma = mu * math.tau + m * 0.65
            mr = hero_radius * (1.85 + m * 0.78 + seeded_unit(seed + 12270 + m) * 0.36)
            moon_pos = Vec3(hero_pos.x + math.cos(ma) * mr, hero_pos.y + (seeded_unit(seed + 12300 + m) - 0.5) * 3.0, hero_pos.z + math.sin(ma) * mr * 0.46)
            moon_col = (min(1.0, hero_color[0] * 0.56 + 0.30), min(1.0, hero_color[1] * 0.56 + 0.30), min(1.0, hero_color[2] * 0.56 + 0.30), 1)
            moon = create_uv_sphere(system, "pass10 nearby hero moon", moon_pos, max(0.36, hero_radius * (0.16 + mu * 0.07)), 12, 24, moon_col, emission=(moon_col[0]*0.018, moon_col[1]*0.018, moon_col[2]*0.020, 1))
            moon.setLightOff(1)
            create_soft_disc_y(system, "pass10 nearby moon atmospheric rim", moon_pos + Vec3(-0.05, -0.08, 0.04), max(0.55, hero_radius*0.30), max(0.42, hero_radius*0.22), (moon_col[0], moon_col[1], moon_col[2], 0.045), (moon_col[0], moon_col[1], moon_col[2], 0.0), 28)

        planet_count = 3 + int(seeded_unit(seed + 501) * 3)
        ringed_forced = 1 + int(seeded_unit(seed + 621) * max(1, planet_count - 1))
        for i in range(planet_count):
            u = seeded_unit(seed + 700 + i * 41)
            v = seeded_unit(seed + 900 + i * 67)
            orbit = 135 + i * (95.0 + seeded_unit(seed + i * 29) * 42.0)
            angle = u * math.tau + i * 0.72
            # Vast spacing: most planets are tiny/far silhouettes at separate depth bands.
            px = math.cos(angle) * orbit
            py = 185 + i * (82.0 + seeded_unit(seed + i * 23) * 46.0) + math.sin(angle * 0.7) * 28.0
            pz = star_pos.z + math.sin(angle) * orbit * (0.075 + v * 0.045) - 10.0 + i * 0.75
            radius = 0.75 + seeded_unit(seed + 1110 + i * 13) * 2.0
            if i == ringed_forced or (kind == "ring_giant" and i == 1):
                radius *= 1.45
            color = body_accents[(i + int(seeded_unit(seed + i) * len(body_accents))) % len(body_accents)]
            if kind == "ice_moon" and i < 2:
                color = (0.48, 0.82, 1.0, 1)
            elif kind == "red_dwarf":
                color = (0.72 + 0.10 * u, 0.28 + 0.12 * v, 0.18, 1)
            elif kind == "nebula_gate" and i % 2 == 0:
                color = (0.62, 0.44, 0.95, 1)
            ringed = i == ringed_forced or (i % 4 == 2 and seeded_unit(seed + 1430 + i) > 0.60)
            gas_giant = radius > 2.8 or ringed
            self.make_pass09_planet(system, f"pass11 very far spaced planet {i}", Vec3(px, py, pz), radius, color, seed + 2000 + i * 157, ringed=ringed, gas_giant=gas_giant, star_bias=light_bias)

            # Vast orbital dust arcs are much subtler now, with broken spacing to avoid an arcade-grid look.
            if i % 2 == 0:
                start = -35 + int(seeded_unit(seed + i * 13) * 60)
                end = 115 + int(seeded_unit(seed + i * 17) * 95)
                create_annular_arc_y(system, "pass11 faint immense orbital dust sweep", star_pos + Vec3(0, -0.16 - i * 0.01, 0), orbit * 0.98, orbit * 1.01, start, end, 118, (star_color[0], star_color[1], star_color[2], 0.015 + i * 0.002), hpr=Vec3(0, 0, 2 + i * 7), emission=(star_color[0]*0.025, star_color[1]*0.020, star_color[2]*0.018, 1))

            moon_count = int(seeded_unit(seed + 3000 + i * 19) * 3)
            if ringed:
                moon_count += 1
            for m in range(moon_count):
                mu = seeded_unit(seed + i * 370 + m * 43)
                ma = mu * math.tau
                mr = radius * (1.70 + m * 0.70 + seeded_unit(seed + i * 440 + m) * 0.45)
                moon_pos = Vec3(px + math.cos(ma) * mr, py + (seeded_unit(seed + i + m * 3) - 0.5) * 2.2, pz + math.sin(ma) * mr * 0.42)
                moon_col = (min(1.0, color[0] * 0.62 + 0.24), min(1.0, color[1] * 0.62 + 0.24), min(1.0, color[2] * 0.62 + 0.24), 1)
                moon = create_uv_sphere(system, "pass10 far natural moon", moon_pos, max(0.14, radius * (0.12 + mu * 0.08)), 10, 20, moon_col, emission=(moon_col[0]*0.014, moon_col[1]*0.014, moon_col[2]*0.018, 1))
                moon.setLightOff(1)
                create_soft_disc_y(system, "pass10 far moon soft limb", moon_pos + Vec3(-0.035, -0.05, 0.025), max(0.26, radius*0.25), max(0.21, radius*0.20), (moon_col[0], moon_col[1], moon_col[2], 0.035), (moon_col[0], moon_col[1], moon_col[2], 0.0), 22)

        # Asteroid and cometary belts are now mostly distant, leaving the hero planet area readable.
        belt_count = 22 if kind in {"comet_shoal", "ring_giant"} else 16
        for i in range(belt_count):
            u = seeded_unit(seed + 5000 + i * 17)
            v = seeded_unit(seed + 5100 + i * 23)
            a = u * math.tau * 1.12
            r = 135 + v * 185
            pos = Vec3(math.cos(a) * r, 135 + seeded_unit(seed + i * 5) * 245, star_pos.z + math.sin(a) * r * 0.075 + (seeded_unit(seed + i * 7) - 0.5) * 10.0)
            rock_radius = 0.08 + seeded_unit(seed + 5200 + i) * 0.24
            rock_color = (0.30 + v * 0.16, 0.30 + v * 0.13, 0.34 + v * 0.11, 1)
            rock = create_uv_sphere(system, "pass11 distant rounded asteroid or comet nucleus", pos, rock_radius, 6, 12, rock_color, emission=(0.006, 0.008, 0.012, 1))
            rock.setHpr(i * 17, i * 11, i * 7)
            if kind == "comet_shoal" and i % 6 == 0:
                create_soft_disc_y(system, "pass11 far comet coma and ion tail", pos + Vec3(0.85 + u, 0.5 + v, 0), 1.25 + u * 1.0, 0.18 + v * 0.13, (0.38, 0.72, 1.0, 0.055), (0.08, 0.18, 0.34, 0.0), 22, hpr=Vec3(0, 0, 12 + i * 2))

        # Nearby fly-through galaxies remain, but they are offset away from the hero planet path.
        for i in range(3):
            p = Vec3(-150 + seeded_unit(seed + 6500 + i) * 300, 110 + seeded_unit(seed + 6600 + i) * 260, -12 + seeded_unit(seed + 6700 + i) * 78)
            self.make_pass08_micro_galaxy(system, f"pass11 far explorable tiny background galaxy {i}", p, 0.95 + seeded_unit(seed + i * 9) * 0.9, (accent[0], accent[1], accent[2], 1), seed + 7000 + i * 211, arms=2 + (i % 2), thickness=0.75 + i * 0.08)

        # Natural return gate behind the spawn point. Player turns around, aims, and clicks to fold in another random system.
        self.build_pass09_return_black_hole_gateway(root, seed, star_color)
        self.current_chunk_name = name
        self.apply_pass16_runtime_optimizations(system)

    def apply_pass16_runtime_optimizations(self, system: NodePath) -> None:
        """Lightweight scene optimization applied after a solar system is generated.

        Flattening transparent/generated geometry too aggressively can break handles used by
        gameplay targets, so this pass uses conservative model-node cleanup plus bounded
        animation throttling elsewhere.  It is safe for the procedural systems and keeps the
        new scan/salvage loop intact.
        """
        try:
            # Clear model nodes and mark the finished system as a static culling boundary.
            # Gameplay target NodePaths stay intact because we avoid flattening them away.
            system.clearModelNodes()
            system.setFinal(True)
        except Exception:
            pass
        # Clean stale handles left by collected samples from previous systems, then keep
        # animation lists bounded so Python does not touch hundreds of static nodes each tick.
        self.organic_cosmic_roots = [node for node in self.organic_cosmic_roots if not node.isEmpty()]
        self.cosmic_twinklers = [node for node in self.cosmic_twinklers if not node.isEmpty()]
        if STARFALL_FAST_PROFILE:
            self.organic_cosmic_roots = self.organic_cosmic_roots[:120]
            self.cosmic_twinklers = self.cosmic_twinklers[:70]

    def make_pass09_planet(self, parent: NodePath, name: str, pos: Vec3, radius: float, color: tuple[float, float, float, float], seed: int, ringed: bool = False, gas_giant: bool = False, star_bias: float = 1.0) -> NodePath:
        planet = create_uv_sphere(parent, name, pos, radius, 18, 36, color, emission=(color[0]*0.018*star_bias, color[1]*0.018*star_bias, color[2]*0.022*star_bias, 1))
        planet.setLightOff(1)
        self.organic_cosmic_roots.append(planet)
        # Natural limb/terminator: transparent overlays instead of angular surface details.
        create_soft_disc_y(parent, "pass09 planet atmospheric limb", pos + Vec3(-radius * 0.10, -0.10, radius * 0.06), radius * 1.32, radius * 1.08, (color[0], color[1], color[2], 0.060), (color[0], color[1], color[2], 0.0), 64, hpr=Vec3(0, 0, -8 + (seed % 17)))
        create_soft_disc_y(parent, "pass09 planet night terminator", pos + Vec3(-radius * 0.28, -0.08, -radius * 0.03), radius * 0.76, radius * 1.02, (0.0, 0.0, 0.0, 0.26), (0.0, 0.0, 0.0, 0.0), 48, hpr=Vec3(0, 0, -12 + (seed % 31)))
        # Belts/clouds using soft curved bands. No boxes or label-like details on planets.
        band_count = 5 if gas_giant else 3
        for b in range(band_count):
            offset = (-0.35 + b * (0.70 / max(1, band_count-1))) * radius
            alpha = 0.055 + seeded_unit(seed + b * 29) * 0.050
            band_col = (min(1.0, color[0] * (0.76 + b*0.035) + 0.05), min(1.0, color[1] * (0.76 + b*0.025) + 0.04), min(1.0, color[2] * (0.78 + b*0.020) + 0.04), alpha)
            create_soft_disc_y(parent, "pass09 soft atmospheric belt", pos + Vec3(0, -0.075 - b*0.006, offset), radius * (1.04 + b*0.018), max(0.035, radius * 0.060), band_col, (band_col[0], band_col[1], band_col[2], 0.0), 28, hpr=Vec3(0, 0, -3 + b * 4 + (seed % 9)))
        if ringed:
            ring_color = (min(1.0, color[0]*0.72 + 0.22), min(1.0, color[1]*0.72 + 0.22), min(1.0, color[2]*0.72 + 0.22), 0.115)
            for k, mul in enumerate([1.72, 2.05, 2.42]):
                create_annular_arc_y(parent, "pass09 natural planetary ring dust", pos + Vec3(0, -0.13 - k * 0.018, 0), radius * mul, radius * (mul + 0.08), -30 + k * 16, 320 - k * 13, 96, ring_color, hpr=Vec3(0, 0, -16 + (seed % 21)), emission=(ring_color[0]*0.06, ring_color[1]*0.05, ring_color[2]*0.04, 1))
            create_soft_disc_y(parent, "pass09 ring soft backscatter glow", pos + Vec3(0, -0.18, 0), radius * 2.65, radius * 0.34, (ring_color[0], ring_color[1], ring_color[2], 0.045), (ring_color[0], ring_color[1], ring_color[2], 0.0), 64, hpr=Vec3(0, 0, -16 + (seed % 21)))
        return planet


    def add_pass10_hero_planet_detail(self, parent: NodePath, pos: Vec3, radius: float, color: tuple[float, float, float, float], seed: int, hero_kind: str, ringed: bool = False) -> None:
        """Extra natural-looking detail for the guaranteed nearby planet.

        These are soft overlay volumes and small rounded glints, not angular decals.
        They read as continents, cloud decks, ice cracks, storm bands, aurora, or city lights
        depending on the generated destination kind.
        """
        # Extra atmospheric shells make the nearby body feel larger and less like a plain ball.
        create_soft_disc_y(parent, "pass10 hero planet outer atmosphere", pos + Vec3(-radius * 0.08, -0.18, radius * 0.04), radius * 1.55, radius * 1.25, (color[0], color[1], color[2], 0.075), (color[0], color[1], color[2], 0.0), 96, hpr=Vec3(0, 0, -8 + seed % 19))
        create_soft_disc_y(parent, "pass10 hero planet sunset limb", pos + Vec3(radius * 0.24, -0.22, -radius * 0.10), radius * 0.55, radius * 1.02, (1.0, 0.58, 0.25, 0.060), (1.0, 0.22, 0.08, 0.0), 48, hpr=Vec3(0, 0, 6 + seed % 17))
        create_soft_disc_y(parent, "pass10 hero planet soft shadow falloff", pos + Vec3(-radius * 0.42, -0.19, -radius * 0.02), radius * 0.72, radius * 1.12, (0.0, 0.0, 0.0, 0.34), (0.0, 0.0, 0.0, 0.0), 72, hpr=Vec3(0, 0, -13 + seed % 29))

        # Surface regions: all round/organic, placed on the front-facing hemisphere.
        patch_count = 20 if hero_kind not in {"ringed", "furnace"} else 14
        for i in range(patch_count):
            u = seeded_unit(seed + i * 31)
            v = seeded_unit(seed + 400 + i * 37)
            a = u * math.tau
            rr = math.sqrt(v) * radius * 0.72
            dx = math.cos(a) * rr
            dz = math.sin(a) * rr * 0.82
            # Keep patch inside a plausible visible disc.
            if (dx / (radius * 0.86)) ** 2 + (dz / (radius * 0.74)) ** 2 > 1.0:
                continue
            if hero_kind == "ice":
                patch_col = (0.72 + 0.16 * u, 0.92, 1.0, 0.070 + 0.045 * v)
            elif hero_kind == "furnace":
                patch_col = (1.0, 0.38 + 0.22 * u, 0.12, 0.070 + 0.060 * v)
            elif hero_kind == "terrestrial":
                if i % 3 == 0:
                    patch_col = (0.18, 0.42 + 0.20*u, 0.26, 0.080 + 0.040*v)
                else:
                    patch_col = (0.25 + 0.12*u, 0.46 + 0.10*v, 0.30, 0.065 + 0.035*v)
            elif hero_kind == "ringed":
                if i % 2 == 0:
                    patch_col = (0.54 + 0.10*u, 0.36 + 0.10*v, 0.20, 0.120 + 0.055*v)
                else:
                    patch_col = (0.96, 0.74 + 0.10*u, 0.42, 0.105 + 0.045*v)
            elif hero_kind == "nebula":
                patch_col = (0.78, 0.50 + 0.20*u, 1.0, 0.105 + 0.060*v)
            else:
                patch_col = (min(1.0, color[0]*0.75 + 0.16), min(1.0, color[1]*0.75 + 0.16), min(1.0, color[2]*0.75 + 0.16), 0.095 + 0.055*v)
            sx = radius * (0.10 + seeded_unit(seed + 800 + i) * 0.22)
            sz = radius * (0.055 + seeded_unit(seed + 900 + i) * 0.16)
            create_soft_disc_y(parent, "pass10 hero organic surface region", pos + Vec3(dx, -radius * 0.115 - i * 0.001, dz), sx, sz, patch_col, (patch_col[0], patch_col[1], patch_col[2], 0.0), 28, hpr=Vec3(0, 0, math.degrees(a) * 0.18 + i * 11))

        # Cloud/storm bands wrap across the front hemisphere with varying thickness.
        band_count = 7 if hero_kind in {"ringed", "furnace"} else 5
        for b in range(band_count):
            zoff = (-0.44 + b * (0.88 / max(1, band_count - 1))) * radius
            u = seeded_unit(seed + 1300 + b * 17)
            if hero_kind == "furnace":
                band_col = (1.0, 0.46 + u*0.22, 0.16, 0.115)
            elif hero_kind == "ice":
                band_col = (0.78, 0.96, 1.0, 0.095)
            else:
                band_col = (0.88, 0.93, 1.0, 0.075 + 0.030*u)
            create_soft_disc_y(parent, "pass10 hero soft cloud/storm belt", pos + Vec3(0, -radius * 0.145 - b*0.006, zoff), radius * (1.06 + 0.04*u), max(0.055, radius * (0.055 + 0.026*u)), band_col, (band_col[0], band_col[1], band_col[2], 0.0), 42, hpr=Vec3(0, 0, -5 + b * 3 + seed % 11))

        # A few natural storm ovals / auroral glows.  They are small, curved, and low-alpha.
        for i in range(4):
            u = seeded_unit(seed + 1900 + i * 43)
            a = (u * 0.72 + 0.12) * math.tau
            dx = math.cos(a) * radius * (0.28 + 0.12 * i)
            dz = math.sin(a) * radius * (0.18 + 0.07 * i)
            if hero_kind == "furnace":
                storm_col = (1.0, 0.64, 0.18, 0.075)
            elif hero_kind == "nebula":
                storm_col = (0.68, 0.95, 1.0, 0.070)
            else:
                storm_col = (0.90, 0.96, 1.0, 0.055)
            create_soft_disc_y(parent, "pass10 hero oval storm or aurora", pos + Vec3(dx, -radius * 0.17 - i*0.006, dz), radius * (0.15 + 0.05*u), radius * (0.045 + 0.025*u), storm_col, (storm_col[0], storm_col[1], storm_col[2], 0.0), 28, hpr=Vec3(0, 0, i * 29 + seed % 23))

        if hero_kind == "terrestrial":
            # Tiny rounded night-side glints read as settlement lights without becoming UI markers.
            for i in range(18):
                u = seeded_unit(seed + 2400 + i * 13)
                v = seeded_unit(seed + 2600 + i * 19)
                dx = (-0.55 + u * 0.55) * radius
                dz = (-0.38 + v * 0.76) * radius
                light_col = (0.65, 0.90, 0.70, 0.070 + 0.050 * v)
                create_soft_disc_y(parent, "pass10 hero tiny settlement light cluster", pos + Vec3(dx, -radius * 0.19 - i*0.002, dz), radius * 0.018, radius * 0.010, light_col, (light_col[0], light_col[1], light_col[2], 0.0), 10, hpr=Vec3(0, 0, i * 17))

        if ringed:
            # Softer near-planet ring layering; all rounded arcs, no hard-edged panels.
            ring_col = (min(1.0, color[0]*0.82 + 0.18), min(1.0, color[1]*0.82 + 0.18), min(1.0, color[2]*0.82 + 0.18), 0.105)
            for k, mul in enumerate([2.85, 3.18, 3.55, 3.95]):
                create_annular_arc_y(parent, "pass10 hero wide natural ring lane", pos + Vec3(0, -0.31 - k*0.020, 0), radius * mul, radius * (mul + 0.055), -48 + k*8, 332 - k*11, 132, ring_col, hpr=Vec3(0, 0, -18 + seed % 25), emission=(ring_col[0]*0.055, ring_col[1]*0.050, ring_col[2]*0.048, 1))
            create_soft_disc_y(parent, "pass10 hero diffuse ring backscatter", pos + Vec3(0, -0.38, 0), radius * 4.15, radius * 0.44, (ring_col[0], ring_col[1], ring_col[2], 0.040), (ring_col[0], ring_col[1], ring_col[2], 0.0), 80, hpr=Vec3(0, 0, -18 + seed % 25))


    def add_pass11_near_planet_orbital_environment(self, parent: NodePath, pos: Vec3, radius: float, color: tuple[float, float, float, float], seed: int, hero_kind: str, accent: tuple[float, float, float, float]) -> None:
        """Local hero-planet orbital detail for Pass 11.

        The goal is a realistic fly-by composition: one close planet with its own
        soft dust, moonlets, debris, and salvage/research POIs, while the rest of
        the solar system remains vastly spaced out.
        """
        local = parent.attachNewNode("pass11 local hero-planet orbit environment")
        local.setTransparency(TransparencyAttrib.M_alpha)
        local.setDepthWrite(False)

        # Soft local orbital haze and magnetospheric curtains. These are broad,
        # translucent volumes, not hard orbit lines.
        haze_col = (min(1.0, color[0] * 0.78 + 0.10), min(1.0, color[1] * 0.78 + 0.10), min(1.0, color[2] * 0.78 + 0.10), 0.055)
        create_soft_disc_y(local, "pass11 near planet exosphere glow", pos + Vec3(0, -0.48, 0), radius * 2.35, radius * 1.62, haze_col, (haze_col[0], haze_col[1], haze_col[2], 0.0), 112, hpr=Vec3(0, 0, -9 + seed % 31))
        create_soft_disc_y(local, "pass11 local orbital dust plane", pos + Vec3(0, -0.62, 0), radius * 5.20, radius * 0.38, (color[0], color[1], color[2], 0.040), (color[0], color[1], color[2], 0.0), 96, hpr=Vec3(0, 0, -18 + seed % 41))
        create_soft_disc_y(local, "pass11 soft planet magnetotail", pos + Vec3(radius * 1.90, 0.35, radius * 0.18), radius * 2.4, radius * 0.30, (accent[0], accent[1], accent[2], 0.040), (accent[0], accent[1], accent[2], 0.0), 72, hpr=Vec3(0, 0, 8 + seed % 23))

        # Realistic nearby rounded rocks, ice chunks, and moonlets. Keep them outside
        # the main approach lane but close enough to provide parallax when flying.
        for i in range(24):
            u = seeded_unit(seed + 100 + i * 13)
            v = seeded_unit(seed + 300 + i * 17)
            a = (u * 0.88 + 0.05) * math.tau
            rr = radius * (2.65 + v * 2.65)
            yoff = -2.0 + seeded_unit(seed + 500 + i * 19) * 7.6
            pos_i = Vec3(pos.x + math.cos(a) * rr, pos.y + yoff, pos.z + math.sin(a) * rr * (0.22 + 0.22 * seeded_unit(seed + 700 + i)))
            rock_radius = 0.075 + seeded_unit(seed + 900 + i * 11) * 0.30
            if i % 11 == 0:
                rock_radius *= 1.9
            if hero_kind == "ice":
                rock_col = (0.55 + 0.24*v, 0.75 + 0.18*u, 0.92 + 0.08*v, 1)
                rim_col = (0.50, 0.82, 1.0, 0.045)
            elif hero_kind == "furnace":
                rock_col = (0.38 + 0.30*v, 0.22 + 0.12*u, 0.16, 1)
                rim_col = (1.0, 0.42, 0.18, 0.040)
            else:
                rock_col = (0.30 + 0.18*v, 0.31 + 0.16*u, 0.34 + 0.16*v, 1)
                rim_col = (accent[0], accent[1], accent[2], 0.035)
            rock = create_uv_sphere(local, "pass11 local rounded orbital fragment", pos_i, rock_radius, 7, 14, rock_col, emission=(rock_col[0]*0.012, rock_col[1]*0.012, rock_col[2]*0.014, 1))
            rock.setHpr(i * 31, i * 17, i * 9)
            if i % 7 == 0:
                create_soft_disc_y(local, "pass11 local fragment faint coma", pos_i + Vec3(0.18, -0.08, 0.05), rock_radius * 3.4, rock_radius * 1.1, rim_col, (rim_col[0], rim_col[1], rim_col[2], 0.0), 18, hpr=Vec3(0, 0, i * 23))

        # Curved, believable orbiting salvage/research POIs. These are small enough
        # to feel like objects near a large planet, and mostly cylindrical/rounded.
        poi_count = 5
        poi_names = ["listening probe", "derelict mapper", "ice-core canister", "survey buoy", "broken relay"]
        for i in range(poi_count):
            u = seeded_unit(seed + 1300 + i * 29)
            a = (0.10 + u * 0.72 + i * 0.14) * math.tau
            rr = radius * (2.25 + i * 0.48 + seeded_unit(seed + 1400 + i) * 0.42)
            poi_pos = Vec3(pos.x + math.cos(a) * rr, pos.y - 1.5 + i * 1.15, pos.z + math.sin(a) * rr * 0.36)
            poi = local.attachNewNode(f"pass11 orbital POI {poi_names[i]}")
            poi.setPos(poi_pos)
            poi.setHpr(math.degrees(a) + 90, -3 + i * 2, math.sin(i) * 9)
            # Rounded pressure body / payload core.
            core_col = (0.23 + accent[0] * 0.22, 0.26 + accent[1] * 0.22, 0.32 + accent[2] * 0.22, 1)
            create_cylinder_y(poi, "pass11 rounded POI pressure can", Vec3(0, 0, 0), 0.16 + 0.02 * i, 0.86 + 0.10 * i, 18, core_col, hpr=Vec3(0, 90, 0), emission=(0.018, 0.024, 0.034, 1))
            create_uv_sphere(poi, "pass11 POI dome cap", Vec3(-0.46 - i*0.03, 0, 0), 0.17 + 0.014*i, 8, 16, (0.42, 0.48, 0.56, 1), emission=(0.018, 0.022, 0.030, 1))
            create_uv_sphere(poi, "pass11 POI aft cap", Vec3(0.46 + i*0.04, 0, 0), 0.14 + 0.012*i, 8, 16, (0.14, 0.17, 0.21, 1), emission=(0.012, 0.016, 0.022, 1))
            # Thin rounded antenna/ring features. A few small boxes are retained as
            # spacecraft hardware, but the silhouette is mostly smooth.
            create_cylinder_y(poi, "pass11 POI soft antenna mast", Vec3(0.0, 0.0, 0.36 + i*0.02), 0.018, 0.88 + i*0.10, 8, (0.52, 0.62, 0.72, 1), hpr=Vec3(90, 0, 0), emission=(0.025, 0.030, 0.040, 1))
            create_soft_disc_y(poi, "pass11 POI sensor glow", Vec3(-0.62 - i*0.02, -0.035, 0.0), 0.24 + i*0.02, 0.18 + i*0.015, (accent[0], accent[1], accent[2], 0.120), (accent[0], accent[1], accent[2], 0.0), 28, hpr=Vec3(0, 0, i * 17))
            create_soft_disc_y(local, "pass11 POI faint scan wake", poi_pos + Vec3(0.30, 0.22, 0), 0.92 + 0.16*i, 0.11 + 0.02*i, (accent[0], accent[1], accent[2], 0.040), (accent[0], accent[1], accent[2], 0.0), 24, hpr=Vec3(0, 0, math.degrees(a) + 12))
            self.organic_cosmic_roots.append(poi)

        # A gentle auroral curtain on the planet-facing side. It makes the nearby
        # body feel alive without creating flat angular markers.
        for i in range(5):
            u = seeded_unit(seed + 1800 + i * 23)
            z = pos.z + (-0.42 + i * 0.21) * radius
            x = pos.x + radius * (0.42 + 0.10 * math.sin(i))
            create_soft_disc_y(local, "pass11 planet auroral veil", Vec3(x, pos.y - radius * 0.25 - i * 0.012, z), radius * (0.34 + 0.04*u), radius * 0.050, (accent[0], min(1.0, accent[1] + 0.25), min(1.0, accent[2] + 0.18), 0.060), (accent[0], accent[1], accent[2], 0.0), 32, hpr=Vec3(0, 0, 86 + i * 5))

    def add_pass12_hero_planet_detail(self, parent: NodePath, pos: Vec3, radius: float, color: tuple[float, float, float, float], seed: int, hero_kind: str, ringed: bool = False, gas_giant: bool = False, accent: tuple[float, float, float, float] = (0.45, 0.7, 1.0, 1.0)) -> None:
        """Pass 12 planet-detail pass.

        Deepens the nearby hero planet with larger surface breakup, crater/ridge fields,
        atmospheric layering, cloud shadows, and type-specific detail while staying smooth
        and organic.  All overlays remain rounded/soft so the planet reads as natural rather
        than decal-like.
        """
        detail = parent.attachNewNode("pass12 hero planet detail envelope")
        detail.setTransparency(TransparencyAttrib.M_alpha)
        detail.setDepthWrite(False)

        # Extra atmospheric depth and broad dusk/dawn shading.
        create_soft_disc_y(detail, "pass12 hero broad stratosphere shell", pos + Vec3(-radius * 0.03, -0.28, radius * 0.01), radius * 1.78, radius * 1.40, (color[0], color[1], color[2], 0.060), (color[0], color[1], color[2], 0.0), 112, hpr=Vec3(0, 0, -5 + seed % 23))
        create_soft_disc_y(detail, "pass12 hero cool shadow hemisphere", pos + Vec3(-radius * 0.48, -0.26, 0), radius * 0.90, radius * 1.18, (0.0, 0.0, 0.0, 0.20), (0.0, 0.0, 0.0, 0.0), 92, hpr=Vec3(0, 0, -9 + seed % 17))
        create_soft_disc_y(detail, "pass12 hero warm dawn arc", pos + Vec3(radius * 0.43, -0.24, -radius * 0.02), radius * 0.42, radius * 1.05, (1.0, 0.72, 0.36, 0.050), (1.0, 0.22, 0.08, 0.0), 64, hpr=Vec3(0, 0, 10 + seed % 21))

        if hero_kind in {"ringed", "nebula"} or gas_giant:
            # Gas/giant worlds: richer turbulence, belts, and one or two large storms.
            for i in range(10):
                u = seeded_unit(seed + 40 + i * 19)
                zoff = (-0.48 + i * 0.105) * radius
                band_h = radius * (0.058 + 0.042 * seeded_unit(seed + 90 + i))
                hue = seeded_unit(seed + 130 + i * 7)
                band_col = (
                    min(1.0, color[0] * (0.80 + 0.22 * hue) + 0.10),
                    min(1.0, color[1] * (0.78 + 0.18 * (1.0-hue)) + 0.08),
                    min(1.0, color[2] * (0.78 + 0.20 * hue) + 0.08),
                    0.085 + 0.020 * u,
                )
                create_soft_disc_y(detail, "pass12 giant turbulent band", pos + Vec3(0, -radius * 0.17 - i * 0.010, zoff), radius * (1.12 + 0.06 * u), band_h, band_col, (band_col[0], band_col[1], band_col[2], 0.0), 54, hpr=Vec3(0, 0, -7 + i * 2 + seed % 13))
                create_soft_disc_y(detail, "pass12 giant band shadow", pos + Vec3(-radius * 0.08, -radius * 0.18 - i * 0.010, zoff + radius * 0.012), radius * (0.96 + 0.03 * u), band_h * 0.82, (0.0, 0.0, 0.0, 0.030), (0.0, 0.0, 0.0, 0.0), 42, hpr=Vec3(0, 0, -8 + i * 2))
            for i in range(2):
                u = seeded_unit(seed + 260 + i * 41)
                storm_col = (min(1.0, color[0] + 0.18), min(1.0, color[1] + 0.16), min(1.0, color[2] + 0.14), 0.095)
                storm_pos = pos + Vec3(radius * (-0.10 + 0.34 * i), -radius * 0.19 - i * 0.01, radius * (-0.14 + 0.22 * u))
                create_soft_disc_y(detail, "pass12 giant storm eye", storm_pos, radius * (0.24 + 0.10 * u), radius * (0.11 + 0.05 * u), storm_col, (storm_col[0], storm_col[1], storm_col[2], 0.0), 34, hpr=Vec3(0, 0, 18 + i * 27 + seed % 19))
                create_soft_disc_y(detail, "pass12 giant storm rim", storm_pos + Vec3(0.05, -0.01, 0.0), radius * (0.30 + 0.09 * u), radius * (0.14 + 0.04 * u), (1.0, 0.95, 0.86, 0.038), (1.0, 0.95, 0.86, 0.0), 34, hpr=Vec3(0, 0, 18 + i * 27 + seed % 19))
        else:
            # Rocky/ice worlds: macro landmass or terrain breakup.
            macro_count = 8 if hero_kind == "terrestrial" else 7
            for i in range(macro_count):
                u = seeded_unit(seed + 300 + i * 29)
                v = seeded_unit(seed + 500 + i * 31)
                a = u * math.tau
                rr = math.sqrt(v) * radius * 0.60
                dx = math.cos(a) * rr
                dz = math.sin(a) * rr * 0.78
                sx = radius * (0.22 + 0.20 * seeded_unit(seed + 700 + i * 11))
                sz = radius * (0.10 + 0.16 * seeded_unit(seed + 900 + i * 13))
                if hero_kind == "ice":
                    macro_col = (0.74 + 0.12 * u, 0.90 + 0.08 * v, 1.0, 0.085)
                    shadow_col = (0.36, 0.58, 0.75, 0.032)
                elif hero_kind == "furnace":
                    macro_col = (0.52 + 0.18 * u, 0.22 + 0.08 * v, 0.14, 0.090)
                    shadow_col = (0.20, 0.07, 0.04, 0.040)
                elif hero_kind == "terrestrial":
                    if i % 2 == 0:
                        macro_col = (0.16 + 0.10 * u, 0.40 + 0.18 * v, 0.20 + 0.05 * u, 0.095)
                    else:
                        macro_col = (0.34 + 0.12 * u, 0.48 + 0.10 * v, 0.24 + 0.04 * u, 0.075)
                    shadow_col = (0.08, 0.16, 0.10, 0.032)
                elif hero_kind == "cold-rock":
                    macro_col = (0.46 + 0.12 * u, 0.52 + 0.10 * v, 0.58 + 0.08 * u, 0.080)
                    shadow_col = (0.12, 0.14, 0.18, 0.030)
                else:
                    macro_col = (min(1.0, color[0] + 0.08), min(1.0, color[1] + 0.10), min(1.0, color[2] + 0.10), 0.082)
                    shadow_col = (0.10, 0.10, 0.14, 0.028)
                create_soft_disc_y(detail, "pass12 hero macro terrain region", pos + Vec3(dx, -radius * 0.15 - i * 0.003, dz), sx, sz, macro_col, (macro_col[0], macro_col[1], macro_col[2], 0.0), 42, hpr=Vec3(0, 0, math.degrees(a) * 0.32 + i * 9))
                create_soft_disc_y(detail, "pass12 hero terrain shadow pocket", pos + Vec3(dx - sx * 0.10, -radius * 0.16 - i * 0.003, dz - sz * 0.04), sx * 0.82, sz * 0.68, shadow_col, (shadow_col[0], shadow_col[1], shadow_col[2], 0.0), 36, hpr=Vec3(0, 0, math.degrees(a) * 0.32 + i * 9))

            # Smaller feature fields: crater chains, ridges, ice fissures, lava belts, etc.
            feature_count = 22
            for i in range(feature_count):
                u = seeded_unit(seed + 1200 + i * 17)
                v = seeded_unit(seed + 1500 + i * 23)
                a = u * math.tau
                rr = math.sqrt(v) * radius * 0.78
                dx = math.cos(a) * rr
                dz = math.sin(a) * rr * 0.82
                if (dx / (radius * 0.88)) ** 2 + (dz / (radius * 0.76)) ** 2 > 1.0:
                    continue
                if hero_kind == "ice":
                    feat_col = (0.82, 0.96, 1.0, 0.080)
                    feat_shadow = (0.48, 0.68, 0.88, 0.028)
                    sx = radius * (0.14 + 0.10 * u)
                    sz = radius * (0.018 + 0.020 * v)
                elif hero_kind == "furnace":
                    feat_col = (1.0, 0.46 + 0.18 * u, 0.16, 0.085)
                    feat_shadow = (0.26, 0.08, 0.04, 0.032)
                    sx = radius * (0.17 + 0.12 * u)
                    sz = radius * (0.024 + 0.020 * v)
                elif hero_kind == "terrestrial":
                    feat_col = (0.70, 0.76, 0.62, 0.060) if i % 4 == 0 else (0.18 + 0.10 * u, 0.28 + 0.12 * v, 0.18, 0.060)
                    feat_shadow = (0.06, 0.10, 0.06, 0.028)
                    sx = radius * (0.10 + 0.10 * u)
                    sz = radius * (0.028 + 0.050 * v)
                else:
                    feat_col = (0.70 + 0.14 * u, 0.74 + 0.12 * v, 0.80 + 0.08 * u, 0.058)
                    feat_shadow = (0.12, 0.14, 0.18, 0.024)
                    sx = radius * (0.09 + 0.08 * u)
                    sz = radius * (0.022 + 0.045 * v)
                ang = math.degrees(a) * 0.22 + i * 13
                create_soft_disc_y(detail, "pass12 hero fine terrain feature", pos + Vec3(dx, -radius * 0.175 - i * 0.001, dz), sx, sz, feat_col, (feat_col[0], feat_col[1], feat_col[2], 0.0), 26, hpr=Vec3(0, 0, ang))
                create_soft_disc_y(detail, "pass12 hero terrain feature shadow", pos + Vec3(dx - sx * 0.12, -radius * 0.178 - i * 0.001, dz + sz * 0.03), sx * 0.88, sz * 0.72, feat_shadow, (feat_shadow[0], feat_shadow[1], feat_shadow[2], 0.0), 22, hpr=Vec3(0, 0, ang))

            # Crater chain overlay for rocky or icy bodies.
            if hero_kind in {"cold-rock", "ice", "terrestrial"}:
                crater_count = 11
                for i in range(crater_count):
                    u = seeded_unit(seed + 1900 + i * 37)
                    v = seeded_unit(seed + 2100 + i * 41)
                    dx = (-0.52 + u * 0.88) * radius
                    dz = (-0.36 + v * 0.72) * radius
                    if (dx / (radius * 0.86)) ** 2 + (dz / (radius * 0.76)) ** 2 > 1.0:
                        continue
                    rr = radius * (0.030 + 0.050 * seeded_unit(seed + 2400 + i))
                    create_soft_disc_y(detail, "pass12 hero crater shadow", pos + Vec3(dx, -radius * 0.182 - i * 0.001, dz), rr, rr * (0.82 + 0.20 * v), (0.0, 0.0, 0.0, 0.075), (0.0, 0.0, 0.0, 0.0), 20, hpr=Vec3(0, 0, i * 17 + seed % 23))
                    create_soft_disc_y(detail, "pass12 hero crater rim", pos + Vec3(dx + rr * 0.08, -radius * 0.181 - i * 0.001, dz - rr * 0.05), rr * 1.18, rr * (0.96 + 0.18 * v), (0.88, 0.88, 0.88, 0.022), (0.88, 0.88, 0.88, 0.0), 20, hpr=Vec3(0, 0, i * 17 + seed % 23))

        # Polar caps / bright polar haze where appropriate.
        if hero_kind in {"ice", "cold-rock", "terrestrial"}:
            cap_col = (0.90, 0.96, 1.0, 0.080) if hero_kind == "ice" else (0.88, 0.90, 0.94, 0.045)
            for sign in (-1, 1):
                create_soft_disc_y(detail, "pass12 hero polar cap", pos + Vec3(0, -radius * 0.18, sign * radius * 0.58), radius * 0.26, radius * 0.10, cap_col, (cap_col[0], cap_col[1], cap_col[2], 0.0), 24, hpr=Vec3(0, 0, 2 + sign * 8))

        # Cloud layers and broad cloud shadows help the nearby world feel less like a plain sphere.
        cloud_layers = 6 if hero_kind not in {"ringed", "nebula"} else 8
        for i in range(cloud_layers):
            u = seeded_unit(seed + 3000 + i * 17)
            zoff = (-0.46 + i * (0.92 / max(1, cloud_layers - 1))) * radius
            cloud_col = (0.92, 0.96, 1.0, 0.040 + 0.025 * u)
            create_soft_disc_y(detail, "pass12 hero cloud veil", pos + Vec3(radius * 0.02, -radius * 0.205 - i * 0.004, zoff), radius * (0.92 + 0.10 * u), radius * (0.046 + 0.028 * u), cloud_col, (cloud_col[0], cloud_col[1], cloud_col[2], 0.0), 44, hpr=Vec3(0, 0, -4 + i * 4 + seed % 13))
            create_soft_disc_y(detail, "pass12 hero cloud shadow", pos + Vec3(-radius * 0.03, -radius * 0.198 - i * 0.004, zoff + radius * 0.01), radius * (0.84 + 0.08 * u), radius * (0.034 + 0.020 * u), (0.0, 0.0, 0.0, 0.018), (0.0, 0.0, 0.0, 0.0), 36, hpr=Vec3(0, 0, -4 + i * 4 + seed % 13))

        # Atmospheric glow accents: aurora, volcanic glow, or oceanic specular hints.
        if hero_kind == "furnace":
            for i in range(5):
                u = seeded_unit(seed + 3500 + i * 29)
                create_soft_disc_y(detail, "pass12 hero lava glow ribbon", pos + Vec3(radius * (-0.20 + 0.14 * i), -radius * 0.22 - i * 0.004, radius * (-0.35 + 0.18 * u)), radius * (0.20 + 0.08 * u), radius * 0.030, (1.0, 0.44 + 0.20 * u, 0.16, 0.060), (1.0, 0.16, 0.05, 0.0), 22, hpr=Vec3(0, 0, -20 + i * 11))
        elif hero_kind == "terrestrial":
            create_soft_disc_y(detail, "pass12 hero oceanic glint", pos + Vec3(radius * 0.18, -radius * 0.23, -radius * 0.08), radius * 0.36, radius * 0.12, (0.74, 0.92, 1.0, 0.040), (0.74, 0.92, 1.0, 0.0), 28, hpr=Vec3(0, 0, 18))
        else:
            for i in range(4):
                u = seeded_unit(seed + 3600 + i * 31)
                create_soft_disc_y(detail, "pass12 hero soft auroral haze", pos + Vec3(radius * 0.44, -radius * 0.20 - i * 0.005, radius * (-0.25 + 0.16 * i)), radius * (0.22 + 0.08 * u), radius * 0.040, (accent[0], min(1.0, accent[1] + 0.18), min(1.0, accent[2] + 0.12), 0.050), (accent[0], accent[1], accent[2], 0.0), 24, hpr=Vec3(0, 0, 82 + i * 4))

    def add_pass13_visible_planet_showcase_detail(self, parent: NodePath, pos: Vec3, radius: float, color: tuple[float, float, float, float], seed: int, hero_kind: str, ringed: bool = False, gas_giant: bool = False, accent: tuple[float, float, float, float] = (0.45, 0.7, 1.0, 1.0)) -> None:
        """Verification-visible planet detail.

        Earlier detail layers were conservative and subtle. This layer deliberately uses
        higher-contrast but still soft/organic overlays so screenshots clearly show the
        planet pass instead of looking like the previous plain sphere.
        """
        layer = parent.attachNewNode("pass13 visible hero planet showcase detail")
        layer.setTransparency(TransparencyAttrib.M_alpha)
        layer.setDepthWrite(False)

        if hero_kind in {"ringed", "nebula"} or gas_giant:
            # Strong, natural giant-planet banding visible at gameplay distance.
            palette = [
                (min(1.0, color[0] * 0.72 + 0.22), min(1.0, color[1] * 0.72 + 0.18), min(1.0, color[2] * 0.72 + 0.10), 0.18),
                (min(1.0, color[0] * 0.55 + 0.33), min(1.0, color[1] * 0.56 + 0.28), min(1.0, color[2] * 0.56 + 0.20), 0.15),
                (0.20, 0.12, 0.08, 0.10),
            ]
            for i in range(12):
                zoff = (-0.50 + i * 0.091) * radius
                u = seeded_unit(seed + 10 + i * 19)
                col = palette[i % len(palette)]
                create_soft_disc_y(layer, "pass13 visible gas giant broad belt", pos + Vec3(0, -radius * 0.245 - i * 0.003, zoff), radius * (1.10 + 0.04 * u), radius * (0.045 + 0.020 * u), col, (col[0], col[1], col[2], 0.0), 48, hpr=Vec3(0, 0, -6 + i * 2 + seed % 9))
            for i in range(3):
                u = seeded_unit(seed + 310 + i * 41)
                x = radius * (-0.18 + i * 0.22)
                z = radius * (-0.20 + 0.20 * u + i * 0.10)
                create_soft_disc_y(layer, "pass13 visible giant storm oval", pos + Vec3(x, -radius * 0.265 - i * 0.004, z), radius * (0.22 + 0.05 * u), radius * (0.085 + 0.020 * u), (1.0, 0.88, 0.64, 0.15), (1.0, 0.60, 0.30, 0.0), 30, hpr=Vec3(0, 0, 16 + i * 28))
        else:
            # Big readable continents / terrain plates.
            for i in range(14):
                u = seeded_unit(seed + i * 23)
                v = seeded_unit(seed + 500 + i * 29)
                a = u * math.tau
                rr = math.sqrt(v) * radius * 0.63
                dx = math.cos(a) * rr
                dz = math.sin(a) * rr * 0.78
                if (dx / (radius * 0.88)) ** 2 + (dz / (radius * 0.78)) ** 2 > 1.0:
                    continue
                if hero_kind == "ice":
                    main_col = (0.82, 0.96, 1.0, 0.18)
                    dark_col = (0.30, 0.52, 0.72, 0.10)
                elif hero_kind == "furnace":
                    main_col = (0.95, 0.33 + 0.18 * u, 0.12, 0.18)
                    dark_col = (0.20, 0.06, 0.03, 0.12)
                elif hero_kind == "terrestrial":
                    main_col = (0.12 + 0.12 * u, 0.40 + 0.18 * v, 0.18 + 0.05 * u, 0.18)
                    dark_col = (0.04, 0.11, 0.06, 0.10)
                else:
                    main_col = (0.60 + 0.12 * u, 0.66 + 0.10 * v, 0.74, 0.16)
                    dark_col = (0.10, 0.13, 0.18, 0.10)
                sx = radius * (0.14 + 0.20 * seeded_unit(seed + 900 + i))
                sz = radius * (0.055 + 0.130 * seeded_unit(seed + 1100 + i))
                ang = math.degrees(a) * 0.30 + i * 17
                create_soft_disc_y(layer, "pass13 visible macro landmass", pos + Vec3(dx, -radius * 0.245 - i * 0.002, dz), sx, sz, main_col, (main_col[0], main_col[1], main_col[2], 0.0), 36, hpr=Vec3(0, 0, ang))
                create_soft_disc_y(layer, "pass13 visible terrain lowland shadow", pos + Vec3(dx - sx * 0.10, -radius * 0.248 - i * 0.002, dz + sz * 0.05), sx * 0.80, sz * 0.70, dark_col, (dark_col[0], dark_col[1], dark_col[2], 0.0), 28, hpr=Vec3(0, 0, ang))

            # Readable crater/ridge/fissure field.  Short narrow ellipses avoid angular shapes.
            for i in range(18):
                u = seeded_unit(seed + 1800 + i * 17)
                v = seeded_unit(seed + 2200 + i * 31)
                x = (-0.56 + u * 1.02) * radius
                z = (-0.42 + v * 0.84) * radius
                if (x / (radius * 0.88)) ** 2 + (z / (radius * 0.78)) ** 2 > 1.0:
                    continue
                if i % 3 == 0:
                    rr = radius * (0.026 + 0.035 * seeded_unit(seed + 2600 + i))
                    create_soft_disc_y(layer, "pass13 visible crater", pos + Vec3(x, -radius * 0.270 - i * 0.001, z), rr, rr * 0.82, (0.0, 0.0, 0.0, 0.13), (0.0, 0.0, 0.0, 0.0), 20, hpr=Vec3(0, 0, i * 19))
                    create_soft_disc_y(layer, "pass13 visible crater rim", pos + Vec3(x + rr * 0.06, -radius * 0.269 - i * 0.001, z - rr * 0.04), rr * 1.18, rr * 0.90, (0.96, 0.94, 0.90, 0.035), (0.96, 0.94, 0.90, 0.0), 20, hpr=Vec3(0, 0, i * 19))
                else:
                    if hero_kind == "furnace":
                        col = (1.0, 0.44, 0.12, 0.12)
                    elif hero_kind == "ice":
                        col = (0.78, 0.96, 1.0, 0.12)
                    else:
                        col = (0.64, 0.72, 0.66, 0.075)
                    create_soft_disc_y(layer, "pass13 visible ridge or seam", pos + Vec3(x, -radius * 0.272 - i * 0.001, z), radius * (0.10 + 0.06 * u), radius * (0.012 + 0.010 * v), col, (col[0], col[1], col[2], 0.0), 18, hpr=Vec3(0, 0, -25 + i * 11))

        # A stronger weather layer on top, still soft and natural.
        for i in range(8):
            u = seeded_unit(seed + 4100 + i * 13)
            zoff = (-0.42 + i * 0.12) * radius
            create_soft_disc_y(layer, "pass13 visible cloud front", pos + Vec3(radius * 0.03, -radius * 0.300 - i * 0.002, zoff), radius * (0.74 + 0.15 * u), radius * (0.030 + 0.020 * u), (0.95, 0.98, 1.0, 0.055), (0.95, 0.98, 1.0, 0.0), 38, hpr=Vec3(0, 0, -4 + i * 5 + seed % 11))

    def add_pass13_hero_planet_ultra_detail(self, parent: NodePath, pos: Vec3, radius: float, color: tuple[float, float, float, float], seed: int, hero_kind: str, ringed: bool = False, gas_giant: bool = False, accent: tuple[float, float, float, float] = (0.45, 0.7, 1.0, 1.0)) -> None:
        """Pass 13: push the hero planet further.

        Adds another layer of readable planetary structure: continent/lithosphere breakup,
        crater chains, canyons, cloud formations, ring subdivision, and richer moon/rim cues.
        Everything remains based on soft discs and rounded geometry for stable Panda3D rendering.
        """
        layer = parent.attachNewNode("pass13 hero planet ultra detail")
        layer.setTransparency(TransparencyAttrib.M_alpha)
        layer.setDepthWrite(False)

        # Additional atmospheric depth and anti-flatness shading.
        create_soft_disc_y(layer, "pass13 high atmosphere shell", pos + Vec3(0, -0.32, 0), radius * 1.92, radius * 1.50, (color[0], color[1], color[2], 0.045), (color[0], color[1], color[2], 0.0), 120, hpr=Vec3(0, 0, seed % 19))
        create_soft_disc_y(layer, "pass13 front hemisphere curvature shade", pos + Vec3(-radius * 0.12, -0.27, 0), radius * 0.72, radius * 1.18, (0.0, 0.0, 0.0, 0.10), (0.0, 0.0, 0.0, 0.0), 88, hpr=Vec3(0, 0, -7 + seed % 17))

        # Deep surface structures for non-gas worlds.
        if not (hero_kind in {"ringed", "nebula"} or gas_giant):
            # Long continent/canyon style structures.
            for i in range(10):
                u = seeded_unit(seed + 101 + i * 17)
                v = seeded_unit(seed + 305 + i * 29)
                dx = (-0.46 + u * 0.92) * radius
                dz = (-0.34 + v * 0.68) * radius
                if (dx / (radius * 0.84)) ** 2 + (dz / (radius * 0.76)) ** 2 > 1.0:
                    continue
                ang = -25 + i * 11 + seed % 23
                sx = radius * (0.18 + 0.10 * seeded_unit(seed + 501 + i))
                sz = radius * (0.030 + 0.026 * seeded_unit(seed + 701 + i))
                if hero_kind == "ice":
                    ridge_col = (0.84, 0.98, 1.0, 0.062)
                    shadow_col = (0.54, 0.74, 0.90, 0.022)
                elif hero_kind == "furnace":
                    ridge_col = (0.94, 0.42 + 0.16 * u, 0.14, 0.068)
                    shadow_col = (0.30, 0.09, 0.04, 0.030)
                elif hero_kind == "terrestrial":
                    ridge_col = (0.20 + 0.12 * u, 0.34 + 0.14 * v, 0.16 + 0.06 * u, 0.054)
                    shadow_col = (0.08, 0.12, 0.06, 0.024)
                else:
                    ridge_col = (0.62 + 0.12 * u, 0.66 + 0.10 * v, 0.72, 0.050)
                    shadow_col = (0.10, 0.12, 0.16, 0.022)
                create_soft_disc_y(layer, "pass13 elongated terrain belt", pos + Vec3(dx, -radius * 0.195 - i * 0.002, dz), sx, sz, ridge_col, (ridge_col[0], ridge_col[1], ridge_col[2], 0.0), 30, hpr=Vec3(0, 0, ang))
                create_soft_disc_y(layer, "pass13 elongated terrain shadow", pos + Vec3(dx - sx * 0.10, -radius * 0.198 - i * 0.002, dz + sz * 0.08), sx * 0.80, sz * 0.70, shadow_col, (shadow_col[0], shadow_col[1], shadow_col[2], 0.0), 24, hpr=Vec3(0, 0, ang))

            # Dense local crater/impact and depression field.
            for i in range(18):
                u = seeded_unit(seed + 901 + i * 37)
                v = seeded_unit(seed + 1401 + i * 41)
                dx = (-0.55 + u * 0.98) * radius
                dz = (-0.40 + v * 0.80) * radius
                if (dx / (radius * 0.86)) ** 2 + (dz / (radius * 0.76)) ** 2 > 1.0:
                    continue
                rr = radius * (0.018 + 0.040 * seeded_unit(seed + 1801 + i * 11))
                crater_alpha = 0.052 if hero_kind != "terrestrial" else 0.040
                create_soft_disc_y(layer, "pass13 crater depression", pos + Vec3(dx, -radius * 0.205 - i * 0.001, dz), rr, rr * (0.82 + 0.28 * v), (0.0, 0.0, 0.0, crater_alpha), (0.0, 0.0, 0.0, 0.0), 18, hpr=Vec3(0, 0, i * 13 + seed % 19))
                rim_col = (0.94, 0.94, 0.92, 0.018) if hero_kind == "ice" else (0.82, 0.82, 0.80, 0.012)
                create_soft_disc_y(layer, "pass13 crater bright rim", pos + Vec3(dx + rr * 0.04, -radius * 0.204 - i * 0.001, dz - rr * 0.03), rr * 1.18, rr * 0.94, rim_col, (rim_col[0], rim_col[1], rim_col[2], 0.0), 18, hpr=Vec3(0, 0, i * 13 + seed % 19))

            # Type-specific feature pass.
            if hero_kind == "ice":
                for i in range(8):
                    u = seeded_unit(seed + 2201 + i * 23)
                    create_soft_disc_y(layer, "pass13 ice fissure glow", pos + Vec3(radius * (-0.26 + 0.08 * i), -radius * 0.212 - i * 0.001, radius * (-0.28 + 0.56 * u)), radius * (0.15 + 0.06 * u), radius * 0.016, (0.76, 0.96, 1.0, 0.058), (0.76, 0.96, 1.0, 0.0), 18, hpr=Vec3(0, 0, 14 + i * 12))
            elif hero_kind == "furnace":
                for i in range(9):
                    u = seeded_unit(seed + 2501 + i * 17)
                    create_soft_disc_y(layer, "pass13 lava seam", pos + Vec3(radius * (-0.28 + 0.08 * i), -radius * 0.214 - i * 0.001, radius * (-0.24 + 0.48 * u)), radius * (0.12 + 0.08 * u), radius * 0.018, (1.0, 0.44 + 0.18 * u, 0.12, 0.070), (1.0, 0.20, 0.05, 0.0), 18, hpr=Vec3(0, 0, -18 + i * 10))
            elif hero_kind == "terrestrial":
                for i in range(6):
                    u = seeded_unit(seed + 2801 + i * 19)
                    create_soft_disc_y(layer, "pass13 ocean shelf or vegetation band", pos + Vec3(radius * (-0.18 + 0.10 * i), -radius * 0.210 - i * 0.001, radius * (-0.22 + 0.44 * u)), radius * (0.16 + 0.08 * u), radius * 0.040, (0.22, 0.48 + 0.14 * u, 0.26, 0.040), (0.22, 0.48, 0.26, 0.0), 20, hpr=Vec3(0, 0, 8 + i * 13))

        else:
            # Gas / ringed world micro-detail: extra belts, eddies, and turbulence streaks.
            for i in range(14):
                u = seeded_unit(seed + 3101 + i * 13)
                zoff = (-0.52 + i * 0.080) * radius
                belt_col = (min(1.0, color[0] * (0.82 + 0.18 * u) + 0.08), min(1.0, color[1] * (0.78 + 0.18 * (1.0-u)) + 0.08), min(1.0, color[2] * (0.80 + 0.16 * u) + 0.08), 0.050)
                create_soft_disc_y(layer, "pass13 giant micro belt", pos + Vec3(radius * 0.02, -radius * 0.196 - i * 0.003, zoff), radius * (0.98 + 0.08 * u), radius * (0.024 + 0.018 * u), belt_col, (belt_col[0], belt_col[1], belt_col[2], 0.0), 28, hpr=Vec3(0, 0, -5 + i * 2 + seed % 13))
            for i in range(8):
                u = seeded_unit(seed + 3501 + i * 29)
                eddy_pos = pos + Vec3(radius * (-0.20 + 0.40 * u), -radius * 0.205 - i * 0.002, radius * (-0.30 + 0.60 * seeded_unit(seed + 3701 + i)))
                create_soft_disc_y(layer, "pass13 giant eddy", eddy_pos, radius * (0.08 + 0.05 * u), radius * (0.030 + 0.020 * u), (1.0, 0.92, 0.84, 0.032), (1.0, 0.92, 0.84, 0.0), 18, hpr=Vec3(0, 0, i * 27))

        # Denser cloud formations for all worlds.
        for i in range(12):
            u = seeded_unit(seed + 4001 + i * 11)
            v = seeded_unit(seed + 4201 + i * 13)
            dx = (-0.42 + u * 0.84) * radius
            dz = (-0.30 + v * 0.60) * radius
            if (dx / (radius * 0.88)) ** 2 + (dz / (radius * 0.78)) ** 2 > 1.0:
                continue
            sx = radius * (0.10 + 0.12 * seeded_unit(seed + 4401 + i))
            sz = radius * (0.030 + 0.040 * seeded_unit(seed + 4601 + i))
            create_soft_disc_y(layer, "pass13 cloud cluster", pos + Vec3(dx, -radius * 0.228 - i * 0.001, dz), sx, sz, (0.94, 0.97, 1.0, 0.035), (0.94, 0.97, 1.0, 0.0), 20, hpr=Vec3(0, 0, i * 19 + seed % 17))
            create_soft_disc_y(layer, "pass13 cloud cluster shadow", pos + Vec3(dx - sx * 0.05, -radius * 0.223 - i * 0.001, dz + sz * 0.03), sx * 0.94, sz * 0.78, (0.0, 0.0, 0.0, 0.012), (0.0, 0.0, 0.0, 0.0), 20, hpr=Vec3(0, 0, i * 19 + seed % 17))

        # Refine ring read if present.
        if ringed:
            ring_col = (min(1.0, color[0] * 0.90 + 0.12), min(1.0, color[1] * 0.90 + 0.12), min(1.0, color[2] * 0.90 + 0.12), 0.070)
            for k, mul in enumerate([4.25, 4.55, 4.92]):
                create_annular_arc_y(layer, "pass13 subdivided hero ring lane", pos + Vec3(0, -0.42 - k * 0.016, 0), radius * mul, radius * (mul + 0.030), -54 + k * 6, 334 - k * 9, 148, ring_col, hpr=Vec3(0, 0, -18 + seed % 25), emission=(ring_col[0] * 0.04, ring_col[1] * 0.04, ring_col[2] * 0.04, 1))

        # Nearby moon accent glows for better readability around the hero world.
        for i in range(4):
            u = seeded_unit(seed + 5001 + i * 17)
            rr = radius * (1.85 + i * 0.42)
            ang = u * math.tau + i * 0.52
            mpos = Vec3(pos.x + math.cos(ang) * rr, pos.y - 0.65 + i * 0.55, pos.z + math.sin(ang) * rr * 0.42)
            create_soft_disc_y(layer, "pass13 moon accent haze", mpos + Vec3(0.0, -0.08, 0.0), radius * 0.11, radius * 0.08, (accent[0], accent[1], accent[2], 0.028), (accent[0], accent[1], accent[2], 0.0), 14, hpr=Vec3(0, 0, i * 23))

    def prepare_system_reward(self, kind: str, seed: int) -> None:
        """Assign a compact reward profile to the next warped system."""
        base_values = {
            "ice_moon": (54, "ICE"),
            "ring_giant": (72, "GIANT"),
            "colony_wreck": (86, "WRECK"),
            "nebula_gate": (98, "RARE"),
            "comet_shoal": (64, "COMET"),
            "red_dwarf": (92, "HOT"),
            "station": (0, "ANCHOR"),
        }
        base, rarity = base_values.get(kind, (60, "UNK"))
        variance = int(seeded_unit(seed + 6101) * 32)
        self.current_system_value = base + variance
        self.current_system_rarity = rarity
        self.current_sample_value = max(10, self.current_system_value // max(1, self.salvage_required + 1))
        self.last_reward = 0

    def generate_research_tasks(self, kind: str, hero_kind: str, seed: int) -> None:
        """Create randomized interior research objectives for the current planet/system."""
        station_pool = {
            "ice": [
                ("CRYO-VOLATILE SURVEY", "LAB", "Map ice chemistry in polar shadow"),
                ("SUBSURFACE OCEAN LISTEN", "OBS", "Track faint tidal glow under crust"),
                ("FROST DUST SPECTRUM", "DATA", "Catalog reflective mineral grain bands"),
            ],
            "furnace": [
                ("THERMAL BLOOM CYCLE", "LAB", "Measure lava-night radiance curves"),
                ("MAGMA STRESS MAP", "NAV", "Solve orbit against thermal plume drag"),
                ("RED DWARF FLARE LOG", "SYS", "Tune shields against stellar bursts"),
            ],
            "ringed": [
                ("RING PARTICLE COUNT", "OBS", "Count ice-rock lanes and dark gaps"),
                ("MOONLET RESONANCE", "NAV", "Solve shepherd moon cadence"),
                ("AMMONIA STORM SPECTRA", "LAB", "Sample giant-world band chemistry"),
            ],
            "nebula": [
                ("ION VEIL TOMOGRAPHY", "LAB", "Layer violet gas sheets by density"),
                ("ANOMALY TRACE FIT", "DATA", "Compare lens scars against catalog"),
                ("NEBULA DRIFT SOLVER", "NAV", "Predict charged dust flow"),
            ],
            "terrestrial": [
                ("BIOSIGNATURE FILTER", "LAB", "Search greenline false positives"),
                ("CLOUD SHADOW TRACK", "OBS", "Track weather bands across limb"),
                ("COLONY DEBRIS INDEX", "DATA", "Classify artificial orbit fragments"),
            ],
            "cold-rock": [
                ("CRATER AGE MODEL", "DATA", "Compare impact density and ejecta fields"),
                ("MAGNETIC ANOMALY GRID", "LAB", "Read metallic crust pockets"),
                ("COMET DUST FLUX", "OBS", "Track high-speed micrometeor haze"),
            ],
        }
        generic = [
            ("GRAVITY FIELD FIT", "NAV", "Refine orbital mass estimate"),
            ("ALBEDO / LIMB STUDY", "OBS", "Compare day-night reflection edge"),
            ("SYSTEM STABILITY AUDIT", "SYS", "Rebalance observatory power load"),
            ("ARCHIVE CROSSMATCH", "DATA", "Compare body against prior discoveries"),
        ]
        candidates = list(station_pool.get(hero_kind, station_pool.get(kind, []))) + generic
        chosen: list[ResearchTask] = []
        used: set[str] = set()
        for i in range(4):
            pick = int(seeded_unit(seed + 7700 + i * 101) * len(candidates)) % len(candidates)
            for step in range(len(candidates)):
                title, station, note = candidates[(pick + step) % len(candidates)]
                if title not in used:
                    used.add(title)
                    reward = 18 + int(seeded_unit(seed + 8100 + i * 43) * 28) + self.scanner_upgrade_level * 4
                    seconds = 1.10 + seeded_unit(seed + 8300 + i * 37) * 0.70
                    chosen.append(ResearchTask(title, station, reward, seconds, note))
                    break
        self.research_tasks = chosen
        self.research_task_index = 0
        self.update_research_panels()

    def current_research_task(self) -> ResearchTask | None:
        if not self.research_tasks:
            return None
        self.research_task_index = max(0, min(self.research_task_index, len(self.research_tasks) - 1))
        return self.research_tasks[self.research_task_index]

    def cycle_research_task(self) -> None:
        if not self.research_tasks:
            self.set_loop_feedback("NO RESEARCH QUEUE", 1.5)
            return
        for _ in range(len(self.research_tasks)):
            self.research_task_index = (self.research_task_index + 1) % len(self.research_tasks)
            if not self.research_tasks[self.research_task_index].complete:
                break
        task = self.current_research_task()
        if task:
            self.set_loop_feedback(f"TASK {task.station}", 1.5)
        self.update_research_panels()
        self.update_objective_text()

    def complete_research_task(self, task: ResearchTask) -> None:
        if task.complete:
            return
        task.complete = True
        task.progress = task.seconds_required
        self.research_points += task.reward
        self.credits += max(6, task.reward // 2)
        self.completed_research_count += 1
        self.last_reward = task.reward
        self.set_loop_feedback(f"{task.station} DATA +{task.reward}", 2.3)
        for i, other in enumerate(self.research_tasks):
            if not other.complete:
                self.research_task_index = i
                break
        self.update_research_panels()
        self.update_objective_text()

    def update_research_panels(self) -> None:
        task = self.current_research_task()
        if hasattr(self, "observatory_station_lines") and self.observatory_station_lines:
            self.update_observatory_station_panels()
        lines = getattr(self, "robot_task_lines", [])
        if lines:
            if task is None:
                readout = ["ROBOTS: STANDBY", "QUEUE: ANCHOR MODE", "T: CYCLE  RMB: STUDY"]
            else:
                pct = int(100 * min(1.0, task.progress / max(0.01, task.seconds_required)))
                status = "DONE" if task.complete else f"{pct}%"
                readout = [
                    f"BOT TASK: {task.station} / {status}",
                    task.title[:32],
                    f"{task.note[:30]}  +{task.reward}D",
                ]
            for node, line in zip(lines, readout):
                node.node().setText(line)
        for idx, lamp in enumerate(getattr(self, "robot_status_lamps", [])):
            if lamp.isEmpty():
                continue
            is_active = bool(task and not task.complete and idx == self.research_task_index % max(1, len(getattr(self, "robot_status_lamps", []))))
            if is_active:
                lamp.setColor(0.0, 0.78, 1.0, 1.0)
                lamp.setColorScale(1.0, 1.0, 1.0, 0.95)
            else:
                lamp.setColor(0.04, 0.16, 0.24, 0.72)
                lamp.setColorScale(1.0, 1.0, 1.0, 0.55)

    def scanner_range_multiplier(self) -> float:
        return 1.0 + self.scanner_upgrade_level * 0.32

    def scanner_upgrade_cost(self) -> int:
        return 75 + self.scanner_upgrade_level * 55

    def buy_scanner_upgrade(self) -> None:
        if self.mode != "interior":
            self.set_loop_feedback("UPGRADE IN CABIN", 1.8)
            return
        if self.scanner_upgrade_level >= self.scanner_upgrade_max:
            self.set_loop_feedback("SCANNER MAX", 2.0)
            self.update_cabin_console()
            return
        cost = self.scanner_upgrade_cost()
        if self.credits < cost:
            self.set_loop_feedback(f"NEED {cost} CR", 2.0)
            self.update_cabin_console()
            return
        self.credits -= cost
        self.scanner_upgrade_level += 1
        self.set_loop_feedback(f"SCAN +{self.scanner_upgrade_level}", 2.4)
        self.update_objective_text()
        self.update_cabin_console()

    def cycle_observatory_station(self) -> None:
        if getattr(self, "operation_active", False):
            return
        if not getattr(self, "observatory_stations", None):
            return
        self.observatory_station_index = (self.observatory_station_index + 1) % len(self.observatory_stations)
        code = self.observatory_stations[self.observatory_station_index][0]
        self.set_loop_feedback(f"STATION {code}", 1.4)
        self.update_observatory_station_panels()
        self.update_saturn_operations_map()
        self.update_objective_text()

    def select_observatory_station(self, index: int) -> None:
        if getattr(self, "operation_active", False):
            return
        if not getattr(self, "observatory_stations", None):
            return
        self.observatory_station_index = max(0, min(index, len(self.observatory_stations) - 1))
        code = self.observatory_stations[self.observatory_station_index][0]
        self.set_loop_feedback(f"STATION {code}", 1.2)
        self.update_observatory_station_panels()
        self.update_saturn_operations_map()
        self.update_objective_text()

    def update_observatory_station_panels(self) -> None:
        stations = getattr(self, "observatory_stations", None)
        lines = getattr(self, "observatory_station_lines", None)
        if not stations or not lines:
            return
        idx = max(0, min(getattr(self, "observatory_station_index", 0), len(stations) - 1))
        code, title, purpose = stations[idx]
        target = OPERATION_TARGETS.get(code, {})
        if target:
            readout = [
                f"STARFALL OPS // {title}",
                f"{target.get('status', '')}: {target.get('mission', purpose)[:42]}",
                f"RES: {target.get('resources', '')[:42]}",
                "LMB MAP / TAB NEXT / M MAP / RMB STUDY",
            ]
        else:
            if self.current_chunk_name == "Anchor Drydock":
                target_text = "ANCHOR / BLACK-HOLE LENS"
            else:
                target_text = f"{self.current_system_rarity} / {self.current_chunk_name[:18]}"
            task = self.current_research_task() if hasattr(self, "current_research_task") else None
            task_line = "TASK: QUEUE CLEAR" if not task else f"{task.station}: {task.title[:22]}"
            readout = [
                f"{code} // {title}",
                task_line,
                f"TARGET: {target_text}",
                f"DATA {self.research_points}D / {self.credits}CR  SCAN {self.scanner_upgrade_level}/{self.scanner_upgrade_max}",
            ]
        for node, line in zip(lines, readout):
            node.node().setText(line)
        for lamp_index, lamp in enumerate(getattr(self, "observatory_station_lamps", [])):
            if lamp.isEmpty():
                continue
            if lamp_index == idx:
                lamp.setColor(0.0, 0.78, 1.0, 1.0)
                lamp.setColorScale(1.0, 1.0, 1.0, 1.0)
            else:
                lamp.setColor(0.04, 0.16, 0.24, 0.72)
                lamp.setColorScale(1.0, 1.0, 1.0, 0.55)

    def update_cabin_console(self) -> None:
        lines = getattr(self, "cabin_console_lines", None)
        if not lines:
            return
        if self.current_chunk_name == "Anchor Drydock":
            sys_line = "SYSTEM: ANCHOR DRYDOCK"
            val_line = "TARGET: LENS ANOMALY"
        else:
            sys_line = f"SYSTEM: {self.current_system_rarity} / {self.current_chunk_name[:16]}"
            val_line = f"VALUE: {self.current_system_value} CR  SAMPLE: {self.current_sample_value} CR"
        upgrade_state = "MAX" if self.scanner_upgrade_level >= self.scanner_upgrade_max else f"U KEY: SCAN UPG {self.scanner_upgrade_cost()} CR"
        task = self.current_research_task() if hasattr(self, "current_research_task") else None
        task_state = "NO PLANET TASKS" if not task else f"TASK: {task.station} {task.title[:18]}"
        console_lines = [
            sys_line,
            task_state,
            f"DATA: {self.research_points}D  BANK: {self.credits} CR",
            f"SCAN: LV {self.scanner_upgrade_level}/{self.scanner_upgrade_max}  RANGE x{self.scanner_range_multiplier():.1f}",
            upgrade_state,
        ]
        for node, line in zip(lines, console_lines):
            node.node().setText(line)

    def reset_gameplay_loop(self) -> None:
        self.gameplay_targets.clear()
        self.active_gameplay_target = None
        self.salvage_collected = 0
        self.planet_scanned = False
        self.system_loop_complete = False
        self.loop_feedback = ""
        self.loop_feedback_timer = 0.0
        self.perf_detail = os.environ.get("STARFALL_DETAIL", "fast").strip().lower()
        self._lensing_accum = 0.0
        self._gameplay_accum = 0.0
        self._cosmic_anim_accum = 0.0
        self._cosmic_anim_phase = 0
        if hasattr(self, "objective_text"):
            self.update_objective_text()
        self.update_cabin_console()
        if hasattr(self, "update_research_panels"):
            self.update_research_panels()

    def spawn_pass14_gameplay_loop(self, parent: NodePath, hero_pos: Vec3, hero_radius: float, color: tuple[float, float, float, float], seed: int, hero_kind: str, accent: tuple[float, float, float, float]) -> None:
        """Create a simple playable loop around each warped solar system."""
        scan_root = parent.attachNewNode("pass14 hero planet scan target")
        scan_root.setPos(hero_pos)
        scan_root.setTransparency(TransparencyAttrib.M_alpha)
        scan_root.setDepthWrite(False)
        create_soft_disc_y(scan_root, "pass14 planet scan shimmer", Vec3(0, -hero_radius * 0.235, 0), hero_radius * 1.08, hero_radius * 0.18, (accent[0], accent[1], accent[2], 0.080), (accent[0], accent[1], accent[2], 0.0), 42, hpr=Vec3(0, 0, seed % 37))
        scan_radius = max(80.0, hero_radius * 8.5) * self.scanner_range_multiplier()
        self.gameplay_targets.append(GameplayTarget("Hero planet surface scan", "scan", scan_root, scan_radius, value=0))

        names = ["Magnetosphere sample", "Derelict probe core", "Ice-dust canister", "Orbital relay data", "Micrometeor survey pod"]
        for i in range(4):
            u = seeded_unit(seed + i * 47)
            v = seeded_unit(seed + 200 + i * 53)
            a = (0.08 + i * 0.17 + u * 0.10) * math.tau
            rr = hero_radius * (2.25 + i * 0.42 + v * 0.30)
            yoff = -3.0 + i * 1.55 + (seeded_unit(seed + 600 + i) - 0.5) * 1.8
            pos_i = Vec3(hero_pos.x + math.cos(a) * rr, hero_pos.y + yoff, hero_pos.z + math.sin(a) * rr * 0.38)
            target = parent.attachNewNode(f"pass14 gameplay salvage target {names[i]}")
            target.setPos(pos_i)
            target.setHpr(math.degrees(a) + 90, -3 + i * 2, 0)
            target.setTransparency(TransparencyAttrib.M_alpha)
            target.setDepthWrite(False)
            core_col = (0.18 + accent[0] * 0.28, 0.22 + accent[1] * 0.30, 0.30 + accent[2] * 0.30, 1)
            create_cylinder_y(target, "pass14 rounded data canister", Vec3(0, 0, 0), 0.22, 0.92, 18, core_col, hpr=Vec3(0, 90, 0), emission=(0.018, 0.030, 0.045, 1))
            create_uv_sphere(target, "pass14 canister glass nose", Vec3(-0.54, 0, 0), 0.20, 8, 16, (accent[0], accent[1], accent[2], 1), emission=(accent[0]*0.06, accent[1]*0.10, accent[2]*0.16, 1))
            create_soft_disc_y(target, "pass14 sample acquisition halo", Vec3(0, -0.07, 0), 0.72, 0.24, (accent[0], accent[1], accent[2], 0.135), (accent[0], accent[1], accent[2], 0.0), 36, hpr=Vec3(0, 0, i * 23))
            create_soft_disc_y(target, "pass14 sample locator glow", Vec3(-0.55, -0.11, 0), 0.34, 0.21, (0.78, 0.95, 1.0, 0.165), (0.40, 0.70, 1.0, 0.0), 26, hpr=Vec3(0, 0, i * 17))
            self.organic_cosmic_roots.append(target)
            sample_value = self.current_sample_value + int(seeded_unit(seed + 940 + i * 37) * 10)
            self.gameplay_targets.append(GameplayTarget(names[i], "sample", target, 5.4, value=sample_value))
        self.update_objective_text()

    def set_hud_bar(self, key: str, value: float) -> None:
        if not hasattr(self, "hud_bars") or key not in self.hud_bars:
            return
        value = max(0.02, min(1.0, float(value)))
        self.hud_bars[key].setScale(value, 1, 1)

    def set_context_prompt(self, text: str, fg: tuple[float, float, float, float] = (0.66, 0.92, 1.0, 0.82)) -> None:
        if hasattr(self, "lens_text"):
            self.lens_text.setText(text)
            self.lens_text.setFg(fg)

    def set_reticle_color(self, color: tuple[float, float, float, float]) -> None:
        if hasattr(self, "crosshair"):
            self.crosshair.setFg(color)
        for tick in getattr(self, "reticle_cards", []):
            tick.setColor(*color)

    def update_objective_text(self) -> None:
        if not hasattr(self, "objective_text"):
            return
        if self.mode == "interior":
            station_code = self.observatory_stations[self.observatory_station_index][0] if getattr(self, "observatory_stations", None) else "OBS"
            self.objective_header_text.setText("OPS MAP")
            self.objective_text.setText(station_code)
            task = self.current_research_task() if hasattr(self, "current_research_task") else None
            tprog = 0 if not task else int(100 * min(1.0, task.progress / max(0.01, task.seconds_required)))
            target = OPERATION_TARGETS.get(station_code, {})
            self.scan_text.setText(str(target.get("status", "OPS"))[:8])
            self.salvage_text.setText("LMB GO")
            self.gateway_text.setText(f"CR {self.credits}")
            self.systems_text.setText("TAB MAP")
            self.update_cabin_console()
            self.update_observatory_station_panels()
            self.set_hud_bar("scan", 1.0)
            self.set_hud_bar("salvage", 0.14)
            self.set_hud_bar("gateway", 0.55)
            return
        if self.current_chunk_name == "Anchor Drydock":
            self.objective_header_text.setText("ANCHOR")
            self.objective_text.setText("LENS")
            self.scan_text.setText(f"CR {self.credits}")
            self.salvage_text.setText("C --")
            self.gateway_text.setText("G ON")
            self.systems_text.setText(f"CLR {self.systems_completed}")
            self.set_hud_bar("scan", 0.04)
            self.set_hud_bar("salvage", 0.04)
            self.set_hud_bar("gateway", 1.0)
            return

        scan_prog = 1.0 if self.planet_scanned else (0.45 if self.scan_held else 0.18)
        salvage_prog = min(1.0, self.salvage_collected / max(1, self.salvage_required))
        gate_prog = 1.0 if self.system_loop_complete else min(0.96, scan_prog * 0.35 + salvage_prog * 0.65)

        scan_state = "OK" if self.planet_scanned else "RMB"
        salvage_state = f"{self.salvage_collected}/{self.salvage_required}"
        gate_state = "RDY" if self.system_loop_complete else "LCK"

        self.objective_header_text.setText(self.current_system_rarity[:6])
        self.objective_text.setText(f"CR {self.credits}")
        self.scan_text.setText(f"S {scan_state}")
        self.salvage_text.setText(f"C {salvage_state}")
        self.gateway_text.setText(f"G {gate_state}")
        self.systems_text.setText(f"CLR {self.systems_completed}")
        self.set_hud_bar("scan", scan_prog)
        self.set_hud_bar("salvage", salvage_prog)
        self.set_hud_bar("gateway", gate_prog)

    def set_loop_feedback(self, text: str, seconds: float = 2.4) -> None:
        self.loop_feedback = text
        self.loop_feedback_timer = seconds
        self.set_context_prompt(text)
        self.update_cabin_console()

    def check_system_loop_complete(self) -> None:
        if not self.system_loop_complete and self.planet_scanned and self.salvage_collected >= self.salvage_required:
            self.system_loop_complete = True
            self.systems_completed += 1
            bonus = max(20, int(self.current_system_value * 0.45))
            self.credits += bonus
            self.last_reward = bonus
            self.set_loop_feedback(f"GATE READY +{bonus} CR", 3.3)
        self.update_objective_text()

    def update_gameplay_targets(self, dt: float) -> None:
        if self.mode != "flight" or self.warping:
            return
        if self.loop_feedback_timer > 0.0:
            self.loop_feedback_timer = max(0.0, self.loop_feedback_timer - dt)
        closest: tuple[float, GameplayTarget] | None = None
        ship_pos = self.ship.getPos(self.render)
        for idx, target in enumerate(self.gameplay_targets):
            if target.collected:
                continue
            pulse = 1.0 + math.sin(task_time() * (2.2 + idx * 0.15) + idx) * 0.08
            if target.kind == "sample":
                target.root.setScale(pulse)
            p_world = target.root.getPos(self.render)
            dist_world = (p_world - ship_pos).length()
            p_cam = self.camera.getRelativePoint(self.render, p_world)
            screen = Point2()
            if self.camLens.project(p_cam, screen):
                screen_dist = math.sqrt(screen.x * screen.x + screen.y * screen.y)
                max_screen = 0.34 if target.kind == "scan" else 0.22
                max_range = target.radius if target.kind == "scan" else max(target.radius, 5.6)
                if screen_dist < max_screen and dist_world <= max_range:
                    score = screen_dist + max(0.0, dist_world - 3.0) * 0.006
                    if closest is None or score < closest[0]:
                        closest = (score, target)
        self.active_gameplay_target = closest[1] if closest else None
        if self.active_gameplay_target:
            active_dist = (self.active_gameplay_target.root.getPos(self.render) - ship_pos).length()
            if self.active_gameplay_target.kind == "scan":
                if self.scan_held and not self.planet_scanned:
                    self.planet_scanned = True
                    self.set_loop_feedback(f"SCAN OK: {self.current_system_rarity} {self.current_system_value}CR", 2.8)
                    self.check_system_loop_complete()
                elif self.loop_feedback_timer <= 0.0:
                    self.set_context_prompt(f"RMB SCAN {int(active_dist)}m", (0.58, 1.0, 0.88, 0.88))
                    self.set_reticle_color((0.58, 1.0, 0.88, 0.70))
            elif self.active_gameplay_target.kind == "sample" and self.loop_feedback_timer <= 0.0:
                self.set_context_prompt(f"LMB SAMPLE {int(active_dist)}m", (0.58, 1.0, 0.72, 0.88))
                self.set_reticle_color((0.58, 1.0, 0.72, 0.72))
        elif self.loop_feedback_timer <= 0.0 and self.current_chunk_name != "Anchor Drydock":
            if self.system_loop_complete:
                self.set_context_prompt("TURN GATE", (1.0, 0.76, 0.36, 0.86))
            elif not self.planet_scanned:
                self.set_context_prompt("FIND PLANET", (0.60, 0.92, 1.0, 0.78))
            else:
                self.set_context_prompt("FIND SAMPLE", (0.58, 1.0, 0.72, 0.78))
            self.set_reticle_color((0.48, 0.90, 1.0, 0.46))

    def collect_active_gameplay_target(self) -> bool:
        target = self.active_gameplay_target
        if not target or target.collected or target.kind != "sample":
            return False
        target.collected = True
        target.root.hide()
        target.root.removeNode()
        self.salvage_collected += 1
        self.credits += target.value
        self.last_reward = target.value
        self.set_loop_feedback(f"SAMPLE +{target.value} CR ({self.salvage_collected}/{self.salvage_required})", 2.2)
        self.check_system_loop_complete()
        self.update_cabin_console()
        return True

    def build_pass09_return_black_hole_gateway(self, root: NodePath, seed: int, star_color: tuple[float, float, float, float]) -> None:
        gateway = root.attachNewNode("pass09 rear black-hole return gateway")
        gateway.setPos(0, -42.0, 8.0)
        gateway.setTransparency(TransparencyAttrib.M_alpha)
        gateway.setDepthWrite(False)
        create_uv_sphere(gateway, "rear gateway smooth event horizon", Vec3(0, 0, 0), 1.38, 20, 48, (0.0, 0.0, 0.0, 1), emission=(0, 0, 0, 1)).setLightOff(1)
        create_soft_disc_y(gateway, "rear gateway soft photon halo", Vec3(0, -0.05, 0), 2.35, 1.75, (0.30, 0.56, 1.0, 0.115), (0.0, 0.0, 0.0, 0.0), 96, hpr=Vec3(0, 0, seed % 360))
        create_soft_disc_y(gateway, "rear gateway warm accretion mist", Vec3(0, 0.02, 0), 3.10, 0.72, (star_color[0], star_color[1]*0.72, max(0.05, star_color[2]*0.45), 0.125), (star_color[0], star_color[1]*0.46, star_color[2]*0.25, 0.0), 96, hpr=Vec3(0, 0, -9 + (seed % 33)))
        for i in range(14):
            u = seeded_unit(seed + 8300 + i * 17)
            a = u * math.tau
            r = 1.8 + seeded_unit(seed + 8400 + i * 11) * 2.6
            p = Vec3(math.cos(a) * r, (seeded_unit(seed + 8500 + i) - 0.5) * 0.42, math.sin(a) * r * 0.35)
            col = (0.40 + u * 0.25, 0.60 + u * 0.20, 1.0, 0.060 + u * 0.045)
            mote = create_soft_disc_y(gateway, "rear gateway orbiting natural lens dust", p, 0.12 + u * 0.12, 0.035 + u * 0.025, col, (col[0], col[1], col[2], 0.0), 12, hpr=Vec3(0, 0, math.degrees(a)))
            if i % 9 == 0:
                self.anomaly_fx_nodes.append(mote)
        self.build_pass20_hyperspatial_disc(gateway, seed + 991, radius_scale=0.70, warm_bias=(star_color[0], max(0.30, star_color[1] * 0.85), max(0.12, star_color[2] * 0.55)), cool_bias=(0.34, 0.62, 1.0))
        self.lensing_root = root.attachNewNode("pass09 active rear-gateway target root")
        # Put the actual target on the visible gateway. The player must turn the ship around to lock it.
        self.lens_targets.append(LensTarget("Rear Black-Hole Gateway", "return_blackhole", seed + 9917, (0.56, 0.78, 1.0, 0.90), gateway))

    def update_lensing_targets(self, dt: float) -> None:
        if self.mode != "flight":
            return
        closest: tuple[float, LensTarget] | None = None
        for idx, target in enumerate(self.lens_targets):
            # Lensing images wobble slightly around the anomaly as if their apparent position is being bent.
            t = task_time()
            target.root.setHpr(math.sin(t * 0.6 + idx) * 8.0, 0, math.sin(t * 0.9 + idx) * 18.0)
            target.root.setScale(1.0 + math.sin(t * 1.7 + idx) * 0.035)
            p = self.camera.getRelativePoint(self.render, target.root.getPos(self.render))
            screen = Point2()
            if self.camLens.project(p, screen):
                dist = math.sqrt(screen.x * screen.x + screen.y * screen.y)
                if dist < 0.28 and (closest is None or dist < closest[0]):
                    closest = (dist, target)
        self.hover_target = closest[1] if closest else None
        for target in self.lens_targets:
            if target is self.hover_target:
                target.root.setColorScale(1.45, 1.45, 1.45, 1.0)
            else:
                target.root.setColorScale(0.78, 0.88, 1.0, 0.78)
        if self.loop_feedback_timer > 0.0:
            self.chunk_text.setText(self.current_chunk_name)
            self.update_objective_text()
            return
        if self.hover_target:
            if self.hover_target.kind == "return_blackhole" and not self.system_loop_complete:
                self.set_context_prompt("GATE LOCKED", (1.0, 0.48, 0.36, 0.90))
                self.set_reticle_color((1.0, 0.48, 0.36, 0.70))
            else:
                self.set_context_prompt("LMB WARP", (1.0, 0.76, 0.36, 0.90))
                self.set_reticle_color((1.0, 0.76, 0.36, 0.76))
        elif self.warping and self.pending_warp_target:
            self.set_context_prompt("WARPING", (1.0, 0.76, 0.36, 0.90))
        else:
            if self.celestial_chunk_root and self.current_chunk_name != "Anchor Drydock":
                self.set_context_prompt("SCAN / SAMPLE")
                self.set_reticle_color((0.48, 0.90, 1.0, 0.58))
            else:
                self.set_context_prompt("LMB WARP")
                self.set_reticle_color((0.48, 0.90, 1.0, 0.58))
        self.chunk_text.setText(self.current_chunk_name)
        self.update_objective_text()

    def handle_primary_click(self) -> None:
        if getattr(self, "operation_active", False):
            return
        if getattr(self, "pause_menu_open", False):
            return
        if getattr(self, "operation_map_open", False):
            return
        if self.mode == "interior":
            self.show_saturn_operations_map()
            return
        if self.mode == "flight" and self.hover_target and not self.warping:
            if self.hover_target.kind == "return_blackhole" and not self.system_loop_complete:
                self.set_loop_feedback("GATE LOCKED", 2.8)
                self.pulse_engine_flare()
                return
            self.trigger_chunk_warp(self.hover_target)
            return
        if self.mode == "flight" and self.collect_active_gameplay_target():
            self.pulse_engine_flare()
            return
        self.pulse_engine_flare()

    def trigger_chunk_warp(self, target: LensTarget) -> None:
        self.warping = True
        self.warp_timer = 0.0
        self.warp_swap_done = False
        self.pending_warp_target = target
        self.ship_velocity *= 0.22
        if target.kind == "return_blackhole":
            self.set_context_prompt("GATE WARP", (1.0, 0.76, 0.36, 0.90))
        else:
            self.set_context_prompt("WARP LOCK", (1.0, 0.76, 0.36, 0.90))
        self.warp_overlay.show()

    def complete_chunk_warp(self) -> None:
        if not self.pending_warp_target:
            return
        target = self.pending_warp_target
        next_seed = target.seed + self.current_chunk_seed + 193
        if target.kind == "return_blackhole":
            # The rear black hole is the exit from the current explored system.
            # It does not send the ship back to a menu; it folds in another random solar system.
            destination_kinds = ["ice_moon", "ring_giant", "colony_wreck", "nebula_gate", "comet_shoal", "red_dwarf"]
            idx = int(seeded_unit(next_seed + 77) * len(destination_kinds)) % len(destination_kinds)
            next_kind = destination_kinds[idx]
            next_name = self.make_pass09_system_name(next_kind, next_seed)
            self.build_celestial_chunk(next_name, next_kind, next_seed)
        else:
            self.build_celestial_chunk(self.make_pass09_system_name(target.kind, next_seed), target.kind, next_seed)
        self.ship.setPos(0, -2.0, 2.5)
        self.ship_velocity = Vec3(0, 0, 0)
        self.warp_swap_done = True

    def update_warp_transition(self, dt: float) -> None:
        if not self.warping:
            self.warp_overlay.hide()
            return
        self.warp_timer += dt
        t = self.warp_timer / self.warp_duration
        if self.anomaly_root:
            ring_scale = 1.0 + math.sin(min(t, 1.0) * math.pi) * 0.28
            self.anomaly_root.setScale(ring_scale)
        if not self.warp_swap_done and self.warp_timer >= self.warp_duration * 0.48:
            self.complete_chunk_warp()
        alpha = math.sin(min(max(t, 0.0), 1.0) * math.pi) * 0.70
        self.warp_overlay.setColor(0.04, 0.32, 0.95, alpha)
        if self.warp_timer >= self.warp_duration:
            self.warping = False
            self.pending_warp_target = None
            if self.anomaly_root:
                self.anomaly_root.setScale(1)
            self.warp_overlay.hide()

    def build_ship_exterior(self, parent: NodePath) -> NodePath:
        """Reference-informed salvage ship exterior, refined for silhouette and presentation.

        Visual references used for this pass:
        - Cupola-like observation glazing: seven-window command/view module idea.
        - Crew/service-module logic: pressure cabin forward, service/engine bus aft.
        - Real spacecraft readability: docking ring, RCS pods, radiator/solar wings, antenna, protected engine nozzles.
        """
        ship = parent.attachNewNode("Player Ship - Exterior")
        hull = (0.30, 0.34, 0.43, 1)
        hull_emit = (0.025, 0.035, 0.055, 1)
        dark = (0.075, 0.085, 0.12, 1)
        panel = (0.42, 0.46, 0.56, 1)
        panel_dark = (0.17, 0.19, 0.25, 1)
        blue = (0.0, 0.78, 1.0, 1)
        amber = (1.0, 0.55, 0.08, 1)
        red = (1.0, 0.12, 0.045, 1)
        glass = (0.075, 0.72, 0.96, 0.48)
        solar = (0.035, 0.10, 0.24, 1)

        # Pressurized crew module: faceted cylinder rather than a plain block.
        create_cylinder_y(ship, "faceted crew pressure hull", Vec3(0, -2.0, 0.08), 1.33, 5.2, 12, hull, emission=hull_emit)
        create_cylinder_y(ship, "dark lower heat-shield belly", Vec3(0, -1.82, -0.26), 1.18, 5.0, 12, dark, emission=(0.005, 0.008, 0.018, 1))
        create_box(ship, "armored dorsal spine", Vec3(0, -1.25, 1.23), Vec3(0.42, 4.65, 0.38), panel_dark, emission=(0.015, 0.02, 0.04, 1))
        dorsal_strip = create_box(ship, "dorsal navigation strip", Vec3(0, -1.25, 1.52), Vec3(0.08, 4.1, 0.07), blue, emission=(0.0, 0.34, 0.82, 1))
        self.ship_accent_nodes.append(dorsal_strip)
        for y in (-3.75, -2.85, -1.95, -1.05, -0.15, 0.75):
            create_box(ship, "individual hull plate seam left", Vec3(-1.02, y, 0.96), Vec3(0.045, 0.45, 0.04), (0.0, 0.35, 0.72, 1), hpr=Vec3(0, 0, -9), emission=(0.0, 0.10, 0.26, 1))
            create_box(ship, "individual hull plate seam right", Vec3(1.02, y, 0.96), Vec3(0.045, 0.45, 0.04), (0.0, 0.35, 0.72, 1), hpr=Vec3(0, 0, 9), emission=(0.0, 0.10, 0.26, 1))
        # Pass 03 silhouette layer: angled armor cheeks, belly keel, and a raised observation brow.
        create_box(ship, "sloped cockpit brow armor", Vec3(0, -4.32, 1.05), Vec3(1.9, 1.15, 0.22), panel_dark, hpr=Vec3(0, 13, 0), emission=(0.014, 0.018, 0.034, 1))
        create_box(ship, "ventral salvage keel", Vec3(0, -0.20, -1.34), Vec3(0.34, 4.8, 0.78), (0.10, 0.12, 0.16, 1), hpr=Vec3(0, -3, 0), emission=(0.008, 0.010, 0.020, 1))
        create_box(ship, "keel scanner strip", Vec3(0, -1.15, -1.78), Vec3(0.11, 2.9, 0.08), (0.0, 0.58, 1.0, 1), emission=(0.0, 0.24, 0.65, 1))
        for side in (-1, 1):
            create_trapezoid_prism(ship, "swept forward cheek armor", Vec3(side * 0.70, -2.35, 0.36), 2.35, 0.55, 0.96, 0.16, (0.22, 0.25, 0.33, 1), side=side, hpr=Vec3(0, 0, side * 2), emission=(0.012, 0.016, 0.030, 1))
            create_box(ship, "cheek armor cyan edge", Vec3(side * 1.38, -3.08, 0.58), Vec3(0.06, 1.95, 0.08), blue, hpr=Vec3(0, 0, side * -10), emission=(0.0, 0.22, 0.58, 1))

        # Nose command/cupola window cluster. It is exaggerated for gameplay readability.
        create_cylinder_y(ship, "forward docking collar", Vec3(0, -4.98, 0.08), 1.06, 0.32, 18, panel, emission=(0.02, 0.025, 0.04, 1))
        create_cylinder_y(ship, "black docking hatch recess", Vec3(0, -5.18, 0.08), 0.72, 0.12, 18, dark, emission=(0.0, 0.0, 0.0, 1))
        create_box(ship, "cupola central window", Vec3(0, -5.30, 0.18), Vec3(0.82, 0.08, 0.55), glass, emission=(0.0, 0.13, 0.22, 1))
        create_box(ship, "cupola top window", Vec3(0, -5.31, 0.72), Vec3(0.66, 0.07, 0.25), glass, emission=(0.0, 0.12, 0.20, 1))
        create_box(ship, "cupola lower window", Vec3(0, -5.31, -0.37), Vec3(0.62, 0.07, 0.22), glass, emission=(0.0, 0.09, 0.16, 1))
        for side in (-1, 1):
            create_box(ship, "cupola side window", Vec3(side * 0.63, -5.32, 0.18), Vec3(0.27, 0.07, 0.47), glass, hpr=Vec3(0, 0, side * 8), emission=(0.0, 0.11, 0.20, 1))
            create_box(ship, "cupola diagonal shutter", Vec3(side * 0.43, -5.34, 0.64), Vec3(0.34, 0.06, 0.08), dark, hpr=Vec3(0, 0, side * 28))
            create_box(ship, "cupola diagonal shutter", Vec3(side * 0.43, -5.34, -0.30), Vec3(0.34, 0.06, 0.08), dark, hpr=Vec3(0, 0, side * -28))
        create_outline_box(ship, "forward hatch outline", Vec3(0, -5.36, 0.08), Vec3(1.82, 0.06, 1.82), (0.0, 0.66, 1.0, 0.75), thickness=2.2)

        # Service bus aft: batteries, tanks, radiators, salvage clamps.
        create_box(ship, "service module trunk", Vec3(0, 1.75, 0.02), Vec3(2.55, 3.15, 1.55), panel_dark, emission=(0.015, 0.02, 0.035, 1))
        create_box(ship, "beveled aft shoulder top", Vec3(0, 2.08, 1.02), Vec3(2.95, 2.35, 0.34), (0.24, 0.27, 0.35, 1), hpr=Vec3(0, -7, 0), emission=(0.012, 0.016, 0.030, 1))
        create_box(ship, "cargo keel bay", Vec3(0, 1.25, -1.02), Vec3(1.75, 2.85, 0.38), dark, emission=(0.0, 0.0, 0.0, 1))
        create_outline_box(ship, "cargo bay edge lights", Vec3(0, 1.24, -1.02), Vec3(1.9, 2.95, 0.44), (0.0, 0.55, 1.0, 0.55), thickness=1.8)
        for side in (-1, 1):
            create_box(ship, "aft armored shoulder block", Vec3(side * 1.58, 2.02, 0.22), Vec3(0.72, 2.65, 1.12), (0.18, 0.20, 0.27, 1), hpr=Vec3(0, 0, side * 7), emission=(0.010, 0.014, 0.026, 1))
            create_trapezoid_prism(ship, "compact maneuver fin", Vec3(side * 1.55, 2.35, -0.70), 2.05, 0.46, 0.92, 0.13, (0.13, 0.16, 0.22, 1), side=side, hpr=Vec3(180, 0, side * -6), emission=(0.006, 0.010, 0.020, 1))

        # Long radiator/solar wings: believable spacecraft panels, also make the ship silhouette stronger in third person.
        for side in (-1, 1):
            create_box(ship, "radiator boom", Vec3(side * 2.05, -0.45, 0.18), Vec3(1.65, 0.16, 0.16), panel, hpr=Vec3(0, 0, side * -8), emission=(0.015, 0.018, 0.032, 1))
            panel_np = create_box(ship, "folded blue-black radiator wing", Vec3(side * 4.05, -0.45, 0.25), Vec3(3.55, 4.85, 0.075), solar, hpr=Vec3(0, 0, side * 4), emission=(0.0, 0.025, 0.08, 1))
            create_outline_box(panel_np, "radiator wing cyan frame", Vec3(0, 0, 0.06), Vec3(3.62, 4.92, 0.04), (0.0, 0.58, 1.0, 0.70), thickness=1.6)
            for rib in (-1.7, -0.85, 0.0, 0.85, 1.7):
                create_box(panel_np, "radiator rib", Vec3(rib, 0, 0.10), Vec3(0.04, 4.65, 0.04), (0.0, 0.33, 0.72, 1), emission=(0.0, 0.12, 0.32, 1))
            for y in (-1.95, 0.0, 1.95):
                create_box(panel_np, "radiator cross rib", Vec3(0, y, 0.105), Vec3(3.35, 0.04, 0.04), (0.0, 0.25, 0.55, 1), emission=(0.0, 0.09, 0.25, 1))
            for y in (-1.18, 1.18):
                create_box(panel_np, "radiator warning strip", Vec3(side * 0.82, y, 0.115), Vec3(0.58, 0.035, 0.045), amber, emission=(0.22, 0.08, 0.01, 1))

            # RCS pods and salvage magnetic claw details.
            create_box(ship, "forward RCS pod", Vec3(side * 1.23, -4.08, 0.72), Vec3(0.36, 0.42, 0.30), panel, emission=(0.015, 0.018, 0.03, 1))
            create_cylinder_y(ship, "RCS dark nozzle", Vec3(side * 1.47, -4.08, 0.72), 0.12, 0.12, 12, dark, hpr=Vec3(90, 0, 0))
            create_box(ship, "aft RCS pod", Vec3(side * 1.46, 2.45, 0.86), Vec3(0.42, 0.48, 0.34), panel, emission=(0.015, 0.018, 0.03, 1))
            create_cylinder_y(ship, "aft RCS nozzle", Vec3(side * 1.72, 2.45, 0.86), 0.12, 0.12, 12, dark, hpr=Vec3(90, 0, 0))
            create_box(ship, "folded salvage arm", Vec3(side * 1.1, -0.75, -1.12), Vec3(0.18, 3.15, 0.16), (0.16, 0.18, 0.22, 1), hpr=Vec3(side * 5, 0, 0), emission=(0.01, 0.012, 0.02, 1))
            create_box(ship, "magnetic salvage clamp", Vec3(side * 1.38, -2.30, -1.16), Vec3(0.66, 0.18, 0.18), blue, emission=(0.0, 0.28, 0.70, 1))

        # Engines: protected cluster with glowing cores. Main + two maneuver engines.
        self.engine_glows: list[NodePath] = []
        create_cylinder_y(ship, "main engine bell armor", Vec3(0, 3.55, 0.02), 0.68, 1.0, 24, dark, emission=(0.0, 0.0, 0.0, 1))
        main_glow = create_cylinder_y(ship, "main blue fusion exhaust", Vec3(0, 4.15, 0.02), 0.49, 0.10, 32, blue, emission=(0.0, 0.72, 1.25, 1))
        self.engine_glows.append(main_glow)
        create_glow_card(ship, "main engine soft flare", Vec3(0, 4.36, 0.02), 1.35, (0.0, 0.50, 1.0, 0.26), hpr=Vec3(0, 90, 0))
        main_trail = create_box(ship, "main animated plasma trail", Vec3(0, 4.95, 0.02), Vec3(0.54, 1.95, 0.54), (0.0, 0.52, 1.0, 0.30), emission=(0.0, 0.44, 1.0, 1))
        self.engine_trails.append(main_trail)
        outer_trail = create_box(ship, "main soft exhaust halo", Vec3(0, 5.18, 0.02), Vec3(1.08, 2.55, 1.08), (0.0, 0.24, 1.0, 0.13), emission=(0.0, 0.20, 0.58, 1))
        self.engine_trails.append(outer_trail)
        for side in (-1, 1):
            create_cylinder_y(ship, "side engine bell armor", Vec3(side * 1.12, 3.38, -0.22), 0.38, 0.92, 20, dark, emission=(0.0, 0.0, 0.0, 1))
            glow = create_cylinder_y(ship, "side engine blue core", Vec3(side * 1.12, 3.92, -0.22), 0.28, 0.08, 24, blue, emission=(0.0, 0.55, 1.0, 1))
            self.engine_glows.append(glow)
            create_glow_card(ship, "side engine flare", Vec3(side * 1.12, 4.10, -0.22), 0.82, (0.0, 0.48, 1.0, 0.22), hpr=Vec3(0, 90, 0))
            trail = create_box(ship, "side animated plasma trail", Vec3(side * 1.12, 4.70, -0.22), Vec3(0.32, 1.55, 0.32), (0.0, 0.48, 1.0, 0.26), emission=(0.0, 0.36, 0.90, 1))
            self.engine_trails.append(trail)

        # Antenna and sensor mast.
        create_box(ship, "sensor mast", Vec3(0.64, -0.15, 1.88), Vec3(0.08, 0.08, 0.78), panel, emission=(0.02, 0.025, 0.04, 1))
        create_cylinder_y(ship, "small comm dish", Vec3(0.64, -0.15, 2.30), 0.34, 0.05, 24, (0.36, 0.40, 0.50, 1), hpr=Vec3(0, -70, 0), emission=(0.025, 0.03, 0.05, 1))
        create_box(ship, "red hazard beacon", Vec3(-0.64, 2.78, 1.26), Vec3(0.18, 0.18, 0.18), red, emission=(0.45, 0.02, 0.0, 1))
        create_box(ship, "amber docking beacon", Vec3(0.64, 2.78, 1.26), Vec3(0.18, 0.18, 0.18), amber, emission=(0.35, 0.16, 0.02, 1))

        # Broad outline pass for screenshot readability without turning the game into wireframe.
        create_outline_box(ship, "crew hull readability outline", Vec3(0, -2.0, 0.08), Vec3(2.9, 5.3, 2.4), (0.0, 0.45, 1.0, 0.32), thickness=1.5)
        create_outline_box(ship, "service trunk outline", Vec3(0, 1.75, 0.02), Vec3(2.65, 3.25, 1.65), (0.0, 0.45, 1.0, 0.30), thickness=1.5)

        ship.setPos(0, -2.0, 2.5)
        ship.setHpr(0, 0, 0)
        return ship

    def build_ship_interior(self, parent: NodePath) -> None:
        """Octagonal crewed orbital observatory bridge.

        Pass 31 continues from the polished the rectangular station-room feel with a fitted eight-sided
        observatory hub.  Every major object is snapped into a section of the shell:
        forward viewport, navigation, research, archive, comms, engineering, crew
        support, and access.  Crew figures are simple generated solids at working
        stations so the interior reads alive without needing external assets.
        """
        root = parent.attachNewNode("Octagonal Crewed Observatory Bridge")
        root.setPos(0, 176, 0)

        floor = (0.135, 0.148, 0.192, 1)
        floor_dark = (0.058, 0.068, 0.096, 1)
        wall = (0.170, 0.195, 0.255, 1)
        wall_dark = (0.070, 0.088, 0.128, 1)
        rib = (0.025, 0.044, 0.080, 1)
        beam = (0.090, 0.118, 0.165, 1)
        panel = (0.160, 0.190, 0.255, 1)
        panel_dark = (0.045, 0.065, 0.098, 1)
        glass = (0.040, 0.78, 1.0, 0.60)
        neon = (0.0, 0.72, 1.0, 1)
        amber = (1.0, 0.58, 0.09, 1)
        green = (0.18, 1.0, 0.58, 1)
        violet = (0.60, 0.32, 1.0, 1)
        crew_suit = (0.42, 0.48, 0.56, 1)
        crew_dark = (0.045, 0.052, 0.070, 1)

        def wall_segment(name: str, pos: Vec3, scale: Vec3, h: float, color=wall, emit=(0.004, 0.008, 0.017, 1)) -> NodePath:
            return create_box(root, name, pos, scale, color, hpr=Vec3(h, 0, 0), emission=emit)

        self.interior_world_labels = []

        def label(text: str, pos: Vec3, scale: float = 0.075, fg=(0.68, 0.94, 1.0, 0.86), hpr: Vec3 = Vec3(0, 0, 0)) -> NodePath:
            node = self.make_world_text(root, text, pos, scale, fg, hpr=hpr)
            self.interior_world_labels.append(node)
            return node

        def crew_member(name: str, base: Vec3, facing_h: float, accent: tuple[float, float, float, float], pose: str = "standing") -> None:
            # Solid low-poly crew figure: boots, legs, torso, helmet, visor, arms, and station glow.
            local = root.attachNewNode(f"crew {name}")
            local.setPos(base)
            local.setHpr(facing_h, 0, 0)
            if pose == "seated":
                create_box(local, "crew seat base", Vec3(0, 0.16, 0.46), Vec3(0.62, 0.52, 0.22), panel_dark, emission=(0.002, 0.004, 0.010, 1))
                hip_z = 0.72
            else:
                hip_z = 0.94
                create_box(local, "left crew boot", Vec3(-0.13, 0.03, 0.22), Vec3(0.16, 0.34, 0.18), crew_dark, emission=(0.0, 0.0, 0.0, 1))
                create_box(local, "right crew boot", Vec3(0.13, 0.03, 0.22), Vec3(0.16, 0.34, 0.18), crew_dark, emission=(0.0, 0.0, 0.0, 1))
                create_box(local, "left crew leg", Vec3(-0.13, 0.02, 0.52), Vec3(0.14, 0.20, 0.48), crew_suit, emission=(0.012, 0.014, 0.018, 1))
                create_box(local, "right crew leg", Vec3(0.13, 0.02, 0.52), Vec3(0.14, 0.20, 0.48), crew_suit, emission=(0.012, 0.014, 0.018, 1))
            create_box(local, "crew torso pressure suit", Vec3(0, 0.0, hip_z), Vec3(0.46, 0.28, 0.62), crew_suit, emission=(0.014, 0.016, 0.022, 1))
            create_box(local, "crew chest role light", Vec3(0, -0.155, hip_z + 0.10), Vec3(0.24, 0.035, 0.06), accent, emission=(accent[0]*0.20, accent[1]*0.20, accent[2]*0.20, 1))
            create_uv_sphere(local, "crew helmet solid dome", Vec3(0, -0.02, hip_z + 0.48), 0.25, 10, 18, (0.78, 0.84, 0.90, 1), emission=(0.02, 0.025, 0.035, 1))
            create_box(local, "crew visor band", Vec3(0, -0.23, hip_z + 0.49), Vec3(0.34, 0.035, 0.10), (0.0, 0.55, 0.80, 0.82), emission=(0.0, 0.12, 0.22, 1))
            create_box(local, "crew left arm on console", Vec3(-0.31, -0.08, hip_z + 0.12), Vec3(0.14, 0.46, 0.12), crew_suit, hpr=Vec3(0, 0, 9), emission=(0.012, 0.014, 0.018, 1))
            create_box(local, "crew right arm on console", Vec3(0.31, -0.08, hip_z + 0.12), Vec3(0.14, 0.46, 0.12), crew_suit, hpr=Vec3(0, 0, -9), emission=(0.012, 0.014, 0.018, 1))
            label(name.upper(), base + Vec3(0, -0.36, 1.70), 0.052, (0.72, 0.94, 1.0, 0.66))

        # Octagonal solid shell: deck, ceiling, 8 faceted walls, and heavy joined corner posts.
        create_box(root, "octagonal central deck plate", Vec3(0, 0.0, -0.06), Vec3(7.6, 14.2, 0.16), floor, emission=(0.004, 0.006, 0.012, 1))
        create_box(root, "wide recessed octagonal walking lane", Vec3(0, 0.0, 0.025), Vec3(4.35, 13.2, 0.052), floor_dark, emission=(0.002, 0.004, 0.010, 1))
        for x, y, h in [(-4.30, -6.95, -45), (4.30, -6.95, 45), (-4.30, 6.95, 45), (4.30, 6.95, -45)]:
            create_box(root, "octagonal diagonal deck shoulder", Vec3(x, y, -0.058), Vec3(3.25, 3.25, 0.15), floor, hpr=Vec3(h, 0, 0), emission=(0.004, 0.006, 0.012, 1))
        create_box(root, "octagonal ceiling central plate", Vec3(0, 0, 3.34), Vec3(7.7, 14.3, 0.18), wall_dark, emission=(0.003, 0.005, 0.012, 1))
        for x, y, h in [(-4.20, -6.75, -45), (4.20, -6.75, 45), (-4.20, 6.75, 45), (4.20, 6.75, -45)]:
            create_box(root, "octagonal diagonal ceiling shoulder", Vec3(x, y, 3.34), Vec3(3.05, 3.05, 0.18), wall_dark, hpr=Vec3(h, 0, 0), emission=(0.003, 0.005, 0.012, 1))

        # Forward face is built around the viewport instead of one solid blocker.
        create_box(root, "forward observation lower hull band", Vec3(0, -8.55, 0.38), Vec3(7.40, 0.28, 0.76), wall_dark, emission=(0.004, 0.008, 0.017, 1))
        create_box(root, "forward observation upper hull band", Vec3(0, -8.55, 2.96), Vec3(7.40, 0.28, 0.54), wall_dark, emission=(0.004, 0.008, 0.017, 1))
        create_box(root, "forward observation left jamb", Vec3(-3.82, -8.55, 1.66), Vec3(0.34, 0.28, 2.44), wall_dark, emission=(0.004, 0.008, 0.017, 1))
        create_box(root, "forward observation right jamb", Vec3(3.82, -8.55, 1.66), Vec3(0.34, 0.28, 2.44), wall_dark, emission=(0.004, 0.008, 0.017, 1))
        wall_segment("rear octagonal access face", Vec3(0, 8.55, 1.62), Vec3(7.40, 0.28, 3.24), 0, wall_dark)
        wall_segment("left long octagonal hull face", Vec3(-5.25, 0, 1.62), Vec3(0.28, 10.5, 3.24), 0, wall)
        wall_segment("right long octagonal hull face", Vec3(5.25, 0, 1.62), Vec3(0.28, 10.5, 3.24), 0, wall)
        for pos, h, nm in [
            (Vec3(-4.34, -7.05, 1.62), -45, "front-left diagonal hull face"),
            (Vec3(4.34, -7.05, 1.62), 45, "front-right diagonal hull face"),
            (Vec3(-4.34, 7.05, 1.62), 45, "rear-left diagonal hull face"),
            (Vec3(4.34, 7.05, 1.62), -45, "rear-right diagonal hull face"),
        ]:
            wall_segment(nm, pos, Vec3(0.30, 3.9, 3.24), h, wall)
        for pos in [Vec3(-4.90, -7.70, 1.66), Vec3(4.90, -7.70, 1.66), Vec3(-4.90, 7.70, 1.66), Vec3(4.90, 7.70, 1.66), Vec3(-5.25, -3.6, 1.66), Vec3(5.25, -3.6, 1.66), Vec3(-5.25, 3.6, 1.66), Vec3(5.25, 3.6, 1.66)]:
            create_box(root, "solid octagonal corner pressure post", pos, Vec3(0.40, 0.40, 3.36), beam, emission=(0.0, 0.022, 0.050, 1))

        # Faceted ring beams and section seams lock the shell together.
        for z, nm, sy in [(0.26, "lower octagonal belt beam", 0.22), (3.08, "upper octagonal belt beam", 0.20)]:
            create_box(root, nm, Vec3(0, -8.30, z), Vec3(7.6, sy, 0.18), rib, emission=(0.0, 0.034, 0.080, 1))
            create_box(root, nm, Vec3(0, 8.30, z), Vec3(7.6, sy, 0.18), rib, emission=(0.0, 0.034, 0.080, 1))
            create_box(root, nm, Vec3(-5.08, 0, z), Vec3(0.20, 10.4, 0.18), rib, emission=(0.0, 0.034, 0.080, 1))
            create_box(root, nm, Vec3(5.08, 0, z), Vec3(0.20, 10.4, 0.18), rib, emission=(0.0, 0.034, 0.080, 1))
            for pos, h in [(Vec3(-4.12, -6.86, z), -45), (Vec3(4.12, -6.86, z), 45), (Vec3(-4.12, 6.86, z), 45), (Vec3(4.12, 6.86, z), -45)]:
                create_box(root, nm, pos, Vec3(0.20, 3.75, 0.18), rib, hpr=Vec3(h, 0, 0), emission=(0.0, 0.034, 0.080, 1))
        for y, name in [(-5.35, "OBS"), (-2.55, "NAV"), (0.80, "RESEARCH"), (3.90, "ARCHIVE"), (6.65, "SUPPORT")]:
            create_box(root, "octagonal section floor light", Vec3(0, y, 0.070), Vec3(6.45, 0.055, 0.055), neon, emission=(0.0, 0.14, 0.36, 1))
            label(name, Vec3(-4.64, y + 0.10, 2.92), 0.083, (0.0, 0.72, 1.0, 0.72), hpr=Vec3(90, 0, 90))

        # Forward observation side: thick framed glass, not loose panes.
        create_box(root, "main viewport lower structural sill", Vec3(0, -8.72, 0.78), Vec3(6.55, 0.20, 0.34), rib, emission=(0.0, 0.040, 0.090, 1))
        create_box(root, "main viewport upper structural sill", Vec3(0, -8.72, 2.70), Vec3(6.55, 0.20, 0.34), rib, emission=(0.0, 0.040, 0.090, 1))
        for x in (-3.25, -1.08, 1.08, 3.25):
            create_box(root, "main viewport vertical mullion", Vec3(x, -8.76, 1.72), Vec3(0.16, 0.18, 2.05), rib, emission=(0.0, 0.040, 0.090, 1))
        for x, sx in [(-2.17, 1.90), (0, 1.92), (2.17, 1.90)]:
            create_box(root, "heavy fitted observation window", Vec3(x, -8.88, 1.72), Vec3(sx, 0.065, 1.58), glass, emission=(0.0, 0.22, 0.42, 1))
            create_soft_disc_y(root, "distant simulated planet beyond glass", Vec3(x*0.30, -8.95, 1.62), sx*0.42, 0.40, (0.55, 0.78, 1.0, 0.15), (0.0, 0.0, 0.0, 0.0), 34)
            for sidx in range(5):
                create_box(root, "tiny exterior star through octagonal glass", Vec3(x + (-0.62 + sidx*0.31), -8.965, 1.05 + ((sidx*41) % 100)/100*1.20), Vec3(0.030, 0.016, 0.030), (0.82, 0.94, 1.0, 0.90), emission=(0.30, 0.42, 0.70, 1))
        create_soft_disc_y(root, "large orbital body visible beyond forward viewport", Vec3(0.95, -9.08, 1.78), 0.82, 0.66, (0.32, 0.62, 1.0, 0.22), (0.0, 0.0, 0.0, 0.0), 48)
        create_soft_disc_y(root, "distant anomaly glow visible beyond viewport", Vec3(-1.35, -9.09, 1.42), 0.44, 0.30, (1.0, 0.48, 0.12, 0.16), (0.0, 0.0, 0.0, 0.0), 36)
        create_box(root, "solid observation counter integrated into wall", Vec3(0, -7.75, 0.70), Vec3(6.85, 1.00, 0.48), panel, emission=(0.006, 0.012, 0.026, 1))
        create_box(root, "observation counter pressure seal", Vec3(0, -8.30, 0.96), Vec3(6.85, 0.14, 0.28), rib, emission=(0.0, 0.035, 0.080, 1))

        # Canopy and side windows set into the octagonal hull faces.
        for y in (-6.6, -4.8, -3.0, -1.2, 0.6, 2.4):
            create_box(root, "octagonal overhead canopy glass", Vec3(0, y, 3.43), Vec3(2.40, 1.05, 0.060), glass, emission=(0.0, 0.11, 0.24, 1))
            create_box(root, "canopy joined left rail", Vec3(-1.38, y, 3.32), Vec3(0.10, 1.13, 0.11), rib, emission=(0.0, 0.04, 0.10, 1))
            create_box(root, "canopy joined right rail", Vec3(1.38, y, 3.32), Vec3(0.10, 1.13, 0.11), rib, emission=(0.0, 0.04, 0.10, 1))
        for side in (-1, 1):
            x = side * 5.38
            for y in (-4.2, -1.55, 1.35, 4.10):
                create_box(root, "fitted side window glass", Vec3(x, y, 1.80), Vec3(0.060, 1.16, 1.00), glass, emission=(0.0, 0.10, 0.22, 1))
                create_box(root, "side window solid upper sill", Vec3(side*5.16, y, 2.39), Vec3(0.16, 1.33, 0.10), rib, emission=(0.0, 0.034, 0.078, 1))
                create_box(root, "side window solid lower sill", Vec3(side*5.16, y, 1.20), Vec3(0.16, 1.33, 0.10), rib, emission=(0.0, 0.034, 0.078, 1))

        # Eight-purpose wall layout: stations built into octagonal faces.
        stations = [
            (-3.45, -5.15, "NAVIGATION", neon, -10),
            (3.45, -5.15, "CELESTIAL TRACK", green, 10),
            (-4.34, -1.70, "SPECTRAL LAB", violet, 0),
            (4.34, -1.70, "ORBIT SOLVER", amber, 0),
            (-3.60, 2.35, "CATALOG", neon, 8),
            (3.60, 2.35, "ANOMALY", violet, -8),
            (-3.55, 5.85, "COMMS", green, 0),
            (3.55, 5.85, "ENGINEERING", amber, 0),
        ]
        for x, y, name, color, yaw in stations:
            create_box(root, f"{name} solid console base", Vec3(x, y, 0.62), Vec3(1.58, 1.05, 0.44), panel, hpr=Vec3(yaw, 0, 0), emission=(0.006, 0.010, 0.022, 1))
            create_box(root, f"{name} inset display slab", Vec3(x, y-0.58, 1.34), Vec3(1.28, 0.07, 0.52), (0.035, 0.075, 0.105, 1), hpr=Vec3(yaw, 0, 0), emission=(color[0]*0.030, color[1]*0.050, color[2]*0.075, 1))
            create_box(root, f"{name} deck skirt", Vec3(x, y+0.55, 0.25), Vec3(1.74, 0.16, 0.30), rib, hpr=Vec3(yaw, 0, 0), emission=(0.0, 0.018, 0.050, 1))
            label(name, Vec3(x, y-0.69, 1.73), 0.055, (0.74, 0.96, 1.0, 0.78))

        # Central orbital table remains low, with wide clearance on every side.
        create_cylinder_y(root, "solid central octagonal research table", Vec3(0, 0.42, 0.82), 1.02, 0.18, 8, (0.0, 0.42, 0.76, 0.36), hpr=Vec3(90, 0, 22.5), emission=(0.0, 0.18, 0.55, 1))
        create_cylinder_y(root, "floating low orbital simulation disc", Vec3(0, 0.42, 1.27), 0.74, 0.035, 64, (0.0, 0.70, 1.0, 0.24), hpr=Vec3(90, 0, 0), emission=(0.0, 0.30, 0.86, 1))
        for r, col in [(0.35, (0.0, 0.74, 1.0, 0.28)), (0.55, (0.45, 0.70, 1.0, 0.16)), (0.70, (1.0, 0.58, 0.10, 0.12))]:
            create_annular_arc_y(root, "table orbital path ring", Vec3(0, 0.43, 1.31), r, r+0.018, 0, 360, 64, col, hpr=Vec3(0, 0, 0), emission=(col[0]*0.22, col[1]*0.22, col[2]*0.22, 1))
        create_uv_sphere(root, "table hero body", Vec3(0.30, 0.45, 1.37), 0.07, 8, 12, (0.55, 0.82, 1.0, 1), emission=(0.08, 0.16, 0.32, 1))

        # Pass 21 economy console is now a built-in rear wall display, not a floating screen.
        create_box(root, "rear integrated economy console body", Vec3(0.0, 8.30, 1.83), Vec3(4.65, 0.12, 1.42), panel_dark, emission=(0.0, 0.018, 0.046, 1))
        create_box(root, "rear integrated economy console glass", Vec3(0.0, 8.18, 1.83), Vec3(4.25, 0.060, 1.10), (0.0, 0.34, 0.52, 0.34), emission=(0.0, 0.16, 0.44, 1))
        self.cabin_console_lines = []
        line_defs = [
            ("OBSERVATORY SYSTEM", Vec3(0.0, 8.08, 2.42), 0.075, (0.62, 0.94, 1.0, 0.90)),
            ("VALUE", Vec3(0.0, 8.08, 2.20), 0.056, (0.76, 0.96, 1.0, 0.84)),
            ("CARGO", Vec3(0.0, 8.08, 2.00), 0.056, (0.56, 1.0, 0.75, 0.84)),
            ("SCAN", Vec3(0.0, 8.08, 1.80), 0.056, (0.66, 0.92, 1.0, 0.84)),
            ("UPGRADE", Vec3(0.0, 8.08, 1.60), 0.056, (1.0, 0.78, 0.38, 0.86)),
        ]
        for text_line, pos, scale, fg in line_defs:
            node = label(text_line, pos, scale, fg, hpr=Vec3(180, 0, 0))
            self.cabin_console_lines.append(node)


        # Pass 29 graphics polish: solid plating, better console glass, believable trim, and less flat lighting.
        # All additions are fitted to existing shell faces and stations; no loose floating props.
        graphite = (0.022, 0.028, 0.040, 1)
        steel_hi = (0.22, 0.25, 0.31, 1)
        steel_mid = (0.115, 0.135, 0.175, 1)
        steel_low = (0.038, 0.048, 0.070, 1)
        blue_glass = (0.0, 0.50, 0.86, 0.34)
        dim_blue = (0.0, 0.18, 0.38, 1)
        warm_line = (1.0, 0.58, 0.18, 1)
        # Pass 30 graphics readability pass: stronger solid materials, fitted depth layers,
        # better orbital window scenery, and clearer station sections.  These additions sit
        # on existing wall/floor/console positions so the room stays coherent and not cluttered.
        deep_black = (0.010, 0.014, 0.022, 1)
        edge_blue = (0.0, 0.52, 0.98, 1)
        white_glow = (0.78, 0.93, 1.0, 1)
        soft_status = (0.10, 0.24, 0.36, 1)
        rubber = (0.010, 0.012, 0.018, 1)
        panel_shadow = (0.026, 0.034, 0.052, 1)
        metal_face = (0.18, 0.205, 0.245, 1)

        # Additional deck material layers: wider structural plates with seams and grates that
        # make the octagonal room read as a solid ship interior instead of a few large blocks.
        for x in (-2.55, -0.85, 0.85, 2.55):
            create_box(root, "pass30 brushed walking deck slab", Vec3(x, -0.12, 0.164), Vec3(1.38, 12.65, 0.018), (0.075, 0.088, 0.120, 1), emission=(0.002, 0.004, 0.010, 1))
            create_box(root, "pass30 deck slab inner bevel", Vec3(x + 0.66, -0.12, 0.186), Vec3(0.030, 12.30, 0.028), graphite, emission=(0.0, 0.005, 0.014, 1))
        for y in [-7.45, -6.25, -5.05, -3.85, -2.65, -1.45, -0.25, 0.95, 2.15, 3.35, 4.55, 5.75, 6.95, 7.75]:
            create_box(root, "pass30 inset black deck gasket", Vec3(0, y, 0.200), Vec3(6.74, 0.018, 0.026), rubber, emission=(0.0, 0.0, 0.004, 1))
            create_box(root, "pass30 tiny deck cyan service light", Vec3(-3.10, y + 0.18, 0.226), Vec3(0.16, 0.030, 0.020), edge_blue, emission=(0.0, 0.20, 0.48, 1))
            create_box(root, "pass30 tiny deck amber service light", Vec3(3.10, y - 0.18, 0.226), Vec3(0.16, 0.030, 0.020), warm_line, emission=(0.16, 0.06, 0.012, 1))

        # Bulkhead ribs between room sections.  They preserve the open center but make the
        # observatory feel compartmentalized into real orbital-simulation work zones.
        for y, tag, accent in [(-6.05, "OBS", edge_blue), (-3.20, "NAV", green), (0.10, "LAB", violet), (3.25, "DATA", neon), (6.35, "SYS", amber)]:
            create_box(root, "pass30 left section bulkhead upright", Vec3(-4.72, y, 1.70), Vec3(0.22, 0.18, 2.74), metal_face, emission=(0.0, 0.020, 0.052, 1))
            create_box(root, "pass30 right section bulkhead upright", Vec3(4.72, y, 1.70), Vec3(0.22, 0.18, 2.74), metal_face, emission=(0.0, 0.020, 0.052, 1))
            create_box(root, "pass30 section overhead bridge", Vec3(0, y, 3.020), Vec3(9.05, 0.18, 0.20), steel_mid, emission=(0.0, 0.018, 0.046, 1))
            create_box(root, "pass30 section floor threshold", Vec3(0, y, 0.255), Vec3(8.60, 0.13, 0.090), graphite, emission=(0.0, 0.012, 0.032, 1))
            create_box(root, "pass30 section accent slit", Vec3(0, y - 0.095, 3.165), Vec3(2.50, 0.028, 0.030), accent, emission=(accent[0]*0.17, accent[1]*0.17, accent[2]*0.22, 1))
            label(tag, Vec3(-4.62, y - 0.12, 2.34), 0.060, (0.72, 0.94, 1.0, 0.72), hpr=Vec3(90, 0, 90))
            label(tag, Vec3(4.62, y + 0.12, 2.34), 0.060, (0.72, 0.94, 1.0, 0.72), hpr=Vec3(-90, 0, -90))

        # The forward view is the reason this game is now interior-first.  Add a brighter but
        # still grounded orbital scene built from simple in-engine shapes behind the fitted glass.
        create_soft_disc_y(root, "pass30 bright planetary limb through window", Vec3(-1.55, -9.115, 0.94), 3.85, 0.64, (0.36, 0.68, 1.0, 0.30), (0.0, 0.0, 0.0, 0.0), 78, hpr=Vec3(0, 0, -5))
        create_soft_disc_y(root, "pass30 white atmospheric edge line", Vec3(-1.55, -9.125, 1.16), 3.82, 0.130, (0.86, 0.98, 1.0, 0.46), (0.0, 0.0, 0.0, 0.0), 78, hpr=Vec3(0, 0, -5))
        create_soft_disc_y(root, "pass30 cold moon crescent", Vec3(2.68, -9.135, 1.90), 0.34, 0.32, (0.56, 0.72, 0.94, 0.24), (0.0, 0.0, 0.0, 0.0), 42, hpr=Vec3(0, 0, 6))
        create_soft_disc_y(root, "pass30 brilliant study star", Vec3(1.32, -9.145, 2.26), 0.23, 0.23, (1.0, 0.95, 0.70, 0.52), (1.0, 0.50, 0.10, 0.0), 42)
        for sx, sy, sz, alpha in [(-2.7, -9.16, 2.08, 0.70), (-0.7, -9.17, 2.42, 0.52), (0.65, -9.18, 1.18, 0.60), (2.05, -9.16, 1.36, 0.50)]:
            create_box(root, "pass30 bright star pin through glass", Vec3(sx, sy, sz), Vec3(0.045, 0.018, 0.045), (0.86, 0.96, 1.0, alpha), emission=(0.30, 0.43, 0.74, 1))

        # More credible window depth: inner/outer gaskets and screw plates make panes look seated.
        for x in (-3.44, -1.12, 1.12, 3.44):
            create_box(root, "pass30 window mullion forward bevel cap", Vec3(x, -8.785, 1.72), Vec3(0.13, 0.060, 2.06), metal_face, emission=(0.0, 0.018, 0.044, 1))
            for z in (0.84, 2.58):
                create_box(root, "pass30 window mullion bolt pad", Vec3(x, -8.735, z), Vec3(0.18, 0.055, 0.060), steel_hi, emission=(0.004, 0.006, 0.012, 1))
        for x in (-2.20, 0.0, 2.20):
            create_box(root, "pass30 faint glass reflection line", Vec3(x, -8.990, 2.28), Vec3(1.50, 0.014, 0.018), white_glow, emission=(0.16, 0.21, 0.30, 1))
            create_box(root, "pass30 lower glass reflection line", Vec3(x + 0.15, -8.990, 1.04), Vec3(1.20, 0.014, 0.014), edge_blue, emission=(0.0, 0.12, 0.32, 1))

        # Wall screen clusters are now mounted into solid frames so the graphic language is richer
        # without adding arbitrary floating UI panels.
        for side, x in [(-1, -5.075), (1, 5.075)]:
            for y, title, col in [(-5.45, "GUIDE", neon), (-2.10, "SCAN", green), (1.35, "ORBIT", violet), (4.85, "POWER", amber)]:
                create_box(root, "pass30 side inset terminal frame", Vec3(x, y, 1.78), Vec3(0.055, 1.04, 0.58), steel_mid, emission=(0.0, 0.018, 0.042, 1))
                create_box(root, "pass30 side terminal dark glass", Vec3(x - side*0.040, y, 1.78), Vec3(0.026, 0.84, 0.42), blue_glass, emission=(0.0, 0.090, 0.28, 1))
                for row in range(3):
                    create_box(root, "pass30 side terminal readout tick", Vec3(x - side*0.067, y - 0.30 + row*0.24, 1.70 + row*0.08), Vec3(0.015, 0.24 - row*0.03, 0.018), col, emission=(col[0]*0.16, col[1]*0.16, col[2]*0.22, 1))

        # Station consoles get second-stage readable physical controls, not more screen clutter.
        for x, y, name, color, yaw in stations:
            create_box(root, f"pass30 {name} lower kickplate", Vec3(x, y + 0.56, 0.445), Vec3(1.62, 0.070, 0.24), graphite, hpr=Vec3(yaw, 0, 0), emission=(0.0, 0.004, 0.014, 1))
            create_box(root, f"pass30 {name} active input tray", Vec3(x, y - 0.24, 1.01), Vec3(1.10, 0.26, 0.035), panel_shadow, hpr=Vec3(yaw, 0, 0), emission=(0.0, 0.012, 0.036, 1))
            for i in range(4):
                create_box(root, f"pass30 {name} physical key light", Vec3(x - 0.36 + i*0.24, y - 0.39, 1.05), Vec3(0.070, 0.030, 0.025), color, hpr=Vec3(yaw, 0, 0), emission=(color[0]*0.16, color[1]*0.16, color[2]*0.20, 1))
            create_box(root, f"pass30 {name} upper screen shade", Vec3(x, y - 0.735, 1.60), Vec3(1.34, 0.075, 0.070), rubber, hpr=Vec3(yaw, 0, 0), emission=(0.0, 0.0, 0.004, 1))

        # Central orbital table feels more like a real instrument: a solid base plus layered holography.
        create_cylinder_y(root, "pass30 central table lower octagonal plinth", Vec3(0, 0.42, 0.38), 0.78, 0.24, 8, steel_low, hpr=Vec3(90, 0, 22.5), emission=(0.0, 0.014, 0.034, 1))
        for idx, (r, col, rot) in enumerate([(0.92, (0.0, 0.74, 1.0, 0.18), 0), (0.58, (0.50, 0.78, 1.0, 0.16), 90), (0.36, (1.0, 0.58, 0.14, 0.12), 45)]):
            create_annular_arc_y(root, "pass30 multi-axis table holo orbit", Vec3(0, 0.435, 1.39), r, r + 0.020, 0, 360, 64, col, hpr=Vec3(90 if idx == 0 else 0, 90 if idx == 1 else 0, rot), emission=(col[0]*0.20, col[1]*0.20, col[2]*0.28, 1))
        create_soft_disc_y(root, "pass30 table soft blue glow pool", Vec3(0, 0.42, 1.19), 1.00, 0.36, (0.0, 0.58, 1.0, 0.12), (0.0, 0.0, 0.0, 0.0), 48)

        # Crew silhouettes get slightly less toy-like with backpacks, wrist displays and grounded foot pads.
        for base, accent, seated in [
            (Vec3(-3.45, -4.35, 0.0), neon, True),
            (Vec3(3.42, -1.25, 0.0), violet, False),
            (Vec3(3.55, 6.30, 0.0), amber, False),
            (Vec3(-3.55, 6.25, 0.0), green, True),
        ]:
            local = root.attachNewNode("pass30 crew extra fitted detail")
            local.setPos(base)
            local.setHpr(180, 0, 0)
            hip_z = 0.72 if seated else 0.94
            create_box(local, "pass30 crew wrist terminal left", Vec3(-0.39, -0.19, hip_z + 0.05), Vec3(0.070, 0.035, 0.050), accent, emission=(accent[0]*0.18, accent[1]*0.18, accent[2]*0.24, 1))
            create_box(local, "pass30 crew wrist terminal right", Vec3(0.39, -0.19, hip_z + 0.05), Vec3(0.070, 0.035, 0.050), accent, emission=(accent[0]*0.18, accent[1]*0.18, accent[2]*0.24, 1))
            create_box(local, "pass30 crew station foot pad", Vec3(0, -0.02, 0.065), Vec3(0.82, 0.64, 0.035), graphite, emission=(0.0, 0.004, 0.014, 1))
            create_box(local, "pass30 crew helmet rim", Vec3(0, -0.025, hip_z + 0.72), Vec3(0.38, 0.060, 0.055), steel_mid, emission=(0.004, 0.006, 0.012, 1))


        # Layered deck panels: the room now reads like heavy metal plates instead of broad flat planes.
        for ix, x in enumerate([-2.75, -1.36, 0.0, 1.36, 2.75]):
            create_box(root, "pass29 brushed deck inset panel", Vec3(x, -0.25, 0.088), Vec3(1.04, 12.20, 0.030), steel_low, emission=(0.001, 0.002, 0.006, 1))
            create_box(root, "pass29 raised deck panel lip", Vec3(x - 0.57, -0.25, 0.122), Vec3(0.030, 12.05, 0.046), rib, emission=(0.0, 0.015, 0.042, 1))
        for y in [-7.0, -5.85, -4.65, -3.45, -2.25, -1.05, 0.15, 1.35, 2.55, 3.75, 4.95, 6.15, 7.35]:
            create_box(root, "pass29 deck cross seam black gasket", Vec3(0, y, 0.134), Vec3(6.60, 0.025, 0.025), graphite, emission=(0.0, 0.0, 0.002, 1))
            create_box(root, "pass29 tiny deck service bolts", Vec3(-3.16, y, 0.160), Vec3(0.060, 0.060, 0.018), steel_hi, emission=(0.004, 0.005, 0.008, 1))
            create_box(root, "pass29 tiny deck service bolts", Vec3(3.16, y, 0.160), Vec3(0.060, 0.060, 0.018), steel_hi, emission=(0.004, 0.005, 0.008, 1))

        # Forward viewport gets deeper, more believable framing and visible orbital backdrop elements.
        create_box(root, "pass29 forward window top black gasket", Vec3(0, -8.825, 2.73), Vec3(6.82, 0.045, 0.070), graphite, emission=(0.0, 0.004, 0.010, 1))
        create_box(root, "pass29 forward window bottom black gasket", Vec3(0, -8.825, 0.72), Vec3(6.82, 0.045, 0.070), graphite, emission=(0.0, 0.004, 0.010, 1))
        create_box(root, "pass29 forward window left black gasket", Vec3(-3.52, -8.825, 1.72), Vec3(0.070, 0.045, 1.94), graphite, emission=(0.0, 0.004, 0.010, 1))
        create_box(root, "pass29 forward window right black gasket", Vec3(3.52, -8.825, 1.72), Vec3(0.070, 0.045, 1.94), graphite, emission=(0.0, 0.004, 0.010, 1))
        for x in (-3.42, -1.12, 1.12, 3.42):
            create_box(root, "pass29 beveled main window mullion face", Vec3(x, -8.93, 1.72), Vec3(0.075, 0.060, 1.95), steel_mid, emission=(0.0, 0.022, 0.050, 1))
            create_box(root, "pass29 main window cyan edge trace", Vec3(x + 0.055, -8.985, 1.72), Vec3(0.018, 0.018, 1.66), neon, emission=(0.0, 0.11, 0.32, 1))
        for z in (0.86, 2.58):
            create_box(root, "pass29 main window horizontal cyan seal", Vec3(0, -8.985, z), Vec3(6.35, 0.018, 0.024), neon, emission=(0.0, 0.11, 0.32, 1))
        # Curved limb, sun glint, and small moon outside the glass create a richer orbital-simulation view.
        create_soft_disc_y(root, "pass29 wide planetary horizon outside viewport", Vec3(-1.45, -9.02, 1.03), 3.15, 0.52, (0.48, 0.78, 1.0, 0.28), (0.0, 0.0, 0.0, 0.0), 72, hpr=Vec3(0, 0, -6))
        create_soft_disc_y(root, "pass29 atmospheric rim glow outside viewport", Vec3(-1.45, -9.03, 1.18), 3.10, 0.16, (0.78, 0.96, 1.0, 0.34), (0.0, 0.0, 0.0, 0.0), 72, hpr=Vec3(0, 0, -6))
        create_soft_disc_y(root, "pass29 distant star glare outside viewport", Vec3(1.74, -9.04, 2.15), 0.30, 0.30, (1.0, 0.92, 0.62, 0.44), (1.0, 0.54, 0.18, 0.0), 36)
        create_soft_disc_y(root, "pass29 distant moon outside viewport", Vec3(2.75, -9.05, 1.90), 0.28, 0.28, (0.42, 0.55, 0.74, 0.18), (0.0, 0.0, 0.0, 0.0), 36)

        # Ceiling and wall panels: thin seams, vents, and warm/cool light strips fitted into the octagonal shell.
        for y in [-6.8, -4.4, -2.0, 0.4, 2.8, 5.2, 7.3]:
            create_box(root, "pass29 recessed ceiling service panel", Vec3(0, y, 3.235), Vec3(4.60, 0.76, 0.035), steel_low, emission=(0.001, 0.003, 0.008, 1))
            create_box(root, "pass29 ceiling warm task light", Vec3(0, y - 0.34, 3.175), Vec3(2.10, 0.040, 0.038), warm_line, emission=(0.18, 0.070, 0.020, 1))
            create_box(root, "pass29 ceiling blue status light", Vec3(0, y + 0.34, 3.176), Vec3(1.30, 0.036, 0.036), neon, emission=(0.0, 0.095, 0.28, 1))
        for side in (-1, 1):
            x = side * 5.055
            for y in [-5.9, -3.5, -1.1, 1.3, 3.7, 6.1]:
                create_box(root, "pass29 side hull inset service panel", Vec3(x, y, 2.78), Vec3(0.035, 1.10, 0.32), steel_low, emission=(0.001, 0.003, 0.010, 1))
                create_box(root, "pass29 side panel small status diode", Vec3(x - side*0.026, y - 0.42, 2.78), Vec3(0.022, 0.050, 0.060), neon, emission=(0.0, 0.13, 0.34, 1))

        # Consoles get darker housings, glass faces, graph lines, and physical separators.
        for x, y, name, color, yaw in stations:
            create_box(root, f"pass29 {name} console black glass", Vec3(x, y-0.655, 1.345), Vec3(1.16, 0.024, 0.44), blue_glass, hpr=Vec3(yaw, 0, 0), emission=(0.0, 0.11, 0.30, 1))
            create_box(root, f"pass29 {name} top metal bevel", Vec3(x, y-0.50, 1.05), Vec3(1.42, 0.11, 0.080), steel_mid, hpr=Vec3(yaw, 0, 0), emission=(0.002, 0.005, 0.013, 1))
            for row in range(3):
                yy = y - 0.695
                zz = 1.245 + row * 0.095
                create_box(root, f"pass29 {name} tiny readout line", Vec3(x - 0.36 + row*0.15, yy-0.010, zz), Vec3(0.34 - row*0.045, 0.012, 0.014), color, hpr=Vec3(yaw, 0, 0), emission=(color[0]*0.20, color[1]*0.20, color[2]*0.28, 1))
            for col_idx, dx in enumerate([-0.52, 0.52]):
                create_box(root, f"pass29 {name} console side armored cheek", Vec3(x + dx, y+0.04, 0.72), Vec3(0.060, 0.78, 0.40), steel_mid, hpr=Vec3(yaw, 0, 0), emission=(0.002, 0.005, 0.012, 1))

        # Research table graphics: stronger transparent orbit cage and tactile pedestal detail.
        create_cylinder_y(root, "pass29 central table armored pedestal", Vec3(0, 0.42, 0.58), 0.58, 0.55, 8, steel_mid, hpr=Vec3(90, 0, 22.5), emission=(0.0, 0.018, 0.040, 1))
        create_annular_arc_y(root, "pass29 orbital table vertical holo ring A", Vec3(0, 0.43, 1.37), 0.86, 0.88, 0, 360, 64, (0.0, 0.76, 1.0, 0.21), hpr=Vec3(90, 0, 0), emission=(0.0, 0.19, 0.52, 1))
        create_annular_arc_y(root, "pass29 orbital table vertical holo ring B", Vec3(0, 0.43, 1.37), 0.72, 0.74, 0, 360, 64, (0.58, 0.76, 1.0, 0.16), hpr=Vec3(0, 90, 0), emission=(0.08, 0.14, 0.40, 1))
        create_uv_sphere(root, "pass29 luminous table target core", Vec3(0.0, 0.43, 1.37), 0.055, 8, 12, (0.85, 0.95, 1.0, 1), emission=(0.22, 0.38, 0.75, 1))

        # Crew polish pass: shoulder plates, belt packs, backpack modules, and brighter role stripes.
        # These attach as fitted additions at each crew station position, not independent decorative clutter.
        def crew_upgrade(base: Vec3, facing_h: float, accent: tuple[float, float, float, float], seated: bool = False) -> None:
            local = root.attachNewNode("pass29 fitted crew suit detail")
            local.setPos(base)
            local.setHpr(facing_h, 0, 0)
            hip_z = 0.72 if seated else 0.94
            create_box(local, "crew shoulder yoke", Vec3(0, -0.018, hip_z + 0.31), Vec3(0.62, 0.08, 0.12), steel_mid, emission=(0.004, 0.006, 0.010, 1))
            create_box(local, "crew back life-support pack", Vec3(0, 0.195, hip_z + 0.08), Vec3(0.34, 0.090, 0.38), steel_low, emission=(0.004, 0.007, 0.015, 1))
            create_box(local, "crew bright role stripe", Vec3(0, -0.218, hip_z + 0.23), Vec3(0.34, 0.020, 0.035), accent, emission=(accent[0]*0.22, accent[1]*0.22, accent[2]*0.25, 1))
            create_box(local, "crew belt utility pack", Vec3(0.27, -0.030, hip_z - 0.28), Vec3(0.10, 0.08, 0.12), graphite, emission=(0.0, 0.0, 0.004, 1))
        crew_upgrade(Vec3(-3.45, -4.35, 0.0), 180, neon, True)
        crew_upgrade(Vec3(4.05, -2.15, 0.0), 182, violet, False)
        crew_upgrade(Vec3(3.55, 6.30, 0.0), 180, amber, False)
        crew_upgrade(Vec3(-3.55, 6.25, 0.0), 180, green, True)

        # Observation labels and room-status indicators kept physical, not HUD-heavy.
        create_box(root, "pass29 forward room nameplate backing", Vec3(0, -8.38, 2.995), Vec3(3.95, 0.055, 0.20), graphite, emission=(0.0, 0.010, 0.028, 1))
        label("ORBITAL OBSERVATORY // CREWED SIMULATION BRIDGE", Vec3(0, -8.42, 3.05), 0.074, (0.82, 0.96, 1.0, 0.86))

        # Crew positioned at real stations, kept outside central walk lane.
        crew_member("Navigator", Vec3(-3.45, -4.35, 0.0), 180, neon, pose="seated")
        crew_member("Research", Vec3(4.05, -2.15, 0.0), 182, violet, pose="standing")
        crew_member("Engineer", Vec3(3.55, 6.30, 0.0), 180, amber, pose="standing")
        crew_member("Comms", Vec3(-3.55, 6.25, 0.0), 180, green, pose="seated")

        # Real solid details: wall trays, access hatch, handrails, floor grates. These are fitted, not free props.
        for side in (-1, 1):
            create_box(root, "solid side lower conduit tray", Vec3(side*4.88, 0.0, 0.48), Vec3(0.14, 13.6, 0.18), rib, emission=(0.0, 0.024, 0.060, 1))
            create_box(root, "solid side upper conduit tray", Vec3(side*4.88, 0.0, 2.68), Vec3(0.14, 13.6, 0.14), rib, emission=(0.0, 0.024, 0.060, 1))
            create_box(root, "observatory side handrail", Vec3(side*2.45, -6.60, 1.04), Vec3(0.12, 2.20, 0.12), beam, emission=(0.0, 0.030, 0.070, 1))
        for y in [-7.4, -6.2, -5.0, -3.8, -2.6, -1.4, -0.2, 1.0, 2.2, 3.4, 4.6, 5.8, 7.0]:
            create_box(root, "fitted deck grating seam", Vec3(0, y, 0.052), Vec3(6.55, 0.034, 0.050), (0.0, 0.24, 0.50, 1), emission=(0.0, 0.070, 0.18, 1))
        create_box(root, "solid rear access hatch", Vec3(0, 8.70, 1.18), Vec3(1.36, 0.16, 1.60), wall, emission=(0.004, 0.008, 0.017, 1))
        create_box(root, "hatch vertical seal", Vec3(0, 8.58, 1.18), Vec3(0.10, 0.06, 1.45), neon, emission=(0.0, 0.13, 0.36, 1))
        label("OCTAGONAL ORBITAL OBSERVATORY", Vec3(0, -8.38, 2.98), 0.122, (0.0, 0.72, 1.0, 0.84))

        # Pass 31: neat functional observatory pass.  These pieces reduce loose-looking brightness,
        # make the room's five functional stations readable, and preserve a clear central aisle.
        pass31_glass = (0.015, 0.045, 0.070, 0.92)
        pass31_edge = (0.0, 0.58, 1.0, 1)
        pass31_metal = (0.030, 0.046, 0.072, 1)
        # Forward command rail holds the active station readout without adding HUD clutter.
        create_box(root, "pass31 fitted command rail body", Vec3(0, -7.05, 1.18), Vec3(5.45, 0.20, 0.42), pass31_metal, emission=(0.0, 0.010, 0.028, 1))
        create_box(root, "pass31 command rail glass readout", Vec3(0, -7.19, 1.28), Vec3(4.95, 0.050, 0.30), pass31_glass, emission=(0.0, 0.040, 0.090, 1))
        self.observatory_station_lines = []
        for i, z in enumerate([1.42, 1.31, 1.20, 1.09]):
            node = label("--", Vec3(0, -7.245, z), 0.052 if i else 0.060, (0.72, 0.95, 1.0, 0.82))
            self.observatory_station_lines.append(node)
        # Five physical selector lamps set into the rail; active one is updated in code.
        self.observatory_station_lamps = []
        for i, code in enumerate(["OBS", "NAV", "LAB", "DATA", "SYS"]):
            x = -2.36 + i * 1.18
            lamp = create_box(root, "pass31 station selector lamp", Vec3(x, -7.31, 0.91), Vec3(0.46, 0.045, 0.060), pass31_edge, emission=(0.0, 0.090, 0.24, 1))
            self.observatory_station_lamps.append(lamp)
            label(code, Vec3(x, -7.345, 0.985), 0.040, (0.70, 0.94, 1.0, 0.70))
        # Make every console read as a built-in workstation with dark glass and small non-blinding lines.
        for x, y, name, color, yaw in stations:
            create_box(root, "pass31 console integrated dark face", Vec3(x, y - 0.675, 1.345), Vec3(1.06, 0.030, 0.37), pass31_glass, hpr=Vec3(yaw, 0, 0), emission=(0.0, 0.035, 0.085, 1))
            for row in range(4):
                create_box(root, "pass31 tiny console telemetry line", Vec3(x - 0.34 + row*0.22, y - 0.707, 1.215 + row*0.072), Vec3(0.20, 0.010, 0.012), color, hpr=Vec3(yaw, 0, 0), emission=(color[0]*0.095, color[1]*0.095, color[2]*0.13, 1))
            create_box(root, "pass31 console wall-fitted cable boot", Vec3(x, y + 0.89, 0.42), Vec3(1.34, 0.11, 0.22), pass31_metal, hpr=Vec3(yaw, 0, 0), emission=(0.0, 0.008, 0.020, 1))
        # Clean lane boundary, subtle and practical; no floating props.
        for side in (-1, 1):
            create_box(root, "pass31 clear aisle low safety rail", Vec3(side*2.25, -0.10, 0.52), Vec3(0.060, 10.25, 0.070), (0.050, 0.085, 0.130, 1), emission=(0.0, 0.028, 0.070, 1))
            create_box(root, "pass31 aisle rail cyan inset", Vec3(side*2.25, -0.10, 0.60), Vec3(0.020, 9.75, 0.024), pass31_edge, emission=(0.0, 0.070, 0.20, 1))
        # Extra floor plates cover gaps and create a coherent walkable surface.
        for y in [-6.40, -4.80, -3.20, -1.60, 0.00, 1.60, 3.20, 4.80, 6.40]:
            create_box(root, "pass31 flush lane floor insert", Vec3(0, y, 0.086), Vec3(3.78, 1.18, 0.026), (0.038, 0.049, 0.070, 1), emission=(0.0, 0.004, 0.014, 1))
            create_box(root, "pass31 floor insert seam", Vec3(0, y + 0.57, 0.108), Vec3(3.70, 0.018, 0.018), (0.0, 0.24, 0.48, 1), emission=(0.0, 0.040, 0.12, 1))
        # Keep the central hologram low and readable; older tall pass rings are hidden here so
        # the table does not block the forward viewport or station readout.
        for pattern in ["**/pass30 multi-axis table holo orbit", "**/pass29 orbital table vertical holo ring A", "**/pass29 orbital table vertical holo ring B"]:
            for old_holo in root.findAllMatches(pattern):
                old_holo.stash()
        create_annular_arc_y(root, "pass31 compact table orbit ring low", Vec3(0, 0.43, 1.12), 0.56, 0.58, 0, 360, 56, (0.0, 0.72, 1.0, 0.16), hpr=Vec3(90, 0, 0), emission=(0.0, 0.14, 0.40, 1))
        create_annular_arc_y(root, "pass31 compact table orbit ring angled", Vec3(0, 0.43, 1.12), 0.42, 0.44, 0, 360, 48, (0.66, 0.82, 1.0, 0.13), hpr=Vec3(58, 0, 28), emission=(0.08, 0.12, 0.30, 1))
        create_soft_disc_y(root, "pass31 low table data pool", Vec3(0, 0.43, 1.05), 0.64, 0.24, (0.0, 0.56, 1.0, 0.070), (0.0, 0.0, 0.0, 0.0), 36)
        # Rear access / systems area gets integrated shelves, not free props.
        create_box(root, "pass31 rear support integrated shelf", Vec3(0, 8.38, 2.18), Vec3(5.70, 0.18, 0.24), pass31_metal, emission=(0.0, 0.012, 0.032, 1))
        for x in [-2.4, -1.2, 0.0, 1.2, 2.4]:
            create_box(root, "pass31 rear archive slim cartridge", Vec3(x, 8.22, 2.18), Vec3(0.12, 0.16, 0.36), (0.070, 0.105, 0.145, 1), emission=(0.0, 0.012, 0.026, 1))
        # Pass 32: compact observatory robots.  They are snapped to station bays so they
        # read as useful crew tools, not loose props in the walking lane.
        self.robot_nodes = []
        self.robot_task_lines = []
        self.robot_status_lamps = []
        self.robot_home_positions = []
        def robot_unit(name: str, pos: Vec3, accent: tuple[float, float, float, float], h: float = 180) -> None:
            bot = root.attachNewNode(f"robot crew {name}")
            bot.setPos(pos)
            bot.setHpr(h, 0, 0)
            create_box(bot, "robot low charging pad", Vec3(0, 0.0, 0.16), Vec3(0.76, 0.54, 0.08), (0.035, 0.048, 0.070, 1), emission=(0.0, 0.010, 0.028, 1))
            create_cylinder_y(bot, "robot solid torso core", Vec3(0, 0.0, 0.52), 0.23, 0.46, 12, (0.19, 0.23, 0.29, 1), hpr=Vec3(90, 0, 0), emission=(0.004, 0.006, 0.012, 1))
            create_uv_sphere(bot, "robot sensor dome", Vec3(0, -0.05, 0.88), 0.23, 10, 16, (0.33, 0.40, 0.48, 1), emission=(0.010, 0.014, 0.020, 1))
            create_box(bot, "robot optical slit", Vec3(0, -0.255, 0.89), Vec3(0.30, 0.028, 0.060), accent, emission=(accent[0]*0.24, accent[1]*0.24, accent[2]*0.32, 1))
            create_box(bot, "robot tool arm left", Vec3(-0.29, -0.03, 0.56), Vec3(0.08, 0.36, 0.08), (0.10, 0.13, 0.17, 1), hpr=Vec3(0, 0, -12), emission=(0.002, 0.004, 0.008, 1))
            create_box(bot, "robot tool arm right", Vec3(0.29, -0.03, 0.56), Vec3(0.08, 0.36, 0.08), (0.10, 0.13, 0.17, 1), hpr=Vec3(0, 0, 12), emission=(0.002, 0.004, 0.008, 1))
            self.robot_nodes.append(bot)
            self.robot_home_positions.append(Vec3(pos))
            label(name.upper(), pos + Vec3(0, -0.36, 1.18), 0.044, (0.72, 0.94, 1.0, 0.62))
        robot_unit("Survey Bot", Vec3(-1.85, -6.20, 0.0), neon, 180)
        robot_unit("Lab Bot", Vec3(2.05, -1.15, 0.0), violet, 180)
        robot_unit("Archive Bot", Vec3(-2.05, 5.25, 0.0), green, 180)
        create_box(root, "pass32 robot task rail", Vec3(0, -6.34, 1.78), Vec3(4.68, 0.055, 0.28), (0.018, 0.035, 0.060, 0.92), emission=(0.0, 0.025, 0.070, 1))
        for i, z in enumerate([1.90, 1.80, 1.70]):
            self.robot_task_lines.append(label("--", Vec3(0, -6.39, z), 0.045 if i else 0.050, (0.70, 0.96, 1.0, 0.76)))
        for i, x in enumerate([-1.45, 0.0, 1.45]):
            lamp = create_box(root, "pass32 robot task lamp", Vec3(x, -6.43, 1.54), Vec3(0.44, 0.038, 0.050), neon, emission=(0.0, 0.075, 0.20, 1))
            self.robot_status_lamps.append(lamp)
        # Update the station and robot readouts now that the nodes exist.
        self.update_observatory_station_panels()
        self.update_research_panels()

        # Section lighting: strong enough for verification, still calm for play.
        for pos, color, strength in [
            (Vec3(0, -7.45, 2.72), Vec4(0.0, 0.56, 1.0, 1), 1.25),
            (Vec3(-3.6, -4.7, 2.45), Vec4(0.24, 0.56, 1.0, 1), 0.72),
            (Vec3(3.6, -1.5, 2.48), Vec4(0.64, 0.40, 1.0, 1), 0.70),
            (Vec3(0, 0.55, 2.68), Vec4(0.45, 0.68, 1.0, 1), 1.08),
            (Vec3(3.6, 6.0, 2.40), Vec4(1.0, 0.48, 0.15, 1), 0.62),
            (Vec3(-3.6, 6.0, 2.40), Vec4(0.22, 1.0, 0.58, 1), 0.62),
            (Vec3(0, 8.0, 2.45), Vec4(0.0, 0.72, 1.0, 1), 0.90),
        ]:
            plight = PointLight("interior octagonal section point")
            plight.setColor(color * strength)
            plight.setAttenuation((1, 0.045, 0.009))
            np = root.attachNewNode(plight)
            np.setPos(pos)
            root.setLight(np)

    def make_world_text(self, parent: NodePath, text: str, pos: Vec3, scale: float, color: tuple[float, float, float, float], hpr: Vec3) -> NodePath:
        node = TextNode(text)
        node.setText(text)
        node.setAlign(TextNode.ACenter)
        node.setTextColor(*color)
        np = parent.attachNewNode(node)
        np.setPos(pos)
        np.setHpr(hpr)
        np.setScale(scale)
        return np

    def make_hud_card(self, name: str, frame: tuple[float, float, float, float], color: tuple[float, float, float, float], sort: int = 1) -> NodePath:
        cm = CardMaker(name)
        cm.setFrame(*frame)
        card = self.aspect2d.attachNewNode(cm.generate())
        card.setTransparency(TransparencyAttrib.M_alpha)
        card.setColor(*color)
        card.setDepthWrite(False)
        card.setBin("fixed", sort)
        return card

    def build_hud(self) -> None:
        """Pass 21: strict minimal corner HUD.

        All essential information stays in the four corners.  The center only keeps a
        tiny reticle, and active prompts remain short enough to avoid covering the ship,
        planet, or anomaly.
        """
        self.hud_elements: list[NodePath] = []
        self.hud_cards: list[NodePath] = []

        # Small transparent corner cards only.  These preserve the playable view and avoid UI overlap.
        panel_specs = [
            ("hud tl micro panel", (-1.34, -1.04, 0.900, 0.965), (0.00, 0.07, 0.13, 0.05), 1),
            ("hud tr micro panel", (0.97, 1.34, 0.900, 0.965), (0.00, 0.07, 0.13, 0.04), 1),
            ("hud bl prompt panel", (-1.34, -0.93, -0.965, -0.890), (0.00, 0.06, 0.11, 0.04), 1),
            ("hud br status panel", (0.91, 1.34, -0.965, -0.815), (0.00, 0.06, 0.11, 0.05), 1),
        ]
        for spec in panel_specs:
            card = self.make_hud_card(*spec)
            self.hud_cards.append(card)
            self.hud_elements.append(card)

        # Micro accent lines, one per corner.  No big boxes in the gameplay view.
        for name, frame, color in [
            ("hud tl accent", (-1.34, -1.04, 0.895, 0.901), (0.0, 0.78, 1.0, 0.28)),
            ("hud tr accent", (0.97, 1.34, 0.895, 0.901), (0.0, 0.78, 1.0, 0.26)),
            ("hud bl accent", (-1.34, -0.93, -0.890, -0.884), (0.0, 0.78, 1.0, 0.26)),
            ("hud br accent", (0.91, 1.34, -0.815, -0.809), (0.0, 0.78, 1.0, 0.28)),
        ]:
            card = self.make_hud_card(name, frame, color, sort=2)
            self.hud_cards.append(card)
            self.hud_elements.append(card)

        self.title_text = OnscreenText(
            text="STARFALL",
            pos=(-1.30, 0.928), scale=0.023,
            align=TextNode.ALeft, fg=(0.66, 0.93, 1.0, 0.90), mayChange=True,
        )
        self.chunk_text = OnscreenText(
            text=f"{self.current_chunk_name}",
            pos=(1.30, 0.928), scale=0.021,
            align=TextNode.ARight, fg=(0.83, 0.94, 1.0, 0.88), mayChange=True,
        )
        self.objective_header_text = OnscreenText(
            text="SURVEY",
            pos=(0.94, -0.842), scale=0.020,
            align=TextNode.ALeft, fg=(0.56, 0.88, 1.0, 0.85), mayChange=True,
        )
        self.objective_text = OnscreenText(
            text="LENS + LMB",
            pos=(1.30, -0.842), scale=0.020,
            align=TextNode.ARight, fg=(0.86, 0.96, 1.0, 0.88), mayChange=True,
        )
        self.scan_text = OnscreenText(
            text="SCAN --",
            pos=(0.94, -0.882), scale=0.019,
            align=TextNode.ALeft, fg=(0.58, 0.86, 1.0, 0.82), mayChange=True,
        )
        self.salvage_text = OnscreenText(
            text="SAMPLE --",
            pos=(0.94, -0.922), scale=0.019,
            align=TextNode.ALeft, fg=(0.58, 0.86, 1.0, 0.82), mayChange=True,
        )
        self.gateway_text = OnscreenText(
            text="GATE --",
            pos=(0.94, -0.958), scale=0.019,
            align=TextNode.ALeft, fg=(0.58, 0.86, 1.0, 0.82), mayChange=True,
        )
        self.systems_text = OnscreenText(
            text=f"CLR {self.systems_completed}",
            pos=(1.30, 0.902), scale=0.018,
            align=TextNode.ARight, fg=(0.43, 0.72, 0.95, 0.76), mayChange=True,
        )
        self.lens_text = OnscreenText(
            text="LMB WARP",
            pos=(-1.30, -0.928), scale=0.020,
            align=TextNode.ALeft, fg=(0.66, 0.92, 1.0, 0.82), mayChange=True,
        )
        self.mode_text = OnscreenText(
            text="FLIGHT",
            pos=(-1.30, -0.902), scale=0.019,
            align=TextNode.ALeft, fg=(0.60, 0.86, 1.0, 0.82), mayChange=True,
        )
        self.crosshair = OnscreenText(
            text="+", pos=(0, -0.002), scale=0.026,
            align=TextNode.ACenter, fg=(0.58, 0.95, 1.0, 0.46), mayChange=True,
        )

        self.hud_elements.extend([
            self.title_text, self.chunk_text, self.objective_header_text, self.objective_text,
            self.scan_text, self.salvage_text, self.gateway_text, self.systems_text,
            self.lens_text, self.mode_text, self.crosshair,
        ])

        # Tiny mission bars tucked into bottom-right.  They are short enough not to invade the view.
        self.hud_bars: dict[str, NodePath] = {}
        bar_specs = [
            ("scan", 1.08, -0.886, (0.10, 0.64, 1.0, 0.56)),
            ("salvage", 1.08, -0.926, (0.25, 1.00, 0.72, 0.56)),
            ("gateway", 1.08, -0.961, (1.00, 0.62, 0.22, 0.56)),
        ]
        for key, x, z, col in bar_specs:
            back = self.make_hud_card(f"hud {key} microbar back", (0.0, 0.22, 0.0, 0.010), (0.02, 0.13, 0.20, 0.32), sort=3)
            back.setPos(x, 0, z)
            fill = self.make_hud_card(f"hud {key} microbar fill", (0.0, 0.22, 0.0, 0.010), col, sort=4)
            fill.setPos(x, 0, z)
            fill.setScale(0.02, 1, 1)
            self.hud_elements.extend([back, fill])
            self.hud_bars[key] = fill

        # Tiny reticle ticks only.  Center remains mostly clear.
        self.reticle_cards: list[NodePath] = []
        for name, frame in [
            ("reticle upper", (-0.0015, 0.0015, 0.024, 0.038)),
            ("reticle lower", (-0.0015, 0.0015, -0.038, -0.024)),
            ("reticle left", (-0.038, -0.024, -0.0015, 0.0015)),
            ("reticle right", (0.024, 0.038, -0.0015, 0.0015)),
        ]:
            tick = self.make_hud_card(name, frame, (0.22, 0.88, 1.0, 0.28), sort=5)
            self.reticle_cards.append(tick)
            self.hud_elements.append(tick)

        cm = CardMaker("warp transition overlay")
        cm.setFrame(-2.0, 2.0, -2.0, 2.0)
        self.warp_overlay = self.aspect2d.attachNewNode(cm.generate())
        self.warp_overlay.setTransparency(TransparencyAttrib.M_alpha)
        self.warp_overlay.setColor(0.04, 0.32, 0.95, 0.0)
        self.warp_overlay.setDepthWrite(False)
        self.warp_overlay.setBin("fixed", 20)
        self.warp_overlay.hide()

        self.hud_minimal_elements = [
            self.title_text, self.chunk_text, self.lens_text, self.mode_text, self.crosshair,
            *getattr(self, "reticle_cards", []),
        ]
        self.hud_compact_elements = list(dict.fromkeys([
            *self.hud_minimal_elements, self.objective_header_text, self.objective_text,
            self.scan_text, self.salvage_text, self.gateway_text,
            *getattr(self, "hud_cards", []), *getattr(self, "hud_bars", {}).values(),
        ]))
        self.hud_full_elements = list(dict.fromkeys(getattr(self, "hud_elements", [])))
        self.apply_shell_hud_level(getattr(self, "shell_hud_level", "MINIMAL"))
        self.update_objective_text()

    # -----------------------------
    # Mode management
    # -----------------------------
    def toggle_mode(self) -> None:
        if getattr(self, "operation_active", False):
            return
        self.set_mode("interior" if self.mode == "flight" else "flight")

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        if mode == "flight":
            self.flight_root.show()
            self.interior_root.hide()
            self.crosshair.show()
            for tick in getattr(self, "reticle_cards", []):
                tick.show()
            self.chunk_text.setText(self.current_chunk_name)
            self.mode_text.setText("FLT")
            if self.current_chunk_name == "Anchor Drydock":
                self.set_context_prompt("LMB WARP")
                self.set_reticle_color((0.48, 0.90, 1.0, 0.58))
        else:
            self.flight_root.hide()
            self.interior_root.show()
            self.crosshair.show()
            for tick in getattr(self, "reticle_cards", []):
                tick.show()
            self.player_pos = Vec3(0, 176.0, 1.72)
            self.interior_heading = INTERIOR_SPAWN_HEADING
            self.interior_pitch = 0.0
            self.chunk_text.setText("INTERIOR")
            self.set_context_prompt("LMB OPEN SATURN OPS MAP")
            self.mode_text.setText("OPS")
        self.update_objective_text()

    def build_operation_overlay(self) -> None:
        """Universal minimal Operation: Starfall overlay used by all moon operations."""
        root = self.aspect2d.attachNewNode("operation_starfall_universal_overlay")
        root.setBin("fixed", 9000)
        root.setDepthTest(False)
        root.setDepthWrite(False)
        root.hide()
        self.operation_overlay_root = root
        self.operation_overlay_nodes: list[NodePath] = []

        def label(name: str, text: str, pos: tuple[float, float], scale: float, align, fg: tuple[float, float, float, float]) -> OnscreenText:
            node = OnscreenText(text=text, parent=root, pos=pos, scale=scale, align=align, fg=fg, mayChange=True)
            self.operation_overlay_nodes.append(node)
            return node

        self.op_title_text = label("op title", "STARFALL OPS", (-1.30, 0.715), 0.024, TextNode.ALeft, (0.65, 0.94, 1.0, 0.62))
        self.op_location_text = label("op location", "LOCATION --", (0.0, 0.715), 0.022, TextNode.ACenter, (0.88, 0.97, 1.0, 0.72))
        # Pass113: live operation telemetry belongs in the monitor bezel, not
        # inside the planet display region where the feed camera can overwrite it.
        self.op_objective_text = label("op objective", "REMOTE OPERATION", (-1.30, -0.820), 0.024, TextNode.ALeft, (0.86, 0.97, 1.0, 0.94))
        self.op_status_text = label("op status", "DRONE LINK READY", (1.30, -0.820), 0.022, TextNode.ARight, (0.96, 0.99, 1.0, 0.92))
        self.op_controls_text = label("op controls", "REMOTE DRONE CONTROL  //  TAB DISCONNECT", (0.0, -0.872), 0.020, TextNode.ACenter, (0.70, 0.92, 1.0, 0.86))
        self.op_crosshair_text = label("op crosshair", "+", (0.0, -0.002), 0.032, TextNode.ACenter, (0.62, 0.95, 1.0, 0.46))

    def _show_operation_overlay(self, code: str) -> None:
        root = getattr(self, "operation_overlay_root", None)
        if root is not None and not root.isEmpty():
            root.show()
        self.update_operation_overlay(code)

    def _hide_operation_overlay(self) -> None:
        root = getattr(self, "operation_overlay_root", None)
        if root is not None and not root.isEmpty():
            root.hide()

    def update_operation_overlay(self, code: str | None = None) -> None:
        app = getattr(self, "operation_app", None)
        target = OPERATION_TARGETS.get(
            code
            or getattr(self, "current_operation_code", "")
            or getattr(self, "pending_operation_code", "")
            or "MIMAS",
            {},
        )
        title = str(target.get("title", "Surface Operation")).upper()
        if hasattr(self, "op_location_text"):
            self.op_location_text.setText(title)
        objective = str(target.get("mission", "Survey, drill, collect, return"))
        action_state = ""
        action_progress = 0
        action_payload = None
        if app is not None:
            payload_factory = getattr(app, "_standard_action_payload", None)
            if callable(payload_factory):
                try:
                    candidate = payload_factory()
                    if isinstance(candidate, dict):
                        action_payload = candidate
                except Exception:
                    action_payload = None
        if action_payload:
            objective = str(action_payload.get("hint", objective) or objective).upper()
            action_state = str(action_payload.get("state", "") or "").replace("_", " ")
            try:
                action_progress = max(0, min(100, int(action_payload.get("progress", 0) or 0)))
            except Exception:
                action_progress = 0
        if len(objective) > 48:
            objective = objective[:45] + "..."
        if hasattr(self, "op_objective_text"):
            self.op_objective_text.setText(objective)
        telemetry = "SURFACE LINK ACTIVE"
        if app is not None:
            msg = str(getattr(app, "last_status_message", "") or "")
            active = int(getattr(app, "active_rig_index", -1)) if hasattr(app, "active_rig_index") else -1
            rigs = getattr(app, "rigs", []) if hasattr(app, "rigs") else []
            if 0 <= active < len(rigs):
                rig = rigs[active]
                signal = float(rig.get("signal", 0.0)) if isinstance(rig, dict) else 0.0
                depth = float(rig.get("line_depth", 0.0)) if isinstance(rig, dict) else 0.0
                telemetry = f"LINE {depth:04.0f}M SIG {signal*100:03.0f}%"
            else:
                sonar = getattr(app, "current_sonar", {})
                if isinstance(sonar, dict):
                    telemetry = f"SONAR {float(sonar.get('signal', 0.0))*100:03.0f}%"
                elif msg:
                    telemetry = msg[:32]
        status = telemetry
        if action_state:
            status = f"{action_state} {action_progress:03d}% // {telemetry}"
        if len(status) > 38:
            status = status[:35] + "..."
        if hasattr(self, "op_status_text"):
            self.op_status_text.setText(status)

    def apply_shell_hud_level(self, level: str | None = None) -> None:
        level = str(level or getattr(self, "shell_hud_level", "MINIMAL")).upper()
        if level not in SHELL_HUD_LEVELS:
            level = "MINIMAL"
        self.shell_hud_level = level
        self.hud_visible = level != "HIDDEN"
        for element in getattr(self, "hud_full_elements", getattr(self, "hud_elements", [])):
            try:
                if element is not None and not element.isEmpty():
                    element.hide()
            except Exception:
                pass
        if self._shell_panel_open():
            self.shell_panel_hud_suppressed = True
            return
        visible = []
        if level == "MINIMAL":
            visible = getattr(self, "hud_minimal_elements", [])
        elif level == "COMPACT":
            visible = getattr(self, "hud_compact_elements", [])
        elif level == "FULL":
            visible = getattr(self, "hud_full_elements", getattr(self, "hud_elements", []))
        for element in visible:
            try:
                if element is not None and not element.isEmpty():
                    element.show()
            except Exception:
                pass

    def toggle_hud(self) -> None:
        current = getattr(self, "shell_hud_level", "MINIMAL").upper()
        try:
            idx = SHELL_HUD_LEVELS.index(current)
        except ValueError:
            idx = 0
        next_level = SHELL_HUD_LEVELS[(idx + 1) % len(SHELL_HUD_LEVELS)]
        self.apply_shell_hud_level(next_level)
        self.set_loop_feedback(f"HUD {next_level}", 1.0)
        # Keep the warp overlay independent of HUD visibility.

    def reset_ship(self) -> None:
        self.ship.setPos(0, -2.0, 2.5)
        self.ship.setHpr(0, 0, 0)
        self.ship_velocity = Vec3(0, 0, 0)
        self.ship_yaw = self.ship_pitch = self.ship_roll = 0.0

    def pulse_engine_flare(self) -> None:
        if self.mode == "flight":
            for glow in self.engine_glows:
                glow.setScale(1.18)

    # -----------------------------
    # Update loop
    # -----------------------------
    def update(self, task: Task) -> int:
        if getattr(self, "operation_active", False):
            self.update_operation_overlay()
            return Task.cont
        dt = min(self.globalClock.getDt(), 1.0 / 20.0)
        if self._shell_panel_open():
            self.controls = ControlState()
            self.scan_held = False
            self.update_warp_transition(dt)
            return Task.cont
        self.process_mouse(dt)
        if self.mode == "flight":
            self.update_flight(dt)
            # Pass 15: target/scan checks do not need to run every render frame.
            # This preserves input feel while reducing repeated projection and NodePath work.
            self._lensing_accum += dt
            if self._lensing_accum >= 0.095:
                lens_dt = self._lensing_accum
                self._lensing_accum = 0.0
                self.update_lensing_targets(lens_dt)
            self._gameplay_accum += dt
            if self._gameplay_accum >= 0.145:
                gameplay_dt = self._gameplay_accum
                self._gameplay_accum = 0.0
                self.update_gameplay_targets(gameplay_dt)
        else:
            self.update_interior(dt)
        self.update_warp_transition(dt)
        return Task.cont

    def process_mouse(self, dt: float) -> None:
        if self._shell_panel_open():
            return
        if not self.mouseWatcherNode or not self.mouseWatcherNode.hasMouse() or not self.win or not self.window_centered:
            return
        props = self.win.getProperties()
        cx, cy = props.getXSize() // 2, props.getYSize() // 2
        pointer = self.win.getPointer(0)
        dx = pointer.getX() - cx
        dy = pointer.getY() - cy
        if dx == 0 and dy == 0:
            return
        if self.mode == "flight":
            self.ship_yaw -= dx * 0.07
            self.ship_pitch = max(-38, min(38, self.ship_pitch - dy * 0.055))
        else:
            self.interior_heading -= dx * 0.08
            self.interior_pitch = max(-72, min(72, self.interior_pitch - dy * 0.065))
        self.win.movePointer(0, cx, cy)

    def update_flight(self, dt: float) -> None:
        thrust = Vec3(0, 0, 0)
        speed = 16.0 * (2.0 if self.controls.boost else 1.0)
        if self.controls.forward:
            thrust.y -= speed
        if self.controls.back:
            thrust.y += speed * 0.55
        if self.controls.left:
            thrust.x -= speed * 0.6
        if self.controls.right:
            thrust.x += speed * 0.6
        if self.controls.up:
            thrust.z += speed * 0.42
        if self.controls.down:
            thrust.z -= speed * 0.42
        if self.controls.roll_l:
            self.ship_roll += 85 * dt
        if self.controls.roll_r:
            self.ship_roll -= 85 * dt
        self.ship_roll *= (1.0 - min(dt * 1.8, 1.0))

        # Forward vector follows ship heading. Strafe/up use ship local axes.
        self.ship.setHpr(self.ship_yaw, self.ship_pitch, self.ship_roll)
        quat = self.ship.getQuat(self.render)
        world_thrust = quat.xform(thrust)
        self.ship_velocity += world_thrust * dt
        self.ship_velocity *= 0.975
        if self.ship_velocity.length() > 32:
            self.ship_velocity.normalize()
            self.ship_velocity *= 32
        self.ship.setPos(self.ship.getPos() + self.ship_velocity * dt)

        # Idle presentation drift and engine pulse.
        t = task_time()
        self._cosmic_anim_accum += dt
        animate_slow_cosmos = self._cosmic_anim_accum >= 0.330
        slow_dt = self._cosmic_anim_accum if animate_slow_cosmos else 0.0
        if animate_slow_cosmos:
            self._cosmic_anim_accum = 0.0
            self._cosmic_anim_phase = (self._cosmic_anim_phase + 1) % 8
        pulse = 1.0 + math.sin(t * 5.0) * 0.06 + (0.18 if self.controls.boost or self.controls.forward else 0.0)
        for glow in self.engine_glows:
            glow.setScale(pulse)
        trail_power = 1.0 + (0.70 if self.controls.boost else 0.0) + (0.28 if self.controls.forward else 0.0)
        for idx, trail in enumerate(self.engine_trails):
            wave = 1.0 + math.sin(t * (6.0 + idx) + idx * 0.7) * 0.10
            trail.setScale(1.0 + 0.10 * wave, trail_power * wave, 1.0 + 0.10 * wave)
        for idx, beacon in enumerate(self.hangar_beacons):
            b = 0.55 + 0.45 * abs(math.sin(t * 2.4 + idx * 0.55))
            beacon.setColor(0.0, 0.48 + b * 0.30, 1.0, 1)
        for idx, node in enumerate(self.anomaly_fx_nodes):
            anim_kind = node.getTag("anomaly_anim") if not node.isEmpty() else ""
            if anim_kind == "hyper":
                node.setHpr(math.sin(t * 0.16 + idx * 0.5) * 6.0, math.sin(t * 0.10 + idx) * 2.2, (t * (7.0 + (idx % 5) * 0.55) + idx * 19) % 360)
                node.setColorScale(1.0, 1.0, 1.0, 0.78 + 0.18 * abs(math.sin(t * 0.95 + idx * 0.7)))
            elif anim_kind == "orbit":
                orbit_idx = int(node.getTag("orbit_index") or 0)
                phase = t * (0.55 + orbit_idx * 0.03) + orbit_idx * 0.8
                p = node.getPos()
                node.setPos(p.x, math.sin(phase) * 0.22, p.z)
                node.setHpr(0, 0, (phase * 40.0) % 360)
                node.setColorScale(1.0, 1.0, 1.0, 0.66 + 0.24 * abs(math.sin(phase * 1.3)))
            else:
                node.setHpr(math.sin(t * 0.18 + idx) * 1.8, 0, t * (3.5 + idx * 0.25) % 360)
                node.setColorScale(1.0, 1.0, 1.0, 0.70 + 0.28 * abs(math.sin(t * 0.8 + idx)))
        for idx, haze in enumerate(self.chunk_haze_nodes):
            haze.setHpr(0, 90, (t * (1.0 + idx * 0.20) + idx * 23) % 360)
            haze.setColorScale(1.0, 1.0, 1.0, 0.74 + 0.22 * math.sin(t * 0.55 + idx))
        for idx, accent_node in enumerate(self.ship_accent_nodes):
            accent_node.setColorScale(1.0, 1.0, 1.0, 0.82 + 0.18 * abs(math.sin(t * 2.0 + idx)))
        if animate_slow_cosmos:
            for idx, star in enumerate(self.cosmic_twinklers):
                if star.isEmpty():
                    continue
                # Very subtle twinkle so the sky feels alive without updating every render frame.
                star.setColorScale(1.0, 1.0, 1.0, 0.78 + 0.22 * abs(math.sin(t * (0.55 + (idx % 5) * 0.08) + idx * 0.7)))
            # Rotate/fade only one third of decorative cosmic roots per slow tick.
            # Gameplay targets still update in update_gameplay_targets, so collection feel is preserved.
            for idx, root in enumerate(self.organic_cosmic_roots):
                if root.isEmpty() or idx % 8 != self._cosmic_anim_phase:
                    continue
                root.setH(root.getH() + slow_dt * (0.18 + (idx % 5) * 0.055))
                root.setR(math.sin(t * 0.10 + idx) * 2.5)
                root.setColorScale(1.0, 1.0, 1.0, 0.82 + 0.18 * abs(math.sin(t * 0.24 + idx * 0.51)))

        # Third-person camera.
        q = self.ship.getQuat(self.render)
        target = self.ship.getPos() + q.xform(Vec3(0, 18.0, 6.2))
        look_at = self.ship.getPos() + q.xform(Vec3(0, -2.4, 0.95))
        current = self.camera.getPos()
        self.camera.setPos(current + (target - current) * min(dt * 5.2, 1.0))
        self.camera.lookAt(look_at)

    def update_interior(self, dt: float) -> None:
        move = Vec3(0, 0, 0)
        speed = 3.0 * (1.6 if self.controls.boost else 1.0)
        heading_rad = math.radians(self.interior_heading)
        forward = Vec3(-math.sin(heading_rad), math.cos(heading_rad), 0)
        right = Vec3(math.cos(heading_rad), math.sin(heading_rad), 0)
        if self.controls.forward:
            move += forward
        if self.controls.back:
            move -= forward
        if self.controls.right:
            move += right
        if self.controls.left:
            move -= right
        if move.length_squared() > 0:
            move.normalize()
            self.player_pos += move * speed * dt
        # Clamp to cabin walkable space; this keeps room traversal reliable without hidden collision bugs.
        self.player_pos.x = max(-4.75, min(4.75, self.player_pos.x))
        self.player_pos.y = max(167.20, min(184.65, self.player_pos.y))
        self.player_pos.z = 1.72
        # Interior research interaction: hold RMB at any station to let the crew robots process
        # the current randomized planet task.  This keeps the action inside the observatory.
        task_obj = self.current_research_task() if hasattr(self, "current_research_task") else None
        if self.scan_held and task_obj and not task_obj.complete:
            station_code = self.observatory_stations[self.observatory_station_index][0] if getattr(self, "observatory_stations", None) else "OBS"
            rate = dt * (1.45 if station_code == task_obj.station else 0.62) * self.scanner_range_multiplier()
            task_obj.progress = min(task_obj.seconds_required, task_obj.progress + rate)
            if task_obj.progress >= task_obj.seconds_required:
                self.complete_research_task(task_obj)
            else:
                self.set_context_prompt(f"{task_obj.station} RESEARCH {int(100*task_obj.progress/max(0.01, task_obj.seconds_required))}%")
                self.update_research_panels()
                self.update_objective_text()
        t = task_time()
        for i, bot in enumerate(getattr(self, "robot_nodes", [])):
            if bot.isEmpty():
                continue
            base = self.robot_home_positions[i] if i < len(self.robot_home_positions) else bot.getPos()
            bot.setZ(base.z + math.sin(t * (1.2 + i * 0.18) + i) * 0.025)
            bot.setH(bot.getH() + math.sin(t * 0.8 + i) * 0.06)
        self.camera.setPos(self.player_pos)
        self.camera.setHpr(self.interior_heading, self.interior_pitch, 0)

    def build_operation_display_panel(self) -> None:
        """Build the persistent 16:9 remote-drone monitor used by every planet operation."""
        root = self.aspect2d.attachNewNode("starfall_planet_drone_display")
        root.setBin("fixed", 8900)
        root.setDepthTest(False)
        root.setDepthWrite(False)
        root.setTransparency(TransparencyAttrib.MAlpha)
        root.setLightOff(1)
        root.hide()

        half_h = 0.78
        half_w = half_h * (16.0 / 9.0)
        self.operation_display_half_height = half_h
        self.operation_display_half_width = half_w
        self.operation_display_region_dims = (0.11, 0.89, 0.11, 0.89)

        outer = CardMaker("planet_drone_display_outer_frame")
        # Pass113 keeps the feed itself at the same 16:9 dimensions and only
        # extends the lower physical bezel to house readable shell telemetry.
        outer.setFrame(-half_w - 0.055, half_w + 0.055, -half_h - 0.145, half_h + 0.070)
        outer_np = root.attachNewNode(outer.generate())
        outer_np.setColor(0.010, 0.016, 0.024, 0.96)
        outer_np.setTransparency(TransparencyAttrib.MAlpha)
        outer_np.setBin("fixed", 8900)
        outer_np.setDepthTest(False)
        outer_np.setDepthWrite(False)

        surface = CardMaker("planet_drone_display_surface")
        surface.setFrame(-half_w, half_w, -half_h, half_h)
        surface_np = root.attachNewNode(surface.generate())
        surface_np.setColor(0.001, 0.004, 0.008, 1.0)
        surface_np.setBin("fixed", 8901)
        surface_np.setDepthTest(False)
        surface_np.setDepthWrite(False)
        self.operation_display_surface = surface_np

        self.operation_display_title = OnscreenText(
            text="REMOTE PLANETARY DRONE LINK", parent=root,
            pos=(-half_w + 0.025, half_h + 0.030), scale=0.026,
            align=TextNode.ALeft, fg=(0.60, 0.92, 1.0, 0.88), mayChange=True,
        )
        self.operation_display_status = OnscreenText(
            text="STANDBY", parent=root,
            pos=(half_w - 0.025, half_h + 0.030), scale=0.022,
            align=TextNode.ARight, fg=(0.72, 0.92, 1.0, 0.72), mayChange=True,
        )
        self.operation_display_root = root

    def _show_operation_display(self, code: str, status: str = "CONNECTING") -> None:
        root = getattr(self, "operation_display_root", None)
        if root is not None and not root.isEmpty():
            root.show()
        target = OPERATION_TARGETS.get(code, {})
        title = str(target.get("title", code)).upper()
        if self.operation_display_title is not None:
            self.operation_display_title.setText(f"REMOTE DRONE // {title}")
        if self.operation_display_status is not None:
            self.operation_display_status.setText(status)
        surface = getattr(self, "operation_display_surface", None)
        if surface is not None and not surface.isEmpty() and not getattr(self, "operation_active", False):
            surface.show()

    def _hide_operation_display(self) -> None:
        self._destroy_operation_feed_camera()
        root = getattr(self, "operation_display_root", None)
        if root is not None and not root.isEmpty():
            root.hide()
        if self.operation_display_status is not None:
            self.operation_display_status.setText("STANDBY")
        surface = getattr(self, "operation_display_surface", None)
        if surface is not None and not surface.isEmpty():
            surface.show()

    def _create_operation_feed_camera(self, operation_root: NodePath):
        """Create the planet-only camera/display region without surrendering the ship camera."""
        self._destroy_operation_feed_camera()
        if self.win is None:
            raise RuntimeError("Starfall window unavailable for remote drone feed")
        lens = self.camLens.makeCopy()
        camera = self.makeCamera(
            self.win,
            sort=10,
            scene=operation_root,
            displayRegion=self.operation_display_region_dims,
            lens=lens,
            camName="starfall_remote_planet_drone_camera",
        )
        camera.reparentTo(operation_root)
        display_region = None
        try:
            for idx in range(self.win.getNumDisplayRegions()):
                candidate = self.win.getDisplayRegion(idx)
                if candidate.getCamera() == camera:
                    display_region = candidate
                    break
        except Exception:
            display_region = None
        if display_region is None:
            camera.removeNode()
            raise RuntimeError("Remote drone feed display region was not created")
        display_region.setClearColorActive(True)
        display_region.setClearColor(Vec4(0.001, 0.004, 0.008, 1.0))
        display_region.setClearDepthActive(True)
        display_region.setActive(False)
        self.operation_feed_camera = camera
        self.operation_feed_display_region = display_region
        self.operation_feed_lens = camera.node().getLens()
        return camera

    def _destroy_operation_feed_camera(self) -> None:
        region = getattr(self, "operation_feed_display_region", None)
        if region is not None:
            try:
                region.setActive(False)
                if self.win is not None:
                    self.win.removeDisplayRegion(region)
            except Exception:
                pass
        camera = getattr(self, "operation_feed_camera", None)
        if camera is not None:
            try:
                if not camera.isEmpty():
                    camera.removeNode()
            except Exception:
                pass
        self.operation_feed_display_region = None
        self.operation_feed_camera = None
        self.operation_feed_lens = None

    def selected_operation_code(self) -> str:
        if not getattr(self, "observatory_stations", None):
            return "MIMAS"
        idx = max(0, min(getattr(self, "observatory_station_index", 0), len(self.observatory_stations) - 1))
        return str(self.observatory_stations[idx][0])

    def activate_selected_operation(self) -> None:
        code = self.selected_operation_code()
        target = OPERATION_TARGETS.get(code)
        if not target:
            self.set_loop_feedback("NO TARGET", 2.0)
            return
        if code == "ANOM":
            self.set_loop_feedback("ANOMALY ANALYSIS // INTERIOR ONLY", 1.8)
            return
        if target.get("status") != "READY" or not target.get("moon"):
            self.set_loop_feedback(f"{target.get('title', code)} PLANNED", 2.6)
            return
        self.begin_operation_loading(code)

    def begin_operation_loading(self, code: str) -> None:
        # One launch request owns the transition until the handoff either succeeds or fails.
        # This prevents rapid repeated input from retargeting the pending operation or
        # queuing multiple embedded-world constructors into the same ShowBase.
        if getattr(self, "operation_active", False) or getattr(self, "operation_loading_in_progress", False):
            self.set_loop_feedback("OPERATION LINK BUSY", 1.2)
            return
        target = OPERATION_TARGETS.get(code)
        if not target or target.get("status") != "READY" or not target.get("moon"):
            self.set_loop_feedback("OPERATION UNAVAILABLE", 1.8)
            return
        self.operation_loading_in_progress = True
        self.pending_operation_code = code
        self.controls = ControlState()
        self.scan_held = False
        self._show_operation_loading(code)
        self.set_loop_feedback(f"LOADING {target['title'].upper()}", 2.0)
        # Defensive cleanup in case an older/stale task survived a prior interrupted run.
        self.taskMgr.remove("finish_operation_loading")
        self.taskMgr.doMethodLater(1.10, self._finish_operation_loading, "finish_operation_loading")

    def _show_operation_loading(self, code: str) -> None:
        """Show destination loading art inside the ship's 16:9 remote-drone display."""
        self._clear_operation_loading()
        target = OPERATION_TARGETS[code]
        self._show_operation_display(code, "CONNECTING")

        hidden_nodes = []
        for node in list(getattr(self, "hud_elements", [])):
            try:
                if node is not None and not node.isEmpty() and not node.isHidden():
                    node.hide(); hidden_nodes.append(node)
            except Exception:
                pass
        for attr in ("operation_map_root", "pause_menu_root", "operation_overlay_root"):
            node = getattr(self, attr, None)
            try:
                if node is not None and not node.isEmpty() and not node.isHidden():
                    node.hide(); hidden_nodes.append(node)
            except Exception:
                pass
        self.operation_loading_hidden_nodes = hidden_nodes

        moon_code = str(target.get("moon", "enceladus")).lower()
        if moon_code not in {"mimas", "enceladus", "iapetus", "titan", "mars", "pluto", "europa", "triton"}:
            moon_code = "enceladus"
        art_path = Path(__file__).resolve().parent / "assets" / "generated" / f"operation_loading_{moon_code}.png"

        root = self.operation_display_root.attachNewNode("operation_starfall_loading_screen")
        root.setBin("fixed", 8950)
        root.setDepthTest(False)
        root.setDepthWrite(False)
        root.setTransparency(TransparencyAttrib.MAlpha)
        root.setLightOff(1)
        cm = CardMaker(f"operation_loading_{moon_code}_panel_art")
        cm.setFrame(
            -self.operation_display_half_width, self.operation_display_half_width,
            -self.operation_display_half_height, self.operation_display_half_height,
        )
        art = root.attachNewNode(cm.generate())
        art.setBin("fixed", 8951)
        art.setDepthTest(False)
        art.setDepthWrite(False)
        art.setTransparency(TransparencyAttrib.MAlpha)
        art.setLightOff(1)
        try:
            art.setTexture(self.loader.loadTexture(Filename.fromOsSpecific(str(art_path))), 1)
        except Exception as exc:
            print(f"[Operation StarFall] loading art fallback for {art_path}: {exc}")
            art.setColor(0.001, 0.006, 0.014, 1.0)
        self.operation_loading_root = root
        self.operation_loading_lines = []
        for _ in range(2):
            self.graphicsEngine.renderFrame()

    def _clear_operation_loading(self) -> None:
        root = getattr(self, "operation_loading_root", None)
        if root is not None and not root.isEmpty():
            root.removeNode()
        self.operation_loading_root = None
        self.operation_loading_lines = []
        hidden_nodes = getattr(self, "operation_loading_hidden_nodes", [])
        self.operation_loading_hidden_nodes = []
        # The physical ship/interior remains visible around the panel. Shell HUD returns
        # only after the remote operation disconnects or a launch fails.
        if not getattr(self, "operation_active", False):
            for node in hidden_nodes:
                try:
                    if node is not None and not node.isEmpty():
                        node.show()
                except Exception:
                    pass
            if not getattr(self, "operation_loading_in_progress", False):
                root = getattr(self, "operation_display_root", None)
                if root is not None and not root.isEmpty():
                    root.hide()

    def _finish_operation_loading(self, task: Task) -> int:
        # A stale duplicate task must never construct a second embedded app.
        if getattr(self, "operation_active", False):
            self.operation_loading_in_progress = False
            return Task.done
        if not getattr(self, "operation_loading_in_progress", False):
            return Task.done
        code = self.pending_operation_code or "MIMAS"
        try:
            self.start_embedded_world_operation(code)
        except Exception as exc:
            self.operation_loading_in_progress = False
            self.pending_operation_code = None
            self.operation_last_error = str(exc)
            self._clear_operation_loading()
            self.set_loop_feedback(f"OPERATION LOAD FAILED: {exc}", 5.0)
            self.write_operation_error(code, exc)
        else:
            self.operation_loading_in_progress = False
        return Task.done

    def write_operation_error(self, code: str, exc: Exception) -> None:
        try:
            reports = Path(__file__).resolve().parent / "verification" / "reports"
            reports.mkdir(parents=True, exist_ok=True)
            (reports / "operation_error.json").write_text(json.dumps({"target": code, "error": str(exc)}, indent=2))
        except Exception:
            pass

    def gxtool_bridge_scene_state(self) -> dict[str, object]:
        """Return compact StarFall state for GXTool runtime proof runs.

        GXTool calls this only when its optional smoke/runtime hook is active.
        Normal gameplay does not depend on GXTool and does not consume this data.
        """
        surface = getattr(self, "win", None)
        if surface is None:
            window_size = [0, 0]
        else:
            try:
                if hasattr(surface, "getProperties"):
                    props = surface.getProperties()
                    window_size = [int(props.getXSize()), int(props.getYSize())]
                else:
                    window_size = [int(surface.getXSize()), int(surface.getYSize())]
            except Exception:
                window_size = [0, 0]
        try:
            residue = self._count_operation_residue()
        except Exception:
            residue = {"render_roots": -1, "ui_roots": -1}
        operation_app = getattr(self, "operation_app", None)
        return {
            "project": "Operation StarFall",
            "build": "Operation_StarFall_Pass114_PlutoTerrainVisualCleanup",
            "mode": str(getattr(self, "mode", "")),
            "current_chunk": str(getattr(self, "current_chunk_name", "")),
            "shell_hud_level": str(getattr(self, "shell_hud_level", "")),
            "interior_heading": float(getattr(self, "interior_heading", 0.0)),
            "operation_active": bool(getattr(self, "operation_active", False)),
            "operation_loading_in_progress": bool(getattr(self, "operation_loading_in_progress", False)),
            "pending_operation_code": getattr(self, "pending_operation_code", None),
            "embedded_operation_present": operation_app is not None,
            "planet_display_visible": bool(getattr(self, "operation_display_root", None) is not None and not self.operation_display_root.isHidden()),
            "planet_feed_active": bool(getattr(self, "operation_feed_display_region", None) is not None and self.operation_feed_display_region.isActive()),
            "operation_residue": residue,
            "operation_lifecycle": self._operation_lifecycle_state(),
            "window_size": window_size,
        }

    def _count_operation_residue(self) -> dict[str, int]:
        render_count = 0
        ui_count = 0
        try:
            for child in self.render.getChildren():
                if child.getName().startswith("embedded_world_operation_"):
                    render_count += 1
        except Exception:
            pass
        try:
            for child in self.aspect2d.getChildren():
                if child.getName().startswith("embedded_world_operation_ui_"):
                    ui_count += 1
        except Exception:
            pass
        return {"render_roots": render_count, "ui_roots": ui_count}

    def _clear_operation_module_cache(self) -> None:
        import sys as _sys
        try:
            _sys.modules.pop("operation_starfall_worlds_main", None)
        except Exception:
            pass

    def _stash_shell_for_operation(self) -> None:
        """Freeze the ship interior while a remote planetary drone owns the control link."""
        if self.operation_shell_snapshot is None:
            self.operation_shell_snapshot = {
                "camera_parent": self.camera.getParent(),
                "camera_pos_render": Vec3(self.camera.getPos(self.render)),
                "camera_hpr_render": Vec3(self.camera.getHpr(self.render)),
                "mode": str(getattr(self, "mode", "interior")),
            }
        self.controls = ControlState()
        self.scan_held = False
        self.ship_velocity = Vec3(0, 0, 0)
        # Pass108 authority: the player never leaves the observatory. Flight stays hidden
        # and the current interior view remains visible around the 16:9 drone monitor.
        self.flight_root.hide()
        self.interior_root.show()
        self.mode = "interior"
        for element in getattr(self, "hud_elements", []):
            try:
                element.hide()
            except Exception:
                pass

    def _give_camera_to_operation(self, app) -> None:
        operation_root = getattr(app, "operation_render_root", None)
        feed_camera = getattr(app, "camera", None)
        if operation_root is None or operation_root.isEmpty():
            raise RuntimeError("Embedded operation did not create a render authority root")
        if feed_camera is None or feed_camera.isEmpty() or feed_camera == self.camera:
            raise RuntimeError("Embedded operation did not adopt the remote drone feed camera")
        self.operation_camera_root = feed_camera
        region = getattr(self, "operation_feed_display_region", None)
        if region is None:
            raise RuntimeError("Remote drone feed display region is unavailable")
        region.setActive(True)
        surface = getattr(self, "operation_display_surface", None)
        if surface is not None and not surface.isEmpty():
            surface.hide()
        self._show_operation_display(getattr(self, "current_operation_code", "MIMAS") or "MIMAS", "DRONE LINK ACTIVE")
        if surface is not None and not surface.isEmpty():
            surface.hide()

    def _reclaim_camera_from_operation(self) -> None:
        # The shell camera never leaves the interior in Pass108. Reclaiming the
        # operation means deleting only the dedicated planet display camera/region.
        self._destroy_operation_feed_camera()
        self.operation_camera_root = None

    def _force_clear_operation_residue(self, module=None) -> dict[str, int]:
        """Shell-owned fallback cleanup for interrupted embedded operations.

        The embedded app normally cleans itself. Pass109 keeps the shell capable of
        removing roots/tasks even when a constructor or shutdown fails before normal
        ownership can complete.
        """
        removed_tasks = 0
        task_names: tuple[str, ...] = ()
        try:
            operation_cls = getattr(module, "EnceladusIce", None) if module is not None else None
            task_name_factory = getattr(operation_cls, "_operation_task_names", None)
            if callable(task_name_factory):
                task_names = tuple(task_name_factory(None))
        except Exception:
            task_names = ()
        for task_name in (*task_names, "finish_operation_loading"):
            try:
                before = len([task for task in self.taskMgr.getTasks() if str(task.getName()) == task_name])
                before += len([task for task in self.taskMgr.getDoLaters() if str(task.getName()) == task_name])
                self.taskMgr.remove(task_name)
                removed_tasks += before
            except Exception:
                pass

        removed_render_roots = 0
        removed_ui_roots = 0
        for parent, prefix, counter_name in (
            (self.render, "embedded_world_operation_", "render"),
            (self.aspect2d, "embedded_world_operation_ui_", "ui"),
        ):
            try:
                for child in list(parent.getChildren()):
                    if child.getName().startswith(prefix):
                        child.removeNode()
                        if counter_name == "render":
                            removed_render_roots += 1
                        else:
                            removed_ui_roots += 1
            except Exception:
                pass
        return {
            "removed_tasks": removed_tasks,
            "removed_render_roots": removed_render_roots,
            "removed_ui_roots": removed_ui_roots,
        }

    def _cleanup_partial_embedded_operation(self, module) -> dict[str, int]:
        """Recover an instance whose embedded constructor never returned."""
        partial = getattr(module, "EMBEDDED_INSTANCE", None) if module is not None else None
        if partial is not None:
            try:
                partial.shutdown_embedded_operation()
            except Exception as exc:
                self.operation_last_error = f"partial launch cleanup: {exc}"
        self._reclaim_camera_from_operation()
        cleanup = self._force_clear_operation_residue(module)
        try:
            if module is not None:
                module.EMBEDDED_INSTANCE = None
        except Exception:
            pass
        return cleanup

    def _operation_lifecycle_state(self) -> dict[str, object]:
        state: dict[str, object] = dict(self._count_operation_residue())
        region = getattr(self, "operation_feed_display_region", None)
        camera = getattr(self, "operation_feed_camera", None)
        loading_root = getattr(self, "operation_loading_root", None)
        display_root = getattr(self, "operation_display_root", None)
        try:
            region_active = bool(region is not None and region.isActive())
        except Exception:
            region_active = False
        state.update({
            "feed_region_present": region is not None,
            "feed_region_active": region_active,
            "feed_camera_present": bool(camera is not None and not camera.isEmpty()),
            "loading_root_present": bool(loading_root is not None and not loading_root.isEmpty()),
            "display_visible": bool(display_root is not None and not display_root.isEmpty() and not display_root.isHidden()),
            "finish_loading_tasks": len([task for task in self.taskMgr.getDoLaters() if str(task.getName()) == "finish_operation_loading"]),
            "mode": str(getattr(self, "mode", "")),
            "interior_visible": bool(self.interior_root is not None and not self.interior_root.isEmpty() and not self.interior_root.isHidden()),
            "flight_visible": bool(self.flight_root is not None and not self.flight_root.isEmpty() and not self.flight_root.isHidden()),
        })
        return state

    def _operation_lifecycle_is_clean(self, state: dict[str, object] | None = None) -> bool:
        state = state or self._operation_lifecycle_state()
        return bool(
            int(state.get("render_roots", 0) or 0) == 0
            and int(state.get("ui_roots", 0) or 0) == 0
            and not bool(state.get("feed_region_present"))
            and not bool(state.get("feed_region_active"))
            and not bool(state.get("feed_camera_present"))
            and not bool(state.get("loading_root_present"))
            and not bool(state.get("display_visible"))
            and int(state.get("finish_loading_tasks", 0) or 0) == 0
            and str(state.get("mode", "")) == "interior"
            and bool(state.get("interior_visible"))
            and not bool(state.get("flight_visible"))
        )

    def _restore_shell_after_operation(self, *, failed_launch: bool = False) -> None:
        snapshot = self.operation_shell_snapshot or {}
        for root in (self.flight_root, self.interior_root):
            try:
                if root is not None and not root.isEmpty():
                    root.unstash()
            except Exception:
                pass
        if failed_launch:
            mode = str(snapshot.get("mode", "interior"))
            self.set_mode(mode if mode in {"flight", "interior"} else "interior")
            try:
                self.camera.setPos(self.render, Vec3(snapshot.get("camera_pos_render", Vec3(0, 176, 1.72))))
                self.camera.setHpr(self.render, Vec3(snapshot.get("camera_hpr_render", Vec3(0, 0, 0))))
            except Exception:
                pass
        else:
            self.flight_root.hide()
            self.interior_root.show()
            self.set_mode("interior")
        self._hide_operation_display()
        self.operation_shell_snapshot = None

    def start_embedded_world_operation(self, code: str) -> None:
        if getattr(self, "operation_active", False):
            raise RuntimeError("Embedded operation already active")
        if getattr(self, "operation_return_in_progress", False):
            self.set_loop_feedback("RETURN LINK BUSY", 1.2)
            return
        target = OPERATION_TARGETS[code]
        moon = str(target["moon"])
        world_path = Path(__file__).resolve().parent / "Worlds" / "main.py"
        if not world_path.exists():
            raise FileNotFoundError("Worlds/main.py not found")
        self.current_operation_code = code
        self._stash_shell_for_operation()
        self._unbind_starfall_controls()
        self._clear_operation_module_cache()
        import sys as _sys
        old_argv = list(_sys.argv)
        old_path = list(_sys.path)
        try:
            worlds_dir = str(world_path.parent)
            if worlds_dir not in _sys.path:
                _sys.path.insert(0, worlds_dir)
            spec = importlib.util.spec_from_file_location("operation_starfall_worlds_main", str(world_path))
            if spec is None or spec.loader is None:
                raise RuntimeError("Could not load Worlds/main.py module spec")
            module = importlib.util.module_from_spec(spec)
            _sys.modules[spec.name] = module
            inherited_audio_args = []
            if ("--no-audio" in old_argv) or ("--headless" in old_argv) or (os.environ.get("STARFALL_HEADLESS") == "1"):
                inherited_audio_args.append("--no-audio")
            _sys.argv = [str(world_path), f"--moon={moon}", "--embedded-operation", "--no-loading-screen", *inherited_audio_args]
            spec.loader.exec_module(module)
            module.EMBEDDED_PARENT = self
            module.EMBEDDED_OPERATION_CODE = code
            self.operation_module = module
            self.operation_app = module.EnceladusIce()
            self._give_camera_to_operation(self.operation_app)
        except Exception:
            # Pass109: EnceladusIce may fail after creating embedded roots/tasks but
            # before assignment to self.operation_app. Recover the module's tracked
            # partial instance first, then run shell-owned fallback cleanup.
            cleanup_module = self.operation_module or locals().get("module")
            self._cleanup_partial_embedded_operation(cleanup_module)
            self.operation_module = None
            self.operation_app = None
            self.operation_active = False
            self.operation_loading_in_progress = False
            self.pending_operation_code = None
            self.current_operation_code = None
            self._hide_operation_overlay()
            self._clear_operation_loading()
            self._restore_shell_after_operation(failed_launch=True)
            self.operation_cleanup_residue = self._operation_lifecycle_state()
            self._bind_starfall_controls()
            raise
        finally:
            _sys.argv = old_argv
            _sys.path[:] = old_path
        self.operation_return_in_progress = False
        self.operation_active = True
        self._clear_operation_loading()
        self._show_operation_overlay(code)
        self.set_loop_feedback(f"{target['title'].upper()} OPERATION LIVE", 2.4)

    def return_from_operation(self, result: dict | None = None) -> None:
        if getattr(self, "operation_return_in_progress", False):
            return
        self.operation_return_in_progress = True
        app = getattr(self, "operation_app", None)
        module = getattr(self, "operation_module", None)
        self._reclaim_camera_from_operation()
        if app is not None:
            try:
                app.shutdown_embedded_operation()
            except Exception as exc:
                self.operation_last_error = f"return cleanup: {exc}"
        # Pass109: normal embedded shutdown remains first authority, but the shell
        # owns a final residue sweep so a shutdown exception cannot strand roots/tasks.
        self._force_clear_operation_residue(module)
        self.operation_app = None
        self.operation_module = None
        self.operation_active = False
        self.operation_loading_in_progress = False
        self.pending_operation_code = None
        self.current_operation_code = None
        self._clear_operation_module_cache()
        self._hide_operation_overlay()
        self._unbind_starfall_controls()
        self._clear_operation_loading()
        self._restore_shell_after_operation(failed_launch=False)
        self.operation_cleanup_residue = self._operation_lifecycle_state()
        for element in getattr(self, "hud_elements", []):
            if self.hud_visible:
                element.show()
        self._bind_starfall_controls()
        if result:
            self.operation_last_result = dict(result)
            self.operation_result_history = list(getattr(self, "operation_result_history", []))[-7:] + [dict(result)]
            self.credits += int(result.get("credits", 0) or 0)
            self.research_points += int(result.get("research_points", 0) or 0)
            # Pass42: moon operations now return standardized result packets.  The
            # shell records them without inventing extra rewards; Prototype Lab
            # point validation still belongs to the result/profile contract files.
            if "lab_points_awarded" in result or "level_id" in result:
                self.last_moon_result_summary = {
                    "level_id": result.get("level_id"),
                    "world_key": result.get("world_key"),
                    "score": int(result.get("score", 0) or 0),
                    "lab_points_awarded": int(result.get("lab_points_awarded", 0) or 0),
                    "completed": bool(result.get("completed", False)),
                    "progress_percent": int(result.get("progress_percent", 0) or 0),
                }
        self.operation_return_in_progress = False
        self.set_loop_feedback("RETURNED TO STARFALL", 2.6)
        self.update_cabin_console()
        self.update_observatory_station_panels()

    def take_screenshot_and_exit(self, task: Task) -> int:
        if self.screenshot_out:
            # Presentation verification angle: this does not change normal gameplay controls.
            if self.screenshot_mode == "flight":
                self.ship.setPos(0, -2.0, 2.5)
                self.ship.setHpr(-30, 6, 3)
                self.camera.setPos(12.6, -14.2, 6.9)
                self.camera.lookAt(self.ship.getPos() + Vec3(0, -0.60, 0.54))
            elif self.screenshot_mode == "warp":
                self.set_mode("flight")
                self.ship.setPos(-3.4, -2.0, 2.35)
                self.ship.setHpr(-18, 5, 2)
                self.camera.setPos(14.2, 21.8, 14.8)
                self.camera.lookAt(Vec3(0.0, 31.0, 7.0))
                self.set_context_prompt("LMB WARP")
                self.set_reticle_color((0.48, 0.90, 1.0, 0.58))
            elif self.screenshot_mode == "system":
                self.set_mode("flight")
                self.build_celestial_chunk("Verification Solar System", "ring_giant", 9909)
                self.ship.setPos(-1.8, 7.0, 3.2)
                self.ship.setHpr(-22, 5, 2)
                self.camera.setPos(10.5, -4.0, 13.6)
                self.camera.lookAt(Vec3(-17.4, 50.0, 8.8))
                self.chunk_text.setText(self.current_chunk_name)
                self.set_context_prompt("SCAN + SAMPLES = CR")
                self.update_objective_text()
            elif self.screenshot_mode == "interior":
                # Interior-only verification: clear central-lane view of the robot research observatory.
                if not self.research_tasks:
                    self.generate_research_tasks("ring_giant", "ringed", 32432)
                self.camera.setPos(-0.18, 180.85, 1.86)
                self.camera.lookAt(Vec3(0.00, 168.80, 1.58))
                self.update_cabin_console()
                self.update_research_panels()
            elif self.screenshot_mode == "opsmap":
                self.set_mode("interior")
                self.show_saturn_operations_map()
                self.select_operation_on_map("EUROPA")
                self.camera.setPos(self.player_pos)
                self.camera.setHpr(self.interior_heading, self.interior_pitch, 0)
            # Ensure several frames are rendered into the offscreen buffer.
            for _ in range(4):
                self.graphicsEngine.renderFrame()
            self.win.saveScreenshot(self.screenshot_out)
        self.userExit()
        return Task.done


def task_time() -> float:
    return ClockObject.getGlobalClock().getFrameTime()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Operation: Starfall")
    parser.add_argument("--screenshot", choices=["flight", "interior", "warp", "system", "opsmap"], default=None, help="Render a verification screenshot then exit.")
    parser.add_argument("--out", default=None, help="Screenshot output path.")
    parser.add_argument("--headless", action="store_true", help="Use offscreen rendering for automated tests and screenshots.")
    parser.add_argument("--no-audio", action="store_true", help="Disable all StarFall and embedded moon audio cleanly.")
    # Match the linked mission launcher: the shell must accept the same display
    # authority flags that display_config.py already knows how to apply.
    for flag in ["--reference-window", "--1080p", "--desktop-window", "--fullscreen", "--bordered-fullscreen", "--decorated-fullscreen", "--bordered-window", "--safe-window", "--large-window", "--windowed-fullscreen", "--full-windowed", "--borderless", "--windowed"]:
        parser.add_argument(flag, action="store_true")
    parser.add_argument("--operation-self-test", choices=["mimas", "enceladus", "iapetus", "titan", "mars", "pluto", "europa", "triton"], default=None, help="Launch an embedded moon operation and exit after validation.")
    parser.add_argument("--operation-cycle-self-test", action="store_true", help="Cycle Mimas -> ship -> Enceladus -> ship in one Panda3D window.")
    parser.add_argument("--shell-ui-self-test", choices=["pause", "map", "help"], default=None, help="Open a Starfall shell panel for verification.")
    parser.add_argument("--map-launch-self-test", choices=["mimas", "enceladus", "iapetus", "titan", "mars", "pluto", "europa", "triton"], default=None, help="Verify that interior LMB opens the map first, then a selected map target starts the embedded operation.")
    parser.add_argument("--operation-return-controls-self-test", choices=["mimas", "enceladus", "iapetus", "titan", "mars", "pluto", "europa", "triton"], default=None, help="Verify embedded moon TAB return and ESC return menu behavior.")
    parser.add_argument("--operation-result-contract-self-test", choices=["mimas", "enceladus", "iapetus", "titan", "mars", "pluto", "europa", "triton"], default=None, help="Verify embedded moon return sends a standardized result packet to the StarFall shell.")
    parser.add_argument("--loading-screen-self-test", choices=["mimas", "enceladus", "iapetus", "titan", "mars", "pluto", "europa", "triton"], default=None, help="Show a destination loading screen and exit for screenshot verification.")
    parser.add_argument("--operation-launch-authority-test", action="store_true", help="Verify one launch request owns the loading/handoff transition and duplicate input cannot retarget or double-launch it.")
    parser.add_argument("--shell-ui-authority-test", action="store_true", help="Verify StarFall shell/menu/map/interior UI ownership and HUD levels.")
    parser.add_argument("--display-authority-test", action="store_true", help="Verify the shared 1920x1080 reference display contract and report the actual runtime surface.")
    return parser.parse_args()



def operation_code_from_moon_arg(value: str | None) -> str:
    mapping = {"mimas": "MIMAS", "enceladus": "ENCELADUS", "iapetus": "IAPETUS", "titan": "TITAN", "mars": "MARS", "pluto": "PLUTO", "europa": "EUROPA", "triton": "TRITON"}
    return mapping.get(str(value or "mimas").lower(), "MIMAS")


def main() -> None:
    args = parse_args()
    headless = args.headless or os.environ.get("STARFALL_HEADLESS") == "1" or bool(args.screenshot)
    configure_panda(headless=headless)
    app = StarfallShipPrototype(screenshot_mode=args.screenshot, screenshot_out=args.out)
    # Optional GXTool runtime intelligence. The bridge adds its own root to
    # PYTHONPATH during proof runs; normal player launches do not require GXTool.
    # install_from_env is inert unless GXTool smoke/test variables are present.
    try:
        from runtime_hooks.panda3d_smoke_hook import install_from_env as install_gxtool_runtime_hook
        install_gxtool_runtime_hook(app)
    except ImportError:
        pass
    except Exception as exc:
        if os.environ.get("GXTOOL_BRIDGE_SMOKE") == "1" or os.environ.get("GXTOOL_BRIDGE_TEST_MODE") == "1":
            print(f"[Operation StarFall] GXTool runtime hook failed: {type(exc).__name__}: {exc}", flush=True)
    if args.display_authority_test:
        def _display_authority_test(task):
            from display_config import display_contract_self_test, requested_display_mode
            report_dir = Path(__file__).resolve().parent / "verification" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            contract = display_contract_self_test(Path(__file__).resolve().parent / "Worlds")
            surface = app.win
            if surface is None:
                runtime_size = [0, 0]
            elif hasattr(surface, "getProperties"):
                props = surface.getProperties()
                runtime_size = [int(props.getXSize()), int(props.getYSize())]
            else:
                runtime_size = [int(surface.getXSize()), int(surface.getYSize())]
            expected_default = requested_display_mode(sys.argv)
            checks = dict(contract.get("checks", {}))
            checks.update({
                "runtime_mode_reference_by_default": expected_default == "reference_1080p_window" or any(f in sys.argv for f in ["--windowed", "--safe-window", "--large-window", "--desktop-window", "--windowed-fullscreen", "--fullscreen"]),
                "runtime_surface_has_size": runtime_size[0] > 0 and runtime_size[1] > 0,
                "runtime_surface_16x9": abs((runtime_size[0] / max(runtime_size[1], 1)) - (16.0 / 9.0)) < 0.02,
                "default_headless_reference_is_1080p": (runtime_size == [1920, 1080]) if not any(f in sys.argv for f in ["--windowed", "--safe-window", "--large-window", "--desktop-window", "--windowed-fullscreen", "--fullscreen"]) else True,
            })
            report = {
                "contract": contract.get("contract"),
                "status": "PASS" if all(checks.values()) else "FAIL",
                "requested_mode": expected_default,
                "runtime_size": runtime_size,
                "checks": checks,
                "simulated_1080p": contract.get("simulated_1080p"),
                "simulated_1440p": contract.get("simulated_1440p"),
                "simulated_720p": contract.get("simulated_720p"),
            }
            (report_dir / "display_authority_test.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            app.userExit()
            return Task.done
        app.taskMgr.doMethodLater(0.18, _display_authority_test, "display_authority_test")
    if args.shell_ui_authority_test:
        def _shell_ui_authority_test(task):
            app.set_mode("interior")
            app.apply_shell_hud_level("MINIMAL")
            def _any_world_label_visible():
                for node in getattr(app, "interior_world_labels", []):
                    try:
                        if node is not None and not node.isEmpty() and not node.isHidden():
                            return True
                    except Exception:
                        pass
                return False

            app.show_pause_menu()
            pause_exclusive = app.shell_panel_is_exclusive("pause")
            app.hide_pause_menu()
            pause_restores_world_labels = _any_world_label_visible()
            app.show_shell_help()
            help_exclusive = app.shell_panel_is_exclusive("help")
            app.hide_shell_help(keep_cursor=True)
            help_restores_world_labels = _any_world_label_visible()
            app.show_saturn_operations_map()
            map_exclusive = app.shell_panel_is_exclusive("map")
            app.hide_saturn_operations_map(keep_cursor=True)
            map_restores_world_labels = _any_world_label_visible()
            app.show_saturn_operations_map()
            app.select_operation_on_map("TITAN")
            app.apply_shell_hud_level("COMPACT")
            app.apply_shell_hud_level("FULL")
            app.apply_shell_hud_level("HIDDEN")
            app.apply_shell_hud_level("MINIMAL")
            def _finish_shell_ui_authority(t):
                report_dir = Path(__file__).resolve().parent / "verification" / "reports"
                report_dir.mkdir(parents=True, exist_ok=True)
                title_text = app.title_text.getText() if hasattr(app, "title_text") else ""
                map_text = app.operation_map_selection_text.getText() if hasattr(app, "operation_map_selection_text") else ""
                text_lines = [line for line in map_text.splitlines() if line.strip()]
                root = getattr(app, "operation_map_root", None)
                checks = {
                    "contract_id": SHELL_UI_CONTRACT_ID,
                    "default_hud_minimal": getattr(app, "shell_hud_level", "") == "MINIMAL",
                    "title_has_no_pass_label": "P" not in title_text and "PASS" not in title_text.upper(),
                    "map_open": bool(getattr(app, "operation_map_open", False)),
                    "pause_modal_exclusive": pause_exclusive,
                    "pause_restores_world_labels": pause_restores_world_labels,
                    "help_modal_exclusive": help_exclusive,
                    "help_restores_world_labels": help_restores_world_labels,
                    "map_modal_exclusive": map_exclusive,
                    "map_restores_world_labels": map_restores_world_labels,
                    "map_inside_safe_canvas_root": bool(root is not None and not root.isEmpty()),
                    "map_backdrop_within_safe_canvas": bool(
                        getattr(app, "operation_map_backdrop_frame", (0, 0, 0, 0))[0] >= SHELL_SAFE_CANVAS["left"]
                        and getattr(app, "operation_map_backdrop_frame", (0, 0, 0, 0))[1] <= SHELL_SAFE_CANVAS["right"]
                        and getattr(app, "operation_map_backdrop_frame", (0, 0, 0, 0))[2] >= SHELL_SAFE_CANVAS["bottom"]
                        and getattr(app, "operation_map_backdrop_frame", (0, 0, 0, 0))[3] <= SHELL_SAFE_CANVAS["top"]
                    ),
                    "map_controls_within_safe_canvas": all(
                        bounds[0] >= SHELL_SAFE_CANVAS["left"]
                        and bounds[1] <= SHELL_SAFE_CANVAS["right"]
                        and bounds[2] >= SHELL_SAFE_CANVAS["bottom"]
                        and bounds[3] <= SHELL_SAFE_CANVAS["top"]
                        for bounds in getattr(app, "operation_map_safe_bounds", {}).values()
                    ) and bool(getattr(app, "operation_map_safe_bounds", {})),
                    "map_detail_concise": len(map_text) <= 300 and len(text_lines) <= 6,
                    "help_overlay_exists": bool(getattr(app, "shell_help_root", None) is not None),
                    "pause_menu_exists": bool(getattr(app, "pause_menu_root", None) is not None),
                    "hud_levels": list(SHELL_HUD_LEVELS),
                    "screen_rule": SHELL_SAFE_CANVAS,
                }
                report = {
                    "contract": SHELL_UI_CONTRACT_ID,
                    "status": "PASS" if all(v for k, v in checks.items() if k not in {"contract_id", "hud_levels", "screen_rule"}) else "FAIL",
                    "checks": checks,
                    "selected_operation": app.selected_operation_code(),
                    "map_text": map_text,
                }
                (report_dir / "shell_ui_authority_contract.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                if args.out:
                    for _ in range(4):
                        app.graphicsEngine.renderFrame()
                    app.win.saveScreenshot(args.out)
                app.userExit()
                return Task.done
            app.taskMgr.doMethodLater(0.35, _finish_shell_ui_authority, "finish_shell_ui_authority_test")
            return Task.done
        app.taskMgr.doMethodLater(0.12, _shell_ui_authority_test, "shell_ui_authority_test")
    if args.operation_launch_authority_test:
        launch_authority_report = {"steps": [], "final": "FAIL"}
        def _launch_authority_begin(task):
            app.set_mode("interior")
            app.begin_operation_loading("MIMAS")
            first_root = getattr(app, "operation_loading_root", None)
            first_tasks = [str(t.getName()) for t in app.taskMgr.getDoLaters() if str(t.getName()) == "finish_operation_loading"]
            app.begin_operation_loading("EUROPA")
            second_root = getattr(app, "operation_loading_root", None)
            second_tasks = [str(t.getName()) for t in app.taskMgr.getDoLaters() if str(t.getName()) == "finish_operation_loading"]
            launch_authority_report["steps"].append({
                "pending_after_duplicate": getattr(app, "pending_operation_code", None),
                "loading_in_progress": bool(getattr(app, "operation_loading_in_progress", False)),
                "finish_tasks_after_first": len(first_tasks),
                "finish_tasks_after_duplicate": len(second_tasks),
                "loading_root_preserved": bool(first_root is second_root),
            })
            return Task.done
        def _launch_authority_success_check(task):
            cleanup_before_return = app._operation_lifecycle_state()
            active_code = getattr(app, "current_operation_code", None)
            app_count = 1 if getattr(app, "operation_app", None) is not None else 0
            app.return_from_operation()
            cleanup_after_return = getattr(app, "operation_cleanup_residue", {})
            launch_authority_report["steps"].append({
                "active_code": active_code,
                "operation_app_count": app_count,
                "residue_while_active": cleanup_before_return,
                "residue_after_return": cleanup_after_return,
            })
            # Force the next launch to fail inside the handoff so failure recovery is
            # exercised without mutating/renaming shipped project files.
            app._pass101_real_start_embedded = app.start_embedded_world_operation
            def _intentional_launch_failure(code):
                raise RuntimeError("PASS101 intentional launch-failure probe")
            app.start_embedded_world_operation = _intentional_launch_failure
            app.begin_operation_loading("EUROPA")
            # Schedule the assertion relative to this second launch.  Embedded-world
            # construction can block long enough that startup-relative delayed tasks
            # become overdue and execute in the same frame.
            app.taskMgr.doMethodLater(1.8, _launch_authority_finish, "launch_authority_finish")
            return Task.done
        def _launch_authority_finish(task):
            try:
                real_start = getattr(app, "_pass101_real_start_embedded", None)
                if real_start is not None:
                    app.start_embedded_world_operation = real_start
                    delattr(app, "_pass101_real_start_embedded")
            except Exception:
                pass
            failure_state = {
                "failure_operation_active": bool(getattr(app, "operation_active", False)),
                "failure_loading_in_progress": bool(getattr(app, "operation_loading_in_progress", False)),
                "failure_pending_code": getattr(app, "pending_operation_code", None),
                "failure_loading_root_cleared": bool(getattr(app, "operation_loading_root", None) is None),
                "failure_shell_snapshot_cleared": bool(getattr(app, "operation_shell_snapshot", None) is None),
                "failure_finish_tasks": len([t for t in app.taskMgr.getDoLaters() if str(t.getName()) == "finish_operation_loading"]),
            }
            launch_authority_report["steps"].append(failure_state)
            first = launch_authority_report["steps"][0] if launch_authority_report["steps"] else {}
            success = launch_authority_report["steps"][1] if len(launch_authority_report["steps"]) > 1 else {}
            ok = (
                first.get("pending_after_duplicate") == "MIMAS"
                and first.get("finish_tasks_after_first") == 1
                and first.get("finish_tasks_after_duplicate") == 1
                and bool(first.get("loading_root_preserved"))
                and success.get("active_code") == "MIMAS"
                and success.get("operation_app_count") == 1
                and int(success.get("residue_while_active", {}).get("render_roots", 0)) == 1
                and int(success.get("residue_while_active", {}).get("ui_roots", 0)) == 1
                and bool(success.get("residue_while_active", {}).get("feed_region_active"))
                and bool(success.get("residue_while_active", {}).get("feed_camera_present"))
                and app._operation_lifecycle_is_clean(success.get("residue_after_return", {}))
                and not failure_state["failure_operation_active"]
                and not failure_state["failure_loading_in_progress"]
                and failure_state["failure_pending_code"] is None
                and failure_state["failure_loading_root_cleared"]
                and failure_state["failure_shell_snapshot_cleared"]
                and failure_state["failure_finish_tasks"] == 0
            )
            launch_authority_report["final"] = "PASS" if ok else "FAIL"
            report_dir = Path(__file__).resolve().parent / "verification" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "operation_launch_authority_test.json").write_text(json.dumps(launch_authority_report, indent=2), encoding="utf-8")
            app.userExit()
            return Task.done
        app.taskMgr.doMethodLater(0.15, _launch_authority_begin, "launch_authority_begin")
        app.taskMgr.doMethodLater(3.2, _launch_authority_success_check, "launch_authority_success_check")
    if args.loading_screen_self_test:
        code = operation_code_from_moon_arg(args.loading_screen_self_test)
        def _loading_screen_test(task):
            app.set_mode("interior")
            app._show_operation_loading(code)
            def _finish_loading_screen_test(t):
                report_dir = Path(__file__).resolve().parent / "verification" / "reports"
                report_dir.mkdir(parents=True, exist_ok=True)
                root = getattr(app, "operation_loading_root", None)
                report = {
                    "target": code,
                    "loading_screen_visible": bool(root is not None and not root.isEmpty()),
                    "animation_tasks": [str(t.getName()) for t in app.taskMgr.getTasks() if "loading" in str(t.getName()).lower() and "finish" not in str(t.getName()).lower()],
                    "planet_asset": str(Path(__file__).resolve().parent / "assets" / "generated" / f"operation_loading_{str(OPERATION_TARGETS.get(code, {}).get('moon', 'enceladus')).lower()}.png"),
                }
                (report_dir / f"loading_screen_{code.lower()}_self_test.json").write_text(json.dumps(report, indent=2))
                if args.out:
                    app.win.saveScreenshot(args.out)
                app._clear_operation_loading()
                app.userExit()
                return Task.done
            app.taskMgr.doMethodLater(0.35, _finish_loading_screen_test, "finish_loading_screen_self_test")
            return Task.done
        app.taskMgr.doMethodLater(0.12, _loading_screen_test, "loading_screen_self_test")
    if args.shell_ui_self_test:
        def _shell_ui_test(task):
            app.set_mode("interior")
            if args.shell_ui_self_test == "pause":
                app.handle_escape()
            elif args.shell_ui_self_test == "map":
                app.show_saturn_operations_map()
            else:
                app.show_shell_help()
            def _finish_shell_ui_test(t):
                report_dir = Path(__file__).resolve().parent / "verification" / "reports"
                report_dir.mkdir(parents=True, exist_ok=True)
                report = {
                    "pause_menu_open": bool(getattr(app, "pause_menu_open", False)),
                    "operation_map_open": bool(getattr(app, "operation_map_open", False)),
                    "shell_help_open": bool(getattr(app, "shell_help_open", False)),
                    "operation_active": bool(getattr(app, "operation_active", False)),
                    "selected_operation": app.selected_operation_code(),
                    "mouse_captured": bool(getattr(app, "mouse_captured", True)),
                    "modal_exclusive": app.shell_panel_is_exclusive(args.shell_ui_self_test),
                    "mode": getattr(app, "mode", ""),
                }
                (report_dir / f"shell_ui_{args.shell_ui_self_test}_self_test.json").write_text(json.dumps(report, indent=2))
                if args.out:
                    app.win.saveScreenshot(args.out)
                app.userExit()
                return Task.done
            app.taskMgr.doMethodLater(0.35, _finish_shell_ui_test, "finish_shell_ui_self_test")
            return Task.done
        app.taskMgr.doMethodLater(0.12, _shell_ui_test, "shell_ui_self_test")
    if args.map_launch_self_test:
        launch_code = operation_code_from_moon_arg(args.map_launch_self_test)
        launch_report = {"steps": [], "target": launch_code}
        def _open_map_first(task):
            app.set_mode("interior")
            app.handle_primary_click()
            launch_report["steps"].append({
                "after_interior_lmb_map_open": bool(getattr(app, "operation_map_open", False)),
                "after_interior_lmb_operation_active": bool(getattr(app, "operation_active", False)),
                "selected_operation": app.selected_operation_code(),
            })
            app.launch_operation_from_map(launch_code)
            return Task.done
        def _finish_map_launch_test(task):
            op_app = getattr(app, "operation_app", None)
            launch_report["steps"].append({
                "operation_active_after_map_target": bool(getattr(app, "operation_active", False)),
                "operation_app_created": op_app is not None,
                "pending_operation_code": getattr(app, "pending_operation_code", ""),
                "operation_error": getattr(app, "operation_last_error", ""),
            })
            launch_report["final"] = "PASS" if bool(getattr(app, "operation_active", False)) and getattr(app, "pending_operation_code", "") == launch_code else "FAIL"
            report_dir = Path(__file__).resolve().parent / "verification" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / f"map_launch_{launch_code.lower()}_self_test.json").write_text(json.dumps(launch_report, indent=2))
            if args.out:
                app.win.saveScreenshot(args.out)
            app.return_from_operation()
            app.userExit()
            return Task.done
        app.taskMgr.doMethodLater(0.20, _open_map_first, "map_launch_open_first")
        app.taskMgr.doMethodLater(3.5, _finish_map_launch_test, "map_launch_finish")
    if args.operation_result_contract_self_test:
        code = operation_code_from_moon_arg(args.operation_result_contract_self_test)
        result_report = {"target": code, "steps": [], "final": "FAIL"}
        def _launch_result_contract_operation(task):
            app.begin_operation_loading(code)
            result_report["steps"].append({"launch_requested": code})
            return Task.done
        def _trigger_result_contract_return(task):
            op_app = getattr(app, "operation_app", None)
            if op_app is None:
                result_report["steps"].append({"operation_app_created": False, "operation_error": getattr(app, "operation_last_error", "")})
                return Task.done
            try:
                # Ensure this self-test proves a completed packet rather than a partial exit.
                op_app.catch_count = max(int(getattr(op_app, "loop_goal_catches", 3) or 3), int(getattr(op_app, "catch_count", 0) or 0))
                op_app._handle_tab_return()
            except Exception as exc:
                result_report["steps"].append({"return_error": str(exc)})
            return Task.done
        def _finish_result_contract_test(task):
            summary = dict(getattr(app, "last_moon_result_summary", {}) or {})
            last_result = dict(getattr(app, "operation_last_result", {}) or {})
            ok = bool(summary) and summary.get("completed") is True and int(summary.get("progress_percent", 0) or 0) == 100 and int(summary.get("lab_points_awarded", 0) or 0) > 0 and not bool(getattr(app, "operation_active", False))
            result_report["steps"].append({
                "operation_active_after_return": bool(getattr(app, "operation_active", False)),
                "last_moon_result_summary": summary,
                "last_result_has_contract": last_result.get("operation_result_contract") == "operation_starfall_progress_result_contract_v0.1",
            })
            result_report["final"] = "PASS" if ok else "FAIL"
            report_dir = Path(__file__).resolve().parent / "verification" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "operation_result_contract_self_test.json").write_text(json.dumps(result_report, indent=2))
            if args.out:
                app.win.saveScreenshot(args.out)
            app.userExit()
            os._exit(0 if ok else 1)
            return Task.done
        app.taskMgr.doMethodLater(0.2, _launch_result_contract_operation, "result_contract_launch")
        app.taskMgr.doMethodLater(3.6, _trigger_result_contract_return, "result_contract_return")
        app.taskMgr.doMethodLater(4.2, _finish_result_contract_test, "result_contract_finish")
    if args.operation_return_controls_self_test:
        code = operation_code_from_moon_arg(args.operation_return_controls_self_test)
        return_report = {"target": code, "steps": [], "final": "FAIL"}
        def _launch_return_controls_operation(task):
            app.begin_operation_loading(code)
            return_report["steps"].append({"launch_requested": code})
            return Task.done
        def _exercise_escape_menu(task):
            op_app = getattr(app, "operation_app", None)
            if op_app is None:
                return_report["steps"].append({"operation_app_created": False, "operation_error": getattr(app, "operation_last_error", "")})
                return Task.done
            try:
                op_app._handle_escape_menu()
            except Exception as exc:
                return_report["steps"].append({"escape_menu_error": str(exc)})
                return Task.done
            options_frame = getattr(op_app, "options_frame", None)
            return_report["steps"].append({
                "operation_app_created": True,
                "embedded_operation": bool(getattr(op_app, "embedded_operation", False)),
                "escape_options_visible": bool(getattr(op_app, "options_visible", False)),
                "escape_frame_visible": bool(options_frame is not None and not options_frame.isEmpty() and not options_frame.isHidden()),
                "moon_hud_hidden": bool(getattr(op_app, "embedded_ui_is_hidden", lambda: False)()),
                "modal_ui_exclusive": bool(getattr(op_app, "options_modal_is_exclusive", lambda: False)()),
                "vessel_active_after_escape": bool(getattr(op_app, "starfall_vessel_active", False)),
            })
            if args.out:
                for _ in range(4):
                    app.graphicsEngine.renderFrame()
                app.win.saveScreenshot(args.out)
            # Close once to prove the exact gameplay HUD state is restored, then
            # reopen so TAB-return is still tested from the modal state.
            op_app._handle_escape_menu()
            parent_overlay = getattr(app, "operation_overlay_root", None)
            sonar_text = getattr(op_app, "sonar_title_text", None)
            vision_root = getattr(op_app, "planet_vision_overlay_root", None)
            return_report["steps"].append({
                "close_options_visible": bool(getattr(op_app, "options_visible", False)),
                "close_parent_overlay_restored": bool(parent_overlay is not None and not parent_overlay.isEmpty() and not parent_overlay.isHidden()),
                "close_sonar_hidden": bool(sonar_text is None or sonar_text.isEmpty() or sonar_text.isHidden()),
                "close_vision_hidden": bool(vision_root is None or vision_root.isEmpty() or vision_root.isHidden()),
            })
            op_app._handle_escape_menu()
            return_report["steps"].append({
                "reopen_options_visible": bool(getattr(op_app, "options_visible", False)),
                "reopen_modal_ui_exclusive": bool(getattr(op_app, "options_modal_is_exclusive", lambda: False)()),
            })
            return Task.done
        def _exercise_tab_return(task):
            op_app = getattr(app, "operation_app", None)
            if op_app is not None:
                try:
                    op_app._handle_tab_return()
                except Exception as exc:
                    return_report["steps"].append({"tab_return_error": str(exc)})
            return Task.done
        def _finish_return_controls_test(task):
            cleanup = getattr(app, "operation_cleanup_residue", {})
            final_state = {
                "operation_active": bool(getattr(app, "operation_active", False)),
                "operation_app_none": getattr(app, "operation_app", None) is None,
                "mode": getattr(app, "mode", ""),
                "cleanup_residue": cleanup,
                "vessel_module_reached": False,
            }
            return_report["steps"].append(final_state)
            escape_step = next((step for step in return_report["steps"] if isinstance(step, dict) and "escape_options_visible" in step), {})
            close_step = next((step for step in return_report["steps"] if isinstance(step, dict) and "close_options_visible" in step), {})
            reopen_step = next((step for step in return_report["steps"] if isinstance(step, dict) and "reopen_options_visible" in step), {})
            no_residue = bool(cleanup) and app._operation_lifecycle_is_clean(cleanup)
            ok = (
                bool(escape_step.get("escape_options_visible"))
                and bool(escape_step.get("escape_frame_visible"))
                and bool(escape_step.get("modal_ui_exclusive"))
                and not bool(escape_step.get("vessel_active_after_escape"))
                and not bool(close_step.get("close_options_visible"))
                and bool(close_step.get("close_parent_overlay_restored"))
                and bool(close_step.get("close_sonar_hidden"))
                and bool(close_step.get("close_vision_hidden"))
                and bool(reopen_step.get("reopen_options_visible"))
                and bool(reopen_step.get("reopen_modal_ui_exclusive"))
                and not final_state["operation_active"]
                and final_state["operation_app_none"]
                and final_state["mode"] == "interior"
                and no_residue
            )
            return_report["final"] = "PASS" if ok else "FAIL"
            report_dir = Path(__file__).resolve().parent / "verification" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "operation_return_controls_self_test.json").write_text(json.dumps(return_report, indent=2))
            app.userExit()
            return Task.done
        app.taskMgr.doMethodLater(0.2, _launch_return_controls_operation, "return_controls_launch")
        app.taskMgr.doMethodLater(3.1, _exercise_escape_menu, "return_controls_escape")
        app.taskMgr.doMethodLater(3.5, _exercise_tab_return, "return_controls_tab")
        app.taskMgr.doMethodLater(4.0, _finish_return_controls_test, "return_controls_finish")
    if args.operation_self_test:
        code = operation_code_from_moon_arg(args.operation_self_test)
        def _op_self_test(task):
            app.begin_operation_loading(code)
            def _finish_self_test(t):
                report_dir = Path(__file__).resolve().parent / "verification" / "reports"
                report_dir.mkdir(parents=True, exist_ok=True)
                overlay_root = getattr(app, "operation_overlay_root", None)
                op_app = getattr(app, "operation_app", None)
                report = {
                    "operation_active": bool(getattr(app, "operation_active", False)),
                    "operation_app_created": op_app is not None,
                    "operation_error": getattr(app, "operation_last_error", ""),
                    "pending_operation_code": getattr(app, "pending_operation_code", ""),
                    "universal_overlay_visible": bool(overlay_root is not None and not overlay_root.isEmpty() and not overlay_root.isHidden()),
                    "moon_ui_hidden": bool(op_app is not None and getattr(op_app, "embedded_ui_is_hidden", lambda: False)()),
                    "residue_while_active": app._count_operation_residue(),
                }
                (report_dir / "operation_embed_self_test.json").write_text(json.dumps(report, indent=2))
                if args.out:
                    app.win.saveScreenshot(args.out)
                app.return_from_operation()
                app.userExit()
                return Task.done
            app.taskMgr.doMethodLater(8.0, _finish_self_test, "finish_operation_self_test")
            return Task.done
        app.taskMgr.doMethodLater(0.2, _op_self_test, "operation_self_test")
    if args.operation_cycle_self_test:
        cycle_report = {"steps": [], "errors": []}
        def _launch_mimas(task):
            app.begin_operation_loading("MIMAS")
            cycle_report["steps"].append("launch_mimas")
            return Task.done
        def _return_mimas(task):
            mimas_app = getattr(app, "operation_app", None)
            mimas_isolation = bool(
                mimas_app is not None
                and not app.interior_root.isHidden()
                and app.flight_root.isHidden()
                and getattr(mimas_app, "camera", None) == getattr(app, "operation_feed_camera", None)
                and getattr(mimas_app, "camera", None) != app.camera
                and getattr(app, "operation_feed_display_region", None) is not None
                and app.operation_feed_display_region.isActive()
            )
            cycle_report["steps"].append({"mimas_active": bool(getattr(app, "operation_active", False)), "mimas_app": mimas_app is not None, "scene_isolated": mimas_isolation})
            app.return_from_operation({"credits": 3, "research_points": 1})
            cycle_report["steps"].append({"returned_from_mimas": not bool(getattr(app, "operation_active", False)), "mode": getattr(app, "mode", ""), "cleanup_residue": getattr(app, "operation_cleanup_residue", {}), "postfx_cleaned": bool(mimas_app is not None and getattr(mimas_app, "filters", None) is None)})
            return Task.done
        def _launch_enceladus(task):
            app.begin_operation_loading("ENCELADUS")
            cycle_report["steps"].append("launch_enceladus")
            return Task.done
        def _finish_cycle(task):
            enceladus_app = getattr(app, "operation_app", None)
            enceladus_isolation = bool(
                enceladus_app is not None
                and not app.interior_root.isHidden()
                and app.flight_root.isHidden()
                and getattr(enceladus_app, "camera", None) == getattr(app, "operation_feed_camera", None)
                and getattr(enceladus_app, "camera", None) != app.camera
                and getattr(app, "operation_feed_display_region", None) is not None
                and app.operation_feed_display_region.isActive()
            )
            cycle_report["steps"].append({"enceladus_active": bool(getattr(app, "operation_active", False)), "enceladus_app": enceladus_app is not None, "scene_isolated": enceladus_isolation})
            if args.out:
                app.win.saveScreenshot(args.out)
            app.return_from_operation({"credits": 5, "research_points": 2})
            cleanup = getattr(app, "operation_cleanup_residue", {})
            cycle_report["steps"].append({"returned_from_enceladus": not bool(getattr(app, "operation_active", False)), "mode": getattr(app, "mode", ""), "credits": int(getattr(app, "credits", 0)), "research_points": int(getattr(app, "research_points", 0)), "cleanup_residue": cleanup, "postfx_cleaned": bool(enceladus_app is not None and getattr(enceladus_app, "filters", None) is None)})
            no_residue = bool(cleanup) and app._operation_lifecycle_is_clean(cleanup)
            isolation_pass = all(bool(step.get("scene_isolated", True)) and bool(step.get("postfx_cleaned", True)) for step in cycle_report["steps"] if isinstance(step, dict))
            cycle_report["final"] = "PASS" if int(getattr(app, "credits", 0)) >= 8 and not bool(getattr(app, "operation_active", False)) and no_residue and isolation_pass else "FAIL"
            report_dir = Path(__file__).resolve().parent / "verification" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "operation_cycle_self_test.json").write_text(json.dumps(cycle_report, indent=2))
            app.userExit()
            return Task.done
        app.taskMgr.doMethodLater(0.2, _launch_mimas, "cycle_launch_mimas")
        app.taskMgr.doMethodLater(8.5, _return_mimas, "cycle_return_mimas")
        app.taskMgr.doMethodLater(9.2, _launch_enceladus, "cycle_launch_enceladus")
        app.taskMgr.doMethodLater(17.5, _finish_cycle, "cycle_finish")
    app.run()


if __name__ == "__main__":
    main()
