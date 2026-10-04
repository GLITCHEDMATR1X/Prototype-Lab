from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import math
import pickle
import py_compile
import random
import re
import sys
from pathlib import Path

from panda3d.core import NodePath

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"
checks: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    checks.append((name, bool(condition), detail))


try:
    py_compile.compile(str(MAIN), cfile="/tmp/glyphbound_pass23_main.pyc", doraise=True)
    check("Python compile", True)
except Exception as exc:
    check("Python compile", False, repr(exc))

source = MAIN.read_text(encoding="utf-8")
tree = ast.parse(source)
classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Glyphbound"]
check("Glyphbound class exists", len(classes) == 1)
methods = [node.name for node in classes[0].body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))] if classes else []
check("No duplicate class methods", len(methods) == len(set(methods)))

required_methods = {
    "_add_terrain_foundation",
    "_sample_footprint_heights",
    "_add_ground_ribbon",
    "_add_foundation_toe",
    "_structure_entrance_anchor",
    "_add_structure_entrance",
    "_add_structure_approach",
    "_biome_ground_dressing_color",
    "_add_settlement_edge_dressing",
    "_build_utopia_portal",
    "_write_portal_handoff",
    "_begin_central_hub_return",
    "_finish_central_hub_return",
    "_return_to_utopia_beacon",
    "_reset_world_to_portal",
    "_update_utopia_portal",
    "_capture_test_shot",
}
for method in sorted(required_methods):
    check(f"Method {method}", method in methods)

check("Pass 24 window title", source.count("Pass 24") >= 1)
check("Foundation demo preserved", '"--foundation-demo" in sys.argv' in source)
check("Village entrance demo", '"--entrance-demo" in sys.argv' in source)
check("City entrance demo", '"--city-entrance-demo" in sys.argv' in source)

# Pass 21/22 terrain authority remains intact.
check("Nine-point footprint sampling preserved", "local_points = (" in source and "(0.0, -half_y), (0.0, half_y)" in source)
check("Foundation clears high terrain", "top = high + 0.055" in source)
check("Foundation embeds below low terrain", "bottom = low - 0.22" in source)
check("Deep foundation lower course", "lower-course" in source and "depth > 0.72" in source)
check("Terrain ribbon generated geometry", 'GeomVertexData(name, fmt, Geom.UHStatic)' in source and 'GeomTriangles(Geom.UHStatic)' in source)
check("Ribbon samples both terrain edges", 'sz = self._height(sx, sy) + 0.070' in source)
check("Ribbon refuses river-water crossings", 'if self._river_water_z(sx, sy) is not None:' in source)
check("Ribbon subdivision bounded", 'min(20, int(math.ceil(length / 1.15)))' in source)
check("Slope steps require measured rise", 'if rise < 0.24:' in source)
check("Retaining stones require exposure", 'if exposure < 0.62:' in source)
check("Settlement visual clearance preserved", 'settlement_clear_radius = 30.5 if city else 20.5 if village else 0.0' in source)
check("Perimeter dressing isolated RNG", 'random.Random(self._chunk_seed(cx, cy, 229))' in source)

# Pass 23 entrance contracts.
check("Facade-center entrance authority", "def _structure_entrance_anchor(" in source and "face_half_span" in source)
check("Entrance chooses X or Y facade", "if tx <= ty:" in source and "face_y = y + ny * half_y" in source)
check("Approach uses entrance anchor", "face_x, face_y, nx, ny, _face_heading, _face_span = self._structure_entrance_anchor(" in source)
check("Sealed threshold root", "sealed-threshold-root" in source)
check("Closed door slab", "sealed-door" in source and "Dark closed slab" in source)
check("Stone jambs", "door-jamb" in source)
check("Stone lintel", "door-lintel" in source)
check("Foundation-connected landing", "threshold-landing" in source and "landing.setPos" in source)
check("Explicit rune seal", "sealed-rune" in source and "seal.setLightOff(1)" in source)
check("Explicit seal bar", "seal-bar" in source and "bar.setLightOff(1)" in source)
check("No handle affordance introduced", "door-handle" not in source and "handle.set" not in source)
check("Village/city houses receive entrances", 'root, "city-house" if city else "village-house"' in source)
check("City keep receives monumental entrance", 'root, "city-keep"' in source and "monumental=True" in source)
check("City gate towers receive entrances", 'root, "city-gate-tower"' in source)

