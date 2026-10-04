"""Frost Circuit in-world runtime for the live ICE HoloVerse region.

The Archivist (Mirror until Pass 282.57) turns the ICE ring into a starter hovercraft race: player vs bot racers,
third-person chase camera, waypoint laps around the ring, safe unload on ESC,
TAB, teleport, or leaving the ICE region. It is intentionally simple and stable
so the region has a complete first playable layer without external launch paths.
"""
from __future__ import annotations

import json
import math
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import (AntialiasAttrib, Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, LineSegs, TextNode, TransparencyAttrib, Vec3)

from holoverse.world_geometry import surface_ring_for_key

from holoverse.frost_track import (
    FROST_TRACK_CENTER_RADIUS, FROST_TRACK_HALF_WIDTH, FROST_TRACK_SAMPLE_COUNT,
    FROST_TRACK_WORLD_CLEARANCE, nearest_centerline_info, sampled_world_centerline,
    track_length as frost_track_length,
)

IN_WORLD_ROUTE = "in_world_region"
FROST_CIRCUIT_SCHEMA = 1
ICE_REGION_NUMBER = 5
_ICE_RING = surface_ring_for_key(6) or {"r0": 3050.0, "r1": 3750.0}
ICE_R0 = float(_ICE_RING["r0"])
ICE_R1 = float(_ICE_RING["r1"])
ICE_TRACK_RADIUS = FROST_TRACK_CENTER_RADIUS
ICE_TRACK_WAYPOINTS = FROST_TRACK_SAMPLE_COUNT
ICE_TRACK_HALF_WIDTH = FROST_TRACK_HALF_WIDTH
ICE_TRACK_OFFROAD_WIDTH = FROST_TRACK_HALF_WIDTH + 18.0
ICE_TRACK_RESET_WIDTH = FROST_TRACK_WORLD_CLEARANCE + 72.0
ICE_WAYPOINT_CAPTURE_RADIUS = 58.0
ICE_REQUIRED_LAPS = 1
ICE_LEAVE_MARGIN = 100.0
ICE_OBSTACLE_COUNT = 0
ICE_LOOP_GATE_COUNT = 0
ICE_WAYPOINT_SCORE = 35
ICE_LOOP_SCORE = 260
ICE_FINISH_SCORE = 750
ICE_SPEED_SCORE_PER_SECOND = 5
ICE_HOVER_BASE_CLEARANCE = 5.8
ICE_HOVER_SPEED_LIFT = 4.2
ICE_SCORE_CRYSTAL_COUNT = 0
ICE_CRYSTAL_SCORE = 120
ICE_CLEAN_STREAK_SCORE = 65
ICE_OVERTAKE_SCORE = 90
ICE_DRIFT_SCORE_PER_SECOND = 18
ICE_BOOST_SCORE_PER_SECOND = 12
BOT_RACERS = ("IO", "Vanta", "Nyx", "Solace", "Ember", "Sable", "Archivist")


def _main_module(cls):
    return sys.modules.get(cls.__module__) or sys.modules.get("__main__")


