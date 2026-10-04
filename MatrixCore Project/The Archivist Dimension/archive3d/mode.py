from __future__ import annotations

import math
import os
import textwrap
from pathlib import Path
from typing import Any

from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from direct.showbase.DirectObject import DirectObject
from panda3d.core import (
    AmbientLight, CardMaker, DirectionalLight, Filename, Fog, NodePath,
    PerspectiveLens, PointLight, TextNode, TransparencyAttrib, Vec3, LineSegs,
    WindowProperties,
)

from reading_progress import load_reading_db, note_open, note_position, resume_spread, save_reading_db
from .data import (
    READING_PATH, ROOT as DATA_ROOT, book_text, find_soundtrack, load_catalog, load_links,
    orb_texture_path, resolve_simulation, simulation_art_path,
)
from .geometry import make_beam_between, make_box, make_ring_segments, make_uv_sphere
from .simulation_links import enter_simulation

ROOT = Path(__file__).resolve().parents[1]
ORB_ROOT = ROOT / "assets" / "orbs"
CYBER_ROOT = ROOT / "assets" / "cyber"
INTERNAL_ECHO_ENTRY = ROOT / "simulations" / "archive_echo" / "main.py"

ARCHIVE_DARK = (0.004, 0.006, 0.011, 1.0)
ARCHIVE_METAL = (0.105, 0.125, 0.155, 1.0)
ARCHIVE_GOLD = (0.70, 0.49, 0.20, 1.0)
ARCHIVE_CYAN = (0.22, 0.72, 0.82, 1.0)
ARCHIVE_VIOLET = (0.48, 0.30, 0.72, 1.0)
ARCHIVE_RED = (0.74, 0.19, 0.12, 1.0)
ARCHIVE_SHELL = (0.20, 0.26, 0.34, 0.46)
ARCHIVE_SHELL_GOLD = (0.52, 0.34, 0.15, 0.34)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _safe_title(book: dict) -> str:
    return str(book.get("display_title") or book.get("title") or "Untitled")


class ArchiveOrbExhibit:
    def __init__(
        self,
        book: dict,
        anchor: NodePath,
        sphere: NodePath,
        base_pos: Vec3,
        radius: float,
        phase: float,
        spin: float,
        linked: bool,
        texture_path: Path | None,
        texture=None,
        halo: NodePath | None = None,
        role: str = "record",
        system_id: str = "",
        orbit_parent: NodePath | None = None,
        orbit_radius: float = 0.0,
        orbit_speed: float = 0.0,
        orbit_phase: float = 0.0,
        orbit_tilt: Vec3 | None = None,
        local_offset: Vec3 | None = None,
    ):
        self.book = book
        self.anchor = anchor
        self.sphere = sphere
        self.base_pos = Vec3(base_pos)
        self.radius = float(radius)
        self.phase = float(phase)
        self.spin = float(spin)
        self.linked = bool(linked)
        self.texture_path = texture_path
        self.texture = texture
        self.halo = halo
        self.role = str(role or "record")
        self.system_id = str(system_id or "")
        self.orbit_parent = orbit_parent
        self.orbit_radius = float(orbit_radius or 0.0)
        self.orbit_speed = float(orbit_speed or 0.0)
        self.orbit_phase = float(orbit_phase or 0.0)
        self.orbit_tilt = Vec3(orbit_tilt or (0, 0, 0))
        self.local_offset = Vec3(local_offset or (0, 0, 0))

    def world_pos(self, render: NodePath) -> Vec3:
        return self.anchor.getPos(render)