# Portal/controls regression contracts.
check("Portal ID", 'UTOPIA_PORTAL_ID = "UTOPIA_FANTASY_GLYPHBOUND"' in source)
check("Central Hub target", '"target": "CENTRAL_HUB"' in source)
check("Handoff source pass identity", '"source_pass": 23' in source)
check("Atomic handoff replace", "os.replace(temp, path)" in source)
check("Handoff environment contract", "GX_PORTAL_HANDOFF_PATH" in source)
check("Standalone portal nonfatal", "PROTOTYPE LAB HANDOFF NOT CONNECTED" in source)
check("Death uses portal recovery", 'self._return_to_utopia_beacon("SIMULATION RECONSTRUCTION")' in source)
check("F6 recovery preserved", 'self.accept("f6", self._reset_world_to_portal)' in source)
check("Portal interaction prompt", "RETURN TO UTOPIA CENTRAL HUB" in source)
q_accept = re.findall(r'self\.accept\(\s*["\']q["\']', source, flags=re.I)
check("Q remains unbound", not q_accept, f"bindings={len(q_accept)}")
check("No abrupt process exit", "sys.exit(" not in source and "os._exit(" not in source)

# Project metadata.
try:
    contract = json.loads((ROOT / "portal_contract.json").read_text(encoding="utf-8"))
    check("Portal contract JSON", True)
    check("Portal contract target", contract.get("return_target") == "CENTRAL_HUB")
    check("Portal contract pass", contract.get("pass") == 24)
    check("Portal contract sanctuary", float(contract.get("sanctuary_radius", 0)) >= 20.0)
except Exception as exc:
    check("Portal contract JSON", False, repr(exc))

try:
    project = json.loads((ROOT / "gptool.project.json").read_text(encoding="utf-8"))
    check("Project metadata JSON", True)
    check("Project authoritative pass", project.get("authoritative_pass") == 24)
    verification = json.dumps(project.get("verification", {})).lower()
    check("Project Pass 24 verifier command", "verify_pass24_holoverse_native" in verification)
    check("Project entrance QA commands", "entrance-demo" in verification and "city-entrance-demo" in verification)
except Exception as exc:
    check("Project metadata JSON", False, repr(exc))

readme = (ROOT / "README.txt").read_text(encoding="utf-8")
check("README identifies Pass 24", "PASS 24" in readme)
check("README documents sealed entrances", "SEALED ENTRANCE IDENTITY" in readme)
check("README explains noninteractive seal", "not playable" in readme.lower() and "sealed" in readme.lower())
check("README preserves Pass 22 terrain integration", "TERRAIN-INTEGRATED SETTLEMENTS" in readme)
check("README preserves Pass 21 foundations", "TERRAIN-BOUND FOUNDATIONS" in readme)
check("README documents entrance demos", "--entrance-demo" in readme and "--city-entrance-demo" in readme)
check("Panda3D locked to 1.10.16", (ROOT / "requirements.txt").read_text().strip() == "panda3d==1.10.16")
check("Launcher forwards arguments", "%*" in (ROOT / "RUN_GLYPHBOUND.bat").read_text())


def sha(path: Path) -> str:
    h = hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()


try:
    preserved_manifest = json.loads((ROOT / "preserved_asset_sha256.json").read_text(encoding="utf-8"))["files"]
    bad = []
    for rel, expected in preserved_manifest.items():
        path = ROOT / rel
        if not path.is_file() or sha(path) != expected:
            bad.append(rel)
    check("Glyph/audio assets preserved byte-for-byte", not bad, ", ".join(bad[:5]))
except Exception as exc:
    check("Asset preservation manifest", False, repr(exc))

