from __future__ import annotations

import ast
import builtins
import importlib
import json
import math
import sys
import types
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"
REPORT = ROOT / "verification" / "reports" / "pass29_code_audit.json"


def source_files():
    return sorted(p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def module_symbols(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 12))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    names.add(alias.asname or alias.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        names.add(sub.id)
    return names


def compile_and_ast_checks() -> dict:
    files = source_files()
    syntax_errors = []
    duplicate_defs = []
    mutable_defaults = []
    unknown_self_calls = []
    unexpected_recursion = []
    allowed_recursive = {("crash_reporter.py", "CrashReporter", "_safe_value")}

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        src = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=rel, feature_version=(3, 12))
            compile(tree, rel, "exec")
        except Exception as exc:
            syntax_errors.append({"file": rel, "error": f"{type(exc).__name__}: {exc}"})
            continue

        def scope_duplicates(body, scope):
            found = defaultdict(list)
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    found[node.name].append(node.lineno)
            for name, lines in found.items():
                if len(lines) > 1:
                    duplicate_defs.append({"file": rel, "scope": scope, "name": name, "lines": lines})
            for node in body:
                if isinstance(node, ast.ClassDef):
                    scope_duplicates(node.body, f"{scope}.{node.name}")
        scope_duplicates(tree.body, rel)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        mutable_defaults.append({"file": rel, "function": node.name, "line": node.lineno})

        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            # Method-call integrity is enforced on shipping runtime classes.
            # Tooling classes may intentionally call inherited visitor methods
            # such as ast.NodeTransformer.generic_visit().
            if not (path.parent == GAME or path == ROOT / "main.py"):
                continue
            methods = {n.name for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            assigned = set()
            calls = Counter()
            for node in ast.walk(cls):
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        for sub in ast.walk(target):
                            if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == "self":
                                assigned.add(sub.attr)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                        calls[node.func.attr] += 1
            for name, count in calls.items():
                if name not in methods and name not in assigned:
                    unknown_self_calls.append({"file": rel, "class": cls.name, "method": name, "calls": count})
            for fn in [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                lines = []
                for node in ast.walk(fn):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        if isinstance(node.func.value, ast.Name) and node.func.value.id == "self" and node.func.attr == fn.name:
                            lines.append(node.lineno)
                if lines and (path.name, cls.name, fn.name) not in allowed_recursive:
                    unexpected_recursion.append({"file": rel, "class": cls.name, "method": fn.name, "lines": lines})

    return {
        "python_files": len(files),
        "python_312_parse_errors": syntax_errors,
        "duplicate_definitions": duplicate_defs,
        "mutable_default_arguments": mutable_defaults,
        "unknown_self_method_calls": unknown_self_calls,
        "unexpected_direct_recursion": unexpected_recursion,
    }


def relative_import_checks() -> dict:
    modules = {p.stem: module_symbols(p) for p in GAME.glob("*.py")}
    issues = []
    for path in sorted(GAME.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 12))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level != 1 or not node.module:
                continue
            target = node.module.split(".")[0]
            if target not in modules:
                issues.append({"file": path.name, "line": node.lineno, "module": node.module, "error": "missing module"})
                continue
            exported = modules[target]
            for alias in node.names:
                if alias.name != "*" and alias.name not in exported:
                    issues.append({"file": path.name, "line": node.lineno, "module": node.module, "name": alias.name, "error": "missing symbol"})
    return {"issues": issues}


def json_checks() -> dict:
    failures = []
    count = 0
    for path in sorted(ROOT.rglob("*.json")):
        if "__pycache__" in path.parts:
            continue
        count += 1
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            failures.append({"file": path.relative_to(ROOT).as_posix(), "error": f"{type(exc).__name__}: {exc}"})
    return {"json_files": count, "failures": failures}


def renderer_static_contract() -> dict:
    render_path = GAME / "render.py"
    sim_path = GAME / "sim.py"
    render_tree = ast.parse(render_path.read_text(encoding="utf-8"), feature_version=(3, 12))
    sim_tree = ast.parse(sim_path.read_text(encoding="utf-8"), feature_version=(3, 12))
    renderer = next(n for n in render_tree.body if isinstance(n, ast.ClassDef) and n.name == "Renderer")
    mission = next(n for n in sim_tree.body if isinstance(n, ast.ClassDef) and n.name == "Mission")
    renderer_methods = {n.name for n in renderer.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    mission_attrs = {n.name for n in mission.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for node in ast.walk(mission):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == "self":
                        mission_attrs.add(sub.attr)
    mission_refs = Counter()
    for node in ast.walk(render_tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "mission":
            mission_refs[node.attr] += 1
    missing_mission_attrs = sorted(name for name in mission_refs if name not in mission_attrs)

    foundation = next(n for n in renderer.body if isinstance(n, ast.FunctionDef) and n.name == "_draw_obstacle_foundation")
    recursive_foundation = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "self"
        and node.func.attr == "_draw_obstacle_foundation"
        for node in ast.walk(foundation)
    )

    return {
        "draw_world_obstacle_defined": "_draw_world_obstacle" in renderer_methods,
        "obstacle_foundation_defined": "_draw_obstacle_foundation" in renderer_methods,
        "obstacle_foundation_not_recursive": not recursive_foundation,
        "renderer_mission_attribute_mismatches": missing_mission_attrs,
    }


def app_api_contract() -> dict:
    app_tree = ast.parse((GAME / "app.py").read_text(encoding="utf-8"), feature_version=(3, 12))
    mapping = {
        "renderer": ("render.py", "Renderer"),
        "audio": ("audio.py", "AudioManager"),
        "microsoft_runtime": ("microsoft_runtime.py", "MicrosoftRuntime"),
        "achievement_tracker": ("achievements.py", "AchievementTracker"),
    }
    missing = []
    for attr, (file_name, class_name) in mapping.items():
        tree = ast.parse((GAME / file_name).read_text(encoding="utf-8"), feature_version=(3, 12))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
        methods = {n.name for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        calls = Counter()
        for node in ast.walk(app_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                base = node.func.value
                if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and base.value.id == "self" and base.attr == attr:
                    calls[node.func.attr] += 1
        for method, count in calls.items():
            if method not in methods:
                missing.append({"object": attr, "method": method, "calls": count})

    assigned_states = set()
    render_states = set()
    for node in ast.walk(app_tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self" and target.attr == "state":
                    assigned_states.add(node.value.value)
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Attribute):
            if isinstance(node.left.value, ast.Name) and node.left.value.id == "self" and node.left.attr == "state":
                for comp in node.comparators:
                    if isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                        render_states.add(comp.value)
                    elif isinstance(comp, (ast.Set, ast.Tuple, ast.List)):
                        for elt in comp.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                render_states.add(elt.value)
    return {
        "missing_component_methods": missing,
        "assigned_states": sorted(assigned_states),
        "referenced_states": sorted(render_states),
        "states_without_any_handler_reference": sorted(assigned_states - render_states),
    }


def install_pygame_geometry_stub() -> None:
    if "pygame" in sys.modules:
        return
    pygame = types.ModuleType("pygame")
    class error(Exception):
        pass
    class Vector2:
        __slots__ = ("x", "y")
        def __init__(self, x=0.0, y=None):
            if y is None:
                if isinstance(x, Vector2): self.x, self.y = float(x.x), float(x.y)
                elif hasattr(x, "__len__") and not isinstance(x, (str, bytes)):
                    vals = list(x); self.x, self.y = float(vals[0]), float(vals[1])
                else: self.x = self.y = float(x)
            else: self.x, self.y = float(x), float(y)
        def __iter__(self): return iter((self.x, self.y))
        def __getitem__(self, i): return (self.x, self.y)[i]
        def __add__(self, other): other = Vector2(other); return Vector2(self.x + other.x, self.y + other.y)
        def __radd__(self, other): return self.__add__(other)
        def __sub__(self, other): other = Vector2(other); return Vector2(self.x - other.x, self.y - other.y)
        def __rsub__(self, other): other = Vector2(other); return Vector2(other.x - self.x, other.y - self.y)
        def __mul__(self, scalar): return Vector2(self.x * float(scalar), self.y * float(scalar))
        def __rmul__(self, scalar): return self.__mul__(scalar)
        def __truediv__(self, scalar): return Vector2(self.x / float(scalar), self.y / float(scalar))
        def __neg__(self): return Vector2(-self.x, -self.y)
        def length_squared(self): return self.x * self.x + self.y * self.y
        def length(self): return math.sqrt(self.length_squared())
        def normalize(self):
            length = self.length(); return Vector2(self.x / length, self.y / length) if length else Vector2()
        def distance_to(self, other): return (self - Vector2(other)).length()
        def distance_squared_to(self, other): return (self - Vector2(other)).length_squared()
        def rotate(self, degrees):
            angle = math.radians(float(degrees)); c, s = math.cos(angle), math.sin(angle)
            return Vector2(self.x*c - self.y*s, self.x*s + self.y*c)
    class Rect:
        __slots__ = ("x", "y", "width", "height")
        def __init__(self, *args):
            if len(args) == 1:
                val = args[0]
                if isinstance(val, Rect): args = (val.x, val.y, val.width, val.height)
                else: args = tuple(val)
            self.x, self.y, self.width, self.height = [int(round(float(v))) for v in args]
        @property
        def left(self): return self.x
        @property
        def top(self): return self.y
        @property
        def right(self): return self.x + self.width
        @property
        def bottom(self): return self.y + self.height
        @property
        def centerx(self): return self.x + self.width // 2
        @centerx.setter
        def centerx(self, value): self.x = int(round(value)) - self.width // 2
        @property
        def centery(self): return self.y + self.height // 2
        @centery.setter
        def centery(self, value): self.y = int(round(value)) - self.height // 2
        @property
        def center(self): return (self.centerx, self.centery)
        @center.setter
        def center(self, value): self.centerx, self.centery = value
        @property
        def midleft(self): return (self.left, self.centery)
        @property
        def midright(self): return (self.right, self.centery)
        @property
        def midtop(self): return (self.centerx, self.top)
        @property
        def midbottom(self): return (self.centerx, self.bottom)
        def copy(self): return Rect(self)
        def move(self, dx, dy): return Rect(self.x + int(dx), self.y + int(dy), self.width, self.height)
        def collidepoint(self, *point):
            if len(point) == 1: point = point[0]
            x, y = (point.x, point.y) if isinstance(point, Vector2) else point
            return self.left <= x < self.right and self.top <= y < self.bottom
        def inflate(self, dx, dy): return Rect(self.x - int(dx)//2, self.y - int(dy)//2, self.width + int(dx), self.height + int(dy))
        def colliderect(self, other): return self.left < other.right and self.right > other.left and self.top < other.bottom and self.bottom > other.top
        def contains(self, other): return self.left <= other.left and self.right >= other.right and self.top <= other.top and self.bottom >= other.bottom
        def clipline(self, *args):
            if len(args) == 1:
                vals = args[0]
                if len(vals) == 4: x1, y1, x2, y2 = vals
                else: (x1, y1), (x2, y2) = vals
            elif len(args) == 2:
                p1, p2 = args; x1, y1 = Vector2(p1); x2, y2 = Vector2(p2)
            else: x1, y1, x2, y2 = args
            dx, dy = x2-x1, y2-y1
            p = (-dx, dx, -dy, dy); q = (x1-self.left, self.right-x1, y1-self.top, self.bottom-y1)
            u1, u2 = 0.0, 1.0
            for pi, qi in zip(p, q):
                if pi == 0:
                    if qi < 0: return ()
                else:
                    t = qi / pi
                    if pi < 0:
                        if t > u2: return ()
                        if t > u1: u1 = t
                    else:
                        if t < u1: return ()
                        if t < u2: u2 = t
            return ((x1+u1*dx, y1+u1*dy), (x1+u2*dx, y1+u2*dy))
    class Draw:
        def __getattr__(self, name): return lambda *args, **kwargs: None
    class Image:
        def load(self, *args, **kwargs): raise error("image unavailable in audit stub")
    class Transform:
        def smoothscale(self, surface, size): return surface
    class Surface:
        def __init__(self, *args, **kwargs): self._clip = None
        def get_clip(self): return self._clip
        def set_clip(self, value=None): self._clip = value
        def blit(self, *args, **kwargs): return None
        def fill(self, *args, **kwargs): return None
        def copy(self): return self
        def set_alpha(self, *args, **kwargs): return None
        def get_width(self): return 1
        def get_height(self): return 1
        def get_rect(self, **kwargs):
            rect = Rect(0, 0, 1, 1)
            if "center" in kwargs: rect.center = kwargs["center"]
            return rect
    pygame.error = error
    pygame.Vector2 = Vector2
    pygame.Rect = Rect
    pygame.Surface = Surface
    pygame.draw = Draw()
    pygame.image = Image()
    pygame.transform = Transform()
    pygame.SRCALPHA = 1
    sys.modules["pygame"] = pygame


def runtime_contract() -> dict:
    # The audit deliberately substitutes geometry/drawing only when pygame is not
    # available. This is not a replacement for native pygame testing; it makes
    # mission construction + first-frame renderer contracts executable in CI.
    try:
        import pygame  # noqa: F401
        using_stub = False
    except Exception:
        install_pygame_geometry_stub()
        using_stub = True

    sys.path.insert(0, str(ROOT))
    from game.data import HEROES
    from game.sim import Mission
    from game.render import Renderer

    mission_results = []
    heroes = list(HEROES)
    for quest in ("purge", "recovery", "rescue"):
        for layout_seed in range(3):
            for lead in heroes:
                sidekicks = tuple(h for h in heroes if h != lead)[:2]
                mission = Mission(lead, quest, seed=layout_seed, sidekick_keys=sidekicks)
                preflight = mission.validate_launch_state()
                mission.update(0.05)
                mission_results.append({"quest": quest, "layout_seed": layout_seed, "lead": lead, "party_size": preflight["party_size"], "status": "PASS"})

    # Exercise the battlefield site renderer itself. This is the exact path that
    # Pass 28 could not enter because _draw_world_obstacle had been lost.
    class Canvas:
        def get_clip(self): return None
        def set_clip(self, *args, **kwargs): return None
        def blit(self, *args, **kwargs): return None
        def fill(self, *args, **kwargs): return None
    class Textures:
        def get(self, *args, **kwargs): return None
    class Fonts:
        xs = sm = md = lg = xl = hero = object()

    renderer = Renderer.__new__(Renderer)
    renderer.canvas = Canvas()
    renderer.world_textures = Textures()
    renderer.fonts = Fonts()
    renderer.time = 0.0
    renderer.high_contrast = False
    renderer.reduced_motion = False
    renderer.text = lambda *args, **kwargs: None

    site_results = []
    for quest in ("purge", "recovery", "rescue"):
        for layout_seed in range(3):
            lead = heroes[(layout_seed + (0 if quest == "purge" else 1 if quest == "recovery" else 2)) % len(heroes)]
            sidekicks = tuple(h for h in heroes if h != lead)[:2]
            mission = Mission(lead, quest, seed=layout_seed, sidekick_keys=sidekicks)
            renderer.current_mission = mission
            renderer._draw_contract_site(mission)
            # Also hit destroyed-cover presentation explicitly.
            destructible = next((obj for obj in mission.world_obstacles if obj.destructible), None)
            if destructible is not None:
                destructible.destroyed = True
                renderer._draw_world_obstacle(destructible, renderer._visual_env(mission))
            site_results.append({"quest": quest, "layout_seed": layout_seed, "status": "PASS"})

    return {
        "pygame_geometry_stub_used": using_stub,
        "mission_first_update_matrix": mission_results,
        "mission_first_update_count": len(mission_results),
        "contract_site_render_matrix": site_results,
        "contract_site_render_count": len(site_results),
    }


def main() -> int:
    compile_checks = compile_and_ast_checks()
    import_checks = relative_import_checks()
    json_result = json_checks()
    renderer = renderer_static_contract()
    app = app_api_contract()
    runtime = runtime_contract()

    checks = {
        "python_312_compile": not compile_checks["python_312_parse_errors"],
        "no_duplicate_definitions": not compile_checks["duplicate_definitions"],
        "no_mutable_default_arguments": not compile_checks["mutable_default_arguments"],
        "no_unknown_self_calls": not compile_checks["unknown_self_method_calls"],
        "no_unexpected_direct_recursion": not compile_checks["unexpected_direct_recursion"],
        "relative_imports_resolve": not import_checks["issues"],
        "all_json_parses": not json_result["failures"],
        "draw_world_obstacle_restored": renderer["draw_world_obstacle_defined"],
        "obstacle_foundation_not_recursive": renderer["obstacle_foundation_not_recursive"],
        "renderer_mission_contract": not renderer["renderer_mission_attribute_mismatches"],
        "app_component_api_contract": not app["missing_component_methods"],
        "app_states_have_handlers": not app["states_without_any_handler_reference"],
        "mission_first_update_36_of_36": runtime["mission_first_update_count"] == 36,
        "contract_site_render_9_of_9": runtime["contract_site_render_count"] == 9,
    }
    result = {
        "pass29_full_code_audit": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "compile_static": compile_checks,
        "relative_imports": import_checks,
        "json": json_result,
        "renderer_contract": renderer,
        "app_contract": app,
        "runtime_contract": runtime,
        "native_runtime_note": "Geometry/drawing compatibility stub is used only when pygame is unavailable; native Windows pygame remains a separate acceptance gate.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
