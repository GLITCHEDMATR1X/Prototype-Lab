from __future__ import annotations

import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AmbientLight,
    CardMaker,
    DirectionalLight,
    Fog,
    Filename,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LineSegs,
    NodePath,
    PerspectiveLens,
    Shader,
    TextNode,
    Texture,
    TransparencyAttrib,
    Vec2,
    Vec3,
    Vec4,
    WindowProperties,
    loadPrcFileData,
)


TITLE = "Glyphbound: The Shattered Shrine"
ROOT = Path(__file__).resolve().parent
SOFTWARE_TEST = "--software-test" in sys.argv
HOLOVERSE_NATIVE_IMPORT = os.environ.get("GLYPHBOUND_HOLOVERSE_NATIVE", "").strip().lower() in {"1", "true", "yes", "on"}

# Standalone owns its Panda window configuration.  A HoloVerse native adapter
# imports this module after the host has already created the one legal ShowBase
# instance, so it must not mutate global PRC window/display settings on import.
if not HOLOVERSE_NATIVE_IMPORT:
    loadPrcFileData("", f"window-title {TITLE} - Pass 24 Native Dimension")
    loadPrcFileData("", "win-size 1600 900")
    loadPrcFileData("", "sync-video true")
    loadPrcFileData("", "show-frame-rate-meter false")
    loadPrcFileData("", "framebuffer-srgb true")
    loadPrcFileData("", "textures-power-2 none")
    loadPrcFileData("", "texture-minfilter linear")
    loadPrcFileData("", "texture-magfilter linear")
    if SOFTWARE_TEST:
        loadPrcFileData("", "load-display p3tinydisplay")
        loadPrcFileData("", "window-type offscreen")
        loadPrcFileData("", "audio-library-name null")
        loadPrcFileData("", "textures-power-2 up")


def _enum(cls, *names):
    """Resolve Panda3D enum spelling across 1.10 builds."""
    for name in names:
        if hasattr(cls, name):
            return getattr(cls, name)
    raise AttributeError(f"{cls.__name__} has none of: {names}")


TEX_LINEAR = _enum(Texture, "FT_linear", "FTLinear")
TEX_CLAMP = _enum(Texture, "WM_clamp", "WMClamp")
MOUSE_ABSOLUTE = _enum(WindowProperties, "M_absolute", "MAbsolute")
TRANS_ALPHA = _enum(TransparencyAttrib, "M_alpha", "MAlpha")


@dataclass
class Settings:
    move_speed: float = 7.2
    sprint_multiplier: float = 1.72
    swim_multiplier: float = 0.52
    mouse_sensitivity: float = 0.105
    eye_height: float = 1.72
    fov: float = 78.0
    max_health: int = 6
    max_stamina: float = 100.0
    max_mana: float = 100.0
    water_z: float = 0.42


@dataclass
class Enemy:
    node: NodePath
    home: Vec3
    kind: str = "beast"
    hp: int = 2
    max_hp: int = 2
    speed: float = 1.7
    damage: int = 1
    attack_range: float = 1.50
    detection_range: float = 18.0
    windup_duration: float = 0.48
    attack_interval: float = 1.05
    ranged: bool = False
    projectile_speed: float = 10.0
    reward: int = 6
    scale_x: float = 1.0
    scale_y: float = 0.78
    scale_z: float = 1.25
    attack_cooldown: float = 0.0
    attack_windup: float = 0.0
    stagger_timer: float = 0.0
    knockback_x: float = 0.0
    knockback_y: float = 0.0
    hit_flash: float = 0.0
    phase: float = 0.0
    alive: bool = True
    stream_chunk: tuple[int, int] | None = None
    spawn_key: tuple | None = None


@dataclass
class MagicProjectile:
    node: NodePath
    velocity: Vec3
    life: float
    damage: int
    radius: float
    friendly: bool
    spell: str


@dataclass
class CombatFx:
    node: NodePath
    velocity: Vec3
    life: float
    duration: float


@dataclass
class LightningFx:
    node: NodePath
    life: float
    duration: float


@dataclass
class Pickup:
    node: NodePath
    kind: str
    value: int
    origin: Vec3
    phase: float
    collected: bool = False


