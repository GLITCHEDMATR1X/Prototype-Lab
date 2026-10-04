from __future__ import annotations

import colorsys
import hashlib
import math
import re
import time
from pathlib import Path

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LineSegs,
    NodePath,
    PNMImage,
    SamplerState,
    TextNode,
    Texture,
    TransparencyAttrib,
    Vec3,
)

from holoverse.world_geometry import MAIN_AREA_RADIUS
from .observatory_layout import (
    SELF_SPIN_DEG,
    SPHERE_RADIUS,
    build_observatory_slots,
)


PLANET_ROOT_NAME = "dimension-observatory-root"
PLANET_TASK_BASENAME = "holoverse-dimension-observatory"
SPHERE_SEGMENTS_U = 48
SPHERE_SEGMENTS_V = 24
IDLE_SPHERE_SEGMENTS_U = 24
IDLE_SPHERE_SEGMENTS_V = 12
ATMOSPHERE_SEGMENTS_U = 16
ATMOSPHERE_SEGMENTS_V = 8
FOCUS_SCAN_INTERVAL = 1.0 / 30.0
ORBIT_HUB_ACTIVE_RADIUS = max(24.0, float(MAIN_AREA_RADIUS) - 18.0)
TARGET_MAX_DISTANCE = 340.0
TARGET_RADIUS_SCALE = 1.24
PLANET_TEXTURE_WIDTH = 256
PLANET_TEXTURE_HEIGHT = 128
INFO_TITLE_PREFIX = "REALITY //"
# Pass 282.64: the orbs no longer float around the hub; the same realities are
# planets in HoloSpace (holoverse/dimension_planets.py).  The class stays so
# older hooks keep working, but it draws and targets nothing.
HUB_ORBS_RETIRED = True


def _slug(value: str) -> str:
    parts = re.findall(r"[a-z0-9]+", str(value or "").lower())
    return "_".join(parts) or "dimension"


