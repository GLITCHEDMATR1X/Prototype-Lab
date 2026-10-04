from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

from panda3d.core import (
    AmbientLight,
    BitMask32,
    CollisionBox,
    CollisionNode,
    Filename,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexReader,
    GeomVertexWriter,
    Material,
    NodePath,
    Point3,
    PointLight,
    Texture,
    TextureStage,
    TransparencyAttrib,
    Vec3,
    Vec4,
)

CELL = 1.0
WALL_HEIGHT = 2.58
WALL_THICK = 0.16
FLOOR_THICK = 0.08
CEILING_THICK = 0.08
WALL_MASK = BitMask32.bit(1)


@dataclass(frozen=True)
class ZoneStyle:
    name: str
    wall_texture: str
    floor_texture: str
    ceiling_texture: str
    light_color: tuple[float, float, float, float]
    trim_color: tuple[float, float, float, float]


@dataclass
class StabilityNode:
    node_id: str
    zone: str
    target_zone: str
    pos: Point3
    source_color: tuple[float, float, float, float]
    unlocked: bool = False
    active: bool = False
    root: NodePath | None = None
    core: NodePath | None = None
    cage: NodePath | None = None
    light_np: NodePath | None = None


ROUTE_PROFILES = (
    ("archive", "feedback", "dead", "buffer"),
    ("archive", "dead", "feedback", "buffer"),
    ("feedback", "archive", "dead", "buffer"),
    ("feedback", "dead", "archive", "buffer"),
    ("dead", "archive", "feedback", "buffer"),
    ("dead", "feedback", "archive", "buffer"),
)


ZONE_STYLES = {
    "intake": ZoneStyle("intake", "wall_neon.png", "floor_grid.png", "ceiling_fluoro.png", (1.0, 0.30, 0.58, 1), (0.95, 0.05, 0.75, 1)),
    "relay": ZoneStyle("relay", "wall_neon.png", "floor_grid.png", "ceiling_fluoro.png", (0.42, 0.83, 1.0, 1), (0.06, 0.86, 1.0, 1)),
    "pressure": ZoneStyle("pressure", "wall_magenta.png", "floor_grid.png", "ceiling_fluoro.png", (0.73, 0.28, 1.0, 1), (0.78, 0.12, 1.0, 1)),
    "lattice": ZoneStyle("lattice", "wall_greenbrick.png", "floor_green.png", "ceiling_dark.png", (0.28, 1.0, 0.40, 1), (0.32, 1.0, 0.58, 1)),
    "analog": ZoneStyle("analog", "wall_orange.png", "floor_dark.png", "ceiling_dark.png", (1.0, 0.43, 0.17, 1), (1.0, 0.30, 0.06, 1)),
    "buffer": ZoneStyle("buffer", "wall_frame.png", "floor_grid.png", "ceiling_fluoro.png", (0.50, 0.60, 1.0, 1), (1.0, 0.19, 0.89, 1)),
    "stable": ZoneStyle("stable", "wall_stable.png", "floor_stable.png", "ceiling_stable.png", (0.43, 0.75, 0.86, 1), (0.16, 0.72, 0.90, 1)),
    "archive": ZoneStyle("archive", "wall_frame.png", "floor_dark.png", "ceiling_dark.png", (0.46, 0.26, 0.88, 1), (0.56, 0.18, 0.96, 1)),
    "feedback": ZoneStyle("feedback", "wall_greenbrick.png", "floor_grid.png", "ceiling_dark.png", (0.20, 0.90, 0.72, 1), (0.18, 1.0, 0.68, 1)),
    "dead": ZoneStyle("dead", "wall_orange.png", "floor_dark.png", "ceiling_dark.png", (0.92, 0.16, 0.08, 1), (1.0, 0.20, 0.05, 1)),
    "falsehall": ZoneStyle("falsehall", "wall_frame.png", "floor_dark.png", "ceiling_dark.png", (0.34, 0.28, 0.62, 1), (0.42, 0.30, 0.74, 1)),
    "focus": ZoneStyle("focus", "wall_stable.png", "floor_dark.png", "ceiling_dark.png", (0.44, 0.50, 0.62, 1), (0.48, 0.62, 0.72, 1)),
    "unlit": ZoneStyle("unlit", "wall_frame.png", "floor_dark.png", "ceiling_dark.png", (0.16, 0.20, 0.30, 1), (0.28, 0.34, 0.46, 1)),
    "echo": ZoneStyle("echo", "wall_stable.png", "floor_grid.png", "ceiling_dark.png", (0.34, 0.46, 0.58, 1), (0.40, 0.60, 0.70, 1)),
    "witness": ZoneStyle("witness", "wall_magenta.png", "floor_dark.png", "ceiling_dark.png", (0.30, 0.12, 0.38, 1), (0.44, 0.16, 0.52, 1)),
    "return": ZoneStyle("return", "wall_orange.png", "floor_dark.png", "ceiling_dark.png", (0.44, 0.18, 0.34, 1), (0.64, 0.20, 0.48, 1)),
    "seam": ZoneStyle("seam", "wall_frame.png", "floor_dark.png", "ceiling_dark.png", (0.18, 0.30, 0.34, 1), (0.12, 0.56, 0.62, 1)),
}


def _make_box_geom(name: str, sx: float, sy: float, sz: float, uv_scale=(1.0, 1.0)) -> NodePath:
    fmt = GeomVertexFormat.getV3n3t2()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vdata.setNumRows(24)
    vtx = GeomVertexWriter(vdata, "vertex")
    nrm = GeomVertexWriter(vdata, "normal")
    uv = GeomVertexWriter(vdata, "texcoord")
    hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
    faces = [
        ((-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz), (0, -1, 0), sx, sz),
        ((hx, hy, -hz), (-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz), (0, 1, 0), sx, sz),
        ((-hx, hy, -hz), (-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz), (-1, 0, 0), sy, sz),
        ((hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz), (1, 0, 0), sy, sz),
        ((-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz), (0, 0, 1), sx, sy),
        ((-hx, hy, -hz), (hx, hy, -hz), (hx, -hy, -hz), (-hx, -hy, -hz), (0, 0, -1), sx, sy),
    ]
    tri = GeomTriangles(Geom.UHStatic)
    for fi, (a, b, c, d, normal, uw, vh) in enumerate(faces):
        base = fi * 4
        for p, tex in ((a, (0, 0)), (b, (uw * uv_scale[0], 0)), (c, (uw * uv_scale[0], vh * uv_scale[1])), (d, (0, vh * uv_scale[1]))):
            vtx.addData3(*p)
            nrm.addData3(*normal)
            uv.addData2(*tex)
        tri.addVertices(base, base + 1, base + 2)
        tri.addVertices(base, base + 2, base + 3)
    geom = Geom(vdata)
    geom.addPrimitive(tri)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