def install_frost_circuit_runtime(CommandHubApp):
    main = _main_module(CommandHubApp)
    if main is None:
        return

    from holoverse_mode_runtime import resolve_shared_data_root, safe_write_json

    ROOT = Path(getattr(main, "ROOT", Path(__file__).resolve().parent))
    SHARED_DATA_ROOT = resolve_shared_data_root(main, ROOT)
    STATE_DIR = SHARED_DATA_ROOT / "holoverse" / "regions" / "ice" / "races"
    STATE_PATH = STATE_DIR / "frost_circuit_state.json"
    ROOT_PROGRESS_PATH = SHARED_DATA_ROOT / "holoverse" / "progression" / "progression_state.json"
    SHARED_PROGRESS_PATH = SHARED_DATA_ROOT / "holoverse" / "progression" / "progression_state.json"

    from holoverse_mode_runtime import install_in_world_route_aliases

    install_in_world_route_aliases(main)

    def _ensure_dirs():
        for folder in (STATE_DIR, ROOT_PROGRESS_PATH.parent, SHARED_PROGRESS_PATH.parent):
            folder.mkdir(parents=True, exist_ok=True)

    def _floor_z(self, x: float, y: float) -> float:
        mount = getattr(self, "world_shell_mount", None)
        if mount is not None:
            try:
                fn = getattr(mount, "shell_ground_offset_at", None)
                if callable(fn):
                    return float(fn(float(x), float(y)))
            except Exception:
                pass
            try:
                runtime = getattr(mount, "source_runtime", None)
                if runtime is not None and bool(getattr(mount, "source_bridge_active", False)):
                    fn = getattr(runtime, "world_height_at", None)
                    if callable(fn):
                        return float(fn(float(x), float(y)))
            except Exception:
                pass
        try:
            eye = float(getattr(self.cfg, "player_eye_height", 3.95))
            clearance = float(getattr(self.cfg, "terrain_collision_clearance", 0.16))
            grounded = float(self.world_shell_grounded_z(float(x), float(y)))
            return grounded - eye - clearance
        except Exception:
            return 0.0

    def _eye_z(self, x: float, y: float) -> float:
        try:
            return float(self.world_shell_grounded_z(float(x), float(y)))
        except Exception:
            return _floor_z(self, x, y) + float(getattr(self.cfg, "player_eye_height", 3.95)) + 0.16

    def _ice_allowed(self):
        try:
            if self.is_holospace_active():
                return False
        except Exception:
            pass
        try:
            return int(self.current_holoverse_region_number()) == ICE_REGION_NUMBER
        except Exception:
            return True

    def _angle_from_xy(x: float, y: float) -> float:
        return math.atan2(float(y), float(x))

    def _wrap_deg(v: float) -> float:
        while v > 180.0:
            v -= 360.0
        while v < -180.0:
            v += 360.0
        return v

    def _heading_vec(yaw_deg: float) -> Vec3:
        rad = math.radians(float(yaw_deg))
        return Vec3(math.sin(rad), math.cos(rad), 0.0)

    def _yaw_to_target(src: Vec3, target: Vec3) -> float:
        dx = float(target.x - src.x)
        dy = float(target.y - src.y)
        # Panda-style heading: 0 faces +Y, 90 faces +X.
        return math.degrees(math.atan2(dx, dy))

    def _dist2d(a: Vec3, b: Vec3) -> float:
        dx = float(a.x - b.x)
        dy = float(a.y - b.y)
        return math.sqrt(dx * dx + dy * dy)

    def _hovercraft_color(name: str):
        table = {
            "Player": (0.72, 1.00, 1.00, 0.98),
            "IO": (0.82, 0.86, 0.92, 0.95),
            "Vanta": (0.20, 1.00, 0.36, 0.95),
            "Nyx": (0.72, 0.48, 1.00, 0.95),
            "Solace": (0.32, 1.00, 0.92, 0.95),
            "Ember": (1.00, 0.54, 0.18, 0.95),
            "Sable": (0.70, 0.74, 0.78, 0.95),
            "Archivist": (0.82, 0.36, 1.00, 0.95),
        }
        return table.get(str(name), (0.66, 0.86, 1.0, 0.95))

    def _init_state(self):
        self.frost_circuit_active = False
        self.frost_circuit_root = None
        self.frost_circuit_track_root = None
        self.frost_circuit_ui_root = None
        self.frost_circuit_ui_panel = None
        self.frost_circuit_ui_title = None
        self.frost_circuit_ui_status = None
        self.frost_circuit_ui_help = None
        self.frost_circuit_racers = []
        self.frost_circuit_waypoints = []
        self.frost_circuit_obstacles = []
        self.frost_circuit_loop_gates = []
        self.frost_circuit_started_at = 0.0
        self.frost_circuit_finished = False
        self.frost_circuit_exit_prompt_until = 0.0
        self.frost_circuit_last_save_at = 0.0
        self.frost_circuit_best_time = None
        self.frost_circuit_wins = 0
        self.frost_circuit_races_completed = 0
        self.frost_circuit_last_results = []
        self.frost_circuit_state_path = STATE_PATH
        self.frost_circuit_player_saved_pos = None
        self.frost_circuit_player_saved_hpr = None
        self.frost_circuit_obstacles = []
        self.frost_circuit_loop_gates = []
        self.frost_circuit_score = 0
        self.frost_circuit_points_this_run = 0
        self.frost_circuit_total_score = 0
        self.frost_circuit_best_score = 0
        self.frost_circuit_obstacle_hits = 0
        self.frost_circuit_loops_cleared = 0
        self.frost_circuit_last_score_tick = 0.0
        self.frost_circuit_ai_avoidance_events = 0
        self.frost_circuit_score_crystals = []
        self.frost_circuit_crystals_collected = 0
        self.frost_circuit_clean_waypoint_streak = 0
        self.frost_circuit_last_player_rank = None
        self.frost_circuit_rank_bonus_count = 0
        self.frost_circuit_drift_score_bank = 0.0
        self.frost_circuit_boost_score_bank = 0.0
        self.frost_circuit_camera_mode = "far_chase"
        self.frost_circuit_camera_distance = 34.0
        self.frost_circuit_camera_height = 11.5
        self.frost_circuit_camera_lookahead = 40.0
        self.frost_circuit_camera_smooth_pos = None
        self.frost_circuit_camera_smooth_target = None

    def _is_frost_circuit_mode(self, mode):
        data = dict(mode or {})
        manifest = dict(data.get("manifest") or {})
        tokens = " ".join(str(x or "") for x in (
            data.get("name"), data.get("id"), data.get("title"),
            manifest.get("id"), manifest.get("title"), manifest.get("description"),
            manifest.get("host_contract"), manifest.get("preferred_display"),
        )).lower()
        return (
            "frost circuit" in tokens
            or "ice circuit" in tokens
            or "ring race" in tokens
            or "ice race" in tokens
            or str(manifest.get("id") or data.get("id") or "").lower() == "frost_circuit"
            or str(data.get("name") or "").lower() == "frost circuit"
        )

    def _load_state() -> dict:
        _ensure_dirs()
        try:
            if STATE_PATH.exists():
                data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {"schema": FROST_CIRCUIT_SCHEMA, "kind": "holoverse_frost_circuit_state", "best_time": None, "wins": 0, "races_completed": 0, "last_results": [], "score_total": 0, "best_score": 0, "last_score": 0, "points_this_run": 0, "loops_cleared": 0, "obstacle_hits": 0, "crystals_collected": 0, "clean_waypoint_streak": 0, "rank_bonus_count": 0}

    def load_frost_circuit_state(self):
        data = _load_state()
        try:
            best = data.get("best_time")
            self.frost_circuit_best_time = None if best in (None, "") else float(best)
        except Exception:
            self.frost_circuit_best_time = None
        try:
            self.frost_circuit_wins = int(data.get("wins") or 0)
        except Exception:
            self.frost_circuit_wins = 0
        try:
            self.frost_circuit_races_completed = int(data.get("races_completed") or 0)
        except Exception:
            self.frost_circuit_races_completed = 0
        self.frost_circuit_last_results = list(data.get("last_results") or [])[:12]
        try:
            self.frost_circuit_total_score = int(data.get("score_total") or data.get("total_score") or 0)
        except Exception:
            self.frost_circuit_total_score = 0
        try:
            self.frost_circuit_best_score = int(data.get("best_score") or 0)
        except Exception:
            self.frost_circuit_best_score = 0
        try:
            self.frost_circuit_loops_cleared = int(data.get("loops_cleared") or 0)
        except Exception:
            self.frost_circuit_loops_cleared = 0
        try:
            self.frost_circuit_obstacle_hits = int(data.get("obstacle_hits") or 0)
        except Exception:
            self.frost_circuit_obstacle_hits = 0
        try:
            self.frost_circuit_crystals_collected = int(data.get("crystals_collected") or 0)
        except Exception:
            self.frost_circuit_crystals_collected = 0
        try:
            self.frost_circuit_rank_bonus_count = int(data.get("rank_bonus_count") or 0)
        except Exception:
            self.frost_circuit_rank_bonus_count = 0
        return data

    def _mirror_progress(self):
        payload = {
            "schema": FROST_CIRCUIT_SCHEMA,
            "best_time": getattr(self, "frost_circuit_best_time", None),
            "wins": int(getattr(self, "frost_circuit_wins", 0) or 0),
            "races_completed": int(getattr(self, "frost_circuit_races_completed", 0) or 0),
            "last_results": list(getattr(self, "frost_circuit_last_results", []) or [])[:8],
            "score_total": int(getattr(self, "frost_circuit_total_score", 0) or 0),
            "best_score": int(getattr(self, "frost_circuit_best_score", 0) or 0),
            "last_score": int(getattr(self, "frost_circuit_score", 0) or 0),
            "points_this_run": int(getattr(self, "frost_circuit_points_this_run", 0) or 0),
            "loops_cleared": int(getattr(self, "frost_circuit_loops_cleared", 0) or 0),
            "obstacle_hits": int(getattr(self, "frost_circuit_obstacle_hits", 0) or 0),
            "crystals_collected": int(getattr(self, "frost_circuit_crystals_collected", 0) or 0),
            "clean_waypoint_streak": int(getattr(self, "frost_circuit_clean_waypoint_streak", 0) or 0),
            "rank_bonus_count": int(getattr(self, "frost_circuit_rank_bonus_count", 0) or 0),
            "ai_avoidance_events": int(getattr(self, "frost_circuit_ai_avoidance_events", 0) or 0),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "state_path": str(STATE_PATH),
        }
        for path in (SHARED_PROGRESS_PATH,):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                data = {}
                if path.exists():
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        data = raw
                regions = data.setdefault("regions", {})
                ice = regions.setdefault("ice", {})
                ice["frost_circuit"] = payload
                data.setdefault("dimension_progress", {})["frost_circuit"] = payload
                score_total = int(getattr(self, "frost_circuit_total_score", 0) or 0)
                data["holoverse_score"] = max(int(data.get("holoverse_score") or 0), score_total)
                data["updated_at"] = datetime.now().isoformat(timespec="seconds")
                safe_write_json(path, data)
            except Exception as exc:
                print(f"frost_circuit_progress_mirror_error:{path}:{exc}")

    def save_frost_circuit_state(self, reason="manual"):
        _ensure_dirs()
        payload = {
            "schema": FROST_CIRCUIT_SCHEMA,
            "kind": "holoverse_frost_circuit_state",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "reason": str(reason),
            "save_path": str(STATE_PATH),
            "best_time": getattr(self, "frost_circuit_best_time", None),
            "wins": int(getattr(self, "frost_circuit_wins", 0) or 0),
            "races_completed": int(getattr(self, "frost_circuit_races_completed", 0) or 0),
            "last_results": list(getattr(self, "frost_circuit_last_results", []) or [])[:12],
            "score_total": int(getattr(self, "frost_circuit_total_score", 0) or 0),
            "best_score": int(getattr(self, "frost_circuit_best_score", 0) or 0),
            "last_score": int(getattr(self, "frost_circuit_score", 0) or 0),
            "points_this_run": int(getattr(self, "frost_circuit_points_this_run", 0) or 0),
            "loops_cleared": int(getattr(self, "frost_circuit_loops_cleared", 0) or 0),
            "obstacle_hits": int(getattr(self, "frost_circuit_obstacle_hits", 0) or 0),
            "crystals_collected": int(getattr(self, "frost_circuit_crystals_collected", 0) or 0),
            "clean_waypoint_streak": int(getattr(self, "frost_circuit_clean_waypoint_streak", 0) or 0),
            "rank_bonus_count": int(getattr(self, "frost_circuit_rank_bonus_count", 0) or 0),
            "ai_avoidance_events": int(getattr(self, "frost_circuit_ai_avoidance_events", 0) or 0),
            "track": {
                "region": "ICE",
                "r0": ICE_R0,
                "r1": ICE_R1,
                "radius": ICE_TRACK_RADIUS,
                "waypoints": ICE_TRACK_WAYPOINTS,
                "laps": ICE_REQUIRED_LAPS,
            },
        }
        try:
            safe_write_json(STATE_PATH, payload)
            self.frost_circuit_last_save_at = time.time()
            _mirror_progress(self)
        except Exception as exc:
            print(f"frost_circuit_save_error:{exc}")
        return payload

    def _generate_waypoints(self):
        # Shared authored centerline: compact local circuit near Mirror rather
        # than the old 20km+ circle around the entire Ice ring.
        points = []
        for x, y in sampled_world_centerline(ICE_TRACK_WAYPOINTS):
            floor = _floor_z(self, x, y)
            points.append(Vec3(float(x), float(y), floor + 0.62))
        self.frost_circuit_waypoints = points
        self.frost_circuit_track_length = float(frost_track_length(ICE_TRACK_WAYPOINTS))
        return points

    def _frost_runtime_parent(self):
        """Visible parent for Frost Circuit race geometry.

        The default HoloVerse shell can hide world_root while normal numbered
        regions are active.  Frost Circuit must draw into the same visible route
        as the Ice region itself, so race rings and hovercrafts live under render
        instead of the hidden artifact-world root.
        """
        try:
            return self.render
        except Exception:
            return self.world_root

    def _ensure_root(self):
        parent = _frost_runtime_parent(self)
        root = getattr(self, "frost_circuit_root", None)
        recreate = root is None or root.isEmpty()
        if not recreate:
            try:
                recreate = root.getParent() != parent
            except Exception:
                recreate = False
        if recreate:
            try:
                if root is not None and not root.isEmpty():
                    root.removeNode()
            except Exception:
                pass
            self.frost_circuit_root = parent.attachNewNode("frost-circuit-runtime")
            self.frost_circuit_root.setTransparency(TransparencyAttrib.MAlpha)
            try:
                self.frost_circuit_root.setPythonTag("frost_circuit_visible_parent", "render")
            except Exception:
                pass
        return self.frost_circuit_root

    def _destroy_visuals(self):
        for attr in ("frost_circuit_root", "frost_circuit_track_root", "frost_circuit_ui_root"):
            try:
                node = getattr(self, attr, None)
                if node is not None and not node.isEmpty():
                    node.removeNode()
            except Exception:
                pass
            setattr(self, attr, None)
        self.frost_circuit_ui_panel = None
        self.frost_circuit_ui_title = None
        self.frost_circuit_ui_status = None
        self.frost_circuit_ui_help = None

    def _line_node(parent, name: str, color, pts, closed=False, thickness=1.0):
        segs = LineSegs(name)
        segs.setThickness(float(thickness))
        segs.setColor(*color)
        if pts:
            segs.moveTo(pts[0])
            for p in pts[1:]:
                segs.drawTo(p)
            if closed and len(pts) > 2:
                segs.drawTo(pts[0])
        np = parent.attachNewNode(segs.create())
        try:
            np.setAntialias(AntialiasAttrib.MLine)
            np.setTransparency(TransparencyAttrib.MAlpha)
        except Exception:
            pass
        return np

    def _draw_waypoint_ring(parent, center: Vec3, radius: float, color, name: str, height=0.0):
        pts = []
        for i in range(25):
            a = (math.pi * 2.0) * (i / 24.0)
            pts.append(Vec3(center.x + math.cos(a) * radius, center.y + math.sin(a) * radius, center.z + height))
        return _line_node(parent, name, color, pts, closed=True, thickness=1.28)

    def _add_runtime_box(self, parent, center: Vec3, size: Vec3, color, thickness=0.38, name="frost-box"):
        holder = parent.attachNewNode(str(name))
        try:
            if hasattr(self, "add_box"):
                self.add_box(holder, Vec3(center), Vec3(size), color, float(thickness))
            else:
                raise RuntimeError("host_add_box_unavailable")
        except Exception:
            segs = LineSegs(str(name) + "-fallback")
            segs.setThickness(max(1.0, float(getattr(self.cfg, "line_thickness", 1.6)) * float(thickness)))
            segs.setColor(*color)
            hx, hy, hz = size.x * 0.5, size.y * 0.5, size.z * 0.5
            corners = [
                Vec3(center.x-hx, center.y-hy, center.z-hz), Vec3(center.x+hx, center.y-hy, center.z-hz),
                Vec3(center.x+hx, center.y+hy, center.z-hz), Vec3(center.x-hx, center.y+hy, center.z-hz),
                Vec3(center.x-hx, center.y-hy, center.z+hz), Vec3(center.x+hx, center.y-hy, center.z+hz),
                Vec3(center.x+hx, center.y+hy, center.z+hz), Vec3(center.x-hx, center.y+hy, center.z+hz),
            ]
            for a, b in ((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)):
                segs.moveTo(corners[a]); segs.drawTo(corners[b])
            fallback = holder.attachNewNode(segs.create())
            try:
                fallback.setAntialias(AntialiasAttrib.MLine)
                fallback.setTransparency(TransparencyAttrib.MAlpha)
            except Exception:
                pass
        return holder

    def _add_frost_score(self, amount: int, reason="race"):
        amount = max(0, int(amount or 0))
        if amount <= 0:
            return 0
        self.frost_circuit_score = int(getattr(self, "frost_circuit_score", 0) or 0) + amount
        self.frost_circuit_points_this_run = int(getattr(self, "frost_circuit_points_this_run", 0) or 0) + amount
        self.frost_circuit_total_score = int(getattr(self, "frost_circuit_total_score", 0) or 0) + amount
        self.frost_circuit_best_score = max(int(getattr(self, "frost_circuit_best_score", 0) or 0), int(getattr(self, "frost_circuit_score", 0) or 0))
        self.frost_circuit_last_score_reason = str(reason)
        return amount

    def _course_axes(center: Vec3):
        _dist, _qx, _qy, tx, ty = nearest_centerline_info(float(center.x), float(center.y), sample_count=ICE_TRACK_WAYPOINTS)
        tangent = Vec3(float(tx), float(ty), 0.0)
        normal = Vec3(-float(ty), float(tx), 0.0)
        if tangent.lengthSquared() <= 0.0001:
            tangent = Vec3(0.0, 1.0, 0.0)
            normal = Vec3(1.0, 0.0, 0.0)
        return normal, tangent

    def _build_loop_gate(app, parent, spec: dict):
        center = Vec3(spec.get("center", Vec3()))
        radial = Vec3(spec.get("radial", Vec3(1, 0, 0)))
        radius = float(spec.get("radius", 34.0))
        color = tuple(spec.get("color") or (0.78, 0.50, 1.0, 0.82))
        accent = tuple(spec.get("accent") or (0.18, 1.0, 1.0, 0.72))
        pts_outer, pts_inner = [], []
        for i in range(73):
            a = math.tau * i / 72.0
            pts_outer.append(center + radial * (math.cos(a) * radius) + Vec3(0, 0, math.sin(a) * radius))
            pts_inner.append(center + radial * (math.cos(a) * radius * 0.70) + Vec3(0, 0, math.sin(a) * radius * 0.70))
        _line_node(parent, f"frost-loop-outer-{spec.get('id','x')}", color, pts_outer, closed=True, thickness=2.3)
        _line_node(parent, f"frost-loop-inner-{spec.get('id','x')}", accent, pts_inner, closed=True, thickness=1.4)
        foot_z = center.z - radius
        for side in (-1, 1):
            base = center + radial * side * (radius * 0.88)
            _add_runtime_box(app, parent, Vec3(base.x, base.y, foot_z + radius * 0.30), Vec3(5.2, 5.2, radius * 0.60), accent, 0.32, f"frost-loop-post-{spec.get('id','x')}-{side}")

    def _build_score_crystal(app, parent, spec: dict):
        center = Vec3(spec.get("center", Vec3()))
        radius = float(spec.get("radius", 16.0))
        color = tuple(spec.get("color") or (0.52, 1.0, 1.0, 0.78))
        hot = tuple(spec.get("hot") or (1.0, 1.0, 1.0, 0.88))
        holder = parent.attachNewNode(f"frost-score-crystal-{spec.get('id','x')}")
        holder.setTransparency(TransparencyAttrib.MAlpha)
        spec["node"] = holder
        # Floating diamond body.  It sits well above the surface so it reads as a pickup,
        # not another ground obstacle.
        top = center + Vec3(0, 0, radius * 0.62)
        bottom = center - Vec3(0, 0, radius * 0.62)
        left = center + Vec3(-radius * 0.55, 0, 0)
        right = center + Vec3(radius * 0.55, 0, 0)
        front = center + Vec3(0, radius * 0.55, 0)
        back = center + Vec3(0, -radius * 0.55, 0)
        diamond = LineSegs(f"frost-score-crystal-wire-{spec.get('id','x')}")
        diamond.setThickness(2.1)
        diamond.setColor(*hot)
        for a, b in ((top,left),(top,right),(top,front),(top,back),(bottom,left),(bottom,right),(bottom,front),(bottom,back),(left,front),(front,right),(right,back),(back,left)):
            diamond.moveTo(a); diamond.drawTo(b)
        node = holder.attachNewNode(diamond.create())
        try:
            node.setAntialias(AntialiasAttrib.MLine)
            node.setTransparency(TransparencyAttrib.MAlpha)
        except Exception:
            pass
        _draw_waypoint_ring(holder, center, radius * 0.92, color, f"frost-score-crystal-ring-{spec.get('id','x')}", height=-radius * 0.54)
        return holder

    def _generate_score_crystals(self):
        wps = list(getattr(self, "frost_circuit_waypoints", []) or [])
        if not wps:
            self.frost_circuit_score_crystals = []
            return []
        rng = random.Random(884021)
        crystals = []
        slots = []
        step = max(1, len(wps) // max(1, ICE_SCORE_CRYSTAL_COUNT))
        for i in range(ICE_SCORE_CRYSTAL_COUNT):
            slots.append((1 + i * step + (i % 3)) % len(wps))
        for idx, slot in enumerate(slots[:ICE_SCORE_CRYSTAL_COUNT]):
            wp = Vec3(wps[slot])
            radial, tangent = _course_axes(wp)
            offset = rng.uniform(-ICE_TRACK_HALF_WIDTH * 0.56, ICE_TRACK_HALF_WIDTH * 0.56)
            drift = rng.uniform(-12.0, 14.0)
            center_xy = wp + radial * offset + tangent * drift
            floor = _floor_z(self, center_xy.x, center_xy.y)
            color = (0.36 + rng.random() * 0.22, 0.86 + rng.random() * 0.12, 1.0, 0.76)
            hot = (0.92, 1.0, 1.0, 0.92) if idx % 3 else (1.0, 0.76, 1.0, 0.90)
            crystals.append({
                "id": idx,
                "center": Vec3(center_xy.x, center_xy.y, floor + ICE_HOVER_BASE_CLEARANCE + 4.8),
                "radius": rng.uniform(12.0, 17.0),
                "value": ICE_CRYSTAL_SCORE + (idx % 4) * 15,
                "active": True,
                "color": color,
                "hot": hot,
            })
        self.frost_circuit_score_crystals = crystals
        return crystals

    def _build_score_crystal_visuals(self, parent):
        crystal_root = parent.attachNewNode("frost-circuit-score-crystals")
        crystal_root.setTransparency(TransparencyAttrib.MAlpha)
        for spec in _generate_score_crystals(self):
            _build_score_crystal(self, crystal_root, spec)
        return crystal_root

    def _update_score_crystals(self, racer):
        if not bool(racer.get("is_player", False)):
            return
        pos = Vec3(racer.get("pos", Vec3()))
        for spec in list(getattr(self, "frost_circuit_score_crystals", []) or []):
            if not bool(spec.get("active", True)):
                continue
            center = Vec3(spec.get("center", Vec3()))
            dxy = math.sqrt((pos.x - center.x) ** 2 + (pos.y - center.y) ** 2)
            dz = abs(pos.z - center.z)
            radius = float(spec.get("radius", 15.0)) + 13.0
            if dxy <= radius and dz <= max(18.0, radius * 1.45):
                spec["active"] = False
                node = spec.get("node")
                try:
                    if node is not None and not node.isEmpty():
                        node.hide()
                except Exception:
                    pass
                self.frost_circuit_crystals_collected = int(getattr(self, "frost_circuit_crystals_collected", 0) or 0) + 1
                gained = _add_frost_score(self, int(spec.get("value", ICE_CRYSTAL_SCORE)), reason="ice_crystal")
                try:
                    self.center_hint["text"] = f"FROST CIRCUIT // ICE CHARGE +{gained} SAVED TO RUN"
                except Exception:
                    pass

    def _build_cube_formation(app, parent, spec: dict):
        center = Vec3(spec.get("center", Vec3()))
        rng = random.Random(int(spec.get("seed", 1)))
        base = tuple(spec.get("color") or (0.56, 0.92, 1.0, 0.42))
        accent = tuple(spec.get("accent") or (0.76, 0.50, 1.0, 0.48))
        hot = tuple(spec.get("hot") or (0.12, 1.0, 1.0, 0.52))
        height = float(spec.get("height", 42.0))
        width = float(spec.get("width", 26.0))
        _add_runtime_box(app, parent, center + Vec3(0, 0, height * 0.22), Vec3(width, width, height * 0.44), base, 0.44, f"ice-obstacle-base-{spec.get('id','x')}")
        _add_runtime_box(app, parent, center + Vec3(width * 0.18, -width * 0.16, height * 0.64), Vec3(width * 0.74, width * 0.74, height * 0.42), accent, 0.38, f"ice-obstacle-cap-{spec.get('id','x')}")
        if rng.random() < 0.72:
            _add_runtime_box(app, parent, center + Vec3(-width * 0.46, width * 0.24, height * 0.40), Vec3(width * 0.38, width * 0.38, height * 0.36), hot, 0.30, f"ice-obstacle-side-{spec.get('id','x')}")
        _line_node(parent, f"ice-obstacle-neon-brace-{spec.get('id','x')}", hot, [center + Vec3(-width*0.62, -width*0.62, height*0.10), center + Vec3(width*0.58, width*0.38, height*1.02)], closed=False, thickness=1.25)

    def _generate_course_features(self):
        wps = list(getattr(self, "frost_circuit_waypoints", []) or [])
        if not wps:
            self.frost_circuit_obstacles = []
            self.frost_circuit_loop_gates = []
            return [], []
        start_ang = _angle_from_xy(wps[0].x, wps[0].y)
        rng = random.Random(513507 + int(start_ang * 1000.0))
        obstacles = []
        colors = [
            ((0.52, 0.96, 1.0, 0.42), (0.76, 0.50, 1.0, 0.48), (0.16, 1.0, 1.0, 0.56)),
            ((0.70, 0.84, 1.0, 0.38), (1.0, 0.42, 0.92, 0.44), (0.96, 1.0, 1.0, 0.52)),
            ((0.48, 0.78, 1.0, 0.40), (0.90, 0.64, 1.0, 0.44), (0.30, 1.0, 0.82, 0.54)),
        ]
        seeded_slots = [2, 4, 6, 8, 11, 13, 15, 18, 20, 23, 25, 27]
        while len(seeded_slots) < ICE_OBSTACLE_COUNT:
            v = rng.randrange(1, max(2, len(wps)))
            if v not in seeded_slots:
                seeded_slots.append(v)
        for idx, slot in enumerate(seeded_slots[:ICE_OBSTACLE_COUNT]):
            wp = Vec3(wps[slot % len(wps)])
            radial, tangent = _course_axes(wp)
            offset = rng.choice([-1.0, 1.0]) * rng.uniform(102.0, 148.0)
            if idx < 4:
                offset = [-112.0, 126.0, -144.0, 106.0][idx]
            center_xy = wp + radial * offset + tangent * rng.uniform(-38.0, 42.0)
            floor = _floor_z(self, center_xy.x, center_xy.y)
            width = rng.uniform(22.0, 42.0)
            height = rng.uniform(28.0, 68.0)
            color, accent, hot = colors[idx % len(colors)]
            obstacles.append({"id": idx, "center": Vec3(center_xy.x, center_xy.y, floor), "radius": width * 0.90, "width": width, "height": height, "seed": rng.randint(1000, 999999), "color": color, "accent": accent, "hot": hot})
        gates = []
        for idx, slot in enumerate([3, 8, 14, 19, 24][:ICE_LOOP_GATE_COUNT]):
            wp = Vec3(wps[slot % len(wps)])
            radial, tangent = _course_axes(wp)
            floor = _floor_z(self, wp.x, wp.y)
            gates.append({"id": idx, "center": Vec3(wp.x, wp.y, floor + 24.0), "normal": tangent, "radial": radial, "radius": 38.0, "scored": False, "color": (0.78, 0.50, 1.0, 0.84), "accent": (0.12, 1.0, 1.0, 0.76)})
        self.frost_circuit_obstacles = obstacles
        self.frost_circuit_loop_gates = gates
        return obstacles, gates

    def _build_course_feature_visuals(self):
        root = getattr(self, "frost_circuit_track_root", None) or _ensure_root(self)
        obstacles, gates = _generate_course_features(self)
        feature_root = root.attachNewNode("frost-circuit-obstacles-and-loops")
        feature_root.setTransparency(TransparencyAttrib.MAlpha)
        for spec in obstacles:
            _build_cube_formation(self, feature_root, spec)
        for spec in gates:
            _build_loop_gate(self, feature_root, spec)
        _build_score_crystal_visuals(self, feature_root)
        try:
            feature_root.setPythonTag("frost_obstacle_count", len(obstacles))
            feature_root.setPythonTag("frost_loop_gate_count", len(gates))
        except Exception:
            pass
        return feature_root

    def _obstacle_avoidance(self, pos: Vec3, yaw: float, lookahead: float = 190.0):
        forward = _heading_vec(yaw)
        right = Vec3(math.cos(math.radians(yaw)), -math.sin(math.radians(yaw)), 0.0)
        steer = 0.0
        slow = 1.0
        threat_count = 0
        for spec in list(getattr(self, "frost_circuit_obstacles", []) or []):
            center = Vec3(spec.get("center", Vec3()))
            rel = center - pos
            rel.z = 0.0
            along = rel.dot(forward)
            if along < -18.0 or along > lookahead:
                continue
            lateral = rel.dot(right)
            clearance = float(spec.get("radius", 28.0)) + 48.0
            if abs(lateral) < clearance:
                away = -1.0 if lateral >= 0.0 else 1.0
                strength = (clearance - abs(lateral)) / max(1.0, clearance)
                steer += away * strength
                slow = min(slow, 0.66 - min(0.28, strength * 0.30))
                threat_count += 1
        return max(-1.0, min(1.0, steer)), max(0.34, min(1.0, slow)), threat_count

    def _keep_racer_on_track(self, racer, dt=0.016):
        pos = Vec3(racer.get("pos", Vec3()))
        dist, qx, qy, _tx, _ty = nearest_centerline_info(pos.x, pos.y, sample_count=ICE_TRACK_WAYPOINTS)
        racer["track_distance"] = float(dist)
        racer["offtrack"] = bool(dist > ICE_TRACK_OFFROAD_WIDTH)
        # Off-course ice is intentionally driveable, but much slower. This is a
        # penalty rather than an invisible wall. Farther excursions are softly
        # returned to the course safety envelope so players cannot lose the race.
        if dist > ICE_TRACK_OFFROAD_WIDTH:
            damp = math.exp(-max(0.0, float(dt)) * 2.6)
            vel = racer.get("velocity")
            if isinstance(vel, Vec3):
                racer["velocity"] = Vec3(vel) * damp
            racer["speed"] = float(racer.get("speed", 0.0)) * damp
        if dist > ICE_TRACK_RESET_WIDTH:
            dx = pos.x - float(qx); dy = pos.y - float(qy)
            length = math.hypot(dx, dy) or 1.0
            keep = ICE_TRACK_RESET_WIDTH * 0.72
            pos.x = float(qx) + dx / length * keep
            pos.y = float(qy) + dy / length * keep
            racer["pos"] = pos
            vel = racer.get("velocity")
            if isinstance(vel, Vec3):
                racer["velocity"] = Vec3(vel) * 0.42
            racer["speed"] = float(racer.get("speed", 0.0)) * 0.42

    def _apply_obstacle_collision(self, racer, is_player=False):
        pos = Vec3(racer.get("pos", Vec3()))
        for spec in list(getattr(self, "frost_circuit_obstacles", []) or []):
            center = Vec3(spec.get("center", Vec3()))
            dx = pos.x - center.x
            dy = pos.y - center.y
            dist = math.sqrt(dx * dx + dy * dy)
            limit = float(spec.get("radius", 28.0)) + (12.0 if is_player else 10.0)
            if dist <= 0.001 or dist >= limit:
                continue
            push = Vec3(dx / dist, dy / dist, 0.0)
            pos.x = center.x + push.x * limit
            pos.y = center.y + push.y * limit
            racer["pos"] = pos
            racer["speed"] = -abs(float(racer.get("speed", 0.0))) * (0.18 if is_player else 0.10)
            if isinstance(racer.get("velocity"), Vec3):
                racer["velocity"] = Vec3(push) * (-abs(float(racer.get("speed", 0.0))) * 0.32)
            if is_player:
                self.frost_circuit_obstacle_hits = int(getattr(self, "frost_circuit_obstacle_hits", 0) or 0) + 1
                self.frost_circuit_clean_waypoint_streak = 0
                try:
                    self.center_hint["text"] = "FROST CIRCUIT // OBSTACLE HIT - DRIVE AROUND THE ICE FORMATIONS"
                except Exception:
                    pass
            return True
        return False

    def _update_loop_gate_score(self, racer):
        if not bool(racer.get("is_player", False)):
            return
        pos = Vec3(racer.get("pos", Vec3()))
        for spec in list(getattr(self, "frost_circuit_loop_gates", []) or []):
            if bool(spec.get("scored", False)):
                continue
            center = Vec3(spec.get("center", Vec3()))
            normal = Vec3(spec.get("normal", Vec3(0, 1, 0)))
            radial = Vec3(spec.get("radial", Vec3(1, 0, 0)))
            rel = pos - center
            plane_dist = abs(rel.dot(normal))
            lateral = rel.dot(radial)
            vertical = rel.z
            radius = float(spec.get("radius", 38.0))
            if plane_dist < 28.0 and (lateral * lateral + vertical * vertical) <= (radius * 0.82) ** 2:
                spec["scored"] = True
                self.frost_circuit_loops_cleared = int(getattr(self, "frost_circuit_loops_cleared", 0) or 0) + 1
                gained = _add_frost_score(self, ICE_LOOP_SCORE, reason="loop_gate")
                try:
                    self.center_hint["text"] = f"FROST CIRCUIT // LOOP CLEAN +{gained}"
                except Exception:
                    pass

    def _build_track_ribbon(self, parent, wps):
        """Build an actual readable road ribbon with shoulders and edge lines."""
        if len(wps) < 4:
            return None
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("frost-track-ribbon-vdata", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")
        offsets = (-ICE_TRACK_HALF_WIDTH - 9.0, -ICE_TRACK_HALF_WIDTH, ICE_TRACK_HALF_WIDTH, ICE_TRACK_HALF_WIDTH + 9.0)
        colors = (
            (0.015, 0.055, 0.105, 0.96),
            (0.035, 0.19, 0.31, 0.98),
            (0.035, 0.19, 0.31, 0.98),
            (0.015, 0.055, 0.105, 0.96),
        )
        stations = []
        for i, wp in enumerate(wps):
            prev = Vec3(wps[(i - 1) % len(wps)])
            nxt = Vec3(wps[(i + 1) % len(wps)])
            tangent = nxt - prev
            tangent.z = 0.0
            if tangent.lengthSquared() <= 1e-6:
                tangent = Vec3(0, 1, 0)
            else:
                tangent.normalize()
            normal = Vec3(-tangent.y, tangent.x, 0.0)
            row = []
            for j, offset in enumerate(offsets):
                x = float(wp.x + normal.x * offset)
                y = float(wp.y + normal.y * offset)
                z = _floor_z(self, x, y) + (0.31 if j in (1, 2) else 0.20)
                vw.addData3(x, y, z)
                c = colors[j]
                cw.addData4(*c)
                row.append(i * len(offsets) + j)
            stations.append((Vec3(wp), normal, tangent))
        prim = GeomTriangles(Geom.UHStatic)
        cols = len(offsets)
        for i in range(len(wps)):
            ni = (i + 1) % len(wps)
            for j in range(cols - 1):
                a = i * cols + j
                b = i * cols + j + 1
                c = ni * cols + j
                d = ni * cols + j + 1
                prim.addVertices(a, c, b)
                prim.addVertices(b, c, d)
        prim.closePrimitive()
        geom = Geom(vdata)
        geom.addPrimitive(prim)
        node = GeomNode("frost-track-ribbon")
        node.addGeom(geom)
        np = parent.attachNewNode(node)
        try:
            np.setTransparency(TransparencyAttrib.MAlpha)
            np.setTwoSided(True)
        except Exception:
            pass

        # Edge rails define the real drivable width.  A broken center stripe gives
        # speed reference without filling the screen with waypoint circles.
        left_pts, right_pts = [], []
        for wp, normal, _tangent in stations:
            for pts, sign in ((left_pts, 1.0), (right_pts, -1.0)):
                x = float(wp.x + normal.x * ICE_TRACK_HALF_WIDTH * sign)
                y = float(wp.y + normal.y * ICE_TRACK_HALF_WIDTH * sign)
                pts.append(Vec3(x, y, _floor_z(self, x, y) + 0.62))
        _line_node(parent, "frost-track-left-edge", (0.72, 0.98, 1.0, 0.86), left_pts, closed=True, thickness=2.0)
        _line_node(parent, "frost-track-right-edge", (0.72, 0.98, 1.0, 0.86), right_pts, closed=True, thickness=2.0)
        for i in range(0, len(wps), 2):
            a = Vec3(wps[i]); b = Vec3(wps[(i + 1) % len(wps)])
            a.z = _floor_z(self, a.x, a.y) + 0.70
            b.z = _floor_z(self, b.x, b.y) + 0.70
            _line_node(parent, f"frost-track-center-dash-{i}", (0.26, 0.82, 1.0, 0.55), [a, b], closed=False, thickness=1.2)

        # Sparse split markers punctuate the course.  These replace the old ring
        # forest and make corner sequence/race direction easy to memorize.
        for idx in range(0, len(wps), 8):
            wp, normal, tangent = stations[idx]
            color = (1.0, 1.0, 1.0, 0.92) if idx == 0 else (0.34, 0.95, 1.0, 0.68)
            z = _floor_z(self, wp.x, wp.y)
            left = Vec3(wp.x + normal.x * (ICE_TRACK_HALF_WIDTH + 3.5), wp.y + normal.y * (ICE_TRACK_HALF_WIDTH + 3.5), z)
            right = Vec3(wp.x - normal.x * (ICE_TRACK_HALF_WIDTH + 3.5), wp.y - normal.y * (ICE_TRACK_HALF_WIDTH + 3.5), z)
            _line_node(parent, f"frost-split-{idx}", color, [left + Vec3(0,0,0.5), left + Vec3(0,0,8.0), right + Vec3(0,0,8.0), right + Vec3(0,0,0.5)], closed=False, thickness=1.55)
        for idx in range(4, len(wps), 8):
            wp, normal, _tangent = stations[idx]
            z = _floor_z(self, wp.x, wp.y)
            for side in (-1.0, 1.0):
                x = wp.x + normal.x * (ICE_TRACK_HALF_WIDTH + 5.0) * side
                y = wp.y + normal.y * (ICE_TRACK_HALF_WIDTH + 5.0) * side
                base = Vec3(x, y, z + 0.4)
                _line_node(parent, f"frost-edge-beacon-{idx}-{int(side)}", (0.18, 0.92, 1.0, 0.82), [base, base + Vec3(0,0,5.5)], closed=False, thickness=1.65)
        return np

    def _build_track_visuals(self):
        root = _ensure_root(self)
        try:
            if getattr(self, "frost_circuit_track_root", None) is not None and not self.frost_circuit_track_root.isEmpty():
                self.frost_circuit_track_root.removeNode()
        except Exception:
            pass
        track = root.attachNewNode("frost-circuit-track")
        track.setTransparency(TransparencyAttrib.MAlpha)
        self.frost_circuit_track_root = track
        wps = list(getattr(self, "frost_circuit_waypoints", []) or [])
        if not wps:
            return
        _build_track_ribbon(self, track, wps)
        # The start/finish is a single strong landmark instead of one giant ring.
        start = Vec3(wps[0])
        _normal, tangent = _course_axes(start)
        normal = Vec3(-tangent.y, tangent.x, 0.0)
        floor = _floor_z(self, start.x, start.y)
        left = start + normal * (ICE_TRACK_HALF_WIDTH + 4.0); left.z = floor
        right = start - normal * (ICE_TRACK_HALF_WIDTH + 4.0); right.z = floor
        gate_pts = [left, left + Vec3(0,0,15.0), right + Vec3(0,0,15.0), right]
        _line_node(track, "frost-finish-gate", (1.0, 1.0, 1.0, 0.94), gate_pts, closed=False, thickness=2.4)
        _build_course_feature_visuals(self)

    def _build_hovercraft_node(self, parent, racer):
        rng = random.Random(int(racer.get("seed", 1)))
        name = str(racer.get("name") or "Racer")
        color = tuple(racer.get("color") or _hovercraft_color(name))
        accent = (min(1.0, color[0] + 0.20), min(1.0, color[1] + 0.20), min(1.0, color[2] + 0.20), 0.88)
        hot = (0.16, 1.0, 1.0, 0.82) if name == "Player" else (1.0, 0.36 + rng.random() * 0.34, 1.0, 0.74)
        width = 5.2 + rng.random() * 2.2
        length = 11.0 + rng.random() * 3.5
        root = parent.attachNewNode(f"frost-hovercraft-3d-{name}")
        root.setTransparency(TransparencyAttrib.MAlpha)
        _add_runtime_box(self, root, Vec3(0.0, 0.0, 0.10), Vec3(width * 1.40, length, 1.25), color, 0.52, f"craft-hull-{name}")
        _add_runtime_box(self, root, Vec3(0.0, length * 0.18, 1.05), Vec3(width * 0.72, length * 0.36, 1.05), accent, 0.42, f"craft-cockpit-{name}")
        _add_runtime_box(self, root, Vec3(0.0, -length * 0.46, 0.62), Vec3(width * 1.08, length * 0.22, 0.80), hot, 0.34, f"craft-engine-{name}")
        for sx in (-1, 1):
            _add_runtime_box(self, root, Vec3(sx * width * 0.88, -length * 0.06, -0.48), Vec3(width * 0.28, length * 0.86, 0.36), accent, 0.30, f"craft-hover-rail-{name}-{sx}")
            _add_runtime_box(self, root, Vec3(sx * width * 0.76, length * 0.38, 0.52), Vec3(width * 0.22, length * 0.34, 0.88), color, 0.30, f"craft-front-fin-{name}-{sx}")
            _add_runtime_box(self, root, Vec3(sx * width * 0.62, -length * 0.56, 1.05), Vec3(width * 0.24, length * 0.20, 1.25), hot, 0.28, f"craft-tail-fin-{name}-{sx}")
        segs = LineSegs(f"craft-wire-{name}")
        segs.setThickness(max(1.0, float(getattr(self.cfg, "line_thickness", 1.6)) * 0.95))
        segs.setColor(*hot)
        nose = Vec3(0, length * 0.64, 0.74)
        left = Vec3(-width * 1.00, length * 0.04, 0.08)
        right = Vec3(width * 1.00, length * 0.04, 0.08)
        tail = Vec3(0, -length * 0.70, 0.22)
        for a, b in ((nose,left),(left,tail),(tail,right),(right,nose),(left,right),(nose,tail)):
            segs.moveTo(a); segs.drawTo(b)
        glow = root.attachNewNode(segs.create())
        try:
            glow.setAntialias(AntialiasAttrib.MLine)
            glow.setTransparency(TransparencyAttrib.MAlpha)
        except Exception:
            pass
        label = LineSegs(f"craft-crown-{name}")
        label.setThickness(max(1.0, float(getattr(self.cfg, "line_thickness", 1.6)) * 0.65))
        label.setColor(*accent)
        label.moveTo(-width * 0.35, -0.4, 2.0); label.drawTo(0, 1.1, 2.65); label.drawTo(width * 0.35, -0.4, 2.0)
        cn = root.attachNewNode(label.create())
        try:
            cn.setAntialias(AntialiasAttrib.MLine)
            cn.setTransparency(TransparencyAttrib.MAlpha)
        except Exception:
            pass
        hover = LineSegs(f"craft-hover-glow-{name}")
        hover.setThickness(max(1.0, float(getattr(self.cfg, "line_thickness", 1.6)) * 0.72))
        hover.setColor(0.48, 0.96, 1.0, 0.42)
        for i in range(49):
            a = math.tau * i / 48.0
            p = Vec3(math.cos(a) * width * 1.18, math.sin(a) * length * 0.46, -1.18)
            if i == 0:
                hover.moveTo(p)
            else:
                hover.drawTo(p)
        hnp = root.attachNewNode(hover.create())
        try:
            hnp.setAntialias(AntialiasAttrib.MLine)
            hnp.setTransparency(TransparencyAttrib.MAlpha)
        except Exception:
            pass
        racer["node"] = root
        racer["collision_radius"] = max(width * 1.10, length * 0.54)
        return root

    def _update_hovercraft_node(self, racer):
        node = racer.get("node")
        if node is None or node.isEmpty():
            node = _build_hovercraft_node(self, _ensure_root(self), racer)
        pos = Vec3(racer.get("pos", Vec3(0, 0, 0)))
        try:
            node.setPos(pos)
            speed = abs(float(racer.get("speed", 0.0)))
            bank = max(-16.0, min(16.0, float(racer.get("steer_bank", 0.0))))
            pitch = max(-10.0, min(10.0, speed * 0.035))
            node.setHpr(float(racer.get("yaw", 0.0)), pitch, bank)
        except Exception:
            pass

    def _setup_racers(self):
        wps = list(getattr(self, "frost_circuit_waypoints", []) or _generate_waypoints(self))
        start = Vec3(wps[0])
        target = Vec3(wps[1]) if len(wps) > 1 else start + Vec3(0, 100, 0)
        base_yaw = _yaw_to_target(start, target)
        tangent = _heading_vec(base_yaw)
        radial = Vec3(start.x, start.y, 0)
        if radial.lengthSquared() > 0:
            radial.normalize()
        else:
            radial = Vec3(1, 0, 0)
        names = ["Player"] + list(BOT_RACERS)
        racers = []
        for idx, name in enumerate(names):
            lane = (idx - (len(names) - 1) * 0.5) * 9.0
            row = (idx // 4) * -24.0
            pos = start + radial * lane + tangent * row
            floor = _floor_z(self, pos.x, pos.y)
            seed = 2823800 + idx * 7919
            rng = random.Random(seed)
            max_speed = 108.0 if name == "Player" else rng.uniform(78.0, 101.0)
            accel = 66.0 if name == "Player" else rng.uniform(45.0, 58.0)
            handling = 1.0 if name == "Player" else rng.uniform(0.84, 1.08)
            racer = {
                "name": name,
                "is_player": name == "Player",
                "seed": seed,
                "color": _hovercraft_color(name),
                "pos": Vec3(pos.x, pos.y, floor + ICE_HOVER_BASE_CLEARANCE),
                "yaw": base_yaw,
                "speed": 0.0,
                "velocity": Vec3(0, 0, 0),
                "steer_input_smoothed": 0.0,
                "max_speed": max_speed,
                "accel": accel,
                "handling": handling,
                "current_wp": 1,
                "lap": 0,
                "finished": False,
                "finish_time": None,
                "steer_bank": 0.0,
                "last_wp_time": time.time(),
            }
            racers.append(racer)
        self.frost_circuit_racers = racers
        for racer in racers:
            _build_hovercraft_node(self, _ensure_root(self), racer)
        return racers

    def _advance_racer_waypoint(self, racer, now):
        if bool(racer.get("finished", False)):
            return
        wps = list(getattr(self, "frost_circuit_waypoints", []) or [])
        if not wps:
            return
        idx = int(racer.get("current_wp", 0)) % len(wps)
        target = wps[idx]
        dist = _dist2d(Vec3(racer.get("pos", Vec3())), target)
        if dist > ICE_WAYPOINT_CAPTURE_RADIUS:
            return
        is_player = bool(racer.get("is_player", False))
        if is_player:
            speed_bonus = int(max(0.0, abs(float(racer.get("speed", 0.0)))) * 0.10)
            base_gain = _add_frost_score(self, ICE_WAYPOINT_SCORE + speed_bonus, reason="waypoint")
            hit_total = int(getattr(self, "frost_circuit_obstacle_hits", 0) or 0)
            last_hit_total = int(racer.get("last_waypoint_hit_total", hit_total))
            if hit_total == last_hit_total:
                self.frost_circuit_clean_waypoint_streak = int(getattr(self, "frost_circuit_clean_waypoint_streak", 0) or 0) + 1
                if self.frost_circuit_clean_waypoint_streak >= 3:
                    streak_bonus = ICE_CLEAN_STREAK_SCORE + min(260, (self.frost_circuit_clean_waypoint_streak - 3) * 18)
                    _add_frost_score(self, streak_bonus, reason="clean_waypoint_streak")
                    try:
                        self.center_hint["text"] = f"FROST CIRCUIT // CLEAN STREAK x{self.frost_circuit_clean_waypoint_streak} +{streak_bonus}"
                    except Exception:
                        pass
            else:
                self.frost_circuit_clean_waypoint_streak = 0
            racer["last_waypoint_hit_total"] = hit_total
        idx += 1
        if idx >= len(wps):
            idx = 0
            racer["lap"] = int(racer.get("lap", 0)) + 1
            if is_player:
                _add_frost_score(self, 220, reason="lap_checkpoint")
        racer["current_wp"] = idx
        racer["last_wp_time"] = now
        if int(racer.get("lap", 0)) >= ICE_REQUIRED_LAPS and idx == 0:
            racer["finished"] = True
            racer["finish_time"] = max(0.0, now - float(getattr(self, "frost_circuit_started_at", now)))

    def _update_racer_height(self, racer, dt):
        pos = Vec3(racer.get("pos", Vec3()))
        floor = _floor_z(self, pos.x, pos.y)
        speed = abs(float(racer.get("speed", 0.0)))
        bob = math.sin(time.time() * 4.0 + int(racer.get("seed", 0)) * 0.01) * 0.18
        lift = ICE_HOVER_BASE_CLEARANCE + min(ICE_HOVER_SPEED_LIFT, speed * 0.034) + bob
        # Keep the craft visibly above the ice.  The vehicle mesh has rails below
        # its origin, so the origin needs real clearance or the body appears to
        # sink through uneven ice tiles.
        target_z = floor + lift
        pos.z += (target_z - pos.z) * min(1.0, dt * 7.0)
        racer["pos"] = pos

    def _update_player_racer(self, racer, dt):
        """Arcade hovercraft handling with real inertia and speed-aware steering."""
        keys = getattr(self, "keys", {})
        dt = max(0.001, min(0.05, float(dt or 0.016)))
        yaw = float(racer.get("yaw", 0.0))
        forward = _heading_vec(yaw)
        right = Vec3(forward.y, -forward.x, 0.0)
        vel = racer.get("velocity")
        if not isinstance(vel, Vec3):
            vel = forward * float(racer.get("speed", 0.0) or 0.0)
        else:
            vel = Vec3(vel)

        forward_speed = float(vel.dot(forward))
        lateral_speed = float(vel.dot(right))
        throttle = 1.0 if keys.get("w") else 0.0
        reverse = False
        service_brake = False
        if keys.get("s"):
            if forward_speed > 7.0:
                service_brake = True
            else:
                reverse = True
        handbrake = bool(keys.get("space"))
        boost = bool(keys.get("shift")) and throttle > 0.0 and not handbrake

        raw_steer = (1.0 if keys.get("d") else 0.0) - (1.0 if keys.get("a") else 0.0)
        steer = float(racer.get("steer_input_smoothed", 0.0) or 0.0)
        steer_rate = 5.8 if raw_steer else 7.2
        step = steer_rate * dt
        if raw_steer > steer:
            steer = min(raw_steer, steer + step)
        elif raw_steer < steer:
            steer = max(raw_steer, steer - step)
        racer["steer_input_smoothed"] = steer

        speed_abs = vel.length()
        speed_norm = max(0.0, min(1.0, speed_abs / 108.0))
        # Useful steering at low speed, calmer steering at racing speed.
        max_yaw_rate = 102.0 - speed_norm * 42.0
        motion_authority = 0.24 + min(1.0, speed_abs / 28.0) * 0.76
        if handbrake:
            max_yaw_rate *= 1.26
        yaw = (yaw + steer * max_yaw_rate * motion_authority * dt) % 360.0
        forward = _heading_vec(yaw)
        right = Vec3(forward.y, -forward.x, 0.0)

        accel_force = float(racer.get("accel", 64.0) or 64.0)
        if throttle:
            vel += forward * accel_force * (1.36 if boost else 1.0) * dt
        elif reverse:
            vel -= forward * accel_force * 0.62 * dt
        if service_brake:
            vel *= math.exp(-5.4 * dt)
        if handbrake:
            # Strong forward braking with intentionally lower lateral grip gives
            # a controlled hover-drift instead of instantly rotating the craft.
            fwd = vel.dot(forward)
            lat = vel.dot(right)
            fwd *= math.exp(-3.25 * dt)
            lat *= math.exp(-1.55 * dt)
            vel = forward * fwd + right * lat

        # Hovercraft grip: lateral motion is damped, not deleted. Releasing the
        # wheel therefore settles naturally instead of snapping to a new vector.
        fwd = float(vel.dot(forward))
        lat = float(vel.dot(right))
        grip = 2.15 if handbrake else (5.7 if boost else 6.8)
        lat *= math.exp(-grip * dt)
        coast_drag = 0.16 if throttle or reverse else 0.62
        fwd *= math.exp(-coast_drag * dt)
        vel = forward * fwd + right * lat

        max_speed = float(racer.get("max_speed", 108.0)) * (1.22 if boost else 1.0)
        speed_len = vel.length()
        if speed_len > max_speed:
            vel *= max_speed / max(0.001, speed_len)

        if boost and vel.length() > 82.0:
            self.frost_circuit_boost_score_bank = float(getattr(self, "frost_circuit_boost_score_bank", 0.0) or 0.0) + dt
            if self.frost_circuit_boost_score_bank >= 1.0:
                seconds = int(self.frost_circuit_boost_score_bank)
                self.frost_circuit_boost_score_bank -= seconds
                _add_frost_score(self, ICE_BOOST_SCORE_PER_SECOND * seconds, reason="boost_chain")
        if handbrake and abs(steer) > 0.32 and vel.length() > 38.0:
            self.frost_circuit_drift_score_bank = float(getattr(self, "frost_circuit_drift_score_bank", 0.0) or 0.0) + dt
            if self.frost_circuit_drift_score_bank >= 1.0:
                seconds = int(self.frost_circuit_drift_score_bank)
                self.frost_circuit_drift_score_bank -= seconds
                _add_frost_score(self, ICE_DRIFT_SCORE_PER_SECOND * seconds, reason="drift_chain")
        else:
            self.frost_circuit_drift_score_bank = max(0.0, float(getattr(self, "frost_circuit_drift_score_bank", 0.0) or 0.0) - dt * 0.45)

        pos = Vec3(racer.get("pos", Vec3())) + vel * dt
        racer["yaw"] = yaw
        racer["velocity"] = Vec3(vel)
        racer["speed"] = float(vel.dot(forward))
        racer["pos"] = pos
        racer["steer_bank"] = -steer * min(13.0, vel.length() * 0.11) + max(-4.0, min(4.0, lat * 0.10))
        racer["handbrake"] = handbrake
        racer["boosting"] = boost
        _keep_racer_on_track(self, racer, dt)
        _apply_obstacle_collision(self, racer, is_player=True)
        _update_loop_gate_score(self, racer)
        _update_score_crystals(self, racer)
        _update_racer_height(self, racer, dt)

    def _update_bot_racer(self, racer, dt):
        if bool(racer.get("finished", False)):
            racer["speed"] = float(racer.get("speed", 0.0)) * max(0.0, 1.0 - dt * 1.2)
            _update_racer_height(self, racer, dt)
            return
        wps = list(getattr(self, "frost_circuit_waypoints", []) or [])
        if not wps:
            return
        idx = int(racer.get("current_wp", 0)) % len(wps)
        target = Vec3(wps[idx])
        next_target = Vec3(wps[(idx + 1) % len(wps)])
        pos = Vec3(racer.get("pos", Vec3()))
        dist = _dist2d(pos, target)
        look_blend = max(0.0, min(0.42, (190.0 - dist) / 330.0))
        target = target * (1.0 - look_blend) + next_target * look_blend
        desired = _yaw_to_target(pos, target)
        current_yaw = float(racer.get("yaw", 0.0))
        avoid, slow, threats = _obstacle_avoidance(self, pos, current_yaw, lookahead=190.0 + abs(float(racer.get("speed", 0.0))) * 1.15)
        if threats:
            self.frost_circuit_ai_avoidance_events = int(getattr(self, "frost_circuit_ai_avoidance_events", 0) or 0) + int(threats)
            desired += avoid * 48.0
        for other in list(getattr(self, "frost_circuit_racers", []) or []):
            if other is racer:
                continue
            other_pos = Vec3(other.get("pos", Vec3()))
            sep = other_pos - pos
            sep.z = 0.0
            d2 = sep.lengthSquared()
            if 1.0 < d2 < 48.0 * 48.0:
                side = 1.0 if (int(racer.get("seed", 0)) + int(other.get("seed", 0))) % 2 else -1.0
                desired += side * 16.0 * (1.0 - math.sqrt(d2) / 48.0)
        diff = _wrap_deg(desired - current_yaw)
        handling = float(racer.get("handling", 1.0))
        max_turn = (82.0 + handling * 32.0) * dt
        turn = max(-max_turn, min(max_turn, diff))
        yaw = (current_yaw + turn) % 360.0
        speed = float(racer.get("speed", 0.0))
        max_speed = float(racer.get("max_speed", 88.0))
        rankings = _race_rankings(self)
        try:
            rank = rankings.index(racer) + 1
        except Exception:
            rank = len(rankings)
        catchup = 1.0 + max(0, rank - 3) * 0.035
        corner_slow = 1.0 - min(0.50, abs(diff) / 150.0)
        target_speed = max_speed * catchup * corner_slow * slow
        if threats and abs(diff) < 45.0:
            target_speed *= 0.82
        elif (int(time.time() * 2.0 + int(racer.get("seed", 0))) % 17) == 0 and abs(diff) < 18.0:
            target_speed *= 1.09
        speed_blend = min(1.0, dt * (2.05 if not threats else 2.85))
        speed = speed * (1.0 - speed_blend) + target_speed * speed_blend
        forward = _heading_vec(yaw)
        pos = pos + forward * speed * dt
        racer["yaw"] = yaw
        racer["speed"] = speed
        racer["pos"] = pos
        racer["steer_bank"] = -max(-1.0, min(1.0, turn / max(max_turn, 0.001))) * min(16.0, abs(speed) * 0.16)
        _keep_racer_on_track(self, racer, dt)
        _apply_obstacle_collision(self, racer, is_player=False)
        _update_racer_height(self, racer, dt)

    def _racer_progress(self, racer):
        wps = list(getattr(self, "frost_circuit_waypoints", []) or [])
        if not wps:
            return 0.0
        if bool(racer.get("finished", False)):
            return 999999.0 - float(racer.get("finish_time") or 9999.0)
        idx = int(racer.get("current_wp", 0)) % len(wps)
        dist = _dist2d(Vec3(racer.get("pos", Vec3())), wps[idx])
        segment = float(getattr(self, "frost_circuit_track_length", frost_track_length(len(wps))) or frost_track_length(len(wps))) / max(1, len(wps))
        return int(racer.get("lap", 0)) * len(wps) + idx - min(0.99, dist / max(1.0, segment))

    def _race_rankings(self):
        racers = list(getattr(self, "frost_circuit_racers", []) or [])
        return sorted(racers, key=lambda r: _racer_progress(self, r), reverse=True)

    def _complete_player_race(self, player):
        if bool(getattr(self, "frost_circuit_finished", False)):
            return
        self.frost_circuit_finished = True
        rankings = _race_rankings(self)
        results = []
        for i, racer in enumerate(rankings, start=1):
            ft = racer.get("finish_time")
            results.append({
                "rank": i,
                "name": str(racer.get("name") or "Racer"),
                "time": None if ft is None else round(float(ft), 3),
                "lap": int(racer.get("lap", 0)),
                "waypoint": int(racer.get("current_wp", 0)),
            })
        finish_time = float(player.get("finish_time") or (time.time() - float(getattr(self, "frost_circuit_started_at", time.time()))))
        player_rank = next((r["rank"] for r in results if r.get("name") == "Player"), len(results) or 1)
        rank_bonus = max(125, ICE_FINISH_SCORE - max(0, int(player_rank) - 1) * 105)
        speed_finish_bonus = max(0, int(220 - finish_time * 2.0))
        _add_frost_score(self, rank_bonus + speed_finish_bonus, reason="finish")
        old_best = getattr(self, "frost_circuit_best_time", None)
        if old_best is None or finish_time < float(old_best):
            self.frost_circuit_best_time = round(finish_time, 3)
        if results and results[0].get("name") == "Player":
            self.frost_circuit_wins = int(getattr(self, "frost_circuit_wins", 0) or 0) + 1
        self.frost_circuit_races_completed = int(getattr(self, "frost_circuit_races_completed", 0) or 0) + 1
        self.frost_circuit_last_results = results[:12]
        save_frost_circuit_state(self, reason="race_finished")
        try:
            rank = next((r["rank"] for r in results if r.get("name") == "Player"), "?")
            self.center_hint["text"] = f"FROST CIRCUIT // FINISHED #{rank} // {finish_time:0.1f}s // ESC ICE / TAB HOME"
        except Exception:
            pass

    def _update_camera(self, player, dt=0.016):
        pos = Vec3(player.get("pos", Vec3()))
        yaw = float(player.get("yaw", 0.0))
        forward = _heading_vec(yaw)
        speed = abs(float(player.get("speed", 0.0) or 0.0))
        mode = str(getattr(self, "frost_circuit_camera_mode", "far_chase") or "far_chase")
        base_distance = float(getattr(self, "frost_circuit_camera_distance", 34.0) or 34.0)
        base_height = float(getattr(self, "frost_circuit_camera_height", 11.5) or 11.5)
        lookahead = float(getattr(self, "frost_circuit_camera_lookahead", 40.0) or 40.0)
        if mode == "overhead":
            distance = max(22.0, base_distance * 0.50)
            height = max(48.0, base_height * 2.75)
            lookahead = max(8.0, lookahead * 0.45)
        elif mode == "cinematic":
            distance = max(44.0, base_distance * 1.18 + speed * 0.055)
            height = max(26.0, base_height * 1.16 + speed * 0.030)
            lookahead = max(42.0, lookahead * 1.18)
        else:
            distance = max(32.0, base_distance + speed * 0.040)
            height = max(14.0, base_height + speed * 0.020)
        target_camera_pos = pos - forward * distance + Vec3(0, 0, height)
        target_look = pos + forward * lookahead + Vec3(0, 0, 4.2)
        smooth = max(0.08, min(1.0, float(dt or 0.016) * 5.8))
        old_pos = getattr(self, "frost_circuit_camera_smooth_pos", None)
        old_target = getattr(self, "frost_circuit_camera_smooth_target", None)
        if old_pos is None:
            camera_pos = Vec3(target_camera_pos)
        else:
            camera_pos = Vec3(old_pos) + (target_camera_pos - Vec3(old_pos)) * smooth
        if old_target is None:
            look_target = Vec3(target_look)
        else:
            look_target = Vec3(old_target) + (target_look - Vec3(old_target)) * min(1.0, smooth * 1.35)
        self.frost_circuit_camera_smooth_pos = Vec3(camera_pos)
        self.frost_circuit_camera_smooth_target = Vec3(look_target)
        # Keep the player position in the world shell near the camera so region
        # systems, teleport safety, and UI tracking remain coherent
        # while the actual race state is owned by the hovercraft record.
        self.player_pos = Vec3(camera_pos)
        try:
            self.camera.setPos(camera_pos)
            self.camera.lookAt(look_target)
        except Exception:
            try:
                self.camera.setPos(camera_pos)
                self.camera.setHpr(yaw, -12.0, 0.0)
            except Exception:
                pass
        try:
            self.player_yaw = yaw
            self.player_pitch = -14.0 if mode != "overhead" else -54.0
        except Exception:
            pass

    def adjust_frost_circuit_camera(self, distance_delta=0.0, height_delta=0.0, lookahead_delta=0.0):
        if not bool(getattr(self, "frost_circuit_active", False)):
            return False
        def clamp(v, lo, hi):
            return max(float(lo), min(float(hi), float(v)))
        self.frost_circuit_camera_distance = clamp(float(getattr(self, "frost_circuit_camera_distance", 34.0) or 34.0) + float(distance_delta or 0.0), 28.0, 90.0)
        self.frost_circuit_camera_height = clamp(float(getattr(self, "frost_circuit_camera_height", 11.5) or 11.5) + float(height_delta or 0.0), 10.0, 58.0)
        self.frost_circuit_camera_lookahead = clamp(float(getattr(self, "frost_circuit_camera_lookahead", 40.0) or 40.0) + float(lookahead_delta or 0.0), 12.0, 72.0)
        try:
            self.center_hint["text"] = f"FROST CAMERA // DIST {self.frost_circuit_camera_distance:.0f} HEIGHT {self.frost_circuit_camera_height:.0f}"
        except Exception:
            pass
        return True

    def cycle_frost_circuit_camera(self):
        if not bool(getattr(self, "frost_circuit_active", False)):
            return False
        modes = ["far_chase", "cinematic", "overhead"]
        current = str(getattr(self, "frost_circuit_camera_mode", "far_chase") or "far_chase")
        try:
            idx = modes.index(current)
        except ValueError:
            idx = 0
        self.frost_circuit_camera_mode = modes[(idx + 1) % len(modes)]
        self.frost_circuit_camera_smooth_pos = None
        self.frost_circuit_camera_smooth_target = None
        try:
            self.center_hint["text"] = f"FROST CAMERA // {self.frost_circuit_camera_mode.upper().replace('_', ' ')}"
        except Exception:
            pass
        return True

    def create_frost_circuit_ui(self):
        if getattr(self, "frost_circuit_ui_root", None) is not None:
            return
        self.frost_circuit_ui_root = self.aspect2d.attachNewNode("frost-circuit-ui")
        # Keep race telemetry out of the driving view.  The upper-right panel
        # owns a small sky-side safe zone while MatrixCore identity remains
        # upper-left and transient world notifications remain bottom-center.
        self.frost_circuit_ui_panel = DirectFrame(
            parent=self.frost_circuit_ui_root,
            frameColor=(0.010, 0.018, 0.035, 0.76),
            frameSize=(-0.70, 0.70, -0.145, 0.145),
            pos=(0.91, 0, 0.625),
        )
        self.frost_circuit_ui_title = DirectLabel(
            parent=self.frost_circuit_ui_panel, text="FROST CIRCUIT", text_align=TextNode.ALeft,
            text_fg=(0.66, 0.94, 1.0, 1), text_shadow=(0, 0, 0, 0.82), frameColor=(0, 0, 0, 0),
            scale=0.030, pos=(-0.64, 0, 0.092),
        )
        self.frost_circuit_ui_status = DirectLabel(
            parent=self.frost_circuit_ui_panel, text="", text_align=TextNode.ALeft,
            text_fg=(1.0, 1.0, 1.0, 0.96), text_shadow=(0, 0, 0, 0.82), frameColor=(0, 0, 0, 0),
            scale=0.019, pos=(-0.64, 0, 0.030),
        )
        self.frost_circuit_ui_help = DirectLabel(
            parent=self.frost_circuit_ui_panel, text="", text_align=TextNode.ALeft,
            text_fg=(0.82, 0.92, 1.0, 0.92), text_shadow=(0, 0, 0, 0.78), frameColor=(0, 0, 0, 0),
            scale=0.016, pos=(-0.64, 0, -0.088),
        )

    def update_frost_circuit_ui(self):
        if not bool(getattr(self, "frost_circuit_active", False)):
            return
        create_frost_circuit_ui(self)
        racers = list(getattr(self, "frost_circuit_racers", []) or [])
        player = racers[0] if racers else None
        rankings = _race_rankings(self)
        rank = "?"
        for i, r in enumerate(rankings, start=1):
            if r is player:
                rank = str(i)
                break
        elapsed = max(0.0, time.time() - float(getattr(self, "frost_circuit_started_at", time.time()) or time.time()))
        if player:
            wp = int(player.get("current_wp", 0))
            lap = min(ICE_REQUIRED_LAPS, int(player.get("lap", 0)) + 1)
            spd = abs(float(player.get("speed", 0.0)))
            best = getattr(self, "frost_circuit_best_time", None)
            best_txt = "--" if best is None else f"{float(best):0.1f}s"
            score = int(getattr(self, "frost_circuit_score", 0) or 0)
            total = int(getattr(self, "frost_circuit_total_score", 0) or 0)
            streak = int(getattr(self, "frost_circuit_clean_waypoint_streak", 0) or 0)
            track_state = "OFF ICE" if bool(player.get("offtrack", False)) else "ON COURSE"
            status = (
                f"RANK {rank}/{len(racers)}  LAP {lap}/{ICE_REQUIRED_LAPS}  CP {wp:02d}/{ICE_TRACK_WAYPOINTS}  SPD {spd:03.0f}\n"
                f"{track_state}  RUN {score}  SAVED {total}  STREAK x{streak}  BEST {best_txt}"
            )
        else:
            status = "RACE READY"
        help_text = "W THROTTLE  S BRAKE/REV  A/D STEER  SPACE DRIFT  SHIFT BOOST  R RESET  ESC ICE  TAB HOME"
        try:
            self.frost_circuit_ui_status["text"] = status
            self.frost_circuit_ui_help["text"] = help_text
        except Exception:
            pass

    def reset_player_to_last_waypoint(self):
        if not bool(getattr(self, "frost_circuit_active", False)):
            return
        racers = list(getattr(self, "frost_circuit_racers", []) or [])
        wps = list(getattr(self, "frost_circuit_waypoints", []) or [])
        if not racers or not wps:
            return
        player = racers[0]
        idx = max(0, (int(player.get("current_wp", 1)) - 1) % len(wps))
        pos = Vec3(wps[idx])
        target = wps[int(player.get("current_wp", 0)) % len(wps)]
        player["pos"] = Vec3(pos.x, pos.y, _floor_z(self, pos.x, pos.y) + ICE_HOVER_BASE_CLEARANCE)
        player["yaw"] = _yaw_to_target(player["pos"], target)
        player["speed"] = 0.0
        player["velocity"] = Vec3(0, 0, 0)
        player["steer_input_smoothed"] = 0.0
        self.center_hint["text"] = "FROST CIRCUIT // RESET TO LAST WAYPOINT"

    def activate_frost_circuit_from_mode(self, mode=None, source="core", route=""):
        if not _ice_allowed(self):
            self.center_hint["text"] = "FROST CIRCUIT // ENTER ICE REGION TO RACE"
            return False
        try:
            if getattr(self, "holoforge_active", False): self.deactivate_holoforge(reason="switch_to_frost_circuit")
            if getattr(self, "forest_growth_active", False): self.deactivate_forest_growth(reason="switch_to_frost_circuit")
            if getattr(self, "hills_life_active", False): self.deactivate_hills_life(reason="switch_to_frost_circuit")
            if getattr(self, "oddities_active", False): self.deactivate_oddities(reason="switch_to_frost_circuit")
            if getattr(self, "desert_ships_active", False): self.deactivate_desert_ships(reason="switch_to_frost_circuit")
            if getattr(self, "shell_flight_craft_active", False): self.toggle_shell_flight_craft()
        except Exception:
            pass
        _ensure_dirs()
        load_frost_circuit_state(self)
        self.frost_circuit_active = True
        self.frost_circuit_finished = False
        self.frost_circuit_exit_prompt_until = 0.0
        self.frost_circuit_score = 0
        self.frost_circuit_points_this_run = 0
        self.frost_circuit_crystals_collected = 0
        self.frost_circuit_clean_waypoint_streak = 0
        self.frost_circuit_last_player_rank = None
        self.frost_circuit_drift_score_bank = 0.0
        self.frost_circuit_boost_score_bank = 0.0
        self.frost_circuit_last_score_tick = time.time()
        self.frost_circuit_player_saved_pos = Vec3(getattr(self, "player_pos", Vec3(0, 0, 0)))
        try:
            self.frost_circuit_player_saved_hpr = self.camera.getHpr()
        except Exception:
            self.frost_circuit_player_saved_hpr = None
        _ensure_root(self)
        _generate_waypoints(self)
        _build_track_visuals(self)
        _setup_racers(self)
        try:
            if self.frost_circuit_racers:
                _update_camera(self, self.frost_circuit_racers[0], 0.20)
        except Exception:
            pass
        self.frost_circuit_started_at = time.time()
        create_frost_circuit_ui(self)
        update_frost_circuit_ui(self)
        try:
            self.center_hint.hide()
            if hasattr(self, "context_hint_root"):
                self.context_hint_root.hide()
                self.hud_hint_alpha = 0.0
        except Exception:
            pass
        self.center_hint["text"] = "FROST CIRCUIT // COMPACT HOVER RACE // FOLLOW THE LIT COURSE"
        label = str((mode or {}).get("name") or "Frost Circuit")
        try:
            self.core_mode_state["launch_count"] = int(self.core_mode_state.get("launch_count", 0)) + 1
            self.core_mode_state["last_mode"] = label
            self.core_mode_state["last_entry"] = IN_WORLD_ROUTE
            self.core_mode_state["last_launch_type"] = IN_WORLD_ROUTE
            self.core_mode_state["last_launch_source"] = str(source or "core")
            main.save_mode_state(self.core_mode_state)
        except Exception:
            pass
        try:
            self._append_mode_gateway_history("frost_circuit_runtime_open", mode=mode, label=label, route=IN_WORLD_ROUTE, extra={"source": source, "state": str(STATE_PATH), "racers": len(self.frost_circuit_racers)})
        except Exception:
            pass
        return True

    def deactivate_frost_circuit(self, reason="closed"):
        if not bool(getattr(self, "frost_circuit_active", False)):
            return
        # Drop the player at the current hovercraft location so quitting the race
        # does not snap them back to the old camera or leave them floating high.
        try:
            racers = list(getattr(self, "frost_circuit_racers", []) or [])
            if racers:
                craft_pos = Vec3(racers[0].get("pos", self.frost_circuit_player_saved_pos or Vec3(0, 0, 0)))
                self.player_pos = Vec3(craft_pos.x, craft_pos.y, _eye_z(self, craft_pos.x, craft_pos.y))
                self.camera.setPos(self.player_pos)
                self.camera.setHpr(float(racers[0].get("yaw", 0.0)), -8.0, 0.0)
            elif self.frost_circuit_player_saved_pos is not None:
                self.player_pos = Vec3(self.frost_circuit_player_saved_pos)
                self.camera.setPos(self.player_pos)
        except Exception:
            pass
        save_frost_circuit_state(self, reason=reason)
        self.frost_circuit_active = False
        _destroy_visuals(self)
        self.frost_circuit_racers = []
        self.frost_circuit_waypoints = []
        try:
            self.center_hint.show()
        except Exception:
            pass
        self.center_hint["text"] = f"FROST CIRCUIT // SAVED + CLOSED ({str(reason).upper()})"
        try:
            self._append_mode_gateway_history("frost_circuit_runtime_close", label="Frost Circuit", route=IN_WORLD_ROUTE, extra={"reason": reason, "state": str(STATE_PATH)})
        except Exception:
            pass

    def update_frost_circuit(self, dt=0.0):
        if not bool(getattr(self, "frost_circuit_active", False)):
            return
        dt = max(0.001, min(0.05, float(dt or 0.016)))
        racers = list(getattr(self, "frost_circuit_racers", []) or [])
        if not racers:
            deactivate_frost_circuit(self, reason="empty_race")
            return
        player = racers[0]
        # Unload if player physically exits the ice ring. Teleport and TAB also
        # unload through wrappers below.
        p = Vec3(player.get("pos", Vec3()))
        radius = math.sqrt(float(p.x) * float(p.x) + float(p.y) * float(p.y))
        if radius < ICE_R0 - ICE_LEAVE_MARGIN or radius > ICE_R1 + ICE_LEAVE_MARGIN:
            deactivate_frost_circuit(self, reason="left_ice_region")
            return
        _update_player_racer(self, player, dt)
        now = time.time()
        last_tick = float(getattr(self, "frost_circuit_last_score_tick", 0.0) or 0.0)
        if now - last_tick >= 1.0 and not bool(getattr(self, "frost_circuit_finished", False)):
            spd_bonus = ICE_SPEED_SCORE_PER_SECOND + int(min(18.0, abs(float(player.get("speed", 0.0))) / 18.0))
            _add_frost_score(self, spd_bonus, reason="speed_tick")
            self.frost_circuit_last_score_tick = now
            if now - float(getattr(self, "frost_circuit_last_save_at", 0.0) or 0.0) > 12.0:
                save_frost_circuit_state(self, reason="active_score_tick")
        for racer in racers[1:]:
            _update_bot_racer(self, racer, dt)
        for racer in racers:
            _advance_racer_waypoint(self, racer, now)
            _update_hovercraft_node(self, racer)
        rankings_now = _race_rankings(self)
        try:
            player_rank = rankings_now.index(player) + 1
        except Exception:
            player_rank = len(rankings_now) or 1
        last_rank = getattr(self, "frost_circuit_last_player_rank", None)
        if last_rank is None:
            self.frost_circuit_last_player_rank = player_rank
        elif player_rank < int(last_rank) and not bool(getattr(self, "frost_circuit_finished", False)):
            passes = max(1, int(last_rank) - int(player_rank))
            gained = _add_frost_score(self, ICE_OVERTAKE_SCORE * passes, reason="overtake")
            self.frost_circuit_rank_bonus_count = int(getattr(self, "frost_circuit_rank_bonus_count", 0) or 0) + passes
            self.frost_circuit_last_player_rank = player_rank
            try:
                self.center_hint["text"] = f"FROST CIRCUIT // OVERTAKE +{gained}"
            except Exception:
                pass
        elif player_rank > int(last_rank):
            self.frost_circuit_last_player_rank = player_rank
        _update_camera(self, player, dt)
        if bool(player.get("finished", False)):
            _complete_player_race(self, player)
        update_frost_circuit_ui(self)

    def frost_circuit_smoke_begin(self, task):
        """Native Panda3D proof for Ice residency, race completion, ESC/TAB law."""
        errors=[]; records=[]
        try:
            station=self._route_perfection_station("region_ice")
            if station is None or not bool(self.activate_artifact_direct(station, source="frost_smoke_region")):
                errors.append("ice_region_entry_failed")
            ring_report={}
            try:
                mount=getattr(self,"world_shell_mount",None); runtime=getattr(mount,"source_runtime",None) if mount is not None else None
                if runtime is not None:
                    runtime.update_runtime(0.0); ring_report=dict(runtime.report() or {})
                    # Since Pass 282.51 the ring streams in over a few frames instead of
                    # stalling on entry; give it up to 600 runtime updates to finish.
                    for _ in range(600):
                        if int((ring_report.get("loaded_sector_counts") or {}).get("6",0)) >= 48: break
                        runtime.update_runtime(0.016); ring_report=dict(runtime.report() or {})
            except Exception as exc:
                errors.append(f"ice_ring_report:{exc.__class__.__name__}")
            records.append({"phase":"ice_ring","report":ring_report})
            if ring_report:
                if ring_report.get("loaded_ring_keys") != [6]: errors.append(f"ice_ring_ownership:{ring_report.get('loaded_ring_keys')}")
                if int((ring_report.get("loaded_sector_counts") or {}).get("6",0)) != 48: errors.append(f"ice_full_ring_count:{ring_report.get('loaded_sector_counts')}")
            mode=None
            for candidate in list(getattr(self,"core_modes",[]) or []):
                if self.is_frost_circuit_mode(candidate): mode=candidate; break
            opened=bool(self.activate_frost_circuit_from_mode(mode, source="frost_smoke", route=IN_WORLD_ROUTE))
            racers=list(getattr(self,"frost_circuit_racers",[]) or []); wps=list(getattr(self,"frost_circuit_waypoints",[]) or [])
            records.append({"phase":"race_open","opened":opened,"active":bool(getattr(self,"frost_circuit_active",False)),"racers":len(racers),"waypoints":len(wps)})
            if not opened or not bool(getattr(self,"frost_circuit_active",False)): errors.append("frost_race_open_failed")
            if len(racers) != 8: errors.append(f"frost_racer_count:{len(racers)}")
            if len(wps) != ICE_TRACK_WAYPOINTS: errors.append(f"frost_waypoint_count:{len(wps)}")
            try:
                if wps:
                    cx=sum(float(v.x) for v in wps)/len(wps); cy=sum(float(v.y) for v in wps)/len(wps)
                    self.camera.setPos(cx, cy - 260.0, 610.0); self.camera.lookAt(Vec3(cx, cy, 0.0))
                    if hasattr(self, "context_hint_root"): self.context_hint_root.hide()
                    if self.graphicsEngine is not None: self.graphicsEngine.renderFrame()
                    if self.win is not None: self.win.saveScreenshot(main.Filename.fromOsSpecific(str(main.FROST_CIRCUIT_TRACK_OVERVIEW_SMOKE_SCREENSHOT)))
                    if racers: _update_camera(self,racers[0],0.20)
            except Exception as exc: errors.append(f"track_overview_screenshot:{exc.__class__.__name__}")
            if racers and wps:
                player=racers[0]
                keys=getattr(self,"keys",{})
                # Explicit brake-response test before the full lap.
                keys["w"]=True; keys["space"]=False
                for _ in range(24): _update_player_racer(self,player,0.05)
                speed_before_brake=abs(float(player.get("speed",0.0) or 0.0))
                keys["w"]=False; keys["space"]=True
                for _ in range(8): _update_player_racer(self,player,0.05)
                speed_after_brake=abs(float(player.get("speed",0.0) or 0.0))
                keys["space"]=False
                records.append({"phase":"brake_response","before":round(speed_before_brake,3),"after":round(speed_after_brake,3)})
                if speed_before_brake < 10.0 or speed_after_brake >= speed_before_brake * 0.72: errors.append(f"frost_brake_response:{speed_before_brake:.1f}->{speed_after_brake:.1f}")
                reset_player_to_last_waypoint(self)
                start=Vec3(player.get("pos",Vec3()))
                sim_start=time.time()
                steps=0; max_track_distance=0.0; steering_frames=0; braking_frames=0
                # Drive the real compact circuit using only the same W/A/S/D/Space/Shift
                # control path available to the player. No waypoint teleporting is allowed.
                while not bool(player.get("finished",False)) and steps < 2600:
                    idx=int(player.get("current_wp",0)) % len(wps)
                    target=Vec3(wps[idx])
                    pos=Vec3(player.get("pos",Vec3()))
                    desired=_yaw_to_target(pos,target)
                    diff=_wrap_deg(desired-float(player.get("yaw",0.0)))
                    speed=abs(float(player.get("speed",0.0) or 0.0))
                    keys["w"]=True
                    keys["s"]=False
                    keys["a"]=diff < -2.4
                    keys["d"]=diff > 2.4
                    keys["space"]=abs(diff) > 34.0 and speed > 58.0
                    keys["shift"]=abs(diff) < 9.0 and speed > 55.0
                    steering_frames += int(keys["a"] or keys["d"])
                    braking_frames += int(keys["space"])
                    _update_player_racer(self,player,0.05)
                    _advance_racer_waypoint(self,player,sim_start+steps*0.05)
                    _update_hovercraft_node(self,player)
                    max_track_distance=max(max_track_distance,float(player.get("track_distance",0.0) or 0.0))
                    if steps == 240:
                        try:
                            _update_camera(self,player,0.05); update_frost_circuit_ui(self)
                            if self.graphicsEngine is not None: self.graphicsEngine.renderFrame()
                            if self.win is not None: self.win.saveScreenshot(main.Filename.fromOsSpecific(str(main.FROST_CIRCUIT_RACE_SMOKE_SCREENSHOT)))
                        except Exception as exc: errors.append(f"race_screenshot:{exc.__class__.__name__}")
                    steps += 1
                for key in ("w","a","s","d","space","shift"): keys[key]=False
                moved=_dist2d(start,Vec3(player.get("pos",Vec3())))
                records.append({"phase":"handling_lap","steps":steps,"sim_seconds":round(steps*0.05,2),"moved_from_start":round(float(moved),3),"speed":round(float(player.get("speed",0.0)),3),"steering_frames":steering_frames,"braking_frames":braking_frames,"max_track_distance":round(max_track_distance,3),"finished":bool(player.get("finished",False))})
                if steering_frames <= 0: errors.append("frost_controls_no_steering")
                if max_track_distance > ICE_TRACK_RESET_WIDTH + 2.0: errors.append(f"frost_track_escape:{max_track_distance:.1f}")
                if not bool(player.get("finished",False)): errors.append(f"frost_input_driven_lap_failed:{steps}")
                before=int(getattr(self,"frost_circuit_races_completed",0) or 0)
                _complete_player_race(self,player)
                after=int(getattr(self,"frost_circuit_races_completed",0) or 0)
                records.append({"phase":"finish","finished":bool(player.get("finished",False)),"races_before":before,"races_after":after,"score":int(getattr(self,"frost_circuit_score",0) or 0)})
                if after != before+1: errors.append(f"frost_completion_persistence:{before}->{after}")
                try:
                    update_frost_circuit_ui(self)
                    if self.graphicsEngine is not None: self.graphicsEngine.renderFrame()
                    if self.win is not None: self.win.saveScreenshot(main.Filename.fromOsSpecific(str(main.FROST_CIRCUIT_FINISH_SMOKE_SCREENSHOT)))
                except Exception as exc: errors.append(f"finish_screenshot:{exc.__class__.__name__}")
            # TAB must cleanly close Frost and continue through the host home action.
            self.handle_tab_action()
            home_distance=round(float((Vec3(self.player_pos)-Vec3(self.base_teleport)).length()),4)
            records.append({"phase":"tab_home","home_distance":home_distance,"frost_active":bool(getattr(self,"frost_circuit_active",False))})
            if home_distance > 0.5: errors.append("frost_tab_home_failed")
            if bool(getattr(self,"frost_circuit_active",False)): errors.append("frost_active_after_tab_home")
        except Exception as exc:
            errors.append(f"exception:{exc.__class__.__name__}:{exc}")
        report={"schema":1,"kind":"frost_circuit_control_and_completion_smoke","status":"PASS" if not errors else "FAIL","errors":errors,"records":records,"tab_owner":"MATRIXCORE_HOME","local_exit":"ESC_DOUBLE_PRESS","race_laps":ICE_REQUIRED_LAPS}
        try:
            main.LOG_DIR.mkdir(parents=True,exist_ok=True); main.FROST_CIRCUIT_SMOKE_REPORT.write_text(json.dumps(report,indent=2),encoding="utf-8")
        except Exception: pass
        print(json.dumps(report,indent=2)); self.userExit()
        try: sys.stdout.flush(); sys.stderr.flush()
        except Exception: pass
        import os
        os._exit(0 if report["status"]=="PASS" else 2)
        return main.Task.done

    CommandHubApp.frost_circuit_smoke_begin = frost_circuit_smoke_begin

    # Public runtime API.
    CommandHubApp.is_frost_circuit_mode = _is_frost_circuit_mode
    CommandHubApp.activate_frost_circuit_from_mode = activate_frost_circuit_from_mode
    CommandHubApp.deactivate_frost_circuit = deactivate_frost_circuit
    CommandHubApp.load_frost_circuit_state = load_frost_circuit_state
    CommandHubApp.save_frost_circuit_state = save_frost_circuit_state
    CommandHubApp.update_frost_circuit = update_frost_circuit
    CommandHubApp.reset_player_to_last_waypoint = reset_player_to_last_waypoint
    CommandHubApp.adjust_frost_circuit_camera = adjust_frost_circuit_camera
    CommandHubApp.cycle_frost_circuit_camera = cycle_frost_circuit_camera

    old_init = CommandHubApp.__init__
    def __init__(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        _init_state(self)
    CommandHubApp.__init__ = __init__

    old_setup_input = CommandHubApp.setup_input
    def setup_input(self, *args, **kwargs):
        # Keep prior runtime key bindings intact. R already routes through
        # holoforge_rotate_tool in the shared builder controls; we intercept that
        # method below only while Frost Circuit is active.
        result = old_setup_input(self, *args, **kwargs)
        self.accept("wheel_up", self.adjust_frost_circuit_camera, [-6.0, 0.0, -2.0])
        self.accept("wheel_down", self.adjust_frost_circuit_camera, [6.0, 0.0, 2.0])
        self.accept("[", self.adjust_frost_circuit_camera, [-6.0, 0.0, -2.0])
        self.accept("]", self.adjust_frost_circuit_camera, [6.0, 0.0, 2.0])
        self.accept("page_up", self.adjust_frost_circuit_camera, [0.0, 5.0, 0.0])
        self.accept("page_down", self.adjust_frost_circuit_camera, [0.0, -5.0, 0.0])
        self.accept("v", self.cycle_frost_circuit_camera)
        return result
    CommandHubApp.setup_input = setup_input


    old_r_rotate = getattr(CommandHubApp, "holoforge_rotate_tool", None)
    if callable(old_r_rotate):
        def holoforge_rotate_tool(self, amount=15.0):
            if bool(getattr(self, "frost_circuit_active", False)):
                return self.reset_player_to_last_waypoint()
            return old_r_rotate(self, amount)
        CommandHubApp.holoforge_rotate_tool = holoforge_rotate_tool

    old_start_escape_hold = CommandHubApp.start_escape_hold
    def start_escape_hold(self):
        if bool(getattr(self, "frost_circuit_active", False)):
            now = time.monotonic()
            until = float(getattr(self, "frost_circuit_exit_prompt_until", 0.0) or 0.0)
            if now <= until:
                self.deactivate_frost_circuit(reason="escape_confirmed")
            else:
                self.frost_circuit_exit_prompt_until = now + 2.2
                self.center_hint["text"] = "FROST CIRCUIT // PRESS ESC AGAIN TO EXIT RACE"
            return
        return old_start_escape_hold(self)
    CommandHubApp.start_escape_hold = start_escape_hold

    old_route = CommandHubApp.launch_core_mode_route
    def launch_core_mode_route(self, mode, source="core", extra_env=None, close_core=True):
        if self.is_frost_circuit_mode(mode):
            return bool(self.activate_frost_circuit_from_mode(mode, source=source, route=IN_WORLD_ROUTE))
        return old_route(self, mode, source=source, extra_env=extra_env, close_core=close_core)
    CommandHubApp.launch_core_mode_route = launch_core_mode_route

    old_update_player = CommandHubApp.update_player
    def update_player(self, dt):
        if bool(getattr(self, "frost_circuit_active", False)):
            self.update_frost_circuit(dt)
            return
        return old_update_player(self, dt)
    CommandHubApp.update_player = update_player

    old_handle_tab = CommandHubApp.handle_tab_action
    def handle_tab_action(self):
        if bool(getattr(self, "frost_circuit_active", False)):
            # TAB is HoloVerse's universal MatrixCore-home law.  Frost Circuit
            # may clean up first, but it must never swallow the host return.
            self.deactivate_frost_circuit(reason="tab_home")
            return old_handle_tab(self)
        return old_handle_tab(self)
    CommandHubApp.handle_tab_action = handle_tab_action

    old_number = CommandHubApp.handle_number_action
    def handle_number_action(self, number):
        if bool(getattr(self, "frost_circuit_active", False)):
            self.deactivate_frost_circuit(reason="teleport_exit")
        return old_number(self, number)
    CommandHubApp.handle_number_action = handle_number_action

    old_region_ui = CommandHubApp.update_holoverse_region_ui
    def update_holoverse_region_ui(self):
        result = old_region_ui(self)
        if bool(getattr(self, "frost_circuit_active", False)):
            try:
                if hasattr(self, "region_keymap_root"):
                    self.region_keymap_root.hide()
                if hasattr(self, "region_top_panel"):
                    self.region_top_panel.hide()
            except Exception:
                pass
        return result
    CommandHubApp.update_holoverse_region_ui = update_holoverse_region_ui

    setattr(main, "FROST_CIRCUIT_RUNTIME_INSTALLED", True)
    setattr(main, "FROST_CIRCUIT_STATE_PATH_RUNTIME", STATE_PATH)