def _safe_resolve(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(Path(path).resolve()).casefold()
    except Exception:
        return str(path).casefold()


def _compatibility_texture_name(record) -> str:
    if not bool(getattr(record, "launchable", False)):
        return "missing.png"
    compatibility = str(getattr(record, "compatibility", "linked") or "linked").strip().lower()
    if compatibility == "native":
        return "native.png"
    if compatibility == "adapted":
        return "adapted.png"
    if compatibility == "legacy":
        return "legacy.png"
    return "linked.png"


def _make_uv_sphere_node(name: str, radius: float = SPHERE_RADIUS, segments_u: int = SPHERE_SEGMENTS_U, segments_v: int = SPHERE_SEGMENTS_V):
    fmt = GeomVertexFormat.getV3n3t2()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    texcoord = GeomVertexWriter(vdata, "texcoord")
    prim = GeomTriangles(Geom.UHStatic)

    segments_u = max(8, int(segments_u))
    segments_v = max(4, int(segments_v))
    for y in range(segments_v + 1):
        v = y / float(segments_v)
        phi = v * math.pi
        for x in range(segments_u + 1):
            u = x / float(segments_u)
            theta = u * math.tau
            sx = math.sin(phi) * math.cos(theta)
            sy = math.sin(phi) * math.sin(theta)
            sz = math.cos(phi)
            vertex.addData3f(sx * radius, sy * radius, sz * radius)
            normal.addData3f(sx, sy, sz)
            texcoord.addData2f(u, 1.0 - v)

    stride = segments_u + 1
    for y in range(segments_v):
        for x in range(segments_u):
            i0 = y * stride + x
            i1 = i0 + 1
            i2 = i0 + stride
            i3 = i2 + 1
            prim.addVertices(i0, i1, i2)
            prim.addVertices(i1, i3, i2)

    geom = Geom(vdata)
    geom.addPrimitive(prim)
    node = GeomNode(name)
    node.addGeom(geom)
    return node


def _seed_bytes(record) -> bytes:
    key = f"{getattr(record, 'dimension_id', '')}|{getattr(record, 'title', '')}".encode("utf-8", "replace")
    return hashlib.sha256(key).digest()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _mix3(a, b, t: float):
    t = _clamp01(t)
    return tuple(a[i] * (1.0 - t) + b[i] * t for i in range(3))


def _planet_profile(record) -> dict:
    seed = _seed_bytes(record)
    accent = tuple(float(v) for v in getattr(record, "accent", (0.2, 0.9, 1.0)))
    if len(accent) < 3:
        accent = (0.2, 0.9, 1.0)
    accent = tuple(_clamp01(v) for v in accent[:3])

    # Keep the registry accent as the family authority, but give each linked
    # reality a deterministic hue offset so generic links do not collapse into
    # six visually identical cyan balls when no project-specific art exists.
    _h, s, v = colorsys.rgb_to_hsv(*accent)
    # Identity hue spans the holographic spectrum instead of clustering around
    # the default registry cyan.  The registry accent still contributes 28%,
    # preserving project family while making different realities readable at a
    # glance from the observatory floor.
    identity_rgb = colorsys.hsv_to_rgb(
        seed[5] / 255.0,
        _clamp01(0.62 + (seed[6] / 255.0) * 0.30),
        _clamp01(0.76 + (seed[7] / 255.0) * 0.22),
    )
    planet_accent = _mix3(accent, identity_rgb, 0.72)
    rotated = (planet_accent[1], planet_accent[2], planet_accent[0])
    secondary = tuple(_clamp01(0.20 + rotated[i] * 0.72 + (seed[4 + i] / 255.0) * 0.10) for i in range(3))
    dark = tuple(_clamp01(0.018 + planet_accent[i] * 0.16) for i in range(3))
    mid = tuple(_clamp01(0.080 + planet_accent[i] * 0.52) for i in range(3))
    bright = tuple(_clamp01(0.25 + planet_accent[i] * 0.75) for i in range(3))

    return {
        "seed": seed,
        "mode": int(seed[0] % 7),
        "freq_a": 2 + int(seed[1] % 6),
        "freq_b": 3 + int(seed[2] % 8),
        "freq_c": 2 + int(seed[3] % 5),
        "phase_a": (seed[8] / 255.0) * math.tau,
        "phase_b": (seed[9] / 255.0) * math.tau,
        "accent": planet_accent,
        "registry_accent": accent,
        "secondary": secondary,
        "dark": dark,
        "mid": mid,
        "bright": bright,
        "size": 0.92 + (seed[10] / 255.0) * 0.28,
        "tilt_p": -18.0 + (seed[11] / 255.0) * 36.0,
        "tilt_r": -10.0 + (seed[12] / 255.0) * 20.0,
        "trace_count": 3 + int(seed[13] % 4),
        "trace_phase": (seed[14] / 255.0) * math.tau,
        "trace_width": 0.92 + (seed[15] / 255.0) * 0.62,
        "atmosphere_scale": 1.040 + (seed[16] / 255.0) * 0.036,
        "atmosphere_alpha": 0.070 + (seed[17] / 255.0) * 0.034,
        "initial_h": (seed[18] / 255.0) * 360.0,
        "spin_speed": (-1.0 if (seed[19] & 1) else 1.0) * (2.0 + (seed[20] / 255.0) * 3.8),
    }


def _procedural_planet_texture(record, profile: dict) -> Texture | None:
    """Build a deterministic equirectangular hardlight surface in memory."""
    width, height = PLANET_TEXTURE_WIDTH, PLANET_TEXTURE_HEIGHT
    image = PNMImage(width, height, 4)
    mode = int(profile["mode"])
    fa = float(profile["freq_a"])
    fb = float(profile["freq_b"])
    fc = float(profile["freq_c"])
    pa = float(profile["phase_a"])
    pb = float(profile["phase_b"])
    launchable = bool(getattr(record, "launchable", False))

    for py in range(height):
        v = py / float(max(1, height - 1))
        lat = (0.5 - v) * math.pi
        for px in range(width):
            u = px / float(max(1, width - 1))
            lon = u * math.tau - math.pi

            a = math.sin(lon * fa + math.sin(lat * fc + pb) * 1.15 + pa)
            b = math.cos(lat * fb - lon * 0.63 + pb)
            c = math.sin((lon + lat * 0.75) * fc + pa * 0.55)
            field = (a * 0.48 + b * 0.31 + c * 0.21 + 1.0) * 0.5

            if mode == 0:  # fractured continents
                region = _clamp01((field - 0.34) / 0.52)
                trace = abs(math.sin(lon * (fa + 3.0) + lat * (fb + 1.0) + pa))
            elif mode == 1:  # flowing strata
                band = (math.sin(lat * (fb + 3.0) + lon * 0.48 + a * 0.9) + 1.0) * 0.5
                region = _clamp01(field * 0.48 + band * 0.52)
                trace = abs(math.sin(lat * (fb + 5.0) + lon * 0.22 + pb))
            elif mode == 2:  # cellular network
                cell = abs(math.sin(lon * fa + pa) * math.sin(lat * fb + pb))
                region = _clamp01(field * 0.55 + cell * 0.45)
                trace = min(abs(math.sin(lon * (fa + 2.0) + pa)), abs(math.sin(lat * (fb + 2.0) + pb)))
            elif mode == 3:  # diagonal signal terrain
                diag = (math.sin((lon * fa + lat * fb) + pa) + 1.0) * 0.5
                region = _clamp01(field * 0.58 + diag * 0.42)
                trace = abs(math.sin((lon * (fa + 4.0) - lat * (fc + 3.0)) + pb))
            elif mode == 4:  # polar / storm geometry
                polar = abs(math.sin(lat * (fb + 1.0)))
                swirl = (math.sin(lon * fa + math.sin(lat * 3.0) * 2.1 + pa) + 1.0) * 0.5
                region = _clamp01(field * 0.45 + polar * 0.22 + swirl * 0.33)
                trace = abs(math.sin(lon * (fa + 2.0) + lat * (fb + 4.0) + pa))
            elif mode == 5:  # hardlight lattice continents
                lon_grid = abs(math.sin(lon * (fa + 2.0) + pa))
                lat_grid = abs(math.sin(lat * (fb + 3.0) + pb))
                lattice = 1.0 - min(lon_grid, lat_grid)
                region = _clamp01(field * 0.60 + lattice * 0.40)
                trace = max(lon_grid, lat_grid)
            else:  # void archipelago / broken signal islands
                islands = abs(math.sin(lon * fa + pa) + math.cos(lat * fb + pb)) * 0.5
                cut = (math.sin((lon - lat) * (fc + 2.0) + pa * 0.7) + 1.0) * 0.5
                region = _clamp01(field * 0.42 + islands * 0.36 + cut * 0.22)
                trace = abs(math.sin(lon * (fa + 5.0) + math.sin(lat * 2.0) * 1.4 + pb))

            color = _mix3(profile["dark"], profile["mid"], region)
            if region > 0.68:
                color = _mix3(color, profile["secondary"], (region - 0.68) / 0.32 * 0.44)

            # Embedded hardlight routes: narrow and identity-derived, never a
            # global ring overlay.  Missing realities show broken route bands.
            line_strength = _clamp01((trace - 0.965) / 0.035)
            if not launchable:
                gate = (px // 11 + py // 7 + profile["seed"][15]) % 4
                if gate == 0:
                    line_strength *= 0.14
            if line_strength > 0.0:
                color = _mix3(color, profile["bright"], line_strength * 0.90)

            # Soft polar glow keeps the sphere legible against the dark Hub.
            pole = _clamp01((abs(lat) - 0.96) / 0.52)
            color = _mix3(color, profile["secondary"], pole * 0.18)
            image.setXelA(px, height - 1 - py, color[0], color[1], color[2], 1.0)

    texture = Texture(f"dimension-planet-{_slug(getattr(record, 'dimension_id', 'dimension'))}")
    if not texture.load(image):
        return None
    try:
        texture.generateRamMipmapImages()
    except Exception:
        pass
    texture.setWrapU(SamplerState.WMRepeat)
    texture.setWrapV(SamplerState.WMClamp)
    texture.setMinfilter(SamplerState.FTLinearMipmapLinear)
    texture.setMagfilter(SamplerState.FTLinear)
    try:
        texture.setAnisotropicDegree(8)
    except Exception:
        pass
    return texture


def _make_surface_traces(parent, profile: dict, radius: float, launchable: bool):
    """Draw sparse identity-specific traces directly on the planet surface."""
    traces = LineSegs("dimension-planet-surface-traces")
    traces.setThickness(float(profile.get("trace_width", 1.15)) * (1.0 if launchable else 0.72))
    accent = profile["bright"] if launchable else tuple(v * 0.48 for v in profile["bright"])
    traces.setColor(accent[0], accent[1], accent[2], 0.66 if launchable else 0.28)
    count = int(profile["trace_count"])
    phase0 = float(profile["trace_phase"])
    mode = int(profile["mode"])
    r = float(radius) * 1.012

    for line_index in range(count):
        phase = phase0 + line_index * (math.tau / max(1, count))
        for step in range(35):
            t = step / 34.0
            if mode == 0:  # narrow meridian currents
                lat = -1.18 + t * 2.36
                lon = phase + math.sin(lat * (1.8 + line_index * 0.18) + phase0) * 0.20
            elif mode == 1:  # broken latitude signal bands, never full rings
                lon = phase - 1.55 + t * 3.10
                lat = -0.82 + (line_index / max(1, count - 1)) * 1.64 + math.sin(lon * 1.7 + phase0) * 0.12
            elif mode == 2:  # diagonal data weave
                lat = -1.12 + t * 2.24
                lon = phase + lat * (0.55 + line_index * 0.06) + math.sin(lat * 3.1 + phase0) * 0.08
            elif mode == 3:  # broad fracture paths
                lat = -1.10 + t * 2.20
                lon = phase + math.sin(lat * (2.6 + line_index * 0.24) + phase0) * (0.32 + 0.035 * line_index)
            elif mode == 4:  # polar storm hooks
                lat = -1.20 + t * 2.40
                lon = phase + math.sin(lat * 1.45 + phase0) * 0.52 + lat * 0.18
            elif mode == 5:  # short lattice diagonals
                lat = -1.04 + t * 2.08
                lon = phase - 0.95 + t * 1.90 + math.sin(t * math.tau + phase0) * 0.10
            else:  # broken archipelago current
                lat = -1.14 + t * 2.28
                lon = phase + math.sin(t * math.tau * 1.5 + phase0) * 0.42 + lat * 0.24
            x = math.cos(lat) * math.cos(lon) * r
            y = math.cos(lat) * math.sin(lon) * r
            z = math.sin(lat) * r
            if step == 0:
                traces.moveTo(x, y, z)
            else:
                traces.drawTo(x, y, z)
    node = parent.attachNewNode(traces.create())
    node.setLightOff(1)
    node.setFogOff(1)
    node.setTransparency(TransparencyAttrib.MAlpha)
    return node



class DimensionObservatory:
    """Holographic planet view over external MatrixCore-linked realities.

    Registry records remain the sole launch authority.  This class only renders
    and targets those records, then delegates Mouse1 activation back to the same
    registry lifecycle used by Gleebs' archive.
    """

    def __init__(self, host, registry, asset_root: Path):
        self.host = host
        self.registry = registry
        self.asset_root = Path(asset_root)
        self.root = None
        self.sphere_template = None
        self.idle_sphere_template = None
        self.atmosphere_template = None
        self.entries: list[dict] = []
        self._signature = ()
        self._focused_id = ""
        self._last_frame_at = time.monotonic()
        self._next_focus_scan_at = 0.0
        self._cached_focus = None
        self._last_info_signature = None
        self._task_name = f"{PLANET_TASK_BASENAME}-{id(self)}"
        self._texture_cache: dict[tuple, Texture] = {}
        self.info_root = None
        self.info_panel = None
        self.info_accent = None
        self.info_title = None
        self.info_meta = None
        self.info_source = None
        self.info_action = None

    def start(self):
        parent = getattr(self.host, "root_3d", None) or getattr(self.host, "render", None)
        if parent is None:
            raise RuntimeError("HoloVerse 3D root unavailable")
        self.root = parent.attachNewNode(PLANET_ROOT_NAME)
        self.root.setPythonTag("holoverse_dimension_observatory", True)
        # Detached templates are copy sources only; they do not live in the
        # render graph and therefore do not expand cull/draw work themselves.
        self.sphere_template = NodePath(_make_uv_sphere_node(
            "dimension-observatory-focus-template", SPHERE_RADIUS, SPHERE_SEGMENTS_U, SPHERE_SEGMENTS_V
        ))
        self.idle_sphere_template = NodePath(_make_uv_sphere_node(
            "dimension-observatory-idle-template", SPHERE_RADIUS, IDLE_SPHERE_SEGMENTS_U, IDLE_SPHERE_SEGMENTS_V
        ))
        self.atmosphere_template = NodePath(_make_uv_sphere_node(
            "dimension-observatory-atmosphere-template", SPHERE_RADIUS, ATMOSPHERE_SEGMENTS_U, ATMOSPHERE_SEGMENTS_V
        ))
        self._build_info_panel()
        if HUB_ORBS_RETIRED:
            self.root.hide()
            return self
        self.sync_records(getattr(self.registry, "records", []), force=True)
        self.host.taskMgr.add(self._task, self._task_name, sort=39)
        return self

    def destroy(self):
        try:
            self.host.taskMgr.remove(self._task_name)
        except Exception:
            pass
        self._hide_info_panel()
        if self.info_root is not None:
            try:
                self.info_root.removeNode()
            except Exception:
                pass
        self.info_root = None
        if self.root is not None:
            try:
                self.root.removeNode()
            except Exception:
                pass
        self.root = None
        self.sphere_template = None
        self.idle_sphere_template = None
        self.atmosphere_template = None
        self.entries.clear()
        self._cached_focus = None
        self._last_info_signature = None
        self._texture_cache.clear()
        self._focused_id = ""

    @property
    def focused_dimension_id(self) -> str:
        return str(self._focused_id or "")

    def _record_signature(self, record) -> tuple:
        return (
            str(getattr(record, "dimension_id", "")),
            str(getattr(record, "title", "")),
            str(getattr(record, "compatibility", "")),
            bool(getattr(record, "launchable", False)),
            _safe_resolve(getattr(record, "entry", None)),
            _safe_resolve(getattr(record, "adapter", None)),
            _safe_resolve(getattr(record, "folder", None)),
            tuple(getattr(record, "accent", (0.2, 0.9, 1.0))),
        )

    def sync_records(self, records, force: bool = False) -> bool:
        if HUB_ORBS_RETIRED:
            return False
        records = [r for r in list(records or []) if str(getattr(r, "origin", "")) == "linked"]
        records.sort(key=lambda r: (str(getattr(r, "title", "")).casefold(), str(getattr(r, "dimension_id", ""))))
        signature = tuple(self._record_signature(r) for r in records)
        if not force and signature == self._signature:
            return False
        self._signature = signature
        self._rebuild(records)
        return True

    def _clear_children(self):
        for entry in self.entries:
            node = entry.get("holder")
            if node is not None:
                try:
                    node.removeNode()
                except Exception:
                    pass
        self.entries.clear()

    def _rebuild(self, records):
        self._clear_children()
        if self.root is None or self.sphere_template is None:
            return
        total = len(records)
        if total <= 0:
            return

        slots = build_observatory_slots([str(getattr(record, "dimension_id", idx)) for idx, record in enumerate(records)])
        for idx, record in enumerate(records):
            slot = slots[idx]
            profile = _planet_profile(record)
            holder = self.root.attachNewNode(f"dimension-planet-{_slug(record.dimension_id)}")
            visual = holder.attachNewNode(f"dimension-planet-visual-{_slug(record.dimension_id)}")
            visual.setH(float(profile["initial_h"]))
            visual.setP(float(profile["tilt_p"]))
            visual.setR(float(profile["tilt_r"]))

            sphere = self._make_surface_node(visual, record, profile, focused=False)

            launchable = bool(record.launchable)
            base_alpha = 0.96 if launchable else 0.52
            # Surface art already carries the identity palette.  Keep the
            # render multiplier neutral so custom/procedural colors are not
            # collapsed back toward one generic cyan compatibility tint.
            tint = (1.0, 1.0, 1.0)
            sphere.setColorScale(1.0, 1.0, 1.0, base_alpha)

            atmosphere = self.atmosphere_template.copyTo(visual)
            atmosphere.show()
            atmosphere.setScale(float(profile["atmosphere_scale"]))
            atmosphere.setLightOff(1)
            atmosphere.setFogOff(1)
            atmosphere.clearTexture()
            atmosphere.setTransparency(TransparencyAttrib.MAlpha)
            atmosphere.setDepthWrite(False)
            atmosphere.setBin("transparent", 20)
            atmosphere.setColorScale(
                profile["secondary"][0], profile["secondary"][1], profile["secondary"][2],
                float(profile["atmosphere_alpha"]) if launchable else float(profile["atmosphere_alpha"]) * 0.34,
            )

            traces = _make_surface_traces(visual, profile, SPHERE_RADIUS, launchable)
            holder.setPythonTag("holoverse_dimension_sphere", True)  # legacy targeting/tool tag
            holder.setPythonTag("holoverse_dimension_planet", True)
            holder.setPythonTag("dimension_id", str(record.dimension_id))
            holder.setPos(slot.x, slot.y, slot.z)
            holder.setScale(float(profile["size"]))

            entry = {
                "record": record,
                "holder": holder,
                "visual": visual,
                "sphere": sphere,
                "atmosphere": atmosphere,
                "traces": traces,
                "field_index": slot.band_index,
                "base_alpha": base_alpha,
                "tint": tint,
                "profile": profile,
                "base_scale": float(profile["size"]),
                "target_radius": SPHERE_RADIUS * float(profile["size"]),
                "surface_detail": "idle",
            }
            self.entries.append(entry)
        print(f"dimension_observatory_rebuild planets={len(self.entries)} layout=stable_3d_field rings=0")

    def _configure_surface_node(self, sphere, record, profile):
        sphere.show()
        sphere.setLightOff(1)
        sphere.setFogOff(1)
        sphere.setTransparency(TransparencyAttrib.MAlpha)
        sphere.setPythonTag("dimension_id", str(record.dimension_id))
        sphere.setPythonTag("dimension_title", str(record.title))
        sphere.setPythonTag("dimension_compatibility", str(record.compatibility))
        self._apply_texture(sphere, record, profile)
        return sphere

    def _make_surface_node(self, visual, record, profile, focused: bool):
        template = self.sphere_template if focused else self.idle_sphere_template
        sphere = template.copyTo(visual)
        self._configure_surface_node(sphere, record, profile)
        sphere.setPythonTag("dimension_planet_lod", "focus" if focused else "idle")
        return sphere

    def _set_surface_detail(self, entry, focused: bool):
        desired = "focus" if focused else "idle"
        if str(entry.get("surface_detail", "idle")) == desired:
            return
        old = entry.get("sphere")
        try:
            if old is not None:
                old.removeNode()
        except Exception:
            pass
        sphere = self._make_surface_node(entry["visual"], entry["record"], entry["profile"], focused=focused)
        entry["sphere"] = sphere
        entry["surface_detail"] = desired

    def _texture_candidates(self, record):
        specific = _slug(str(getattr(record, "dimension_id", ""))) + ".png"
        folder = Path(getattr(record, "folder", self.asset_root) or self.asset_root)
        # Explicit project/user art remains authoritative.  Compatibility
        # fallbacks are now only used if procedural generation fails.
        yield self.asset_root / specific
        yield folder / "holoverse" / "dimension_sphere.png"
        yield folder / "dimension_sphere.png"

    def _apply_texture(self, sphere, record, profile):
        for candidate in self._texture_candidates(record):
            try:
                if not Path(candidate).is_file():
                    continue
                tex = self.host.loader.loadTexture(str(candidate))
                if tex is None:
                    continue
                tex.setWrapU(SamplerState.WMRepeat)
                tex.setWrapV(SamplerState.WMClamp)
                tex.setMinfilter(SamplerState.FTLinearMipmapLinear)
                tex.setMagfilter(SamplerState.FTLinear)
                try:
                    tex.setAnisotropicDegree(8)
                except Exception:
                    pass
                sphere.setTexture(tex, 1)
                sphere.setPythonTag("dimension_sphere_texture", str(candidate))
                sphere.setPythonTag("dimension_planet_surface_source", "override")
                return True
            except Exception:
                continue

        key = self._record_signature(record)
        tex = self._texture_cache.get(key)
        if tex is None:
            try:
                tex = _procedural_planet_texture(record, profile)
            except Exception as exc:
                tex = None
                print(f"dimension_planet_texture_generation_failed id={record.dimension_id} err={exc}")
            if tex is not None:
                self._texture_cache[key] = tex
        if tex is not None:
            sphere.setTexture(tex, 1)
            sphere.setPythonTag("dimension_sphere_texture", f"procedural://{record.dimension_id}")
            sphere.setPythonTag("dimension_planet_surface_source", "procedural")
            return True

        for fallback in (self.asset_root / _compatibility_texture_name(record), self.asset_root / "linked.png"):
            try:
                if not fallback.is_file():
                    continue
                tex = self.host.loader.loadTexture(str(fallback))
                if tex is None:
                    continue
                sphere.setTexture(tex, 1)
                sphere.setPythonTag("dimension_sphere_texture", str(fallback))
                sphere.setPythonTag("dimension_planet_surface_source", "compatibility-fallback")
                return True
            except Exception:
                continue
        return False

    def _build_info_panel(self):
        parent = getattr(self.host, "hud_root", None) or getattr(self.host, "aspect2d", None)
        if parent is None:
            return
        try:
            from direct.gui.DirectFrame import DirectFrame
            from direct.gui.DirectLabel import DirectLabel

            font_kw = self.host._core_text_kw() if hasattr(self.host, "_core_text_kw") else {}
            self.info_root = parent.attachNewNode("dimension-observatory-info-root")
            self.info_panel = DirectFrame(
                parent=self.info_root,
                frameColor=(0.004, 0.018, 0.026, 0.78),
                frameSize=(0.0, 0.72, -0.12, 0.13),
                pos=(-1.27, 0, -0.72),
            )
            self.info_accent = DirectFrame(
                parent=self.info_panel,
                frameColor=(0.18, 0.95, 1.0, 0.88),
                frameSize=(0.0, 0.010, -0.12, 0.13),
                pos=(0, 0, 0),
            )
            self.info_title = DirectLabel(
                parent=self.info_panel,
                text="",
                text_align=TextNode.ALeft,
                text_scale=0.028,
                text_fg=(0.90, 0.99, 1.0, 0.98),
                text_wordwrap=27.0,
                frameColor=(0, 0, 0, 0),
                pos=(0.028, 0, 0.076),
                textMayChange=True,
                **font_kw,
            )
            self.info_meta = DirectLabel(
                parent=self.info_panel,
                text="",
                text_align=TextNode.ALeft,
                text_scale=0.021,
                text_fg=(0.58, 0.84, 0.90, 0.94),
                text_wordwrap=34.0,
                frameColor=(0, 0, 0, 0),
                pos=(0.028, 0, 0.018),
                textMayChange=True,
                **font_kw,
            )
            self.info_source = DirectLabel(
                parent=self.info_panel,
                text="",
                text_align=TextNode.ALeft,
                text_scale=0.019,
                text_fg=(0.48, 0.66, 0.72, 0.90),
                text_wordwrap=38.0,
                frameColor=(0, 0, 0, 0),
                pos=(0.028, 0, -0.034),
                textMayChange=True,
                **font_kw,
            )
            self.info_action = DirectLabel(
                parent=self.info_panel,
                text="",
                text_align=TextNode.ALeft,
                text_scale=0.020,
                text_fg=(0.76, 0.98, 0.92, 0.98),
                text_wordwrap=36.0,
                frameColor=(0, 0, 0, 0),
                pos=(0.028, 0, -0.087),
                textMayChange=True,
                **font_kw,
            )
            self.info_root.hide()
        except Exception as exc:
            print(f"dimension_observatory_info_init_failed err={exc}")
            self.info_root = None

    def _hide_info_panel(self):
        if self.info_root is not None:
            try:
                self.info_root.hide()
            except Exception:
                pass

    def _host_available(self) -> bool:
        if getattr(self.host, "active_native_mode", None) is not None:
            return False
        if bool(getattr(self.host, "external_suspended", False)):
            return False
        if bool(getattr(self.registry, "menu_open", False)):
            return False
        if bool(getattr(self.host, "menu_open", False)):
            return False
        if bool(getattr(self.host, "bot_dialogue_open", False)):
            return False
        if bool(getattr(self.host, "core_console_open", False)):
            return False
        try:
            pos = getattr(self.host, "player_pos", Vec3(0, 0, 0))
            if math.hypot(float(pos.x), float(pos.y)) > ORBIT_HUB_ACTIVE_RADIUS:
                return False
        except Exception:
            return False
        return True

    def _rotate_focused(self, focused, dt: float):
        """Animate only the planet currently under the crosshair."""
        if focused is None or dt <= 0.0:
            return
        try:
            spin_speed = float(focused.get("profile", {}).get("spin_speed", 2.4))
            visual = focused["visual"]
            visual.setH(float(visual.getH()) + float(spin_speed) * float(dt))
        except Exception:
            pass

    def _find_focus(self):
        if not self._host_available():
            return None
        try:
            origin = self.host.head_world_pos()
            forward, _right, _up = self.host.get_view_basis()
            forward = Vec3(forward)
            if forward.lengthSquared() <= 1e-8:
                return None
            forward.normalize()
            render = getattr(self.host, "render", None)
            if render is None:
                return None
        except Exception:
            return None
        best = None
        best_distance = 1e30
        for entry in self.entries:
            try:
                center = entry["holder"].getPos(render)
                rel = center - origin
                along = float(rel.dot(forward))
                if along <= 0.0 or along > TARGET_MAX_DISTANCE:
                    continue
                effective_radius = float(entry["target_radius"]) * TARGET_RADIUS_SCALE
                perp_vec = rel - forward * along
                perp_sq = float(perp_vec.lengthSquared())
                if perp_sq > effective_radius * effective_radius:
                    continue
                hit_distance = along - math.sqrt(max(0.0, effective_radius * effective_radius - perp_sq))
                if hit_distance < best_distance:
                    best_distance = hit_distance
                    best = entry
            except Exception:
                continue
        return best

    def _apply_focus_visual(self, focused):
        focused_id = str(getattr(focused.get("record"), "dimension_id", "")) if focused else ""
        if focused_id == self._focused_id:
            return
        for entry in self.entries:
            record = entry["record"]
            is_focus = bool(focused_id and str(record.dimension_id) == focused_id)
            holder = entry["holder"]
            atmosphere = entry["atmosphere"]
            traces = entry["traces"]
            try:
                self._set_surface_detail(entry, is_focus)
                sphere = entry["sphere"]
                base_scale = float(entry["base_scale"])
                holder.setScale(base_scale * (1.10 if is_focus else 1.0))
                tint = entry["tint"]
                alpha = 1.0 if is_focus else float(entry["base_alpha"])
                if is_focus:
                    sphere.setColorScale(1.12, 1.12, 1.12, alpha)
                    atmosphere.setColorScale(
                        entry["profile"]["secondary"][0], entry["profile"]["secondary"][1], entry["profile"]["secondary"][2],
                        min(0.17, float(entry["profile"]["atmosphere_alpha"]) * 1.50) if bool(record.launchable) else 0.050,
                    )
                    traces.setColorScale(1.20, 1.20, 1.20, 1.0)
                else:
                    sphere.setColorScale(1.0, 1.0, 1.0, alpha)
                    atmosphere.setColorScale(
                        entry["profile"]["secondary"][0], entry["profile"]["secondary"][1], entry["profile"]["secondary"][2],
                        float(entry["profile"]["atmosphere_alpha"]) if bool(record.launchable) else float(entry["profile"]["atmosphere_alpha"]) * 0.34,
                    )
                    traces.setColorScale(1.0, 1.0, 1.0, 1.0)
            except Exception:
                pass
        self._focused_id = focused_id

    @staticmethod
    def _project_label(record) -> str:
        try:
            raw = str(getattr(record, "folder", "") or "").strip().rstrip("\\/")
            if raw:
                # Linked paths may have been authored on Windows and inspected on
                # Linux (or vice versa).  Split both separator styles so the UI
                # shows the real project folder name instead of an entire foreign
                # absolute path that can overflow the compact info panel.
                label = re.split(r"[\\/]+", raw)[-1].strip()
                if label:
                    return label
        except Exception:
            pass
        return "LINKED PROJECT"

    def _update_info(self, focused):
        if self.info_root is None:
            return
        if focused is None:
            if self._last_info_signature is not None:
                self._last_info_signature = None
                self._hide_info_panel()
            return
        record = focused["record"]
        launchable = bool(record.launchable)
        native = bool(record.native_launchable)
        mode = "NATIVE" if native else str(getattr(record, "compatibility", "linked") or "linked").upper()
        engine = str(getattr(record, "engine", "") or "").strip().upper()
        status = "READY" if launchable else "LINK UNAVAILABLE"
        source = self._project_label(record)
        info_signature = (str(record.dimension_id), str(record.title), mode, engine, status, source, launchable, str(getattr(record, "link_id", "") or ""))
        if info_signature == self._last_info_signature:
            return
        self._last_info_signature = info_signature
        try:
            accent = tuple(float(v) for v in focused.get("profile", {}).get("accent", getattr(record, "accent", (0.2, 0.9, 1.0))))
            self.info_accent["frameColor"] = (accent[0], accent[1], accent[2], 0.92)
            title_text = f"{INFO_TITLE_PREFIX} {str(record.title).upper()}"
            self.info_title["text"] = title_text
            self.info_title["text_scale"] = 0.028 if len(title_text) <= 32 else (0.024 if len(title_text) <= 50 else 0.021)
            self.info_meta["text"] = f"{mode}{(' // ' + engine) if engine else ''} // {status}"
            self.info_source["text"] = f"PROJECT // {source}"
            catalog_link = str(getattr(record, "link_id", "") or "").startswith("catalog:")
            if launchable:
                action_text = "MOUSE1 // ENTER REALITY"
            elif catalog_link:
                action_text = f"MOUSE1 // LINK {str(record.title).upper()} main.py"
            else:
                action_text = "MOVE/RELINK SOURCE TO RESTORE ACCESS"
            self.info_action["text"] = action_text
            self.info_action["text_fg"] = (0.76, 0.98, 0.92, 0.98) if launchable else (1.0, 0.60, 0.34, 0.96)
            self.info_root.show()
        except Exception:
            pass

    def _task(self, task):
        now = time.monotonic()
        dt = max(0.0, min(0.10, now - self._last_frame_at))
        self._last_frame_at = now
        if getattr(self.host, "active_native_mode", None) is not None or bool(getattr(self.host, "external_suspended", False)):
            self._cached_focus = None
            self._apply_focus_visual(None)
            self._update_info(None)
            return task.cont
        if now >= float(self._next_focus_scan_at):
            self._next_focus_scan_at = now + FOCUS_SCAN_INTERVAL
            self._cached_focus = self._find_focus()
        focused = self._cached_focus
        self._rotate_focused(focused, dt)
        self._apply_focus_visual(focused)
        self._update_info(focused)
        return task.cont

    def activate_focused(self) -> bool:
        if HUB_ORBS_RETIRED:
            return False
        if not self._host_available():
            return False
        focused = self._find_focus()
        if focused is None:
            return False
        record = focused["record"]
        if not bool(record.launchable):
            self._update_info(focused)
            if str(getattr(record, "link_id", "") or "").startswith("catalog:"):
                try:
                    return bool(self.registry.link_catalog_record(record))
                except Exception as exc:
                    print(f"dimension_observatory_relink_failed id={record.dimension_id} err={exc}")
            return True
        try:
            self.registry._mark_seen(record)
        except Exception:
            pass
        print(
            "dimension_observatory_click "
            f"id={record.dimension_id} title={record.title!r} compatibility={record.compatibility} "
            f"native={int(bool(record.native_launchable))}"
        )
        return bool(self.registry._launch(record))
