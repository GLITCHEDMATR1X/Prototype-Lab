"""HoloCore strata: the open column above the seabed (Pass HC-1).

HoloCore is an ocean without water.  The neon seabed grid is the floor and
there is no surface above it: the column goes up forever, split into altitude
bands ("strata") read from ``assets/strata/strata.json``.

Per band:
    * atmosphere: background and fog colour (near-identical, so the column
      has no horizon line); the seabed band keeps HoloCore's original values
      exactly; colours and fog density blend across band floors
    * marine snow: world-fixed drifting specks around the camera (tinted per
      band) that make height and motion readable in empty space
    * life: jellyfish, mermaids and octopuses drifting free in the column,
      streamed in 3D cells around the camera with stable seeds
    * drop-in floating assets: ``assets/strata/<asset_folder>/*.py``

Drop-in floating asset format (mirrors the seabed's surface objects)::

    STRATA_OBJECT = {"id": "...", "weight": 1.0, "per_cell": 0.6}
    def build(parent, x, y, z, rng, metadata) -> NodePath | None
    def update(node, time_value) -> None        # optional

``metadata`` carries ``band_id``, ``band_name``, ``accent`` and ``cell``.

The seabed band keeps the existing chunk-owned, surface-locked creatures and
surface flora; nothing here changes them.  The whole system lives under the
outer world's root, so HoloVerse's native mount cleans it up with the rest of
HoloCore (the band title, on aspect2d, is removed by :meth:`destroy`).
"""
from __future__ import annotations

import importlib.util
import json
import math
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from types import ModuleType

from panda3d.core import (
    AntialiasAttrib,
    ColorBlendAttrib,
    Geom,
    GeomNode,
    GeomPoints,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LineSegs,
    NodePath,
    TextNode,
    TransparencyAttrib,
    Vec3,
)

try:
    from holocore_line_kit import line_scale
except Exception:  # pragma: no cover
    def line_scale() -> float:
        return 1.0

try:
    from holo_jellyfish import HoloJellyfishMob, JELLYFISH_VARIANTS
except Exception:  # pragma: no cover
    HoloJellyfishMob = None
    JELLYFISH_VARIANTS = ()
try:
    from holo_mermaid import HoloMermaidMob
except Exception:  # pragma: no cover
    HoloMermaidMob = None
try:
    from holo_octopus import HoloOctopusMob
except Exception:  # pragma: no cover
    HoloOctopusMob = None


BAND_BLEND = 120.0              # metres either side of a band floor that blend
LIFE_FADE_FULL = 560.0          # free-drifting life is fully visible inside this
LIFE_FADE_END = 860.0           # ... and hidden beyond this (3D distance)
LIFE_UPDATE_INTERVAL = 1.0 / 24.0
LIFE_LIVE_RANGE = 240.0         # creatures animate inside this; beyond it a flattened stand-in drifts
LIFE_CELL_RADIUS = 1            # horizontal cells either side of the camera cell
LIFE_DECKS_BELOW = 1
LIFE_DECKS_ABOVE = 2
LIFE_BUILDS_PER_FRAME = 1
SNOW_TILE = 120.0               # marine snow tile edge (metres)
SNOW_POINTS_PER_TILE = 70
SNOW_RISE_SPEED = 0.55          # specks drift slowly upward (m/s)
BOUNDARY_RADIUS = 900.0
BOUNDARY_VISIBLE = 110.0        # a band floor ring shows only within this of the camera
TITLE_HOLD = 2.6
TITLE_FADE = 0.6
MAX_LIFE_PER_CELL = 6


@dataclass(frozen=True)
class StratumBand:
    band_id: str
    name: str
    floor: float
    background: tuple[float, float, float]
    fog_density: float
    snow_color: tuple[float, float, float]
    snow_alpha: float
    accent: tuple[float, float, float]
    creatures: dict
    asset_folder: str
    fog_color: tuple[float, float, float] | None = None   # defaults to background

    @property
    def fog_rgb(self) -> tuple[float, float, float]:
        return self.fog_color if self.fog_color is not None else self.background