class NightmareWorld:
    """Hand-authored grid topology with procedural walls and themed sectors."""

    def __init__(self, base, project_root: Path, dream_seed: int = 6060):
        self.base = base
        self.ceiling_height = WALL_HEIGHT
        self.root = base.render.attachNewNode("nightmare-world")
        self.project_root = project_root
        self.dream_seed = int(dream_seed)
        self.dream_cycle = 0
        self._cycle_signature = ""
        self.texture_dir = project_root / "assets" / "textures"
        self.textures: dict[str, Texture] = {}
        self.texture_variants: dict[str, tuple[Texture, ...]] = {}
        self._surface_records: list[tuple[NodePath, str, str | None]] = []
        self._cycle_color_nodes: list[tuple[NodePath, Vec4, str | None]] = []
        self._dream_lights: list[tuple[NodePath, Vec4, str | None]] = []
        self._zone_visual_nodes: dict[str, list[NodePath]] = {}
        self._target_beacons: dict[str, list[NodePath]] = {}
        self._zone_lights: dict[str, list[NodePath]] = {}
        self.relay_spindle_parts: list[NodePath] = []
        self.walkable: dict[tuple[int, int], str] = {}
        self.stability_nodes: dict[str, StabilityNode] = {}
        # Pass 13: one of six authored room orders is selected from the run seed.
        # The order never mutates during datamosh/dream-cycle changes, so progress
        # cannot be invalidated mid-run.  Normal launches already use a random seed;
        # QA uses fixed seeds and can exercise every route profile deterministically.
        route_rng = random.Random((self.dream_seed * 1000003) ^ 23)
        self.route_profile_index = route_rng.randrange(len(ROUTE_PROFILES))
        self.route_zones = tuple(ROUTE_PROFILES[self.route_profile_index])
        self.route_signature = ">".join(self.route_zones)
        self.route_node_order: tuple[str, ...] = ()
        self.stabilized_zones: set[str] = {"stable"}
        self.visited_stabilized_zones: set[str] = set()
        self.route_complete = False
        self.instance_complete = False
        self.null_layer = False
        self.null_exit_complete = False
        self.glasses_collected = False
        self.glasses_root: NodePath | None = None
        self.glasses_pos = Point3(40.25, 8.35, 0.0)
        self.glasses_anchor_index = 0
        self._glasses_anchors = [
            Point3(40.25, 8.35, 0.0),
            Point3(-16.25, 5.22, 0.0),
            Point3(-9.15, -8.25, 0.0),
            Point3(-8.35, 22.62, 0.0),
            Point3(7.35, -14.18, 0.0),
            Point3(-9.25, -2.15, 0.0),
            Point3(10.15, 26.15, 0.0),
            Point3(7.20, -3.60, 0.0),
        ]
        self._point_lights = []
        self._memory_seam_nodes: list[NodePath] = []
        self._memory_seam_revealed = False
        self._false_sleeper_roots: list[NodePath] = []
        self._false_sleeper_profile_indices: tuple[int, ...] = ()
        self._false_sleeper_visible_indices: tuple[int, ...] = ()
        self._gleebs_trace_root: NodePath | None = None
        self._gleebs_trace_eyes: list[NodePath] = []
        self._gleebs_trace_enabled = False
        self._gleebs_trace_seen = False
        self._gleebs_trace_vanished = False
        self._gleebs_trace_anchor_index = 0
        self._gleebs_trace_anchors = [
            (Point3(-9.50, 6.82, 0.15), 0.0),
            (Point3(-12.82, 3.12, 1.25), 0.0),
            (Point3(-8.82, 22.65, 1.28), 0.0),
            (Point3(38.15, 2.18, 1.30), 180.0),
        ]
        self._null_exit_root: NodePath | None = None
        self._resonance_active = False
        self._resonance_target_zone: str | None = None
        self._glasses_glint: NodePath | None = None
        self.null_exit_pos = Point3(0.0, 26.25, 0.0)
        self._instance_signature = ""
        self._unlit_afterglow: list[tuple[NodePath, float]] = []
        self._echo_bleed_nodes: list[NodePath] = []
        self._witness_root: NodePath | None = None
        self._witness_base_pos = Point3(-8.0, -8.62, 0.0)
        self._return_memory_root: NodePath | None = None
        self._return_memory_parts: list[NodePath] = []
        self._return_memory_base_pos = Point3(-5.13, 4.45, 0.0)
        self._return_memory_cycle_pos = Point3(self._return_memory_base_pos)
        self._return_memory_shifted = False
        self._return_memory_target = Point3(-5.13, 4.45, 1.35)
        self._anomaly_signature = ""
        self._build_layout()
        self._load_textures()
        self._build_geometry()
        self._build_decor()
        self._build_worldbuilding()
        self._build_target_beacons()
        self._build_stability_nodes()
        self._build_lighting()
        self.apply_dream_cycle(0, force=True)

    @property
    def spawn(self):
        return Point3(0.0, -18.0, 0.0), 0.0

    @property
    def relocation_anchors(self):
        # Authored valid positions used by datamosh displacement.  These are
        # deliberately inside real walkable cells, never arbitrary coordinates.
        return [
            (Point3(0.0, -2.0, 0.0), 0.0, Point3(0.0, 12.45, 0.0)),
            (Point3(7.0, 6.0, 0.0), 90.0, Point3(-8.0, 11.2, 0.0)),
            (Point3(-8.0, 11.0, 0.0), -90.0, Point3(9.5, 15.0, 0.0)),
            (Point3(0.0, 20.0, 0.0), 0.0, Point3(7.8, 6.3, 0.0)),
            (Point3(7.0, 23.0, 0.0), 90.0, Point3(0.0, 9.0, 0.0)),
            (Point3(-7.2, 0.4, 0.0), -90.0, Point3(9.0, 7.0, 180.0)),
            (Point3(15.0, 6.0, 0.0), 90.0, Point3(-8.0, 12.0, 180.0)),
            (Point3(-15.0, 11.5, 0.0), -90.0, Point3(0.0, 6.0, 180.0)),
        ]

    def zone_at(self, x: float, y: float) -> str | None:
        return self.walkable.get((math.floor(x), math.floor(y)))

    def stability_at(self, x: float, y: float) -> float:
        if self.null_layer:
            return 1.0
        zone = self.zone_at(x, y)
        if zone == "stable":
            return 0.88
        if zone in self.stabilized_zones:
            return 0.80
        if zone == "relay":
            return 0.20
        return 0.0

    def darkness_at(self, x: float, y: float) -> float:
        """0=normal room exposure, 1=strong authored darkness."""
        if self.null_layer:
            return 0.0
        zone = self.zone_at(x, y)
        base = {
            "dead": 0.62,
            "archive": 0.43,
            "buffer": 0.26,
            "falsehall": 0.68,
            "focus": 0.48,
            "unlit": 0.88,
            "echo": 0.46,
            "witness": 0.76,
            "return": 0.61,
            "seam": 0.74,
            "analog": 0.20,
            "stable": 0.02,
        }.get(zone, 0.10)
        if zone in self.stabilized_zones:
            base *= 0.36
        return max(0.0, min(1.0, base))

    def dream_lens_fov_offset(self, x: float, y: float) -> float:
        if self.null_layer:
            return 0.0
        """Authored false-near corridor lens distortion in degrees.

        Entering the hall compresses perspective with a telephoto-like negative
        FOV offset so the far doorway initially reads closer than it is.  Walking
        forward smoothly widens the lens, countering the normal apparent growth
        of the doorway.  The last metres release back to the player's chosen FOV.
        """
        if not (5.05 <= y <= 6.95 and 18.0 <= x <= 37.4):
            return 0.0
        t = max(0.0, min(1.0, (x - 18.0) / 19.4))
        # Stronger perspective lie for Pass 15 recovery: the far room initially
        # reads much nearer, then the lens widens while Andrew advances so the
        # doorway resists normal apparent growth.
        smooth = t * t * (3.0 - 2.0 * t)
        offset = -18.0 + 36.0 * smooth
        # Let the illusion collapse naturally at the actual threshold.
        if t > 0.82:
            release = (t - 0.82) / 0.18
            release = release * release * (3.0 - 2.0 * release)
            offset *= (1.0 - release)
        return offset

    def current_route_target(self) -> str | None:
        """Return the world-space destination Andrew currently needs to understand.

        The target stays the remotely stabilized room until Andrew physically
        reaches it; after arrival the newly unlocked relay becomes the next target.
        This keeps the resonance clue consistent with the existing route contract.
        """
        if self.route_complete or self.null_layer:
            return None
        for node_id in self.route_node_order:
            node = self.stability_nodes[node_id]
            if node.active and node.target_zone not in self.visited_stabilized_zones:
                return node.target_zone
            if node.unlocked and not node.active:
                return node.target_zone
        return None

    def set_resonance_view(self, active: bool) -> str | None:
        """Temporarily strip false readings and strengthen real world clues.

        This is a risk/reward observation reward, not a HUD objective system.
        The underlying topology and collision never change.
        """
        self._resonance_active = bool(active) and not self.null_layer
        self._resonance_target_zone = self.current_route_target() if self._resonance_active else None

        if self._resonance_active:
            for root in self._false_sleeper_roots:
                root.hide()
            for zone, parts in self._target_beacons.items():
                for np in parts:
                    if zone == self._resonance_target_zone:
                        np.setColor(0.10, 0.86, 1.0, 0.98)
                        np.setColorScale(1.25, 1.30, 1.34, 1.0)
                    else:
                        np.setColorScale(0.54, 0.58, 0.62, 0.70)
            for np in self._memory_seam_nodes:
                if self._memory_seam_revealed:
                    np.setColorScale(1.55, 1.85, 1.95, 1.0)
            if self._glasses_glint is not None and not self.glasses_collected:
                self._glasses_glint.setColorScale(2.35, 2.60, 2.75, 1.0)
        else:
            for zone, parts in self._target_beacons.items():
                for np in parts:
                    np.clearColorScale()
                self._refresh_target_beacon(zone)
            for np in self._memory_seam_nodes:
                np.clearColorScale()
            if self._glasses_glint is not None:
                self._glasses_glint.clearColorScale()
            if self.null_layer:
                for root in self._false_sleeper_roots:
                    root.hide()
            else:
                self._apply_destabilization_response()
        return self._resonance_target_zone

    def update_resonance_pulse(self, time_s: float):
        if not self._resonance_active or not self._resonance_target_zone or self.null_layer:
            return
        wave = 0.5 + 0.5 * math.sin(float(time_s) * 5.4)
        gain = 1.95 + 0.62 * wave
        for zone, parts in self._target_beacons.items():
            for np in parts:
                if zone == self._resonance_target_zone:
                    np.setColor(0.08 + 0.05 * wave, 0.78 + 0.12 * wave, 1.0, 0.98)
                    np.setColorScale(1.18 + 0.18 * wave, 1.22 + 0.18 * wave, 1.26 + 0.20 * wave, 1.0)
                else:
                    np.setColorScale(0.54, 0.58, 0.62, 0.70)
        if self._glasses_glint is not None and not self.glasses_collected:
            g = 2.10 + 0.55 * wave
            self._glasses_glint.setColorScale(g, g * 1.08, g * 1.14, 1.0)

    def glasses_near(self, x: float, y: float, max_distance: float = 1.15) -> bool:
        if self.glasses_collected or self.glasses_root is None or self.glasses_root.isHidden():
            return False
        return math.hypot(self.glasses_pos.x - x, self.glasses_pos.y - y) <= max_distance

    def collect_glasses(self) -> bool:
        if self.glasses_collected or self.glasses_root is None:
            return False
        self.glasses_collected = True
        self.glasses_root.hide()
        return True

    def null_exit_near(self, x: float, y: float, max_distance: float = 1.45) -> bool:
        if not self.null_layer or self.null_exit_complete or self._null_exit_root is None or self._null_exit_root.isHidden():
            return False
        return math.hypot(self.null_exit_pos.x - x, self.null_exit_pos.y - y) <= max_distance

    def complete_null_exit(self) -> bool:
        if not self.null_layer or self.null_exit_complete:
            return False
        self.null_exit_complete = True
        self.instance_complete = True
        if self._null_exit_root is not None:
            self._null_exit_root.hide()
        return True

    @property
    def memory_seam_revealed(self) -> bool:
        return self._memory_seam_revealed

    @property
    def instance_signature(self) -> str:
        return self._instance_signature

    @property
    def instance_destabilization_fraction(self) -> float:
        total = max(1, len(self.stability_nodes))
        return max(0.0, min(1.0, self.stabilized_count / total))

    def enter_null_layer(self):
        if self.null_layer:
            return False
        self.null_layer = True
        stage = TextureStage.getDefault()
        for np, _base_name, _zone in self._surface_records:
            np.clearTexture(stage)
            np.setColorScale(0.72, 0.73, 0.75, 1.0)
        for np, _base_color, _zone in self._cycle_color_nodes:
            np.setColor(0.58, 0.60, 0.63, min(1.0, max(0.35, np.getColor().w)))
        for light_np, _base_color, _zone in self._dream_lights:
            light_np.node().setColor(Vec4(0.38, 0.39, 0.41, 1.0))
        for node in self.stability_nodes.values():
            if node.root:
                node.root.hide()
        for part in self.relay_spindle_parts:
            part.hide()
        for parts in self._target_beacons.values():
            for np in parts:
                np.hide()
        for np, _ in self._unlit_afterglow:
            np.hide()
        for np in self._echo_bleed_nodes:
            np.hide()
        if self._witness_root:
            self._witness_root.hide()
        if self._return_memory_root:
            self._return_memory_root.hide()
        for root in self._false_sleeper_roots:
            root.hide()
        if self._gleebs_trace_root:
            self._gleebs_trace_root.hide()
        for np in self._memory_seam_nodes:
            np.setColor(0.47, 0.49, 0.52, 0.55)
        if self._null_exit_root:
            self._null_exit_root.show()
        return True

    @property
    def route_sequence(self) -> tuple[str, ...]:
        return self.route_zones

    def _apply_destabilization_response(self):
        """Let room recovery visibly weaken the false interception layer.

        False Sleepers are seeded scenery, not enemies.  Pass 13 makes their
        persistence communicate progress: each active relay removes one of the
        current profile's decoys, while the real Sleeper remains until final
        instance collapse.  The chosen decoys stay deterministic for the cycle.
        """
        if self.null_layer:
            return
        profile = self._false_sleeper_profile_indices
        if not profile:
            return
        remaining = max(0, len(profile) - self.stabilized_count)
        visible = tuple(profile[:remaining])
        self._false_sleeper_visible_indices = visible
        for i, root in enumerate(self._false_sleeper_roots):
            root.show() if i in visible else root.hide()

    @property
    def false_sleeper_count(self) -> int:
        return len(self._false_sleeper_visible_indices)

    def nearest_stabilizer(self, x: float, y: float, max_distance: float = 1.85) -> StabilityNode | None:
        best = None
        best_d = max_distance
        for node in self.stability_nodes.values():
            d = math.hypot(node.pos.x - x, node.pos.y - y)
            if d <= best_d:
                best = node
                best_d = d
        return best

    def node_can_activate(self, node: StabilityNode) -> bool:
        return bool(node.unlocked and not node.active)

    def stabilize_nearest(self, x: float, y: float, max_distance: float = 1.85) -> StabilityNode | None:
        node = self.nearest_stabilizer(x, y, max_distance=max_distance)
        if node is None or not self.node_can_activate(node):
            return None
        node.active = True
        self.stabilized_zones.add(node.target_zone)
        self._refresh_stabilizer_visual(node)
        self._apply_stabilized_zone_overrides()
        # The seam belongs to the first successful room recovery, not to any
        # specific named room; this remains valid when Pass 13 changes route order.
        if self.stabilized_count == 1:
            self._reveal_memory_seam()
        self._apply_destabilization_response()
        return node

    def register_zone_visit(self, zone: str | None):
        """Confirm arrival in a remotely stabilized destination.

        The destination visit is what unlocks the relay located inside that room,
        creating the route: stabilize remotely -> travel there -> acquire next relay.
        """
        if not zone or zone not in self.stabilized_zones or zone in self.visited_stabilized_zones:
            return None
        self.visited_stabilized_zones.add(zone)
        unlocked = None
        for node in self.stability_nodes.values():
            if node.zone == zone and not node.unlocked and not node.active:
                node.unlocked = True
                self._refresh_stabilizer_visual(node)
                unlocked = node
        if zone == "buffer":
            self.route_complete = True
            return ("complete", None)
        if unlocked is not None:
            return ("relay", unlocked)
        return ("arrived", None)

    def target_display_name(self, zone: str) -> str:
        return {
            "archive": "ARCHIVE CELL",
            "feedback": "FEEDBACK ROOM",
            "dead": "DEAD CHANNEL",
            "buffer": "DEEP BUFFER",
            "stable": "STABLE ROOM",
        }.get(zone, zone.upper())

    @property
    def stabilized_count(self) -> int:
        return sum(1 for node in self.stability_nodes.values() if node.active)

    @property
    def dreamer_recovery_fraction(self) -> float:
        """How much of the linked route has reconstructed the trapped Dreamer.

        Active relays provide gradual recovery, but only physically reaching the
        final Deep Buffer can complete the reconstruction and make release safe.
        """
        if self.route_complete:
            return 1.0
        total = max(1, len(self.stability_nodes))
        return min(0.92, (self.stabilized_count / total) * 0.92)

    def can_stand(self, x: float, y: float, radius: float = 0.34) -> bool:
        # Collision authority is derived from the exact same walkable-cell map that creates visible walls.
        # Sampling the player footprint prevents entering corners without introducing invisible blockers.
        samples = [(0.0, 0.0)]
        for i in range(12):
            a = math.tau * i / 12.0
            samples.append((math.cos(a) * radius, math.sin(a) * radius))
        for ox, oy in samples:
            cell = (math.floor(x + ox), math.floor(y + oy))
            if cell not in self.walkable:
                return False
        return True

    def path_exists(self, start: tuple[int, int], goal: tuple[int, int]) -> bool:
        if start not in self.walkable or goal not in self.walkable:
            return False
        if start == goal:
            return True
        frontier = [start]
        seen = {start}
        while frontier:
            x, y = frontier.pop(0)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (x + dx, y + dy)
                if nxt == goal:
                    return nxt in self.walkable
                if nxt in self.walkable and nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
        return False

    def has_clear_line(self, x0: float, y0: float, x1: float, y1: float, radius: float = 0.025) -> bool:
        """Return whether a horizontal sight line stays inside visible walkable space.

        The same grid that creates the walls is the occlusion authority, so Dreamer
        visibility cannot disagree with the level layout.
        """
        dx, dy = x1 - x0, y1 - y0
        distance = math.hypot(dx, dy)
        if distance <= 0.001:
            return True
        steps = max(2, int(math.ceil(distance / 0.08)))
        for i in range(1, steps):
            t = i / steps
            x = x0 + dx * t
            y = y0 + dy * t
            if not self.can_stand(x, y, radius=radius):
                return False
        return True

    def _paint_rect(self, x0, x1, y0, y1, zone):
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                self.walkable[(x, y)] = zone

    def _build_layout(self):
        # The entire layout is intentionally compressed: most travel lanes are 2 cells (~2 m) wide.
        self._paint_rect(-1, 0, -20, -5, "intake")       # 2 m intake hall
        self._paint_rect(-3, 2, -5, 2, "relay")          # release room
        self._paint_rect(-1, 0, 3, 16, "pressure")       # 2 m pressure hall
        self._paint_rect(1, 3, 5, 6, "lattice")          # east neck
        self._paint_rect(4, 11, 3, 10, "lattice")        # green lattice chamber
        self._paint_rect(-4, -2, 10, 11, "analog")       # west neck
        self._paint_rect(-11, -5, 8, 15, "analog")       # orange analog chamber
        self._paint_rect(-2, 1, 17, 27, "buffer")        # frame tunnel / deep buffer
        self._paint_rect(2, 4, 22, 23, "stable")         # stable neck
        self._paint_rect(5, 11, 19, 27, "stable")        # calm room
        # A thin loop from the green room toward the stable room.
        self._paint_rect(9, 10, 11, 18, "lattice")
        self._paint_rect(9, 10, 19, 19, "stable")

        # Pass 04: the chambers now branch into real side rooms rather than all
        # reading as terminals on one corridor.  The connecting necks remain
        # deliberately narrow so entering a room feels like crossing a threshold.
        self._paint_rect(-5, -4, -1, 0, "archive")
        self._paint_rect(-10, -6, -3, 2, "archive")

        self._paint_rect(12, 13, 5, 6, "feedback")
        self._paint_rect(14, 18, 3, 8, "feedback")

        self._paint_rect(-13, -12, 11, 12, "dead")
        self._paint_rect(-18, -14, 9, 14, "dead")

        # Pass 09: optional false-near corridor.  The physical route is honest and
        # walkable; only the camera lens lies about its apparent distance.  The
        # far room is optional and contains no required progression.
        self._paint_rect(19, 36, 5, 6, "falsehall")
        self._paint_rect(37, 42, 2, 9, "focus")

        # Pass 10: three optional authored anomaly spaces.  They are ordinary
        # walkable rooms with honest collision; the wrongness comes from lighting,
        # memory overlays and composition rather than impossible blockers.
        self._paint_rect(1, 2, -12, -11, "unlit")
        self._paint_rect(3, 8, -15, -8, "unlit")

        self._paint_rect(-4, -3, 20, 21, "echo")
        self._paint_rect(-9, -5, 18, 23, "echo")

        self._paint_rect(-8, -7, -5, -4, "witness")
        self._paint_rect(-10, -6, -9, -6, "witness")

        # Pass 11: a recognizably ordinary side room that lies about continuity.
        # It branches south from Analog through a real two-cell threshold.  A
        # four-metre west recess looks like another corridor through Andrew's
        # depth blur, but it ends at an ordinary visible wall when approached.
        self._paint_rect(-10, -9, 6, 7, "return")
        self._paint_rect(-13, -6, 3, 6, "return")
        self._paint_rect(-17, -14, 4, 5, "return")

        # Pass 12: always-real secret seam/shortcut.  It is merely hard to read
        # until the first remote recovery exposes its edge language.
        self._paint_rect(3, 4, -3, -2, "seam")
        self._paint_rect(5, 8, -5, 0, "seam")
        self._paint_rect(5, 6, -8, -6, "seam")

    def _instance_rng(self, cycle: int, salt: int = 0):
        return random.Random((self.dream_seed * 1000003) ^ (int(cycle) * 9176) ^ int(salt))

    def _reveal_memory_seam(self):
        if self._memory_seam_revealed or self.null_layer:
            return False
        self._memory_seam_revealed = True
        for np in self._memory_seam_nodes:
            np.setColor(0.035, 0.14, 0.16, 0.28)
        return True

    def _set_glasses_anchor_for_cycle(self, cycle: int):
        if self.glasses_collected or not self._glasses_anchors:
            return
        rng = self._instance_rng(cycle, 44041)
        idx = rng.randrange(len(self._glasses_anchors))
        self.glasses_anchor_index = idx
        self.glasses_pos = Point3(self._glasses_anchors[idx])
        if self.glasses_root is not None:
            self.glasses_root.setPos(self.glasses_pos.x, self.glasses_pos.y, 0.24)
            self.glasses_root.show()

    def _apply_instance_variant(self, cycle: int):
        if self.null_layer:
            return
        rng = self._instance_rng(cycle, 12012)
        if self._false_sleeper_roots:
            indices = list(range(len(self._false_sleeper_roots)))
            rng.shuffle(indices)
            chosen = tuple(sorted(indices[:2 + (1 if rng.random() < 0.35 else 0)]))
            self._false_sleeper_profile_indices = chosen
            self._false_sleeper_visible_indices = chosen
            for i, root in enumerate(self._false_sleeper_roots):
                root.show() if i in chosen else root.hide()
        self._set_glasses_anchor_for_cycle(cycle)
        trace_rng = self._instance_rng(cycle, 87191)
        self._gleebs_trace_enabled = trace_rng.random() < 0.72
        self._gleebs_trace_seen = False
        self._gleebs_trace_vanished = False
        self._gleebs_trace_anchor_index = trace_rng.randrange(len(self._gleebs_trace_anchors))
        if self._gleebs_trace_root is not None:
            pos, heading = self._gleebs_trace_anchors[self._gleebs_trace_anchor_index]
            self._gleebs_trace_root.setPos(pos)
            self._gleebs_trace_root.setH(heading)
            self._gleebs_trace_root.show() if self._gleebs_trace_enabled else self._gleebs_trace_root.hide()
            for eye in self._gleebs_trace_eyes:
                eye.show() if trace_rng.random() < 0.82 else eye.hide()
        self._apply_destabilization_response()
        self._instance_signature = (
            f"cycle={int(cycle)};route={self.route_profile_index}:{self.route_signature};"
            f"glasses={self.glasses_anchor_index};"
            f"false={','.join(map(str, self._false_sleeper_visible_indices))};"
            f"gleebs={'1' if self._gleebs_trace_enabled else '0'}:{self._gleebs_trace_anchor_index}"
        )

    def _point_observed(self, point: Point3, heading: float, x: float, y: float, half_fov: float = 48.0) -> bool:
        dx, dy = point.x - x, point.y - y
        dist = math.hypot(dx, dy)
        if dist <= 0.05:
            return True
        fwd_x = -math.sin(math.radians(heading))
        fwd_y = math.cos(math.radians(heading))
        dot = (dx / dist) * fwd_x + (dy / dist) * fwd_y
        return dot > math.cos(math.radians(half_fov)) and self.has_clear_line(x, y, point.x, point.y)

    def _configure_texture(self, tex: Texture):
        tex.setWrapU(Texture.WMRepeat)
        tex.setWrapV(Texture.WMRepeat)
        tex.setMinfilter(Texture.FTLinearMipmapLinear)
        tex.setMagfilter(Texture.FTLinear)
        tex.setAnisotropicDegree(8)
        return tex

    def _load_textures(self):
        variant_dir = self.texture_dir / "dream_variants"
        for style in ZONE_STYLES.values():
            for name in (style.wall_texture, style.floor_texture, style.ceiling_texture):
                if name in self.textures:
                    continue
                tex = self.base.loader.loadTexture(Filename.fromOsSpecific(str(self.texture_dir / name)))
                self.textures[name] = self._configure_texture(tex)
                variants = [self.textures[name]]
                stem = Path(name).stem
                for suffix in ("A", "B"):
                    candidate = variant_dir / f"{stem}_{suffix}.png"
                    if candidate.exists():
                        vtex = self.base.loader.loadTexture(Filename.fromOsSpecific(str(candidate)))
                        variants.append(self._configure_texture(vtex))
                self.texture_variants[name] = tuple(variants)

    def _add_box(self, name, pos, scale, texture_name=None, color=(1, 1, 1, 1), light_off=False, parent=None, zone=None, cycle_color=True):
        parent = parent or self.root
        np = _make_box_geom(name, *scale, uv_scale=(0.85, 0.85))
        np.reparentTo(parent)
        np.setPos(*pos)
        if texture_name:
            np.setTexture(self.textures[texture_name], 1)
            self._surface_records.append((np, texture_name, zone))
        np.setColor(*color)
        if zone:
            np.setTag("dream-zone", zone)
            self._zone_visual_nodes.setdefault(zone, []).append(np)
        if light_off:
            np.setLightOff(1)
            if cycle_color and not texture_name and "-node" not in np.getName():
                self._cycle_color_nodes.append((np, Vec4(*color), zone))
        return np

    @property
    def cycle_signature(self) -> str:
        return self._cycle_signature

    def _cycle_rng(self, cycle: int, salt: int = 0):
        return random.Random((self.dream_seed * 1000003 + cycle * 9176 + salt * 131) & 0xFFFFFFFF)

    @staticmethod
    def _bounded_tint(rng, amount: float = 0.045):
        # Small RGB disagreement keeps the world recognizably the same while making
        # each dream re-entry feel fractionally misremembered.
        return (
            1.0 + rng.uniform(-amount, amount),
            1.0 + rng.uniform(-amount, amount),
            1.0 + rng.uniform(-amount, amount),
            1.0,
        )

    def apply_dream_cycle(self, cycle: int, force: bool = False) -> bool:
        cycle = max(0, int(cycle))
        if cycle == self.dream_cycle and self._cycle_signature and not force:
            return False
        self.dream_cycle = cycle
        rng = self._cycle_rng(cycle, 11)
        stage = TextureStage.getDefault()

        # Pick one coherent variant per source texture.  Some textures intentionally
        # stay on the original image in a cycle so the room is never totally remixed.
        texture_choice: dict[str, int] = {}
        tint_choice: dict[str, tuple[float, float, float, float]] = {}
        uv_choice: dict[str, tuple[float, float, float]] = {}
        for name, variants in sorted(self.texture_variants.items()):
            local = self._cycle_rng(cycle, sum(name.encode("utf-8")))
            roll = local.random()
            if len(variants) <= 1 or roll < 0.38:
                idx = 0
            elif roll < 0.70:
                idx = 1
            else:
                idx = min(2, len(variants) - 1)
            texture_choice[name] = idx
            tint_choice[name] = self._bounded_tint(local, 0.035 if "stable" in name else 0.050)
            # Tiny phase/scale drift is enough to make repeating grids and panels
            # appear subtly re-authored without turning them into random noise.
            uv_choice[name] = (
                local.uniform(-0.045, 0.045),
                local.uniform(-0.045, 0.045),
                local.uniform(0.975, 1.030),
            )

        for np, base_name, zone in self._surface_records:
            variants = self.texture_variants.get(base_name, (self.textures[base_name],))
            idx = min(texture_choice.get(base_name, 0), len(variants) - 1)
            np.setTexture(variants[idx], 1)
            np.setColorScale(*tint_choice.get(base_name, (1, 1, 1, 1)))
            u, v, scale = uv_choice.get(base_name, (0.0, 0.0, 1.0))
            np.setTexOffset(stage, u, v)
            np.setTexScale(stage, scale, scale)

        # Emissive trims and non-textured architecture receive the same restrained
        # dream-cycle color disagreement.  Stable cyan elements move less.
        for idx, (np, base_color, zone) in enumerate(self._cycle_color_nodes):
            local = self._cycle_rng(cycle, 5000 + idx)
            amount = 0.025 if base_color.y > 0.65 and base_color.z > 0.65 else 0.060
            mul = self._bounded_tint(local, amount)
            np.setColor(
                max(0.0, min(1.0, base_color.x * mul[0])),
                max(0.0, min(1.0, base_color.y * mul[1])),
                max(0.0, min(1.0, base_color.z * mul[2])),
                base_color.w,
            )

        for idx, (light_np, base_color, zone) in enumerate(self._dream_lights):
            local = self._cycle_rng(cycle, 9000 + idx)
            mul = self._bounded_tint(local, 0.050)
            exposure = {"dead": 0.52, "archive": 0.68, "buffer": 0.78, "falsehall": 0.46, "focus": 0.72, "unlit": 0.28, "echo": 0.64, "witness": 0.42, "return": 0.58, "seam": 0.38}.get(zone, 1.0)
            exposure *= local.uniform(0.94, 1.06)
            light_np.node().setColor(Vec4(
                max(0.0, min(1.0, base_color.x * mul[0] * exposure)),
                max(0.0, min(1.0, base_color.y * mul[1] * exposure)),
                max(0.0, min(1.0, base_color.z * mul[2] * exposure)),
                1.0,
            ))

        # Optional anomaly props shift slightly between dream cycles, but never
        # enough to stop being the same room.  This keeps respawns uncertain while
        # preserving navigation and recognition.
        if self._witness_root is not None:
            local = self._cycle_rng(cycle, 17777)
            dx = local.uniform(-0.14, 0.14)
            dz = local.uniform(-0.025, 0.035)
            self._witness_root.setPos(self._witness_base_pos.x + dx, self._witness_base_pos.y, self._witness_base_pos.z + dz)
            self._witness_root.setH(local.uniform(-3.2, 3.2))
        echo_rng = self._cycle_rng(cycle, 18881)
        # The Return Room begins each dream cycle with the same recognizable
        # wall-mounted memory bracket, but its exact resting place is slightly
        # misremembered.  The larger shift can only occur later while unseen.
        if self._return_memory_root is not None:
            rrng = self._cycle_rng(cycle, 19991)
            self._return_memory_cycle_pos = Point3(
                self._return_memory_base_pos.x,
                self._return_memory_base_pos.y + rrng.uniform(-0.08, 0.08),
                self._return_memory_base_pos.z + rrng.uniform(-0.015, 0.025),
            )
            self._return_memory_shifted = False
            self._apply_return_memory_visual(False)
        self._anomaly_signature = (
            f"witness:{self._witness_root.getX() if self._witness_root else 0.0:.3f}"
            f"|echo:{echo_rng.uniform(0.76, 0.96):.3f}"
            f"|return:{self._return_memory_cycle_pos.y:.3f}"
        )

        self._apply_stabilized_zone_overrides()
        if self._memory_seam_revealed:
            for np in self._memory_seam_nodes:
                np.setColor(0.08, 0.72, 0.76, 0.82)
        self._apply_instance_variant(self.dream_cycle)

        signature_bits = [f"{name}:{texture_choice[name]}" for name in sorted(texture_choice)]
        signature_bits.append(f"cycle:{cycle}")
        self._cycle_signature = "|".join(signature_bits)
        return True

    def advance_dream_cycle(self) -> str:
        self.apply_dream_cycle(self.dream_cycle + 1)
        return self._cycle_signature

    def cycle_environment_colors(self):
        if self.null_layer:
            return (0.18, 0.18, 0.19), (0.035, 0.035, 0.038)
        rng = self._cycle_rng(self.dream_cycle, 12000)
        fog = (
            0.018 * (1.0 + rng.uniform(-0.16, 0.18)),
            0.010 * (1.0 + rng.uniform(-0.12, 0.22)),
            0.030 * (1.0 + rng.uniform(-0.18, 0.18)),
        )
        bg = (
            0.008 * (1.0 + rng.uniform(-0.14, 0.16)),
            0.005 * (1.0 + rng.uniform(-0.12, 0.20)),
            0.012 * (1.0 + rng.uniform(-0.14, 0.18)),
        )
        return fog, bg

    @property
    def anomaly_signature(self) -> str:
        return self._anomaly_signature

    def update_anomalies(self, x: float, y: float, time_s: float, heading: float | None = None):
        """Update subtle authored dream errors without changing traversal authority.

        Returns sparse audio event names for anomalies that actually changed state.
        """
        events = []
        if self.null_layer:
            return events
        # Lightless Gallery: ceiling fixtures visibly glow *after* the player has
        # passed them, but they cast no corresponding light.  The mismatch reads as
        # a delayed visual memory rather than a conventional flicker.
        in_unlit = self.zone_at(x, y) == "unlit"
        for np, mark_x in self._unlit_afterglow:
            if not in_unlit:
                intensity = 0.18
            else:
                # Entering from the east means decreasing X.  A passed fixture is
                # east of the player and lingers brightly behind them.
                passed = max(0.0, min(1.0, (mark_x - x + 0.10) / 1.30))
                pulse = 0.90 + 0.10 * math.sin(time_s * 2.3 + mark_x)
                intensity = 0.16 + 0.78 * passed * pulse
            np.setColorScale(intensity, intensity, intensity, 1.0)

        # Echo Room: from the doorway, translucent cyan memory skins make the room
        # look like a misplaced copy of the Stable Room.  As the player approaches,
        # the borrowed memory fades and the room resolves into its real surfaces.
        if self._echo_bleed_nodes:
            dist = math.hypot(x + 7.0, y - 20.5)
            # Strong when seen from outside/at range; mostly gone at arm's length.
            alpha = max(0.0, min(0.82, (dist - 1.8) / 6.2))
            if self.zone_at(x, y) == "echo":
                alpha *= 0.72
            for idx, np in enumerate(self._echo_bleed_nodes):
                shimmer = 0.94 + 0.06 * math.sin(time_s * 0.7 + idx * 1.7)
                np.setColorScale(1.0, 1.0, 1.0, alpha * shimmer)

        # Return Room: one wall-mounted bracket is allowed to recompose itself,
        # but only after Andrew has entered the room and actually looks away from
        # it.  It never changes collision, blocks a route, or teleports.  The
        # effect is a continuity error discovered only when the player looks back.
        if self._return_memory_root is not None and heading is not None and self.zone_at(x, y) == "return":
            dx = self._return_memory_target.x - x
            dy = self._return_memory_target.y - y
            dist = max(0.0001, math.hypot(dx, dy))
            h = math.radians(float(heading))
            fx, fy = -math.sin(h), math.cos(h)
            dot = (dx / dist) * fx + (dy / dist) * fy
            observed = dot > math.cos(math.radians(52.0)) and dist < 8.5
            if not self._return_memory_shifted and not observed and dist < 7.0:
                self._return_memory_shifted = True
                self._apply_return_memory_visual(True)
                events.append("memory_shift")

        if self._gleebs_trace_enabled and self._gleebs_trace_root is not None and not self._gleebs_trace_vanished and heading is not None:
            point = self._gleebs_trace_root.getPos(self.base.render)
            observed = self._point_observed(point, float(heading), x, y, half_fov=52.0)
            if observed:
                self._gleebs_trace_seen = True
            elif self._gleebs_trace_seen:
                self._gleebs_trace_vanished = True
                self._gleebs_trace_root.hide()
                events.append("gleebs_trace")
        return tuple(events)

    def _apply_return_memory_visual(self, shifted: bool):
        if self._return_memory_root is None:
            return
        base = self._return_memory_cycle_pos
        if shifted:
            self._return_memory_root.setPos(base.x, base.y + 0.34, base.z + 0.070)
            self._return_memory_root.setR(0.0)
            for np in self._return_memory_parts:
                np.setColorScale(0.78, 1.08, 1.18, 1.0)
        else:
            self._return_memory_root.setPos(base)
            self._return_memory_root.setR(0.0)
            for np in self._return_memory_parts:
                np.setColorScale(1.0, 1.0, 1.0, 1.0)

    @property
    def return_memory_shifted(self) -> bool:
        return self._return_memory_shifted

    def _add_wall_collision(self, name, center, half_extents):
        cnode = CollisionNode(name)
        cnode.setIntoCollideMask(WALL_MASK)
        cnode.addSolid(CollisionBox(Point3(*center), *half_extents))
        np = self.root.attachNewNode(cnode)
        return np

    def _dominant_zone(self, cell, neighbor=None):
        return self.walkable.get(cell) or (self.walkable.get(neighbor) if neighbor else None) or "intake"

    def _build_geometry(self):
        # Floor/ceiling tiles. Tiles preserve the narrow rhythm rather than presenting giant flat slabs.
        for (x, y), zone in self.walkable.items():
            style = ZONE_STYLES[zone]
            self._add_box(f"floor-{x}-{y}", (x + 0.5, y + 0.5, -FLOOR_THICK * 0.5), (CELL, CELL, FLOOR_THICK), style.floor_texture, zone=zone)
            self._add_box(f"ceiling-{x}-{y}", (x + 0.5, y + 0.5, WALL_HEIGHT + CEILING_THICK * 0.5), (CELL, CELL, CEILING_THICK), style.ceiling_texture, zone=zone)

        dirs = [
            ((-1, 0), "west"), ((1, 0), "east"), ((0, -1), "south"), ((0, 1), "north")
        ]
        for (x, y), zone in self.walkable.items():
            style = ZONE_STYLES[zone]
            for (dx, dy), label in dirs:
                nb = (x + dx, y + dy)
                if nb in self.walkable:
                    continue
                if dx:
                    wx = x + (0.0 if dx < 0 else 1.0)
                    wy = y + 0.5
                    self._add_box(f"wall-{x}-{y}-{label}", (wx, wy, WALL_HEIGHT * 0.5), (WALL_THICK, CELL + 0.02, WALL_HEIGHT), style.wall_texture, zone=zone)
                    self._add_wall_collision(f"col-{x}-{y}-{label}", (wx, wy, WALL_HEIGHT * 0.5), (WALL_THICK * 0.5, CELL * 0.5, WALL_HEIGHT * 0.5))
                    # restrained luminous seam
                    self._add_box(f"trim-{x}-{y}-{label}", (wx - dx * (WALL_THICK * 0.55), wy, 0.18), (0.018 if dx else CELL, CELL if dx else 0.018, 0.035), color=style.trim_color, light_off=True, zone=zone)
                else:
                    wx = x + 0.5
                    wy = y + (0.0 if dy < 0 else 1.0)
                    self._add_box(f"wall-{x}-{y}-{label}", (wx, wy, WALL_HEIGHT * 0.5), (CELL + 0.02, WALL_THICK, WALL_HEIGHT), style.wall_texture, zone=zone)
                    self._add_wall_collision(f"col-{x}-{y}-{label}", (wx, wy, WALL_HEIGHT * 0.5), (CELL * 0.5, WALL_THICK * 0.5, WALL_HEIGHT * 0.5))
                    self._add_box(f"trim-{x}-{y}-{label}", (wx, wy - dy * (WALL_THICK * 0.55), 0.18), (CELL, 0.018, 0.035), color=style.trim_color, light_off=True, zone=zone)

    def _build_decor(self):
        # Nested frame tunnel: repeated portals make the north run feel digitally recursive.
        for y in (18.0, 20.5, 23.0, 25.5):
            color = (0.95, 0.08, 0.85, 1) if int(y * 2) % 5 else (0.08, 0.88, 1.0, 1)
            self._add_box("frame-L", (-2.02, y, 1.28), (0.08, 0.16, 2.42), color=color, light_off=True)
            self._add_box("frame-R", (2.02, y, 1.28), (0.08, 0.16, 2.42), color=color, light_off=True)
            self._add_box("frame-T", (0, y, 2.48), (4.12, 0.16, 0.08), color=color, light_off=True)

        # Analog chamber wall blades: shallow angled slashes inspired by bad geometric reconstruction.
        for i in range(6):
            x = -10.75 + i * 0.95
            blade = self._add_box("analog-blade", (x, 15.02, 1.30), (0.11, 0.035, 1.75), color=(1.0, 0.17 + i * 0.04, 0.04, 1), light_off=True)
            blade.setR(-24 if i % 2 else 24)

        # Green chamber concentric edge lines toward a dead-black recess.
        for i in range(3):
            z = 0.34 + i * 0.48
            self._add_box("green-line-left", (4.14, 6.6, z), (0.025, 6.4 - i * 0.65, 0.025), color=(0.25, 1, 0.45, 1), light_off=True)
            # The east-side linework leaves a real visual gap at the new branch
            # doorway instead of drawing a glowing bar across the opening.
            self._add_box("green-line-right-south", (11.86, 3.95, z), (0.025, 1.45, 0.025), color=(0.55, 1, 0.20, 1), light_off=True)
            self._add_box("green-line-right-north", (11.86, 8.65, z), (0.025, 1.85, 0.025), color=(0.55, 1, 0.20, 1), light_off=True)

        # Stable room centerpiece: a quiet uncorrupted data column; no gameplay function yet.
        column = self._add_box("stable-data-column", (8.2, 23.2, 1.05), (0.24, 0.24, 2.1), color=(0.18, 0.82, 0.95, 0.32), light_off=True)
        column.setTransparency(TransparencyAttrib.MAlpha)
        for z in (0.38, 0.83, 1.28, 1.73):
            self._add_box("stable-crossbar", (8.2, 23.2, z), (0.80, 0.05, 0.035), color=(0.12, 0.75, 0.95, 1), light_off=True)

        # Ceiling strip lights in major travel lanes.
        fixtures = [
            (0, -16, "intake"), (0, -10, "intake"), (0, -2, "relay"),
            (0, 5, "pressure"), (0, 11, "pressure"), (0, 18.5, "buffer"),
            (0, 24.5, "buffer"), (7.5, 6.5, "lattice"), (-8.0, 11.5, "analog"),
            (8.0, 24.5, "stable"),
        ]
        for x, y, zone in fixtures:
            style = ZONE_STYLES[zone]
            self._add_box("ceiling-light", (x, y, 2.49), (0.72, 0.18, 0.035), color=style.light_color, light_off=True)

        # Branch thresholds.  These are architectural openings, not UI markers.
        # Each frame sits around a real two-cell walkable neck so visual and
        # traversal authority remain the same.
        self._add_threshold("archive-threshold", (-3.92, -0.0, 0.0), axis="x", color=(0.62, 0.18, 1.0, 1))
        self._add_threshold("feedback-threshold", (11.92, 6.0, 0.0), axis="x", color=(0.18, 1.0, 0.66, 1))
        self._add_threshold("dead-threshold", (-11.92, 12.0, 0.0), axis="x", color=(1.0, 0.16, 0.04, 1))
        self._add_threshold("unlit-threshold", (0.92, -11.5, 0.0), axis="x", color=(0.28, 0.34, 0.46, 0.58))
        self._add_threshold("echo-threshold", (-2.92, 20.5, 0.0), axis="x", color=(0.34, 0.58, 0.68, 0.62))
        self._add_threshold("witness-threshold", (-7.5, -3.92, 0.0), axis="y", color=(0.44, 0.16, 0.52, 0.56))
        self._add_threshold("return-threshold", (-9.5, 7.92, 0.0), axis="y", color=(0.72, 0.20, 0.42, 0.60))
        self._add_threshold("return-false-exit", (-13.92, 5.0, 0.0), axis="x", color=(0.07, 0.19, 0.23, 1.0))

        # Archive Cell: sparse side-wall data ribs suggest stored records
        # without putting bright rectangular slabs in the player's path.
        for i in range(5):
            x = -9.55 + i * 0.78
            c = (0.11 + i * 0.012, 0.035, 0.18 + i * 0.018, 1)
            left = self._add_box(f"archive-rib-a-{i}", (x, -2.87, 1.18), (0.065, 0.055, 2.08), color=c, light_off=True)
            right = self._add_box(f"archive-rib-b-{i}", (x, 2.87, 1.18), (0.065, 0.055, 2.08), color=c, light_off=True)
            left.setR(-7.0 + i * 2.5)
            right.setR(7.0 - i * 2.5)
            self._add_box(f"archive-rib-top-{i}", (x, 0.0, 2.34), (0.055, 5.72, 0.045), color=(0.16, 0.045, 0.25, 1), light_off=True)

        # Feedback Room: nested fins point toward the stabilizer and produce
        # parallax/moiré movement while walking rather than a flat painted wall.
        for i in range(7):
            x = 14.25 + i * 0.60
            fin = self._add_box(
                f"feedback-fin-{i}", (x, 8.78, 1.20), (0.10, 0.055, 2.15),
                color=(0.10, 0.55 + i * 0.045, 0.38 + i * 0.025, 1), light_off=True
            )
            fin.setR(-17.0 if i % 2 else 17.0)

        # Dead Channel: broken horizontal bars make the room feel like a frozen
        # failed video field.  The gaps deliberately do not form collision.
        for i in range(8):
            z = 0.34 + i * 0.25
            width = 3.5 - (i % 3) * 0.42
            self._add_box(
                f"dead-scanbar-{i}", (-17.75 + width * 0.5, 14.78, z),
                (width, 0.035, 0.055), color=(0.90, 0.10 + i * 0.018, 0.035, 1), light_off=True
            )

    def _build_worldbuilding(self):
        # Aesthetic/world-building pass: the architecture should imply a damaged
        # dream-recording facility without adding explanatory HUD text.  All of
        # these pieces are non-colliding environmental details.

        # Dream Catcher relay spindle in the first release room.  It hangs above
        # head height so the room remains physically open while suggesting that
        # this space once routed recorded dreams rather than ordinary power.
        spindle = self.root.attachNewNode("dream-catcher-relay-spindle")
        spindle.setPos(-2.15, -2.0, 0.0)
        relay_spine = self._add_box("relay-spine", (0, 0, 2.02), (0.045, 0.045, 0.92), color=(0.10, 0.74, 1.0, 0.72), light_off=True, parent=spindle, cycle_color=False)
        self.relay_spindle_parts.append(relay_spine)
        # Twelve short tangent segments form a recognizable suspended ring instead
        # of a stack of bright rectangular bars.  The ring sits in the X/Z plane.
        for ring_idx, radius in enumerate((0.30, 0.43)):
            for seg in range(12):
                a = math.tau * seg / 12.0
                x = math.cos(a) * radius
                z = 2.04 + math.sin(a) * radius
                col = (0.78, 0.10, 0.92, 0.68) if ring_idx == 0 else (0.06, 0.72, 0.96, 0.58)
                piece = self._add_box(f"relay-ring-{ring_idx}-{seg}", (x, 0.0, z), (0.20, 0.03, 0.024), color=col, light_off=True, parent=spindle, cycle_color=False)
                piece.setR(-math.degrees(a) - 90.0)
                self.relay_spindle_parts.append(piece)

        # Pressure-hall phosphor memories.  These are recessed black display wounds
        # with broken color traces, not openings; their geometry stays flush with
        # the wall and cannot contradict collision.
        for i, y in enumerate((5.0, 8.35, 11.7, 14.65)):
            side = -1 if i % 2 == 0 else 1
            x = -0.905 if side < 0 else 0.905
            self._add_box(f"pressure-memory-black-{i}", (x, y, 1.37), (0.025, 1.34, 0.72), color=(0.002, 0.001, 0.006, 1.0), light_off=True)
            for j in range(4):
                z = 1.13 + j * 0.16
                col = (0.86, 0.08 + 0.05*j, 0.92, 0.72) if (i+j)%2 == 0 else (0.05, 0.72, 1.0, 0.72)
                self._add_box(f"pressure-trace-{i}-{j}", (x - side*0.014, y - 0.42 + j*0.21, z), (0.018, 0.34, 0.025), color=col, light_off=True)

        # Thin signal vein runs through the original intake toward the pressure
        # corridor.  It ties the disconnected color families together as one
        # damaged Dream Catcher data path.
        for y0, y1, col in ((-19.0, -5.3, (1.0, 0.10, 0.55, 0.72)), (-4.7, 2.2, (0.08, 0.76, 1.0, 0.72)), (3.2, 16.8, (0.72, 0.10, 1.0, 0.72))):
            mid = (y0 + y1) * 0.5
            self._add_box("ceiling-signal-vein", (0.66, mid, 2.475), (0.035, y1-y0, 0.022), color=col, light_off=True)

        # Analog chamber observation wounds: black recesses with displaced scan
        # stripes.  They read as dead recording surfaces rather than fake doors.
        for i, x in enumerate((-10.0, -8.3, -6.6)):
            self._add_box(f"analog-recess-{i}", (x, 15.905, 1.33), (1.22, 0.024, 0.72), color=(0.004, 0.001, 0.001, 1.0), light_off=True)
            for j in range(3):
                self._add_box(f"analog-recess-line-{i}-{j}", (x - 0.36 + j*0.36, 15.886, 1.18 + j*0.15), (0.24, 0.018, 0.025), color=(1.0, 0.18 + j*0.08, 0.025, 0.78), light_off=True)

        # Lattice chamber hanging signal filaments give the room vertical depth and
        # reinforce the idea that the brick texture is only one layer of a larger
        # rendered memory structure.
        for i, x in enumerate((5.0, 6.6, 8.2, 9.8, 11.0)):
            length = 0.48 + (i % 3) * 0.22
            self._add_box(f"lattice-filament-{i}", (x, 4.2 + (i%2)*4.8, 2.36-length*0.5), (0.025, 0.025, length), color=(0.18, 1.0, 0.42, 0.62), light_off=True)

        # Stable room gets the inverse treatment: broad calm ceiling rails and no
        # broken fragments.  It should feel reconstructed rather than merely blue.
        for x in (6.1, 8.1, 10.1):
            self._add_box("stable-ceiling-rail", (x, 23.4, 2.46), (0.055, 6.3, 0.035), color=(0.10, 0.58, 0.72, 0.55), light_off=True)

        # False-near hall: a sparse series of ceiling marks provides motion cues
        # while the changing lens resists the expected apparent approach.  The far
        # threshold is real geometry around a real opening.
        for i, x in enumerate((21.0, 24.0, 27.0, 30.0, 33.0, 35.5)):
            alpha = 0.20 + i * 0.035
            self._add_box(f"falsehall-ceiling-mark-{i}", (x, 6.0, 2.47), (0.045, 1.35, 0.025), color=(0.42, 0.28, 0.72, alpha), light_off=True)
        self._add_threshold("falsehall-far-threshold", (36.92, 6.0, 0.0), axis="x", color=(0.52, 0.64, 0.78, 0.78))

        # The optional far room has one deliberately duplicated architectural
        # memory: a small copy of the relay spindle's ring shape, inert and dark.
        # It is recognisable, not random, and has no gameplay authority.
        for seg in range(8):
            a = math.tau * seg / 8.0
            x = 39.15 + math.cos(a) * 0.36
            z = 1.70 + math.sin(a) * 0.36
            piece = self._add_box(f"focus-memory-ring-{seg}", (x, 9.78, z), (0.24, 0.025, 0.025), color=(0.16, 0.22, 0.30, 0.56), light_off=True)
            piece.setR(-math.degrees(a) - 90.0)

        # Pass 10 — Lightless Gallery.  The fixtures are visibly luminous meshes
        # but intentionally have no matching PointLight, so the room remains far
        # darker than the hardware suggests.  Their delayed afterglow is updated
        # from player position by update_anomalies().
        for i, x in enumerate((3.8, 5.1, 6.4, 7.7)):
            glow = self._add_box(
                f"unlit-late-fixture-{i}", (x, -11.55, 2.46), (0.46, 0.16, 0.028),
                color=(0.34, 0.44, 0.58, 0.92), light_off=True, zone="unlit", cycle_color=False,
            )
            self._unlit_afterglow.append((glow, x))
        # One low floor seam at the entrance preserves orientation without curing
        # the room's darkness.
        self._add_box("unlit-entry-seam", (3.22, -11.5, 0.10), (0.035, 1.55, 0.035), color=(0.18, 0.28, 0.40, 0.72), light_off=True, zone="unlit", cycle_color=False)

        # Pass 10 — Echo Room.  Sparse borrowed rails imitate the Stable Room's
        # calm architecture when seen through the doorway, then fade as the player
        # approaches.  Avoid full-wall translucent planes: those read as billboards
        # rather than memory corruption.
        echo_specs = []
        for z in (0.46, 1.08, 1.70, 2.30):
            echo_specs.append(((-8.86, 20.5, z), (0.035, 4.10, 0.026)))
            echo_specs.append(((-5.14, 20.5, z), (0.035, 4.10, 0.026)))
        for x in (-8.2, -7.0, -5.8):
            echo_specs.append(((x, 23.86, 1.33), (0.035, 0.025, 2.12)))
        for i, (pos, scale) in enumerate(echo_specs):
            rail = self._add_box(
                f"echo-borrowed-rail-{i}", pos, scale,
                color=(0.10, 0.62, 0.74, 0.64), light_off=True, zone="echo", cycle_color=False,
            )
            rail.setTransparency(TransparencyAttrib.MAlpha)
            self._echo_bleed_nodes.append(rail)
        # A misplaced copy of the calm data column anchors the memory error.
        self._add_box("echo-misplaced-column", (-7.0, 21.9, 0.95), (0.16, 0.16, 1.80), color=(0.10, 0.44, 0.54, 0.42), light_off=True, zone="echo", cycle_color=False)
        for z in (0.52, 0.94, 1.36):
            self._add_box("echo-column-crossbar", (-7.0, 21.9, z), (0.58, 0.04, 0.026), color=(0.10, 0.50, 0.60, 0.54), light_off=True, zone="echo", cycle_color=False)

        # Pass 10 — Witness Alcove.  From the corridor and through Andrew's
        # nearsighted blur, this broken support frame can read as a tall figure.
        # At close range its floor brace and wall tether reveal ordinary structure.
        witness = self.root.attachNewNode("witness-scaffold")
        witness.setPos(self._witness_base_pos)
        self._witness_root = witness
        dark = (0.018, 0.012, 0.024, 1.0)
        edge = (0.15, 0.07, 0.18, 0.56)
        # Two close structural rails merge into a torso-like mass at distance but
        # resolve as separate supports up close.
        self._add_box("witness-torso-a", (-0.055, 0, 1.38), (0.065, 0.13, 0.78), color=dark, light_off=True, parent=witness, cycle_color=False)
        self._add_box("witness-torso-b", (0.055, 0, 1.38), (0.065, 0.13, 0.78), color=dark, light_off=True, parent=witness, cycle_color=False)
        head = self._add_box("witness-head-a", (-0.035, 0, 1.93), (0.065, 0.12, 0.24), color=dark, light_off=True, parent=witness, cycle_color=False)
        head.setR(-4.0)
        head2 = self._add_box("witness-head-b", (0.045, 0, 1.92), (0.060, 0.12, 0.22), color=dark, light_off=True, parent=witness, cycle_color=False)
        head2.setR(3.0)
        self._add_box("witness-cross-brace", (0, 0.045, 1.40), (0.52, 0.045, 0.045), color=(0.085, 0.035, 0.10, 1.0), light_off=True, parent=witness, cycle_color=False)
        for name, px, roll in (("arm-l", -0.19, -7.0), ("arm-r", 0.19, 9.0)):
            limb = self._add_box(name, (px, 0, 1.25), (0.075, 0.10, 1.05), color=dark, light_off=True, parent=witness, cycle_color=False)
            limb.setR(roll)
        for name, px, roll in (("leg-l", -0.08, -2.0), ("leg-r", 0.10, 3.0)):
            limb = self._add_box(name, (px, 0, 0.53), (0.075, 0.10, 0.98), color=dark, light_off=True, parent=witness, cycle_color=False)
            limb.setR(roll)
        self._add_box("witness-floor-brace", (0, 0.16, 0.08), (0.82, 0.44, 0.07), color=(0.05, 0.03, 0.06, 1.0), light_off=True, parent=witness, cycle_color=False)
        self._add_box("witness-wall-tether", (0, 0.30, 1.42), (0.035, 0.64, 0.035), color=edge, light_off=True, parent=witness, cycle_color=False)

        # Return Room continuity error.  The room initially borrows Analog's
        # warm memory, but a sparse wall bracket can recompose itself while it
        # is outside Andrew's view.  Because it is wall-mounted and decorative,
        # the change cannot disagree with collision or obstruct traversal.
        return_root = self.root.attachNewNode("return-memory-bracket")
        return_root.setPos(self._return_memory_base_pos)
        self._return_memory_root = return_root
        rcol = (0.54, 0.14, 0.34, 0.82)
        for name, pos, scale in [
            ("return-memory-v-a", (0.0, -0.68, 1.30), (0.045, 0.045, 1.74)),
            ("return-memory-v-b", (0.0, 0.68, 1.30), (0.045, 0.045, 1.74)),
            ("return-memory-cross-a", (0.0, 0.0, 1.92), (0.045, 1.38, 0.035)),
            ("return-memory-cross-b", (0.0, 0.0, 0.72), (0.045, 0.92, 0.028)),
        ]:
            part = self._add_box(name, pos, scale, color=rcol, light_off=True, parent=return_root, cycle_color=False)
            self._return_memory_parts.append(part)

        # The west recess is a real, walkable four-metre indentation that ends
        # at a real wall.  Dim edge rails carry perspective into the blur so it
        # reads as an open continuation at range, then resolves honestly nearby.
        for yy in (4.08, 5.92):
            self._add_box("return-recess-floor-line", (-15.48, yy, 0.11), (4.55, 0.024, 0.024), color=(0.12, 0.34, 0.39, 0.56), light_off=True, zone="return", cycle_color=False)
        self._add_box("return-recess-ceiling-line", (-15.48, 5.0, 2.47), (4.55, 0.030, 0.026), color=(0.18, 0.38, 0.44, 0.42), light_off=True, zone="return", cycle_color=False)
        for yy in (4.22, 5.78):
            self._add_box("return-recess-back-seam", (-17.90, yy, 1.26), (0.028, 0.032, 1.86), color=(0.10, 0.26, 0.30, 0.42), light_off=True, zone="return", cycle_color=False)

        # Pass 12 — backward-reacting memory seam.  The route is physically real
        # from the beginning, but its edge language is nearly black until the first
        # remote recovery reveals that something in the Relay room changed behind
        # Andrew.  It becomes an optional shortcut into the Lightless Gallery.
        for name, pos, scale in [
            ("seam-entry-left", (3.08, -2.86, 1.28), (0.035, 0.32, 2.10)),
            ("seam-entry-right", (3.08, -1.14, 1.28), (0.035, 0.32, 2.10)),
            ("seam-entry-head", (3.08, -2.0, 2.40), (0.035, 1.64, 0.035)),
            ("seam-secret-line-a", (7.70, -4.72, 0.11), (0.035, 4.60, 0.025)),
            ("seam-secret-line-b", (5.28, -4.72, 1.42), (0.035, 4.60, 0.025)),
        ]:
            np = self._add_box(name, pos, scale, color=(0.012, 0.030, 0.034, 0.32), light_off=True, zone="seam", cycle_color=False)
            np.setTransparency(TransparencyAttrib.MAlpha)
            self._memory_seam_nodes.append(np)

        # False Sleepers are harmless authored structures.  At Andrew's normal
        # distance blur they can read as people, but every one resolves into braces,
        # cables and support feet when approached.  Each dream cycle exposes only a
        # seeded subset, so caution is useful without turning the level procedural.
        false_specs = [
            (Point3(-9.32, 1.35, 0.0), 180.0),
            (Point3(7.52, -14.25, 0.0), 0.0),
            (Point3(-8.18, 22.70, 0.0), 180.0),
            (Point3(38.55, 3.05, 0.0), 90.0),
            (Point3(-16.25, 4.28, 0.0), -90.0),
        ]
        for idx, (pos, heading) in enumerate(false_specs):
            root = self.root.attachNewNode(f"false-sleeper-{idx}")
            root.setPos(pos)
            root.setH(heading)
            dark = (0.012, 0.010, 0.016, 1.0)
            faint = (0.070, 0.090, 0.105, 0.46)
            self._add_box(f"false-sleeper-{idx}-spine", (0, 0, 1.25), (0.105, 0.10, 1.28), color=dark, light_off=True, parent=root, cycle_color=False)
            self._add_box(f"false-sleeper-{idx}-head", (0.035, 0.0, 2.05), (0.15, 0.11, 0.29), color=dark, light_off=True, parent=root, cycle_color=False)
            for side, roll in ((-0.18, -7.0), (0.19, 8.0)):
                arm = self._add_box(f"false-sleeper-{idx}-arm", (side, 0.0, 1.35), (0.065, 0.085, 1.02), color=dark, light_off=True, parent=root, cycle_color=False)
                arm.setR(roll)
            for side in (-0.075, 0.085):
                self._add_box(f"false-sleeper-{idx}-leg", (side, 0.0, 0.52), (0.060, 0.085, 0.98), color=dark, light_off=True, parent=root, cycle_color=False)
            self._add_box(f"false-sleeper-{idx}-floor-foot", (0, 0.12, 0.07), (0.62, 0.40, 0.07), color=(0.035,0.040,0.045,1), light_off=True, parent=root, cycle_color=False)
            tether = self._add_box(f"false-sleeper-{idx}-tether", (0, 0.34, 1.40), (0.028, 0.70, 0.028), color=faint, light_off=True, parent=root, cycle_color=False)
            tether.setTransparency(TransparencyAttrib.MAlpha)
            self._false_sleeper_roots.append(root)

        # Rare Gleebs interference trace.  The player is never told what this is.
        # It is a flattened wall-shadow shape with sharp ears and, on some seeded
        # instances, two faint green eyes.  Once Andrew has seen it, looking away
        # removes it for the rest of that instance.
        gt = self.root.attachNewNode("intercept-shadow-trace")
        self._gleebs_trace_root = gt
        shadow = (0.014, 0.020, 0.018, 0.94)
        eye = (0.18, 1.00, 0.34, 1.00)
        # Keep the trace clearly critter-sized.  It should read like a seated
        # cat/rabbit shadow with oversized ears, never another humanoid Sleeper.
        self._add_box("trace-body", (0, 0, 0.30), (0.56, 0.024, 0.36), color=shadow, light_off=True, parent=gt, cycle_color=False)
        self._add_box("trace-head", (0, 0, 0.60), (0.30, 0.024, 0.28), color=shadow, light_off=True, parent=gt, cycle_color=False)
        self._add_box("trace-leg-l", (-0.18, 0, 0.08), (0.12, 0.024, 0.28), color=shadow, light_off=True, parent=gt, cycle_color=False)
        self._add_box("trace-leg-r", (0.18, 0, 0.08), (0.12, 0.024, 0.28), color=shadow, light_off=True, parent=gt, cycle_color=False)
        ear_l = self._add_box("trace-ear-l", (-0.10, 0, 0.97), (0.10, 0.024, 0.56), color=shadow, light_off=True, parent=gt, cycle_color=False)
        ear_l.setR(-12.0)
        ear_r = self._add_box("trace-ear-r", (0.10, 0, 0.97), (0.10, 0.024, 0.56), color=shadow, light_off=True, parent=gt, cycle_color=False)
        ear_r.setR(12.0)
        for ex in (-0.065, 0.065):
            e = self._add_box("trace-eye", (ex, -0.018, 0.63), (0.030, 0.020, 0.030), color=eye, light_off=True, parent=gt, cycle_color=False)
            e.setDepthOffset(6)
            self._gleebs_trace_eyes.append(e)

        # Null Layer raw exit.  It exists from the start but stays hidden until the
        # glasses remove the dream presentation.  It is neutral geometry, not a
        # holographic objective marker.
        ne = self.root.attachNewNode("null-layer-exit")
        ne.setPos(self.null_exit_pos.x, self.null_exit_pos.y, 0.0)
        self._null_exit_root = ne
        for x in (-0.62, 0.62):
            self._add_box("null-exit-post", (x, 0, 1.20), (0.08, 0.10, 2.25), color=(0.72,0.74,0.76,1), light_off=True, parent=ne, cycle_color=False)
        self._add_box("null-exit-head", (0, 0, 2.30), (1.30, 0.10, 0.08), color=(0.72,0.74,0.76,1), light_off=True, parent=ne, cycle_color=False)
        ne.hide()

        # Hidden optional glasses.  The seeded instance chooses from several
        # hand-authored, reachable hiding anchors.  There is deliberately no plinth.
        g = self.root.attachNewNode("forgotten-glasses")
        g.setPos(self.glasses_pos.x, self.glasses_pos.y, 0.24)
        self.glasses_root = g
        frame_col = (0.12, 0.13, 0.15, 1.0)
        lens_col = (0.30, 0.46, 0.52, 0.16)
        for side in (-0.16, 0.16):
            self._add_box("glasses-top", (side, 0, 0.08), (0.26, 0.025, 0.018), color=frame_col, light_off=True, parent=g, cycle_color=False)
            self._add_box("glasses-bottom", (side, 0, -0.08), (0.26, 0.025, 0.018), color=frame_col, light_off=True, parent=g, cycle_color=False)
            self._add_box("glasses-left", (side-0.13, 0, 0), (0.018, 0.025, 0.16), color=frame_col, light_off=True, parent=g, cycle_color=False)
            self._add_box("glasses-right", (side+0.13, 0, 0), (0.018, 0.025, 0.16), color=frame_col, light_off=True, parent=g, cycle_color=False)
            lens = self._add_box("glasses-lens", (side, 0.008, 0), (0.23, 0.012, 0.13), color=lens_col, light_off=True, parent=g, cycle_color=False)
            lens.setTransparency(TransparencyAttrib.MAlpha)
        self._add_box("glasses-bridge", (0, 0, 0.03), (0.085, 0.025, 0.018), color=frame_col, light_off=True, parent=g, cycle_color=False)
        self._add_box("glasses-arm-a", (-0.29, 0.12, 0.03), (0.018, 0.28, 0.018), color=frame_col, light_off=True, parent=g, cycle_color=False)
        self._add_box("glasses-arm-b", (0.29, 0.12, 0.03), (0.018, 0.28, 0.018), color=frame_col, light_off=True, parent=g, cycle_color=False)
        self._glasses_glint = self._add_box("glasses-glint", (0.14, -0.012, 0.11), (0.028, 0.012, 0.028), color=(0.72, 0.86, 0.90, 0.54), light_off=True, parent=g, cycle_color=False)

    def _add_threshold(self, name: str, pos, axis: str, color):
        x, y, _ = pos
        if axis == "x":
            # Opening extends along Y; jambs sit outside the two-cell neck.
            self._add_box(name + "-jamb-a", (x, y - 1.02, 1.24), (0.10, 0.10, 2.34), color=color, light_off=True)
            self._add_box(name + "-jamb-b", (x, y + 1.02, 1.24), (0.10, 0.10, 2.34), color=color, light_off=True)
            self._add_box(name + "-head", (x, y, 2.42), (0.10, 2.14, 0.10), color=color, light_off=True)
        else:
            self._add_box(name + "-jamb-a", (x - 1.02, y, 1.24), (0.10, 0.10, 2.34), color=color, light_off=True)
            self._add_box(name + "-jamb-b", (x + 1.02, y, 1.24), (0.10, 0.10, 2.34), color=color, light_off=True)
            self._add_box(name + "-head", (x, y, 2.42), (2.14, 0.10, 0.10), color=color, light_off=True)

    def _build_target_beacons(self):
        # These are destination indicators, not blockers.  They frame the real
        # traversable thresholds and change state when a remote relay stabilizes
        # the room beyond them.
        specs = {
            "archive": ((-3.80, 0.0, 2.16), "x", (0.52, 0.10, 0.82, 0.82)),
            "feedback": ((11.80, 6.0, 2.16), "x", (0.08, 0.82, 0.50, 0.82)),
            "dead": ((-11.80, 12.0, 2.16), "x", (0.82, 0.08, 0.025, 0.82)),
            "buffer": ((0.0, 16.86, 2.16), "y", (0.68, 0.10, 0.86, 0.82)),
        }
        for zone, (pos, axis, color) in specs.items():
            x, y, z = pos
            parts = []
            if axis == "x":
                parts.append(self._add_box(f"target-{zone}-left", (x, y-0.72, z), (0.035, 0.34, 0.035), color=color, light_off=True, cycle_color=False))
                parts.append(self._add_box(f"target-{zone}-right", (x, y+0.72, z), (0.035, 0.34, 0.035), color=color, light_off=True, cycle_color=False))
            else:
                parts.append(self._add_box(f"target-{zone}-left", (x-0.72, y, z), (0.34, 0.035, 0.035), color=color, light_off=True, cycle_color=False))
                parts.append(self._add_box(f"target-{zone}-right", (x+0.72, y, z), (0.34, 0.035, 0.035), color=color, light_off=True, cycle_color=False))
            parts.append(self._add_box(f"target-{zone}-pulse", (x, y, z+0.17), (0.08, 0.08, 0.08), color=color, light_off=True, cycle_color=False))
            self._target_beacons[zone] = parts

    def _refresh_target_beacon(self, zone: str):
        stable = zone in self.stabilized_zones
        color = (0.10, 0.86, 1.0, 0.96) if stable else (0.32, 0.045, 0.42, 0.68)
        if zone == "feedback" and not stable:
            color = (0.045, 0.40, 0.25, 0.68)
        elif zone == "dead" and not stable:
            color = (0.40, 0.035, 0.02, 0.68)
        for np in self._target_beacons.get(zone, []):
            np.setColor(*color)
            np.setScale(1.12 if stable else 1.0)

    def _refresh_stabilizer_visual(self, node: StabilityNode):
        if node.active:
            color = (0.10, 0.86, 1.0, 0.86)
            light_color = Vec4(0.10, 0.62, 0.96, 1.0)
        elif node.unlocked:
            color = node.source_color
            light_color = Vec4(node.source_color[0]*0.72, node.source_color[1]*0.72, node.source_color[2]*0.72, 1.0)
        else:
            color = (0.035, 0.045, 0.060, 0.38)
            light_color = Vec4(0.015, 0.020, 0.030, 1.0)
        if node.node_id == "relay-node" and self.relay_spindle_parts:
            spindle_color = color
            for part in self.relay_spindle_parts:
                part.setColor(*spindle_color)
                part.setColorScale(1.0, 1.0, 1.0, 1.0)
        if node.core:
            node.core.setColor(*color)
            node.core.setScale(1.06 if node.active else 1.0)
        if node.cage:
            for geom_np in node.cage.findAllMatches("**/+GeomNode"):
                geom_np.setColor(*color)
        if node.light_np:
            node.light_np.node().setColor(light_color)

    def _apply_stabilized_zone_overrides(self):
        # Remote stabilization calms the actual destination room, not the relay
        # the player is standing beside.  Textures retain room identity but their
        # color disagreement is pulled toward cool reconstructed data.
        for zone in ("archive", "feedback", "dead", "buffer"):
            self._refresh_target_beacon(zone)
            if zone not in self.stabilized_zones:
                continue
            for np in self._zone_visual_nodes.get(zone, []):
                np.setColorScale(0.72, 1.02, 1.10, 1.0)
            for light_np in self._zone_lights.get(zone, []):
                light_np.node().setColor(Vec4(0.10, 0.62, 0.95, 1.0))

    def _build_stability_nodes(self):
        # Pass 13 keeps the same four physical relays and the same trustworthy
        # topology, but assigns their target links from one of six curated orders.
        # Every profile visits Archive, Feedback and Dead exactly once before the
        # final Deep Buffer, so no generated maze or unreachable objective exists.
        next_target = {"relay": self.route_zones[0]}
        for current, target in zip(self.route_zones[:-1], self.route_zones[1:]):
            next_target[current] = target

        physical_specs = [
            ("relay-node", "relay", Point3(-2.15, -2.0, 0.0), (0.12, 0.70, 1.0, 0.72), True),
            ("archive-node", "archive", Point3(-8.0, 0.0, 0.0), (0.70, 0.14, 1.0, 0.65), False),
            ("feedback-node", "feedback", Point3(16.0, 6.0, 0.0), (0.08, 1.0, 0.58, 0.65), False),
            ("dead-node", "dead", Point3(-16.0, 12.0, 0.0), (1.0, 0.12, 0.035, 0.65), False),
        ]
        for node_id, zone, pos, corrupt_color, unlocked in physical_specs:
            target_zone = next_target[zone]
            root = self.root.attachNewNode(node_id)
            root.setPos(pos.x, pos.y, 0.0)
            core = None
            cage = None
            if node_id != "relay-node":
                core = self._add_box(node_id + "-core", (0, 0, 0.88), (0.12, 0.12, 1.34), color=corrupt_color, light_off=True, parent=root, cycle_color=False)
                core.setTransparency(TransparencyAttrib.MAlpha)
                cage = root.attachNewNode(node_id + "-cage")
                for z in (0.40, 0.72, 1.04, 1.36):
                    self._add_box(node_id + "-bar-x", (0, 0, z), (0.50, 0.030, 0.022), color=corrupt_color, light_off=True, parent=cage, cycle_color=False)
                    bar = self._add_box(node_id + "-bar-y", (0, 0, z + 0.07), (0.030, 0.50, 0.022), color=corrupt_color, light_off=True, parent=cage, cycle_color=False)
                    bar.setR(8.0 if int(z * 100) % 2 else -8.0)
            light = PointLight(node_id + "-light")
            light.setColor(Vec4(corrupt_color[0] * 0.72, corrupt_color[1] * 0.72, corrupt_color[2] * 0.72, 1.0))
            light.setAttenuation(Vec3(0.9, 0.38, 0.12))
            light_np = root.attachNewNode(light)
            light_np.setPos(0, 0, 1.0)
            self.root.setLight(light_np)
            self._point_lights.append(light_np)
            node = StabilityNode(
                node_id=node_id, zone=zone, target_zone=target_zone, pos=Point3(pos),
                source_color=corrupt_color, unlocked=unlocked, root=root, core=core, cage=cage, light_np=light_np
            )
            self.stability_nodes[node_id] = node
            self._refresh_stabilizer_visual(node)

        node_by_zone = {node.zone: node.node_id for node in self.stability_nodes.values()}
        self.route_node_order = tuple(["relay-node"] + [node_by_zone[z] for z in self.route_zones[:-1]])

    def _build_lighting(self):
        amb = AmbientLight("ambient")
        # Lower global fill lets authored rooms actually differ in darkness.
        amb.setColor(Vec4(0.064, 0.054, 0.082, 1))
        amb_np = self.root.attachNewNode(amb)
        self.root.setLight(amb_np)

        lights = [
            ((0, -14, 2.25), (1.0, 0.18, 0.48, 1), 10, "intake"),
            ((0, -2, 2.25), (0.10, 0.52, 1.0, 1), 9, "relay"),
            ((0, 8, 2.25), (0.65, 0.12, 1.0, 1), 8, "pressure"),
            ((7.5, 6.4, 2.15), (0.18, 1.0, 0.26, 1), 9, "lattice"),
            ((-8.0, 11.3, 2.15), (1.0, 0.25, 0.06, 1), 8, "analog"),
            ((0, 22, 2.2), (0.48, 0.20, 1.0, 1), 10, "buffer"),
            ((8.0, 23.5, 2.15), (0.18, 0.70, 0.88, 1), 9, "stable"),
            ((-8.0, 0.0, 2.1), (0.38, 0.12, 0.78, 1), 8, "archive"),
            ((16.0, 6.0, 2.1), (0.10, 0.72, 0.48, 1), 8, "feedback"),
            ((-16.0, 12.0, 2.1), (0.56, 0.06, 0.020, 1), 10, "dead"),
            ((28.0, 6.0, 2.22), (0.16, 0.10, 0.30, 1), 13, "falsehall"),
            ((39.7, 6.0, 2.18), (0.34, 0.42, 0.52, 1), 10, "focus"),
            ((3.35, -11.5, 1.05), (0.10, 0.16, 0.24, 1), 14, "unlit"),
            ((-7.0, 20.5, 2.05), (0.20, 0.34, 0.40, 1), 11, "echo"),
            ((-8.0, -7.0, 1.95), (0.18, 0.055, 0.22, 1), 16, "witness"),
            ((-9.3, 4.6, 2.05), (0.36, 0.12, 0.28, 1), 13, "return"),
            ((-16.6, 5.0, 1.25), (0.055, 0.16, 0.18, 1), 19, "return"),
        ]
        for idx, (pos, color, attenuation_scale, zone) in enumerate(lights):
            light = PointLight(f"dream-light-{idx}")
            light.setColor(Vec4(*color))
            light.setAttenuation(Vec3(0.6, 0.04 * attenuation_scale, 0.015 * attenuation_scale))
            np = self.root.attachNewNode(light)
            np.setPos(*pos)
            self.root.setLight(np)
            self._point_lights.append(np)
            self._dream_lights.append((np, Vec4(*color), zone))
            self._zone_lights.setdefault(zone, []).append(np)
        self._apply_stabilized_zone_overrides()