# Pure Panda3D placement/anchor validation without opening a graphics window.
try:
    spec = importlib.util.spec_from_file_location("glyphbound_pass23_main", MAIN)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    obj = module.Glyphbound.__new__(module.Glyphbound)
    obj.world_seed = 0x6A17B04D
    obj.settings = module.Settings()
    obj.proc_obstacles = {}
    obj.defeated_stream_spawns = set()

    vx, vy = obj._settlement_center(-5, -1)
    terrain_samples = obj._sample_footprint_heights(vx, vy, 4.0, 4.0)
    spread = max(terrain_samples) - min(terrain_samples)
    check("QA village footprint meaningfully sloped", spread > 1.5, f"spread={spread:.3f}m")
    check("QA footprint returns nine samples", len(terrain_samples) == 9, f"count={len(terrain_samples)}")

    # Anchor faces should land on facade centers, not corner/intersection points.
    east = obj._structure_entrance_anchor(0.0, 0.0, 2.0, 1.0, 10.0, 1.5)
    west = obj._structure_entrance_anchor(0.0, 0.0, 2.0, 1.0, -10.0, -1.5)
    north = obj._structure_entrance_anchor(0.0, 0.0, 2.0, 1.0, 0.2, 10.0)
    south = obj._structure_entrance_anchor(0.0, 0.0, 2.0, 1.0, -0.2, -10.0)
    check("East facade center anchor", abs(east[0] - 2.0) < 1e-9 and abs(east[1]) < 1e-9 and east[2:4] == (1.0, 0.0))
    check("West facade center anchor", abs(west[0] + 2.0) < 1e-9 and abs(west[1]) < 1e-9 and west[2:4] == (-1.0, 0.0))
    check("North facade center anchor", abs(north[0]) < 1e-9 and abs(north[1] - 1.0) < 1e-9 and north[2:4] == (0.0, 1.0))
    check("South facade center anchor", abs(south[0]) < 1e-9 and abs(south[1] + 1.0) < 1e-9 and south[2:4] == (0.0, -1.0))

    # Advance the exact pre-settlement RNG stream used by _build_stream_chunk.
    def advance_to_settlement(cx: int, cy: int):
        rng = random.Random(obj._chunk_seed(cx, cy, 101))
        biome = obj._biome_at((cx + 0.5) * obj.CHUNK_SIZE, (cy + 0.5) * obj.CHUNK_SIZE)
        settlement = obj._settlement_kind(cx, cy)
        city = settlement == "CITY"
        village = settlement == "VILLAGE"
        center = obj._settlement_center(cx, cy) if settlement else None
        clear_radius = 30.5 if city else 20.5 if village else 0.0
        prop_count = 10 if biome in ("EMERALD FOREST", "MISTWOOD") else 6
        for _ in range(prop_count):
            x = cx * obj.CHUNK_SIZE + rng.uniform(5, obj.CHUNK_SIZE - 5)
            y = cy * obj.CHUNK_SIZE + rng.uniform(5, obj.CHUNK_SIZE - 5)
            road_dist, road_width = obj._road_info(x, y)
            if (
                max(abs(x), abs(y)) < obj.STREAM_CORE_HALF
                or obj._in_utopia_sanctuary(x, y, 8.0)
                or obj._river_water_z(x, y) is not None
                or road_dist < road_width * 1.7
            ):
                continue
            _ = obj._height(x, y)
            in_clearance = center is not None and math.hypot(x - center[0], y - center[1]) < clear_radius
            if in_clearance:
                if biome in ("RED CANYONS", "SUNSTONE DESERT"):
                    rng.uniform(1.8, 4.8); rng.uniform(0.5, 1.4); rng.uniform(0.5, 1.3)
                elif biome == "LUMINOUS MARSH":
                    rng.uniform(0.18, 0.42)
                elif biome == "ASH WASTES":
                    rng.uniform(0.35, 0.72)
                elif biome not in ("EMERALD FOREST", "MISTWOOD", "FROST HIGHLANDS"):
                    rng.uniform(0.32, 0.70)
                continue
            if biome in ("EMERALD FOREST", "MISTWOOD", "FROST HIGHLANDS"):
                pass  # tree construction consumes no RNG
            elif biome in ("RED CANYONS", "SUNSTONE DESERT"):
                rng.uniform(1.8, 4.8); rng.uniform(0.5, 1.4); rng.uniform(0.5, 1.3)
            elif biome == "LUMINOUS MARSH":
                rng.uniform(0.18, 0.42)
            elif biome == "ASH WASTES":
                rng.uniform(0.35, 0.72)
            else:
                rng.uniform(0.32, 0.70)
        return rng, city

    baseline = {
        (-5, -1): {
            "count": 6,
            "rng": "40f9ee7f2abe4d6ad09a38055f82d93fb229de3e7bc0e51da28f9a8473cafc89",
            "obstacles": [
                (-339.429609503456, -38.574234227704, 2.019305097479),
                (-347.443546911533, -32.130196760177, 1.973260550553),
                (-349.656746922413, -29.753528859188, 2.169428488903),
                (-358.198952216035, -27.083673454694, 2.301695955040),
                (-358.209246053541, -35.941048116331, 1.884249841020),
                (-357.988708959849, -42.600190680796, 1.827336512718),
            ],
        },
        (-6, -8): {"count": 21, "rng": "2e3041be9a3e8784e64d731ac68816cdfc51bdf8778a99b386cc0b60250d00ac"},
        (7, 2): {"count": 12, "rng": "ba311ae27d7ceb6e55fa76c75930e61c80fda848cc280b121841f9de4eea99bc"},
    }
    for chunk, expected in baseline.items():
        rng, city = advance_to_settlement(*chunk)
        obj.proc_obstacles[chunk] = []
        root = NodePath(f"verify-{chunk[0]}-{chunk[1]}")
        obj._build_proc_settlement(*chunk, root, rng, city)
        entrance_count = len(root.findAllMatches("**/*sealed-threshold-root"))
        state_hash = hashlib.sha256(pickle.dumps(rng.getstate())).hexdigest()
        check(f"{chunk} entrance count", entrance_count == expected["count"], f"count={entrance_count}")
        check(f"{chunk} RNG preserved vs Pass 22", state_hash == expected["rng"], state_hash)
        if "obstacles" in expected:
            actual = [tuple(round(v, 12) for v in row) for row in obj.proc_obstacles[chunk]]
            check(f"{chunk} obstacles preserved vs Pass 22", actual == expected["obstacles"], f"count={len(actual)}")
        root.removeNode()