class ArchivistMode(DirectObject):
    """The Archivist Pass 07 — planetary story systems.

    The cybernetic 4D archive remains floorless/wall-less/ceilingless and uses
    zero-gravity free-flight.  Major records now read as planet-scale story
    worlds, while related stories orbit them as moons and linked simulations
    appear as more mechanical satellite records.  The result is a readable
    cosmic hierarchy without sacrificing the nested-dimension interface layer.
    """

    MODE_ID = "the_archivist"
    MODE_TITLE = "The Archivist"
    HOST_CONTRACT = "holoverse_dimension_v1"

    def __init__(self, host, *, mode: dict | None = None, entry_path: Path | None = None, label: str = MODE_TITLE):
        DirectObject.__init__(self)
        self.host = host
        self.mode = dict(mode or {})
        self.entry_path = Path(entry_path or (ROOT / "main.py")).resolve()
        self.label = str(label or self.MODE_TITLE)
        self.embedded = bool(hasattr(host, "push_nested_native_entry"))
        self.entered = False
        self.destroyed = False
        self.suspended_nested = False
        self.elapsed = 0.0
        self.preview_accum = 0.0
        self.keys: dict[str, bool] = {}
        self.owned_events: set[str] = set()

        self.root: NodePath | None = None
        self.world_root: NodePath | None = None
        self.player: NodePath | None = None
        self.camera_rig: NodePath | None = None
        self.ui_root: NodePath | None = None
        self.prompt: DirectLabel | None = None
        self.title_label: DirectLabel | None = None
        self.notice: DirectLabel | None = None
        self.mind_caption: DirectLabel | None = None

        self.reader_root: DirectFrame | None = None
        self.reader_book: dict | None = None
        self.reader_pages: list[str] = []
        self.reader_spread = 0
        self.reader_page_labels: list[DirectLabel] = []

        self.interface_root: DirectFrame | None = None
        self.interface_book: dict | None = None
        self.interface_labels: list[DirectLabel] = []

        self.exhibits: list[ArchiveOrbExhibit] = []
        self.system_roots: dict[str, NodePath] = {}
        self.system_books: dict[str, dict] = {}
        self.system_tracks: list[NodePath] = []
        self.primary_sim_gates: list[tuple[NodePath, float]] = []
        self.near_exhibit: ArchiveOrbExhibit | None = None
        self.selection_root: NodePath | None = None
        self.selection_ring: NodePath | None = None
        self._last_near_book_id = ""

        self.reading_db = load_reading_db(os.fspath(READING_PATH))
        self.reality_bleed = False
        self.bleed_book_id = ""
        self.bleed_accent = ARCHIVE_VIOLET

        self.preview_buffer = None
        self.preview_texture = None
        self.preview_scene = None
        self.preview_camera = None
        self.preview_orb = None
        self.preview_card = None
        self.preview_world_root = None

        self.shell_roots: list[NodePath] = []
        self.shell_panels: list[NodePath] = []
        self.shell_memory_cards: list[NodePath] = []
        self.shell_follow_root: NodePath | None = None
        self.shell_follow_pos = Vec3(0, 0, 0)
        self.mind_root: NodePath | None = None
        self.mind_core: NodePath | None = None
        self.mind_rings: list[NodePath] = []
        self.remote_eyes: list[NodePath] = []
        self.walk_markers: list[NodePath] = []
        self.constellation_root: NodePath | None = None
        self.constellation_book_id = ""
        self.constellation_related_ids: set[str] = set()
        self.constellation_accum = 0.0
        self.preview_spires: list[NodePath] = []
        self.cyber_shell_texture = None
        self.cyber_grid_texture = None
        self.soundtrack = None
        self.soundtrack_path: Path | None = None
        self.soundtrack_time = 0.0

        self._render_baseline: set[Any] = set()
        self._aspect_baseline: set[Any] = set()
        self._saved_background = None
        self._saved_camera_parent = None
        self._saved_camera_transform = None
        self._saved_lens = None
        self._saved_cursor_hidden = False
        self._saved_mouse_mode = WindowProperties.M_absolute
        self._lights: list[NodePath] = []
        self._fog = None

        self.yaw = 0.0
        self.pitch = -3.0
        self.mouse_sensitivity = 0.115

        # Pass 06 zero-gravity flight authority.  Movement is deliberately
        # damped rather than fully inertial so the archive remains comfortable
        # to navigate while still feeling weightless.
        self.velocity = Vec3(0, 0, 0)
        self.flight_radius = 78.0
        self.flight_thrust = 14.5
        self.flight_damping = 1.35
        self.flight_max_speed = 10.5
        self.flight_boost_max_speed = 18.0
        self.shell_follow_rate = 0.44

    # ---------- lifecycle ----------
    def enter(self):
        if self.entered or self.destroyed:
            return
        self.entered = True
        self._snapshot_host()
        self._load_cyber_assets()
        self._build_world()
        self._build_player()
        self._build_preview_interface()
        self._build_ui()
        self._bind_input()
        self._set_mouse_capture(True)
        self._start_soundtrack()
        self._set_notice("ARCHIVIST MIND // 55 RECORDS // PLANETARY STORY SYSTEMS ONLINE")

    def _snapshot_host(self):
        try:
            self._render_baseline = {self._node_key(n) for n in self.host.render.getChildren()}
        except Exception:
            self._render_baseline = set()
        try:
            self._aspect_baseline = {self._node_key(n) for n in self.host.aspect2d.getChildren()}
        except Exception:
            self._aspect_baseline = set()
        try:
            self._saved_background = self.host.win.getClearColor()
        except Exception:
            self._saved_background = None
        try:
            self._saved_camera_parent = self.host.camera.getParent()
            self._saved_camera_transform = self.host.camera.getTransform(self.host.render)
        except Exception:
            pass
        try:
            self._saved_lens = (self.host.camLens.getFov(), self.host.camLens.getNear(), self.host.camLens.getFar())
        except Exception:
            self._saved_lens = None
        try:
            props = self.host.win.getProperties()
            self._saved_cursor_hidden = bool(props.getCursorHidden())
            self._saved_mouse_mode = props.getMouseMode()
        except Exception:
            pass

    @staticmethod
    def _node_key(np):
        try:
            return int(np.node().this)
        except Exception:
            return id(np)

    # ---------- cybernetic assets / soundtrack ----------
    def _load_cyber_assets(self):
        def load(name: str):
            path = CYBER_ROOT / name
            if not path.is_file():
                return None
            try:
                return self.host.loader.loadTexture(Filename.fromOsSpecific(os.fspath(path)))
            except Exception:
                return None
        self.cyber_shell_texture = load("archive_shell_cyber.jpg")
        self.cyber_grid_texture = load("interface_grid.png")

    def _start_soundtrack(self):
        path = find_soundtrack()
        if path is None:
            self.soundtrack_path = None
            return
        if self.soundtrack is None or self.soundtrack_path != path:
            try:
                self.soundtrack = self.host.loader.loadMusic(Filename.fromOsSpecific(os.fspath(path)))
                self.soundtrack.setLoop(True)
                self.soundtrack.setVolume(0.68)
                self.soundtrack_path = path
            except Exception:
                self.soundtrack = None
                self.soundtrack_path = None
                return
        try:
            if self.soundtrack_time > 0:
                self.soundtrack.setTime(self.soundtrack_time)
            self.soundtrack.play()
        except Exception:
            pass

    def _pause_soundtrack(self):
        if self.soundtrack is None:
            return
        try:
            self.soundtrack_time = max(0.0, float(self.soundtrack.getTime()))
        except Exception:
            self.soundtrack_time = 0.0
        try:
            self.soundtrack.stop()
        except Exception:
            pass

    def _stop_soundtrack(self):
        if self.soundtrack is not None:
            try:
                self.soundtrack.stop()
            except Exception:
                pass
        self.soundtrack = None
        self.soundtrack_time = 0.0

    # ---------- world ----------
    def _build_world(self):
        self.host.setBackgroundColor(*ARCHIVE_DARK)
        self.root = self.host.render.attachNewNode("archivist_native_root")
        self.world_root = self.root.attachNewNode("archivist_mind_archive")

        self._make_dimensional_shell()
        self._make_walk_markers()
        self._make_story_orbs()
        self._make_archivist_mind()
        self._make_memory_dust()
        self._make_lighting()

        self.constellation_root = self.world_root.attachNewNode("archive_story_constellation")
        self.selection_root = self.world_root.attachNewNode("archive_orb_selection")
        self.selection_ring = make_ring_segments(
            self.selection_root, "selection_ring", radius=1.75, segments=24,
            thickness=0.055, depth=0.055, color=(0.45,0.88,0.95,0.74), transparency=True,
        )
        self.selection_ring.setP(90)
        self.selection_root.hide()

    def _make_dimensional_shell(self):
        # Pass 04 preserves observer-centering while cybernetic exterior skins add
        # inertial lag.  It is still collisionless and never becomes a room.
        # The effect is that the viewer remains inside a higher-dimensional
        # object whose exterior continuously re-centres around their location.
        self.shell_follow_root = self.world_root.attachNewNode("archive_observer_centered_exterior")
        shell_a = self.shell_follow_root.attachNewNode("archive_4d_shell_primary")
        shell_a.setPos(0, 0, 7)
        self._make_hypercube_frame(shell_a, outer=52.0, inner=31.0, color=ARCHIVE_SHELL)
        shell_a.setHpr(12, -9, 6)
        self.shell_roots.append(shell_a)

        # Shell B: three gigantic ribs on different planes.
        shell_b = self.shell_follow_root.attachNewNode("archive_4d_shell_ribs")
        shell_b.setPos(0, 0, 6)
        ring1 = make_ring_segments(shell_b, "shell_rib_xy", 41.0, 44, 0.30, 0.34, ARCHIVE_SHELL_GOLD, True)
        ring2 = make_ring_segments(shell_b, "shell_rib_xz", 46.0, 48, 0.22, 0.26, (0.19,0.39,0.48,0.30), True)
        ring3 = make_ring_segments(shell_b, "shell_rib_diag", 35.0, 40, 0.18, 0.22, (0.34,0.22,0.46,0.30), True)
        ring2.setP(90); ring3.setHpr(33, 58, 17)
        self.shell_roots.append(shell_b)

        # Shell C: broken exterior faces.  Large gaps prevent them reading as a room.
        shell_c = self.shell_follow_root.attachNewNode("archive_4d_shell_faces")
        shell_c.setPos(0,0,5)
        for i in range(22):
            a = math.tau * i / 22.0 + (i % 3) * 0.13
            radius = 43.0 + (i % 5) * 3.2
            z = -4.0 + (i % 7) * 4.0
            pos = Vec3(math.cos(a) * radius, math.sin(a) * radius, z)
            face_root = shell_c.attachNewNode(f"archive_exterior_face_{i:02d}")
            face_root.setPos(pos)
            face_root.lookAt(0,0,4.5)
            face_root.setR((i * 23) % 70 - 35)
            width = 5.5 + (i % 4) * 2.2
            height = 7.0 + (i % 6) * 1.8
            panel = make_box(face_root, "exterior_fragment", (width, 0.18, height), (0,0,0),
                             (0.22+(i%3)*0.018, 0.28+(i%4)*0.015, 0.34+(i%2)*0.025, 0.48),
                             transparency=True, texture=self.cyber_shell_texture)
            panel.setTwoSided(True)
            # An inset seam hints that the visible surface is an object's exterior.
            make_box(face_root, "exterior_seam", (width*0.70, 0.08, 0.09), (0,-0.13,0),
                     (0.20,0.70,0.80,0.56), transparency=True)
            self.shell_panels.append(face_root)
            # Selected records can appear on the *exterior* of the archive.
            # These sparse membranes are hidden until a story is focused, so
            # the shell never reads as a conventional textured wall.
            if i % 3 == 0:
                cm = CardMaker(f"exterior_memory_membrane_{i:02d}")
                cm.setFrame(-width * 0.40, width * 0.40, -height * 0.38, height * 0.38)
                card = face_root.attachNewNode(cm.generate())
                card.setPos(0, -0.14, 0)
                card.setTransparency(TransparencyAttrib.MAlpha)
                card.setTwoSided(True)
                card.setColorScale(1, 1, 1, 0)
                card.hide()
                self.shell_memory_cards.append(card)
        shell_c.setHpr(-8, 13, -4)
        self.shell_roots.append(shell_c)

    def _make_hypercube_frame(self, parent: NodePath, outer: float, inner: float, color):
        def cube_points(size: float):
            h = size * 0.5
            return [Vec3(x*h, y*h, z*h) for z in (-1,1) for y in (-1,1) for x in (-1,1)]

        def edges(points):
            result = []
            for i, a in enumerate(points):
                for j in range(i+1, len(points)):
                    b = points[j]
                    diff = int(abs(a.x-b.x)>1e-5) + int(abs(a.y-b.y)>1e-5) + int(abs(a.z-b.z)>1e-5)
                    if diff == 1:
                        result.append((a,b))
            return result

        outer_pts = cube_points(outer)
        inner_pts = cube_points(inner)
        for idx,(a,b) in enumerate(edges(outer_pts)):
            make_beam_between(parent, f"outer_edge_{idx:02d}", a, b, 0.28, color, True)
        for idx,(a,b) in enumerate(edges(inner_pts)):
            make_beam_between(parent, f"inner_edge_{idx:02d}", a, b, 0.20, (0.24,0.42,0.52,0.33), True)
        for i,(a,b) in enumerate(zip(outer_pts,inner_pts)):
            make_beam_between(parent, f"dimension_connector_{i:02d}", a, b, 0.16, (0.46,0.30,0.56,0.28), True)

    def _make_walk_markers(self):
        # Pass 06 replaces the old horizon-like ground sigils with sparse 3-D
        # navigation filaments.  They provide depth/parallax references in zero
        # gravity without implying a floor, wall or ceiling.
        golden = math.pi * (3.0 - math.sqrt(5.0))
        for i in range(54):
            t = (i + 0.5) / 54.0
            z = (1.0 - 2.0 * t) * 24.0
            a = i * golden + 0.37
            r = 12.0 + (i % 9) * 3.8
            pos = (math.cos(a) * r, math.sin(a) * r, z)
            length = 0.28 + (i % 4) * 0.16
            marker = make_box(
                self.world_root, f"zero_g_memory_filament_{i:02d}",
                (0.035, length, 0.035), pos,
                (0.20 + (i % 3) * 0.04, 0.45, 0.58, 0.20), transparency=True,
            )
            marker.setHpr((i * 47) % 360, ((i * 29) % 110) - 55, ((i * 17) % 90) - 45)
            self.walk_markers.append(marker)

    def _book_accent(self, book: dict):
        key = f"{book.get('id','')} {_safe_title(book)}".lower()
        if "afterlife" in key or "ghost" in key or "sable" in key:
            return ARCHIVE_VIOLET
        if "entropy" in key or "last light" in key or "exodus" in key:
            return (0.20,0.46,0.78,1)
        if "utopia" in key or "matrix" in key or "andrew" in key:
            return ARCHIVE_CYAN
        if "apocalypse" in key or "doomsday" in key or "crimson" in key:
            return (0.84,0.27,0.14,1)
        seed = sum(ord(ch) for ch in str(book.get("id") or "record"))
        palette = [ARCHIVE_GOLD, ARCHIVE_CYAN, ARCHIVE_VIOLET, (0.34,0.64,0.39,1), (0.65,0.36,0.18,1)]
        return palette[seed % len(palette)]

    def _major_system_specs(self):
        # Major archive authorities.  These six records are the large planets;
        # every other record is assigned as a moon or simulation satellite.
        return [
            {"id": "matrixcore", "main_book_id": "continuation_matrixcore", "label": "MatrixCore", "pos": Vec3(0, 31, 7)},
            {"id": "afterlife", "main_book_id": "continuation_afterlife_of_io", "label": "Afterlife of IO", "pos": Vec3(-36, -9, 15)},
            {"id": "entropy", "main_book_id": "continuation_entropy", "label": "Entropy", "pos": Vec3(31, -22, 19)},
            {"id": "utopia", "main_book_id": "continuation_the_restoration_of_utopia", "label": "Utopia", "pos": Vec3(-8, 54, -10)},
            {"id": "apocalypse", "main_book_id": "apocalypse_apocalypse_run", "label": "Apocalypse", "pos": Vec3(43, 18, -19)},
            {"id": "archive", "main_book_id": "archive_what_the_archive_became", "label": "The Archive", "pos": Vec3(-45, 25, 1)},
        ]

    def _system_for_book(self, book: dict) -> str:
        """Assign a story to one major world using existing catalog semantics.

        This is deliberately deterministic rather than a fuzzy text classifier.
        It keeps story relationships stable across launches and future art passes.
        """
        bid = str(book.get("id") or "")
        collection = str(book.get("collection") or "")
        section = str(book.get("archive_section") or "")

        primary = {
            "continuation_matrixcore": "matrixcore",
            "continuation_afterlife_of_io": "afterlife",
            "continuation_entropy": "entropy",
            "continuation_the_restoration_of_utopia": "utopia",
            "apocalypse_apocalypse_run": "apocalypse",
            "archive_what_the_archive_became": "archive",
        }
        if bid in primary:
            return primary[bid]

        if collection == "Mainland Apocalypse Cycle":
            return "apocalypse"

        continuation_map = {
            "continuation_the_continuum": "matrixcore",
            "continuation_beyond_the_last_light": "entropy",
            "continuation_the_last_signal": "entropy",
            "continuation_sables_mission": "afterlife",
            "continuation_io_88_and_the_prototype_realities": "matrixcore",
            "continuation_the_victory_and_reunion": "utopia",
        }
        if bid in continuation_map:
            return continuation_map[bid]
        if collection == "MatrixCore Continuation":
            return "matrixcore"

        if section in ("ARCHIVE ZERO", "I — PUBLIC UTOPIA"):
            return "utopia"
        if section == "II — ANOMALOUS MATERIAL":
            return "archive"
        if section == "III — PERSONHOOD AND REVIEW":
            return "matrixcore"
        if section == "IV — CONTINUITY CASES":
            return "afterlife"
        if section == "V — REMNANTS AND CONTINUITY":
            return "entropy"
        return "archive"

    def _planetary_layout(self, catalog: list[dict]):
        linked_ids = set(load_links())
        specs = self._major_system_specs()
        book_by_id = {str(b.get("id") or ""): b for b in catalog}
        systems: list[dict] = []
        for spec in specs:
            main_book = book_by_id.get(spec["main_book_id"])
            if not main_book:
                continue
            systems.append({"spec": spec, "main": main_book, "stories": [], "sims": []})
        by_id = {str(system["spec"]["id"]): system for system in systems}

        orbit_counts = {sid: 0 for sid in by_id}
        sim_counts = {sid: 0 for sid in by_id}
        primary_ids = {str(system["main"].get("id") or "") for system in systems}
        for book in catalog:
            bid = str(book.get("id") or "")
            if bid in primary_ids:
                continue
            sid = self._system_for_book(book)
            system = by_id.get(sid) or by_id.get("archive")
            if system is None:
                continue
            entry = {"book": book}
            if bid in linked_ids:
                entry["sim_index"] = sim_counts[sid]
                system["sims"].append(entry)
                sim_counts[sid] += 1
            else:
                entry["orbit_index"] = orbit_counts[sid]
                system["stories"].append(entry)
                orbit_counts[sid] += 1
        return systems, linked_ids

    def _story_size(self, book: dict, role: str) -> float:
        # Story text length influences apparent mass without allowing huge outliers.
        try:
            chars = max(0, len(book_text(book)))
        except Exception:
            chars = 0
        if role == "planet":
            return 2.55 + min(0.80, chars / 75000.0)
        if role == "satellite":
            return 0.92 + min(0.18, chars / 50000.0)
        return 0.70 + min(0.42, chars / 32000.0)

    def _make_system_orbit_tracks(self, center: NodePath, exhibits: list[ArchiveOrbExhibit], accent):
        tracks = [ex for ex in exhibits if ex.role in {"moon", "satellite"} and ex.orbit_radius > 0]
        if not tracks:
            return
        lines = LineSegs(f"{center.getName()}_orbital_tracks")
        lines.setThickness(1.0)
        lines.setColor(accent[0], accent[1], accent[2], 0.16)
        seen = set()
        for ex in tracks:
            key = (round(ex.orbit_radius, 1), ex.role)
            if key in seen:
                continue
            seen.add(key)
            tilt_h, tilt_p, tilt_r = map(math.radians, (ex.orbit_tilt.x, ex.orbit_tilt.y, ex.orbit_tilt.z))
            for i in range(65):
                a = math.tau * i / 64.0
                v = Vec3(math.cos(a)*ex.orbit_radius, math.sin(a)*ex.orbit_radius, 0)
                # Lightweight deterministic Euler rotation for the visual track.
                ch,sh=math.cos(tilt_h),math.sin(tilt_h); cp,sp=math.cos(tilt_p),math.sin(tilt_p); cr,sr=math.cos(tilt_r),math.sin(tilt_r)
                x1,y1,z1 = v.x*ch-v.y*sh, v.x*sh+v.y*ch, v.z
                x2,y2,z2 = x1, y1*cp-z1*sp, y1*sp+z1*cp
                x3,y3,z3 = x2*cr+z2*sr, y2, -x2*sr+z2*cr
                if i == 0:
                    lines.moveTo(x3,y3,z3)
                else:
                    lines.drawTo(x3,y3,z3)
        np = center.attachNewNode(lines.create())
        np.setTransparency(TransparencyAttrib.MAlpha)
        self.system_tracks.append(np)

    def _load_book_texture(self, book: dict):
        # Prefer the exact linked simulation icon if it is currently available
        # on the user's machine.  Otherwise use the packaged story-derived orb art.
        path = simulation_art_path(str(book.get("id") or "")) or orb_texture_path(str(book.get("id") or ""))
        if not path:
            return None, None
        try:
            tex = self.host.loader.loadTexture(Filename.fromOsSpecific(os.fspath(path)))
            return tex, path
        except Exception:
            return None, path

    def _make_story_orbs(self):
        catalog = load_catalog()
        systems, linked_ids = self._planetary_layout(catalog)
        index = 0
        for system in systems:
            spec = system["spec"]
            main_book = system["main"]
            system_id = str(spec["id"])
            center = self.world_root.attachNewNode(f"story_system_{system_id}")
            center.setPos(spec["pos"])
            self.system_roots[system_id] = center
            self.system_books[system_id] = main_book
            system_exhibits: list[ArchiveOrbExhibit] = []

            main_linked = str(main_book.get("id") or "") in linked_ids
            accent = self._book_accent(main_book)
            tex, tex_path = self._load_book_texture(main_book)
            anchor = center.attachNewNode(f"story_planet_anchor_{system_id}")
            anchor.setPos(0, 0, 0)
            radius = self._story_size(main_book, "planet") + (0.12 if main_linked else 0.0)
            sphere = make_uv_sphere(anchor, f"story_planet_{system_id}", radius, (0,0,0), (0.95,0.95,0.95,1), segments=28, rings=18, texture=tex)
            if self.cyber_grid_texture is not None:
                skin = make_uv_sphere(anchor, f"story_planet_skin_{system_id}", radius*1.02, (0,0,0),
                                      (0.34+accent[0]*0.40,0.44+accent[1]*0.38,0.50+accent[2]*0.36,0.16),
                                      segments=20, rings=12, texture=self.cyber_grid_texture, transparency=True)
                skin.setTransparency(TransparencyAttrib.MAlpha)
            core = make_uv_sphere(anchor, f"story_planet_core_{system_id}", radius*0.80, (0,0,0),
                                  (accent[0],accent[1],accent[2],0.19), segments=18, rings=11, transparency=True)
            core.setTransparency(TransparencyAttrib.MAlpha)
            halo = make_ring_segments(anchor, f"story_planet_halo_{system_id}", radius*1.55, 28, 0.07, 0.05,
                                      (accent[0],accent[1],accent[2],0.28), True)
            halo.setP(72)
            ex = ArchiveOrbExhibit(main_book, anchor, sphere, spec["pos"], radius,
                                   phase=(index*0.71), spin=3.2 + (index%5)*0.28, linked=main_linked,
                                   texture_path=tex_path, texture=tex, halo=halo, role="planet", system_id=system_id,
                                   orbit_parent=None, local_offset=Vec3(0,0,0))
            self.exhibits.append(ex)
            system_exhibits.append(ex)
            index += 1

            # If the major story itself has a playable simulation, represent that
            # simulation as a separate mechanical satellite orbiting the story planet.
            if main_linked:
                gate_track = center.attachNewNode(f"primary_simulation_gate_track_{system_id}")
                gate_track.setP(28 + (index % 3) * 11)
                gate_track.setH((index * 41) % 360)
                gate_sat = gate_track.attachNewNode(f"primary_simulation_gate_{system_id}")
                gate_sat.setPos(radius * 1.95, 0, 0)
                make_box(gate_sat, "primary_sim_core", (0.24,0.62,0.24), (0,0,0),
                         (accent[0]*0.88+0.08, accent[1]*0.88+0.08, accent[2]*0.88+0.08, 0.96))
                make_ring_segments(gate_sat, "primary_sim_ring", 0.55, 16, 0.04, 0.035,
                                   (accent[0],accent[1],accent[2],0.78), True).setP(90)
                self.primary_sim_gates.append((gate_track, 7.0 + (index % 4) * 1.2))

            # Story moons
            story_count = max(1, len(system["stories"]))
            for entry in system["stories"]:
                book = entry["book"]
                ordinal = int(entry.get("orbit_index", 0))
                tex, tex_path = self._load_book_texture(book)
                linked = str(book.get("id") or "") in linked_ids
                moon_anchor = center.attachNewNode(f"story_moon_anchor_{index:02d}")
                moon_anchor.setPos(0, 0, 0)
                local_phase = math.tau * ordinal / story_count + (ordinal % 3) * 0.27
                orbit_radius = 6.2 + (ordinal % 5) * 1.9 + (ordinal // 5) * 1.1
                moon_radius = self._story_size(book, "moon")
                sphere = make_uv_sphere(moon_anchor, f"story_moon_{index:02d}", moon_radius, (0,0,0), (0.94,0.94,0.94,1),
                                        segments=18, rings=11, texture=tex)
                if self.cyber_grid_texture is not None:
                    skin = make_uv_sphere(moon_anchor, f"story_moon_skin_{index:02d}", moon_radius*1.018, (0,0,0),
                                          (0.34+accent[0]*0.38,0.46+accent[1]*0.36,0.54+accent[2]*0.34,0.15),
                                          segments=16, rings=9, texture=self.cyber_grid_texture, transparency=True)
                    skin.setTransparency(TransparencyAttrib.MAlpha)
                core = make_uv_sphere(moon_anchor, f"story_moon_core_{index:02d}", moon_radius*0.72, (0,0,0),
                                      (accent[0],accent[1],accent[2],0.18), segments=12, rings=8, transparency=True)
                core.setTransparency(TransparencyAttrib.MAlpha)
                moon_halo = make_ring_segments(moon_anchor, f"story_moon_orbit_halo_{index:02d}", moon_radius*1.42, 18, 0.04, 0.035,
                                               (accent[0],accent[1],accent[2],0.18), True)
                moon_halo.setP(90)
                ex = ArchiveOrbExhibit(book, moon_anchor, sphere, spec["pos"], moon_radius,
                                       phase=(index*0.773), spin=4.8 + (index%7)*0.55, linked=linked,
                                       texture_path=tex_path, texture=tex, halo=moon_halo, role="moon", system_id=system_id,
                                       orbit_parent=center, orbit_radius=orbit_radius, orbit_speed=0.16 + (ordinal%4)*0.03,
                                       orbit_phase=local_phase, orbit_tilt=Vec3((ordinal*17)%30 - 15, (ordinal*11)%22 - 11, 0),
                                       local_offset=Vec3(0, 0, ((ordinal%5)-2)*1.25))
                self.exhibits.append(ex)
                system_exhibits.append(ex)
                index += 1

            # Simulation satellites / orbital gates
            sim_count = max(1, len(system["sims"]))
            for entry in system["sims"]:
                book = entry["book"]
                ordinal = int(entry.get("sim_index", 0))
                tex, tex_path = self._load_book_texture(book)
                sat_anchor = center.attachNewNode(f"story_satellite_anchor_{index:02d}")
                sat_anchor.setPos(0, 0, 0)
                local_phase = math.tau * ordinal / sim_count + 0.48
                orbit_radius = 4.8 + ordinal * 1.6
                sat_radius = self._story_size(book, "satellite")
                sphere = make_uv_sphere(sat_anchor, f"story_satellite_{index:02d}", sat_radius, (0,0,0), (0.96,0.96,0.96,1),
                                        segments=20, rings=12, texture=tex)
                if self.cyber_grid_texture is not None:
                    skin = make_uv_sphere(sat_anchor, f"story_satellite_skin_{index:02d}", sat_radius*1.022, (0,0,0),
                                          (0.38+accent[0]*0.44,0.50+accent[1]*0.40,0.58+accent[2]*0.38,0.18),
                                          segments=16, rings=10, texture=self.cyber_grid_texture, transparency=True)
                    skin.setTransparency(TransparencyAttrib.MAlpha)
                core = make_uv_sphere(sat_anchor, f"story_satellite_core_{index:02d}", sat_radius*0.68, (0,0,0),
                                      (accent[0],accent[1],accent[2],0.22), segments=12, rings=8, transparency=True)
                core.setTransparency(TransparencyAttrib.MAlpha)
                halo = make_ring_segments(sat_anchor, f"linked_reality_satellite_halo_{index:02d}", sat_radius*1.60, 22, 0.055, 0.045,
                                          (accent[0],accent[1],accent[2],0.68), True)
                halo.setP(76 + (ordinal%3)*8)
                gate = make_ring_segments(sat_anchor, f"linked_reality_gate_{index:02d}", sat_radius*2.08, 26, 0.06, 0.05,
                                          (0.30+accent[0]*0.46,0.42+accent[1]*0.42,0.56+accent[2]*0.38,0.40), True)
                gate.setHpr((ordinal*41)%360, 90, (ordinal*23)%360)
                ex = ArchiveOrbExhibit(book, sat_anchor, sphere, spec["pos"], sat_radius,
                                       phase=(index*0.773), spin=5.8 + (index%5)*0.65, linked=True,
                                       texture_path=tex_path, texture=tex, halo=halo, role="satellite", system_id=system_id,
                                       orbit_parent=center, orbit_radius=orbit_radius, orbit_speed=0.28 + ordinal*0.03,
                                       orbit_phase=local_phase, orbit_tilt=Vec3((ordinal*23)%44 - 22, 0, (ordinal*31)%36 - 18),
                                       local_offset=Vec3(0, 0, 1.2 + ordinal*0.6))
                self.exhibits.append(ex)
                system_exhibits.append(ex)
                index += 1

            self._make_system_orbit_tracks(center, system_exhibits, accent)

    def _make_archivist_mind(self):
        self.mind_root = self.world_root.attachNewNode("archivist_mind_entity")
        self.mind_root.setPos(0, 7.5, 10.5)
        eye_tex = None
        eye_path = CYBER_ROOT / "archivist_mind_eye_cyber.jpg"
        if not eye_path.is_file():
            eye_path = ORB_ROOT / "_archivist_mind_eye.png"
        try:
            if eye_path.is_file():
                eye_tex = self.host.loader.loadTexture(Filename.fromOsSpecific(os.fspath(eye_path)))
        except Exception:
            eye_tex = None
        self.mind_core = make_uv_sphere(self.mind_root, "archivist_mind_eye", 1.45, (0,0,0), (1,0.86,0.56,1),
                                        segments=30, rings=18, texture=eye_tex)
        for idx,(radius,col,hpr) in enumerate([
            (2.3,(0.75,0.52,0.20,0.74),(0,12,0)),
            (3.1,(0.27,0.68,0.78,0.56),(40,68,10)),
            (4.0,(0.46,0.29,0.67,0.42),(-28,34,52)),
        ]):
            ring = make_ring_segments(self.mind_root, f"archivist_mind_ring_{idx}", radius, 32, 0.10, 0.10, col, True)
            ring.setHpr(*hpr)
            self.mind_rings.append(ring)
        # Cybernetic diagnostic spokes connect the Mind core to its outer ring.
        for i in range(12):
            a = math.tau*i/12.0
            end = Vec3(math.cos(a)*3.65, math.sin(a)*3.65, math.sin(a*2.0)*0.22)
            make_beam_between(self.mind_root, f"mind_data_spoke_{i:02d}", Vec3(0,0,0), end, 0.028,
                              (0.18,0.72,0.82,0.34), True)
        # Four remote observation nodes make the Mind feel distributed rather than embodied.
        for i,a in enumerate((0.35,2.15,3.75,5.40)):
            p = Vec3(math.cos(a)*24, math.sin(a)*24, 8.0 + (i%2)*5)
            node = self.world_root.attachNewNode(f"archivist_remote_eye_{i}")
            node.setPos(p)
            make_uv_sphere(node, "remote_eye_core", 0.48, (0,0,0), (0.70,0.55,0.24,0.78), segments=14, rings=8, transparency=True)
            ring = make_ring_segments(node, "remote_eye_ring", 0.92, 16, 0.05, 0.05, (0.26,0.65,0.76,0.44), True)
            ring.setP(90)
            self.remote_eyes.append(node)

    def _make_memory_dust(self):
        # Sparse opaque glints provide depth cues without introducing a floor or
        # a large transparent particle sheet.  Their positions are deterministic.
        root = self.world_root.attachNewNode("archive_memory_dust")
        for i in range(72):
            a = (i * 2.399963229728653) % math.tau
            r = 5.0 + ((i * 17) % 31) * 0.92
            z = 0.7 + ((i * 13) % 29) * 0.48
            x = math.cos(a) * r
            y = math.sin(a) * r
            col = (0.18, 0.32 + (i % 4) * 0.035, 0.42 + (i % 5) * 0.025, 1)
            make_box(root, f"memory_glint_{i:02d}", (0.035, 0.035, 0.035), (x, y, z), col)

    def _make_lighting(self):
        ambient = AmbientLight("archive_void_ambient"); ambient.setColor((0.19,0.22,0.30,1))
        amb_np = self.root.attachNewNode(ambient); self.root.setLight(amb_np); self._lights.append(amb_np)
        key = DirectionalLight("archive_dimensional_key"); key.setColor((0.30,0.36,0.50,1)); key.setDirection(Vec3(-0.3,-0.6,-1.0))
        key_np = self.root.attachNewNode(key); self.root.setLight(key_np); self._lights.append(key_np)
        for name,pos,col in [
            ("mind_light",(0,7.5,10.5),(0.95,0.62,0.25,1)),
            ("cyan_memory",(-13,-4,5),(0.18,0.55,0.72,1)),
            ("violet_memory",(12,8,6),(0.44,0.25,0.66,1)),
        ]:
            light = PointLight(name); light.setColor(col); light.setAttenuation((1,0.035,0.005))
            np = self.root.attachNewNode(light); np.setPos(*pos); self.root.setLight(np); self._lights.append(np)
        fog = Fog("archive_void_fog"); fog.setColor(0.004, 0.006, 0.012); fog.setExpDensity(0.0065)
        self.root.setFog(fog); self._fog = fog

    # ---------- player / camera ----------
    def _build_player(self):
        self.player = self.host.render.attachNewNode("archivist_observer")
        self.player.setPos(0,-20,0)
        self.camera_rig = self.player.attachNewNode("archivist_first_person_rig")
        self.camera_rig.setZ(1.72)
        self.host.camera.reparentTo(self.camera_rig)
        self.host.camera.setPos(0,0,0)
        self.host.camera.setHpr(0,self.pitch,0)
        try:
            self.host.camLens.setFov(72); self.host.camLens.setNearFar(0.06,1200)
        except Exception:
            pass

    def _set_mouse_capture(self, active: bool):
        try:
            props = WindowProperties()
            props.setCursorHidden(bool(active))
            props.setMouseMode(WindowProperties.M_confined if active else WindowProperties.M_absolute)
            self.host.win.requestProperties(props)
            if active:
                self._recenter_pointer()
        except Exception:
            pass

    def _recenter_pointer(self):
        try:
            props = self.host.win.getProperties()
            cx = max(1, props.getXSize() // 2); cy = max(1, props.getYSize() // 2)
            self.host.win.movePointer(0, cx, cy)
        except Exception:
            pass

    # ---------- render-to-texture observation ----------
    def _build_preview_interface(self):
        try:
            self.preview_buffer = self.host.win.makeTextureBuffer("archivist_orb_observation", 512, 288)
            self.preview_buffer.setSort(-80)
            self.preview_texture = self.preview_buffer.getTexture()
            self.preview_scene = NodePath("archivist_preview_scene")
            self.preview_camera = self.host.makeCamera(self.preview_buffer)
            self.preview_camera.reparentTo(self.preview_scene)
            self.preview_camera.setPos(0,-15,7); self.preview_camera.lookAt(0,0,2)
            lens = PerspectiveLens(); lens.setFov(58); lens.setNearFar(0.1,100); self.preview_camera.node().setLens(lens)
            for i in range(10):
                a = math.tau*i/10.0
                x,y = math.cos(a)*4.2, math.sin(a)*4.2
                spire = make_box(self.preview_scene, f"preview_memory_spire_{i:02d}", (0.32,0.32,1.5+(i%4)*0.7), (x,y,0.75+(i%4)*0.35),
                                 (0.12,0.36+(i%3)*0.09,0.58,1), texture=self.cyber_shell_texture)
                self.preview_spires.append(spire)
            self.preview_orb = make_uv_sphere(self.preview_scene, "preview_story_orb", 1.55, (0,0,3.1), ARCHIVE_VIOLET,
                                              segments=24, rings=14)
            amb = AmbientLight("preview_ambient"); amb.setColor((0.34,0.37,0.50,1))
            self.preview_scene.setLight(self.preview_scene.attachNewNode(amb))
            self.preview_world_root = self.world_root.attachNewNode("archive_world_projection")
            cm = CardMaker("archive_preview_card"); cm.setFrame(-3.6,3.6,-2.05,2.05)
            self.preview_card = self.preview_world_root.attachNewNode(cm.generate())
            self.preview_card.setTexture(self.preview_texture)
            self.preview_card.setTransparency(TransparencyAttrib.MAlpha)
            self.preview_world_root.hide()
        except Exception as exc:
            print(f"archivist_preview_buffer_disabled:{exc.__class__.__name__}:{exc}")
            self.preview_buffer = self.preview_texture = self.preview_scene = self.preview_camera = None
            self.preview_world_root = None

    # ---------- UI ----------
    def _build_ui(self):
        self.ui_root = self.host.aspect2d.attachNewNode("archivist_ui_root")
        self.title_label = DirectLabel(parent=self.ui_root, text="THE ARCHIVIST // PLANETARY STORY SYSTEMS", pos=(-1.27,0,0.92), scale=0.039,
                                       text_align=TextNode.ALeft, frameColor=(0,0,0,0), text_fg=(0.77,0.84,0.87,0.88))
        self.mind_caption = DirectLabel(parent=self.ui_root, text="", pos=(0,0,0.78), scale=0.033,
                                        frameColor=(0,0,0,0), text_fg=(0.90,0.69,0.35,0.92),
                                        text_shadow=(0,0,0,0.85), text_align=TextNode.ACenter)
        self.prompt = DirectLabel(parent=self.ui_root, text="", pos=(0,0,-0.91), scale=0.036, frameColor=(0,0,0,0),
                                  text_fg=(0.90,0.86,0.74,0.96), text_shadow=(0,0,0,0.85), text_align=TextNode.ACenter)
        self.notice = DirectLabel(parent=self.ui_root, text="", pos=(0,0,0.86), scale=0.029, frameColor=(0,0,0,0),
                                  text_fg=(0.60,0.88,0.92,0.93), text_shadow=(0,0,0,0.80), text_align=TextNode.ACenter)

    # ---------- input ----------
    def _bind(self, event: str, fn, args=None):
        self.host.accept(event, fn, args or []); self.owned_events.add(event)

    def _bind_input(self):
        for key in ("w","a","s","d","space","control","lcontrol","rcontrol","shift","lshift","rshift"):
            self._bind(key, self._set_key, [key,True]); self._bind(key+"-up", self._set_key, [key,False])
        self._bind("e", self.interact_read)
        self._bind("r", self.interact_interface)
        self._bind("f", self.toggle_reality_bleed)
        self._bind("escape", self.escape_action)
        self._bind("arrow_left", self.reader_prev)
        self._bind("arrow_right", self.reader_next)
        self._bind("wheel_up", self.reader_prev)
        self._bind("wheel_down", self.reader_next)
        self._bind("enter", self.enter_interface_simulation)
        if not self.embedded:
            self._bind("tab", self._standalone_tab)

    def _unbind_input(self):
        for event in list(self.owned_events):
            try:
                self.host.ignore(event)
            except Exception:
                pass
        self.owned_events.clear(); self.keys.clear()

    def _set_key(self, key, down):
        self.keys[str(key)] = bool(down)

    def _down(self, *keys):
        return any(self.keys.get(k,False) for k in keys)

    # ---------- frame ----------
    def update(self, dt: float):
        if not self.entered or self.destroyed or self.suspended_nested:
            return
        dt = _clamp(float(dt or 0), 0, 0.05)
        self.elapsed += dt
        modal = bool(self.reader_root or self.interface_root)
        if not modal:
            self._update_mouse_look()
            self._update_movement(dt)
            self._update_near_exhibit()
        self._update_orbs(dt)
        self._update_shells(dt)
        self._update_mind(dt)
        self._update_constellation(dt)
        self._update_preview(dt)
        self._update_bleed(dt)

    def _update_mouse_look(self):
        try:
            props = self.host.win.getProperties()
            cx = max(1, props.getXSize() // 2); cy = max(1, props.getYSize() // 2)
            ptr = self.host.win.getPointer(0)
            dx, dy = ptr.getX() - cx, ptr.getY() - cy
            if abs(dx) > 0 or abs(dy) > 0:
                self.yaw -= dx * self.mouse_sensitivity
                self.pitch = _clamp(self.pitch - dy * self.mouse_sensitivity, -88.0, 88.0)
                self.player.setH(self.yaw)
                self.camera_rig.setP(self.pitch)
            self.host.win.movePointer(0, cx, cy)
        except Exception:
            pass

    def _update_movement(self, dt):
        # Damped zero-gravity flight.  Forward/back follows the full camera pitch,
        # strafe follows the camera right vector, and Space/Ctrl provide explicit
        # world-up/world-down thrust.  No position is pinned to a floor plane.
        axis_forward = (1.0 if self._down("w") else 0.0) - (1.0 if self._down("s") else 0.0)
        axis_right = (1.0 if self._down("d") else 0.0) - (1.0 if self._down("a") else 0.0)
        axis_up = (1.0 if self._down("space") else 0.0) - (1.0 if self._down("control","lcontrol","rcontrol") else 0.0)
        try:
            quat = self.camera_rig.getQuat(self.host.render)
            forward = quat.getForward(); right = quat.getRight()
        except Exception:
            h = math.radians(self.yaw); p = math.radians(self.pitch)
            forward = Vec3(-math.sin(h)*math.cos(p), math.cos(h)*math.cos(p), math.sin(p))
            right = Vec3(math.cos(h), math.sin(h), 0)
        if forward.lengthSquared() > 0: forward.normalize()
        if right.lengthSquared() > 0: right.normalize()
        desired = forward*axis_forward + right*axis_right + Vec3(0,0,axis_up)
        if desired.lengthSquared() > 0:
            desired.normalize()
            boost = 1.72 if self._down("shift","lshift","rshift") else 1.0
            self.velocity += desired * (self.flight_thrust * boost * dt)

        # Exponential damping gives a gentle coast while still allowing the
        # observer to stop precisely beside a record orb.
        self.velocity *= math.exp(-self.flight_damping * dt)
        max_speed = self.flight_boost_max_speed if self._down("shift","lshift","rshift") else self.flight_max_speed
        speed = self.velocity.length()
        if speed > max_speed and speed > 0:
            self.velocity *= max_speed / speed

        pos = Vec3(self.player.getPos(self.host.render)) + self.velocity * dt
        dist = pos.length()
        if dist > self.flight_radius:
            inward = Vec3(-pos.x, -pos.y, -pos.z)
            if inward.lengthSquared() > 0:
                inward.normalize()
                excess = dist - self.flight_radius
                self.velocity += inward * (3.4 + excess * 1.35) * dt
                self._set_notice("THE ARCHIVE CURVES ZERO-G SPACE BACK TOWARD ITS OBSERVER")
            # A very generous final containment guard prevents numerical escape
            # without presenting a visible wall.
            if dist > self.flight_radius + 16.0:
                pos.normalize(); pos *= self.flight_radius + 16.0
                self.velocity *= 0.45
        self.player.setPos(self.host.render, pos)

    @staticmethod
    def _rotate_orbit_vector(v: Vec3, hpr: Vec3) -> Vec3:
        h,p,r = map(math.radians, (hpr.x,hpr.y,hpr.z))
        ch,sh=math.cos(h),math.sin(h); cp,sp=math.cos(p),math.sin(p); cr,sr=math.cos(r),math.sin(r)
        x1,y1,z1 = v.x*ch-v.y*sh, v.x*sh+v.y*ch, v.z
        x2,y2,z2 = x1, y1*cp-z1*sp, y1*sp+z1*cp
        return Vec3(x2*cr+z2*sr, y2, -x2*sr+z2*cr)

    def _update_orbs(self, dt):
        for idx,ex in enumerate(self.exhibits):
            # Planets drift subtly in place; moons and simulation satellites orbit
            # their parent story world so the archive reads like a navigable
            # cosmology of related records.
            if ex.orbit_parent is not None and ex.role in {"moon", "satellite"}:
                center = ex.orbit_parent.getPos(self.host.render)
                ang = self.elapsed * ex.orbit_speed + ex.orbit_phase
                eccentricity = 1.0 + math.sin(ang*2.0 + ex.phase) * (0.035 if ex.role == "moon" else 0.018)
                orbit = Vec3(math.cos(ang) * ex.orbit_radius * eccentricity, math.sin(ang) * ex.orbit_radius, 0)
                orbit = self._rotate_orbit_vector(orbit, ex.orbit_tilt) + ex.local_offset
                ex.anchor.setPos(self.host.render, center + orbit)
            else:
                drift_scale = 0.22 if ex.role == "planet" else 0.12
                drift = Vec3(
                    math.sin(self.elapsed*0.13 + ex.phase) * drift_scale,
                    math.cos(self.elapsed*0.11 + ex.phase*1.13) * drift_scale,
                    math.sin(self.elapsed*0.09 + ex.phase*0.83) * (drift_scale*0.75),
                )
                ex.anchor.setPos(ex.base_pos + drift)
            ex.sphere.setH(ex.sphere.getH() + ex.spin*dt)
            ex.sphere.setP(math.sin(self.elapsed*(0.16 if ex.role == "planet" else 0.22) + ex.phase) * (5.0 if ex.role == "planet" else 7.0))
            focused = ex is self.near_exhibit
            related = str(ex.book.get("id") or "") in self.constellation_related_ids
            target_scale = 1.18 if focused and ex.role == "planet" else (1.16 if focused else (1.07 if related else 1.0))
            current = ex.anchor.getSx()
            amount = min(1.0, dt * (4.4 if focused else 2.8))
            ex.anchor.setScale(current + (target_scale-current)*amount)
            if ex.halo is not None:
                base_h = 10.0 if ex.role == "satellite" else 5.5
                ex.halo.setH(ex.halo.getH() + (base_h + (6.0 if focused else 0.0)) * dt)
                ex.halo.setR(ex.halo.getR() + ((8.0 if related else 2.0) + (6.0 if ex.role == "satellite" else 0.0)) * dt)
        for gate_track, speed in self.primary_sim_gates:
            gate_track.setH(gate_track.getH() + speed * dt)

        if self.selection_root and self.near_exhibit:
            p = self.near_exhibit.world_pos(self.host.render)
            self.selection_root.setPos(self.host.render,p)
            scale = 2.25 if self.near_exhibit.role == "planet" else 1.0
            self.selection_root.setScale(scale)
            self.selection_root.setH(self.selection_root.getH() + 18.0*dt)

    def _update_shells(self, dt):
        if self.shell_follow_root is not None and self.player is not None:
            target = Vec3(self.player.getPos(self.host.render))
            blend = 1.0 - math.exp(-self.shell_follow_rate * max(0.0, dt))
            self.shell_follow_pos += (target - self.shell_follow_pos) * blend
            # Tiny phase offsets prevent the exterior from reading as a rigid skybox.
            phase = Vec3(math.sin(self.elapsed*0.11)*0.7, math.cos(self.elapsed*0.09)*0.6, math.sin(self.elapsed*0.07)*0.5)
            self.shell_follow_root.setPos(self.shell_follow_pos + phase)
        if len(self.shell_roots) >= 1:
            self.shell_roots[0].setH(self.shell_roots[0].getH() + 0.42*dt)
            self.shell_roots[0].setP(self.shell_roots[0].getP() + 0.11*dt)
            self.shell_roots[0].setR(self.shell_roots[0].getR() - 0.17*dt)
        if len(self.shell_roots) >= 2:
            self.shell_roots[1].setH(self.shell_roots[1].getH() - 0.25*dt)
            self.shell_roots[1].setR(self.shell_roots[1].getR() + 0.09*dt)
        if len(self.shell_roots) >= 3:
            self.shell_roots[2].setH(self.shell_roots[2].getH() + 0.16*dt)
            self.shell_roots[2].setP(self.shell_roots[2].getP() - 0.07*dt)

    def _update_mind(self, dt):
        if self.mind_root:
            self.mind_root.setZ(10.5 + math.sin(self.elapsed*0.27)*0.45)
            self.mind_root.setH(math.sin(self.elapsed*0.18)*8.0)
        alert = 1.75 if (self.reality_bleed or self.interface_root) else 1.0
        for idx,ring in enumerate(self.mind_rings):
            ring.setH(ring.getH() + (6.0 + idx*2.2)*dt*alert*(1 if idx%2==0 else -1))
        if self.mind_core and self.host.camera:
            try:
                self.mind_core.lookAt(self.host.camera)
                self.mind_core.setH(self.mind_core.getH()+180)
            except Exception:
                pass
        if self.player:
            for eye in self.remote_eyes:
                try: eye.lookAt(self.player)
                except Exception: pass

    def _related_exhibits(self, source: ArchiveOrbExhibit, limit: int = 5) -> list[ArchiveOrbExhibit]:
        book = source.book
        section = str(book.get("archive_section") or "")
        collection = str(book.get("collection") or "")
        scored = []
        for ex in self.exhibits:
            if ex is source:
                continue
            other = ex.book
            score = 0
            if source.system_id and ex.system_id == source.system_id:
                score += 6
                if source.role == "planet":
                    score += 1
            if section and str(other.get("archive_section") or "") == section:
                score += 3
            if collection and str(other.get("collection") or "") == collection:
                score += 2
            if ex.linked and source.linked:
                score += 1
            if source.role == "planet" and ex.role == "satellite":
                score += 2
            if score:
                scored.append((-score, (ex.world_pos(self.world_root)-source.world_pos(self.world_root)).lengthSquared(), ex))
        scored.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in scored[:max(0,int(limit))]]

    def _rebuild_constellation(self):
        if self.constellation_root is None:
            return
        [child.removeNode() for child in self.constellation_root.getChildren()]
        self.constellation_related_ids.clear()
        ex = self.near_exhibit
        if ex is None:
            self.constellation_book_id = ""
            return
        related = self._related_exhibits(ex)
        self.constellation_book_id = str(ex.book.get("id") or "")
        self.constellation_related_ids = {str(r.book.get("id") or "") for r in related}
        if not related:
            return
        accent = self._book_accent(ex.book)
        lines = LineSegs("archive_constellation_lines")
        lines.setThickness(1.4)
        lines.setColor(accent[0], accent[1], accent[2], 0.46)
        origin = ex.world_pos(self.world_root)
        for other in related:
            lines.moveTo(origin)
            lines.drawTo(other.world_pos(self.world_root))
        node = self.constellation_root.attachNewNode(lines.create())
        node.setTransparency(TransparencyAttrib.MAlpha)

    def _update_constellation(self, dt):
        self.constellation_accum += dt
        current = str(self.near_exhibit.book.get("id") or "") if self.near_exhibit else ""
        if current != self.constellation_book_id or self.constellation_accum >= 0.24:
            self.constellation_accum = 0.0
            self._rebuild_constellation()

    def _apply_shell_memory(self, book: dict | None, strength: float = 0.0):
        if not self.shell_memory_cards:
            return
        if not book or strength <= 0:
            for card in self.shell_memory_cards:
                card.hide()
            return
        ex = next((x for x in self.exhibits if str(x.book.get("id") or "") == str(book.get("id") or "")), None)
        tex = ex.texture if ex is not None else None
        if tex is None:
            tex, _ = self._load_book_texture(book)
        if tex is None:
            for card in self.shell_memory_cards: card.hide()
            return
        accent = self._book_accent(book)
        for i,card in enumerate(self.shell_memory_cards):
            card.setTexture(tex, 1)
            card.setColorScale(0.82+accent[0]*0.26, 0.82+accent[1]*0.26, 0.86+accent[2]*0.26, min(0.58, strength*(0.82+(i%3)*0.12)))
            card.show()

    def _refresh_shell_memory_state(self):
        if self.reality_bleed and self.near_exhibit and str(self.near_exhibit.book.get("id") or "") == self.bleed_book_id:
            self._apply_shell_memory(self.near_exhibit.book, 0.46)
        elif self.reality_bleed:
            ex = next((x for x in self.exhibits if str(x.book.get("id") or "") == self.bleed_book_id), None)
            self._apply_shell_memory(ex.book if ex else None, 0.46)
        elif self.interface_book:
            self._apply_shell_memory(self.interface_book, 0.28)
        elif self.near_exhibit:
            self._apply_shell_memory(self.near_exhibit.book, 0.13)
        else:
            self._apply_shell_memory(None, 0)

    def _update_near_exhibit(self):
        p = self.player.getPos(self.host.render)
        best = None; best_d = 999.0
        for ex in self.exhibits:
            ep = ex.world_pos(self.host.render)
            d = max(0.0, (ep - p).length() - ex.radius)
            if d < best_d:
                best,best_d = ex,d
        self.near_exhibit = best if best_d <= 3.0 else None
        if self.selection_root:
            if self.near_exhibit: self.selection_root.show()
            else: self.selection_root.hide()
        if not self.prompt:
            return
        if not self.near_exhibit:
            self.prompt["text"] = "ZERO-G // WASD THRUST // SPACE/CTRL VERTICAL // SHIFT BOOST // APPROACH STORY SYSTEM"
            if self.mind_caption: self.mind_caption["text"] = ""
            if self._last_near_book_id:
                self._last_near_book_id = ""
                self._refresh_shell_memory_state()
            return
        b = self.near_exhibit.book
        book_id = str(b.get("id") or "")
        title = _safe_title(b)
        sim_path, state = resolve_simulation(book_id)
        sim_tag = "LINKED REALITY" if sim_path else ("ARCHIVE ECHO" if book_id == "archive_the_empty_field" else state)
        role_map = {"planet": "PRIMARY WORLD", "moon": "SIDE STORY", "satellite": "SIMULATION SATELLITE"}
        role_tag = role_map.get(getattr(self.near_exhibit, "role", "record"), "ARCHIVE RECORD")
        self.prompt["text"] = f"{title.upper()}  //  {role_tag}  //  E READ  //  R OBSERVE  //  F BLEED  //  {sim_tag}"
        if book_id != self._last_near_book_id:
            self._last_near_book_id = book_id
            self._refresh_shell_memory_state()
            if self.mind_caption:
                collection = str(b.get("collection") or "ARCHIVE RECORD").upper()
                system_book = self.system_books.get(getattr(self.near_exhibit, "system_id", ""), {})
                system_name = (_safe_title(system_book).upper() if system_book else collection)
                self.mind_caption["text"] = f"ARCHIVIST // RECORD RECOGNIZED // {system_name} SYSTEM // CONSTELLATION INDEXED"

    def _update_preview(self, dt):
        if self.preview_orb is None:
            return
        self.preview_accum += dt
        if self.preview_accum < 1.0/12.0:
            return
        step = self.preview_accum; self.preview_accum = 0.0
        self.preview_orb.setH(self.preview_orb.getH() + 22.0*step)
        self.preview_orb.setZ(3.1 + math.sin(self.elapsed*1.1)*0.55)
        if self.preview_world_root and not self.preview_world_root.isHidden():
            try:
                # Keep the floating interface facing the current observer.
                self.preview_world_root.lookAt(self.host.camera)
                self.preview_world_root.setH(self.preview_world_root.getH()+180)
            except Exception:
                pass

    def _update_bleed(self, dt):
        if not self.reality_bleed:
            return
        wave = 0.5 + 0.5*math.sin(self.elapsed*0.7)
        c = self.bleed_accent
        self.host.setBackgroundColor(0.003+c[0]*0.018*wave, 0.004+c[1]*0.018*wave, 0.008+c[2]*0.026*wave, 1)
        if self._fog:
            self._fog.setExpDensity(0.0045 + wave*0.004)
        for i,root in enumerate(self.shell_roots):
            amount = 0.62 + wave*(0.12+i*0.025)
            root.setColorScale(0.70+c[0]*amount, 0.70+c[1]*amount, 0.78+c[2]*amount, 1)

    # ---------- book reader ----------
    def interact_read(self):
        if self.interface_root:
            return False
        if self.reader_root:
            return True
        if not self.near_exhibit:
            return False
        self.open_reader(self.near_exhibit.book)
        return True

    def _paginate(self, text: str, chars=56, lines=23) -> list[str]:
        wrapped: list[str] = []
        for para in text.replace("\r","").split("\n"):
            if not para.strip():
                wrapped.append(""); continue
            wrapped.extend(textwrap.wrap(para.strip(), width=chars, replace_whitespace=True, drop_whitespace=True) or [""])
        pages = []
        for start in range(0,max(1,len(wrapped)),lines):
            pages.append("\n".join(wrapped[start:start+lines]))
        return pages or [""]

    def open_reader(self, book: dict):
        self.velocity = Vec3(0,0,0)
        self.reader_book = book; self.reader_pages = self._paginate(book_text(book))
        self.reader_spread = resume_spread(self.reading_db, str(book.get("id")), len(self.reader_pages))
        note_open(self.reading_db, str(book.get("id")), len(self.reader_pages), self.reader_spread); self._save_reading()
        self.reader_root = DirectFrame(parent=self.host.aspect2d, frameColor=(0.018,0.020,0.026,0.985), frameSize=(-1.42,1.42,-0.94,0.94))
        DirectLabel(parent=self.reader_root, text=_safe_title(book).upper(), pos=(0,0,0.82), scale=0.055,
                    frameColor=(0,0,0,0), text_fg=(0.88,0.80,0.62,1), text_align=TextNode.ACenter)
        DirectLabel(parent=self.reader_root, text="LEFT/RIGHT OR WHEEL TURN PAGES  //  ESC CLOSE", pos=(0,0,-0.86), scale=0.032,
                    frameColor=(0,0,0,0), text_fg=(0.60,0.66,0.70,1), text_align=TextNode.ACenter)
        self.reader_page_labels = [
            DirectLabel(parent=self.reader_root, text="", pos=(-0.68,0,0.60), scale=0.032, text_align=TextNode.ALeft,
                        frameColor=(0,0,0,0), text_fg=(0.88,0.86,0.80,1), text_wordwrap=38),
            DirectLabel(parent=self.reader_root, text="", pos=(0.08,0,0.60), scale=0.032, text_align=TextNode.ALeft,
                        frameColor=(0,0,0,0), text_fg=(0.88,0.86,0.80,1), text_wordwrap=38),
        ]
        self._refresh_reader(); self._set_mouse_capture(False)

    def _refresh_reader(self):
        if not self.reader_root or not self.reader_book:
            return
        left=self.reader_spread; right=left+1
        self.reader_page_labels[0]["text"] = self.reader_pages[left] if left < len(self.reader_pages) else ""
        self.reader_page_labels[1]["text"] = self.reader_pages[right] if right < len(self.reader_pages) else ""
        note_position(self.reading_db, str(self.reader_book.get("id")), len(self.reader_pages), self.reader_spread); self._save_reading()

    def reader_prev(self):
        if not self.reader_root: return False
        self.reader_spread=max(0,self.reader_spread-2); self._refresh_reader(); return True

    def reader_next(self):
        if not self.reader_root: return False
        max_spread=max(0,((len(self.reader_pages)-1)//2)*2)
        self.reader_spread=min(max_spread,self.reader_spread+2); self._refresh_reader(); return True

    def _close_reader(self):
        if not self.reader_root:
            return
        self._save_reading()
        try: self.reader_root.destroy()
        except Exception: pass
        self.reader_root=None; self.reader_book=None; self.reader_pages=[]; self.reader_page_labels=[]
        self._set_mouse_capture(True)

    def _save_reading(self):
        try: save_reading_db(os.fspath(READING_PATH), self.reading_db)
        except Exception: pass

    # ---------- reality interface ----------
    def interact_interface(self):
        if self.reader_root:
            return False
        if self.interface_root:
            return True
        if not self.near_exhibit:
            return False
        self.open_interface(self.near_exhibit.book)
        return True

    def _preview_selected_book(self, book: dict):
        accent = self._book_accent(book)
        seed = sum((i+1)*ord(ch) for i,ch in enumerate(str(book.get("id") or "record")))
        for i,spire in enumerate(self.preview_spires):
            spire.setSz(0.65 + ((seed >> (i % 11)) & 7) * 0.11)
            spire.setColorScale(0.45+accent[0]*0.75, 0.45+accent[1]*0.75, 0.50+accent[2]*0.75, 1)
        if self.preview_world_root and self.near_exhibit:
            p = self.near_exhibit.world_pos(self.host.render)
            # Float the projection slightly above and to one side of its source orb.
            self.preview_world_root.setPos(self.host.render, p + Vec3(3.4,0,2.0))
            self.preview_world_root.show()
        if self.preview_orb is not None:
            tex, _ = self._load_book_texture(book)
            if tex is not None:
                self.preview_orb.setTexture(tex,1)
            accent = self._book_accent(book)
            self.preview_orb.setColorScale(accent[0]*1.15,accent[1]*1.15,accent[2]*1.15,1)

    def open_interface(self, book: dict):
        self.velocity = Vec3(0,0,0)
        self.interface_book = book
        path,state = resolve_simulation(str(book.get("id") or ""))
        self._preview_selected_book(book)
        self._apply_shell_memory(book, 0.28)
        self.interface_root = DirectFrame(parent=self.host.aspect2d, frameColor=(0.010,0.020,0.030,0.94), frameSize=(-0.76,0.76,-0.76,0.76), pos=(0.56,0,0.02))
        if self.cyber_grid_texture is not None:
            try: self.interface_root.setTexture(self.cyber_grid_texture, 1)
            except Exception: pass
        self.interface_labels = [
            DirectLabel(parent=self.interface_root, text="ORB REALITY INTERFACE", pos=(0,0,0.64), scale=0.047, frameColor=(0,0,0,0), text_fg=(0.42,0.84,0.90,1)),
            DirectLabel(parent=self.interface_root, text=_safe_title(book).upper(), pos=(0,0,0.51), scale=0.038, frameColor=(0,0,0,0), text_fg=(0.90,0.84,0.66,1)),
            DirectLabel(parent=self.interface_root, text=f"SOURCE // {state}", pos=(0,0,0.35), scale=0.031, frameColor=(0,0,0,0), text_fg=(0.70,0.74,0.78,1)),
            DirectLabel(parent=self.interface_root, text=(str(path) if path else "NO EXTERNAL SOURCE CURRENTLY RESOLVED")[-80:], pos=(0,0,0.23), scale=0.022,
                        text_wordwrap=48, frameColor=(0,0,0,0), text_fg=(0.55,0.62,0.66,1)),
            DirectLabel(parent=self.interface_root, text="A live projection has unfolded beside the record orb.\nENTER attempts the nested native reality.\nESC folds the interface back into the orb.",
                        pos=(0,0,-0.02), scale=0.030, text_wordwrap=42, frameColor=(0,0,0,0), text_fg=(0.75,0.82,0.84,1)),
        ]
        DirectButton(parent=self.interface_root, text="ENTER SIMULATION", pos=(0,0,-0.38), scale=0.045,
                     frameColor=(0.10,0.20,0.23,0.95), text_fg=(0.86,0.94,0.95,1), command=self.enter_interface_simulation)
        DirectButton(parent=self.interface_root, text="CLOSE", pos=(0,0,-0.57), scale=0.040,
                     frameColor=(0.09,0.10,0.12,0.95), text_fg=(0.78,0.80,0.82,1), command=self._close_interface)
        self._set_mouse_capture(False)

    def enter_interface_simulation(self):
        if not self.interface_root or not self.interface_book:
            return False
        book=self.interface_book
        fallback=INTERNAL_ECHO_ENTRY if str(book.get("id")) == "archive_the_empty_field" else None
        ok,message=enter_simulation(self.host,book,fallback_internal=fallback)
        self._set_notice(message)
        return ok

    def _close_interface(self):
        if not self.interface_root:
            return
        try: self.interface_root.destroy()
        except Exception: pass
        self.interface_root=None; self.interface_book=None; self.interface_labels=[]
        if self.preview_world_root: self.preview_world_root.hide()
        self._refresh_shell_memory_state()
        self._set_mouse_capture(True)

    def toggle_reality_bleed(self):
        if not self.near_exhibit and not self.reality_bleed:
            return False
        if self.reality_bleed:
            self.reality_bleed=False; self.bleed_book_id=""; self.host.setBackgroundColor(*ARCHIVE_DARK)
            if self._fog: self._fog.setExpDensity(0.0065)
            for root in self.shell_roots: root.clearColorScale()
            self._refresh_shell_memory_state()
            self._set_notice("REALITY BLEED CONTAINED")
            if self.mind_caption: self.mind_caption["text"] = "ARCHIVIST // BOUNDARY RESTORED"
            return True
        self.reality_bleed=True
        self.bleed_book_id=str(self.near_exhibit.book.get("id") or "")
        self.bleed_accent=self._book_accent(self.near_exhibit.book)
        self._apply_shell_memory(self.near_exhibit.book, 0.46)
        self._set_notice(f"REALITY BLEED // {_safe_title(self.near_exhibit.book).upper()}")
        if self.mind_caption: self.mind_caption["text"] = "ARCHIVIST // RECORD MEMBRANE OPEN"
        return True

    def escape_action(self):
        if self.reader_root:
            self._close_reader(); return True
        if self.interface_root:
            self._close_interface(); return True
        self._set_notice("TAB RETURNS ONE DIMENSION" if self.embedded else "ESC CLOSES ACTIVE INTERFACES")
        return False

    def _set_notice(self,text):
        if self.notice:
            self.notice["text"] = str(text or "")[:180]

    # ---------- nested lifecycle ----------
    def suspend_for_nested(self, child_label: str = ""):
        if self.suspended_nested:
            return
        self.suspended_nested=True
        self.velocity = Vec3(0,0,0)
        self._pause_soundtrack()
        self._close_reader(); self._close_interface(); self._unbind_input(); self._set_mouse_capture(False)
        if self.root: self.root.stash()
        if self.ui_root: self.ui_root.hide()

    def resume_from_nested(self, child_label: str = "", result: dict | None = None):
        if not self.suspended_nested:
            return
        self.suspended_nested=False
        if self.root: self.root.unstash()
        if self.ui_root: self.ui_root.show()
        try:
            self.host.camera.reparentTo(self.camera_rig)
            self.host.camera.setPos(0,0,0)
            self.camera_rig.setP(self.pitch)
            self.player.setH(self.yaw)
        except Exception:
            pass
        self._bind_input(); self._set_mouse_capture(True)
        self._start_soundtrack()
        msg=f"RETURNED FROM {str(child_label or 'SIMULATION').upper()}"
        if isinstance(result,dict) and result.get("signal"):
            msg += f" // {result.get('signal')}"
        self._set_notice(msg)
        if self.mind_caption: self.mind_caption["text"] = "ARCHIVIST // NESTED RECORD CLOSED"

    def _standalone_tab(self):
        self._set_notice("STANDALONE MIND ARCHIVE // TAB RETURN IS PROVIDED BY HOLOVERSE")
        return True

    # ---------- host result + teardown ----------
    def get_holoverse_result(self) -> dict[str,Any]:
        return {"dimension": self.MODE_ID, "completed": False, "signal": "mind_archive_online", "records": len(self.exhibits)}

    def exit(self):
        self.destroy()

    def destroy(self):
        if self.destroyed:
            return
        self.destroyed=True
        self._stop_soundtrack()
        self._save_reading(); self._unbind_input(); self._close_reader(); self._close_interface()
        try:
            if self.preview_buffer is not None: self.host.graphicsEngine.removeWindow(self.preview_buffer)
        except Exception: pass
        try:
            if self.preview_scene is not None: self.preview_scene.removeNode()
        except Exception: pass
        try:
            self.host.camera.reparentTo(self.host.render)
            if self._saved_camera_transform is not None:
                self.host.camera.setTransform(self.host.render,self._saved_camera_transform)
        except Exception: pass
        if self._saved_lens:
            try:
                fov,near,far=self._saved_lens; self.host.camLens.setFov(fov); self.host.camLens.setNearFar(near,far)
            except Exception: pass
        for widget in (self.prompt,self.title_label,self.notice,self.mind_caption):
            try:
                if widget: widget.destroy()
            except Exception: pass
        try:
            if self.ui_root: self.ui_root.removeNode()
        except Exception: pass
        try:
            if self.root: self.root.removeNode()
        except Exception: pass
        try:
            if self.player: self.player.removeNode()
        except Exception: pass
        try:
            props=WindowProperties(); props.setCursorHidden(self._saved_cursor_hidden); props.setMouseMode(self._saved_mouse_mode)
            self.host.win.requestProperties(props)
        except Exception: pass
        try:
            if self._saved_background is not None: self.host.win.setClearColor(self._saved_background)
        except Exception: pass


def create_mode(host_app, *, mode: dict | None = None, entry_path: Path | None = None, label: str = ArchivistMode.MODE_TITLE):
    return ArchivistMode(host_app, mode=mode, entry_path=entry_path, label=label)