class Glyphbound(ShowBase):
    WORLD_HALF = 278.0  # handcrafted origin-region half-size
    STREAM_CORE_HALF = 268.0
    CHUNK_SIZE = 72.0
    STREAM_RADIUS = 5
    SHRINE_POS = Vec3(18.0, 110.0, 0.0)
    UTOPIA_PORTAL_POS = Vec3(-2.0, -154.0, 0.0)
    UTOPIA_RESPAWN_POS = Vec3(-2.0, -128.0, 0.0)
    UTOPIA_SANCTUARY_RADIUS = 25.0
    UTOPIA_PORTAL_ID = "UTOPIA_FANTASY_GLYPHBOUND"
    LAKE_CENTER = Vec2(-58.0, 30.0)
    LAKE_RADIUS = 31.0

    # Exactly six semantic glyph rows are generated in assets/glyph_atlas.png.
    MATERIAL_NAMES = ("PLANT", "STONE", "EARTH", "WATER", "MAGIC", "CREATURE")
    STYLE_NAMES = ("SEMANTIC", "CLASSIC", "GREENSCREEN")
    GRID_PRESETS = ((136, 76), (176, 99), (220, 124))
    AUDIO_EXTENSIONS = {".wav", ".ogg", ".mp3"}
    SFX_EVENTS = (
        "sword_swing", "sword_hit", "guard", "hurt", "death",
        "enemy_hit", "enemy_die", "demon_cast", "demon_fireball", "cast_arc", "cast_ember",
        "cast_ward", "staff_electric", "magic_impact", "ward_break", "pickup", "sigil",
        "shrine_unlock", "shrine_enter", "weather_rain", "weather_wind", "weather_thunder",
    )

    def __init__(self, host_base=None, hosted_return_callback=None) -> None:
        self.hosted_mode = host_base is not None
        self.host_base = host_base
        self.hosted_return_callback = hosted_return_callback
        self._hosted_cleanup_done = False
        if not self.hosted_mode:
            super().__init__()
            self._showbase = self
        else:
            # HoloVerse already owns the only ShowBase instance and has rebound
            # its conventional camera aliases to a disposable native-dimension
            # camera.  Bind only the host services Glyphbound needs and keep all
            # Glyphbound scene/UI state under removable child roots.
            self._showbase = host_base
            self.win = host_base.win
            self.loader = host_base.loader
            self.taskMgr = host_base.taskMgr
            self.camera = host_base.camera
            self.cam = host_base.cam
            self.camNode = host_base.camNode
            self.camLens = host_base.camLens
            self.mouseWatcherNode = host_base.mouseWatcherNode
            self._host_render = host_base.render
            self._host_render2d = host_base.render2d
            self._host_aspect2d = host_base.aspect2d
            self.render = host_base.render.attachNewNode("glyphbound-native-world")
            self.render2d = host_base.render2d.attachNewNode("glyphbound-native-present")
            self.aspect2d = host_base.aspect2d.attachNewNode("glyphbound-native-hud")
        self._showbase.disableMouse()
        self.software_test = SOFTWARE_TEST and not self.hosted_mode
        self.portal_demo = "--portal-demo" in sys.argv
        self.foundation_demo = "--foundation-demo" in sys.argv
        self.entrance_demo = "--entrance-demo" in sys.argv
        self.city_entrance_demo = "--city-entrance-demo" in sys.argv
        self.portal_handoff_test = "--portal-handoff-test" in sys.argv
        self.no_audio = "--no-audio" in sys.argv or self.software_test
        self.test_shot_path: Path | None = None
        if "--test-shot" in sys.argv:
            try:
                index = sys.argv.index("--test-shot")
                self.test_shot_path = Path(sys.argv[index + 1]).expanduser().resolve()
            except Exception:
                print("[TEST] --test-shot requires an output path")
        self.settings = Settings()
        self.random = random.Random(19870421)
        self.last_frame = time.perf_counter()
        self.heading = 0.0
        self.pitch = -4.0
        self.mouse_locked = True
        self.raw_mode = False
        self.style_mode = 0
        self.grid_index = 1
        self.keys = {k: False for k in ("w", "a", "s", "d", "shift", "up", "down", "left", "right", "block")}

        self.player_pos = Vec3(self.UTOPIA_RESPAWN_POS)
        self.respawn_pos = Vec3(self.UTOPIA_RESPAWN_POS)
        self.last_safe_pos = Vec3(self.player_pos)
        self.utopia_portal_pos = Vec3(self.UTOPIA_PORTAL_POS)
        self.portal_respawn_pos = Vec3(self.UTOPIA_RESPAWN_POS)
        self.portal_transition_timer = 0.0
        self.portal_transition_duration = 1.10
        self.portal_link_ready = False
        self.portal_handoff_requested = False
        self.utopia_portal_parts: list[NodePath] = []
        self.health = self.settings.max_health
        self.stamina = self.settings.max_stamina
        self.mana = self.settings.max_mana
        self.magic_cooldown = 0.0
        self.mana_regen_delay = 0.0
        self.magic_ward_timer = 0.0
        self.magic_ward_charges = 0
        self.cast_flash_timer = 0.0
        self.selected_spell = 0
        self.spell_names = ("ARC BOLT", "EMBER ORB", "WARD RUNE")
        self.currency = 0
        self.sigils = 0
        self.shrine_unlocked = False
        self.prototype_complete = False
        self.in_water = False
        self.velocity = Vec3(0)
        self.bob_phase = 0.0
        self.sword_timer = 0.0
        self.sword_cooldown = 0.0
        self.sword_attack_duration = 0.50
        self.sword_hit_done = False
        self.sword_impact_kick = 0.0
        self.staff_cast_timer = 0.0
        self.staff_cast_duration = 0.36
        self.staff_cooldown = 0.0
        self.staff_arc_cost = 14.0
        self.damage_flash = 0.0
        self.message_timer = 0.0
        self.play_time = 0.0
        self.near_prompt = ""

        # PASS 15 atmosphere simulation. One full in-game day lasts eight real
        # minutes by default, long enough to explore while still making the
        # entire cycle easy to witness during a normal play session.
        self.day_length_seconds = 480.0
        self.time_of_day = 7.25
        self.weather_states = ("CLEAR", "CLOUDY", "RAIN", "STORM")
        self.weather_state = "CLEAR"
        self.weather_timer = 42.0
        self.weather_cloud = 0.0
        self.weather_rain = 0.0
        self.weather_cloud_target = 0.0
        self.weather_rain_target = 0.0
        self.weather_particle_timer = 0.0
        self.storm_lightning_timer = 5.0
        self.lightning_flash = 0.0
        self.weather_lightning_fx: list[tuple[NodePath, float]] = []
        self.rain_drops: list[list[float]] = []

        # PASS 16 streamed-world state.  The authored shrine/canyon remains the
        # origin landmark; everything beyond it is deterministic from world-space
        # chunk coordinates, so walking away can continue without a map edge.
        self.world_seed = 0x6A17B04D
        self.stream_chunks: dict[tuple[int, int], NodePath] = {}
        self.proc_obstacles: dict[tuple[int, int], list[tuple[float, float, float]]] = {}
        self.last_stream_center: tuple[int, int] | None = None
        self.stream_wanted: set[tuple[int, int]] = set()
        self.stream_build_queue: list[tuple[int, int]] = []
        # Build at most one heavy procedural chunk per frame.  The old value of
        # two could cause visible hitches while crossing chunk boundaries.
        self.stream_build_budget = 1
        self.current_biome = "SHRINE VALLEY"
        self.current_place = ""
        self.defeated_stream_spawns: set[tuple] = set()

        self.obstacles: list[tuple[float, float, float]] = []
        self.enemies: list[Enemy] = []
        self.pickups: list[Pickup] = []
        self.combat_fx: list[CombatFx] = []
        self.lightning_fx: list[LightningFx] = []
        self.magic_projectiles: list[MagicProjectile] = []
        self.animated_magic: list[tuple[NodePath, Vec3, float, float]] = []

        # Audio is entirely optional. Empty folders are valid and never block startup.
        self.audio_random = random.Random(time.time_ns())
        self.sfx_library: dict[str, list] = {}
        self.music_files: list[Path] = []
        self.music_current = None
        self.music_current_path: Path | None = None
        self.music_failed: set[Path] = set()
        self.music_index = -1
        self.music_check_timer = 0.0
        self.music_retry_exhausted = False
        self.audio_messages_seen: set[str] = set()
        self.sfx_volume = 0.72
        self.music_volume = 0.30

        # Lightweight runtime throttles. HUD text does not need to rebuild at
        # render-frame frequency, and keeping a clean quit flag prevents repeated
        # shutdown requests from event callbacks.
        self.hud_update_timer = 0.0
        self._quitting = False

        self._configure_window()
        self._setup_lighting_and_fog()
        self._build_world()
        if self.portal_demo:
            self.player_pos = Vec3(self.portal_respawn_pos)
            self.last_safe_pos = Vec3(self.portal_respawn_pos)
            self.heading = 180.0
            self.pitch = -5.0
        elif self.foundation_demo or self.entrance_demo or self.city_entrance_demo:
            # Deterministic QA viewpoint: this Luminous Marsh village sits on a
            # deliberately uneven footprint and exposes structure/terrain seams well.
            if self.city_entrance_demo:
                demo_x, demo_y = self._settlement_center(-6, -8)
                self.player_pos = Vec3(demo_x, demo_y - 18.0, 0.0)
                self.heading = 0.0
                self.pitch = -5.0
                self.last_safe_pos = Vec3(self.player_pos)
                self._update_world_stream(force=True)
            else:
                demo_x, demo_y = self._settlement_center(-5, -1)
            if not self.city_entrance_demo:
                if self.entrance_demo:
                    # Closer view of the village threshold.  It keeps the same
                    # chunk/seed as foundation QA while making door, landing and seal
                    # readability easy to inspect without walking through progression.
                    self.player_pos = Vec3(demo_x + 3.5, demo_y + 1.2, 0.0)
                    self.heading = 90.0
                    self.pitch = -4.0
                else:
                    self.player_pos = Vec3(demo_x, demo_y - 23.0, 0.0)
                    self.heading = 0.0
                    self.pitch = -6.0
                self.last_safe_pos = Vec3(self.player_pos)
                self._update_world_stream(force=True)
        self._build_capture_pipeline()
        self._build_weather_system()
        self._build_first_person_weapon()
        self._build_hud()
        if not self.no_audio:
            self._setup_audio()
        self._bind_controls()
        if not self.software_test:
            self._capture_mouse()
        self._sync_camera()

        if not self.hosted_mode:
            self.taskMgr.add(self._update, "glyphbound-update", sort=10)
            if self.test_shot_path is not None:
                self.taskMgr.doMethodLater(1.25, self._capture_test_shot, "glyphbound-test-shot")
            if self.portal_handoff_test:
                self.taskMgr.doMethodLater(0.35, self._run_portal_handoff_test, "glyphbound-portal-handoff-test")

    # ------------------------------------------------------------------
    # Window / render pipeline
    # ------------------------------------------------------------------
    def _configure_window(self) -> None:
        if not self.hosted_mode:
            props = WindowProperties()
            props.setTitle(f"{TITLE} - Pass 24 HoloVerse Native Dimension")
            props.setSize(1600, 900)
            if not self.software_test and hasattr(self.win, "requestProperties"):
                self.win.requestProperties(props)
        self._showbase.setBackgroundColor(0.004, 0.008, 0.022, 1)
        if not self.software_test:
            self.camNode.setActive(False)

    def _setup_lighting_and_fog(self) -> None:
        self.render.setShaderAuto()

        ambient = AmbientLight("ambient")
        ambient.setColor(Vec4(0.22, 0.24, 0.31, 1))
        self.ambient_light = ambient
        self.ambient_np = self.render.attachNewNode(ambient)
        self.render.setLight(self.ambient_np)

        sun = DirectionalLight("moon-sun")
        sun.setColor(Vec4(0.92, 0.97, 1.08, 1))
        self.sun_light = sun
        self.sun_np = self.render.attachNewNode(sun)
        self.sun_np.setHpr(-28, -56, -8)
        self.render.setLight(self.sun_np)

        fog = Fog("blue-distance")
        fog.setColor(0.020, 0.045, 0.105)
        fog.setLinearRange(145.0, 505.0)
        self.fog = fog
        self.render.setFog(fog)

    def _build_capture_pipeline(self) -> None:
        if self.software_test:
            # TinyDisplay has no GLSL path. For deterministic container QA we
            # render the same real scene directly, verifying geometry, camera,
            # HUD, portal composition, and culling without pretending to verify
            # the final ASCII post-process.
            self.scene_cam = self.camera
            self.scene_buffer = self.win
            self.present_card = NodePath("software-test-present")
            return

        self.scene_tex = Texture("world-color")
        self.scene_buffer = self.win.makeTextureBuffer("world-buffer", 1280, 720, self.scene_tex, True)
        self.scene_buffer.setClearColor(Vec4(0.004, 0.008, 0.022, 1))

        lens = PerspectiveLens()
        lens.setFov(self.settings.fov)
        lens.setNearFar(0.06, 920.0)
        self.scene_cam = self._showbase.makeCamera(self.scene_buffer, lens=lens, scene=self.render)
        # makeCamera() parents new cameras under the ShowBase camera. When Glyphbound is
        # hosted, that is the host's player camera (Utopia Vision: hundreds of metres away,
        # pitched), which offset every Glyphbound view. The scene camera must live in
        # Glyphbound's own world root so _sync_camera() positions are world positions,
        # and so shutdown removes it together with that root.
        self.scene_cam.reparentTo(self.render)

        atlas_path = ROOT / "assets" / "glyph_atlas.png"
        if not atlas_path.is_file():
            raise RuntimeError(f"Glyph atlas is missing: {atlas_path}")

        # Panda3D uses its own Filename syntax internally.  Passing a raw
        # Windows Path string (C:\\...) can be interpreted as a Panda virtual
        # path, so always translate native OS paths explicitly first.
        atlas_filename = Filename.fromOsSpecific(str(atlas_path))
        self.glyph_tex = self.loader.loadTexture(atlas_filename)
        if not self.glyph_tex:
            raise RuntimeError(f"Could not load glyph atlas: {atlas_filename}")
        self.glyph_tex.setMinfilter(TEX_LINEAR)
        self.glyph_tex.setMagfilter(TEX_LINEAR)
        self.glyph_tex.setWrapU(TEX_CLAMP)
        self.glyph_tex.setWrapV(TEX_CLAMP)

        cm = CardMaker("ascii-present")
        cm.setFrameFullscreenQuad()
        self.present_card = self.render2d.attachNewNode(cm.generate())
        self.present_card.setDepthTest(False)
        self.present_card.setDepthWrite(False)
        self.present_card.setBin("background", -100)

        vertex_shader = r"""
#version 130
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
uniform mat4 p3d_ModelViewProjectionMatrix;
out vec2 uv;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_MultiTexCoord0;
}
"""
        fragment_shader = r"""
#version 130
uniform sampler2D scene_tex;
uniform sampler2D glyph_tex;
uniform vec2 grid_size;
uniform float star_amount;
uniform float atlas_columns;
uniform float atlas_rows;
uniform float ascii_enabled;
uniform float style_mode;
uniform float pulse;
in vec2 uv;
out vec4 fragColor;

float luminance(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

float materialRow(vec3 c) {
    float hi = max(c.r, max(c.g, c.b));
    float lo = min(c.r, min(c.g, c.b));

    // Purple/pink emissive objects are magic.
    if (c.r > 0.24 && c.b > 0.30 && c.g < max(c.r, c.b) * 0.78) return 4.0;
    // Red/orange dominated moving objects are creatures.
    if (c.r > c.g * 1.72 && c.r > c.b * 1.48 && c.r > 0.22) return 5.0;
    // Strong blue/cyan is water.
    if (c.b > c.r * 1.30 && c.b > c.g * 1.08 && c.b > 0.14) return 3.0;
    // Vegetation is strongly green.
    if (c.g > c.r * 1.12 && c.g > c.b * 0.95 && c.g > 0.12) return 0.0;
    // Warm ochre/brown path and soil.
    if (c.r > c.b * 1.34 && c.g > c.b * 1.18 && c.r > 0.14) return 2.0;
    return 1.0;
}

float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

void main() {
    vec3 raw = texture(scene_tex, uv).rgb;
    if (ascii_enabled < 0.5) {
        fragColor = vec4(raw, 1.0);
        return;
    }

    vec2 cell = floor(uv * grid_size);
    vec2 local = fract(uv * grid_size);
    vec2 center_uv = (cell + vec2(0.5)) / grid_size;

    vec3 c = texture(scene_tex, center_uv).rgb;
    float lum = luminance(c);

    // Neighbor contrast keeps cliffs, trees, weapons and silhouettes readable.
    vec2 px = 1.0 / grid_size;
    float lx = luminance(texture(scene_tex, center_uv + vec2(px.x, 0.0)).rgb);
    float ly = luminance(texture(scene_tex, center_uv + vec2(0.0, px.y)).rgb);
    float edge = min(0.28, abs(lum - lx) + abs(lum - ly));
    float density = clamp(pow(lum, 0.72) + edge * 1.35, 0.0, 1.0);

    float row = materialRow(c);
    if (style_mode > 0.5 && style_mode < 1.5) row = 1.0; // classic one-ramp ASCII

    float glyph_index = floor(density * (atlas_columns - 1.0) + 0.001);
    vec2 guv;
    guv.x = (glyph_index + local.x) / atlas_columns;
    guv.y = (row + (1.0 - local.y)) / atlas_rows;
    float glyph = texture(glyph_tex, guv).r;

    // Suppress very dark cells, but leave a sparse blue star/noise texture in the sky.
    float speck = step(0.9935, hash21(cell + floor(pulse * 0.05))) * (1.0 - smoothstep(0.02, 0.07, lum)) * star_amount;
    glyph = max(glyph * smoothstep(0.010, 0.045, density), speck * 0.48);

    vec3 chroma = c / max(0.10, max(c.r, max(c.g, c.b)));
    vec3 fg = clamp(c * 2.15 + chroma * 0.16, 0.0, 1.0);

    if (style_mode > 1.5) {
        float mono = clamp(lum * 2.7 + edge, 0.08, 1.0);
        fg = vec3(0.20, 1.0, 0.34) * mono;
    }

    vec3 bg = vec3(0.0015, 0.0030, 0.0090);
    vec3 outc = mix(bg, fg, clamp(glyph * 1.18, 0.0, 1.0));
    fragColor = vec4(outc, 1.0);
}
"""
        shader = Shader.make(Shader.SL_GLSL, vertex=vertex_shader, fragment=fragment_shader)
        self.present_card.setShader(shader)
        self.present_card.setShaderInput("scene_tex", self.scene_tex)
        self.present_card.setShaderInput("glyph_tex", self.glyph_tex)
        self.present_card.setShaderInput("atlas_columns", 16.0)
        self.present_card.setShaderInput("atlas_rows", 6.0)
        self.present_card.setShaderInput("ascii_enabled", 1.0)
        self.present_card.setShaderInput("style_mode", float(self.style_mode))
        self.present_card.setShaderInput("star_amount", 0.0)
        self._apply_grid_size()

    def _apply_grid_size(self) -> None:
        cols, rows = self.GRID_PRESETS[self.grid_index]
        if not getattr(self, "software_test", False):
            self.present_card.setShaderInput("grid_size", Vec2(float(cols), float(rows)))

    # ------------------------------------------------------------------
    # World construction
    # ------------------------------------------------------------------
    def _build_world(self) -> None:
        self.terrain = self._make_terrain()
        self.terrain.reparentTo(self.render)

        self._build_water()
        self._build_forest()
        self._build_rocks_and_ruins()
        self._build_canyon_region()
        self._build_shrine()
        self._build_demon_rifts()
        self._build_stars()
        self._build_utopia_portal()
        self._spawn_pickups()
        self._spawn_enemies()
        self._update_world_stream(force=True)

    def _in_utopia_sanctuary(self, x: float, y: float, margin: float = 0.0) -> bool:
        radius = self.UTOPIA_SANCTUARY_RADIUS + margin
        return math.hypot(x - self.UTOPIA_PORTAL_POS.x, y - self.UTOPIA_PORTAL_POS.y) <= radius

    def _canyon_factor(self, x: float, y: float) -> float:
        """Blend from the original green shrine valley into the expanded high-desert canyons."""
        def smooth01(v: float) -> float:
            v = max(0.0, min(1.0, v))
            return v * v * (3.0 - 2.0 * v)

        east_west = smooth01((abs(x) - 138.0) / 72.0)
        north = smooth01((y - 138.0) / 72.0)
        south = smooth01((-y - 166.0) / 64.0)
        return max(east_west, north, south)

    def _canyon_trail_distance(self, x: float, y: float) -> float:
        """Distance to the three sandy routes that lead out of the shrine valley."""
        best = 9999.0

        if 104.0 <= y <= 270.0:
            tx = 18.0 + 34.0 * math.sin((y - 108.0) * 0.020) + 7.0 * math.sin((y - 108.0) * 0.051)
            best = min(best, abs(x - tx))

        if 132.0 <= x <= 270.0:
            u = x - 132.0
            ty = -18.0 + 0.48 * u + 17.0 * math.sin(u * 0.038 + 0.35)
            best = min(best, abs(y - ty))

        if -270.0 <= x <= -132.0:
            u = -x - 132.0
            ty = -34.0 + 0.42 * u + 15.0 * math.sin(u * 0.041 + 1.25)
            best = min(best, abs(y - ty))

        return best

    def _legacy_height(self, x: float, y: float) -> float:
        """Pass-14 authored origin heightfield, retained as the central landmark region."""
        canyon = self._canyon_factor(x, y)

        # The original valley remains a readable green basin around the shrine route.
        h = (
            0.52 * math.sin(x * 0.030)
            + 0.38 * math.cos(y * 0.025)
            + 0.26 * math.sin((x + y) * 0.052)
            + 0.18 * math.cos((x - y) * 0.071)
        )

        # Long mountain shoulders still frame the old valley, but fade into the new
        # sandstone region rather than becoming the outer edge of the world.
        side = min(1.0, max(0.0, (abs(x) - 72.0) / 88.0))
        h += side * side * 13.5 * (1.0 - canyon * 0.88)
        north = min(1.0, max(0.0, (y - 72.0) / 88.0))
        h += north * north * 7.0 * (0.42 + 0.58 * min(1.0, abs(x) / 95.0)) * (1.0 - canyon * 0.82)

        road_dist = abs(x - self._path_x(y))
        if road_dist < 22.0 and -142.0 < y < 122.0:
            trough = max(0.0, 1.0 - road_dist / 22.0)
            h -= trough * trough * 0.85

        # Existing lake and island are preserved inside the lush central valley.
        dx = x - self.LAKE_CENTER.x
        dy = y - self.LAKE_CENTER.y
        d = math.hypot(dx, dy)
        if d < self.LAKE_RADIUS + 11.0:
            bowl = max(0.0, 1.0 - d / (self.LAKE_RADIUS + 11.0))
            h -= bowl * bowl * 7.1
            island = max(0.0, 1.0 - d / 7.6)
            h += island * island * 9.4

        # The shrine remains on its broad green shelf.
        sd = math.hypot(x - self.SHRINE_POS.x, y - self.SHRINE_POS.y)
        if sd < 34.0:
            blend = max(0.0, 1.0 - sd / 34.0)
            blend = blend * blend * (3.0 - 2.0 * blend)
            target = 5.6 + max(0.0, (y - 92.0) * 0.018)
            h = h * (1.0 - blend) + target * blend

        # Outside the valley, the terrain becomes a wide high-desert floor.  Huge
        # formations are built separately, so the floor stays navigable between them.
        if canyon > 0.0:
            desert = (
                1.10
                + 0.72 * math.sin(x * 0.017 + y * 0.010)
                + 0.58 * math.cos(y * 0.023 - x * 0.006)
                + 0.34 * math.sin((x - y) * 0.041)
            )

            # Soft shelves and eroded benches create long canyon contours without
            # trapping the player in procedural spikes.
            shelf_wave = 0.5 + 0.5 * math.sin(abs(x) * 0.031 + y * 0.013)
            shelf = max(0.0, shelf_wave - 0.58) * 5.3
            desert += shelf * shelf

            # A broad wandering wash keeps the high desert from reading as a flat plane.
            wash_x = 52.0 * math.sin(y * 0.0105) + 18.0 * math.sin(y * 0.027)
            wash_d = abs(x - wash_x)
            if wash_d < 48.0:
                wash = 1.0 - wash_d / 48.0
                desert -= wash * wash * 1.25

            h = h * (1.0 - canyon) + desert * canyon

        # Sandy routes branch out from the old valley into the expanded canyons.
        cdist = self._canyon_trail_distance(x, y)
        if cdist < 17.0 and canyon > 0.08:
            trail = max(0.0, 1.0 - cdist / 17.0)
            h -= trail * trail * 0.55 * canyon

        return h

    # ------------------------------------------------------------------
    # Pass 16: deterministic infinite-world field
    # ------------------------------------------------------------------
    @staticmethod
    def _smooth01(value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value * value * (3.0 - 2.0 * value)

    def _coord_hash(self, x: int, y: int, salt: int = 0) -> float:
        # Integer hash: stable across Python launches (unlike hash()).
        n = (x * 0x1F123BB5) ^ (y * 0x5F356495) ^ self.world_seed ^ (salt * 0x45D9F3B)
        n = (n ^ (n >> 16)) * 0x45D9F3B
        n = (n ^ (n >> 16)) * 0x45D9F3B
        n = n ^ (n >> 16)
        return (n & 0xFFFFFFFF) / 4294967295.0

    def _chunk_seed(self, cx: int, cy: int, salt: int = 0) -> int:
        return int(self._coord_hash(cx, cy, salt) * 0x7FFFFFFF) ^ (salt * 1315423911)

    def _biome_at(self, x: float, y: float) -> str:
        if max(abs(x), abs(y)) < 232.0:
            return "SHRINE VALLEY"
        # Slow, continuous climate waves make regions large enough to feel like
        # destinations instead of changing biome every chunk.
        heat = (
            0.50
            + 0.24 * math.sin(x * 0.00175 + y * 0.00063)
            + 0.18 * math.cos(y * 0.00215 - x * 0.00041)
            + 0.08 * math.sin((x + y) * 0.0043)
        )
        wet = (
            0.50
            + 0.26 * math.sin(y * 0.00193 + 1.7)
            + 0.19 * math.cos(x * 0.00231 - 0.8)
            + 0.08 * math.sin((x - y) * 0.0047)
        )
        rugged = 0.5 + 0.5 * math.sin(x * 0.00111 - y * 0.00139 + math.sin(y * 0.0009) * 1.5)
        if heat > 0.72 and wet < 0.42:
            return "SUNSTONE DESERT" if rugged < 0.58 else "RED CANYONS"
        if heat < 0.30:
            return "FROST HIGHLANDS"
        if wet > 0.70:
            return "EMERALD FOREST" if heat > 0.38 else "MISTWOOD"
        if wet < 0.31 and rugged > 0.68:
            return "ASH WASTES"
        if wet > 0.58 and rugged < 0.37:
            return "LUMINOUS MARSH"
        return "GOLDEN STEPPE"

    def _river_info(self, x: float, y: float) -> tuple[float, float]:
        """Distance + local width for a globally continuous river/tributary network."""
        spacing = 520.0
        lane = int(round(x / spacing))
        phase = self._coord_hash(lane, 0, 71) * math.tau
        center_x = lane * spacing + 62.0 * math.sin(y * 0.0060 + phase) + 18.0 * math.sin(y * 0.017 + phase * 1.7)
        d_main = abs(x - center_x)
        main_w = 8.0 + 2.8 * (0.5 + 0.5 * math.sin(y * 0.0083 + phase))

        # Long east-west tributaries cross the main channels and therefore join them
        # rather than terminating at chunk edges.
        tspacing = 760.0
        band = int(round(y / tspacing))
        tphase = self._coord_hash(0, band, 83) * math.tau
        center_y = band * tspacing + 44.0 * math.sin(x * 0.0041 + tphase) + 13.0 * math.sin(x * 0.0127 + tphase * 0.7)
        d_trib = abs(y - center_y)
        trib_w = 5.2 + 1.8 * (0.5 + 0.5 * math.cos(x * 0.009 + tphase))
        if d_trib / trib_w < d_main / main_w:
            return d_trib, trib_w
        return d_main, main_w

    def _road_centers(self, x: float, y: float) -> tuple[float, float]:
        """Return the nearest continuous north/south road x and east/west road y."""
        spacing_x = 342.0
        lane_x = int(round(x / spacing_x))
        phase_x = self._coord_hash(lane_x, 0, 117) * math.tau
        road_x = (
            lane_x * spacing_x
            + 26.0 * math.sin(y * 0.0048 + phase_x)
            + 7.0 * math.sin(y * 0.013 + phase_x * 1.7)
        )

        spacing_y = 418.0
        lane_y = int(round(y / spacing_y))
        phase_y = self._coord_hash(0, lane_y, 123) * math.tau
        road_y = (
            lane_y * spacing_y
            + 22.0 * math.sin(x * 0.0042 + phase_y)
            + 6.5 * math.sin(x * 0.012 + phase_y * 0.9)
        )
        return road_x, road_y

    def _road_info(self, x: float, y: float) -> tuple[float, float]:
        road_x, road_y = self._road_centers(x, y)
        dx = abs(x - road_x)
        dy = abs(y - road_y)
        width_x = 3.2 + 0.55 * (0.5 + 0.5 * math.sin(y * 0.011))
        width_y = 3.0 + 0.50 * (0.5 + 0.5 * math.cos(x * 0.010))
        if dx / width_x < dy / width_y:
            return dx, width_x
        return dy, width_y

    def _settlement_kind(self, cx: int, cy: int) -> str:
        center_x = (cx + 0.5) * self.CHUNK_SIZE
        center_y = (cy + 0.5) * self.CHUNK_SIZE
        if max(abs(center_x), abs(center_y)) < self.STREAM_CORE_HALF + 42.0:
            return ""
        roll = self._coord_hash(cx, cy, 139)
        if roll < 0.018:
            return "CITY"
        if roll < 0.087:
            return "VILLAGE"
        return ""

    def _settlement_center(self, cx: int, cy: int) -> tuple[float, float]:
        rng = random.Random(self._chunk_seed(cx, cy, 151))
        x0 = cx * self.CHUNK_SIZE
        y0 = cy * self.CHUNK_SIZE
        x = x0 + self.CHUNK_SIZE * 0.5 + rng.uniform(-10.0, 10.0)
        y = y0 + self.CHUNK_SIZE * 0.5 + rng.uniform(-10.0, 10.0)
        road_x, road_y = self._road_centers(x, y)
        # Settlements sit on the nearest through-road so roads remain useful
        # navigation features rather than unrelated decorative lines.
        if abs(road_x - x) <= abs(road_y - y):
            x = road_x
        else:
            y = road_y
        x = max(x0 + 9.0, min(x0 + self.CHUNK_SIZE - 9.0, x))
        y = max(y0 + 9.0, min(y0 + self.CHUNK_SIZE - 9.0, y))
        return x, y

    def _settlement_name(self, cx: int, cy: int, kind: str) -> str:
        first = (
            "AMBER", "ASH", "BRIGHT", "CEDAR", "CINDER", "DUSK", "EMBER", "FROST",
            "GOLD", "MIST", "MOON", "RUNE", "SAGE", "STONE", "SUN", "THORN",
        )
        second = (
            "FORD", "HAVEN", "HOLLOW", "KEEP", "MARCH", "REST", "RIDGE", "ROOK",
            "SPIRE", "VALE", "WATCH", "WELL", "GATE", "CROSS", "FIELD", "FALL",
        )
        a = int(self._coord_hash(cx, cy, 157) * len(first)) % len(first)
        b = int(self._coord_hash(cx, cy, 163) * len(second)) % len(second)
        base = f"{first[a]} {second[b]}"
        return f"{base} CITY" if kind == "CITY" else base

    def _landmark_kind(self, cx: int, cy: int) -> str:
        if self._settlement_kind(cx, cy):
            return ""
        center_x = (cx + 0.5) * self.CHUNK_SIZE
        center_y = (cy + 0.5) * self.CHUNK_SIZE
        if max(abs(center_x), abs(center_y)) < self.STREAM_CORE_HALF + 60.0:
            return ""
        roll = self._coord_hash(cx, cy, 173)
        distance_chunks = math.hypot(cx, cy)
        if distance_chunks > 6.0 and roll < 0.012:
            return "DRAGON NEST"
        if roll < 0.037:
            return "RUNE ARCH"
        if roll < 0.060:
            return "STONE CIRCLE"
        if roll < 0.082:
            return "OLD WATCHTOWER"
        return ""

    def _landmark_center(self, cx: int, cy: int) -> tuple[float, float]:
        x0 = cx * self.CHUNK_SIZE
        y0 = cy * self.CHUNK_SIZE
        rng = random.Random(self._chunk_seed(cx, cy, 181))
        candidates = [
            (x0 + self.CHUNK_SIZE * 0.5, y0 + self.CHUNK_SIZE * 0.5)
        ]
        for _ in range(8):
            candidates.append((
                x0 + rng.uniform(14.0, self.CHUNK_SIZE - 14.0),
                y0 + rng.uniform(14.0, self.CHUNK_SIZE - 14.0),
            ))
        for x, y in candidates:
            road_dist, road_width = self._road_info(x, y)
            if self._river_water_z(x, y) is None and road_dist > road_width * 1.8:
                return x, y
        return candidates[0]

    def _nearest_place(self, x: float, y: float) -> str:
        cx = int(math.floor(x / self.CHUNK_SIZE))
        cy = int(math.floor(y / self.CHUNK_SIZE))
        best_name = ""
        best_dist = 9999.0
        for oy in range(-1, 2):
            for ox in range(-1, 2):
                scx, scy = cx + ox, cy + oy
                kind = self._settlement_kind(scx, scy)
                if kind:
                    sx, sy = self._settlement_center(scx, scy)
                    d = math.hypot(x - sx, y - sy)
                    if d < best_dist and d < (58.0 if kind == "CITY" else 40.0):
                        best_dist = d
                        best_name = self._settlement_name(scx, scy, kind)
                landmark = self._landmark_kind(scx, scy)
                if landmark:
                    lx, ly = self._landmark_center(scx, scy)
                    d = math.hypot(x - lx, y - ly)
                    if d < best_dist and d < 35.0:
                        best_dist = d
                        best_name = landmark
        return best_name

    def _procedural_land_height_for_biome(self, x: float, y: float, biome: str) -> float:
        broad = 0.85 * math.sin(x * 0.0107) + 0.72 * math.cos(y * 0.0091) + 0.45 * math.sin((x + y) * 0.017)
        detail = 0.28 * math.sin(x * 0.043 - y * 0.031) + 0.18 * math.cos((x - y) * 0.061)
        if biome == "SUNSTONE DESERT":
            return 1.0 + broad * 0.55 + 0.65 * abs(math.sin(x * 0.021 + y * 0.013))
        if biome == "RED CANYONS":
            shelves = (0.5 + 0.5 * math.sin(x * 0.0082 + y * 0.0057)) ** 3
            return 2.4 + broad * 0.8 + shelves * 7.5 + detail
        if biome == "FROST HIGHLANDS":
            ridges = abs(math.sin(x * 0.008 - y * 0.005)) ** 2
            return 4.2 + broad * 1.8 + ridges * 6.8 + detail
        if biome == "EMERALD FOREST":
            return 1.7 + broad * 1.0 + detail * 0.7
        if biome == "MISTWOOD":
            return 1.1 + broad * 0.75 + detail * 0.45
        if biome == "ASH WASTES":
            crags = max(0.0, math.sin(x * 0.012 + y * 0.009)) ** 4
            return 2.7 + broad * 1.15 + crags * 5.8 + detail
        if biome == "LUMINOUS MARSH":
            return 0.35 + broad * 0.30 + detail * 0.18
        return 1.2 + broad * 0.70 + detail * 0.55

    def _procedural_land_height(self, x: float, y: float) -> float:
        # Blend neighboring climate samples so biome borders become broad ecotones
        # rather than hard height seams between two procedural formulas.
        samples = (
            (x, y, 0.44),
            (x + 34.0, y, 0.14),
            (x - 34.0, y, 0.14),
            (x, y + 34.0, 0.14),
            (x, y - 34.0, 0.14),
        )
        height = 0.0
        for sx, sy, weight in samples:
            height += self._procedural_land_height_for_biome(x, y, self._biome_at(sx, sy)) * weight
        return height

    def _procedural_height(self, x: float, y: float) -> float:
        land = self._procedural_land_height(x, y)
        dist, width = self._river_info(x, y)
        if dist < width * 2.5:
            bank = self._smooth01(1.0 - dist / (width * 2.5))
            land -= bank * (1.25 + width * 0.055)
        if dist < width:
            channel = self._smooth01(1.0 - dist / width)
            land -= 1.05 + channel * 0.55
        return land

    def _height(self, x: float, y: float) -> float:
        # Preserve the authored starting country, then blend seamlessly into the
        # deterministic field used by every streamed chunk.
        edge = max(abs(x), abs(y))
        if edge <= 228.0:
            return self._legacy_height(x, y)
        proc = self._procedural_height(x, y)
        if edge >= self.WORLD_HALF:
            base = proc
        else:
            legacy = self._legacy_height(x, y)
            blend = self._smooth01((edge - 228.0) / (self.WORLD_HALF - 228.0))
            base = legacy * (1.0 - blend) + proc * blend

        # Continuous roads become shallow raised causeways where they cross rivers.
        # This makes the visible road bridge actually traversable instead of forcing
        # the player to swim through geometry that looks like a bridge.
        road_dist, road_width = self._road_info(x, y)
        if road_dist < road_width * 1.08:
            water = self._river_water_z(x, y)
            if water is not None:
                base = max(base, water + 0.34)
        return base

    def _sample_footprint_heights(
        self,
        x: float,
        y: float,
        half_x: float,
        half_y: float,
        heading: float = 0.0,
    ) -> list[float]:
        """Sample terrain beneath a structure in its own footprint frame.

        The center, corners and edge midpoints are transformed by the authored
        heading before height lookup.  Structure placement therefore derives from
        the same real terrain that the player walks on rather than one guessed
        center-point height.
        """
        angle = math.radians(heading)
        ca = math.cos(angle)
        sa = math.sin(angle)
        local_points = (
            (0.0, 0.0),
            (-half_x, -half_y), (half_x, -half_y),
            (half_x, half_y), (-half_x, half_y),
            (-half_x, 0.0), (half_x, 0.0),
            (0.0, -half_y), (0.0, half_y),
        )
        heights: list[float] = []
        for lx, ly in local_points:
            wx = x + lx * ca - ly * sa
            wy = y + lx * sa + ly * ca
            heights.append(self._height(wx, wy))
        return heights

    def _add_terrain_foundation(
        self,
        root: NodePath,
        name: str,
        x: float,
        y: float,
        half_x: float,
        half_y: float,
        color: Vec4,
        heading: float = 0.0,
    ) -> tuple[float, float]:
        """Create a terrain-following structural plinth and return its top Z.

        The upper face clears the highest terrain sample under the footprint.
        The lower face embeds below the lowest sample, so a building cannot float
        on the downhill side or expose a daylight seam as the terrain slopes away.
        Deep foundations receive a small wider lower course to read as intentional
        masonry instead of a single suspended box.
        """
        heights = self._sample_footprint_heights(x, y, half_x, half_y, heading)
        low = min(heights)
        high = max(heights)
        top = high + 0.055
        bottom = low - 0.22
        depth = max(0.26, top - bottom)

        # Main plinth is kept just inside the visual wall footprint.  A slightly
        # wider buried course appears only on meaningful slopes and breaks up tall
        # exposed foundation faces without increasing normal flat-ground clutter.
        main_bottom = bottom
        if depth > 0.72:
            lower_top = min(top - 0.24, bottom + max(0.26, depth * 0.42))
            lower_half_z = max(0.13, (lower_top - bottom) * 0.5)
            lower = self._make_box(
                f"{name}-lower-course",
                Vec3(half_x * 1.08, half_y * 1.08, lower_half_z),
                Vec4(color.x * 0.82, color.y * 0.82, color.z * 0.82, 1.0),
            )
            lower.reparentTo(root)
            lower.setPos(x, y, bottom + lower_half_z)
            lower.setH(heading)
            main_bottom = lower_top - 0.03

        half_z = max(0.13, (top - main_bottom) * 0.5)
        foundation = self._make_box(
            name,
            Vec3(half_x * 1.025, half_y * 1.025, half_z),
            color,
        )
        foundation.reparentTo(root)
        foundation.setPos(x, y, main_bottom + half_z)
        foundation.setH(heading)
        return top, high - low

    def _biome_ground_dressing_color(self, x: float, y: float) -> Vec4:
        """Return a restrained ground color that belongs to the local biome."""
        palette = {
            "EMERALD FOREST": Vec4(0.40, 0.27, 0.075, 1),
            "MISTWOOD": Vec4(0.31, 0.25, 0.12, 1),
            "FROST HIGHLANDS": Vec4(0.46, 0.43, 0.36, 1),
            "RED CANYONS": Vec4(0.54, 0.30, 0.14, 1),
            "SUNSTONE DESERT": Vec4(0.61, 0.43, 0.15, 1),
            "LUMINOUS MARSH": Vec4(0.31, 0.26, 0.085, 1),
            "ASH WASTES": Vec4(0.27, 0.24, 0.22, 1),
            "GOLDEN STEPPE": Vec4(0.52, 0.37, 0.085, 1),
        }
        return palette.get(self._biome_at(x, y), Vec4(0.46, 0.33, 0.09, 1))

    def _add_ground_ribbon(
        self,
        root: NodePath,
        name: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        width: float,
        color: Vec4,
    ) -> bool:
        """Lay a narrow worn-ground strip directly on sampled terrain.

        This is deliberately real terrain-following geometry, not a flat decal.
        Both ribbon edges sample the authoritative world height, so approaches
        remain attached on side-slopes and streamed terrain.
        """
        dx = end_x - start_x
        dy = end_y - start_y
        length = math.hypot(dx, dy)
        if length < 0.85:
            return False
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        segments = max(2, min(20, int(math.ceil(length / 1.15))))

        # Do not paint paths over real water.  A later bridge/path pass can make
        # that crossing intentionally rather than hiding it with a ground strip.
        for i in range(segments + 1):
            t = i / segments
            sx = start_x + dx * t
            sy = start_y + dy * t
            if self._river_water_z(sx, sy) is not None:
                return False

        fmt = GeomVertexFormat.getV3n3c4()
        data = GeomVertexData(name, fmt, Geom.UHStatic)
        v = GeomVertexWriter(data, "vertex")
        n = GeomVertexWriter(data, "normal")
        c = GeomVertexWriter(data, "color")
        prim = GeomTriangles(Geom.UHStatic)

        for i in range(segments + 1):
            t = i / segments
            cx = start_x + dx * t
            cy = start_y + dy * t
            # A slight taper keeps the strip from looking like a road stencil.
            half_w = width * (0.74 + 0.16 * math.sin(t * math.pi))
            for side in (-1.0, 1.0):
                sx = cx + px * half_w * side
                sy = cy + py * half_w * side
                sz = self._height(sx, sy) + 0.070
                v.addData3(sx, sy, sz)
                n.addData3(0, 0, 1)
                shade = 0.94 if side < 0 else 1.0
                c.addData4(Vec4(color.x * shade, color.y * shade, color.z * shade, 1.0))

        for i in range(segments):
            a = i * 2
            b = a + 1
            d = a + 2
            e = a + 3
            prim.addVertices(a, d, b)
            prim.addVertices(b, d, e)

        geom = Geom(data)
        geom.addPrimitive(prim)
        node = GeomNode(name)
        node.addGeom(geom)
        np = root.attachNewNode(node)
        np.setTwoSided(True)
        np.setDepthOffset(1)
        return True

    def _add_foundation_toe(
        self,
        root: NodePath,
        name: str,
        x: float,
        y: float,
        half_x: float,
        half_y: float,
        top_z: float,
        color: Vec4,
        heading: float = 0.0,
    ) -> int:
        """Add sparse retaining stones only along a meaningfully exposed low edge."""
        angle = math.radians(heading)
        ca, sa = math.cos(angle), math.sin(angle)
        edges = (
            ((-half_x, 0.0), (0.0, 1.0), half_y),
            ((half_x, 0.0), (0.0, 1.0), half_y),
            ((0.0, -half_y), (1.0, 0.0), half_x),
            ((0.0, half_y), (1.0, 0.0), half_x),
        )
        candidates = []
        for (lx, ly), tangent, span in edges:
            wx = x + lx * ca - ly * sa
            wy = y + lx * sa + ly * ca
            candidates.append((self._height(wx, wy), lx, ly, tangent, span))
        edge_z, lx, ly, tangent, span = min(candidates, key=lambda item: item[0])
        exposure = top_z - edge_z
        if exposure < 0.62:
            return 0

        # Transform the chosen local edge and tangent to world space.
        ex = x + lx * ca - ly * sa
        ey = y + lx * sa + ly * ca
        tx = tangent[0] * ca - tangent[1] * sa
        ty = tangent[0] * sa + tangent[1] * ca
        # Outward normal is the edge's local center direction.
        nl = math.hypot(lx, ly)
        nx_l, ny_l = (lx / nl, ly / nl) if nl > 1e-6 else (0.0, -1.0)
        nx = nx_l * ca - ny_l * sa
        ny = nx_l * sa + ny_l * ca

        count = 3 if span >= 1.8 else 2
        made = 0
        for i in range(count):
            offset = 0.0 if count == 1 else ((i / (count - 1)) * 2.0 - 1.0) * span * 0.58
            sx = ex + tx * offset + nx * 0.18
            sy = ey + ty * offset + ny * 0.18
            ground = self._height(sx, sy)
            half_z = min(0.30, 0.15 + exposure * 0.08)
            stone = self._make_box(
                f"{name}-retaining-stone",
                Vec3(0.32, 0.25, half_z),
                Vec4(color.x * 0.76, color.y * 0.76, color.z * 0.76, 1.0),
            )
            stone.reparentTo(root)
            stone.setPos(sx, sy, ground + half_z - 0.045)
            stone.setH(heading)
            made += 1
        return made

    def _structure_entrance_anchor(
        self,
        x: float,
        y: float,
        half_x: float,
        half_y: float,
        target_x: float,
        target_y: float,
    ) -> tuple[float, float, float, float, float, float]:
        """Return a canonical facade-center anchor facing a logical destination.

        The target selects one *whole facade*, not an arbitrary point on a wall.
        Paths, thresholds, frames and seals can therefore share one placement
        authority and keep their visual relationship even when terrain varies.

        Returns: face_x, face_y, normal_x, normal_y, heading, face_half_span.
        Local +Y at ``heading`` points outward from the chosen facade.
        """
        dx = target_x - x
        dy = target_y - y
        distance = math.hypot(dx, dy)
        if distance < 1e-6:
            # Stable fallback for structures placed exactly on their destination.
            dx, dy, distance = 0.0, -1.0, 1.0
        ux, uy = dx / distance, dy / distance

        tx = half_x / max(abs(ux), 1e-6)
        ty = half_y / max(abs(uy), 1e-6)
        if tx <= ty:
            nx = 1.0 if ux >= 0.0 else -1.0
            ny = 0.0
            face_x = x + nx * half_x
            face_y = y
            face_half_span = half_y
        else:
            nx = 0.0
            ny = 1.0 if uy >= 0.0 else -1.0
            face_x = x
            face_y = y + ny * half_y
            face_half_span = half_x

        heading = math.degrees(math.atan2(-nx, ny))
        return face_x, face_y, nx, ny, heading, face_half_span

    def _add_structure_entrance(
        self,
        root: NodePath,
        name: str,
        x: float,
        y: float,
        half_x: float,
        half_y: float,
        top_z: float,
        target_x: float,
        target_y: float,
        wall_color: Vec4,
        foundation_color: Vec4,
        city: bool = False,
        monumental: bool = False,
    ) -> None:
        """Build a sealed threshold whose geometry shares the approach anchor.

        Procedural settlement interiors are not playable.  The doorway therefore
        uses an unmistakable luminous seal instead of a handle/open gap: it gives
        the new terrain approach an architectural destination without promising a
        building interaction that does not exist.
        """
        face_x, face_y, nx, ny, heading, face_span = self._structure_entrance_anchor(
            x, y, half_x, half_y, target_x, target_y
        )
        entrance = root.attachNewNode(f"{name}-sealed-threshold-root")
        entrance.setPos(face_x + nx * 0.035, face_y + ny * 0.035, top_z)
        entrance.setH(heading)

        if monumental:
            door_half_w = min(0.92, max(0.72, face_span * 0.34))
            door_half_h = 1.48
            frame_thickness = 0.16
            landing_depth = 0.72
        elif city:
            door_half_w = min(0.74, max(0.58, face_span * 0.34))
            door_half_h = 1.24
            frame_thickness = 0.13
            landing_depth = 0.58
        else:
            door_half_w = min(0.64, max(0.52, face_span * 0.34))
            door_half_h = 1.08
            frame_thickness = 0.115
            landing_depth = 0.50

        recess_color = Vec4(
            max(0.035, wall_color.x * 0.28),
            max(0.028, wall_color.y * 0.24),
            max(0.030, wall_color.z * 0.24),
            1.0,
        )
        frame_color = Vec4(
            min(0.78, foundation_color.x * 1.24),
            min(0.78, foundation_color.y * 1.24),
            min(0.78, foundation_color.z * 1.24),
            1.0,
        )

        # Dark closed slab: no handle and no open void, so it reads as architecture
        # rather than an accidentally interactable door.
        panel = self._make_box(
            f"{name}-sealed-door", Vec3(door_half_w, 0.055, door_half_h), recess_color
        )
        panel.reparentTo(entrance)
        panel.setPos(0.0, 0.070, door_half_h + 0.035)

        jamb_half_h = door_half_h + 0.10
        for side in (-1.0, 1.0):
            jamb = self._make_box(
                f"{name}-door-jamb",
                Vec3(frame_thickness, 0.105, jamb_half_h),
                frame_color,
            )
            jamb.reparentTo(entrance)
            jamb.setPos(side * (door_half_w + frame_thickness * 0.70), 0.105, jamb_half_h)

        lintel = self._make_box(
            f"{name}-door-lintel",
            Vec3(door_half_w + frame_thickness * 1.55, 0.11, frame_thickness),
            frame_color,
        )
        lintel.reparentTo(entrance)
        lintel.setPos(0.0, 0.11, door_half_h * 2.0 + frame_thickness * 0.72)

        # The landing overlaps the foundation slightly and projects outward into
        # the existing approach/step zone, eliminating the old path-to-blank-wall
        # termination while keeping settlement collision authority unchanged.
        landing_half_w = door_half_w + (0.28 if monumental else 0.22)
        landing = self._make_box(
            f"{name}-threshold-landing",
            Vec3(landing_half_w, landing_depth, 0.085),
            Vec4(
                foundation_color.x * 0.93,
                foundation_color.y * 0.93,
                foundation_color.z * 0.93,
                1.0,
            ),
        )
        landing.reparentTo(entrance)
        landing.setPos(0.0, landing_depth * 0.88, 0.015)

        # The saturated seal is the explicit "closed" affordance and remains small
        # enough not to become a floating HUD-like billboard in semantic view.
        seal = self._make_octahedron(
            f"{name}-sealed-rune",
            0.20 if monumental else 0.155 if city else 0.135,
            Vec4(0.82, 0.16, 1.0, 1.0),
        )
        seal.reparentTo(entrance)
        seal.setPos(0.0, 0.175, door_half_h + 0.10)
        seal.setScale(0.80, 0.30, 1.25)
        seal.setLightOff(1)

        bar = self._make_box(
            f"{name}-seal-bar",
            Vec3(door_half_w * 0.70, 0.035, 0.045),
            Vec4(0.66, 0.10, 0.82, 1.0),
        )
        bar.reparentTo(entrance)
        bar.setPos(0.0, 0.155, door_half_h * 0.96)
        bar.setLightOff(1)

    def _add_structure_approach(
        self,
        root: NodePath,
        name: str,
        x: float,
        y: float,
        half_x: float,
        half_y: float,
        top_z: float,
        target_x: float,
        target_y: float,
        foundation_color: Vec4,
        path_width: float = 0.72,
        max_path_length: float = 6.0,
    ) -> None:
        """Connect a structure edge to its logical destination with terrain-bound cues."""
        center_distance = math.hypot(target_x - x, target_y - y)
        if center_distance < 0.8:
            return
        face_x, face_y, nx, ny, _face_heading, _face_span = self._structure_entrance_anchor(
            x, y, half_x, half_y, target_x, target_y
        )
        front_x = face_x + nx * 0.10
        front_y = face_y + ny * 0.10
        pdx = target_x - front_x
        pdy = target_y - front_y
        path_distance = math.hypot(pdx, pdy)
        if path_distance < 0.70:
            return
        ux, uy = pdx / path_distance, pdy / path_distance
        available = max(0.0, path_distance - 0.60)
        path_length = min(max_path_length, available)
        end_x = front_x + ux * path_length
        end_y = front_y + uy * path_length

        path_color = self._biome_ground_dressing_color(x, y)
        self._add_ground_ribbon(
            root, f"{name}-worn-approach", front_x, front_y, end_x, end_y, path_width, path_color
        )

        # Build compact risers only when the foundation is actually above the
        # approach terrain.  Flat sites receive no decorative staircase.
        front_ground = self._height(front_x, front_y)
        rise = top_z - front_ground
        if rise < 0.24:
            return
        steps = max(1, min(4, int(math.ceil(rise / 0.31))))
        step_depth = 0.34
        heading = math.degrees(math.atan2(-ux, uy))
        for i in range(steps):
            # Low steps extend toward the path; the highest step sits at the wall.
            back = (steps - 1 - i) * step_depth
            sx = front_x + ux * back
            sy = front_y + uy * back
            terrain_z = self._height(sx, sy)
            step_top = front_ground + rise * ((i + 1) / steps)
            bottom = terrain_z - 0.055
            half_z = max(0.085, (step_top - bottom) * 0.5)
            slab = self._make_box(
                f"{name}-terrain-step",
                Vec3(max(0.52, path_width * 0.82), step_depth * 0.58, half_z),
                Vec4(
                    foundation_color.x * (0.90 + i * 0.018),
                    foundation_color.y * (0.90 + i * 0.018),
                    foundation_color.z * (0.90 + i * 0.018),
                    1.0,
                ),
            )
            slab.reparentTo(root)
            slab.setPos(sx, sy, bottom + half_z)
            slab.setH(heading)

    def _river_water_z(self, x: float, y: float) -> float | None:
        if max(abs(x), abs(y)) < 228.0:
            return None
        dist, width = self._river_info(x, y)
        if dist > width * 0.96:
            return None
        return self._procedural_land_height(x, y) - 1.05

    def _water_surface_at(self, x: float, y: float) -> float | None:
        d_lake = math.hypot(x - self.LAKE_CENTER.x, y - self.LAKE_CENTER.y)
        if d_lake < self.LAKE_RADIUS + 1.5 and self._height(x, y) < self.settings.water_z - 0.32:
            return self.settings.water_z
        return self._river_water_z(x, y)

    def _path_x(self, y: float) -> float:
        """Winding hero road that begins in frame and resolves exactly at the shrine."""
        t = max(0.0, min(1.0, (y + 136.0) / 246.0))
        base = -2.0 + 20.0 * t
        wander = (1.0 - t) * (
            8.2 * math.sin(t * math.pi * 1.62 - 0.48)
            + 2.8 * math.sin((y + 22.0) * 0.047)
        )
        return base + wander

    def _terrain_color(self, x: float, y: float, z: float) -> Vec4:
        path_dist = abs(x - self._path_x(y))
        if -138.0 < y < 112.0 and path_dist < 6.6:
            fringe = min(1.0, path_dist / 6.6)
            return Vec4(0.57 - fringe * 0.13, 0.39 + fringe * 0.025, 0.050, 1)

        d_lake = math.hypot(x - self.LAKE_CENTER.x, y - self.LAKE_CENTER.y)
        if d_lake < self.LAKE_RADIUS + 8.0 and z < self.settings.water_z + 1.0:
            return Vec4(0.080, 0.25, 0.17, 1)

        canyon = self._canyon_factor(x, y)
        if canyon > 0.06:
            # Carefully balanced warm colors stay on the EARTH/STONE glyph rows while
            # producing horizontal Monument-Valley-like strata in the final ASCII image.
            palette = (
                Vec4(0.56, 0.38, 0.19, 1),
                Vec4(0.67, 0.46, 0.23, 1),
                Vec4(0.61, 0.40, 0.29, 1),
                Vec4(0.74, 0.54, 0.31, 1),
                Vec4(0.58, 0.42, 0.32, 1),
                Vec4(0.78, 0.64, 0.43, 1),
            )
            band = int(math.floor((z + 4.0) * 0.72 + 0.22 * math.sin(x * 0.025))) % len(palette)
            c = palette[band]

            # Pale sandy trails remain legible between the colored walls.
            cdist = self._canyon_trail_distance(x, y)
            if cdist < 6.2:
                c = Vec4(0.77, 0.62, 0.36, 1)

            if canyon >= 0.82:
                return c

            # Blend the canyon palette into the original green foothills.
            if z > 8.0:
                base = Vec4(0.56, 0.61, 0.70, 1)
            elif z > 4.5:
                base = Vec4(0.34, 0.47, 0.36, 1)
            elif z > 2.4:
                base = Vec4(0.13, 0.42, 0.11, 1)
            else:
                variation = 0.030 * math.sin(x * 0.37 + y * 0.21)
                base = Vec4(0.075 + variation, 0.42 + variation * 1.35, 0.055, 1)
            return base * (1.0 - canyon) + c * canyon

        if z > 8.0:
            return Vec4(0.56, 0.61, 0.70, 1)
        if z > 4.5:
            return Vec4(0.34, 0.47, 0.36, 1)
        if z > 2.4:
            return Vec4(0.13, 0.42, 0.11, 1)

        variation = 0.030 * math.sin(x * 0.37 + y * 0.21)
        return Vec4(0.075 + variation, 0.42 + variation * 1.35, 0.055, 1)

    def _make_terrain(self) -> NodePath:
        name = "open-world-terrain"
        fmt = GeomVertexFormat.getV3n3c4()
        data = GeomVertexData(name, fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(data, "vertex")
        normal = GeomVertexWriter(data, "normal")
        color = GeomVertexWriter(data, "color")
        prim = GeomTriangles(Geom.UHStatic)

        segments = 136
        step = (self.WORLD_HALF * 2.0) / segments

        for iy in range(segments + 1):
            y = -self.WORLD_HALF + iy * step
            for ix in range(segments + 1):
                x = -self.WORLD_HALF + ix * step
                z = self._height(x, y)
                eps = 0.7
                dx = self._height(x + eps, y) - self._height(x - eps, y)
                dy = self._height(x, y + eps) - self._height(x, y - eps)
                n = Vec3(-dx, -dy, 2.0 * eps)
                n.normalize()
                vertex.addData3(x, y, z)
                normal.addData3(n)
                color.addData4(self._terrain_color(x, y, z))

        row = segments + 1
        for iy in range(segments):
            for ix in range(segments):
                a = iy * row + ix
                b = a + 1
                d = (iy + 1) * row + ix
                c = d + 1
                prim.addVertices(a, b, c)
                prim.addVertices(a, c, d)

        geom = Geom(data)
        geom.addPrimitive(prim)
        node = GeomNode(name)
        node.addGeom(geom)
        return NodePath(node)

    def _build_water(self) -> None:
        water = self._make_disc("lake-water", self.LAKE_RADIUS + 1.4, 72, Vec4(0.030, 0.22, 0.78, 0.76))
        water.reparentTo(self.render)
        water.setPos(self.LAKE_CENTER.x, self.LAKE_CENTER.y, self.settings.water_z)
        water.setTransparency(TRANS_ALPHA)
        water.setLightOff(1)
        water.setBin("transparent", 10)
        self.water_node = water

        # Small cyan surface facets keep the lake legible as WATER glyphs from the
        # opening field instead of collapsing into one dark flat disc.
        shimmer = self.render.attachNewNode("lake-shimmer")
        for i in range(42):
            ang = self.random.uniform(0.0, math.tau)
            r = self.random.uniform(5.0, self.LAKE_RADIUS - 2.0)
            # Keep the raised center island dry.
            if r < 8.3:
                r = 8.3 + self.random.uniform(0.0, self.LAKE_RADIUS - 10.3)
            sx = self.LAKE_CENTER.x + math.cos(ang) * r
            sy = self.LAKE_CENTER.y + math.sin(ang) * r
            facet = self._make_octahedron("water-glint", self.random.uniform(0.08, 0.18), Vec4(0.08, 0.48, 1.0, 1))
            facet.reparentTo(shimmer)
            facet.setScale(self.random.uniform(1.8, 3.4), self.random.uniform(0.55, 1.15), 0.18)
            facet.setPos(sx, sy, self.settings.water_z + 0.055)
            facet.setH(self.random.uniform(0, 360))
            facet.setLightOff(1)
        shimmer.flattenStrong()

    def _build_forest(self) -> None:
        forest = self.render.attachNewNode("forest")

        def place_tree(x: float, y: float, scale: float, crown_green: float | None = None) -> None:
            z = self._height(x, y)
            green = crown_green if crown_green is not None else self.random.uniform(0.37, 0.56)
            trunk = self._make_box("tree-trunk", Vec3(0.24 * scale, 0.24 * scale, 2.05 * scale), Vec4(0.45, 0.25, 0.040, 1))
            trunk.reparentTo(forest)
            trunk.setPos(x, y, z + 2.05 * scale)

            # Two overlapping crowns make the trees read as full leafy silhouettes
            # through the glyph shader instead of isolated diamond props.
            lower = self._make_octahedron("tree-crown-low", 2.20 * scale, Vec4(0.025, green * 0.86, 0.035, 1))
            lower.reparentTo(forest)
            lower.setScale(1.25, 1.05, 1.15)
            lower.setPos(x, y, z + 4.35 * scale)
            lower.setH(self.random.uniform(0, 360))

            crown = self._make_octahedron("tree-crown", 2.35 * scale, Vec4(0.035, green, 0.040, 1))
            crown.reparentTo(forest)
            crown.setScale(1.05, 0.92, 1.35)
            crown.setPos(x, y, z + 6.15 * scale)
            crown.setH(self.random.uniform(0, 360))
            self.obstacles.append((x, y, 0.58 * scale))

        # Deliberate foreground framing like the reference: a huge tree mass to the
        # left and a smaller counterpart on the right, while the center remains open.
        for x, y, scale in (
            (-72.0, -84.0, 1.92), (-63.0, -78.0, 1.36), (-82.0, -72.0, 1.25),
            (76.0, -64.0, 1.55), (88.0, -51.0, 1.18),
        ):
            place_tree(x, y, scale, self.random.uniform(0.43, 0.58))

        # Build dense forest shoulders, but preserve long sight-lines along the hero
        # road, lake shore and shrine approach.
        attempts = 0
        made = 0
        while made < 168 and attempts < 1800:
            attempts += 1
            x = self.random.uniform(-158, 158)
            y = self.random.uniform(-142, 148)
            if math.hypot(x, y + 128) < 16 or self._in_utopia_sanctuary(x, y, 5.0):
                continue
            road_clearance = 12.0 if y < 70 else 15.0
            if abs(x - self._path_x(y)) < road_clearance and -136 < y < 116:
                continue
            if math.hypot(x - self.SHRINE_POS.x, y - self.SHRINE_POS.y) < 35:
                continue
            if math.hypot(x - self.LAKE_CENTER.x, y - self.LAKE_CENTER.y) < self.LAKE_RADIUS + 9:
                continue
            z = self._height(x, y)
            if z > 7.8:
                continue

            # More large trees near the valley flanks, smaller ones in the mid-field.
            flank = min(1.0, abs(x) / 150.0)
            scale = self.random.uniform(0.70, 1.18 + flank * 0.38)
            place_tree(x, y, scale)
            made += 1

        # Continuous low vegetation and bright flower glyphs fill the foreground just
        # like the reference without adding collision clutter.
        for _ in range(220):
            x = self.random.uniform(-165, 165)
            y = self.random.uniform(-150, 154)
            if self._in_utopia_sanctuary(x, y, 4.0):
                continue
            if abs(x - self._path_x(y)) < 7.8 and -138 < y < 114:
                continue
            if math.hypot(x - self.LAKE_CENTER.x, y - self.LAKE_CENTER.y) < self.LAKE_RADIUS + 4:
                continue
            z = self._height(x, y)
            if z > 8.5:
                continue
            bush = self._make_octahedron("bush", self.random.uniform(0.17, 0.40), Vec4(0.045, self.random.uniform(0.34, 0.53), 0.045, 1))
            bush.reparentTo(forest)
            bush.setScale(1.65, 1.30, 0.72)
            bush.setPos(x, y, z + 0.25)

        flowers = self.render.attachNewNode("wildflowers")
        flower_colors = (
            Vec4(0.93, 0.12, 0.96, 1), Vec4(0.98, 0.72, 0.035, 1), Vec4(0.60, 0.26, 1.0, 1),
        )
        for _ in range(84):
            y = self.random.uniform(-125, 84)
            side = self.random.choice((-1.0, 1.0))
            x = self._path_x(y) + side * self.random.uniform(8.0, 28.0)
            if self._in_utopia_sanctuary(x, y, 3.0):
                continue
            if math.hypot(x - self.LAKE_CENTER.x, y - self.LAKE_CENTER.y) < self.LAKE_RADIUS + 3:
                continue
            z = self._height(x, y)
            bloom = self._make_octahedron("wildflower", self.random.uniform(0.08, 0.17), self.random.choice(flower_colors))
            bloom.reparentTo(flowers)
            bloom.setScale(1.0, 1.0, 1.55)
            bloom.setPos(x, y, z + self.random.uniform(0.18, 0.34))
            bloom.setLightOff(1)

        forest.flattenStrong()
        flowers.flattenStrong()

    def _build_rocks_and_ruins(self) -> None:
        stone = self.render.attachNewNode("stone-landmarks")
        mountain_color = Vec4(0.48, 0.54, 0.64, 1)
        pale_stone = Vec4(0.65, 0.70, 0.78, 1)
        old_stone = Vec4(0.45, 0.51, 0.60, 1)

        # Layered mountain silhouettes.  The original random ring read as isolated
        # spikes; these grouped ridges create the huge enclosing valley in the target.
        ridge_specs = (
            (-146.0, 44.0, 14), (-132.0, 96.0, 11), (145.0, 52.0, 14),
            (132.0, 108.0, 11), (-48.0, 164.0, 10), (64.0, 165.0, 10),
        )
        for cx, cy, count in ridge_specs:
            for i in range(count):
                spread = 9.0 if abs(cx) > 100 else 12.0
                x = cx + self.random.uniform(-spread, spread) + (i - count * 0.5) * self.random.uniform(1.0, 2.7)
                y = cy + self.random.uniform(-16.0, 16.0)
                h = self.random.uniform(11.0, 30.0)
                r = self.random.uniform(3.0, 7.0)
                rock = self._make_octahedron("mountain-ridge", 1.0, mountain_color)
                rock.reparentTo(stone)
                rock.setScale(r, r * self.random.uniform(0.86, 1.55), h)
                rock.setPos(x, y, self._height(x, y) + h * 0.70)
                rock.setH(self.random.uniform(0, 360))

        # A handful of nearer rock faces break up the forest edges.
        for _ in range(22):
            side = self.random.choice((-1.0, 1.0))
            x = side * self.random.uniform(92.0, 145.0)
            y = self.random.uniform(-80.0, 115.0)
            h = self.random.uniform(4.0, 10.0)
            r = self.random.uniform(1.8, 4.2)
            rock = self._make_octahedron("valley-rock", 1.0, Vec4(0.39, 0.46, 0.53, 1))
            rock.reparentTo(stone)
            rock.setScale(r, r * 1.25, h)
            rock.setPos(x, y, self._height(x, y) + h * 0.67)
            rock.setH(self.random.uniform(0, 360))

        # Landmark 1: recognizable broken arch on the left side of the route.
        arch_x, arch_y = -43.0, -20.0
        az = self._height(arch_x, arch_y)
        for xoff in (-3.5, 3.5):
            leg = self._make_box("broken-arch-leg", Vec3(0.82, 1.05, 4.2), pale_stone)
            leg.reparentTo(stone)
            leg.setPos(arch_x + xoff, arch_y, az + 4.2)
            leg.setR(self.random.uniform(-4, 4))
            self.obstacles.append((arch_x + xoff, arch_y, 0.95))
        lintel = self._make_box("broken-arch-top", Vec3(4.45, 1.05, 0.72), pale_stone)
        lintel.reparentTo(stone)
        lintel.setPos(arch_x, arch_y, az + 8.15)
        lintel.setR(-5)

        # Landmark 2: a standing-stone glade on the bright right forest shelf.
        gx, gy = 66.0, 22.0
        for i in range(8):
            ang = i * math.tau / 8.0
            x = gx + math.cos(ang) * 8.0
            y = gy + math.sin(ang) * 8.0
            h = self.random.uniform(3.1, 6.1)
            monolith = self._make_box("glade-stone", Vec3(0.65, 0.65, h / 2), Vec4(0.55, 0.61, 0.69, 1))
            monolith.reparentTo(stone)
            monolith.setPos(x, y, self._height(x, y) + h / 2)
            monolith.setHpr(self.random.uniform(-18, 18), 0, self.random.uniform(-7, 7))
            self.obstacles.append((x, y, 0.72))

        # Central processional arch: the strong white ruin silhouette visible halfway
        # between the player and shrine in the reference.
        gate_y = 43.0
        gate_x = self._path_x(gate_y)
        gz = self._height(gate_x, gate_y)
        for xoff in (-5.2, 5.2):
            col = self._make_box("processional-column", Vec3(0.88, 1.05, 5.4), pale_stone)
            col.reparentTo(stone)
            col.setPos(gate_x + xoff, gate_y, gz + 5.4)
            self.obstacles.append((gate_x + xoff, gate_y, 0.96))
            cap = self._make_box("processional-cap", Vec3(1.28, 1.26, 0.38), Vec4(0.73, 0.76, 0.82, 1))
            cap.reparentTo(stone)
            cap.setPos(gate_x + xoff, gate_y, gz + 10.48)
        lintel2 = self._make_box("processional-lintel", Vec3(6.2, 1.04, 0.66), pale_stone)
        lintel2.reparentTo(stone)
        lintel2.setPos(gate_x, gate_y, gz + 10.75)
        # Broken upper block keeps it ancient rather than a perfect gate.
        broken = self._make_box("processional-broken-top", Vec3(1.45, 0.95, 1.15), old_stone)
        broken.reparentTo(stone)
        broken.setPos(gate_x - 2.9, gate_y + 0.15, gz + 12.25)
        broken.setR(-13)

        # Smaller ruin towers and fragments around the road make the midground dense
        # like the reference while keeping the path itself fully walkable.
        ruin_points = (
            (-63, 7, 6.8), (-74, 54, 8.4), (-34, 63, 5.5),
            (53, 54, 7.5), (79, 79, 9.5), (43, 84, 5.8),
        )
        for rx, ry, rh in ruin_points:
            rz = self._height(rx, ry)
            tower = self._make_box("ruin-tower", Vec3(1.45, 1.45, rh / 2.0), old_stone)
            tower.reparentTo(stone)
            tower.setPos(rx, ry, rz + rh / 2.0)
            tower.setH(self.random.uniform(-8, 8))
            cap = self._make_box("ruin-cap", Vec3(1.75, 1.75, 0.34), pale_stone)
            cap.reparentTo(stone)
            cap.setPos(rx, ry, rz + rh + 0.10)
            cap.setR(self.random.uniform(-8, 8))
            self.obstacles.append((rx, ry, 1.55))

        # The white broken causeway at the right foreground is a strong reference
        # feature.  It points toward the shrine but remains decorative/off the hero road.
        causeway = self.render.attachNewNode("broken-causeway")
        for i in range(18):
            t = i / 17.0
            x = 78.0 - 31.0 * t + 3.0 * math.sin(t * math.pi * 1.3)
            y = -117.0 + 106.0 * t
            z = self._height(x, y)
            slab = self._make_box("causeway-slab", Vec3(1.35, 2.35, 0.16), Vec4(0.70, 0.74, 0.79, 1))
            slab.reparentTo(causeway)
            slab.setPos(x, y, z + 0.12)
            slab.setH(-13 + 8 * math.sin(t * 2.2))
            if i % 5 == 2:
                slab.setR(self.random.uniform(-7, 7))
        causeway.flattenStrong()

        stone.flattenStrong()

    def _build_canyon_region(self) -> None:
        """Build the expanded layered canyon wilderness surrounding the original valley."""
        root = self.render.attachNewNode("layered-canyon-country")
        palette = (
            Vec4(0.56, 0.38, 0.19, 1),
            Vec4(0.68, 0.47, 0.23, 1),
            Vec4(0.61, 0.40, 0.29, 1),
            Vec4(0.75, 0.55, 0.31, 1),
            Vec4(0.57, 0.42, 0.33, 1),
            Vec4(0.80, 0.65, 0.44, 1),
        )

        def band_color(i: int, offset: int = 0) -> Vec4:
            return palette[(i + offset) % len(palette)]

        def add_mesa(x: float, y: float, rx: float, ry: float, height: float, layers: int, heading: float, offset: int = 0, crown: bool = False) -> None:
            base_z = self._height(x, y)
            layer_h = height / layers
            for i in range(layers):
                t = i / max(1, layers - 1)
                # Broad lower shelves and a narrower flat summit create the iconic
                # stacked canyon silhouette while keeping every band visible.
                taper = 1.0 - 0.30 * t + 0.035 * math.sin(i * 1.7 + x * 0.03)
                shelf = 1.0 + (0.08 if i in (1, layers - 2) else 0.0)
                block = self._make_box(
                    "sandstone-stratum",
                    Vec3(rx * taper * shelf, ry * taper * shelf, layer_h * 0.48),
                    band_color(i, offset),
                )
                block.reparentTo(root)
                block.setPos(x, y, base_z + (i + 0.50) * layer_h)
                block.setH(heading + math.sin(i * 1.21) * 1.8)

            cap = self._make_box("mesa-cap", Vec3(rx * 0.68, ry * 0.68, 0.38), band_color(layers + 1, offset))
            cap.reparentTo(root)
            cap.setPos(x, y, base_z + height + 0.20)
            cap.setH(heading)

            if crown:
                spire = self._make_octahedron("mesa-crown", 1.0, band_color(layers + 2, offset))
                spire.reparentTo(root)
                spire.setScale(rx * 0.28, ry * 0.30, min(10.0, height * 0.30))
                spire.setPos(x + rx * 0.10, y - ry * 0.08, base_z + height + min(10.0, height * 0.30) * 0.72)
                spire.setH(heading + 14.0)

            self.obstacles.append((x, y, max(2.2, min(rx, ry) * 0.78)))

        # Large mesas make the expanded map read as a coherent canyon region from
        # almost any overlook instead of a collection of disconnected props.
        mesa_specs = (
            (-205, -128, 22, 14, 36, 9, -12, 0, True),
            (-232, -34, 16, 11, 28, 8, 8, 2, False),
            (-205, 70, 20, 13, 34, 9, -5, 4, True),
            (-153, 184, 18, 11, 32, 8, 16, 1, False),
            (-78, 226, 23, 14, 39, 10, -8, 3, True),
            (48, 236, 18, 12, 29, 8, 7, 5, False),
            (126, 205, 24, 15, 41, 10, -10, 0, True),
            (205, 132, 18, 12, 33, 9, 12, 2, False),
            (231, 28, 15, 10, 27, 8, -4, 4, True),
            (207, -90, 23, 15, 38, 10, 9, 1, False),
            (112, -224, 20, 13, 31, 8, -13, 5, True),
            (-62, -232, 17, 11, 26, 8, 5, 3, False),
        )
        for spec in mesa_specs:
            add_mesa(*spec)

        # Slender needles give the skyline depth between the broad mesas.
        needle_specs = (
            (-252, 116, 6.5, 23, 0), (-178, 132, 5.2, 19, 2), (-116, 252, 6.0, 25, 4),
            (16, 262, 5.5, 21, 1), (178, 214, 6.5, 26, 3), (252, 98, 5.0, 22, 5),
            (246, -150, 6.0, 24, 2), (24, -258, 5.5, 20, 4), (-172, -218, 6.2, 23, 1),
        )
        for x, y, radius, height, offset in needle_specs:
            base_z = self._height(x, y)
            layers = 7
            lh = height / layers
            for i in range(layers):
                t = i / (layers - 1)
                spire = self._make_octahedron("canyon-needle", 1.0, band_color(i, offset))
                spire.reparentTo(root)
                spire.setScale(radius * (1.0 - 0.38 * t), radius * 0.78 * (1.0 - 0.34 * t), lh * 0.86)
                spire.setPos(x, y, base_z + (i + 0.52) * lh)
                spire.setH(i * 9.0 + x * 0.06)
            self.obstacles.append((x, y, radius * 0.62))

        def add_arch(x: float, y: float, heading: float, width: float, height: float, depth: float, offset: int) -> None:
            base_z = self._height(x, y)
            arch = root.attachNewNode("natural-sandstone-arch")
            layer_h = height / 7.0
            for side in (-1.0, 1.0):
                for i in range(7):
                    col = self._make_box(
                        "arch-stratum",
                        Vec3(1.65, depth, layer_h * 0.48),
                        band_color(i, offset),
                    )
                    col.reparentTo(arch)
                    col.setPos(side * width * 0.50, 0, (i + 0.50) * layer_h)
            # Layer the bridge too so the horizontal color strata continue naturally.
            for i in range(3):
                bridge = self._make_box(
                    "arch-bridge-band",
                    Vec3(width * 0.70, depth * 1.04, 0.55),
                    band_color(7 + i, offset),
                )
                bridge.reparentTo(arch)
                bridge.setPos(0, 0, height + 0.52 + i * 1.02)
            arch.setPos(x, y, base_z)
            arch.setH(heading)

            # Approximate collision at the two legs while leaving the opening passable.
            ang = math.radians(heading)
            for side in (-1.0, 1.0):
                lx = x + math.cos(ang) * side * width * 0.50
                ly = y + math.sin(ang) * side * width * 0.50
                self.obstacles.append((lx, ly, 2.0))

        add_arch(-186.0, -62.0, 36.0, 14.0, 18.0, 2.3, 1)
        add_arch(185.0, 156.0, -27.0, 16.0, 21.0, 2.6, 3)
        add_arch(12.0, 232.0, 6.0, 18.0, 22.0, 2.8, 5)

        # Stepped rim walls at the far edges make the world feel enclosed by miles of
        # layered canyon country, while gaps preserve distant vistas and exploration.
        wall_specs = (
            (-258, -70, 8, 0), (-258, 42, 7, 2), (-250, 172, 6, 4),
            (258, -176, 6, 3), (258, -48, 8, 5), (252, 84, 7, 1),
            (-120, 268, 7, 4), (82, 270, 8, 0),
        )
        for wx, wy, count, offset in wall_specs:
            horizontal = abs(wy) > 240
            for j in range(count):
                x = wx + (j - count * 0.5) * (17.0 if horizontal else 4.0)
                y = wy + (j - count * 0.5) * (4.0 if horizontal else 17.0)
                rx = self.random.uniform(8.0, 13.0)
                ry = self.random.uniform(7.0, 12.0)
                add_mesa(x, y, rx, ry, self.random.uniform(15.0, 24.0), 6, self.random.uniform(-8, 8), offset + j, False)

        # Sparse desert vegetation provides scale without turning the canyon into forest.
        scrub = root.attachNewNode("desert-scrub")
        for _ in range(92):
            for _attempt in range(20):
                x = self.random.uniform(-264, 264)
                y = self.random.uniform(-264, 264)
                if self._canyon_factor(x, y) < 0.55:
                    continue
                if self._canyon_trail_distance(x, y) < 7.0:
                    continue
                z = self._height(x, y)
                tuft = self._make_octahedron("desert-tuft", self.random.uniform(0.10, 0.23), Vec4(0.27, 0.39, 0.12, 1))
                tuft.reparentTo(scrub)
                tuft.setScale(1.8, 1.2, self.random.uniform(1.2, 2.1))
                tuft.setPos(x, y, z + 0.18)
                break

        root.flattenStrong()

    def _build_shrine(self) -> None:
        root = self.render.attachNewNode("shattered-shrine")
        x, y = self.SHRINE_POS.x, self.SHRINE_POS.y
        z = self._height(x, y)
        stone = Vec4(0.72, 0.76, 0.83, 1)
        bright = Vec4(0.82, 0.84, 0.88, 1)
        dark = Vec4(0.34, 0.39, 0.48, 1)
        gold = Vec4(0.60, 0.49, 0.19, 1)

        # Wide stepped sanctuary on a hill: the shrine is the world's visual anchor,
        # so its silhouette is intentionally much stronger than in earlier passes.
        platform = self._make_box("shrine-platform", Vec3(13.0, 10.5, 0.62), dark)
        platform.reparentTo(root)
        platform.setPos(x, y + 2.5, z + 0.35)

        for step_i in range(8):
            step = self._make_box("shrine-step", Vec3(7.2 - step_i * 0.30, 0.88, 0.22), gold)
            step.reparentTo(root)
            step.setPos(x, y - 11.8 + step_i * 1.12, z + 0.20 + step_i * 0.23)

        # Tall front pylons and inner columns create a readable temple facade.
        for xoff in (-8.4, 8.4):
            tower = self._make_box("shrine-tower", Vec3(2.15, 2.2, 8.0), stone)
            tower.reparentTo(root)
            tower.setPos(x + xoff, y + 3.4, z + 8.25)
            tower.setH(self.random.uniform(-2.2, 2.2))
            cap = self._make_box("shrine-tower-cap", Vec3(2.55, 2.55, 0.46), bright)
            cap.reparentTo(root)
            cap.setPos(x + xoff, y + 3.4, z + 16.05)

        for xoff in (-5.2, 5.2):
            col = self._make_box("shrine-column", Vec3(0.82, 0.82, 5.7), bright)
            col.reparentTo(root)
            col.setPos(x + xoff, y - 1.7, z + 6.0)
            self.obstacles.append((x + xoff, y - 1.7, 0.92))
            cap = self._make_box("shrine-column-cap", Vec3(1.16, 1.06, 0.34), stone)
            cap.reparentTo(root)
            cap.setPos(x + xoff, y - 1.7, z + 11.6)

        roof = self._make_box("shrine-roof", Vec3(7.3, 2.35, 0.74), stone)
        roof.reparentTo(root)
        roof.setPos(x, y - 1.75, z + 12.05)

        # Central peaked crown/spire gives the temple the unmistakable high silhouette
        # visible in the supplied reference.
        crown = self._make_octahedron("shrine-crown", 2.35, bright)
        crown.reparentTo(root)
        crown.setScale(2.25, 1.20, 2.8)
        crown.setPos(x, y + 0.25, z + 15.0)
        crown.setH(45)
        spire = self._make_octahedron("shrine-spire", 1.0, stone)
        spire.reparentTo(root)
        spire.setScale(0.70, 0.70, 4.8)
        spire.setPos(x, y + 2.0, z + 19.1)

        back = self._make_box("shrine-back", Vec3(10.5, 1.35, 5.7), dark)
        back.reparentTo(root)
        back.setPos(x, y + 9.0, z + 6.0)

        # Side fragments make the temple look shattered rather than symmetrical/new.
        for sx, sy, sh, roll in ((-12.0, 7.2, 6.8, -9), (12.2, 8.6, 5.1, 11), (-10.8, -2.0, 3.2, 5)):
            shard = self._make_box("shrine-ruin-wing", Vec3(1.35, 1.6, sh / 2.0), Vec4(0.53, 0.58, 0.66, 1))
            shard.reparentTo(root)
            shard.setPos(x + sx, y + sy, z + sh / 2.0)
            shard.setR(roll)

        self.shrine_door = self._make_box("sealed-door", Vec3(2.35, 0.52, 4.15), Vec4(0.70, 0.07, 0.98, 1))
        self.shrine_door.reparentTo(root)
        self.shrine_door.setPos(x, y - 1.00, z + 4.45)
        self.shrine_door.setLightOff(1)

        # Layered portal crystal creates a larger purple focal point at long range.
        self.portal = self._make_octahedron("shrine-heart", 1.65, Vec4(0.98, 0.06, 1.0, 1))
        self.portal.reparentTo(root)
        self.portal.setScale(0.72, 0.42, 1.55)
        self.portal.setPos(x, y + 0.15, z + 4.7)
        self.portal.setLightOff(1)
        self.portal.hide()
        self.animated_magic.append((self.portal, self.portal.getPos(self.render), 0.45, 0.0))

        halo = self._make_octahedron("sealed-rune", 0.82, Vec4(0.84, 0.10, 1.0, 1))
        halo.reparentTo(root)
        halo.setScale(0.48, 0.24, 1.25)
        halo.setPos(x, y - 1.62, z + 5.2)
        halo.setLightOff(1)
        self.animated_magic.append((halo, halo.getPos(self.render), 0.10, 0.9))

        self.shrine_entrance = Vec3(x, y - 4.2, z)
        self.shrine_portal_pos = Vec3(x, y + 0.15, z)

    def _build_utopia_portal(self) -> None:
        """Permanent Utopia return anchor at the southern trailhead.

        The portal is intentionally authored outside procedural streaming.  Its
        sanctuary is a protected world-space region and its beacon remains a
        stable navigation landmark even when the player explores arbitrarily far.
        """
        root = self.render.attachNewNode("utopia-central-hub-portal")
        x = self.UTOPIA_PORTAL_POS.x
        y = self.UTOPIA_PORTAL_POS.y
        z = self._height(x, y)
        self.utopia_portal_pos = Vec3(x, y, z)
        self.portal_respawn_pos = Vec3(self.UTOPIA_RESPAWN_POS.x, self.UTOPIA_RESPAWN_POS.y, 0.0)

        # Quiet hardlight dais.  It is wide enough to read as infrastructure but
        # deliberately leaves the player-facing north side open.
        base = self._make_disc("utopia-dais", 7.4, 32, Vec4(0.20, 0.26, 0.34, 1))
        base.reparentTo(root)
        base.setPos(x, y, z + 0.07)
        inner = self._make_disc("utopia-dais-core", 5.4, 32, Vec4(0.08, 0.36, 0.44, 1))
        inner.reparentTo(root)
        inner.setPos(x, y, z + 0.10)
        inner.setLightOff(1)

        # Tall hardlight pylons intentionally exceed nearby fantasy ruins.  Their
        # magenta/white cores survive the semantic renderer as a distinct signal.
        for side in (-1.0, 1.0):
            px = x + side * 5.8
            pylon = self._make_box("utopia-pylon", Vec3(0.62, 0.76, 6.7), Vec4(0.72, 0.78, 0.88, 1))
            pylon.reparentTo(root)
            pylon.setPos(px, y + 0.4, z + 6.7)
            core = self._make_box("utopia-pylon-core", Vec3(0.16, 0.84, 5.2), Vec4(0.98, 0.07, 0.95, 1))
            core.reparentTo(root)
            core.setPos(px - side * 0.18, y - 0.38, z + 6.8)
            core.setLightOff(1)
            cap = self._make_octahedron("utopia-pylon-cap", 0.88, Vec4(0.92, 0.96, 1.0, 1))
            cap.reparentTo(root)
            cap.setPos(px, y + 0.4, z + 13.8)
            cap.setScale(0.78, 0.78, 1.55)
            cap.setLightOff(1)
            self.obstacles.append((px, y + 0.4, 0.86))

        # Three concentric vertical rings form the connection aperture.  LineSegs
        # keeps the portal lightweight and exceptionally readable in ASCII.
        ring_specs = (
            (4.25, 0.15, Vec4(0.93, 0.08, 1.0, 1), 4.0),
            (3.50, 0.00, Vec4(0.75, 0.84, 1.0, 1), 2.8),
            (2.82, -0.12, Vec4(0.15, 0.96, 0.92, 1), 2.2),
        )
        for idx, (radius, yoff, color, thickness) in enumerate(ring_specs):
            lines = LineSegs(f"utopia-ring-{idx}")
            lines.setThickness(thickness)
            lines.setColor(color)
            for step in range(65):
                a = math.tau * step / 64.0
                point = Vec3(x + math.cos(a) * radius, y + yoff, z + 5.15 + math.sin(a) * radius)
                if step == 0:
                    lines.moveTo(point)
                else:
                    lines.drawTo(point)
            ring = self.render.attachNewNode(lines.create())
            ring.setLightOff(1)
            self.utopia_portal_parts.append(ring)

        aperture = self._make_disc("utopia-aperture", 2.55, 32, Vec4(0.54, 0.035, 0.74, 0.58))
        aperture.reparentTo(root)
        aperture.setPos(x, y + 0.24, z + 5.15)
        aperture.setP(90)
        aperture.setTransparency(TRANS_ALPHA)
        aperture.setLightOff(1)
        self.utopia_aperture = aperture

        core = self._make_octahedron("utopia-link-core", 0.82, Vec4(1.0, 0.07, 0.96, 1))
        core.reparentTo(root)
        core.setPos(x, y + 0.02, z + 5.15)
        core.setScale(0.55, 0.32, 1.50)
        core.setLightOff(1)
        self.utopia_core = core

        # Beacon is intentionally extremely tall.  It is not collision geometry;
        # it exists to provide a reliable home signature across the open world.
        beacon = LineSegs("utopia-home-beacon")
        beacon.setThickness(5.0)
        beacon.setColor(Vec4(0.98, 0.07, 1.0, 0.92))
        beacon.moveTo(x, y, z + 13.8)
        beacon.drawTo(x, y, z + 92.0)
        self.utopia_beacon = self.render.attachNewNode(beacon.create())
        self.utopia_beacon.setLightOff(1)

        cross = LineSegs("utopia-beacon-cross")
        cross.setThickness(2.5)
        cross.setColor(Vec4(0.18, 0.92, 1.0, 0.88))
        cross.moveTo(x - 8.0, y, z + 30.0); cross.drawTo(x + 8.0, y, z + 30.0)
        cross.moveTo(x, y - 8.0, z + 30.0); cross.drawTo(x, y + 8.0, z + 30.0)
        self.utopia_beacon_cross = self.render.attachNewNode(cross.create())
        self.utopia_beacon_cross.setLightOff(1)

        # Simple physical title marker at the north approach.  HUD text remains
        # separate so this does not depend on texture assets or unsupported glyphs.
        marker = self._make_box("utopia-marker", Vec3(3.0, 0.30, 0.16), Vec4(0.18, 0.34, 0.42, 1))
        marker.reparentTo(root)
        marker.setPos(x, y + 5.4, z + 0.52)
        marker.setLightOff(1)

        self.utopia_portal_root = root
        self.portal_link_ready = True

    def _write_portal_handoff(self) -> bool:
        """Write an optional Prototype Lab handoff request atomically.

        Prototype Lab can provide GX_PORTAL_HANDOFF_PATH when it launches the
        game.  Standalone runs never write into the install directory or exit
        unexpectedly; they simply report that the host link is unavailable.
        """
        raw_path = os.environ.get("GX_PORTAL_HANDOFF_PATH", "").strip()
        if not raw_path:
            return False
        path = Path(raw_path).expanduser()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": 1,
                "action": "PORTAL_RETURN",
                "source_project": "GLYPHBOUND",
                "source_title": TITLE,
                "source_pass": 23,
                "portal_id": self.UTOPIA_PORTAL_ID,
                "target": "CENTRAL_HUB",
                "world_seed": int(self.world_seed),
                "timestamp_unix": time.time(),
            }
            temp = path.with_name(path.name + ".tmp")
            temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            os.replace(temp, path)
            return True
        except Exception as exc:
            print(f"[PORTAL] Could not write Central Hub handoff: {exc}")
            return False

    def _begin_central_hub_return(self) -> None:
        if self.portal_transition_timer > 0.0:
            return
        self.portal_transition_timer = self.portal_transition_duration
        if self.hosted_mode and callable(self.hosted_return_callback):
            self.portal_handoff_requested = True
        else:
            self.portal_handoff_requested = self._write_portal_handoff()
        self.velocity = Vec3(0)
        self._play_sfx("shrine_enter")
        if self.hosted_mode and self.portal_handoff_requested:
            self._show_message("UTOPIA LINK // RETURNING TO HOLOVERSE", self.portal_transition_duration)
        elif self.portal_handoff_requested:
            self._show_message("UTOPIA LINK // RETURNING TO CENTRAL HUB", self.portal_transition_duration)
        else:
            self._show_message("CENTRAL HUB LINK READY // PROTOTYPE LAB HANDOFF NOT CONNECTED", 3.2)

    def _finish_central_hub_return(self) -> None:
        if self.portal_handoff_requested and not self._quitting:
            self._quitting = True
            if self.hosted_mode and callable(self.hosted_return_callback):
                self.hosted_return_callback("glyphbound-portal")
            else:
                self.userExit()

    def hosted_update(self, dt: float) -> None:
        """Advance exactly one HoloVerse-owned native frame without adding a task."""
        class _HostedTask:
            cont = "cont"
        dt = min(0.065, max(0.0, float(dt)))
        self.last_frame = time.perf_counter() - dt
        self._update(_HostedTask())

    def shutdown_hosted(self) -> None:
        """Release only Glyphbound-owned state; HoloVerse restores host state next."""
        if not self.hosted_mode or self._hosted_cleanup_done:
            return
        self._hosted_cleanup_done = True
        try:
            self.ignoreAll()
        except Exception:
            pass
        try:
            self.taskMgr.remove("glyphbound-update")
            self.taskMgr.remove("glyphbound-test-shot")
            self.taskMgr.remove("glyphbound-portal-handoff-test")
        except Exception:
            pass
        try:
            if self.music_current is not None:
                self.music_current.stop()
        except Exception:
            pass
        try:
            for sounds in self.sfx_library.values():
                for sound in sounds:
                    try:
                        sound.stop()
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            buffer = getattr(self, "scene_buffer", None)
            if buffer is not None and buffer is not self.win:
                self._showbase.graphicsEngine.removeWindow(buffer)
        except Exception:
            pass
        for root_name in ("aspect2d", "render2d", "render"):
            root = getattr(self, root_name, None)
            try:
                if root is not None and not root.isEmpty():
                    root.removeNode()
            except Exception:
                pass

    def _return_to_utopia_beacon(self, reason: str = "SIMULATION RESET") -> None:
        """Recover the player at the permanent portal-safe anchor."""
        self.health = self.settings.max_health
        self.stamina = self.settings.max_stamina
        self.mana = self.settings.max_mana
        self.magic_ward_timer = 0.0
        self.magic_ward_charges = 0
        self.magic_cooldown = 0.0
        self.staff_cooldown = 0.0
        self.sword_cooldown = 0.0
        self.player_pos = Vec3(self.portal_respawn_pos)
        self.last_safe_pos = Vec3(self.portal_respawn_pos)
        self.respawn_pos = Vec3(self.portal_respawn_pos)
        self.heading = 0.0
        self.pitch = -3.0
        self.velocity = Vec3(0)
        # Do not mutate streamed-enemy/projectile lists from inside a damage
        # callback. The next frame notices the new stream center naturally and
        # hostile projectiles are harmless inside the sanctuary/old region.
        self.last_stream_center = None
        self._sync_camera()
        self._show_message(f"{reason} // RESTORED AT UTOPIA RETURN BEACON", 2.8)

    def _reset_world_to_portal(self) -> None:
        self._return_to_utopia_beacon("WORLD RECOVERY")

    def _build_demon_rifts(self) -> None:
        """Three corrupted landmarks seed demon encounters without gating exploration."""
        self.demon_rift_positions = [Vec3(-94.0, 2.0, 0), Vec3(96.0, 57.0, 0), Vec3(-76.0, 118.0, 0)]
        for idx, pos in enumerate(self.demon_rift_positions):
            pos.z = self._height(pos.x, pos.y)
            root = self.render.attachNewNode(f"demon-rift-{idx}")
            core = self._make_octahedron("rift-core", 1.0, Vec4(0.84, 0.055, 0.96, 1))
            core.reparentTo(root)
            core.setScale(0.75, 0.42, 1.55)
            core.setPos(pos.x, pos.y, pos.z + 1.65)
            core.setLightOff(1)
            self.animated_magic.append((core, core.getPos(self.render), 0.24, idx * 1.7))
            for j in range(5):
                ang = j * math.tau / 5.0 + idx * 0.31
                shard = self._make_octahedron("rift-shard", 0.42, Vec4(0.39, 0.18, 0.48, 1))
                shard.reparentTo(root)
                shard.setScale(0.55, 0.55, 1.9)
                shard.setPos(
                    pos.x + math.cos(ang) * 2.25,
                    pos.y + math.sin(ang) * 2.25,
                    pos.z + 0.82,
                )
                shard.setHpr(math.degrees(ang), 0, self.random.uniform(-22, 22))
                shard.setLightOff(1)

    def _make_demon_model(self, name: str, kind: str) -> NodePath:
        root = self.render.attachNewNode(name)
        if kind == "imp":
            body_scale = (0.72, 0.58, 0.88)
            head_z = 1.05
            horn_len = 0.52
        elif kind == "brute":
            body_scale = (1.05, 0.86, 1.05)
            head_z = 1.42
            horn_len = 0.72
        elif kind == "pyre":
            body_scale = (0.86, 0.68, 1.10)
            head_z = 1.38
            horn_len = 0.70
        else:  # hexer
            body_scale = (0.72, 0.58, 1.20)
            head_z = 1.48
            horn_len = 0.62

        body_color = Vec4(0.78, 0.025, 0.018, 1) if kind == "pyre" else Vec4(0.86, 0.035, 0.055, 1)
        body = self._make_octahedron(f"{kind}-torso", 0.72, body_color)
        body.reparentTo(root)
        body.setScale(*body_scale)
        body.setZ(0.48)
        body.setLightOff(1)

        head_color = Vec4(1.0, 0.20, 0.025, 1) if kind == "pyre" else Vec4(0.98, 0.075, 0.035, 1)
        head = self._make_octahedron(f"{kind}-head", 0.47, head_color)
        head.reparentTo(root)
        head.setScale(0.88, 0.75, 0.80)
        head.setZ(head_z)
        head.setLightOff(1)

        for side in (-1.0, 1.0):
            horn = self._make_box(f"{kind}-horn", Vec3(0.075, 0.075, horn_len), Vec4(0.66, 0.025, 0.025, 1))
            horn.reparentTo(root)
            horn.setPos(side * 0.34, 0.0, head_z + 0.52)
            horn.setHpr(0, side * 20.0, side * 24.0)
            horn.setLightOff(1)

        if kind == "brute":
            for side in (-1.0, 1.0):
                shoulder = self._make_octahedron("brute-shoulder", 0.36, Vec4(0.73, 0.025, 0.025, 1))
                shoulder.reparentTo(root)
                shoulder.setPos(side * 0.78, 0.0, 0.78)
                shoulder.setScale(1.15, 0.82, 0.68)
                shoulder.setLightOff(1)
        elif kind == "hexer":
            focus = self._make_octahedron("hexer-focus", 0.25, Vec4(0.88, 0.08, 1.0, 1))
            focus.reparentTo(root)
            focus.setPos(0, 0, 2.28)
            focus.setScale(0.72, 0.72, 1.18)
            focus.setLightOff(1)
        elif kind == "pyre":
            # A permanent crown of flame plus a hidden hand-flame make this demon
            # readable as a fire caster even after the semantic glyph pass.
            for j, (xoff, zoff, scale) in enumerate(((-0.24, 0.0, 0.72), (0.0, 0.18, 0.92), (0.24, 0.02, 0.68))):
                flame = self._make_octahedron(f"pyre-crown-{j}", 0.22, Vec4(1.0, 0.22 + j * 0.09, 0.015, 1))
                flame.reparentTo(root)
                flame.setPos(xoff, 0.0, head_z + 0.64 + zoff)
                flame.setScale(0.72 * scale, 0.58 * scale, 1.45 * scale)
                flame.setLightOff(1)
            ember = self._make_octahedron("pyre-chest-ember", 0.22, Vec4(1.0, 0.42, 0.02, 1))
            ember.reparentTo(root)
            ember.setPos(0.0, -0.42, 0.90)
            ember.setScale(1.0, 0.45, 1.0)
            ember.setLightOff(1)
            hand_flame = self._make_octahedron("pyre-hand-flame", 0.28, Vec4(1.0, 0.28, 0.015, 1))
            hand_flame.reparentTo(root)
            hand_flame.setPos(0.78, -0.10, 1.12)
            hand_flame.setLightOff(1)
            hand_flame.hide()

        return root

    def _build_stars(self) -> None:
        stars = self.render.attachNewNode("stars")
        self.stars_np = stars
        stars.setTransparency(TRANS_ALPHA)
        for _ in range(640):
            ang = self.random.uniform(0, math.tau)
            r = self.random.uniform(190, 410)
            x = math.cos(ang) * r
            y = math.sin(ang) * r
            z = self.random.uniform(62, 235)
            size = self.random.uniform(0.05, 0.15)
            star = self._make_octahedron("star", size, Vec4(self.random.uniform(0.55, 0.95), 0.72, 1.0, 1))
            star.reparentTo(stars)
            star.setPos(x, y, z)
            star.setLightOff(1)
        stars.flattenStrong()
        stars.setColorScale(1.0, 1.0, 1.0, 0.0)

    # ------------------------------------------------------------------
    # Pass 15: day / night + weather
    # ------------------------------------------------------------------
    @staticmethod
    def _color_lerp(a: Vec4, b: Vec4, amount: float) -> Vec4:
        amount = max(0.0, min(1.0, amount))
        return a + (b - a) * amount

    def _build_weather_system(self) -> None:
        # Visible sun and moon are lightweight geometric markers so the sky
        # itself participates in the glyph renderer instead of being a flat
        # color-only day/night toggle.
        self.celestial_root = self.render.attachNewNode("celestial-cycle")
        self.sun_disc = self._make_octahedron("sun-disc", 5.8, Vec4(1.0, 0.74, 0.16, 1.0))
        self.sun_disc.reparentTo(self.celestial_root)
        self.sun_disc.setLightOff(1)
        self.moon_disc = self._make_octahedron("moon-disc", 4.2, Vec4(0.66, 0.78, 1.0, 1.0))
        self.moon_disc.reparentTo(self.celestial_root)
        self.moon_disc.setLightOff(1)

        # A compact cloud ceiling follows the player so storms have visible
        # structure without requiring hundreds of world-sized cloud meshes.
        self.cloud_root = self.render.attachNewNode("weather-clouds")
        self.cloud_root.setTransparency(TRANS_ALPHA)
        for i in range(22):
            cloud = self._make_octahedron(
                f"storm-cloud-{i}",
                1.0,
                Vec4(self.random.uniform(0.10, 0.16), self.random.uniform(0.12, 0.18), self.random.uniform(0.20, 0.28), 0.78),
            )
            cloud.reparentTo(self.cloud_root)
            cloud.setPos(
                self.random.uniform(-42.0, 42.0),
                self.random.uniform(-36.0, 42.0),
                self.random.uniform(23.0, 33.0),
            )
            cloud.setScale(
                self.random.uniform(6.5, 13.0),
                self.random.uniform(4.0, 8.5),
                self.random.uniform(0.75, 1.45),
            )
            cloud.setH(self.random.uniform(0.0, 360.0))
            cloud.setLightOff(1)
        self.cloud_root.setColorScale(1.0, 1.0, 1.0, 0.0)

        # High translucent cloud ribbons remain visible even in clear weather,
        # giving the enormous streamed world a layered sky instead of a flat void.
        self.high_cloud_root = self.render.attachNewNode("high-cloud-ribbons")
        self.high_cloud_root.setTransparency(TRANS_ALPHA)
        for i in range(28):
            ribbon = self._make_octahedron(f"high-cloud-{i}", 1.0, Vec4(0.54, 0.67, 0.82, 0.28))
            ribbon.reparentTo(self.high_cloud_root)
            ang = self.random.uniform(0, math.tau); radial = self.random.uniform(75.0, 210.0)
            ribbon.setPos(math.cos(ang)*radial, math.sin(ang)*radial, self.random.uniform(48.0, 78.0))
            ribbon.setScale(self.random.uniform(10.0,25.0), self.random.uniform(2.0,5.0), self.random.uniform(0.28,0.65))
            ribbon.setH(self.random.uniform(0,360)); ribbon.setLightOff(1)
        self.high_cloud_root.setColorScale(1,1,1,0.22)

        self.horizon_root = self.render.attachNewNode("distant-sky-haze")
        self.horizon_root.setTransparency(TRANS_ALPHA)
        for i in range(24):
            ang=i*math.tau/24.0
            haze=self._make_box("horizon-haze",Vec3(15.0,2.0,self.random.uniform(8.0,18.0)),Vec4(0.10,0.22,0.38,0.22))
            haze.reparentTo(self.horizon_root); haze.setPos(math.cos(ang)*330.0,math.sin(ang)*330.0,self.random.uniform(22.0,40.0)); haze.setH(math.degrees(ang)+90); haze.setLightOff(1)
        self.horizon_root.setColorScale(1,1,1,0.28)

        # Regional night-sky ribbons give distant procedural biomes their own
        # celestial identity without using texture assets.
        self.aurora_root = self.render.attachNewNode("regional-aurora")
        self.aurora_root.setTransparency(TRANS_ALPHA)
        for i in range(8):
            ribbon = self._make_box(
                f"aurora-ribbon-{i}",
                Vec3(self.random.uniform(18.0, 34.0), self.random.uniform(0.35, 0.75), self.random.uniform(2.5, 5.5)),
                Vec4(0.20, 0.82, 0.78, 0.28),
            )
            ribbon.reparentTo(self.aurora_root)
            ribbon.setPos(
                self.random.uniform(-90.0, 90.0),
                self.random.uniform(70.0, 150.0),
                self.random.uniform(66.0, 108.0),
            )
            ribbon.setH(self.random.uniform(-18.0, 18.0))
            ribbon.setP(self.random.uniform(-4.0, 4.0))
            ribbon.setLightOff(1)
        self.aurora_root.setColorScale(1.0, 1.0, 1.0, 0.0)

        self.rain_root = self.render.attachNewNode("rain-field")
        self.rain_root.setTransparency(TRANS_ALPHA)
        self.rain_root.setDepthWrite(False)
        for _ in range(150):
            self.rain_drops.append([
                self.random.uniform(-22.0, 22.0),
                self.random.uniform(-16.0, 30.0),
                self.random.uniform(0.5, 27.0),
                self.random.uniform(20.0, 34.0),
            ])
        self.rain_root.hide()
        self._apply_atmosphere_visuals()

    def _set_weather(self, state: str, announce: bool = True) -> None:
        state = state if state in self.weather_states else "CLEAR"
        self.weather_state = state
        targets = {
            "CLEAR": (0.0, 0.0, (70.0, 118.0)),
            "CLOUDY": (0.62, 0.0, (48.0, 82.0)),
            "RAIN": (0.82, 0.70, (54.0, 92.0)),
            "STORM": (1.0, 1.0, (38.0, 66.0)),
        }
        self.weather_cloud_target, self.weather_rain_target, span = targets[state]
        self.weather_timer = self.random.uniform(*span)
        if state == "STORM":
            self.storm_lightning_timer = self.random.uniform(1.8, 5.5)
            self._play_sfx("weather_wind")
        elif state == "RAIN":
            self._play_sfx("weather_rain")
        if announce and hasattr(self, "message_text"):
            label = {"CLEAR": "THE SKY CLEARS", "CLOUDY": "CLOUDS GATHER", "RAIN": "RAIN MOVES ACROSS THE VALLEY", "STORM": "A STORM ROLLS INTO THE CANYONS"}[state]
            self._show_message(label, 2.0)

    def _choose_next_weather(self) -> None:
        roll = self.random.random()
        if self.weather_state == "STORM":
            next_state = "RAIN" if roll < 0.72 else "CLOUDY"
        elif self.weather_state == "RAIN":
            next_state = "STORM" if roll < 0.16 else ("CLOUDY" if roll < 0.58 else "CLEAR")
        elif self.weather_state == "CLOUDY":
            next_state = "RAIN" if roll < 0.42 else ("CLEAR" if roll < 0.84 else "STORM")
        else:
            next_state = "CLOUDY" if roll < 0.48 else ("RAIN" if roll < 0.65 else "CLEAR")
        self._set_weather(next_state)

    def _cycle_weather_debug(self) -> None:
        idx = (self.weather_states.index(self.weather_state) + 1) % len(self.weather_states)
        self._set_weather(self.weather_states[idx])

    def _advance_time_debug(self) -> None:
        self.time_of_day = (self.time_of_day + 3.0) % 24.0
        self._apply_atmosphere_visuals()
        self._show_message(f"TIME {self._format_world_time()}", 1.2)

    def _format_world_time(self) -> str:
        hour = int(self.time_of_day) % 24
        minute = int((self.time_of_day - int(self.time_of_day)) * 60.0) % 60
        suffix = "AM" if hour < 12 else "PM"
        display = hour % 12
        if display == 0:
            display = 12
        return f"{display:02d}:{minute:02d} {suffix}"

    def _rebuild_rain(self) -> None:
        if self.weather_rain < 0.04:
            self.rain_root.hide()
            return
        self.rain_root.show()
        old = self.rain_root.find("**/rain-lines")
        if not old.isEmpty():
            old.removeNode()
        lines = LineSegs("rain-lines")
        lines.setThickness(1.15 if self.weather_state != "STORM" else 1.65)
        alpha = 0.45 + self.weather_rain * 0.38
        lines.setColor(0.46, 0.68, 1.0, alpha)
        active = max(1, int(len(self.rain_drops) * self.weather_rain))
        slant = 0.28 + 0.38 * self.weather_cloud
        for x, y, z, speed in self.rain_drops[:active]:
            length = 0.8 + (speed - 20.0) * 0.045
            lines.moveTo(x, y, z)
            lines.drawTo(x - slant, y - slant * 0.55, z - length)
        node = self.rain_root.attachNewNode(lines.create(False))
        node.setName("rain-lines")
        node.setLightOff(1)
        node.setTransparency(TRANS_ALPHA)
        node.setDepthWrite(False)

    def _spawn_weather_lightning(self) -> None:
        strike_x = self.player_pos.x + self.random.uniform(-34.0, 34.0)
        strike_y = self.player_pos.y + self.random.uniform(12.0, 58.0)
        ground_z = self._height(strike_x, strike_y) + 0.4
        start = Vec3(strike_x + self.random.uniform(-3.0, 3.0), strike_y + self.random.uniform(-2.0, 2.0), ground_z + 62.0)
        end = Vec3(strike_x, strike_y, ground_z)
        delta = end - start
        count = 13
        pts: list[Vec3] = []
        for i in range(count + 1):
            u = i / float(count)
            p = start + delta * u
            if 0 < i < count:
                envelope = math.sin(math.pi * u)
                p += Vec3(self.random.uniform(-2.4, 2.4) * envelope, self.random.uniform(-1.7, 1.7) * envelope, 0.0)
            pts.append(p)

        root = self.render.attachNewNode("storm-lightning")
        root.setTransparency(TRANS_ALPHA)
        root.setLightOff(1)
        for thickness, color in ((7.0, (0.38, 0.48, 1.0, 0.82)), (2.2, (0.92, 0.96, 1.0, 1.0))):
            bolt = LineSegs("storm-bolt")
            bolt.setThickness(thickness)
            bolt.setColor(*color)
            bolt.moveTo(pts[0])
            for point in pts[1:]:
                bolt.drawTo(point)
            root.attachNewNode(bolt.create(False)).setLightOff(1)

        branches = LineSegs("storm-branches")
        branches.setThickness(2.0)
        branches.setColor(0.72, 0.82, 1.0, 0.88)
        for idx in (4, 7, 9):
            p0 = pts[idx]
            direction = -1.0 if idx % 2 else 1.0
            p1 = p0 + Vec3(direction * self.random.uniform(3.0, 7.0), self.random.uniform(-1.5, 3.0), self.random.uniform(-4.0, -1.5))
            p2 = p1 + Vec3(direction * self.random.uniform(2.0, 5.0), self.random.uniform(-1.0, 2.0), self.random.uniform(-3.0, -1.0))
            branches.moveTo(p0)
            branches.drawTo(p1)
            branches.drawTo(p2)
        root.attachNewNode(branches.create(False)).setLightOff(1)
        self.weather_lightning_fx.append((root, 0.24))
        self.lightning_flash = 0.20
        self._play_sfx("weather_thunder")

    def _apply_atmosphere_visuals(self) -> None:
        # Solar altitude is zero around 6 AM / 6 PM and positive during day.
        solar_angle = math.tau * ((self.time_of_day - 6.0) / 24.0)
        sun_alt = math.sin(solar_angle)
        daylight = self._smoothstep01((sun_alt + 0.10) / 0.42)
        twilight = max(0.0, 1.0 - abs(sun_alt) / 0.24) * (1.0 - 0.30 * daylight)

        night_sky = Vec4(0.002, 0.006, 0.026, 1.0)
        day_sky = Vec4(0.030, 0.125, 0.315, 1.0)
        dusk_sky = Vec4(0.235, 0.072, 0.075, 1.0)
        sky = self._color_lerp(night_sky, day_sky, daylight)
        sky = self._color_lerp(sky, dusk_sky, twilight * 0.58)
        cloud_factor = max(0.0, min(1.0, self.weather_cloud))
        storm_sky = Vec4(0.028, 0.044, 0.075, 1.0)
        sky = self._color_lerp(sky, storm_sky, cloud_factor * 0.68)

        flash = max(0.0, min(1.0, self.lightning_flash / 0.20))
        if flash > 0.0:
            sky = self._color_lerp(sky, Vec4(0.45, 0.57, 0.86, 1.0), flash * 0.88)

        self.setBackgroundColor(sky.x, sky.y, sky.z, 1.0)
        self.scene_buffer.setClearColor(sky)

        ambient_night = Vec4(0.095, 0.115, 0.19, 1.0)
        ambient_day = Vec4(0.30, 0.31, 0.34, 1.0)
        ambient = self._color_lerp(ambient_night, ambient_day, daylight)
        ambient *= (1.0 - 0.24 * cloud_factor)
        ambient.w = 1.0
        if flash > 0.0:
            ambient = self._color_lerp(ambient, Vec4(0.88, 0.93, 1.0, 1.0), flash * 0.92)
        self.ambient_light.setColor(ambient)

        sun_day = Vec4(1.0, 0.88, 0.68, 1.0)
        moon_night = Vec4(0.32, 0.43, 0.72, 1.0)
        directional = self._color_lerp(moon_night, sun_day, daylight)
        directional *= (1.0 - 0.35 * cloud_factor)
        directional.w = 1.0
        if flash > 0.0:
            directional = self._color_lerp(directional, Vec4(1.0, 1.0, 1.0, 1.0), flash)
        self.sun_light.setColor(directional)
        self.sun_np.setHpr((self.time_of_day / 24.0) * 360.0 - 110.0, -28.0 - abs(sun_alt) * 48.0, -8.0)

        fog_night = Vec4(0.010, 0.022, 0.060, 1.0)
        fog_day = Vec4(0.100, 0.175, 0.290, 1.0)
        fog_dusk = Vec4(0.205, 0.090, 0.090, 1.0)
        fog_color = self._color_lerp(fog_night, fog_day, daylight)
        fog_color = self._color_lerp(fog_color, fog_dusk, twilight * 0.45)
        fog_color = self._color_lerp(fog_color, Vec4(0.055, 0.072, 0.095, 1.0), cloud_factor * 0.62)
        if flash > 0.0:
            fog_color = self._color_lerp(fog_color, Vec4(0.48, 0.58, 0.78, 1.0), flash * 0.75)
        self.fog.setColor(fog_color.x, fog_color.y, fog_color.z)
        near = 170.0 - 62.0 * self.weather_rain - 22.0 * cloud_factor
        far = 425.0 - 145.0 * self.weather_rain - 48.0 * cloud_factor
        self.fog.setLinearRange(max(70.0, near), max(245.0, far))

        star_amount = ((1.0 - daylight) ** 1.5) * (1.0 - cloud_factor * 0.86)
        self.present_card.setShaderInput("star_amount", float(max(0.0, star_amount)))
        self.stars_np.setColorScale(1.0, 1.0, 1.0, max(0.0, min(1.0, star_amount)))

        # Celestial bodies orbit relative to the player so the enormous canyon
        # map cannot outrun the sky markers.
        az = math.tau * (self.time_of_day / 24.0)
        radial = 168.0
        sun_pos = Vec3(
            self.player_pos.x + math.cos(az) * radial,
            self.player_pos.y + math.sin(az) * radial,
            self.player_pos.z + sun_alt * 112.0 + 30.0,
        )
        moon_pos = Vec3(
            self.player_pos.x - math.cos(az) * radial,
            self.player_pos.y - math.sin(az) * radial,
            self.player_pos.z - sun_alt * 112.0 + 30.0,
        )
        self.sun_disc.setPos(sun_pos)
        self.moon_disc.setPos(moon_pos)
        if sun_alt > -0.23 and cloud_factor < 0.92:
            self.sun_disc.show()
        else:
            self.sun_disc.hide()
        if sun_alt < 0.30 and cloud_factor < 0.88:
            self.moon_disc.show()
        else:
            self.moon_disc.hide()

        self.cloud_root.setPos(self.player_pos.x, self.player_pos.y, self.player_pos.z)
        cloud_alpha = max(0.0, min(0.86, cloud_factor * 0.82))
        self.cloud_root.setColorScale(1.0, 1.0, 1.0, cloud_alpha)
        self.stars_np.setPos(self.player_pos.x, self.player_pos.y, self.player_pos.z * 0.12)
        self.high_cloud_root.setPos(self.player_pos.x, self.player_pos.y, self.player_pos.z)
        self.high_cloud_root.setH(self.high_cloud_root.getH() + 0.012)
        high_alpha = (0.20 + 0.22 * twilight + 0.10 * daylight) * (1.0 - cloud_factor * 0.55)
        self.high_cloud_root.setColorScale(1.0, 0.88 + twilight * 0.12, 0.88 + daylight * 0.12, max(0.04, high_alpha))
        self.horizon_root.setPos(self.player_pos.x, self.player_pos.y, self.player_pos.z * 0.08)
        biome_now = self._biome_at(self.player_pos.x, self.player_pos.y)
        warm_sky = biome_now in ("SUNSTONE DESERT", "RED CANYONS", "ASH WASTES")
        if warm_sky:
            self.horizon_root.setColorScale(1.0, 0.72 + daylight * 0.18, 0.58 + daylight * 0.20, 0.18 + daylight * 0.24)
        else:
            self.horizon_root.setColorScale(0.72 + daylight * 0.28, 0.64 + daylight * 0.36, 0.78 + daylight * 0.22, 0.16 + daylight * 0.22)

        self.aurora_root.setPos(self.player_pos.x, self.player_pos.y, self.player_pos.z)
        self.aurora_root.setH(self.aurora_root.getH() + 0.004)
        aurora_biome = biome_now in ("FROST HIGHLANDS", "MISTWOOD", "LUMINOUS MARSH")
        aurora_alpha = star_amount * (1.0 - cloud_factor * 0.76) * (0.52 if aurora_biome else 0.0)
        if biome_now == "FROST HIGHLANDS":
            self.aurora_root.setColorScale(0.66, 0.94, 1.0, aurora_alpha)
        elif biome_now == "MISTWOOD":
            self.aurora_root.setColorScale(0.42, 1.0, 0.74, aurora_alpha)
        else:
            self.aurora_root.setColorScale(0.72, 0.62, 1.0, aurora_alpha)

    def _update_weather(self, dt: float) -> None:
        self.time_of_day = (self.time_of_day + dt * (24.0 / self.day_length_seconds)) % 24.0
        self.weather_timer -= dt
        if self.weather_timer <= 0.0:
            self._choose_next_weather()

        response = 1.0 - math.exp(-dt * 0.24)
        self.weather_cloud += (self.weather_cloud_target - self.weather_cloud) * response
        self.weather_rain += (self.weather_rain_target - self.weather_rain) * response

        if self.weather_rain > 0.02:
            wind_x = -2.4 - self.weather_cloud * 3.8
            wind_y = -1.0 - self.weather_cloud * 2.0
            for drop in self.rain_drops:
                drop[0] += wind_x * dt
                drop[1] += wind_y * dt
                drop[2] -= drop[3] * dt
                if drop[2] < -1.0 or abs(drop[0]) > 26.0 or drop[1] < -20.0:
                    drop[0] = self.random.uniform(-22.0, 22.0)
                    drop[1] = self.random.uniform(12.0, 32.0)
                    drop[2] = self.random.uniform(19.0, 30.0)
                    drop[3] = self.random.uniform(20.0, 34.0)
            self.rain_root.setPos(self.player_pos.x, self.player_pos.y, self.player_pos.z + 1.0)
            self.weather_particle_timer -= dt
            if self.weather_particle_timer <= 0.0:
                self.weather_particle_timer = 0.075
                self._rebuild_rain()
        else:
            self.rain_root.hide()

        if self.weather_state == "STORM" and self.weather_cloud > 0.72:
            self.storm_lightning_timer -= dt
            if self.storm_lightning_timer <= 0.0:
                self._spawn_weather_lightning()
                self.storm_lightning_timer = self.random.uniform(2.8, 7.2)

        next_fx: list[tuple[NodePath, float]] = []
        for node, life in self.weather_lightning_fx:
            life -= dt
            if life <= 0.0:
                node.removeNode()
            else:
                alpha = max(0.0, min(1.0, life / 0.24))
                node.setColorScale(1.0, 1.0, 1.0, alpha)
                next_fx.append((node, life))
        self.weather_lightning_fx = next_fx
        self.lightning_flash = max(0.0, self.lightning_flash - dt)
        self._apply_atmosphere_visuals()

    def _spawn_pickups(self) -> None:
        sigil_positions = [
            Vec3(-43.0, -20.0, 0),
            Vec3(66.0, 22.0, 0),
            Vec3(self.LAKE_CENTER.x, self.LAKE_CENTER.y, 0),
        ]
        for idx, p in enumerate(sigil_positions):
            p.z = self._height(p.x, p.y) + 1.55
            node = self._make_octahedron(f"sigil-{idx}", 0.82, Vec4(0.88, 0.10, 1.0, 1))
            node.reparentTo(self.render)
            node.setPos(p)
            node.setLightOff(1)
            self.pickups.append(Pickup(node, "sigil", 1, Vec3(p), self.random.random() * math.tau))

        # Currency breadcrumbs reward leaving the central path without becoming a checklist.
        for i in range(24):
            y = self.random.uniform(-105, 78)
            x = self._path_x(y) + self.random.choice((-1, 1)) * self.random.uniform(4.0, 17.0)
            if math.hypot(x - self.LAKE_CENTER.x, y - self.LAKE_CENTER.y) < self.LAKE_RADIUS:
                continue
            p = Vec3(x, y, self._height(x, y) + 0.85)
            node = self._make_octahedron("memory-coin", 0.26, Vec4(1.0, 0.70, 0.035, 1))
            node.reparentTo(self.render)
            node.setPos(p)
            node.setLightOff(1)
            self.pickups.append(Pickup(node, "coin", 4, Vec3(p), self.random.random() * math.tau))

    def _spawn_enemies(self) -> None:
        positions = [
            (-24, -71), (25, -47), (-60, -12), (48, -7),
            (-77, 57), (75, 47), (-18, 48), (36, 69), (5, 118),
        ]
        for i, (x, y) in enumerate(positions):
            z = self._height(x, y) + 1.15
            node = self._make_octahedron(f"glyph-beast-{i}", 0.78, Vec4(0.92, 0.075, 0.055, 1))
            node.reparentTo(self.render)
            node.setScale(1.0, 0.78, 1.25)
            node.setPos(x, y, z)
            node.setLightOff(1)
            self.enemies.append(Enemy(
                node=node, home=Vec3(x, y, z), kind="beast", hp=2, max_hp=2,
                speed=self.random.uniform(1.45, 2.05), reward=6,
                phase=self.random.random() * math.tau,
            ))

        # Each rift has a small mixed pack so the player immediately learns that
        # demons have different combat roles instead of being recolored beasts.
        demon_specs = (
            ("imp", 3, 2.35, 1, 1.42, 0.34, 0.82, False, 9, 0.78, 0.62, 1.30),
            ("brute", 6, 1.15, 2, 1.82, 0.72, 1.35, False, 18, 1.30, 1.04, 1.42),
            ("hexer", 4, 1.38, 1, 12.0, 0.86, 1.55, True, 14, 0.90, 0.70, 1.48),
            ("pyre", 5, 1.28, 2, 15.5, 0.96, 2.05, True, 17, 1.00, 0.78, 1.50),
        )
        demon_id = 0
        for rift_idx, center in enumerate(self.demon_rift_positions):
            for local_idx, spec in enumerate(demon_specs):
                kind, hp, speed, damage, attack_range, windup, interval, ranged, reward, sx, sy, sz = spec
                ang = local_idx * math.tau / len(demon_specs) + rift_idx * 0.71
                x = center.x + math.cos(ang) * (5.0 + local_idx * 1.35)
                y = center.y + math.sin(ang) * (5.0 + local_idx * 1.35)
                z = self._height(x, y) + 0.45
                node = self._make_demon_model(f"demon-{kind}-{demon_id}", kind)
                node.reparentTo(self.render)
                node.setScale(sx, sy, sz)
                node.setPos(x, y, z)
                self.enemies.append(Enemy(
                    node=node, home=Vec3(x, y, z), kind=kind, hp=hp, max_hp=hp, speed=speed,
                    damage=damage, attack_range=attack_range, detection_range=24.0,
                    windup_duration=windup, attack_interval=interval, ranged=ranged,
                    projectile_speed=(9.2 if kind == "pyre" else 12.0) if ranged else 0.0, reward=reward,
                    scale_x=sx, scale_y=sy, scale_z=sz, phase=self.random.random() * math.tau,
                ))
                demon_id += 1

    # ------------------------------------------------------------------
    # Pass 16: streamed biomes, rivers, settlements and wildlife
    # ------------------------------------------------------------------
    def _procedural_palette_color(self, biome: str, x: float, y: float, z: float) -> Vec4:
        palettes = {
            "SUNSTONE DESERT": (Vec4(0.78, 0.58, 0.28, 1), Vec4(0.67, 0.42, 0.22, 1)),
            "RED CANYONS": (Vec4(0.69, 0.32, 0.22, 1), Vec4(0.82, 0.53, 0.31, 1)),
            "FROST HIGHLANDS": (Vec4(0.58, 0.67, 0.73, 1), Vec4(0.82, 0.90, 0.94, 1)),
            "EMERALD FOREST": (Vec4(0.07, 0.38, 0.09, 1), Vec4(0.16, 0.48, 0.13, 1)),
            "MISTWOOD": (Vec4(0.11, 0.31, 0.22, 1), Vec4(0.27, 0.42, 0.36, 1)),
            "ASH WASTES": (Vec4(0.29, 0.20, 0.22, 1), Vec4(0.46, 0.26, 0.20, 1)),
            "LUMINOUS MARSH": (Vec4(0.07, 0.33, 0.25, 1), Vec4(0.10, 0.49, 0.34, 1)),
            "GOLDEN STEPPE": (Vec4(0.42, 0.44, 0.10, 1), Vec4(0.59, 0.50, 0.13, 1)),
        }
        a, b = palettes.get(biome, palettes["GOLDEN STEPPE"])
        band = 0.5 + 0.5 * math.sin(z * 1.05 + x * 0.018 - y * 0.013)
        return a * (1.0 - band * 0.45) + b * (band * 0.45)

    def _procedural_color(self, x: float, y: float, z: float) -> Vec4:
        # Color blends over the same broad scale as the terrain blend, creating
        # visible foothills/ecotones between neighboring biomes.
        samples = (
            (x, y, 0.48),
            (x + 46.0, y, 0.13),
            (x - 46.0, y, 0.13),
            (x, y + 46.0, 0.13),
            (x, y - 46.0, 0.13),
        )
        result = Vec4(0, 0, 0, 0)
        for sx, sy, weight in samples:
            result += self._procedural_palette_color(self._biome_at(sx, sy), x, y, z) * weight
        return result

    def _make_stream_terrain(self, cx: int, cy: int, root: NodePath) -> None:
        """Build one terrain chunk with shared vertices and cached heights.

        Pass 17 emitted four unique vertices per cell and sampled _height five
        times per vertex for normals.  This indexed grid reduces geometry and
        world-function calls dramatically while producing the same 10x10 surface.
        """
        size = self.CHUNK_SIZE
        x0 = cx * size
        y0 = cy * size
        segments = 10
        step = size / segments

        # One height sample per grid vertex; neighboring cached samples provide
        # a stable central-difference normal without extra procedural queries.
        heights: list[list[float]] = []
        for iy in range(segments + 1):
            row: list[float] = []
            py = y0 + iy * step
            for ix in range(segments + 1):
                px = x0 + ix * step
                row.append(self._height(px, py))
            heights.append(row)

        fmt = GeomVertexFormat.getV3n3c4()
        data = GeomVertexData(f"stream-terrain-{cx}-{cy}", fmt, Geom.UHStatic)
        v = GeomVertexWriter(data, "vertex")
        n = GeomVertexWriter(data, "normal")
        c = GeomVertexWriter(data, "color")

        for iy in range(segments + 1):
            py = y0 + iy * step
            ym = max(0, iy - 1)
            yp = min(segments, iy + 1)
            for ix in range(segments + 1):
                px = x0 + ix * step
                xm = max(0, ix - 1)
                xp = min(segments, ix + 1)
                pz = heights[iy][ix]
                dx_span = max(step, (xp - xm) * step)
                dy_span = max(step, (yp - ym) * step)
                dzdx = (heights[iy][xp] - heights[iy][xm]) / dx_span
                dzdy = (heights[yp][ix] - heights[ym][ix]) / dy_span
                norm = Vec3(-dzdx, -dzdy, 1.0)
                norm.normalize()
                v.addData3(px, py, pz)
                n.addData3(norm)
                c.addData4(self._procedural_color(px, py, pz))

        prim = GeomTriangles(Geom.UHStatic)
        stride = segments + 1
        triangle_count = 0
        for iy in range(segments):
            for ix in range(segments):
                corners = (
                    (x0 + ix * step, y0 + iy * step),
                    (x0 + (ix + 1) * step, y0 + iy * step),
                    (x0 + (ix + 1) * step, y0 + (iy + 1) * step),
                    (x0 + ix * step, y0 + (iy + 1) * step),
                )
                if all(max(abs(px), abs(py)) < self.STREAM_CORE_HALF for px, py in corners):
                    continue
                i0 = iy * stride + ix
                i1 = i0 + 1
                i3 = (iy + 1) * stride + ix
                i2 = i3 + 1
                prim.addVertices(i0, i1, i2)
                prim.addVertices(i0, i2, i3)
                triangle_count += 2

        if triangle_count:
            geom = Geom(data)
            geom.addPrimitive(prim)
            node = GeomNode(f"stream-terrain-{cx}-{cy}")
            node.addGeom(geom)
            np = root.attachNewNode(node)
            np.setTwoSided(True)

    def _make_stream_water(self, cx: int, cy: int, root: NodePath) -> None:
        size = self.CHUNK_SIZE
        x0 = cx * size
        y0 = cy * size
        segments = 12
        step = size / segments
        fmt = GeomVertexFormat.getV3n3c4()
        data = GeomVertexData(f"river-water-{cx}-{cy}", fmt, Geom.UHStatic)
        v = GeomVertexWriter(data, "vertex")
        n = GeomVertexWriter(data, "normal")
        c = GeomVertexWriter(data, "color")
        prim = GeomTriangles(Geom.UHStatic)
        index = 0
        for iy in range(segments):
            for ix in range(segments):
                mx = x0 + (ix + 0.5) * step
                my = y0 + (iy + 0.5) * step
                wz = self._river_water_z(mx, my)
                if wz is None:
                    continue
                corners = ((mx-step*0.52,my-step*0.52),(mx+step*0.52,my-step*0.52),(mx+step*0.52,my+step*0.52),(mx-step*0.52,my+step*0.52))
                for px, py in corners:
                    local_wz = self._river_water_z(px, py)
                    pz = wz if local_wz is None else local_wz
                    v.addData3(px, py, pz + 0.06)
                    n.addData3(0, 0, 1)
                    c.addData4(Vec4(0.035, 0.28, 0.58, 0.91))
                prim.addVertices(index,index+1,index+2)
                prim.addVertices(index,index+2,index+3)
                index += 4
        if index:
            geom=Geom(data); geom.addPrimitive(prim)
            node=GeomNode(f"river-water-{cx}-{cy}"); node.addGeom(geom)
            np=root.attachNewNode(node)
            np.setTransparency(TRANS_ALPHA)
            np.setLightOff(1)

    def _make_stream_roads(self, cx: int, cy: int, root: NodePath) -> None:
        size = self.CHUNK_SIZE
        x0 = cx * size
        y0 = cy * size
        segments = 14
        step = size / segments
        fmt = GeomVertexFormat.getV3n3c4()
        data = GeomVertexData(f"road-surface-{cx}-{cy}", fmt, Geom.UHStatic)
        v = GeomVertexWriter(data, "vertex")
        n = GeomVertexWriter(data, "normal")
        c = GeomVertexWriter(data, "color")
        prim = GeomTriangles(Geom.UHStatic)
        index = 0

        for iy in range(segments):
            for ix in range(segments):
                mx = x0 + (ix + 0.5) * step
                my = y0 + (iy + 0.5) * step
                if max(abs(mx), abs(my)) < self.STREAM_CORE_HALF:
                    continue
                dist, width = self._road_info(mx, my)
                if dist > width:
                    continue
                corners = (
                    (mx - step * 0.52, my - step * 0.52),
                    (mx + step * 0.52, my - step * 0.52),
                    (mx + step * 0.52, my + step * 0.52),
                    (mx - step * 0.52, my + step * 0.52),
                )
                bridge = self._river_water_z(mx, my) is not None
                for px, py in corners:
                    wz = self._river_water_z(px, py)
                    pz = self._height(px, py) + 0.10
                    if bridge or wz is not None:
                        pz = max(pz, (wz if wz is not None else self._height(px, py)) + 0.28)
                    v.addData3(px, py, pz)
                    n.addData3(0, 0, 1)
                    c.addData4(Vec4(0.74, 0.62, 0.39, 1) if not bridge else Vec4(0.62, 0.58, 0.50, 1))
                prim.addVertices(index, index + 1, index + 2)
                prim.addVertices(index, index + 2, index + 3)
                index += 4

        if index:
            geom = Geom(data)
            geom.addPrimitive(prim)
            node = GeomNode(f"road-surface-{cx}-{cy}")
            node.addGeom(geom)
            np = root.attachNewNode(node)
            np.setTwoSided(True)

    def _build_proc_landmark(self, cx: int, cy: int, root: NodePath, rng: random.Random, kind: str) -> None:
        if not kind:
            return
        center_x, center_y = self._landmark_center(cx, cy)
        center_z = self._height(center_x, center_y)
        obstacles = self.proc_obstacles.setdefault((cx, cy), [])

        if kind == "DRAGON NEST":
            for i in range(10):
                ang = i * math.tau / 10.0
                radius = 7.0 + (i % 2) * 1.6
                x = center_x + math.cos(ang) * radius
                y = center_y + math.sin(ang) * radius
                z = self._height(x, y)
                rock = self._make_octahedron("nest-rock", 1.15 + (i % 3) * 0.22, Vec4(0.31, 0.15, 0.12, 1))
                rock.reparentTo(root)
                rock.setPos(x, y, z + 0.8)
                rock.setScale(1.0, 0.85, 1.55)
            ember = self._make_octahedron("dragon-nest-ember", 1.25, Vec4(1.0, 0.18, 0.025, 1))
            ember.reparentTo(root)
            ember.setPos(center_x, center_y, center_z + 0.9)
            ember.setLightOff(1)
            for i in range(3):
                egg = self._make_octahedron("dragon-egg", 0.58, Vec4(0.78, 0.46, 0.16, 1))
                egg.reparentTo(root)
                egg.setPos(center_x + (i - 1) * 1.6, center_y + (0.7 if i == 1 else -0.4), center_z + 0.75)
                egg.setScale(0.72, 0.72, 1.35)
            return

        if kind == "RUNE ARCH":
            foundation_color = Vec4(0.36, 0.37, 0.38, 1)
            base_z, _ = self._add_terrain_foundation(
                root, "rune-arch-foundation", center_x, center_y, 3.9, 1.05, foundation_color
            )
            self._add_foundation_toe(
                root, "rune-arch-foundation", center_x, center_y, 3.9, 1.05, base_z, foundation_color
            )
            self._add_ground_ribbon(
                root, "rune-arch-worn-crossing", center_x, center_y - 4.6,
                center_x, center_y + 4.6, 0.82, self._biome_ground_dressing_color(center_x, center_y),
            )
            for side in (-1, 1):
                x = center_x + side * 3.0
                pillar = self._make_box("rune-arch-pillar", Vec3(0.7, 0.9, 4.2), Vec4(0.53, 0.55, 0.56, 1))
                pillar.reparentTo(root)
                pillar.setPos(x, center_y, base_z + 4.2)
                obstacles.append((x, center_y, 0.9))
            lintel = self._make_box("rune-arch-lintel", Vec3(3.8, 0.9, 0.62), Vec4(0.56, 0.58, 0.60, 1))
            lintel.reparentTo(root)
            lintel.setPos(center_x, center_y, base_z + 8.0)
            rune = self._make_octahedron("rune-arch-light", 0.60, Vec4(0.74, 0.18, 1.0, 1))
            rune.reparentTo(root)
            rune.setPos(center_x, center_y - 0.4, base_z + 5.0)
            rune.setLightOff(1)
            return

        if kind == "STONE CIRCLE":
            for i in range(9):
                ang = i * math.tau / 9.0
                x = center_x + math.cos(ang) * 6.8
                y = center_y + math.sin(ang) * 6.8
                z = self._height(x, y)
                half_h = 2.1 + (i % 3) * 0.4
                stone = self._make_box("standing-stone", Vec3(0.55, 0.75, half_h), Vec4(0.48, 0.50, 0.52, 1))
                stone.reparentTo(root)
                # Embed the stone consistently instead of using one fixed center Z
                # for three different heights (which left the shortest stones floating).
                stone.setPos(x, y, z + half_h - 0.12)
                stone.setH(math.degrees(ang) + 90)
                obstacles.append((x, y, 0.8))
            return

        if kind == "OLD WATCHTOWER":
            watch_foundation_color = Vec4(0.35, 0.34, 0.33, 1)
            base_z, _ = self._add_terrain_foundation(
                root, "watchtower-foundation", center_x, center_y, 2.35, 2.35, watch_foundation_color
            )
            self._add_foundation_toe(
                root, "watchtower-foundation", center_x, center_y, 2.35, 2.35, base_z, watch_foundation_color
            )
            tower = self._make_box("old-watchtower", Vec3(2.2, 2.2, 7.2), Vec4(0.49, 0.46, 0.43, 1))
            tower.reparentTo(root)
            tower.setPos(center_x, center_y, base_z + 7.2)
            cap = self._make_octahedron("watchtower-cap", 2.45, Vec4(0.36, 0.30, 0.28, 1))
            cap.reparentTo(root)
            cap.setPos(center_x, center_y, base_z + 14.8)
            cap.setScale(1.0, 1.0, 0.42)
            beacon = self._make_octahedron("watchtower-light", 0.36, Vec4(0.90, 0.38, 0.95, 1))
            beacon.reparentTo(root)
            beacon.setPos(center_x, center_y, base_z + 15.4)
            beacon.setLightOff(1)
            obstacles.append((center_x, center_y, 2.5))

    def _make_proc_tree(self, root: NodePath, x: float, y: float, z: float, rng: random.Random, biome: str) -> None:
        trunk = self._make_box("wild-trunk", Vec3(0.22, 0.22, 1.35), Vec4(0.25, 0.15, 0.06, 1))
        trunk.reparentTo(root); trunk.setPos(x, y, z + 1.25)
        if biome == "FROST HIGHLANDS":
            crown_color = Vec4(0.22, 0.40, 0.38, 1)
        elif biome == "MISTWOOD":
            crown_color = Vec4(0.08, 0.29, 0.22, 1)
        else:
            crown_color = Vec4(0.06, 0.43, 0.07, 1)
        for k, (dz, scale) in enumerate(((2.3, 1.5), (3.25, 1.2), (4.0, 0.82))):
            crown = self._make_octahedron(f"wild-crown-{k}", 1.15, crown_color)
            crown.reparentTo(root); crown.setPos(x, y, z + dz); crown.setScale(scale, scale, scale * 0.75)

    def _add_settlement_edge_dressing(
        self, cx: int, cy: int, root: NodePath, city: bool
    ) -> None:
        """Restore sparse biome-native detail at the settlement perimeter.

        Generic streamed props are deliberately cleared from the settlement core;
        this controlled ring prevents the result from becoming a sterile cutout.
        """
        center_x, center_y = self._settlement_center(cx, cy)
        rng = random.Random(self._chunk_seed(cx, cy, 229))
        biome = self._biome_at(center_x, center_y)
        radius = 28.0 if city else 18.5
        count = 8 if city else 6
        for i in range(count):
            ang = (i / count) * math.tau + rng.uniform(-0.16, 0.16)
            r = radius + rng.uniform(-1.8, 2.4)
            x = center_x + math.cos(ang) * r
            y = center_y + math.sin(ang) * r
            road_dist, road_width = self._road_info(x, y)
            if self._river_water_z(x, y) is not None or road_dist < road_width * 1.30:
                continue
            z = self._height(x, y)
            if biome in ("EMERALD FOREST", "MISTWOOD"):
                self._make_proc_tree(root, x, y, z, rng, biome)
            elif biome == "FROST HIGHLANDS":
                stone = self._make_octahedron("settlement-frost-stone", rng.uniform(0.28, 0.52), Vec4(0.52, 0.58, 0.57, 1))
                stone.reparentTo(root); stone.setPos(x, y, z + 0.26)
            elif biome == "LUMINOUS MARSH":
                crystal = self._make_octahedron("settlement-marsh-light", rng.uniform(0.16, 0.28), Vec4(0.10, 0.76, 0.61, 1))
                crystal.reparentTo(root); crystal.setPos(x, y, z + 0.38); crystal.setLightOff(1)
            elif biome in ("RED CANYONS", "SUNSTONE DESERT"):
                stone = self._make_octahedron("settlement-sandstone", rng.uniform(0.30, 0.55), Vec4(0.58, 0.34, 0.17, 1))
                stone.reparentTo(root); stone.setPos(x, y, z + 0.25)
                stone.setScale(1.15, 0.85, 0.60)
            elif biome == "ASH WASTES":
                crystal = self._make_octahedron("settlement-ash-stone", rng.uniform(0.24, 0.48), Vec4(0.39, 0.27, 0.36, 1))
                crystal.reparentTo(root); crystal.setPos(x, y, z + 0.28)
            else:
                stone = self._make_octahedron("settlement-steppe-stone", rng.uniform(0.24, 0.44), Vec4(0.47, 0.39, 0.20, 1))
                stone.reparentTo(root); stone.setPos(x, y, z + 0.24)

    def _build_proc_settlement(self, cx: int, cy: int, root: NodePath, rng: random.Random, city: bool) -> None:
        center_x, center_y = self._settlement_center(cx, cy)
        count = rng.randint(12, 18) if city else rng.randint(5, 8)
        radius = 21.0 if city else 12.5
        obstacles = self.proc_obstacles.setdefault((cx, cy), [])
        road_x, road_y = self._road_centers(center_x, center_y)
        vertical_road = abs(center_x - road_x) <= abs(center_y - road_y)

        for i in range(count):
            if city:
                # Buildings line two avenues instead of forming a random ring.
                side = -1 if i % 2 == 0 else 1
                rank = i // 2
                along = (rank - (count // 4)) * 4.4 + rng.uniform(-1.0, 1.0)
                across = side * rng.uniform(6.0, 11.5)
                x = center_x + (across if vertical_road else along)
                y = center_y + (along if vertical_road else across)
            else:
                ang = (i / max(1, count)) * math.tau + rng.uniform(-0.20, 0.20)
                dist = rng.uniform(5.2, radius)
                x = center_x + math.cos(ang) * dist
                y = center_y + math.sin(ang) * dist

            if self._river_water_z(x, y) is not None:
                continue
            floors = rng.randint(2, 4) if city else 1
            w = rng.uniform(1.9, 3.0) if city else rng.uniform(1.7, 2.5)
            h = floors * rng.uniform(1.45, 1.9)
            wall_color = Vec4(0.64, 0.52, 0.34, 1) if not city else Vec4(0.58, 0.49, 0.40, 1)
            foundation_color = Vec4(0.38, 0.37, 0.34, 1) if not city else Vec4(0.36, 0.36, 0.35, 1)
            foundation_name = "city-house-foundation" if city else "village-house-foundation"
            z, _ = self._add_terrain_foundation(
                root, foundation_name, x, y, w, w * 0.78, foundation_color,
            )
            self._add_foundation_toe(
                root, foundation_name, x, y, w, w * 0.78, z, foundation_color
            )
            if city:
                target_x, target_y = (road_x, y) if vertical_road else (x, road_y)
            else:
                target_x, target_y = center_x, center_y
            self._add_structure_approach(
                root, foundation_name, x, y, w, w * 0.78, z,
                target_x, target_y, foundation_color,
                0.66 if city else 0.54,
                6.2 if city else 3.4,
            )
            wall = self._make_box("city-house" if city else "village-house", Vec3(w, w * 0.78, h), wall_color)
            wall.reparentTo(root)
            wall.setPos(x, y, z + h)
            self._add_structure_entrance(
                root, "city-house" if city else "village-house",
                x, y, w, w * 0.78, z, target_x, target_y,
                wall_color, foundation_color, city=city,
            )
            roof_color = Vec4(0.43, 0.18, 0.13, 1) if not city else Vec4(0.35, 0.22, 0.18, 1)
            roof = self._make_octahedron("settlement-roof", w * 0.88, roof_color)
            roof.reparentTo(root)
            roof.setPos(x, y, z + h * 2.0 + 0.42)
            roof.setScale(1.0, 0.82, 0.45)
            roof.setH(0 if vertical_road else 90)
            obstacles.append((x, y, w * 1.05))

        cz = self._height(center_x, center_y)
        if city:
            # A central keep and paired gate towers make cities unmistakable from afar.
            keep_foundation_color = Vec4(0.34, 0.34, 0.34, 1)
            cz, _ = self._add_terrain_foundation(
                root, "city-keep-foundation", center_x, center_y, 4.0, 4.0, keep_foundation_color
            )
            self._add_foundation_toe(
                root, "city-keep-foundation", center_x, center_y, 4.0, 4.0, cz, keep_foundation_color
            )
            keep_wall_color = Vec4(0.54, 0.50, 0.46, 1)
            keep = self._make_box("city-keep", Vec3(3.8, 3.8, 6.8), keep_wall_color)
            keep.reparentTo(root)
            keep.setPos(center_x, center_y, cz + 6.8)
            keep_target_x = center_x if vertical_road else center_x - 8.0
            keep_target_y = center_y - 8.0 if vertical_road else center_y
            self._add_structure_entrance(
                root, "city-keep", center_x, center_y, 3.8, 3.8, cz,
                keep_target_x, keep_target_y, keep_wall_color, keep_foundation_color,
                city=True, monumental=True,
            )
            crown = self._make_octahedron("city-keep-crown", 3.2, Vec4(0.40, 0.31, 0.27, 1))
            crown.reparentTo(root)
            crown.setPos(center_x, center_y, cz + 14.0)
            crown.setScale(1.0, 1.0, 0.48)
            obstacles.append((center_x, center_y, 4.2))

            for side in (-1, 1):
                offset = 16.5 * side
                gx = center_x + (5.8 * side if vertical_road else offset)
                gy = center_y + (offset if vertical_road else 5.8 * side)
                gate_foundation_color = Vec4(0.35, 0.34, 0.33, 1)
                gz, _ = self._add_terrain_foundation(
                    root, "city-gate-foundation", gx, gy, 2.12, 2.12, gate_foundation_color
                )
                self._add_foundation_toe(
                    root, "city-gate-foundation", gx, gy, 2.12, 2.12, gz, gate_foundation_color
                )
                target_x, target_y = (road_x, gy) if vertical_road else (gx, road_y)
                self._add_structure_approach(
                    root, "city-gate-foundation", gx, gy, 2.12, 2.12, gz,
                    target_x, target_y, gate_foundation_color, 0.76, 5.4,
                )
                gate_wall_color = Vec4(0.56, 0.48, 0.40, 1)
                tower = self._make_box("city-gate-tower", Vec3(2.0, 2.0, 4.7), gate_wall_color)
                tower.reparentTo(root)
                tower.setPos(gx, gy, gz + 4.7)
                self._add_structure_entrance(
                    root, "city-gate-tower", gx, gy, 2.0, 2.0, gz,
                    target_x, target_y, gate_wall_color, gate_foundation_color,
                    city=True,
                )
                obstacles.append((gx, gy, 2.2))
        else:
            # The small village well should nest into the terrain rather than sit on
            # a building-sized plinth.  Its base is deliberately embedded at the
            # center sample while the larger enclosed structures use full footings.
            cz = self._height(center_x, center_y)
            well = self._make_octahedron("village-well", 1.0, Vec4(0.48, 0.45, 0.38, 1))
            well.reparentTo(root)
            well.setScale(1.25, 1.25, 0.45)
            well.setPos(center_x, center_y, cz + 0.46)
            lantern = self._make_octahedron("village-lantern", 0.30, Vec4(0.95, 0.60, 0.12, 1))
            lantern.reparentTo(root)
            lantern.setPos(center_x, center_y, cz + 2.3)
            lantern.setLightOff(1)

        self._add_settlement_edge_dressing(cx, cy, root, city)

        beacon = self._make_octahedron("city-beacon" if city else "village-lantern-high", 0.56 if city else 0.30, Vec4(0.92, 0.36, 0.98, 1))
        beacon.reparentTo(root)
        beacon.setPos(center_x, center_y, cz + (15.4 if city else 3.2))
        beacon.setLightOff(1)

    def _make_stream_monster(self, kind: str, name: str) -> NodePath:
        colors = {
            "wolf": Vec4(0.80, 0.12, 0.08, 1), "scorpion": Vec4(0.96, 0.24, 0.05, 1),
            "wraith": Vec4(0.72, 0.08, 0.26, 1), "golem": Vec4(0.72, 0.23, 0.08, 1),
            "frostling": Vec4(0.72, 0.22, 0.36, 1), "bogling": Vec4(0.76, 0.11, 0.20, 1),
            "ashfiend": Vec4(0.98, 0.10, 0.02, 1), "dragon": Vec4(0.95, 0.07, 0.025, 1),
        }
        color = colors.get(kind, Vec4(0.9,0.08,0.04,1))
        if kind != "dragon":
            monster = self.render.attachNewNode(f"{name}-root")
            body = self._make_octahedron(name, 0.82 if kind != "golem" else 1.22, color)
            body.reparentTo(monster)
            body.setLightOff(1)
            if kind == "scorpion": body.setScale(1.15, 1.55, 0.55)
            elif kind == "wraith": body.setScale(0.82, 0.76, 1.65)
            elif kind == "golem": body.setScale(1.35, 1.05, 1.55)
            else: body.setScale(1.05, 0.78, 1.20)
            return monster
        dragon = self.render.attachNewNode(name)
        body = self._make_octahedron("dragon-body", 1.55, color); body.reparentTo(dragon); body.setScale(1.25,2.0,0.88)
        head = self._make_octahedron("dragon-head", 0.82, Vec4(1.0,0.16,0.03,1)); head.reparentTo(dragon); head.setPos(0,2.45,0.35)
        for side in (-1,1):
            wing = self._make_box("dragon-wing", Vec3(2.45,0.10,0.72), Vec4(0.58,0.06,0.04,1)); wing.reparentTo(dragon); wing.setPos(side*2.05,-0.15,0.35); wing.setHpr(side*11, side*18, side*20)
        dragon.setLightOff(1)
        return dragon

    def _spawn_stream_monsters(
        self,
        cx: int,
        cy: int,
        root: NodePath,
        rng: random.Random,
        biome: str,
        city: bool,
        village: bool,
        landmark: str = "",
    ) -> None:
        if city:
            count = rng.randint(0, 1)
        elif village:
            count = rng.randint(1, 2)
        else:
            count = rng.randint(1, 3)
        kind_by_biome = {
            "SUNSTONE DESERT": "scorpion", "RED CANYONS": "golem", "FROST HIGHLANDS": "frostling",
            "EMERALD FOREST": "wolf", "MISTWOOD": "wraith", "ASH WASTES": "ashfiend",
            "LUMINOUS MARSH": "bogling", "GOLDEN STEPPE": "wolf",
        }
        kind = kind_by_biome.get(biome, "wolf")
        size = self.CHUNK_SIZE
        for i in range(count):
            x = cx * size + rng.uniform(8, size - 8)
            y = cy * size + rng.uniform(8, size - 8)
            spawn_key = ("wild", cx, cy, i, kind)
            if spawn_key in self.defeated_stream_spawns:
                continue
            if self._river_water_z(x, y) is not None:
                continue
            z = self._height(x, y)
            node = self._make_stream_monster(kind, f"{kind}-{cx}-{cy}-{i}")
            node.reparentTo(root)
            node.setPos(x, y, z + 0.8)
            specs = {
                "wolf": (3, 2.25, 1, 1.45, 0.38, 0.90, False, 8),
                "scorpion": (4, 1.75, 1, 1.55, 0.50, 1.10, False, 10),
                "wraith": (4, 1.55, 1, 10.5, 0.72, 1.45, True, 13),
                "golem": (8, 0.95, 2, 1.85, 0.75, 1.55, False, 18),
                "frostling": (5, 1.55, 1, 1.65, 0.52, 1.08, False, 12),
                "bogling": (4, 1.65, 1, 1.60, 0.48, 1.0, False, 10),
                "ashfiend": (5, 1.62, 2, 12.5, 0.82, 1.75, True, 16),
            }
            hp, spd, dmg, ar, wind, interval, ranged, reward = specs[kind]
            self.enemies.append(Enemy(
                node=node,
                home=Vec3(x, y, z + 0.8),
                kind=kind,
                hp=hp,
                max_hp=hp,
                speed=spd,
                damage=dmg,
                attack_range=ar,
                detection_range=26.0,
                windup_duration=wind,
                attack_interval=interval,
                ranged=ranged,
                projectile_speed=11.0 if ranged else 0.0,
                reward=reward,
                phase=rng.random() * math.tau,
                stream_chunk=(cx, cy),
                spawn_key=spawn_key,
            ))

        # Dragon nests always have a territorial dragon until it is defeated.
        # Elsewhere, a very small deterministic chance creates a wandering dragon.
        distance_chunks = math.hypot(cx, cy)
        has_dragon = landmark == "DRAGON NEST"
        if not has_dragon and distance_chunks > 5.0:
            has_dragon = rng.random() < 0.008
        dragon_key = ("dragon", cx, cy)
        if has_dragon and dragon_key not in self.defeated_stream_spawns:
            if landmark == "DRAGON NEST":
                x, y = self._landmark_center(cx, cy)
            else:
                x = cx * size + rng.uniform(16, size - 16)
                y = cy * size + rng.uniform(16, size - 16)
            z = self._height(x, y)
            node = self._make_stream_monster("dragon", f"dragon-{cx}-{cy}")
            node.reparentTo(root)
            node.setPos(x, y, z + 5.0)
            self.enemies.append(Enemy(
                node=node,
                home=Vec3(x, y, z + 5.0),
                kind="dragon",
                hp=20 if landmark == "DRAGON NEST" else 18,
                max_hp=20 if landmark == "DRAGON NEST" else 18,
                speed=1.48,
                damage=3,
                attack_range=19.0,
                detection_range=46.0,
                windup_duration=1.05,
                attack_interval=2.55,
                ranged=True,
                projectile_speed=11.0,
                reward=80 if landmark == "DRAGON NEST" else 65,
                scale_x=1.0,
                scale_y=1.0,
                scale_z=1.0,
                phase=rng.random() * math.tau,
                stream_chunk=(cx, cy),
                spawn_key=dragon_key,
            ))

    def _build_stream_chunk(self, cx: int, cy: int) -> None:
        key=(cx,cy)
        root=self.render.attachNewNode(f"world-chunk-{cx}-{cy}")
        self.stream_chunks[key]=root
        self.proc_obstacles[key]=[]
        self._make_stream_terrain(cx, cy, root)
        self._make_stream_water(cx, cy, root)
        self._make_stream_roads(cx, cy, root)
        rng = random.Random(self._chunk_seed(cx, cy, 101))
        biome = self._biome_at((cx + 0.5) * self.CHUNK_SIZE, (cy + 0.5) * self.CHUNK_SIZE)
        settlement = self._settlement_kind(cx, cy)
        city = settlement == "CITY"
        village = settlement == "VILLAGE"
        settlement_center = self._settlement_center(cx, cy) if settlement else None
        settlement_clear_radius = 30.5 if city else 20.5 if village else 0.0

        # Decorative density stays deliberately low; the ASCII renderer benefits from
        # readable silhouettes more than thousands of tiny meshes.
        prop_count = 10 if biome in ("EMERALD FOREST", "MISTWOOD") else 6
        for i in range(prop_count):
            x = cx * self.CHUNK_SIZE + rng.uniform(5, self.CHUNK_SIZE - 5)
            y = cy * self.CHUNK_SIZE + rng.uniform(5, self.CHUNK_SIZE - 5)
            road_dist, road_width = self._road_info(x, y)
            if (
                max(abs(x), abs(y)) < self.STREAM_CORE_HALF
                or self._in_utopia_sanctuary(x, y, 8.0)
                or self._river_water_z(x, y) is not None
                or road_dist < road_width * 1.7
            ):
                continue
            z = self._height(x, y)
            in_settlement_clearance = (
                settlement_center is not None
                and math.hypot(x - settlement_center[0], y - settlement_center[1]) < settlement_clear_radius
            )
            if in_settlement_clearance:
                # Preserve Pass 21's RNG stream exactly even when suppressing a
                # decorative prop, so settlement/enemy generation does not move.
                if biome in ("RED CANYONS", "SUNSTONE DESERT"):
                    rng.uniform(1.8, 4.8)
                    rng.uniform(0.5, 1.4)
                    rng.uniform(0.5, 1.3)
                elif biome == "LUMINOUS MARSH":
                    rng.uniform(0.18, 0.42)
                elif biome == "ASH WASTES":
                    rng.uniform(0.35, 0.72)
                elif biome not in ("EMERALD FOREST", "MISTWOOD", "FROST HIGHLANDS"):
                    rng.uniform(0.32, 0.70)
                continue
            if biome in ("EMERALD FOREST", "MISTWOOD", "FROST HIGHLANDS"):
                self._make_proc_tree(root, x, y, z, rng, biome)
            elif biome in ("RED CANYONS", "SUNSTONE DESERT"):
                half_h = rng.uniform(1.8, 4.8)
                spire = self._make_box(
                    "sandstone-spire",
                    Vec3(rng.uniform(0.5, 1.4), rng.uniform(0.5, 1.3), half_h),
                    Vec4(0.67, 0.36, 0.20, 1),
                )
                spire.reparentTo(root)
                spire.setPos(x, y, z + half_h)
            elif biome == "LUMINOUS MARSH":
                crystal = self._make_octahedron("marsh-light", rng.uniform(0.18, 0.42), Vec4(0.12, 0.86, 0.72, 1))
                crystal.reparentTo(root)
                crystal.setPos(x, y, z + 0.6)
                crystal.setLightOff(1)
            elif biome == "ASH WASTES":
                crystal = self._make_octahedron("ash-crystal", rng.uniform(0.35, 0.72), Vec4(0.72, 0.08, 0.68, 1))
                crystal.reparentTo(root)
                crystal.setPos(x, y, z + 0.8)
                crystal.setScale(0.65, 0.65, 1.8)
                crystal.setLightOff(1)
            else:
                stone = self._make_octahedron("steppe-stone", rng.uniform(0.32, 0.70), Vec4(0.50, 0.45, 0.25, 1))
                stone.reparentTo(root)
                stone.setPos(x, y, z + 0.35)

        landmark = self._landmark_kind(cx, cy)
        chunk_center_x = (cx + 0.5) * self.CHUNK_SIZE
        chunk_center_y = (cy + 0.5) * self.CHUNK_SIZE
        sanctuary_chunk = self._in_utopia_sanctuary(chunk_center_x, chunk_center_y, self.CHUNK_SIZE * 0.8)
        if not sanctuary_chunk:
            if city or village:
                self._build_proc_settlement(cx, cy, root, rng, city)
            elif landmark:
                self._build_proc_landmark(cx, cy, root, rng, landmark)
            self._spawn_stream_monsters(cx, cy, root, rng, biome, city, village, landmark)

    def _unload_stream_chunk(self, key: tuple[int,int]) -> None:
        root=self.stream_chunks.pop(key,None)
        if root is not None and not root.isEmpty(): root.removeNode()
        self.proc_obstacles.pop(key,None)
        survivors=[]
        for enemy in self.enemies:
            if enemy.stream_chunk == key:
                enemy.alive=False
            else:
                survivors.append(enemy)
        self.enemies=survivors

    def _update_world_stream(self, force: bool = False) -> None:
        cx = int(math.floor(self.player_pos.x / self.CHUNK_SIZE))
        cy = int(math.floor(self.player_pos.y / self.CHUNK_SIZE))
        center = (cx, cy)

        if force or center != self.last_stream_center:
            self.last_stream_center = center
            wanted: set[tuple[int, int]] = set()
            for oy in range(-self.STREAM_RADIUS, self.STREAM_RADIUS + 1):
                for ox in range(-self.STREAM_RADIUS, self.STREAM_RADIUS + 1):
                    key = (cx + ox, cy + oy)
                    # Chunks fully inside the authored central square are already covered.
                    x0 = key[0] * self.CHUNK_SIZE
                    y0 = key[1] * self.CHUNK_SIZE
                    x1 = x0 + self.CHUNK_SIZE
                    y1 = y0 + self.CHUNK_SIZE
                    if max(abs(x0), abs(x1)) < self.STREAM_CORE_HALF and max(abs(y0), abs(y1)) < self.STREAM_CORE_HALF:
                        continue
                    wanted.add(key)

            self.stream_wanted = wanted
            for key in list(self.stream_chunks):
                if key not in wanted:
                    self._unload_stream_chunk(key)

            missing = [key for key in wanted if key not in self.stream_chunks]
            missing.sort(key=lambda key: (key[0] - cx) ** 2 + (key[1] - cy) ** 2)
            self.stream_build_queue = missing

            # On a fresh load, establish a close safety ring immediately, then let
            # the remaining horizon fill incrementally over subsequent frames.
            if force:
                immediate = [
                    key for key in self.stream_build_queue
                    if max(abs(key[0] - cx), abs(key[1] - cy)) <= 2
                ]
                for key in immediate:
                    if key in self.stream_wanted and key not in self.stream_chunks:
                        self._build_stream_chunk(*key)
                immediate_set = set(immediate)
                self.stream_build_queue = [key for key in self.stream_build_queue if key not in immediate_set]

        built = 0
        while self.stream_build_queue and built < self.stream_build_budget:
            key = self.stream_build_queue.pop(0)
            if key in self.stream_wanted and key not in self.stream_chunks:
                self._build_stream_chunk(*key)
                built += 1

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------
    def _make_box(self, name: str, half: Vec3, color: Vec4) -> NodePath:
        fmt = GeomVertexFormat.getV3n3c4()
        data = GeomVertexData(name, fmt, Geom.UHStatic)
        v = GeomVertexWriter(data, "vertex")
        n = GeomVertexWriter(data, "normal")
        c = GeomVertexWriter(data, "color")
        prim = GeomTriangles(Geom.UHStatic)

        hx, hy, hz = half.x, half.y, half.z
        faces = [
            ((-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz), (0, -1, 0)),
            ((hx, hy, -hz), (-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz), (0, 1, 0)),
            ((-hx, hy, -hz), (-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz), (-1, 0, 0)),
            ((hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz), (1, 0, 0)),
            ((-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz), (0, 0, 1)),
            ((-hx, hy, -hz), (hx, hy, -hz), (hx, -hy, -hz), (-hx, -hy, -hz), (0, 0, -1)),
        ]
        index = 0
        for a, b, cc, d, norm in faces:
            for p in (a, b, cc, d):
                v.addData3(*p)
                n.addData3(*norm)
                c.addData4(color)
            prim.addVertices(index, index + 1, index + 2)
            prim.addVertices(index, index + 2, index + 3)
            index += 4

        geom = Geom(data)
        geom.addPrimitive(prim)
        node = GeomNode(name)
        node.addGeom(geom)
        return NodePath(node)

    def _make_disc(self, name: str, radius: float, segments: int, color: Vec4) -> NodePath:
        fmt = GeomVertexFormat.getV3n3c4()
        data = GeomVertexData(name, fmt, Geom.UHStatic)
        v = GeomVertexWriter(data, "vertex")
        n = GeomVertexWriter(data, "normal")
        c = GeomVertexWriter(data, "color")
        prim = GeomTriangles(Geom.UHStatic)

        v.addData3(0, 0, 0)
        n.addData3(0, 0, 1)
        c.addData4(color)
        for i in range(segments + 1):
            a = (i / segments) * math.tau
            v.addData3(math.cos(a) * radius, math.sin(a) * radius, 0)
            n.addData3(0, 0, 1)
            c.addData4(color)
        for i in range(segments):
            prim.addVertices(0, i + 1, i + 2)

        geom = Geom(data)
        geom.addPrimitive(prim)
        node = GeomNode(name)
        node.addGeom(geom)
        return NodePath(node)

    def _make_octahedron(self, name: str, radius: float, color: Vec4) -> NodePath:
        fmt = GeomVertexFormat.getV3n3c4()
        data = GeomVertexData(name, fmt, Geom.UHStatic)
        v = GeomVertexWriter(data, "vertex")
        n = GeomVertexWriter(data, "normal")
        c = GeomVertexWriter(data, "color")
        prim = GeomTriangles(Geom.UHStatic)

        verts = [
            Vec3(0, 0, radius), Vec3(radius, 0, 0), Vec3(0, radius, 0),
            Vec3(-radius, 0, 0), Vec3(0, -radius, 0), Vec3(0, 0, -radius),
        ]
        faces = ((0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4))
        for tri in faces:
            a, b, cc = [verts[i] for i in tri]
            norm = (b - a).cross(cc - a)
            norm.normalize()
            base = data.getNumRows()
            for p in (a, b, cc):
                v.addData3(p)
                n.addData3(norm)
                c.addData4(color)
            prim.addVertices(base, base + 1, base + 2)

        geom = Geom(data)
        geom.addPrimitive(prim)
        node = GeomNode(name)
        node.addGeom(geom)
        return NodePath(node)

    # ------------------------------------------------------------------
    # First-person item / HUD
    # ------------------------------------------------------------------
    def _make_sword_blade(self) -> NodePath:
        """Create a compact tapered blade rather than the old rectangular bar."""
        fmt = GeomVertexFormat.getV3n3c4()
        data = GeomVertexData("sword-blade", fmt, Geom.UHStatic)
        v = GeomVertexWriter(data, "vertex")
        n = GeomVertexWriter(data, "normal")
        c = GeomVertexWriter(data, "color")
        prim = GeomTriangles(Geom.UHStatic)
        metal = Vec4(0.76, 0.84, 0.96, 1)

        # Blade runs forward along local +Y.  It narrows once before the point,
        # which stays readable even after the world is converted into glyphs.
        w0, w1, t = 0.095, 0.070, 0.024
        y0, y1, y2 = 0.0, 1.02, 1.28
        pts = [
            Vec3(-w0, y0, -t), Vec3(w0, y0, -t), Vec3(w0, y0, t), Vec3(-w0, y0, t),
            Vec3(-w1, y1, -t), Vec3(w1, y1, -t), Vec3(w1, y1, t), Vec3(-w1, y1, t),
            Vec3(0.0, y2, -t), Vec3(0.0, y2, t),
        ]

        def face(indices):
            base = data.getNumRows()
            a, b, cc = (pts[i] for i in indices[:3])
            norm = (b - a).cross(cc - a)
            if norm.lengthSquared() > 0.000001:
                norm.normalize()
            else:
                norm = Vec3(0, 0, 1)
            for i in indices:
                v.addData3(pts[i])
                n.addData3(norm)
                c.addData4(metal)
            if len(indices) == 3:
                prim.addVertices(base, base + 1, base + 2)
            else:
                prim.addVertices(base, base + 1, base + 2)
                prim.addVertices(base, base + 2, base + 3)

        face((3, 2, 6, 7))
        face((7, 6, 9))
        face((0, 4, 5, 1))
        face((4, 8, 5))
        face((0, 3, 7, 4))
        face((4, 7, 9, 8))
        face((1, 5, 6, 2))
        face((5, 8, 9, 6))
        face((0, 1, 2, 3))

        geom = Geom(data)
        geom.addPrimitive(prim)
        node = GeomNode("sword-blade")
        node.addGeom(geom)
        return NodePath(node)

    def _build_first_person_weapon(self) -> None:
        # The visible model keeps its original orientation, but it now sits under
        # a dedicated hand pivot.  Earlier passes animated the model origin near
        # the guard, which made the far end of the sword appear to act like the
        # hinge during a wide slash.  The pivot is now centered in the grip.
        pivot = self.scene_cam.attachNewNode("first-person-sword-hand-pivot")
        root = pivot.attachNewNode("first-person-sword-model")
        root.setPos(0, 0.26, 0)

        blade = self._make_sword_blade()
        blade.reparentTo(root)
        blade.setPos(0, 0.10, 0)
        blade.setLightOff(1)

        # A narrow central ridge makes the blade easier to read in both raw 3D
        # and the semantic ASCII pass without relying on a texture asset.
        ridge = self._make_box("blade-ridge", Vec3(0.022, 0.47, 0.009), Vec4(0.48, 0.57, 0.72, 1))
        ridge.reparentTo(root)
        ridge.setPos(0, 0.58, 0.031)
        ridge.setLightOff(1)

        guard = self._make_box("guard", Vec3(0.29, 0.045, 0.048), Vec4(0.84, 0.61, 0.08, 1))
        guard.reparentTo(root)
        guard.setPos(0, 0.045, 0)
        guard.setLightOff(1)

        for side in (-1.0, 1.0):
            cap = self._make_box("guard-cap", Vec3(0.055, 0.060, 0.065), Vec4(0.93, 0.70, 0.12, 1))
            cap.reparentTo(root)
            cap.setPos(side * 0.315, 0.035, 0)
            cap.setHpr(0, 0, side * 18.0)
            cap.setLightOff(1)

        grip = self._make_box("grip", Vec3(0.068, 0.24, 0.068), Vec4(0.30, 0.12, 0.035, 1))
        grip.reparentTo(root)
        grip.setPos(0, -0.245, 0)
        grip.setLightOff(1)

        # Simple grip bands survive the glyph conversion better than tiny texture detail.
        for y in (-0.39, -0.29, -0.19, -0.09):
            band = self._make_box("grip-band", Vec3(0.079, 0.016, 0.079), Vec4(0.62, 0.39, 0.10, 1))
            band.reparentTo(root)
            band.setPos(0, y, 0)
            band.setLightOff(1)

        pommel = self._make_octahedron("pommel", 0.105, Vec4(0.86, 0.63, 0.10, 1))
        pommel.reparentTo(root)
        pommel.setPos(0, -0.525, 0)
        pommel.setScale(0.78, 1.0, 0.78)
        pommel.setLightOff(1)

        # Lower-right resting pose for the HAND pivot.  Pass 09 treats this
        # location as a hard visual anchor: attacks and guarding rotate the sword
        # around this grip point instead of translating the handle into the view.
        pivot.setPos(0.63, 0.86, -0.66)
        pivot.setHpr(-16, 5, -22)
        self.sword_root = pivot
        self.sword_model = root
        self.sword_rest_pos = Vec3(pivot.getPos())
        self.sword_rest_hpr = Vec3(pivot.getHpr())

        # PASS 10: the player's second hand carries a long casting staff.  Its
        # pivot is anchored on the lower-left and the shaft deliberately continues
        # below the camera frame so it reads as a full-length staff rather than a
        # short wand.  The top crystal is the exact origin of the R-key lightning.
        staff_pivot = self.scene_cam.attachNewNode("first-person-staff-hand-pivot")
        staff_root = staff_pivot.attachNewNode("first-person-staff-model")

        shaft = self._make_box("staff-shaft", Vec3(0.052, 0.052, 1.08), Vec4(0.31, 0.17, 0.055, 1))
        shaft.reparentTo(staff_root)
        shaft.setPos(0, 0, -0.82)
        shaft.setLightOff(1)

        # Broad bands remain readable after the glyph conversion and help show
        # that the staff is rotating slightly during a cast.
        for z in (-1.58, -1.08, -0.58, -0.10):
            band = self._make_box("staff-band", Vec3(0.071, 0.071, 0.030), Vec4(0.66, 0.45, 0.12, 1))
            band.reparentTo(staff_root)
            band.setPos(0, 0, z)
            band.setLightOff(1)

        crown = self._make_box("staff-crystal-crown", Vec3(0.18, 0.045, 0.045), Vec4(0.67, 0.39, 0.11, 1))
        crown.reparentTo(staff_root)
        crown.setPos(0, 0, 0.20)
        crown.setHpr(0, 0, 18)
        crown.setLightOff(1)

        crystal = self._make_octahedron("staff-lightning-crystal", 0.19, Vec4(0.88, 0.16, 1.0, 1))
        crystal.reparentTo(staff_root)
        crystal.setPos(0, 0.045, 0.38)
        crystal.setScale(0.88, 0.88, 1.42)
        crystal.setLightOff(1)

        crystal_core = self._make_octahedron("staff-lightning-crystal-core", 0.085, Vec4(1.0, 0.44, 1.0, 1))
        crystal_core.reparentTo(staff_root)
        crystal_core.setPos(0, 0.025, 0.39)
        crystal_core.setScale(0.78, 0.78, 1.35)
        crystal_core.setLightOff(1)

        staff_pivot.setPos(-0.72, 1.00, -0.36)
        staff_pivot.setHpr(4.0, -4.0, 7.0)
        self.staff_root = staff_pivot
        self.staff_model = staff_root
        self.staff_crystal = crystal
        self.staff_crystal_core = crystal_core
        self.staff_rest_pos = Vec3(staff_pivot.getPos())
        self.staff_rest_hpr = Vec3(staff_pivot.getHpr())

        # Three translucent after-images create a short readable cutting arc.
        # They live in camera space so they remain stable in both raw and glyph modes.
        self.slash_trails = []
        for i in range(3):
            trail = self._make_box(
                f"slash-trail-{i}",
                Vec3(0.12 + i * 0.025, 0.54 - i * 0.06, 0.010),
                Vec4(0.68, 0.90, 1.0, 0.58 - i * 0.12),
            )
            trail.reparentTo(self.scene_cam)
            trail.setLightOff(1)
            trail.setTransparency(TRANS_ALPHA)
            trail.setDepthWrite(False)
            trail.hide()
            self.slash_trails.append(trail)

        # Casting focus occupies the opposite hand-space so magic is visible in
        # first person and survives the semantic glyph conversion as MAGIC.
        self.cast_focus = self._make_octahedron("first-person-rune-focus", 0.19, Vec4(0.88, 0.08, 1.0, 0.92))
        self.cast_focus.reparentTo(self.scene_cam)
        self.cast_focus.setPos(-0.58, 1.02, -0.34)
        self.cast_focus.setScale(0.9, 0.9, 1.35)
        self.cast_focus.setLightOff(1)
        self.cast_focus.setTransparency(TRANS_ALPHA)
        self.cast_focus.hide()

    @staticmethod
    def _font_safe_text(text: str) -> str:
        """Keep Panda3D's bundled monospace HUD font on its defined ASCII range.

        The built-in cmtt12 font does not define several decorative Unicode symbols
        previously used by the HUD.  Mapping them here prevents TextNode from
        emitting repeated "no definition in font" warnings, and also protects new
        messages from accidentally reintroducing unsupported glyphs.
        """
        replacements = {
            "\u2013": "-", "\u2014": "-", "\u00d7": "x",
            "\u2665": "#", "\u2661": ".", "\u25c7": "<>",
            "\u25b6": ">", "\u00b7": ".", "\u2726": "*",
            "\u25c9": "O",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        return text.encode("ascii", "replace").decode("ascii")

    def _build_hud(self) -> None:
        try:
            self.mono_font = self.loader.loadFont("cmtt12.egg")
        except Exception:
            self.mono_font = None

        self.hearts_text = OnscreenText(parent=self.aspect2d, text="", pos=(-1.30, 0.92), scale=0.053, fg=(1.0, 0.18, 0.19, 1), align=TextNode.ALeft, mayChange=True, font=self.mono_font)
        self.stamina_text = OnscreenText(parent=self.aspect2d, text="", pos=(-1.30, 0.83), scale=0.032, fg=(0.32, 1.0, 0.25, 1), align=TextNode.ALeft, mayChange=True, font=self.mono_font)
        self.mana_text = OnscreenText(parent=self.aspect2d, text="", pos=(-1.30, 0.765), scale=0.030, fg=(0.80, 0.31, 1.0, 1), align=TextNode.ALeft, mayChange=True, font=self.mono_font)
        self.currency_text = OnscreenText(parent=self.aspect2d, text="", pos=(-1.30, 0.68), scale=0.040, fg=(1.0, 0.77, 0.12, 1), align=TextNode.ALeft, mayChange=True, font=self.mono_font)
        self.compass_text = OnscreenText(parent=self.aspect2d, text="", pos=(0, 0.94), scale=0.040, fg=(0.88, 0.90, 0.95, 1), align=TextNode.ACenter, mayChange=True, font=self.mono_font)
        self.weather_text = OnscreenText(parent=self.aspect2d, text="", pos=(0, 0.875), scale=0.027, fg=(0.66, 0.74, 0.88, 1), align=TextNode.ACenter, mayChange=True, font=self.mono_font)
        self.quest_text = OnscreenText(parent=self.aspect2d, text="", pos=(1.30, 0.92), scale=0.040, fg=(1.0, 0.80, 0.10, 1), align=TextNode.ARight, mayChange=True, font=self.mono_font)
        self.prompt_text = OnscreenText(parent=self.aspect2d, text="", pos=(0, -0.73), scale=0.045, fg=(0.96, 0.96, 1.0, 1), align=TextNode.ACenter, mayChange=True, font=self.mono_font)
        self.portal_status_text = OnscreenText(parent=self.aspect2d, text="", pos=(0, -0.54), scale=0.029, fg=(0.70, 0.88, 1.0, 1), align=TextNode.ACenter, mayChange=True, font=self.mono_font)
        self.message_text = OnscreenText(parent=self.aspect2d, text="", pos=(0, 0.62), scale=0.050, fg=(0.94, 0.77, 1.0, 1), align=TextNode.ACenter, mayChange=True, font=self.mono_font)
        self.crosshair_text = OnscreenText(parent=self.aspect2d, text="+", pos=(0, -0.018), scale=0.036, fg=(0.88, 0.92, 1.0, 0.82), align=TextNode.ACenter, font=self.mono_font)
        self.controls_text = OnscreenText(
            parent=self.aspect2d, text="WASD move   LMB sword   RMB guard   R staff   1/2/3 spell   F cast   E interact   Shift sprint   F6 beacon recovery   F1/F2 render",
            pos=(0, -0.95), scale=0.026, fg=(0.54, 0.62, 0.75, 1), align=TextNode.ACenter, font=self.mono_font,
        )
        self.dev_text = OnscreenText(parent=self.aspect2d, text="", pos=(1.30, -0.91), scale=0.025, fg=(0.43, 0.50, 0.65, 1), align=TextNode.ARight, mayChange=True, font=self.mono_font)
        self._update_hud()

    # ------------------------------------------------------------------
    # Replaceable audio
    # ------------------------------------------------------------------
    @staticmethod
    def _audio_filename(path: Path) -> Filename:
        """Translate a native absolute path to Panda3D filename syntax."""
        # resolve(strict=False) avoids cwd/model-path ambiguity while still letting
        # us validate existence ourselves before Panda3D's audio loader sees it.
        native = str(path.resolve(strict=False))
        return Filename.fromOsSpecific(native)

    def _audio_note_once(self, key: str, message: str) -> None:
        """Keep a bad replacement file from flooding the console every frame."""
        if key in self.audio_messages_seen:
            return
        self.audio_messages_seen.add(key)
        print(message)

    @staticmethod
    def _audio_header_ok(path: Path) -> tuple[bool, str]:
        """Cheap preflight for empty, mislabeled, and common metadata-only files.

        This intentionally does not try to decode the audio. Panda3D remains the
        decoder, but obviously unreadable replacements are rejected before they can
        trigger lower-level read errors in the audio backend.
        """
        try:
            size = path.stat().st_size
            if size < 32:
                return False, "file is empty or too small to contain playable audio"
            with path.open("rb") as handle:
                head = handle.read(16)
        except OSError as exc:
            return False, f"filesystem read failed: {exc}"

        ext = path.suffix.lower()
        if ext == ".wav":
            if len(head) < 12 or head[:4] not in (b"RIFF", b"RF64") or head[8:12] != b"WAVE":
                return False, "extension is .wav but the file has no RIFF/WAVE header"
        elif ext == ".ogg":
            if not head.startswith(b"OggS"):
                return False, "extension is .ogg but the file has no OggS header"
        elif ext == ".mp3":
            # MP3 commonly starts with an ID3 tag or an MPEG frame sync.  Leading
            # metadata formats vary, so only reject a clearly empty/zero header.
            if not (head.startswith(b"ID3") or (len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0)):
                if not any(head):
                    return False, "MP3 header is blank"
        return True, ""

    def _usable_audio_files(self, folder: Path) -> list[Path]:
        """Return replacement files that are safe enough to hand to Panda3D."""
        usable: list[Path] = []
        try:
            entries = sorted(folder.iterdir(), key=lambda item: item.name.lower())
        except OSError as exc:
            self._audio_note_once(
                f"scan:{folder}",
                f"[audio] Could not read folder {folder.name!r}; audio in it is disabled: {exc}",
            )
            return usable

        for path in entries:
            try:
                if not path.is_file() or path.suffix.lower() not in self.AUDIO_EXTENSIONS:
                    continue
            except OSError:
                continue
            ok, reason = self._audio_header_ok(path)
            if not ok:
                self._audio_note_once(
                    f"preflight:{path}",
                    f"[audio] Skipping unreadable replacement {path.name!r}: {reason}.",
                )
                continue
            usable.append(path)
        return usable

    def _load_sfx_file(self, path: Path):
        """Load one SFX once; failures never become recurring read attempts."""
        try:
            panda_path = self._audio_filename(path)
            sound = self.loader.loadSfx(panda_path)
            if not sound:
                raise IOError("Panda3D returned no sound object")
            sound.setVolume(self.sfx_volume)
            return sound
        except Exception as exc:
            self._audio_note_once(
                f"sfx:{path}",
                f"[audio] Skipping SFX {path.name!r}; Panda3D could not read it: {exc}",
            )
            return None

    def _setup_audio(self) -> None:
        """Scan replaceable audio safely; audio can never block game startup."""
        sfx_dir = ROOT / "assets" / "sfx"
        music_dir = ROOT / "assets" / "music"
        try:
            sfx_dir.mkdir(parents=True, exist_ok=True)
            music_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._audio_note_once("mkdir", f"[audio] Replacement folders are unavailable: {exc}")
            return

        try:
            sfx_files = self._usable_audio_files(sfx_dir)
            for event in self.SFX_EVENTS:
                sounds = []
                for path in sfx_files:
                    stem = path.stem.lower()
                    if not (
                        stem == event
                        or stem.startswith(event + "_")
                        or stem.startswith(event + "-")
                        or stem.startswith(event + " ")
                    ):
                        continue
                    sound = self._load_sfx_file(path)
                    if sound is not None:
                        sounds.append(sound)
                if sounds:
                    self.sfx_library[event] = sounds

            self.music_files = self._usable_audio_files(music_dir)
            self.music_failed.clear()
            self.music_retry_exhausted = False
            self.music_index = -1
            if self.music_files:
                self.audio_random.shuffle(self.music_files)
                self._start_next_music()
        except Exception as exc:
            # Audio must never prevent the prototype from launching.
            self._audio_note_once("setup", f"[audio] Audio setup disabled: {exc}")
            self.sfx_library = {}
            self.music_files = []
            self.music_current = None
            self.music_current_path = None
            self.music_retry_exhausted = True

    def _play_sfx(self, *events: str, volume: float | None = None) -> None:
        """Play the first event prefix that has one or more replacement files."""
        for event in events:
            sounds = self.sfx_library.get(event)
            if not sounds:
                continue
            sound = self.audio_random.choice(sounds)
            try:
                sound.setVolume(self.sfx_volume if volume is None else volume)
                sound.play()
            except Exception as exc:
                self._audio_note_once(
                    f"sfx-play:{event}:{id(sound)}",
                    f"[audio] SFX playback failed ({event}); this replacement is being ignored: {exc}",
                )
                try:
                    sounds.remove(sound)
                except ValueError:
                    pass
            return

    def _mark_music_failed(self, path: Path | None, reason: object) -> None:
        if path is None:
            return
        self.music_failed.add(path)
        self._audio_note_once(
            f"music:{path}",
            f"[audio] Skipping music {path.name!r}; Panda3D could not read/play it: {reason}",
        )

    def _start_next_music(self) -> None:
        if self.music_retry_exhausted or not self.music_files:
            self.music_current = None
            self.music_current_path = None
            return
        if self.music_current is not None:
            try:
                self.music_current.stop()
            except Exception:
                pass
        self.music_current = None
        self.music_current_path = None

        # Try each still-healthy file once. A failed track is quarantined for this
        # run so the update loop never hammers the same unreadable file every 0.5 s.
        candidates = [path for path in self.music_files if path not in self.music_failed]
        if not candidates:
            self.music_retry_exhausted = True
            self._audio_note_once(
                "music-exhausted",
                "[audio] No readable music remains. Continuing silently without retry spam.",
            )
            return

        attempts = 0
        max_attempts = len(self.music_files)
        while attempts < max_attempts:
            self.music_index = (self.music_index + 1) % len(self.music_files)
            path = self.music_files[self.music_index]
            attempts += 1
            if path in self.music_failed:
                continue
            try:
                panda_path = self._audio_filename(path)
                music = self.loader.loadMusic(panda_path)
                if not music:
                    raise IOError("Panda3D returned no music object")
                music.setVolume(self.music_volume)
                # Only a truly usable lone track loops forever.
                usable_count = sum(1 for item in self.music_files if item not in self.music_failed)
                music.setLoop(usable_count == 1)
                music.play()
                self.music_current = music
                self.music_current_path = path
                self.music_check_timer = 0.75
                return
            except Exception as exc:
                self._mark_music_failed(path, exc)

        if not any(path not in self.music_failed for path in self.music_files):
            self.music_retry_exhausted = True
            self._audio_note_once(
                "music-exhausted",
                "[audio] No readable music remains. Continuing silently without retry spam.",
            )

    def _update_audio(self, dt: float) -> None:
        if self.music_retry_exhausted or not self.music_files:
            return
        self.music_check_timer -= dt
        if self.music_check_timer > 0.0:
            return
        self.music_check_timer = 0.50
        if self.music_current is None:
            self._start_next_music()
            return

        usable_count = sum(1 for item in self.music_files if item not in self.music_failed)
        if usable_count <= 1:
            return
        try:
            playing_value = getattr(self.music_current, "PLAYING", 2)
            if self.music_current.status() != playing_value:
                self._start_next_music()
        except Exception as exc:
            failed_path = self.music_current_path
            self._mark_music_failed(failed_path, f"status check failed: {exc}")
            self.music_current = None
            self.music_current_path = None
            self._start_next_music()

    def _run_portal_handoff_test(self, task):
        self._begin_central_hub_return()
        return task.done

    def _capture_test_shot(self, task):
        if self.test_shot_path is None:
            return task.done
        try:
            self.test_shot_path.parent.mkdir(parents=True, exist_ok=True)
            filename = Filename.fromOsSpecific(str(self.test_shot_path))
            ok = self.win.saveScreenshot(filename)
            print(f"[TEST] screenshot {'saved' if ok else 'failed'}: {self.test_shot_path}")
        except Exception as exc:
            print(f"[TEST] screenshot failed: {exc}")
        self.userExit()
        return task.done

    # ------------------------------------------------------------------
    # Controls / movement
    # ------------------------------------------------------------------
    def _bind_controls(self) -> None:
        bindings = (
            ("w", "w"), ("a", "a"), ("s", "s"), ("d", "d"),
            ("arrow_up", "up"), ("arrow_down", "down"), ("arrow_left", "left"), ("arrow_right", "right"),
        )
        for event, key in bindings:
            self.accept(event, self._set_key, [key, True])
            self.accept(f"{event}-up", self._set_key, [key, False])
        self.accept("shift", self._set_key, ["shift", True])
        self.accept("shift-up", self._set_key, ["shift", False])
        self.accept("mouse3", self._set_key, ["block", True])
        self.accept("mouse3-up", self._set_key, ["block", False])
        self.accept("mouse1", self._sword_attack)
        self.accept("r", self._cast_staff_lightning)
        self.accept("1", self._select_spell, [0])
        self.accept("2", self._select_spell, [1])
        self.accept("3", self._select_spell, [2])
        self.accept("f", self._cast_magic)
        self.accept("e", self._interact)
        self.accept("escape", self._toggle_mouse)
        self.accept("f1", self._toggle_raw)
        self.accept("f2", self._cycle_style)
        self.accept("f6", self._reset_world_to_portal)
        self.accept("f7", self._cycle_weather_debug)
        self.accept("f8", self._advance_time_debug)
        self.accept("[", self._change_grid, [-1])
        self.accept("]", self._change_grid, [1])
        # Q is deliberately left unbound.  Previous passes used Q as an
        # immediate quit key, which made an ordinary key press terminate the
        # game and was reported as a crash.  Closing the window remains the
        # normal OS/Panda3D exit path.

    def _set_key(self, key: str, down: bool) -> None:
        if key in self.keys:
            self.keys[key] = down

    def _capture_mouse(self) -> None:
        self.mouse_locked = True
        props = WindowProperties()
        props.setCursorHidden(True)
        props.setMouseMode(MOUSE_ABSOLUTE)
        self.win.requestProperties(props)
        self._center_pointer()

    def _release_mouse(self) -> None:
        self.mouse_locked = False
        props = WindowProperties()
        props.setCursorHidden(False)
        props.setMouseMode(MOUSE_ABSOLUTE)
        self.win.requestProperties(props)

    def _toggle_mouse(self) -> None:
        if self.mouse_locked:
            self._release_mouse()
        else:
            self._capture_mouse()

    def _center_pointer(self) -> None:
        cx = max(1, self.win.getXSize() // 2)
        cy = max(1, self.win.getYSize() // 2)
        self.win.movePointer(0, cx, cy)

    def _toggle_raw(self) -> None:
        self.raw_mode = not self.raw_mode
        self.present_card.setShaderInput("ascii_enabled", 0.0 if self.raw_mode else 1.0)
        self._show_message("RAW 3D VIEW" if self.raw_mode else "GLYPH WORLD VIEW", 1.2)

    def _cycle_style(self) -> None:
        self.style_mode = (self.style_mode + 1) % len(self.STYLE_NAMES)
        self.present_card.setShaderInput("style_mode", float(self.style_mode))
        self._show_message(f"STYLE: {self.STYLE_NAMES[self.style_mode]}", 1.4)

    def _change_grid(self, direction: int) -> None:
        self.grid_index = max(0, min(len(self.GRID_PRESETS) - 1, self.grid_index + direction))
        self._apply_grid_size()
        cols, rows = self.GRID_PRESETS[self.grid_index]
        self._show_message(f"GLYPH GRID {cols} x {rows}", 1.2)

    def _is_blocked(self, x: float, y: float) -> bool:
        for ox, oy, radius in self.obstacles:
            if (x - ox) * (x - ox) + (y - oy) * (y - oy) < (radius + 0.34) ** 2:
                return True
        for chunk_obstacles in self.proc_obstacles.values():
            for ox, oy, radius in chunk_obstacles:
                if (x - ox) * (x - ox) + (y - oy) * (y - oy) < (radius + 0.34) ** 2:
                    return True
        if not self.shrine_unlocked:
            # Physical seal across the temple entrance.
            if abs(x - self.SHRINE_POS.x) < 2.55 and self.SHRINE_POS.y - 2.0 < y < self.SHRINE_POS.y + 0.1:
                return True
        return False

    def _move_player(self, dt: float) -> None:
        rad = math.radians(self.heading)
        forward = Vec3(-math.sin(rad), math.cos(rad), 0)
        right = Vec3(math.cos(rad), math.sin(rad), 0)
        move = Vec3(0)
        if self.keys["w"]:
            move += forward
        if self.keys["s"]:
            move -= forward
        if self.keys["d"]:
            move += right
        if self.keys["a"]:
            move -= right
        if move.lengthSquared() > 0:
            move.normalize()

        ground_here = self._height(self.player_pos.x, self.player_pos.y)
        water_here = self._water_surface_at(self.player_pos.x, self.player_pos.y)
        self.in_water = water_here is not None and ground_here < water_here - 0.24

        sprinting = self.keys["shift"] and self.stamina > 1.0 and not self.in_water and not self.keys["block"] and move.lengthSquared() > 0
        speed = self.settings.move_speed
        if sprinting:
            speed *= self.settings.sprint_multiplier
            self.stamina = max(0.0, self.stamina - 20.0 * dt)
        elif self.in_water:
            speed *= self.settings.swim_multiplier
            if move.lengthSquared() > 0:
                self.stamina = max(0.0, self.stamina - 8.5 * dt)
        elif self.keys["block"]:
            speed *= 0.70
            self.stamina = min(self.settings.max_stamina, self.stamina + 5.0 * dt)
        else:
            self.stamina = min(self.settings.max_stamina, self.stamina + 17.0 * dt)

        if self.in_water and self.stamina <= 0.05:
            self._hurt_player(1, "You were pulled under the glyph-water.")
            self.player_pos = Vec3(self.last_safe_pos)
            self.stamina = 55.0
            return

        self.velocity = move * speed
        delta = self.velocity * dt

        nx = self.player_pos.x + delta.x
        if not self._is_blocked(nx, self.player_pos.y):
            self.player_pos.x = nx
        ny = self.player_pos.y + delta.y
        if not self._is_blocked(self.player_pos.x, ny):
            self.player_pos.y = ny

        new_ground = self._height(self.player_pos.x, self.player_pos.y)
        new_water = self._water_surface_at(self.player_pos.x, self.player_pos.y)
        now_in_water = new_water is not None and new_ground < new_water - 0.24
        if not now_in_water:
            self.last_safe_pos = Vec3(self.player_pos)

        if self.velocity.lengthSquared() > 0.05:
            self.bob_phase += dt * (11.5 if sprinting else 7.4)

    def _sync_camera(self) -> None:
        ground = self._height(self.player_pos.x, self.player_pos.y)
        water = self._water_surface_at(self.player_pos.x, self.player_pos.y)
        swimming = water is not None and ground < water - 0.24
        base_z = (water - 0.52) if swimming and water is not None else ground
        bob = math.sin(self.bob_phase) * 0.035 if self.velocity.lengthSquared() > 0.05 else 0.0
        eye = Vec3(self.player_pos.x, self.player_pos.y, base_z + self.settings.eye_height + bob)
        self.scene_cam.setPos(eye)
        self.scene_cam.setHpr(self.heading, self.pitch, 0)

    # ------------------------------------------------------------------
    # Combat / interaction
    # ------------------------------------------------------------------
    def _select_spell(self, index: int) -> None:
        self.selected_spell = max(0, min(len(self.spell_names) - 1, index))
        self._show_message(f"SPELL: {self.spell_names[self.selected_spell]}", 0.75)

    def _view_direction(self) -> Vec3:
        h = math.radians(self.heading)
        p = math.radians(self.pitch)
        cp = math.cos(p)
        direction = Vec3(-math.sin(h) * cp, math.cos(h) * cp, math.sin(p))
        if direction.lengthSquared() > 0.0001:
            direction.normalize()
        return direction

    @staticmethod
    def _enemy_name(enemy: Enemy) -> str:
        return {"beast": "GLYPH BEAST", "imp": "RIFT IMP", "brute": "HORNED BRUTE", "hexer": "HEXER", "pyre": "PYRE HURLER", "wolf": "RUNE WOLF", "scorpion": "SUN SCORPION", "wraith": "MIST WRAITH", "golem": "CANYON GOLEM", "frostling": "FROSTLING", "bogling": "MARSH BOGGLING", "ashfiend": "ASH FIEND", "dragon": "SKY DRAGON"}.get(enemy.kind, "WILDLING")

    def _damage_enemy(self, enemy: Enemy, damage: int, origin: Vec3, force: float, source: str) -> bool:
        if not enemy.alive:
            return False
        enemy.hp -= damage
        enemy.hit_flash = 0.18
        enemy.attack_windup = 0.0
        enemy.attack_cooldown = max(enemy.attack_cooldown, 0.42)
        away = Vec2(enemy.node.getX(self.render) - origin.x, enemy.node.getY(self.render) - origin.y)
        if away.lengthSquared() > 0.001:
            away.normalize()
            enemy.knockback_x = away.x * force
            enemy.knockback_y = away.y * force
        enemy.stagger_timer = 0.34 if enemy.hp > 0 else 0.0
        pos = enemy.node.getPos(self.render) + Vec3(0, 0, 0.55)
        self._spawn_hit_sparks(pos, heavy=enemy.hp <= 0)
        if source != "SWORD":
            self._play_sfx("enemy_hit")
        if enemy.hp <= 0:
            self._play_sfx("enemy_die")
            enemy.alive = False
            enemy.node.hide()
            if enemy.spawn_key is not None:
                self.defeated_stream_spawns.add(enemy.spawn_key)
            self.currency += enemy.reward
            # Demons leave behind a little mana so magic remains usable during a fight.
            if enemy.kind != "beast":
                self.mana = min(self.settings.max_mana, self.mana + 10.0)
            self._show_message(f"{self._enemy_name(enemy)} DISPERSED  +{enemy.reward}", 1.0)
            return True
        self._show_message(f"{source}  {enemy.hp}/{enemy.max_hp}", 0.50)
        return False

    def _spawn_magic_projectile(self, origin: Vec3, direction: Vec3, speed: float, damage: int, radius: float, friendly: bool, spell: str) -> None:
        if spell == "DEMON FIREBALL":
            # Layered red/orange geometry gives the hostile projectile a hot core and
            # ragged silhouette without requiring a texture asset.
            orb = self.render.attachNewNode("demon-fireball")
            shell = self._make_octahedron("fireball-shell", 0.46, Vec4(0.96, 0.055, 0.008, 1))
            shell.reparentTo(orb)
            shell.setScale(1.0, 0.90, 1.18)
            shell.setLightOff(1)
            core = self._make_octahedron("fireball-core", 0.25, Vec4(1.0, 0.55, 0.025, 1))
            core.reparentTo(orb)
            core.setScale(0.82, 0.82, 1.05)
            core.setLightOff(1)
            for j in range(3):
                lick = self._make_octahedron(f"fireball-lick-{j}", 0.16, Vec4(1.0, 0.20 + 0.10 * j, 0.01, 1))
                lick.reparentTo(orb)
                lick.setPos((j - 1) * 0.18, -0.34, 0.10 + 0.10 * j)
                lick.setScale(0.62, 1.35, 1.45)
                lick.setLightOff(1)
            life = 4.2
        else:
            color = Vec4(0.82, 0.07, 1.0, 1) if spell != "EMBER ORB" else Vec4(0.98, 0.11, 0.70, 1)
            if not friendly:
                color = Vec4(0.60, 0.035, 0.92, 1)
            orb = self._make_octahedron(f"magic-{spell.lower().replace(' ', '-')}", 0.24 if radius < 2.0 else 0.38, color)
            orb.setScale(1.0, 1.0, 1.35)
            orb.setLightOff(1)
            life = 3.2
        orb.reparentTo(self.render)
        orb.setPos(origin)
        self.magic_projectiles.append(MagicProjectile(orb, direction * speed, life, damage, radius, friendly, spell))

    def _spawn_magic_burst_fx(self, origin: Vec3, radius: float = 1.0) -> None:
        count = 12 if radius > 2.0 else 7
        for i in range(count):
            ang = i * math.tau / count + self.random.uniform(-0.12, 0.12)
            spark = self._make_octahedron("rune-spark", 0.10 if radius <= 2.0 else 0.15, Vec4(0.91, 0.10, 1.0, 0.92))
            spark.reparentTo(self.render)
            spark.setPos(origin + Vec3(0, 0, 0.22))
            spark.setLightOff(1)
            spark.setTransparency(TRANS_ALPHA)
            speed = self.random.uniform(2.6, 5.0) * (1.3 if radius > 2.0 else 1.0)
            vel = Vec3(math.cos(ang) * speed, math.sin(ang) * speed, self.random.uniform(0.7, 3.8))
            life = self.random.uniform(0.28, 0.46)
            self.combat_fx.append(CombatFx(spark, vel, life, life))

    def _spawn_fire_burst_fx(self, origin: Vec3, radius: float = 1.0) -> None:
        count = 16 if radius > 1.5 else 10
        for i in range(count):
            ang = i * math.tau / count + self.random.uniform(-0.18, 0.18)
            hot = (i % 3) == 0
            color = Vec4(1.0, 0.55, 0.02, 0.96) if hot else Vec4(0.98, 0.10, 0.01, 0.94)
            spark = self._make_octahedron("fire-spark", 0.11 if not hot else 0.14, color)
            spark.reparentTo(self.render)
            spark.setPos(origin + Vec3(0, 0, 0.18))
            spark.setLightOff(1)
            spark.setTransparency(TRANS_ALPHA)
            speed = self.random.uniform(3.4, 6.4) * (1.20 if radius > 1.5 else 1.0)
            vel = Vec3(math.cos(ang) * speed, math.sin(ang) * speed, self.random.uniform(1.2, 5.0))
            life = self.random.uniform(0.28, 0.52)
            self.combat_fx.append(CombatFx(spark, vel, life, life))

    def _cast_magic(self) -> None:
        if self.magic_cooldown > 0.0 or self.sword_timer > 0.0:
            return
        spell = self.spell_names[self.selected_spell]
        costs = (12.0, 28.0, 24.0)
        cost = costs[self.selected_spell]
        if self.mana < cost:
            self._show_message("NOT ENOUGH MANA", 0.8)
            return
        self.mana -= cost
        self.cast_flash_timer = 0.34
        self.mana_regen_delay = 1.45
        self.magic_cooldown = (0.28, 0.72, 0.55)[self.selected_spell]
        if self.selected_spell == 0:
            self._play_sfx("cast_arc")
        elif self.selected_spell == 1:
            self._play_sfx("cast_ember")
        else:
            self._play_sfx("cast_ward")
        direction = self._view_direction()
        eye = self.scene_cam.getPos(self.render)
        origin = eye + direction * 0.75 + Vec3(0, 0, -0.18)

        if self.selected_spell == 0:
            self._spawn_magic_projectile(origin, direction, 26.0, 2, 0.85, True, "ARC BOLT")
            self._spawn_magic_burst_fx(origin, 0.8)
        elif self.selected_spell == 1:
            self._spawn_magic_projectile(origin, direction, 13.5, 2, 4.6, True, "EMBER ORB")
            self._spawn_magic_burst_fx(origin, 1.2)
        else:
            self.magic_ward_timer = 8.0
            self.magic_ward_charges = 1
            self._spawn_magic_burst_fx(Vec3(self.player_pos.x, self.player_pos.y, self._height(self.player_pos.x, self.player_pos.y) + 1.0), 3.2)
            self._show_message("WARD RUNE - ONE HIT WILL BE ABSORBED", 1.5)

    def _staff_targets(self) -> list[Enemy]:
        """Pick one aimed target, then let the arc fork into nearby enemies."""
        eye = self.scene_cam.getPos(self.render)
        view = self._view_direction()
        candidates: list[tuple[float, float, Enemy]] = []
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            target = enemy.node.getPos(self.render) + Vec3(0, 0, 0.62)
            delta = target - eye
            dist = delta.length()
            if dist <= 0.05 or dist > 24.0:
                continue
            delta.normalize()
            alignment = view.dot(delta)
            if alignment < 0.90:
                continue
            candidates.append((alignment, -dist, enemy))

        if not candidates:
            return []
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        primary = candidates[0][2]
        chosen = [primary]

        # Up to two secondary targets can be caught by branches near the primary.
        while len(chosen) < 3:
            best: tuple[float, Enemy] | None = None
            for enemy in self.enemies:
                if not enemy.alive or any(enemy is selected for selected in chosen):
                    continue
                ep = enemy.node.getPos(self.render)
                nearest = min((ep - c.node.getPos(self.render)).length() for c in chosen)
                if nearest > 5.7:
                    continue
                if best is None or nearest < best[0]:
                    best = (nearest, enemy)
            if best is None:
                break
            chosen.append(best[1])
        return chosen

    def _make_lightning_geometry(self, name: str, start: Vec3, end: Vec3, fork_count: int = 3) -> NodePath:
        """Create a two-layer jagged bolt in camera space with visible side forks."""
        delta = end - start
        distance = max(0.2, delta.length())
        segments = max(7, min(14, int(distance * 0.85)))
        jitter = min(0.34, 0.075 + distance * 0.017)
        points: list[Vec3] = []
        for i in range(segments + 1):
            u = i / float(segments)
            p = start + delta * u
            envelope = math.sin(math.pi * u)
            if 0 < i < segments:
                p += Vec3(
                    self.random.uniform(-jitter, jitter) * envelope,
                    self.random.uniform(-jitter * 0.14, jitter * 0.14) * envelope,
                    self.random.uniform(-jitter, jitter) * envelope,
                )
            points.append(Vec3(p))

        group = self.scene_cam.attachNewNode(name)
        group.setLightOff(1)
        group.setTransparency(TRANS_ALPHA)
        group.setDepthWrite(False)
        group.setDepthTest(False)

        # A thick saturated purple shell keeps the bolt in the MAGIC glyph row.
        outer = LineSegs(name + "-outer")
        outer.setThickness(7.0)
        outer.setColor(0.78, 0.10, 1.0, 0.95)
        outer.moveTo(points[0])
        for p in points[1:]:
            outer.drawTo(p)
        outer_np = group.attachNewNode(outer.create(False))
        outer_np.setLightOff(1)

        # Bright inner filament, still purple-biased enough to remain magic.
        inner = LineSegs(name + "-inner")
        inner.setThickness(2.5)
        inner.setColor(1.0, 0.28, 1.0, 1.0)
        inner.moveTo(points[0])
        for p in points[1:]:
            inner.drawTo(p)
        inner_np = group.attachNewNode(inner.create(False))
        inner_np.setLightOff(1)

        # Forks split from several points on the main discharge.  They are short
        # enough to look like electrical branches rather than extra projectiles.
        forks = LineSegs(name + "-forks")
        forks.setThickness(3.4)
        forks.setColor(0.86, 0.12, 1.0, 0.88)
        for f in range(fork_count):
            idx = max(1, min(segments - 2, int((f + 2) * segments / (fork_count + 3))))
            branch_start = points[idx]
            direction_sign = -1.0 if f % 2 == 0 else 1.0
            branch_len = 0.32 + distance * self.random.uniform(0.025, 0.055)
            mid = branch_start + Vec3(
                direction_sign * branch_len * 0.55,
                branch_len * 0.55,
                self.random.uniform(-0.34, 0.34),
            )
            finish = mid + Vec3(
                direction_sign * branch_len * 0.65,
                branch_len * 0.52,
                self.random.uniform(-0.38, 0.38),
            )
            forks.moveTo(branch_start)
            forks.drawTo(mid)
            forks.drawTo(finish)
        fork_np = group.attachNewNode(forks.create(False))
        fork_np.setLightOff(1)
        return group

    def _spawn_staff_lightning_fx(self, targets: list[Enemy]) -> None:
        start = Vec3(self.staff_crystal.getPos(self.scene_cam))
        endpoints: list[Vec3] = []
        if targets:
            for enemy in targets:
                target_world = enemy.node.getPos(self.render) + Vec3(0, 0, 0.72)
                endpoints.append(Vec3(self.scene_cam.getRelativePoint(self.render, target_world)))
        else:
            endpoints.append(Vec3(0.02, 15.0, -0.02))

        # Every selected target receives its own fork from the crystal.  The first
        # discharge is strongest; chained branches are a little thinner/shorter-lived.
        for i, endpoint in enumerate(endpoints):
            node = self._make_lightning_geometry(
                f"staff-lightning-{i}", start, endpoint, 4 if i == 0 else 2
            )
            duration = 0.15 if i == 0 else 0.12
            node.setColorScale(1.0, 1.0, 1.0, 1.0 if i == 0 else 0.82)
            self.lightning_fx.append(LightningFx(node, duration, duration))

    def _cast_staff_lightning(self) -> None:
        if self.staff_cooldown > 0.0 or self.keys["block"]:
            return
        if self.mana < self.staff_arc_cost:
            self._show_message(f"NOT ENOUGH MANA - STAFF ARC {int(self.staff_arc_cost)}", 0.9)
            return

        self.mana -= self.staff_arc_cost
        self.mana_regen_delay = 0.90
        self.staff_cooldown = 0.58
        self.staff_cast_timer = self.staff_cast_duration
        targets = self._staff_targets()
        self._spawn_staff_lightning_fx(targets)
        self._play_sfx("staff_electric", "cast_arc")

        origin = Vec3(self.player_pos.x, self.player_pos.y, self._height(self.player_pos.x, self.player_pos.y) + 1.0)
        for index, enemy in enumerate(targets):
            damage = 2 if index == 0 else 1
            force = 5.3 if index == 0 else 3.7
            hit_pos = enemy.node.getPos(self.render) + Vec3(0, 0, 0.55)
            self._spawn_magic_burst_fx(hit_pos, 0.72)
            self._damage_enemy(enemy, damage, origin, force, "STAFF ARC")

        if targets:
            self._show_message(f"STAFF ARC  x{len(targets)}", 0.55)

    def _sword_attack(self) -> None:
        if self.sword_cooldown > 0.0 or self.keys["block"]:
            return
        self.sword_timer = self.sword_attack_duration
        self.sword_cooldown = 0.53
        self.sword_hit_done = False
        self.sword_attack_start_pos = Vec3(self.sword_root.getPos())
        self.sword_attack_start_hpr = Vec3(self.sword_root.getHpr())
        self._play_sfx("sword_swing")

    def _spawn_hit_sparks(self, origin: Vec3, heavy: bool = False) -> None:
        count = 8 if heavy else 5
        for i in range(count):
            spark = self._make_octahedron(
                "combat-spark",
                0.13 if heavy else 0.095,
                Vec4(0.96, 0.36 + self.random.random() * 0.42, 0.10, 0.92),
            )
            spark.reparentTo(self.render)
            spark.setPos(origin + Vec3(
                self.random.uniform(-0.22, 0.22),
                self.random.uniform(-0.22, 0.22),
                self.random.uniform(-0.12, 0.28),
            ))
            spark.setLightOff(1)
            spark.setTransparency(TRANS_ALPHA)
            spread = 4.6 if heavy else 3.4
            velocity = Vec3(
                self.random.uniform(-spread, spread),
                self.random.uniform(-spread, spread),
                self.random.uniform(1.8, 5.6 if heavy else 4.2),
            )
            duration = self.random.uniform(0.20, 0.34)
            self.combat_fx.append(CombatFx(spark, velocity, duration, duration))

    def _resolve_sword_hit(self) -> None:
        """Apply damage at the visual contact point and give the target real reaction."""
        if self.sword_hit_done:
            return
        self.sword_hit_done = True

        rad = math.radians(self.heading)
        forward = Vec2(-math.sin(rad), math.cos(rad))
        best: tuple[float, Enemy] | None = None
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            ep = enemy.node.getPos(self.render)
            to = Vec2(ep.x - self.player_pos.x, ep.y - self.player_pos.y)
            dist = to.length()
            if dist <= 0.01 or dist > 3.55:
                continue
            to.normalize()
            if forward.dot(to) < 0.48:
                continue
            if best is None or dist < best[0]:
                best = (dist, enemy)

        if best:
            enemy = best[1]
            self.sword_impact_kick = 0.075
            self._play_sfx("sword_hit", "enemy_hit")
            self._damage_enemy(enemy, 1, Vec3(self.player_pos.x, self.player_pos.y, 0), 5.4, "SWORD")

    def _interact(self) -> None:
        utopia_dist = math.hypot(self.player_pos.x - self.utopia_portal_pos.x, self.player_pos.y - self.utopia_portal_pos.y)
        if utopia_dist < 6.2:
            self._begin_central_hub_return()
            return

        dist_entrance = math.hypot(self.player_pos.x - self.shrine_entrance.x, self.player_pos.y - self.shrine_entrance.y)
        if dist_entrance < 5.0 and not self.shrine_unlocked:
            if self.sigils < 3:
                self._show_message(f"THE SEAL REQUIRES {3 - self.sigils} MORE SIGIL(S)", 2.0)
            else:
                self.shrine_unlocked = True
                self._play_sfx("shrine_unlock")
                self.shrine_door.hide()
                self.portal.show()
                self._show_message("THE SHATTERED SHRINE AWAKENS", 2.4)
            return

        dist_portal = math.hypot(self.player_pos.x - self.shrine_portal_pos.x, self.player_pos.y - self.shrine_portal_pos.y)
        if self.shrine_unlocked and not self.prototype_complete and dist_portal < 4.0:
            self.prototype_complete = True
            self._play_sfx("shrine_enter")
            self._show_message("SHRINE ENTERED - THE GLYPH WORLD REMAINS OPEN", 4.0)

    def _hurt_player(self, amount: int, reason: str = "") -> bool:
        if self.damage_flash > 0.0:
            return False
        if self.magic_ward_timer > 0.0 and self.magic_ward_charges > 0:
            self.magic_ward_charges -= 1
            self.magic_ward_timer = 0.0
            self.damage_flash = 0.18
            self._play_sfx("ward_break", "guard")
            self._spawn_magic_burst_fx(Vec3(self.player_pos.x, self.player_pos.y, self._height(self.player_pos.x, self.player_pos.y) + 1.0), 3.0)
            self._show_message("WARD RUNE SHATTERED - DAMAGE ABSORBED", 0.95)
            return False
        if self.keys["block"] and self.stamina >= 14.0:
            self.stamina -= 14.0
            self.damage_flash = 0.25
            self._play_sfx("guard")
            self.sword_impact_kick = max(self.sword_impact_kick, 0.055)
            self._show_message("GUARDED", 0.65)
            return False
        self.health = max(0, self.health - amount)
        self.damage_flash = 0.85
        self._play_sfx("hurt")
        if reason:
            self._show_message(reason, 1.4)
        if self.health <= 0:
            self._play_sfx("death")
            self._return_to_utopia_beacon("SIMULATION RECONSTRUCTION")
        return True

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------
    def _update_mouse_look(self, dt: float) -> None:
        if self.software_test:
            return
        if self.mouse_locked:
            cx = max(1, self.win.getXSize() // 2)
            cy = max(1, self.win.getYSize() // 2)
            pointer = self.win.getPointer(0)
            dx = pointer.getX() - cx
            dy = pointer.getY() - cy
            if abs(dx) < self.win.getXSize() and abs(dy) < self.win.getYSize():
                self.heading -= dx * self.settings.mouse_sensitivity
                self.pitch = max(-82.0, min(82.0, self.pitch - dy * self.settings.mouse_sensitivity))
            self.win.movePointer(0, cx, cy)

        turn = 72.0 * dt
        if self.keys["left"]:
            self.heading += turn
        if self.keys["right"]:
            self.heading -= turn
        if self.keys["up"]:
            self.pitch = min(82.0, self.pitch + turn)
        if self.keys["down"]:
            self.pitch = max(-82.0, self.pitch - turn)

    def _spawn_enemy_hex_bolt(self, enemy: Enemy, origin: Vec3) -> None:
        eye = self.scene_cam.getPos(self.render)
        direction = eye - origin
        if direction.lengthSquared() > 0.0001:
            direction.normalize()
        self._play_sfx("demon_cast")
        self._spawn_magic_projectile(origin, direction, enemy.projectile_speed, enemy.damage, 0.82, False, "HEX BOLT")
        self._spawn_magic_burst_fx(origin, 0.7)

    def _spawn_enemy_fireball(self, enemy: Enemy, origin: Vec3) -> None:
        # Aim slightly below the player's eye so a sidestep can cleanly dodge it.
        target = self.scene_cam.getPos(self.render) - Vec3(0, 0, 0.18)
        direction = target - origin
        if direction.lengthSquared() > 0.0001:
            direction.normalize()
        self._play_sfx("demon_fireball", "demon_cast")
        self._spawn_magic_projectile(origin, direction, enemy.projectile_speed, enemy.damage, 1.35, False, "DEMON FIREBALL")
        self._spawn_fire_burst_fx(origin, 0.70)

    def _update_enemies(self, dt: float, t: float) -> None:
        for enemy in self.enemies:
            if not enemy.alive:
                continue

            enemy.attack_cooldown = max(0.0, enemy.attack_cooldown - dt)
            enemy.hit_flash = max(0.0, enemy.hit_flash - dt)
            p = enemy.node.getPos(self.render)
            to_player = Vec2(self.player_pos.x - p.x, self.player_pos.y - p.y)
            dist = to_player.length()
            sanctuary_hold = self._in_utopia_sanctuary(self.player_pos.x, self.player_pos.y, 1.5)

            # Streamed enemies well outside combat/readability range do not need
            # terrain sampling, pathing, bobbing, wing animation, or model searches
            # every frame. They wake instantly as the player approaches.
            far_limit = 96.0 if enemy.kind == "dragon" else 72.0
            if (
                dist > far_limit
                and enemy.stagger_timer <= 0.0
                and enemy.attack_windup <= 0.0
                and enemy.hit_flash <= 0.0
            ):
                continue

            if enemy.stagger_timer > 0.0:
                enemy.stagger_timer = max(0.0, enemy.stagger_timer - dt)
                nx = p.x + enemy.knockback_x * dt
                ny = p.y + enemy.knockback_y * dt
                if not self._is_blocked(nx, p.y):
                    p.x = nx
                if not self._is_blocked(p.x, ny):
                    p.y = ny
                decay = math.exp(-dt * 8.0)
                enemy.knockback_x *= decay
                enemy.knockback_y *= decay
                enemy.attack_windup = 0.0
            elif sanctuary_hold:
                # The Utopia return pad is a true sanctuary.  Hostiles disengage
                # instead of camping the respawn/portal connection.
                enemy.attack_windup = 0.0
                to_home = Vec2(enemy.home.x - p.x, enemy.home.y - p.y)
                if to_home.length() > 0.8:
                    to_home.normalize()
                    nx = p.x + to_home.x * enemy.speed * 0.72 * dt
                    ny = p.y + to_home.y * enemy.speed * 0.72 * dt
                    if not self._is_blocked(nx, p.y):
                        p.x = nx
                    if not self._is_blocked(p.x, ny):
                        p.y = ny
            elif enemy.attack_windup > 0.0:
                before = enemy.attack_windup
                enemy.attack_windup = max(0.0, enemy.attack_windup - dt)
                if before > 0.0 and enemy.attack_windup <= 0.0:
                    if enemy.ranged:
                        if dist < enemy.attack_range + 3.0:
                            if enemy.kind in ("pyre", "dragon", "ashfiend"):
                                zoff = 2.1 if enemy.kind == "dragon" else 1.34
                                self._spawn_enemy_fireball(enemy, p + Vec3(0.58, -0.08, zoff))
                            else:
                                self._spawn_enemy_hex_bolt(enemy, p + Vec3(0, 0, 1.35))
                    elif dist < enemy.attack_range + 0.38:
                        landed = self._hurt_player(enemy.damage, f"A {self._enemy_name(enemy)} STRUCK YOU")
                        if not landed and self.keys["block"]:
                            away = Vec2(p.x - self.player_pos.x, p.y - self.player_pos.y)
                            if away.lengthSquared() > 0.001:
                                away.normalize()
                                enemy.knockback_x = away.x * 4.2
                                enemy.knockback_y = away.y * 4.2
                                enemy.stagger_timer = 0.20
                    enemy.attack_cooldown = enemy.attack_interval
            else:
                if enemy.kind == "dragon" and dist >= enemy.detection_range:
                    # Territorial dragons circle their nest/home instead of standing
                    # on the terrain like an ordinary ranged monster.
                    patrol_r = 9.0 + 2.0 * math.sin(t * 0.17 + enemy.phase)
                    p.x = enemy.home.x + math.cos(t * 0.24 + enemy.phase) * patrol_r
                    p.y = enemy.home.y + math.sin(t * 0.24 + enemy.phase) * patrol_r
                elif enemy.ranged and dist < enemy.detection_range:
                    if dist < 6.0 and dist > 0.01:
                        away = Vec2(p.x - self.player_pos.x, p.y - self.player_pos.y)
                        away.normalize()
                        nx = p.x + away.x * enemy.speed * 0.78 * dt
                        ny = p.y + away.y * enemy.speed * 0.78 * dt
                        if not self._is_blocked(nx, p.y): p.x = nx
                        if not self._is_blocked(p.x, ny): p.y = ny
                    elif dist > 10.5 and dist > 0.01:
                        to_player.normalize()
                        nx = p.x + to_player.x * enemy.speed * dt
                        ny = p.y + to_player.y * enemy.speed * dt
                        if not self._is_blocked(nx, p.y): p.x = nx
                        if not self._is_blocked(p.x, ny): p.y = ny
                elif dist < enemy.detection_range and dist > enemy.attack_range * 0.90:
                    if dist > 0.01:
                        to_player.normalize()
                        nx = p.x + to_player.x * enemy.speed * dt
                        ny = p.y + to_player.y * enemy.speed * dt
                        if not self._is_blocked(nx, p.y): p.x = nx
                        if not self._is_blocked(p.x, ny): p.y = ny
                elif dist > enemy.detection_range + 6.0:
                    to_home = Vec2(enemy.home.x - p.x, enemy.home.y - p.y)
                    if to_home.length() > 0.8:
                        to_home.normalize()
                        p.x += to_home.x * enemy.speed * 0.52 * dt
                        p.y += to_home.y * enemy.speed * 0.52 * dt

                if dist < enemy.attack_range and enemy.attack_cooldown <= 0.0:
                    enemy.attack_windup = enemy.windup_duration

            ground = self._height(p.x, p.y)
            bob_speed = 4.6 if enemy.kind == "imp" else (2.4 if enemy.kind in ("brute", "golem") else (1.55 if enemy.kind == "dragon" else (2.85 if enemy.kind in ("pyre", "ashfiend") else 3.2)))
            bob_amp = 0.18 if enemy.kind in ("brute", "golem") else (0.58 if enemy.kind == "dragon" else (0.22 if enemy.kind in ("pyre", "ashfiend") else 0.28))
            base_height = 4.8 if enemy.kind == "dragon" else (1.15 if enemy.kind in ("beast", "wolf", "scorpion", "frostling", "bogling") else 0.72)
            if enemy.kind == "dragon":
                home_flight = enemy.home.z + 2.0 + math.sin(t * bob_speed + enemy.phase) * 1.15
                p.z = max(ground + base_height, home_flight)
            else:
                p.z = ground + base_height + math.sin(t * bob_speed + enemy.phase) * bob_amp
            enemy.node.setPos(p)
            if enemy.kind == "dragon":
                flap = math.sin(t * 4.2 + enemy.phase)
                wings = enemy.node.findAllMatches("**/dragon-wing")
                for wi in range(wings.getNumPaths()):
                    wing = wings.getPath(wi)
                    side = -1.0 if wing.getX() < 0.0 else 1.0
                    wing.setR(side * (18.0 + flap * 24.0))

            if enemy.hit_flash > 0.0:
                pulse = enemy.hit_flash / 0.18
                mul = 0.88 + (1.0 - pulse) * 0.12
                enemy.node.setScale(enemy.scale_x * mul, enemy.scale_y * mul, enemy.scale_z * mul)
                enemy.node.setColorScale(1.55, 0.56, 0.24, 1.0)
                enemy.node.setH(enemy.node.getH() + 190.0 * dt)
            elif enemy.attack_windup > 0.0:
                charge = 1.0 - enemy.attack_windup / max(0.01, enemy.windup_duration)
                throb = 1.0 + 0.16 * math.sin(charge * math.pi * 5.0) + 0.12 * charge
                enemy.node.setScale(enemy.scale_x * throb, enemy.scale_y * throb, enemy.scale_z * throb)
                if enemy.kind == "hexer":
                    enemy.node.setColorScale(1.22, 0.38, 1.42, 1.0)
                elif enemy.kind == "pyre":
                    enemy.node.setColorScale(1.42, 0.42 + 0.42 * charge, 0.16, 1.0)
                    flame = enemy.node.find("**/pyre-hand-flame")
                    if not flame.isEmpty():
                        flame.show()
                        pulse = 0.55 + charge * 1.15 + 0.18 * math.sin(charge * math.pi * 8.0)
                        flame.setScale(pulse, pulse, pulse * 1.18)
                    enemy.node.setP(-10.0 * charge)
                else:
                    enemy.node.setColorScale(1.30, 0.42 + 0.20 * charge, 0.30, 1.0)
                enemy.node.setH(enemy.node.getH() + 28.0 * dt)
            else:
                enemy.node.setScale(enemy.scale_x, enemy.scale_y, enemy.scale_z)
                enemy.node.setColorScale(1.0, 1.0, 1.0, 1.0)
                if enemy.kind == "pyre":
                    flame = enemy.node.find("**/pyre-hand-flame")
                    if not flame.isEmpty():
                        flame.hide()
                    enemy.node.setP(0.0)
                spin = 18.0 if enemy.kind == "dragon" else (118.0 if enemy.kind == "imp" else (46.0 if enemy.kind in ("brute", "golem") else (58.0 if enemy.kind in ("pyre", "ashfiend") else 72.0)))
                enemy.node.setH(enemy.node.getH() + spin * dt)

    def _update_magic_projectiles(self, dt: float) -> None:
        alive: list[MagicProjectile] = []
        for projectile in self.magic_projectiles:
            projectile.life -= dt
            if projectile.life <= 0.0:
                projectile.node.removeNode()
                continue
            p = projectile.node.getPos(self.render)
            if projectile.spell == "DEMON FIREBALL":
                # A shallow downward drift keeps the shot feeling thrown rather than
                # like another straight magical laser.
                projectile.velocity.z -= 0.65 * dt
            p += projectile.velocity * dt
            projectile.node.setPos(p)
            if not projectile.friendly and self._in_utopia_sanctuary(p.x, p.y, 1.0):
                self._spawn_magic_burst_fx(p, 0.55)
                projectile.node.removeNode()
                continue
            projectile.node.setHpr(
                projectile.node.getH() + 310.0 * dt,
                projectile.node.getP() + 180.0 * dt,
                projectile.node.getR() + 240.0 * dt,
            )

            consumed = False
            if projectile.friendly:
                hit_enemy = None
                for enemy in self.enemies:
                    if not enemy.alive:
                        continue
                    ep = enemy.node.getPos(self.render) + Vec3(0, 0, 0.6)
                    if (ep - p).length() < 1.05:
                        hit_enemy = enemy
                        break
                terrain_hit = p.z <= self._height(p.x, p.y) + 0.20
                if hit_enemy is not None or terrain_hit:
                    self._play_sfx("magic_impact")
                    if projectile.spell == "EMBER ORB":
                        self._spawn_magic_burst_fx(p, projectile.radius)
                        for enemy in self.enemies:
                            if not enemy.alive:
                                continue
                            ep = enemy.node.getPos(self.render)
                            if (ep - p).length() <= projectile.radius:
                                self._damage_enemy(enemy, projectile.damage, p, 6.8, "EMBER")
                    elif hit_enemy is not None:
                        self._spawn_magic_burst_fx(p, 1.0)
                        self._damage_enemy(hit_enemy, projectile.damage, p, 5.6, "ARC BOLT")
                    projectile.node.removeNode()
                    consumed = True
            else:
                eye = self.scene_cam.getPos(self.render)
                terrain_hit = p.z <= self._height(p.x, p.y) + 0.16
                hit_radius = 1.12 if projectile.spell == "DEMON FIREBALL" else 0.90
                if (eye - p).length() < hit_radius:
                    self._play_sfx("magic_impact")
                    if projectile.spell == "DEMON FIREBALL":
                        self._spawn_fire_burst_fx(p, 1.75)
                        self._hurt_player(projectile.damage, "A PYRE HURLER'S FIREBALL HIT YOU")
                    else:
                        self._spawn_magic_burst_fx(p, 1.0)
                        self._hurt_player(projectile.damage, "A HEXER'S RUNE BOLT HIT YOU")
                    projectile.node.removeNode()
                    consumed = True
                elif terrain_hit:
                    self._play_sfx("magic_impact")
                    if projectile.spell == "DEMON FIREBALL":
                        self._spawn_fire_burst_fx(p, 1.55)
                    else:
                        self._spawn_magic_burst_fx(p, 0.75)
                    projectile.node.removeNode()
                    consumed = True

            if not consumed:
                alive.append(projectile)
        self.magic_projectiles = alive

    def _update_combat_fx(self, dt: float) -> None:
        alive_fx: list[CombatFx] = []
        for fx in self.combat_fx:
            fx.life -= dt
            if fx.life <= 0.0:
                fx.node.removeNode()
                continue
            p = fx.node.getPos(self.render)
            fx.velocity.z -= 12.0 * dt
            p += fx.velocity * dt
            fx.node.setPos(p)
            fx.node.setHpr(
                fx.node.getH() + 280.0 * dt,
                fx.node.getP() + 190.0 * dt,
                fx.node.getR() + 120.0 * dt,
            )
            life01 = max(0.0, min(1.0, fx.life / fx.duration))
            fx.node.setScale(0.55 + life01 * 0.70)
            fx.node.setColorScale(1.0, 1.0, 1.0, life01)
            alive_fx.append(fx)
        self.combat_fx = alive_fx

    def _update_lightning_fx(self, dt: float) -> None:
        alive: list[LightningFx] = []
        for fx in self.lightning_fx:
            fx.life -= dt
            if fx.life <= 0.0:
                fx.node.removeNode()
                continue
            life01 = max(0.0, min(1.0, fx.life / max(0.001, fx.duration)))
            # Electricity snaps on hard, then disappears quickly instead of
            # drifting like the physical combat particles.
            alpha = min(1.0, life01 * 1.65)
            fx.node.setColorScale(1.0, 1.0, 1.0, alpha)
            alive.append(fx)
        self.lightning_fx = alive

    def _update_pickups(self, dt: float, t: float) -> None:
        for pickup in self.pickups:
            if pickup.collected:
                continue
            pickup.node.setZ(pickup.origin.z + math.sin(t * 2.0 + pickup.phase) * 0.22)
            pickup.node.setH(pickup.node.getH() + (95.0 if pickup.kind == "coin" else 46.0) * dt)
            p = pickup.node.getPos(self.render)
            if math.hypot(self.player_pos.x - p.x, self.player_pos.y - p.y) < 1.55:
                pickup.collected = True
                pickup.node.hide()
                if pickup.kind == "sigil":
                    self._play_sfx("sigil", "pickup")
                    self.sigils += 1
                    self.currency += 20
                    if self.sigils >= 3:
                        self._show_message("FINAL SIGIL FOUND - RETURN TO THE SHRINE", 2.4)
                    else:
                        self._show_message(f"SIGIL FOUND  {self.sigils}/3", 1.8)
                else:
                    self._play_sfx("pickup")
                    self.currency += pickup.value

    @staticmethod
    def _smoothstep01(value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value * value * (3.0 - 2.0 * value)

    @staticmethod
    def _pose_lerp(a: Vec3, b: Vec3, amount: float) -> Vec3:
        return a + (b - a) * amount

    def _update_weapon(self, dt: float) -> None:
        self.sword_cooldown = max(0.0, self.sword_cooldown - dt)
        self.sword_impact_kick = max(0.0, self.sword_impact_kick - dt)

        if self.sword_timer > 0.0:
            self.sword_timer = max(0.0, self.sword_timer - dt)
            phase = 1.0 - self.sword_timer / self.sword_attack_duration

            rest_p = self.sword_rest_pos
            rest_r = self.sword_rest_hpr
            start_p = self.sword_attack_start_pos
            start_r = self.sword_attack_start_hpr
            # PASS 09: keep the player's HAND anchored in the lower-right.
            # Previous passes technically pivoted from the grip, but still moved
            # that entire pivot several tenths of a screen-width toward center.
            # That made the handle sweep into the camera even though the blade
            # model itself faced the correct direction.  These poses now have
            # only millimetric hand movement; the visible cut is almost entirely
            # rotation around the grip.
            wind_p = rest_p + Vec3(0.012, 0.008, 0.010)
            wind_r = Vec3(30, -6, -48)
            hit_p = rest_p + Vec3(-0.010, 0.018, 0.025)
            hit_r = Vec3(-30, -2, -6)
            follow_p = rest_p + Vec3(0.006, 0.012, -0.010)
            follow_r = Vec3(-60, 5, 24)

            # Never lose the hit because of a long frame that skips over the
            # narrow visual contact phase.
            if phase >= 0.40:
                self._resolve_sword_hit()

            if phase < 0.22:
                # Deliberate anticipation: draw the weapon back before committing.
                u = self._smoothstep01(phase / 0.22)
                pos = self._pose_lerp(start_p, wind_p, u)
                hpr = self._pose_lerp(start_r, wind_r, u)
            elif phase < 0.50:
                # Fast cutting arc.  Ease-out makes the blade accelerate away
                # from the wind-up and arrive decisively at the contact point.
                u = (phase - 0.22) / 0.28
                u = 1.0 - (1.0 - u) ** 3
                pos = self._pose_lerp(wind_p, hit_p, u)
                hpr = self._pose_lerp(wind_r, hit_r, u)
            elif phase < 0.68:
                u = self._smoothstep01((phase - 0.50) / 0.18)
                pos = self._pose_lerp(hit_p, follow_p, u)
                hpr = self._pose_lerp(hit_r, follow_r, u)
            else:
                # Recovery is intentionally slower than the actual cut so the
                # sword has weight and cannot instantly snap back to idle.
                u = self._smoothstep01((phase - 0.68) / 0.32)
                pos = self._pose_lerp(follow_p, rest_p, u)
                hpr = self._pose_lerp(follow_r, rest_r, u)

            if self.sword_impact_kick > 0.0:
                kick = self.sword_impact_kick / 0.075
                # Never kick the hand back toward the camera.  Contact is shown
                # as a tiny wrist recoil plus rotation while the grip stays put.
                pos += Vec3(0.004 * kick, 0.020 * kick, 0.003 * kick)
                hpr += Vec3(2.5 * kick, 0.8 * kick, -2.2 * kick)

            self.sword_root.setPos(pos)
            self.sword_root.setHpr(hpr)

            # Show a very short after-image only through the cutting portion.
            if 0.28 <= phase <= 0.66:
                cut = (phase - 0.28) / 0.38
                alpha = math.sin(max(0.0, min(1.0, cut)) * math.pi)
                for i, trail in enumerate(self.slash_trails):
                    lag = 0.035 + i * 0.035
                    trail_pos = pos + Vec3(0.10 + i * 0.045, -0.10 - i * 0.04, 0.02)
                    trail_hpr = hpr + Vec3(8.0 + i * 10.0, 0.0, -7.0 - i * 7.0)
                    trail.setPos(trail_pos)
                    trail.setHpr(trail_hpr)
                    trail.setScale(1.0 + lag * 1.8, 1.0, 1.0)
                    trail.setColorScale(1.0, 1.0, 1.0, alpha * (0.62 - i * 0.13))
                    trail.show()
            else:
                for trail in self.slash_trails:
                    trail.hide()
            return

        for trail in self.slash_trails:
            trail.hide()

        # Blocking and idle blend without ever dragging the hand toward the
        # middle of the screen.  Guard changes wrist angle, not hand location.
        moving = self.velocity.lengthSquared() > 0.05
        idle_bob = math.sin(self.play_time * (7.2 if moving else 2.0))
        if self.keys["block"]:
            target_p = self.sword_rest_pos + Vec3(0.010, 0.018, 0.055 + idle_bob * 0.005)
            target_r = Vec3(-4.0, -14.0, -64.0 + idle_bob * 0.8)
            response = 1.0 - math.exp(-dt * 18.0)
        else:
            target_p = self.sword_rest_pos + Vec3(idle_bob * 0.003, 0.0, idle_bob * 0.006)
            target_r = self.sword_rest_hpr + Vec3(idle_bob * 0.45, 0.0, -idle_bob * 0.30)
            response = 1.0 - math.exp(-dt * 13.0)

        self.sword_root.setPos(self._pose_lerp(self.sword_root.getPos(), target_p, response))
        self.sword_root.setHpr(self._pose_lerp(self.sword_root.getHpr(), target_r, response))

    def _update_staff(self, dt: float, t: float) -> None:
        self.staff_cooldown = max(0.0, self.staff_cooldown - dt)
        self.staff_cast_timer = max(0.0, self.staff_cast_timer - dt)

        moving = self.velocity.lengthSquared() > 0.05
        bob = math.sin(t * (6.4 if moving else 1.8))
        if self.staff_cast_timer > 0.0:
            phase = 1.0 - self.staff_cast_timer / self.staff_cast_duration
            cast = math.sin(max(0.0, min(1.0, phase)) * math.pi)
            # The hand stays on the left edge; casting is a modest forward lean
            # of the staff top rather than a large screen-space sweep.
            target_p = self.staff_rest_pos + Vec3(0.0, 0.018 * cast, 0.008 * cast)
            target_r = self.staff_rest_hpr + Vec3(-1.5 * cast, -13.0 * cast, 2.5 * cast)
            response = 1.0 - math.exp(-dt * 24.0)
            pulse = 1.0 + 0.42 * cast + 0.10 * math.sin(t * 52.0)
        else:
            target_p = self.staff_rest_pos + Vec3(-bob * 0.0025, 0.0, bob * 0.006)
            target_r = self.staff_rest_hpr + Vec3(bob * 0.24, 0.0, bob * 0.28)
            response = 1.0 - math.exp(-dt * 12.0)
            pulse = 1.0 + 0.055 * math.sin(t * 5.0)

        self.staff_root.setPos(self._pose_lerp(self.staff_root.getPos(), target_p, response))
        self.staff_root.setHpr(self._pose_lerp(self.staff_root.getHpr(), target_r, response))
        self.staff_crystal.setScale(0.88 * pulse, 0.88 * pulse, 1.42 * pulse)
        self.staff_crystal_core.setScale(0.78 * pulse, 0.78 * pulse, 1.35 * pulse)
        self.staff_crystal_core.setH(self.staff_crystal_core.getH() + 190.0 * dt)

    def _update_utopia_portal(self, dt: float, t: float) -> None:
        if not self.portal_link_ready:
            return
        pulse = 1.0 + 0.08 * math.sin(t * 4.5)
        core_pulse = 1.0 + 0.14 * math.sin(t * 7.2)
        if hasattr(self, "utopia_core") and not self.utopia_core.isEmpty():
            self.utopia_core.setScale(0.55 * core_pulse, 0.32 * core_pulse, 1.50 * core_pulse)
            self.utopia_core.setH((t * 58.0) % 360.0)
        if hasattr(self, "utopia_aperture") and not self.utopia_aperture.isEmpty():
            self.utopia_aperture.setScale(pulse, pulse, pulse)
            self.utopia_aperture.setColorScale(1.0, 1.0, 1.0, 0.58 + 0.18 * math.sin(t * 3.1))
        if hasattr(self, "utopia_beacon") and not self.utopia_beacon.isEmpty():
            glow = 0.82 + 0.18 * math.sin(t * 2.6)
            self.utopia_beacon.setColorScale(1.0, glow, 1.0, 1.0)
        if hasattr(self, "utopia_beacon_cross") and not self.utopia_beacon_cross.isEmpty():
            self.utopia_beacon_cross.setColorScale(0.72 + 0.28 * pulse, 1.0, 1.0, 1.0)

    def _update_magic(self, dt: float, t: float) -> None:
        for node, origin, amp, phase in self.animated_magic:
            if node.isHidden():
                continue
            node.setZ(origin.z + math.sin(t * 2.4 + phase) * amp)
            node.setH(node.getH() + 42.0 * dt)

        self.cast_flash_timer = max(0.0, self.cast_flash_timer - dt)
        ward_active = self.magic_ward_timer > 0.0 and self.magic_ward_charges > 0
        if self.cast_flash_timer > 0.0 or ward_active:
            self.cast_focus.show()
            pulse = 1.0 + 0.22 * math.sin(t * 14.0)
            if self.cast_flash_timer > 0.0:
                pulse += 0.38 * (self.cast_flash_timer / 0.34)
            self.cast_focus.setScale(0.9 * pulse, 0.9 * pulse, 1.35 * pulse)
            self.cast_focus.setHpr(t * 150.0, t * 95.0, t * 120.0)
            self.cast_focus.setColorScale(1.0, 1.0, 1.0, 0.72 if ward_active else 1.0)
        else:
            self.cast_focus.hide()

    def _update_prompt(self) -> None:
        self.near_prompt = ""
        utopia_dist = math.hypot(self.player_pos.x - self.utopia_portal_pos.x, self.player_pos.y - self.utopia_portal_pos.y)
        entrance_dist = math.hypot(self.player_pos.x - self.shrine_entrance.x, self.player_pos.y - self.shrine_entrance.y)
        portal_dist = math.hypot(self.player_pos.x - self.shrine_portal_pos.x, self.player_pos.y - self.shrine_portal_pos.y)
        if utopia_dist < 7.0:
            self.near_prompt = "[ E ] RETURN TO UTOPIA CENTRAL HUB"
            host = "CONNECTED" if os.environ.get("GX_PORTAL_HANDOFF_PATH", "").strip() else "STANDALONE"
            self.portal_status_text.setText(self._font_safe_text(
                f"UTOPIA IMMERSIVE SYSTEMS  //  PORTAL NODE: GLYPHBOUND  //  CENTRAL HUB LINK: {host}"
            ))
        else:
            self.portal_status_text.setText("")
        if utopia_dist >= 7.0 and not self.shrine_unlocked and entrance_dist < 6.0:
            self.near_prompt = "[ E ] READ THE SHRINE SEAL"
        elif self.shrine_unlocked and not self.prototype_complete and portal_dist < 5.0:
            self.near_prompt = "[ E ] ENTER THE AWAKENED SHRINE"
        self.prompt_text.setText(self._font_safe_text(self.near_prompt))

    def _objective_text(self) -> str:
        if self.prototype_complete:
            return "THE SHATTERED SHRINE\n> EXPLORE THE GLYPH WORLD"
        if self.shrine_unlocked:
            return "THE SHATTERED SHRINE\n> ENTER THE AWAKENED SHRINE"
        if self.sigils >= 3:
            return "THE SHATTERED SHRINE\n> RETURN TO THE SEALED DOOR"
        return f"THE SHATTERED SHRINE\n> FIND THE LOST SIGILS  {self.sigils}/3"

    def _update_hud(self) -> None:
        hp_full = "#" * self.health
        hp_empty = "." * (self.settings.max_health - self.health)
        self.hearts_text.setText(self._font_safe_text(f"HP   [{hp_full}{hp_empty}]"))

        segments = 22
        filled = int(round((self.stamina / self.settings.max_stamina) * segments))
        self.stamina_text.setText(self._font_safe_text("STA  [" + "|" * filled + "." * (segments - filled) + "]"))
        mana_segments = 18
        mana_filled = int(round((self.mana / self.settings.max_mana) * mana_segments))
        ward = "  [WARD]" if self.magic_ward_timer > 0.0 and self.magic_ward_charges > 0 else ""
        mana_bar = "*" * mana_filled + "." * (mana_segments - mana_filled)
        self.mana_text.setText(self._font_safe_text(f"MANA [{mana_bar}]  [{self.selected_spell + 1}] {self.spell_names[self.selected_spell]}{ward}"))
        self.currency_text.setText(self._font_safe_text(f"GOLD {self.currency:03d}     SIGILS {self.sigils}/3"))

        angle = self.heading % 360.0
        cardinals = ((0, "N"), (90, "W"), (180, "S"), (270, "E"))
        nearest = min(cardinals, key=lambda pair: abs(((angle - pair[0] + 180) % 360) - 180))[1]
        target = self.SHRINE_POS
        dx = target.x - self.player_pos.x
        dy = target.y - self.player_pos.y
        meters = int(math.hypot(dx, dy))
        target_heading = math.degrees(math.atan2(-dx, dy)) % 360.0
        delta = ((target_heading - angle + 180.0) % 360.0) - 180.0
        arrow = "^" if abs(delta) < 8 else (">" if delta < 0 else "<")
        hub_dx = self.utopia_portal_pos.x - self.player_pos.x
        hub_dy = self.utopia_portal_pos.y - self.player_pos.y
        hub_meters = int(math.hypot(hub_dx, hub_dy))
        hub_heading = math.degrees(math.atan2(-hub_dx, hub_dy)) % 360.0
        hub_delta = ((hub_heading - angle + 180.0) % 360.0) - 180.0
        hub_arrow = "^" if abs(hub_delta) < 8 else (">" if hub_delta < 0 else "<")
        self.compass_text.setText(self._font_safe_text(f"W . {nearest} . E   {arrow} SHRINE {meters}m   {hub_arrow} HUB {hub_meters}m"))

        self.quest_text.setText(self._font_safe_text(self._objective_text()))
        weather_label = self.weather_state
        if self.weather_state == "CLEAR" and self.weather_cloud > 0.18:
            weather_label = "CLEARING"
        elif self.weather_state in ("RAIN", "STORM") and self.weather_rain < 0.24:
            weather_label = "RAIN APPROACHING"
        self.current_biome = self._biome_at(self.player_pos.x, self.player_pos.y)
        self.current_place = self._nearest_place(self.player_pos.x, self.player_pos.y)
        region_label = self.current_biome if not self.current_place else f"{self.current_biome}  >  {self.current_place}"
        self.weather_text.setText(self._font_safe_text(f"{self._format_world_time()}   {weather_label}   |   {region_label}"))
        cols, rows = self.GRID_PRESETS[self.grid_index]
        water = "  SWIMMING" if self.in_water else ""
        self.dev_text.setText(self._font_safe_text(f"{self.STYLE_NAMES[self.style_mode]}  {cols}x{rows}{water}"))

    def _show_message(self, text: str, duration: float = 1.4) -> None:
        self.message_timer = duration
        self.message_text.setText(self._font_safe_text(text))

    def _update(self, task):
        now = time.perf_counter()
        dt = min(0.065, max(0.0, now - self.last_frame))
        self.last_frame = now
        self.play_time += dt

        self._update_mouse_look(dt)
        if self.portal_transition_timer <= 0.0:
            self._move_player(dt)
        self._update_world_stream()
        self._update_weather(dt)
        self._update_enemies(dt, self.play_time)
        self._update_magic_projectiles(dt)
        self._update_combat_fx(dt)
        self._update_lightning_fx(dt)
        self._update_pickups(dt, self.play_time)
        self._update_weapon(dt)
        self._update_staff(dt, self.play_time)
        self._update_utopia_portal(dt, self.play_time)
        self._update_magic(dt, self.play_time)
        if not self.no_audio:
            self._update_audio(dt)
        self._update_prompt()
        self._sync_camera()

        if self.portal_transition_timer > 0.0:
            self.portal_transition_timer = max(0.0, self.portal_transition_timer - dt)
            pulse = 1.0 + 0.16 * math.sin(self.play_time * 18.0)
            if hasattr(self, "utopia_core") and not self.utopia_core.isEmpty():
                self.utopia_core.setScale(0.55 * pulse, 0.32 * pulse, 1.50 * pulse)
            if self.portal_transition_timer <= 0.0:
                self._finish_central_hub_return()

        self.damage_flash = max(0.0, self.damage_flash - dt)
        self.magic_cooldown = max(0.0, self.magic_cooldown - dt)
        self.mana_regen_delay = max(0.0, self.mana_regen_delay - dt)
        self.magic_ward_timer = max(0.0, self.magic_ward_timer - dt)
        if self.magic_ward_timer <= 0.0:
            self.magic_ward_charges = 0
        if self.mana_regen_delay <= 0.0:
            self.mana = min(self.settings.max_mana, self.mana + 7.5 * dt)
        if self.message_timer > 0.0:
            self.message_timer -= dt
            if self.message_timer <= 0.0:
                self.message_text.setText("")

        # Gives the glyph shader a stable time source for sparse sky speckles.
        if not self.software_test:
            self.present_card.setShaderInput("pulse", float(self.play_time))
        self.hud_update_timer -= dt
        if self.hud_update_timer <= 0.0:
            self.hud_update_timer = 0.10
            self._update_hud()
        return task.cont


if __name__ == "__main__":
    # Pass 282.69: closing the window always ends the process (nothing left running in the background).
    _exit_code = 0
    try:
        Glyphbound().run()
    except SystemExit as _exc:
        _exit_code = _exc.code if isinstance(_exc.code, int) else 0
    except BaseException:
        import traceback
        traceback.print_exc()
        _exit_code = 1
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(_exit_code)