@dataclass(frozen=True)
class StrataAsset:
    asset_id: str
    weight: float
    per_cell: float
    module: ModuleType

    def build(self, parent: NodePath, x: float, y: float, z: float, rng: Random, metadata: dict):
        fn = getattr(self.module, "build", None)
        return fn(parent, x, y, z, rng, metadata) if callable(fn) else None

    def update(self, node: NodePath, time_value: float) -> None:
        fn = getattr(self.module, "update", None)
        if callable(fn):
            fn(node, time_value)


DEFAULT_BANDS = (
    # Exactly HoloCore's original seabed: clear colour 0.0025 blue, fog 0.004 blue at 0.0022.
    StratumBand("seabed", "Seabed Grid", -1.0e5, (0.0, 0.0, 0.0025), 0.0022, (0.55, 0.92, 1.0), 0.0, (0.10, 0.92, 1.0), {}, "", (0.0, 0.0, 0.004)),
)


def _vec3(value, fallback) -> tuple[float, float, float]:
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return tuple(fallback)


def load_bands(path: Path) -> tuple[list[StratumBand], dict]:
    """Read strata.json; fall back to the seabed band alone if it is missing or broken."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"holocore_strata_config_fallback path={path} err={exc.__class__.__name__}:{exc}")
        return list(DEFAULT_BANDS), {}
    bands: list[StratumBand] = []
    for raw in data.get("bands", []) or []:
        try:
            bands.append(StratumBand(
                band_id=str(raw["id"]),
                name=str(raw.get("name") or raw["id"]),
                floor=float(raw.get("floor", 0.0)),
                background=_vec3(raw.get("background"), (0.0, 0.0, 0.004)),
                fog_density=max(0.0, float(raw.get("fog_density", 0.0022))),
                snow_color=_vec3(raw.get("snow_color"), (0.6, 0.9, 1.0)),
                snow_alpha=max(0.0, min(1.0, float(raw.get("snow_alpha", 0.5)))),
                accent=_vec3(raw.get("accent"), (0.2, 0.9, 1.0)),
                creatures={str(k): max(0.0, float(v)) for k, v in dict(raw.get("creatures") or {}).items()},
                asset_folder=str(raw.get("asset_folder") or ""),
                fog_color=_vec3(raw["fog_color"], (0.0, 0.0, 0.004)) if raw.get("fog_color") is not None else None,
            ))
        except Exception as exc:
            print(f"holocore_strata_band_skipped raw={raw!r} err={exc.__class__.__name__}:{exc}")
    bands.sort(key=lambda b: b.floor)
    if not bands:
        bands = list(DEFAULT_BANDS)
    return bands, data


def _lerp3(a, b, t: float) -> tuple[float, float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


@dataclass
class Drifter:
    """One free-drifting creature or floating asset in a life cell."""

    kind: str
    node_root: NodePath
    anchor: Vec3
    orbit_radius: float
    orbit_speed: float
    bob: float
    phase: float
    mob: object | None = None
    asset: StrataAsset | None = None
    visible_alpha: float = -1.0
    proxy: NodePath | None = None   # flattened far-range stand-in for a creature
    showing: str = ""               # "", "live" or "proxy"


@dataclass
class LifeCell:
    key: tuple[int, int, int]
    band_id: str
    root: NodePath
    drifters: list[Drifter] = field(default_factory=list)


class HoloCoreStrata:
    """Upward strata for HoloCore's open column (see module docstring)."""

    def __init__(self, app, assets_root: Path, parent: NodePath) -> None:
        self.app = app
        self.render = app.render
        self.assets_root = Path(assets_root)
        self.config_path = self.assets_root / "strata" / "strata.json"
        self.bands, self.config = load_bands(self.config_path)
        self.cell_size = float(self.config.get("life_cell_size", 600.0) or 600.0)
        self.deck_height = float(self.config.get("life_deck_height", 260.0) or 260.0)
        self.root = parent.attachNewNode("holocore_strata_root")
        self.life_root = self.root.attachNewNode("holocore_strata_life")
        self.assets: dict[str, list[StrataAsset]] = {b.band_id: self._load_assets(b.asset_folder) for b in self.bands}
        self.cells: dict[tuple[int, int, int], LifeCell] = {}
        self.build_queue: list[tuple[int, int, int]] = []
        self.desired: set[tuple[int, int, int]] = set()
        self.last_centre: tuple[int, int, int] | None = None
        self.current_band_id: str | None = None
        self.band_changes = 0
        self.atmosphere = {}
        self._life_elapsed = 0.0
        self._time = 0.0
        self._title = None
        self._title_age = 999.0
        self.title_alpha = 0.0
        self._snow_offset = 0.0
        self._build_snow()
        self._build_boundaries()

    # ------------------------------------------------------------------
    # Bands
    # ------------------------------------------------------------------
    def band_index_at(self, z: float) -> int:
        idx = 0
        for i, band in enumerate(self.bands):
            if float(z) >= band.floor:
                idx = i
        return idx

    def band_at(self, z: float) -> StratumBand:
        return self.bands[self.band_index_at(z)]

    def blended_atmosphere(self, z: float) -> dict:
        """Background/fog colour, fog density and snow tint at altitude z."""
        idx = self.band_index_at(z)
        band = self.bands[idx]
        background = band.background
        fog_rgb = band.fog_rgb
        density = band.fog_density
        snow = band.snow_color
        snow_alpha = band.snow_alpha
        # Blend into the band below near this band's floor, and into the band
        # above near the next floor, so crossing a floor never pops.
        if idx > 0 and z < band.floor + BAND_BLEND:
            below = self.bands[idx - 1]
            t = _smooth(0.5 + (z - band.floor) / (2.0 * BAND_BLEND))
            background = _lerp3(below.background, band.background, t)
            fog_rgb = _lerp3(below.fog_rgb, band.fog_rgb, t)
            density = below.fog_density + (band.fog_density - below.fog_density) * t
            snow = _lerp3(below.snow_color, band.snow_color, t)
            snow_alpha = below.snow_alpha + (band.snow_alpha - below.snow_alpha) * t
        elif idx + 1 < len(self.bands) and z > self.bands[idx + 1].floor - BAND_BLEND:
            above = self.bands[idx + 1]
            t = _smooth(0.5 - (above.floor - z) / (2.0 * BAND_BLEND))
            background = _lerp3(band.background, above.background, t)
            fog_rgb = _lerp3(band.fog_rgb, above.fog_rgb, t)
            density = band.fog_density + (above.fog_density - band.fog_density) * t
            snow = _lerp3(band.snow_color, above.snow_color, t)
            snow_alpha = band.snow_alpha + (above.snow_alpha - band.snow_alpha) * t
        return {"band": band, "background": background, "fog_color": fog_rgb, "fog_density": density, "snow": snow, "snow_alpha": snow_alpha}

    def _apply_atmosphere(self, z: float) -> None:
        atmo = self.blended_atmosphere(z)
        bg = atmo["background"]
        prev = self.atmosphere
        changed = (not prev or max(abs(prev["background"][i] - bg[i]) for i in range(3)) > 1.0e-4
                   or abs(prev["fog_density"] - atmo["fog_density"]) > 1.0e-6)
        if changed:
            try:
                self.app.setBackgroundColor(bg[0], bg[1], bg[2], 1.0)
            except Exception:
                pass
            try:
                fog = self.render.getFog() if self.render.hasFog() else None
                if fog is not None:
                    fc = atmo["fog_color"]
                    fog.setColor(fc[0], fc[1], fc[2])
                    fog.setExpDensity(float(atmo["fog_density"]))
            except Exception:
                pass
        if self.snow_root is not None:
            s = atmo["snow"]
            alpha = float(atmo["snow_alpha"])
            if alpha <= 0.002:
                if not self.snow_root.isHidden():
                    self.snow_root.hide()      # the seabed itself stays as it always was
            else:
                if self.snow_root.isHidden():
                    self.snow_root.show()
                self.snow_root.setColorScale(s[0], s[1], s[2], alpha)
        self.atmosphere = atmo

    # ------------------------------------------------------------------
    # Marine snow: 3x3x3 world-fixed tiles of one shared point cloud
    # ------------------------------------------------------------------
    def _build_snow(self) -> None:
        rng = Random(0x5A0C0E)
        vdata = GeomVertexData("holocore_marine_snow", GeomVertexFormat.getV3c4(), Geom.UHStatic)
        vdata.setNumRows(SNOW_POINTS_PER_TILE)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")
        points = GeomPoints(Geom.UHStatic)
        for i in range(SNOW_POINTS_PER_TILE):
            vw.addData3f(rng.uniform(0.0, SNOW_TILE), rng.uniform(0.0, SNOW_TILE), rng.uniform(0.0, SNOW_TILE))
            bright = rng.uniform(0.55, 1.0)
            cw.addData4f(bright, bright, bright, rng.uniform(0.35, 1.0))
            points.addVertex(i)
        points.closePrimitive()
        geom = Geom(vdata)
        geom.addPrimitive(points)
        node = GeomNode("holocore_marine_snow_tile")
        node.addGeom(geom)
        self.snow_tile = NodePath(node)
        self.snow_root = self.root.attachNewNode("holocore_marine_snow")
        self.snow_root.setLightOff()
        self.snow_root.setTransparency(TransparencyAttrib.MAlpha)
        self.snow_root.setDepthWrite(False)
        self.snow_root.setBin("transparent", 2)
        self.snow_root.setRenderModeThickness(2.4 * line_scale())
        # Square specks: smoothed points are slow or unsupported on some drivers.
        self.snow_root.setAntialias(AntialiasAttrib.MNone)
        self.snow_root.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        self.snow_tiles: list[NodePath] = []
        for _ in range(27):
            holder = self.snow_root.attachNewNode("holocore_marine_snow_slot")
            self.snow_tile.instanceTo(holder)
            self.snow_tiles.append(holder)

    def _place_snow(self, cam: Vec3, dt: float) -> None:
        self._snow_offset = (self._snow_offset + SNOW_RISE_SPEED * dt) % SNOW_TILE
        bx = math.floor(cam.x / SNOW_TILE)
        by = math.floor(cam.y / SNOW_TILE)
        bz = math.floor((cam.z - self._snow_offset) / SNOW_TILE)
        i = 0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    self.snow_tiles[i].setPos((bx + dx) * SNOW_TILE, (by + dy) * SNOW_TILE, (bz + dz) * SNOW_TILE + self._snow_offset)
                    i += 1

    # ------------------------------------------------------------------
    # Band floor rings (a faint "thermocline" so the floors read in the void)
    # ------------------------------------------------------------------
    def _build_boundaries(self) -> None:
        self.boundaries: list[tuple[StratumBand, NodePath]] = []
        for band in self.bands[1:]:
            ls = LineSegs(f"holocore_stratum_floor_{band.band_id}")
            ls.setThickness(1.3 * line_scale())
            r, g, b = band.accent
            for ring_r, alpha in ((BOUNDARY_RADIUS, 0.20), (BOUNDARY_RADIUS * 0.62, 0.15), (BOUNDARY_RADIUS * 0.30, 0.12)):
                ls.setColor(r, g, b, alpha)
                for k in range(97):
                    a = math.tau * k / 96.0
                    p = (math.cos(a) * ring_r, math.sin(a) * ring_r, 0.0)
                    (ls.moveTo if k == 0 else ls.drawTo)(*p)
            ls.setColor(r, g, b, 0.10)
            for k in range(24):
                a = math.tau * k / 24.0
                ls.moveTo(math.cos(a) * BOUNDARY_RADIUS * 0.30, math.sin(a) * BOUNDARY_RADIUS * 0.30, 0.0)
                ls.drawTo(math.cos(a) * BOUNDARY_RADIUS, math.sin(a) * BOUNDARY_RADIUS, 0.0)
            np_ = self.root.attachNewNode(ls.create())
            np_.setZ(band.floor)
            np_.setLightOff()
            np_.setTransparency(TransparencyAttrib.MAlpha)
            np_.setDepthWrite(False)
            np_.setBin("transparent", 3)
            np_.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
            np_.hide()
            self.boundaries.append((band, np_))

    def _place_boundaries(self, cam: Vec3) -> None:
        snap = 200.0
        for band, np_ in self.boundaries:
            gap = abs(cam.z - band.floor)
            if gap > BOUNDARY_VISIBLE:
                if not np_.isHidden():
                    np_.hide()
                continue
            if np_.isHidden():
                np_.show()
            np_.setPos(round(cam.x / snap) * snap, round(cam.y / snap) * snap, band.floor)
            np_.setColorScale(1.0, 1.0, 1.0, 1.0 - gap / BOUNDARY_VISIBLE)

    # ------------------------------------------------------------------
    # Drop-in floating assets
    # ------------------------------------------------------------------
    def _load_assets(self, folder: str) -> list[StrataAsset]:
        if not folder:
            return []
        directory = self.assets_root / "strata" / folder
        loaded: list[StrataAsset] = []
        if not directory.is_dir():
            return loaded
        for path in sorted(directory.glob("*.py")):
            if path.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(f"holocore_strata_{folder}_{path.stem}", path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as exc:
                print(f"holocore_strata_asset_skipped path={path.name} err={exc.__class__.__name__}:{exc}")
                continue
            info = dict(getattr(module, "STRATA_OBJECT", {}) or {})
            weight = float(info.get("weight", 1.0))
            if weight <= 0.0:
                continue
            loaded.append(StrataAsset(str(info.get("id") or path.stem), weight, max(0.0, float(info.get("per_cell", 0.5))), module))
        return loaded

    # ------------------------------------------------------------------
    # Life cells
    # ------------------------------------------------------------------
    def _cell_for(self, pos: Vec3) -> tuple[int, int, int]:
        return (math.floor(pos.x / self.cell_size), math.floor(pos.y / self.cell_size), math.floor(pos.z / self.deck_height))

    def _cell_band(self, key: tuple[int, int, int]) -> StratumBand:
        return self.band_at((key[2] + 0.5) * self.deck_height)

    def _cell_has_life(self, band: StratumBand) -> bool:
        return bool(band.creatures) or bool(self.assets.get(band.band_id))

    def _sync_cells(self, cam: Vec3) -> None:
        centre = self._cell_for(cam)
        if centre == self.last_centre:
            return
        self.last_centre = centre
        desired: set[tuple[int, int, int]] = set()
        for dx in range(-LIFE_CELL_RADIUS, LIFE_CELL_RADIUS + 1):
            for dy in range(-LIFE_CELL_RADIUS, LIFE_CELL_RADIUS + 1):
                for dz in range(-LIFE_DECKS_BELOW, LIFE_DECKS_ABOVE + 1):
                    key = (centre[0] + dx, centre[1] + dy, centre[2] + dz)
                    if self._cell_has_life(self._cell_band(key)):
                        desired.add(key)
        self.desired = desired
        for key in list(self.cells):
            if key not in desired:
                self._remove_cell(key)
        self.build_queue = [k for k in self.build_queue if k in desired]
        missing = [k for k in desired if k not in self.cells and k not in self.build_queue]
        missing.sort(key=lambda k: (k[0] - centre[0]) ** 2 + (k[1] - centre[1]) ** 2 + (k[2] - centre[2]) ** 2)
        self.build_queue.extend(missing)

    def _remove_cell(self, key) -> None:
        cell = self.cells.pop(key, None)
        if cell is not None and not cell.root.isEmpty():
            cell.root.removeNode()

    @staticmethod
    def _cell_seed(key, salt: int) -> int:
        return ((int(key[0]) * 73856093) ^ (int(key[1]) * 19349663) ^ (int(key[2]) * 83492791) ^ int(salt)) & 0xFFFFFFFF

    def _roll_count(self, rng: Random, expected: float) -> int:
        whole = int(expected)
        return min(MAX_LIFE_PER_CELL, whole + (1 if rng.random() < expected - whole else 0))

    def _build_cell(self, key) -> None:
        band = self._cell_band(key)
        root = self.life_root.attachNewNode(f"holocore_strata_cell_{key[0]}_{key[1]}_{key[2]}")
        cell = LifeCell(key=key, band_id=band.band_id, root=root)
        rng = Random(self._cell_seed(key, 0x57A7A))
        x0, y0 = key[0] * self.cell_size, key[1] * self.cell_size
        z0 = max(key[2] * self.deck_height, band.floor + 30.0)
        z1 = (key[2] + 1) * self.deck_height
        if z1 <= z0 + 20.0:
            z1 = z0 + 20.0

        def spot(margin: float = 40.0) -> Vec3:
            return Vec3(rng.uniform(x0 + margin, x0 + self.cell_size - margin),
                        rng.uniform(y0 + margin, y0 + self.cell_size - margin),
                        rng.uniform(z0, z1))

        for kind in sorted(band.creatures):
            for n in range(self._roll_count(rng, band.creatures[kind])):
                pos = spot()
                drifter = self._spawn_creature(kind, root, pos, self._cell_seed(key, zlib.crc32(kind.encode()) & 0xFFFF) + n * 7919)
                if drifter is not None:
                    self._make_proxy(drifter)
                    cell.drifters.append(drifter)
        meta = {"band_id": band.band_id, "band_name": band.name, "accent": band.accent, "cell": key}
        for asset in self.assets.get(band.band_id, []):
            for n in range(self._roll_count(rng, asset.per_cell)):
                pos = spot(60.0)
                arng = Random(self._cell_seed(key, zlib.crc32(asset.asset_id.encode()) & 0xFFFF) + n)
                try:
                    node = asset.build(root, pos.x, pos.y, pos.z, arng, dict(meta))
                except Exception as exc:
                    print(f"holocore_strata_asset_build_silent id={asset.asset_id} err={exc.__class__.__name__}:{exc}")
                    node = None
                if node is None or node.isEmpty():
                    continue
                node.setPythonTag("holocore_strata_asset", asset.asset_id)
                cell.drifters.append(Drifter("asset", node, Vec3(node.getPos(self.render)), 0.0, 0.0, arng.uniform(1.5, 4.0), arng.uniform(0.0, math.tau), asset=asset))
        self.cells[key] = cell

    def _spawn_creature(self, kind: str, parent: NodePath, pos: Vec3, seed: int) -> Drifter | None:
        rng = Random(seed)
        try:
            if kind == "jellyfish" and HoloJellyfishMob is not None:
                variant = JELLYFISH_VARIANTS[seed % len(JELLYFISH_VARIANTS)] if JELLYFISH_VARIANTS else None
                mob = HoloJellyfishMob(seed=seed, variant=variant, surface_height_offset=0.0).build(parent, pos, scale=rng.uniform(0.85, 1.25))
                return Drifter(kind, mob.root, Vec3(pos), rng.uniform(4.0, 14.0), rng.uniform(0.03, 0.07), rng.uniform(4.0, 9.0), rng.uniform(0.0, math.tau), mob=mob)
            if kind == "mermaid" and HoloMermaidMob is not None:
                mob = HoloMermaidMob(seed=seed, surface_height_offset=0.0).build(parent, pos, scale=rng.uniform(2.35, 2.9))
                return Drifter(kind, mob.root, Vec3(pos), rng.uniform(28.0, 64.0), rng.uniform(0.07, 0.13) * (1 if rng.random() < 0.5 else -1), rng.uniform(2.0, 5.0), rng.uniform(0.0, math.tau), mob=mob)
            if kind == "octopus" and HoloOctopusMob is not None:
                mob = HoloOctopusMob(seed=seed, surface_height_offset=3.0).build(parent, pos, scale=rng.uniform(7.5, 10.5))
                return Drifter(kind, mob.root, Vec3(pos), rng.uniform(40.0, 90.0), rng.uniform(0.015, 0.03), rng.uniform(6.0, 12.0), rng.uniform(0.0, math.tau), mob=mob)
        except Exception as exc:
            print(f"holocore_strata_spawn_silent kind={kind} err={exc.__class__.__name__}:{exc}")
        return None

    def _make_proxy(self, d: Drifter) -> None:
        """Freeze a copy of a creature into a few flattened nodes for far range.

        An animated creature is ~40-120 nodes; culling dozens of them every
        frame costs CPU on any GPU.  Beyond LIFE_LIVE_RANGE the eye cannot
        read the tendril sway, so a flattened copy drifts instead.
        """
        if d.mob is None or d.node_root is None or d.node_root.isEmpty():
            return
        try:
            proxy = d.node_root.copyTo(d.node_root.getParent())
            proxy.setName(f"strata_{d.kind}_far_proxy")
            proxy.clearColorScale()
            for child in proxy.getChildren():
                child.flattenStrong()
            proxy.flattenStrong()
            proxy.hide()
            d.proxy = proxy
        except Exception as exc:
            d.proxy = None
            print(f"holocore_strata_proxy_silent kind={d.kind} err={exc.__class__.__name__}:{exc}")

    @staticmethod
    def _set_alpha(d: Drifter, node: NodePath, alpha: float, live: bool) -> None:
        if live and d.mob is not None and hasattr(d.mob, "set_visibility_alpha"):
            d.mob.set_visibility_alpha(alpha)
        else:
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setColorScale(1.0, 1.0, 1.0, alpha)

    def _update_life(self, cam: Vec3) -> None:
        t = self._time
        for cell in self.cells.values():
            for d in cell.drifters:
                root = d.node_root
                if root is None or root.isEmpty():
                    continue
                ang = d.phase + t * d.orbit_speed
                if d.kind == "asset":
                    pos = Vec3(d.anchor.x, d.anchor.y, d.anchor.z + math.sin(t * 0.21 + d.phase) * d.bob)
                else:
                    pos = Vec3(d.anchor.x + math.cos(ang) * d.orbit_radius,
                               d.anchor.y + math.sin(ang) * d.orbit_radius,
                               d.anchor.z + math.sin(t * 0.17 + d.phase * 1.7) * d.bob)
                dist = (pos - cam).length()
                if dist >= LIFE_FADE_END:
                    alpha = 0.0
                elif dist <= LIFE_FADE_FULL:
                    alpha = 1.0
                else:
                    alpha = 1.0 - (dist - LIFE_FADE_FULL) / (LIFE_FADE_END - LIFE_FADE_FULL)
                if alpha <= 0.0:
                    if not root.isHidden():
                        root.hide()
                    if d.proxy is not None and not d.proxy.isHidden():
                        d.proxy.hide()
                    d.showing = ""
                    continue
                live = d.proxy is None or dist <= LIFE_LIVE_RANGE
                node = root if live else d.proxy
                other = d.proxy if live else root
                mode = "live" if live else "proxy"
                if other is not None and not other.isHidden():
                    other.hide()
                if node.isHidden():
                    node.show()
                if d.showing != mode:
                    d.showing = mode
                    d.visible_alpha = -1.0
                node.setPos(self.render, pos)
                if d.kind in ("mermaid", "octopus") and abs(d.orbit_speed) > 0.0:
                    # Face along the orbit (swim direction).
                    node.setH(self.render, math.degrees(ang) + (0.0 if d.orbit_speed > 0 else 180.0))
                if abs(alpha - d.visible_alpha) > 0.01:
                    self._set_alpha(d, node, alpha, live)
                    d.visible_alpha = alpha
                if not live:
                    continue
                try:
                    if d.mob is not None:
                        d.mob.update_pose(t)
                    elif d.asset is not None:
                        d.asset.update(root, t)
                except Exception as exc:
                    print(f"holocore_strata_pose_silent kind={d.kind} err={exc.__class__.__name__}:{exc}")

    # ------------------------------------------------------------------
    # Band title
    # ------------------------------------------------------------------
    def _show_title(self, band: StratumBand, z: float) -> None:
        try:
            if self._title is None:
                from direct.gui.OnscreenText import OnscreenText

                self._title = OnscreenText(text="", pos=(0.0, 0.78), scale=0.058, fg=(1, 1, 1, 0),
                                           align=TextNode.ACenter, mayChange=True)
            r, g, b = band.accent
            self._title.setText(f"{band.name.upper()}\n{int(round(z))} m")
            self._title.setFg((r, g, b, 0.0))
            self._title_age = 0.0
            self._title_rgb = (r, g, b)
        except Exception as exc:
            print(f"holocore_strata_title_silent err={exc.__class__.__name__}:{exc}")

    def _update_title(self, dt: float) -> None:
        if self._title is None:
            return
        self._title_age += dt
        age = self._title_age
        if age < TITLE_FADE:
            a = age / TITLE_FADE
        elif age < TITLE_FADE + TITLE_HOLD:
            a = 1.0
        else:
            a = max(0.0, 1.0 - (age - TITLE_FADE - TITLE_HOLD) / TITLE_FADE)
        r, g, b = getattr(self, "_title_rgb", (1.0, 1.0, 1.0))
        self.title_alpha = 0.9 * a
        self._title.setFg((r, g, b, self.title_alpha))

    # ------------------------------------------------------------------
    # Frame update
    # ------------------------------------------------------------------
    def camera_position(self) -> Vec3:
        try:
            return Vec3(self.app.camera.getPos(self.render))
        except Exception:
            return Vec3(0, 0, 0)

    def update(self, dt: float, time_value: float | None = None, force: bool = False) -> None:
        if self.root is None or self.root.isEmpty():
            return
        dt = max(0.0, min(0.05, float(dt or 0.0)))
        self._time = float(time_value) if time_value is not None else self._time + dt
        cam = self.camera_position()
        self._apply_atmosphere(cam.z)
        band = self.atmosphere["band"]
        if band.band_id != self.current_band_id:
            if self.current_band_id is not None:
                self.band_changes += 1
                self._show_title(band, cam.z)
            self.current_band_id = band.band_id
        self._place_snow(cam, dt)
        self._place_boundaries(cam)
        self._sync_cells(cam)
        builds = len(self.build_queue) if force else LIFE_BUILDS_PER_FRAME
        for _ in range(builds):
            if not self.build_queue:
                break
            self._build_cell(self.build_queue.pop(0))
        self._life_elapsed += dt
        if force or self._life_elapsed >= LIFE_UPDATE_INTERVAL:
            self._life_elapsed = 0.0
            self._update_life(cam)
        self._update_title(dt)

    def settle(self) -> None:
        """Build every pending cell and pose everything now (smokes, teleports)."""
        self.last_centre = None
        self.update(0.0, self._time, force=True)

    def report(self) -> dict:
        cam = self.camera_position()
        kinds: dict[str, int] = {}
        for cell in self.cells.values():
            for d in cell.drifters:
                name = d.kind if d.kind != "asset" else f"asset:{d.asset.asset_id if d.asset else '?'}"
                kinds[name] = kinds.get(name, 0) + 1
        return {
            "band": self.atmosphere.get("band").band_id if self.atmosphere else None,
            "camera_z": round(float(cam.z), 2),
            "bands": [{"id": b.band_id, "name": b.name, "floor": b.floor, "assets": [a.asset_id for a in self.assets.get(b.band_id, [])]} for b in self.bands],
            "cells": len(self.cells),
            "pending_cells": len(self.build_queue),
            "drifters": kinds,
            "fog_density": round(float(self.atmosphere.get("fog_density", 0.0)), 6) if self.atmosphere else None,
            "background": [round(float(c), 4) for c in self.atmosphere.get("background", (0, 0, 0))] if self.atmosphere else None,
            "band_changes": int(self.band_changes),
        }

    def destroy(self) -> None:
        for key in list(self.cells):
            self._remove_cell(key)
        if self._title is not None:
            try:
                self._title.destroy()
            except Exception:
                pass
            self._title = None
        if self.root is not None and not self.root.isEmpty():
            self.root.removeNode()


__all__ = ["HoloCoreStrata", "StratumBand", "load_bands"]