except Exception as exc:
    check("Panda3D placement/entrance runtime", False, repr(exc))

# HoloVerse native-dimension contract.
responder_path = ROOT / "holoverse" / "holoverse_dimension.json"
identity_path = ROOT / "holoverse" / "identity.json"
dimension_path = ROOT / "dimension.json"
adapter_path = ROOT / "holoverse_native_adapter.py"
check("HoloVerse responder exists", responder_path.is_file())
check("HoloVerse identity exists", identity_path.is_file())
check("Root dimension manifest exists", dimension_path.is_file())
check("Native adapter exists", adapter_path.is_file())
if responder_path.is_file():
    responder = json.loads(responder_path.read_text(encoding="utf-8"))
    check("Responder protocol", responder.get("protocol") == "holoverse_responder_v1")
    check("Responder id", responder.get("id") == "glyphbound")
    check("Responder compatibility native", responder.get("compatibility") == "native")
    check("Responder host contract", responder.get("host_contract") == "holoverse_dimension_v1")
    check("Responder adapter", responder.get("native_adapter") == "holoverse_native_adapter.py")
if identity_path.is_file():
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    check("Stable HoloVerse UUID", identity.get("dimension_id") == "c66bd2c6-86a5-48bd-8f09-1ccca083a93f")
if dimension_path.is_file():
    manifest = json.loads(dimension_path.read_text(encoding="utf-8"))
    check("Root manifest native", manifest.get("compatibility") == "native")
    check("Root manifest host contract", manifest.get("host_contract") == "holoverse_dimension_v1")
if adapter_path.is_file():
    adapter_src = adapter_path.read_text(encoding="utf-8", errors="replace")
    check("Adapter host contract constant", 'HOST_CONTRACT = "holoverse_dimension_v1"' in adapter_src)
    check("Adapter never creates ShowBase", "ShowBase(" not in adapter_src)
    check("Adapter does not bind TAB", 'accept("tab"' not in adapter_src and "accept('tab'" not in adapter_src)
    check("Adapter cleanup calls hosted shutdown", "shutdown_hosted" in adapter_src)
    check("Adapter queues host return", "return_from_native_mode" in adapter_src)
check("Hosted runtime supports existing ShowBase", "def __init__(self, host_base=None, hosted_return_callback=None)" in source)
check("Hosted world root isolated", 'attachNewNode("glyphbound-native-world")' in source)
check("Hosted present root isolated", 'attachNewNode("glyphbound-native-present")' in source)
check("Hosted HUD root isolated", 'attachNewNode("glyphbound-native-hud")' in source)
check("Hosted update entry", "def hosted_update" in source)
check("Hosted cleanup entry", "def shutdown_hosted" in source)
check("Native portal callback", 'self.hosted_return_callback("glyphbound-portal")' in source)
check("Native import skips standalone PRC mutation", "if not HOLOVERSE_NATIVE_IMPORT:" in source)
check("README documents HoloVerse native mode", "HOLOVERSE NATIVE DIMENSION" in readme and "TAB" in readme)

residue = [p for p in ROOT.rglob("*") if p.name == "__pycache__" or p.suffix == ".pyc"]
check("No cache/bytecode residue", not residue, ", ".join(str(p.relative_to(ROOT)) for p in residue[:5]))

passed = sum(ok for _, ok, _ in checks)
print(f"Glyphbound Pass 24 HoloVerse native verifier: {passed}/{len(checks)} PASS")
for name, ok, detail in checks:
    suffix = f" -- {detail}" if detail else ""
    print(f"{'PASS' if ok else 'FAIL'}  {name}{suffix}")
sys.exit(0 if passed == len(checks) else 1)
